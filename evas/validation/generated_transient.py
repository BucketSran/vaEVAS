#!/usr/bin/env python3
"""N15 bounded generator: timer sample/hold and integral cases with exact oracles.

This module is validation-side tooling; it does not change any production code,
existing checker or historical result.  It generates small deterministic
scalar Verilog-A models from a fixed set of *known supported templates* (no
random language grammar), derives the expected answer independently with exact
``Fraction`` arithmetic, runs the case through the public ``compile_sources`` +
``transient`` boundary, classifies the outcome honestly, and reduces any
failure to a smaller case that preserves the diagnosed failure class.

Mathematics (independent of the kernel)
---------------------------------------
Both templates hold one scalar event state ``q``:

* ``hold``:     ``V(y,r)<+q;``                -- y(t) = q(t), piecewise constant.
* ``integral``: ``V(y,r)<+idt(q,ic);``        -- y(t) = ic + integral of q.

``@(initial_step)`` sets ``q=q0``; each ``@(timer(t_j,0,1e-9))`` sets ``q=v_j``
and increments an integer counter ``n``.  Observations are post-event values,
so the exact answer uses breakpoints ``0 < t_1 < ... < t_k < stop``::

    held(t) = q0                      for t <  t_1
            = v_j                     for t_j <= t < t_{j+1}
    y_hold(t)     = held(t)
    y_integral(t) = ic + sum over segments of (breakpoint span) * held(span start)

Every generated time is a multiple of 1/4 and every value a multiple of 1/2,
so all breakpoints, held values and exact areas are exactly representable in
binary64; the ``Fraction`` oracle is compared with a tight absolute delta
rather than a loose tolerance.  Expected event records are one ``timer`` event
per breakpoint with ``after == [v_j, j]``; expected per-sample states are
``[held(t), index(t)]``.

Negative controls (checker calibration)
---------------------------------------
``corrupt_oracle`` builds deliberately wrong expectations; ``calibrate`` proves
the checker rejects each of them instead of silently accepting:

* ``wrong_value``    -- one expected node value is shifted beyond delta;
* ``missing_event``  -- one expected event row is removed;
* ``duplicate_event``-- one expected event row is duplicated.

``MUTATIONS`` are model-side defects (the equivalent real failure), used by the
reducer tests to show reduction preserves the original failure.

Outcome classification
----------------------
A process that does not crash is *not* numerical acceptance.  Outcomes are:
``pass``, ``numerical_fail`` (value/state mismatch), ``event_fail`` (event
record mismatch), the kernel diagnostic categories ``unsupported``,
``numerical``, ``resource``, ``protocol``, ``infrastructure``, ``version``, and
``invalid_case`` when the generator's own template fails to compile (a
generator defect, not a simulator verdict).

Failure reduction
-----------------
``reduce_failure`` re-runs bounded simplifications (timer-prefix truncation,
value zeroing, both) with the same model mutation and accepts a reduction only
when the diagnosed failure class (outcome + failure kind) is preserved.  The
reduction record always retains the seed id, the original case digest and the
complete original failure; a smaller case that changes the failure class is
rejected and reported as an attempt.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "runs" / "night-generated"

# Resource bounds for generation and execution.
MAX_TIMERS = 5                 # timers per generated case
TIME_GRID = tuple(Fraction(i, 4) for i in range(1, 37))   # 0.25 .. 9.0
VALUE_GRID = tuple(Fraction(i, 2) for i in range(-4, 5))  # -2 .. 2 in halves
IC_GRID = tuple(Fraction(i, 2) for i in range(-2, 3))     # -1 .. 1
MAX_OUTPUT_TIMES = 16          # samples per case
PER_RUN_TIMEOUT = 30.0         # seconds per kernel execution
MAX_REDUCTION_RUNS = 12        # kernel executions per reduction

# Checker setting shared by every generated case; all exact values are
# binary64-representable, so a tight delta is meaningful.
VALUE_DELTA = Fraction(1, 10**9)
VABSTOL = 1e-10
REL_TOL = 0.0
TIMER_TOL = 1e-9

# Kernel diagnostic kinds -> honest outcome classes (mirrors evas.errors
# categories; only kinds the public transport can raise are listed).
KERNEL_OUTCOMES = {
    "unsupported": "unsupported",
    "numerical": "numerical",
    "resource": "resource",
    "protocol": "protocol",
    "infrastructure": "infrastructure",
    "version": "version",
    "invalid_input": "invalid_case",
    "internal": "infrastructure",
    # An unrecognized diagnostic category is reported as such; it is not
    # laundered into a supported/infrastructure claim.
    "unknown": "unknown_diagnostic",
}

FAIL_OUTCOMES = ("numerical_fail", "event_fail")


def _fmt(value: Fraction) -> str:
    """Exact binary64 literal for a dyadic rational."""
    result = repr(float(value))
    if float(result) != value:
        raise ValueError(f"value {value} is not binary64-exact")
    return result


# --------------------------------------------------------------------------
# Generation (deterministic from the seed; no random grammar, fixed templates)
# --------------------------------------------------------------------------

def generate_case(seed: int) -> dict:
    """Build one bounded case deterministically from ``seed``."""
    rng = random.Random(seed)
    template = rng.choice(("hold", "integral"))
    count = rng.randint(1, MAX_TIMERS)
    times = sorted(rng.sample(TIME_GRID, count))
    values = [rng.choice(VALUE_GRID) for _ in times]
    case = {
        "seed": seed,
        "template": template,
        "q0": rng.choice(VALUE_GRID),
        "ic": rng.choice(IC_GRID) if template == "integral" else Fraction(0),
        "events": [dict(time=t, value=v) for t, v in zip(times, values)],
        "stop": times[-1] + Fraction(rng.randint(1, 4), 4),
    }
    return _finalize(case)


def _finalize(case: dict) -> dict:
    """Validate bounds/invariants and attach the case digest."""
    times = [e["time"] for e in case["events"]]
    if not (1 <= len(times) <= MAX_TIMERS):
        raise ValueError("timer count out of bounds")
    if any(not (a < b) for a, b in zip(times, times[1:])):
        raise ValueError("timer times must be strictly increasing")
    if not all(Fraction(0) < t < Fraction(case["stop"]) <= 10 for t in times):
        raise ValueError("timer times must be inside (0, stop<=10]")
    if case["template"] not in ("hold", "integral"):
        raise ValueError("unknown template")
    canonical = json.dumps(_portable({k: v for k, v in case.items() if k != "digest"}), sort_keys=True)
    case["digest"] = hashlib.sha256(canonical.encode()).hexdigest()[:16]
    return case


def fixed_case(template: str, q0, ic, events, stop) -> dict:
    """Hand-specified case with the same invariants as a generated one."""
    return _finalize(dict(seed=0, template=template, q0=Fraction(q0), ic=Fraction(ic),
                          events=[dict(time=Fraction(t), value=Fraction(v)) for t, v in events],
                          stop=Fraction(stop)))


def output_times(case: dict) -> list[Fraction]:
    """Sample grid: 0, every breakpoint, segment midpoints and stop."""
    points = [Fraction(0)] + [e["time"] for e in case["events"]] + [Fraction(case["stop"])]
    mid = [(a + b) / 2 for a, b in zip(points, points[1:])]
    times = sorted(set(points + mid))
    if len(times) > MAX_OUTPUT_TIMES:
        raise ValueError("output grid exceeded the bound")
    return times


def _portable(value):
    """JSON-serializable form (Fractions as exact 'num/den' strings)."""
    if isinstance(value, Fraction):
        return f"{value.numerator}/{value.denominator}"
    if isinstance(value, float) and not math.isfinite(value):
        return {"nonfinite_float": repr(value)}
    if isinstance(value, dict):
        return {k: _portable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_portable(v) for v in value]
    return value


# --------------------------------------------------------------------------
# Independent exact oracle (pure Fraction arithmetic; never consults the kernel)
# --------------------------------------------------------------------------

def held_value(case: dict, t: Fraction) -> Fraction:
    """Exact post-event held value q(t)."""
    current = Fraction(case["q0"])
    for event in case["events"]:
        if t >= event["time"]:
            current = Fraction(event["value"])
    return current


def event_index(case: dict, t: Fraction) -> int:
    """Number of timers that fired at or before t."""
    return sum(t >= e["time"] for e in case["events"])


def exact_output(case: dict, t: Fraction) -> Fraction:
    """Exact answer for node y at time t."""
    if case["template"] == "hold":
        return held_value(case, t)
    total = Fraction(case["ic"])
    previous = Fraction(0)
    for event in case["events"]:
        if t <= event["time"]:
            break
        total += (Fraction(event["time"]) - previous) * held_value(case, previous)
        previous = Fraction(event["time"])
    total += (t - previous) * held_value(case, previous)
    return total


def expected(case: dict) -> dict:
    """Full independent expectation: node values, events and states."""
    times = output_times(case)
    nodes = {"y": [exact_output(case, t) for t in times]}
    if case["template"] == "integral":
        nodes["h"] = [held_value(case, t) for t in times]
    nodes["nc"] = [Fraction(event_index(case, t)) for t in times]
    events = [dict(time=Fraction(e["time"]), kind="timer", event=i,
                   before=[Fraction(case["q0"] if i == 0 else case["events"][i-1]["value"]), Fraction(i)],
                   after=[Fraction(e["value"]), Fraction(i + 1)])
              for i, e in enumerate(case["events"])]
    states = [[held_value(case, t), Fraction(event_index(case, t))] for t in times]
    return dict(times=times, nodes=nodes, events=events, states=states)


# --------------------------------------------------------------------------
# Model rendering (fixed supported templates + model-side defect mutations)
# --------------------------------------------------------------------------

MUTATIONS = ("drop_timer", "duplicate_timer", "ic_bias", "value_bias",
             "unsupported_feedback")


def model_source(case: dict, mutation: dict | None = None) -> str:
    """Render the Verilog-A source; ``mutation`` deliberately injects a defect."""
    mutation = dict(mutation or {})
    unknown = set(mutation) - set(MUTATIONS)
    if unknown:
        raise ValueError(f"unknown mutation keys {sorted(unknown)}")
    by_time = {Fraction(e["time"]): i for i, e in enumerate(case["events"])}

    def dropped(t: Fraction) -> bool:
        return mutation.get("drop_timer") is not None and by_time[Fraction(t)] == mutation["drop_timer"]

    def biased(t: Fraction) -> Fraction:
        value = Fraction(case["events"][by_time[Fraction(t)]]["value"])
        if mutation.get("value_bias", {}).get("index") == by_time[Fraction(t)]:
            value += Fraction(mutation["value_bias"]["eps"])
        return value

    timers = []
    for event in case["events"]:
        t = Fraction(event["time"])
        if dropped(t):
            continue
        timers.append(f"@({_timer(t)}) begin q={_fmt(biased(t))}; n=n+1; end")
        if mutation.get("duplicate_timer") == by_time[t]:
            # A second timer at the same instant must be a *different* state
            # writer: two same-time blocks writing q are an event_conflict
            # rejection (documented settlement semantics), not a duplicate
            # event record.  Writing the auxiliary counter m keeps the model
            # valid while producing two event records at t.
            timers.append(f"@({_timer(t)}) begin m=m+1; end")
    ic = Fraction(case["ic"])
    if "ic_bias" in mutation:
        ic += Fraction(mutation["ic_bias"])
    duplicated = mutation.get("duplicate_timer") is not None
    init = f"q={_fmt(Fraction(case['q0']))}; n=0;" + (" m=0;" if duplicated else "")
    body = [
        "@(initial_step) begin " + init + " end",
        *timers,
        "V(y,r)<+" + ("idt(q," + _fmt(ic) + ")" if case["template"] == "integral" else "q") + ";",
    ]
    if mutation.get("unsupported_feedback"):
        # Rejection control: ddt of an event-driven state is a documented
        # unsupported operator (event-state impulses); the outcome must be an
        # honest rejection, never a pass or a crash-based "accepted" verdict.
        # (Integral feedback like idt(q*V(y,r),0) is *supported* implicit
        # dynamics and must not be used as a rejection probe.)
        body.append("V(y,r)<+ddt(q);")
    ports = "u,y,nc,r"
    directions = "input u; output y,nc; inout r;"
    if case["template"] == "integral":
        body.insert(-1, "V(h,r)<+q;")
        ports = "u,y,h,nc,r"
        directions = "input u; output y,h,nc; inout r;"
    body.append("V(nc,r)<+n;")
    if duplicated:
        body.append("V(nd,r)<+m;")
        ports += ",nd"
        directions = directions[:-1] + ",nd;"
        # The duplicated-event record also changes the state vector shape.
    counters = "integer n,m;" if duplicated else "integer n;"
    return (f'`include "disciplines.vams"\n'
            f"module m({ports}); {directions} electrical {ports}; real q; {counters}\n"
            f"analog begin {' '.join(body)} end endmodule\n")


def _timer(t: Fraction) -> str:
    return f"timer({_fmt(t)},0,{TIMER_TOL!r})"


# --------------------------------------------------------------------------
# Execution through the public boundary + honest outcome classification
# --------------------------------------------------------------------------

def execute(case: dict, kernel, *, mutation: dict | None = None,
            timeout: float = PER_RUN_TIMEOUT) -> dict:
    """Compile and run one case through the public compile/transient boundary."""
    from evas import Instance, compile_sources, transient
    connections = dict(u="u", y="y", nc="nc", r="0")
    if case["template"] == "integral":
        connections["h"] = "h"
    if mutation and mutation.get("duplicate_timer") is not None:
        connections["nd"] = "nd"
    program = compile_sources({"generated.va": model_source(case, mutation)},
                              [Instance("dut", "m", connections)])
    times = [float(t) for t in output_times(case)]
    return transient(program, {"u": [[0.0, 0.0], [float(case["stop"]), 0.0]]},
                     times, stop=float(case["stop"]), max_step=float(case["stop"]),
                     kernel=kernel, vabstol=VABSTOL, reltol=REL_TOL, timeout=timeout)


def run_case(case: dict, kernel, *, mutation: dict | None = None,
             timeout: float = PER_RUN_TIMEOUT) -> dict:
    """Compile and run one case; return a full outcome record.

    Never turns a rejection or an error into acceptance: kernel diagnostics are
    classified through their published categories, and non-kernel failures are
    reported as infrastructure, not as passes.
    """
    from evas import CompileError, KernelError
    record = dict(seed=case["seed"], digest=case["digest"], template=case["template"],
                  mutation=dict(mutation or {}), outcome=None, failure_kind=None,
                  mismatches=[], detail={})
    started = time.monotonic()
    try:
        result = execute(case, kernel, mutation=mutation, timeout=timeout)
        times = output_times(case)
    except CompileError as error:
        record.update(outcome="invalid_case", failure_kind="compile_error",
                      detail={"message": str(error), "code": error.diagnostic["code"]})
        return record
    except KernelError as error:
        category = error.diagnostic["category"]
        record.update(outcome=KERNEL_OUTCOMES.get(category, "infrastructure"),
                      failure_kind=error.detail["kind"], detail=dict(error.detail))
        return record
    except (OSError, ValueError, RecursionError, MemoryError) as error:
        record.update(outcome="infrastructure", failure_kind=type(error).__name__,
                      detail={"message": str(error)})
        return record
    mismatches = check(case, result, times)
    record["mismatches"] = mismatches
    record["response"] = result
    record["expectation"] = expected(case)
    record["detail"] = {}
    if isinstance(result, dict):
        record["detail"]["schema_version"] = result.get("schema_version")
        tr = result.get("transient")
        if isinstance(tr, dict) and isinstance(tr.get("events"), list):
            record["detail"]["event_count"] = len(tr["events"])
    record["elapsed_s"] = round(time.monotonic() - started, 3)
    if mismatches:
        kinds = {m["type"] for m in mismatches}
        structural = kinds & {"event_count", "duplicate_event", "event_time", "event_kind", "event_identity"}
        if "response_shape" in kinds:
            record.update(outcome="protocol", failure_kind="invalid_response_shape")
        elif structural or (not kinds & {"value", "state"} and kinds & {"event_before", "event_after"}):
            # Wrong event records are the root cause; the value/state mismatches
            # they cause are collateral and must not mask the event diagnosis.
            record.update(outcome="event_fail", failure_kind=diagnose_event_failure(case, result))
        else:
            nodes = sorted({m.get("node", m["type"]) for m in mismatches if m["type"] == "value"})
            record.update(outcome="numerical_fail", failure_kind=("value_mismatch:" + "+".join(nodes)) if nodes else "state_mismatch")
    else:
        record.update(outcome="pass", failure_kind=None)
    record["witness"] = failure_witness(case, result, record)
    return record


def failure_witness(case, result, record):
    """Keep the affected observable, physical time and error direction stable."""
    if record["outcome"] not in FAIL_OUTCOMES:
        return None
    events = result["transient"]["events"]
    if record["failure_kind"] == "missing_event":
        seen = [Fraction(e["time"]) for e in events]
        missing = [Fraction(e["time"]) for e in case["events"] if Fraction(e["time"]) not in seen]
        return ["missing_event", str(missing[0])] if missing else ["missing_event", "count"]
    if record["failure_kind"] == "duplicate_event":
        seen = [Fraction(e["time"]) for e in events]
        repeated = [t for t in seen if seen.count(t) > 1]
        return ["duplicate_event", str(repeated[0])] if repeated else ["duplicate_event", "count"]
    m = record["mismatches"][0]
    index = m.get("index")
    physical_time = m.get("time", events[index]["time"] if index is not None and m["type"].startswith("event_") else None)
    direction = None
    if m["type"] in ("value", "state", "event_before", "event_after"): direction = 1 if m["actual"] > m["expected"] else -1
    return [m["type"], m.get("node",m.get("state")), physical_time, direction]


def response_shape(result, times, want):
    """Reject missing, extra, nonfinite and mismatched-grid data before values."""
    def finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    try:
        nodes = result["nodes"]; solutions = result["solutions"]; tr = result["transient"]
        names = tr["state_names"]; states = tr["states"]; events = tr["events"]
        if not isinstance(nodes, list) or not all(isinstance(n, str) for n in nodes) or len(set(nodes)) != len(nodes):
            return "invalid node identity"
        if any(node not in nodes for node in want["nodes"]): return "missing required node"
        if not isinstance(names, list) or not all(isinstance(n,str) for n in names) or len(set(names)) != len(names): return "invalid state identity"
        if not {"dut:q","dut:n"}.issubset(names): return "missing required state"
        if len(solutions) != len(times) or len(states) != len(times): return "output/state row count"
        if not all(finite(t) for t in tr["times"]) or list(map(Fraction,tr["times"])) != times:
            return "response time grid"
        for row in solutions:
            values=row["voltages"]
            if len(values)!=len(nodes) or not all(map(finite,values)): return "voltage shape or nonfinite value"
        for row in states:
            if len(row)!=len(names) or not all(map(finite,row)): return "state shape or nonfinite value"
        if not isinstance(events,list): return "invalid event rows"
        for event in events:
            if not isinstance(event,dict): return "invalid event object"
            if not isinstance(event.get("event"),int) or isinstance(event["event"],bool): return "invalid event identity"
            if not finite(event["time"]): return "nonfinite event time"
            for key in ("before","after"):
                if len(event[key])!=len(names) or not all(map(finite,event[key])): return "event state shape or nonfinite value"
        if any(a["time"] > b["time"] for a,b in zip(events,events[1:])): return "event chronology"
    except (KeyError,TypeError,ValueError,OverflowError):
        return "malformed response"
    return None


def check(case: dict, result: dict, times, expectation: dict | None = None) -> list[dict]:
    """Compare a transient result against the independent oracle.

    ``times`` are the requested output times (the validated response keeps the
    requested order but does not echo the grid).  ``expectation`` overrides the
    oracle (used only by calibration controls); the default always recomputes
    the exact answer from the case.
    """
    want = expected(case) if expectation is None else expectation
    mismatches = []
    times = [Fraction(t) for t in times]
    if times != want["times"]:
        mismatches.append(dict(type="time_grid", actual=[float(t) for t in times],
                               expected=[float(t) for t in want["times"]]))
    malformed = response_shape(result, times, want)
    if malformed:
        return mismatches + [dict(type="response_shape", reason=malformed)]
    index = {node: result["nodes"].index(node) for node in want["nodes"]}
    for node, answers in want["nodes"].items():
        for t, row, exact in zip(times, result["solutions"], answers):
            actual = Fraction(row["voltages"][index[node]])
            if abs(actual - exact) > VALUE_DELTA:
                mismatches.append(dict(type="value", node=node, time=float(t),
                                       expected=float(exact), actual=float(actual)))
    state_index=[result["transient"]["state_names"].index(name) for name in ("dut:q","dut:n")]
    actual_events = result["transient"]["events"]
    expected_events = want["events"]
    if len(actual_events) != len(expected_events):
        mismatches.append(dict(type="event_count", actual=len(actual_events),
                               expected=len(expected_events)))
    actual_times = [Fraction(e["time"]) for e in actual_events]
    if len(actual_times) != len(set(actual_times)):
        repeated = sorted({float(t) for t in actual_times if actual_times.count(t) > 1})
        mismatches.append(dict(type="duplicate_event", times=repeated))
    for i, (got, want_event) in enumerate(zip(actual_events, expected_events)):
        if Fraction(got["time"]) != Fraction(want_event["time"]):
            mismatches.append(dict(type="event_time", index=i,
                                   actual=got["time"], expected=float(want_event["time"])))
        if got.get("event") != want_event["event"]:
            mismatches.append(dict(type="event_identity",index=i,time=got["time"],actual=got.get("event"),expected=want_event["event"]))
        if got.get("kind") != want_event["kind"]:
            mismatches.append(dict(type="event_kind", index=i,
                                   actual=got.get("kind"), expected=want_event["kind"]))
        for phase in ("before","after"):
            for name,j,w in zip(("dut:q","dut:n"),state_index,want_event[phase],strict=True):
                actual=got[phase][j]
                if Fraction(actual)!=Fraction(w):
                    mismatches.append(dict(type="event_"+phase,index=i,time=got["time"],state=name,actual=actual,expected=float(w)))
    for i, (got, want_state) in enumerate(zip(result["transient"]["states"], want["states"], strict=True)):
        for name,j,w in zip(("dut:q","dut:n"),state_index,want_state,strict=True):
            actual=got[j]
            if abs(Fraction(actual)-Fraction(w))>VALUE_DELTA:
                mismatches.append(dict(type="state",index=i,time=float(times[i]),state=name,actual=actual,expected=float(w)))
    return mismatches


def diagnose_event_failure(case: dict, result: dict) -> str:
    """Name the diagnosed defect behind an event-record mismatch."""
    actual = len(result["transient"]["events"])
    wanted = len(case["events"])
    times = [Fraction(e["time"]) for e in result["transient"]["events"]]
    if actual < wanted:
        return "missing_event"
    if actual > wanted or len(times) != len(set(times)):
        return "duplicate_event"
    return "event_record_mismatch"


# --------------------------------------------------------------------------
# Negative controls: corrupt oracles and model defects must be rejected
# --------------------------------------------------------------------------

def corrupt_oracle(case: dict, mode: str, index: int = 0) -> dict:
    """Deliberately wrong expectation used to calibrate the checker."""
    want = expected(case)
    if mode == "wrong_value":
        want["nodes"]["y"][index] += 1000 * VALUE_DELTA
    elif mode == "missing_event":
        want["events"].pop(index)
    elif mode == "duplicate_event":
        want["events"].insert(index, dict(want["events"][index]))
    else:
        raise ValueError(f"unknown corruption mode {mode!r}")
    return want


CONTROLS = ("wrong_value", "missing_event", "duplicate_event")


def calibrate(case: dict, result: dict, times) -> dict:
    """Each corrupted oracle must produce mismatches; silence is a calibration failure."""
    report = {}
    for mode in CONTROLS:
        mismatches = check(case, result, times, corrupt_oracle(case, mode))
        detected = any(m["type"] in {"value", "event_count", "duplicate_event"}
                       for m in mismatches)
        report[mode] = dict(detected=detected, mismatch_types=sorted({m["type"] for m in mismatches}))
    return report


def assert_calibration(case: dict, result: dict, times) -> None:
    report = calibrate(case, result, times)
    silent = [mode for mode, entry in report.items() if not entry["detected"]]
    if silent:
        raise AssertionError(f"checker silently accepted corrupted oracles: {silent}")


# --------------------------------------------------------------------------
# Failure reduction (preserves seed, original case and original failure)
# --------------------------------------------------------------------------

def same_failure(original: dict, candidate: dict) -> bool:
    """A reduction is valid only if the diagnosed failure class is preserved."""
    return (original["outcome"] == candidate["outcome"]
            and original["failure_kind"] == candidate["failure_kind"]
            and original.get("witness") is not None
            and original["witness"] == candidate.get("witness"))


def _prefix_case(case: dict, count: int) -> dict:
    events = [dict(e) for e in case["events"][:count]]
    reduced = dict(case, events=events)
    reduced["stop"] = Fraction(events[-1]["time"]) + Fraction(1, 4)
    return _finalize(reduced)


def _zeroed_case(case: dict) -> dict:
    reduced = dict(case, q0=Fraction(0), ic=Fraction(0),
                   events=[dict(e, value=Fraction(0)) for e in case["events"]])
    return _finalize(reduced)


def complexity(case):
    values = [case["q0"],case["ic"]]+[e["value"] for e in case["events"]]
    return (len(case["events"]), sum(v != 0 for v in values), sum(abs(v) for v in values), Fraction(case["stop"]))


def reduction_candidates(case: dict) -> list[dict]:
    """Bounded simplifications, cheapest structural cut first."""
    candidates = []
    for count in range(len(case["events"]) - 1, 0, -1):
        candidates.append(_prefix_case(case, count))
    candidates.append(_zeroed_case(case))
    candidates.append(_zeroed_case(_prefix_case(case, 1)))
    seen, unique = set(), []
    for candidate in candidates:
        if candidate["digest"] not in seen and complexity(candidate) < complexity(case):
            seen.add(candidate["digest"])
            unique.append(candidate)
    return unique[:MAX_REDUCTION_RUNS]


def reduce_failure(case: dict, failure: dict, kernel, *,
                   mutation: dict | None = None, max_runs: int = MAX_REDUCTION_RUNS) -> dict:
    """Reduce a failed case while preserving seed id, original input and failure.

    The returned record always keeps the original failure verbatim; attempts
    that changed the diagnosed failure class are recorded, never hidden.
    """
    if failure["outcome"] not in FAIL_OUTCOMES:
        return dict(seed=case["seed"], reduced=None, attempts=[],
                    note="outcome class is not a checker failure; nothing to reduce")
    attempts = []
    reduced = None
    for candidate in reduction_candidates(case)[:max_runs]:
        outcome = run_case(candidate, kernel, mutation=mutation)
        preserved = same_failure(failure, outcome)
        attempts.append(dict(digest=candidate["digest"], timers=len(candidate["events"]),
                             outcome=outcome["outcome"], failure_kind=outcome["failure_kind"],
                             preserved=preserved, witness=outcome.get("witness"),
                             candidate=candidate, candidate_outcome=outcome))
        if preserved:
            reduced = candidate
            break
    return dict(seed=case["seed"], attempts=attempts, reduced=reduced,
                original_failure=failure, original_case=case, original_digest=case["digest"])


# --------------------------------------------------------------------------
# Batch driver: per-seed machine outcomes kept separate, ids preserved
# --------------------------------------------------------------------------

def kernel_identity(kernel) -> dict:
    path = Path(kernel)
    return dict(path=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def run_batch(seeds, kernel, out_dir: Path, *, reduce_failures: bool = True) -> dict:
    """Run all seeds; write one JSON outcome per seed plus a summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    identity = kernel_identity(kernel)
    summary = dict(kernel=identity, seeds=[], counts={})
    for seed in seeds:
        case = generate_case(seed)
        outcome = run_case(case, kernel)
        record = dict(seed_id=f"seed-{seed}", case=_portable(case),
                      source=model_source(case), outcome=outcome,
                      kernel=identity, checker_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                      requested_settings=dict(vabstol=VABSTOL,reltol=REL_TOL,max_step=float(case["stop"]),stop=float(case["stop"]),
                                              output_times=[float(t) for t in output_times(case)]))
        path = out_dir / f"seed-{seed}.json"
        # Publish original evidence first. A reducer failure must not lose it.
        path.write_text(json.dumps(_portable(record), indent=1, sort_keys=True, allow_nan=False) + "\n")
        if outcome["outcome"] in FAIL_OUTCOMES and reduce_failures:
            try:
                record["reduction"] = reduce_failure(case, outcome, kernel)
            except Exception as error:
                record["reduction_error"] = {"kind":type(error).__name__,"message":str(error)}
            path.write_text(json.dumps(_portable(record), indent=1, sort_keys=True, allow_nan=False) + "\n")
        summary["seeds"].append(dict(seed_id=path.name, outcome=outcome["outcome"],
                                     failure_kind=outcome["failure_kind"]))
        summary["counts"][outcome["outcome"]] = summary["counts"].get(outcome["outcome"], 0) + 1
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    return summary


def _seed_range(text: str) -> list[int]:
    if "-" in text:
        first, last = text.split("-", 1)
        return list(range(int(first), int(last) + 1))
    return [int(item) for item in text.split(",")]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--kernel", default=str(REPO_ROOT / "evas/rust_core/target/debug/evas-kernel"))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--seeds", default="1-12", help="e.g. 1-12 or 3,7,11")
    parser.add_argument("--no-reduce", action="store_true")
    parser.add_argument("--calibrate-only", action="store_true",
                        help="run one seed and only verify the negative controls")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(REPO_ROOT / "evas/src"))
    seeds = _seed_range(args.seeds)
    if args.calibrate_only:
        case = generate_case(seeds[0])
        outcome = run_case(case, args.kernel)
        if outcome["outcome"] != "pass":
            print(json.dumps(outcome, indent=1))
            return 1
        report = calibrate(case, execute(case, args.kernel), output_times(case))
        print(json.dumps(report, indent=1, sort_keys=True))
        return 0 if all(entry["detected"] for entry in report.values()) else 1
    summary = run_batch(seeds, args.kernel, Path(args.out),
                        reduce_failures=not args.no_reduce)
    print(json.dumps(dict(counts=summary["counts"], kernel=summary["kernel"]["sha256"]), indent=1))
    failed = sum(count for kind, count in summary["counts"].items() if kind != "pass")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

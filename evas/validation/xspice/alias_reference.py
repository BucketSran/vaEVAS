"""Independent P0 rational events and closed-form finite-ramp RC responses.

No compiler, kernel or generated C history code supplies expected results.
"""

from fractions import Fraction
import math

from check import sample
from r53_reference import value, accepted_trace


def event(spec):
    return float(Fraction(*spec["event_ns"])) * 1e-9


def captured(spec):
    return float(Fraction(*spec["captured_V"]))


def output(spec, t, rc=False):
    at, q, duration = event(spec), captured(spec), spec["rise_s"]
    knots = [(0.0, 0.0), (at, 0.0), (at + duration, q)]
    return value(knots, t, spec["tau_s"] if rc else 0)


def vectors_valid(wave, names, stop):
    required = ["time", *names]
    return (all(n in wave for n in required) and bool(wave["time"])
            and all(len(wave[n]) == len(wave["time"]) and all(math.isfinite(v) for v in wave[n]) for n in required)
            and all(a <= b for a, b in zip(wave["time"], wave["time"][1:]))
            and wave["time"][0] == 0 and abs(wave["time"][-1] - stop) <= 1e-18)


def score_wave(wave, cfg):
    names = [*cfg["inputs"], *(s[n] for s in cfg["instances"].values() for n in ("output", "rc"))]
    if not vectors_valid(wave, names, cfg["stop"]):
        return {"passed": False, "errors": ["missing/nonfinite/inconsistent vectors or range"]}
    errors, maxima = [], {}
    b = cfg["budgets"]
    for name, knots in cfg["inputs"].items():
        err = max(abs(v - value(knots, t)) for t, v in zip(wave["time"], wave[name]))
        maxima[name] = err
        if err > b["platform_V"]:
            errors.append(name + " stimulus")
    for inst, spec in cfg["instances"].items():
        at = event(spec)
        plateau = edge = rc = 0.0
        for i, t in enumerate(wave["time"]):
            e = abs(wave[spec["output"]][i] - output(spec, t))
            if at - b["event_s"] <= t <= at + spec["rise_s"] + b["event_s"]:
                edge = max(edge, e)
            else:
                plateau = max(plateau, e)
            rc = max(rc, abs(wave[spec["rc"]][i] - output(spec, t, True)))
        maxima[inst] = {"output_platform_V": plateau, "output_edge_V": edge, "RC_all_points_V": rc}
        if plateau > b["platform_V"] or edge > b["edge_V"] or rc > b["rc_V"]:
            errors.append(inst + " independent output/RC")
    return {"passed": not errors, "errors": errors, "max_error": maxima, "points": len(wave["time"])}


def score_events(observed, initial, spec, budgets):
    finite = math.isfinite(initial) and all(math.isfinite(t) and math.isfinite(q) for t, q in observed)
    dt = abs(observed[0][0] - event(spec)) if len(observed) == 1 and finite else None
    dq = abs(observed[0][1] - captured(spec)) if len(observed) == 1 and finite else None
    errors = []
    if not finite or abs(initial - spec["initial"]) > budgets["state_V"]:
        errors.append("initial/nonfinite state")
    if len(observed) != 1:
        errors.append("event count")
    if dt is None or dt > budgets["event_s"]:
        errors.append("event time")
    if dq is None or dq > budgets["state_V"]:
        errors.append("captured value")
    return {"passed": not errors, "errors": errors, "initial": initial, "observed": observed,
            "expected": [[event(spec), captured(spec)]], "max_time_error_s": dt, "max_state_error_V": dq}


def ng_state(path, spec, budgets):
    frames, lineage_errors = accepted_trace(path)
    if not frames:
        return {"passed": False, "errors": ["missing accepted trace"]}
    values = [(t, float(row["prev_s0"])) for t, row in frames]
    observed = [row for i, row in enumerate(values) if i and row[1] != values[i - 1][1]]
    result = score_events(observed, values[0][1], spec, budgets)
    result["lineage_errors"] = lineage_errors
    result["passed"] = result["passed"] and not lineage_errors
    return result


def native_state(wave, inst, spec, budgets):
    name = "x" + inst + ":q"
    if not wave.get("time") or not vectors_valid(wave, [name], wave["time"][-1]):
        return {"passed": False, "errors": ["missing native state"]}
    values = list(zip(wave["time"], wave[name]))
    observed = [row for i, row in enumerate(values) if i and row[1] != values[i - 1][1]]
    return score_events(observed, values[0][1], spec, budgets)


def pair(a, b, cfg, limit=None):
    names = [*cfg["inputs"], *(s[n] for s in cfg["instances"].values() for n in ("output", "rc"))]
    if not all(vectors_valid(w, names, cfg["stop"]) for w in (a, b)):
        return {"passed": False, "errors": ["pair vectors/range"]}
    budgets = cfg["budgets"]
    grid = {*(i * budgets["pair_grid_s"] for i in range(int(cfg["stop"] / budgets["pair_grid_s"]) + 1)), cfg["stop"]}
    # Keep the original common platform grid. A 50ps edge can lie entirely
    # between its 1ns samples, so also compare fixed edge probes and both
    # engines' native points inside the unchanged edge window.
    edges = set()
    for spec in cfg["instances"].values():
        at, rise = event(spec), spec["rise_s"]
        lo, hi = at - budgets["event_s"], at + rise + budgets["event_s"]
        edges.update((lo, hi, *(at + rise * i / 4 for i in range(5))))
        edges.update(t for w in (a, b) for t in w["time"] if lo <= t <= hi)
    times = sorted(grid | {t for t in edges if 0 <= t <= cfg["stop"]})
    maxima, passed = {}, True
    for name in names:
        maximum = 0.0
        for t in times:
            bound = budgets["pair_platform_V"]
            for spec in cfg["instances"].values():
                if name == spec["output"] and event(spec) - budgets["event_s"] <= t <= event(spec) + spec["rise_s"] + budgets["event_s"]:
                    bound = budgets["pair_edge_V"]
            e = abs(sample(a, name, t) - sample(b, name, t))
            maximum = max(maximum, e)
            passed &= e <= (limit if limit is not None else bound)
        maxima[name] = maximum
    return {"passed": bool(passed), "max_difference_V": maxima, "points": len(times),
            "grid_s": budgets["pair_grid_s"], "platform_grid_points": len(grid),
            "edge_probe_points": len(set(times) - grid), "override_limit_V": limit}

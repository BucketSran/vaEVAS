"""P1 analytic finite clock edges, held states and timer identity checks."""

import bisect
import csv
import math

from clock_cases import answers
from check import sample
from trace_files import open_trace


def shape(wave, names, stop):
    return (all(n in wave for n in ["time", *names]) and bool(wave["time"])
            and wave["time"][0] == 0 and abs(wave["time"][-1] - stop) <= 1e-18
            and all(a <= b for a, b in zip(wave["time"], wave["time"][1:]))
            and all(len(wave[n]) == len(wave["time"]) and all(math.isfinite(v) for v in wave[n]) for n in ["time", *names]))


def curve(initial, changes, rise, t):
    k = bisect.bisect_right([e[0] for e in changes], t) - 1
    if k < 0:
        return initial
    at, target = changes[k]
    old = changes[k - 1][1] if k else initial
    return old + (target - old) * min(1, max(0, (t - at) / rise))


def score_wave(wave, cfg):
    expected = answers(cfg)
    names = [n for a in expected.values() for n in a["outputs"]]
    if not shape(wave, names, cfg["stop"]):
        return {"passed": False, "errors": ["incomplete/nonfinite wave or range"]}
    maxima, errors = {}, []
    for a in expected.values():
        for node, (state, rise) in a["outputs"].items():
            changes, plateau, edge = a["histories"][state], 0.0, 0.0
            probes = {i * 1e-9 for i in range(int(cfg["stop"] / 1e-9) + 1)} | {cfg["stop"]}
            probes.update(at + rise * i / 4 for at, _ in changes for i in range(5))
            points = [*zip(wave["time"], wave[node]),
                      *((t, sample(wave, node, t)) for t in probes if 0 <= t <= cfg["stop"])]
            for t, v in points:
                err = abs(v - curve(a["initial"][state], changes, rise, t))
                in_edge = any(at - cfg["budgets"]["event_s"] <= t <= at + rise + cfg["budgets"]["event_s"] for at, _ in changes)
                if in_edge: edge = max(edge, err)
                else: plateau = max(plateau, err)
            maxima[node] = {"platform_V": plateau, "edge_V": edge, "t0_error_V": abs(wave[node][0] - a["initial"][state])}
            if (maxima[node]["t0_error_V"] > cfg["budgets"]["platform_V"]
                    or plateau > cfg["budgets"]["platform_V"] or edge > cfg["budgets"]["edge_V"]):
                errors.append(node)
    return {"passed": not errors, "errors": errors, "max_error": maxima, "points": len(wave["time"])}


def state_series(times, values, initial, changes, budgets, integer=False):
    if not times or len(times) != len(values) or any(not math.isfinite(v) for v in values):
        return {"passed": False, "errors": ["missing/nonfinite state"]}
    observed = [(t, v) for i, (t, v) in enumerate(zip(times, values)) if i and v != values[i - 1]]
    same = len(observed) == len(changes)
    dt = max((abs(a[0] - b[0]) for a, b in zip(observed, changes)), default=0) if same else None
    dv = max((abs(a[1] - b[1]) for a, b in zip(observed, changes)), default=0) if same else None
    initial_error = abs(values[0] - initial)
    passed = same and dt <= budgets["event_s"] and dv <= budgets["platform_V"] and initial_error <= budgets["platform_V"]
    if integer:
        passed = passed and initial_error == 0 and dv == 0 and all(v == round(v) for v in values)
    return {"passed": bool(passed), "expected_count": len(changes), "observed_count": len(observed),
            "max_time_s": dt, "max_state_V": dv, "initial": values[0], "initial_error": initial_error,
            "observed": observed}


def native_states(wave, cfg):
    results = {}
    for tag, a in answers(cfg).items():
        for state, initial in a["initial"].items():
            name = "x" + tag + ":" + state
            results[tag + ":" + state] = state_series(wave.get("time", []), wave.get(name, []), initial,
                a["histories"][state], cfg["budgets"], state == "hits")
    return {"passed": all(r["passed"] for r in results.values()), "states": results}


def ng_trace(path, cfg, tag, state_names, triggers, require_dc_retry=False):
    with open_trace(path) as stream:
        rows = list(csv.DictReader(stream))
    dc = [r for r in rows if r["analysis"] == "0"]
    tr = [r for r in rows if r["analysis"] == "1"]
    a = answers(cfg)[tag]
    frames, lineage = {}, 0
    trials = {}
    for r in rows:
        trials.setdefault(r["trial_hash"], []).append(r)
    for r in tr:
        at = float(r["accepted_time"])
        if at in frames and frames[at]["prev_hash"] != r["prev_hash"]: lineage += 1
        frames[at] = r
    frames = sorted(frames.items())
    results = {n: state_series([t for t, _ in frames], [float(r["prev_s" + str(i)]) for _, r in frames],
        a["initial"][n], a["histories"][n], cfg["budgets"], n == "hits") for i, n in enumerate(state_names)}
    tick_events, tick_errors, initial_ok = [], [], bool(dc and tr)
    for i, trigger in enumerate(triggers):
        initial_tick = 1 if trigger["start"] == 0 else 0
        initial_ok = initial_ok and all(int(r["trial_tick" + str(i)]) == initial_tick for r in dc)
        prior = 0
        for t, r in frames:
            tick = int(r["prev_tick" + str(i)])
            if tick != prior:
                if tick != prior + 1: tick_errors.append("cursor jump")
                trial = next((q for q in trials.get(r["prev_hash"], [])
                              if int(q["event_mask"]) & (1 << i)
                              and int(q["prev_tick" + str(i)]) == prior), None)
                nominal = 0.0 if t == 0 and initial_tick else float(trial["nominal" + str(i)]) if trial else None
                host_time = float(trial["time"]) if trial else t
                # ngspice's accepted-time array and model callback TIME can
                # round differently. Hash+cursor identify the exact accepted
                # candidate; the small coordinate difference is also checked.
                if abs(host_time - t) > 4 * max(math.ulp(host_time), math.ulp(t)):
                    tick_errors.append("accepted/callback time identity")
                # The C default-timer path itself must never consume early.
                if nominal is None or host_time < nominal or host_time - nominal > trigger["time_tolerance"]:
                    tick_errors.append("timer source window")
                tick_events.append([host_time, i, prior, nominal])
            prior = tick
            prior = tick
    expected = {(e["id"], e["cycle"]): e["time"] for e in a["occurrences"]}
    observed = {(e[1], e[2]): e[0] for e in tick_events}
    if set(expected) != set(observed): tick_errors.append("occurrence identity/count")
    dt = max((abs(t - expected[key]) for key, t in observed.items() if key in expected), default=0)
    if dt > cfg["budgets"]["event_s"]: tick_errors.append("design event time")
    if require_dc_retry and not (len(dc) >= 2 and any(r["dc_injected"] == "1" for r in dc)):
        tick_errors.append("missing actual DC retry")
    if not initial_ok or lineage: tick_errors.append("initial cursor or accepted lineage")
    dc_state_ok = bool(dc) and all(
        abs(float(r["trial_s" + str(i)]) - a["initial"][n]) <= cfg["budgets"]["platform_V"]
        and (n != "hits" or float(r["trial_s" + str(i)]) == a["initial"][n])
        for r in dc for i, n in enumerate(state_names))
    if not dc_state_ok: tick_errors.append("DC final-state reconstruction")
    return {"passed": not tick_errors and all(r["passed"] for r in results.values()), "errors": tick_errors,
            "states": results, "timer_events": tick_events, "expected_occurrences": len(expected),
            "max_time_s": dt, "dc_calls": len(dc), "dc_state_invariants": dc_state_ok,
            "dc_injected": any(r["dc_injected"] == "1" for r in dc), "accepted_lineage_errors": lineage}


def pair(a, b, cfg, limit=None):
    expected = answers(cfg)
    names = [n for x in expected.values() for n in x["outputs"]]
    if not all(shape(w, names, cfg["stop"]) for w in (a, b)):
        return {"passed": False, "errors": ["pair shape/range"]}
    times = {i * 1e-9 for i in range(int(cfg["stop"] / 1e-9) + 1)} | {cfg["stop"]}
    edges = []
    for x in expected.values():
        for node, (state, rise) in x["outputs"].items():
            for at, _ in x["histories"][state]:
                lo, hi = at - cfg["budgets"]["event_s"], at + rise + cfg["budgets"]["event_s"]
                edges.append((node, lo, hi))
                times.update(at + rise * i / 4 for i in range(5))
                times.update(t for w in (a, b) for t in w["time"] if lo <= t <= hi)
    times = sorted(t for t in times if 0 <= t <= cfg["stop"])
    maxima, passed = {}, True
    for n in names:
        errors = []
        for t in times:
            bound = cfg["budgets"]["pair_edge_V"] if any(node == n and lo <= t <= hi for node, lo, hi in edges) else cfg["budgets"]["pair_platform_V"]
            e = abs(sample(a, n, t) - sample(b, n, t)); errors.append(e)
            passed = passed and e <= (limit if limit is not None else bound)
        maxima[n] = max(errors)
    return {"passed": passed, "max_difference_V": maxima, "points": len(times), "limit_override_V": limit}

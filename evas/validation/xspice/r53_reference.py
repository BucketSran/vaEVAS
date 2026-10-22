"""Independent ramp/RC and sampled-level answers for the bounded r53 pilot.

No compiler or generated history implementation is imported. The RC formula is
the closed-form solution of tau*y' + y = a + m*t on each linear segment.
"""

import bisect
import csv
import math
from trace_files import open_trace

TIME_BUDGET = 1e-12 + 1e-18
VOLTAGE_BUDGET = 20e-6


def ramp_input(cfg, t):
    b, m, tau = cfg["bias"], cfg["slope"], cfg["tau"]
    return b + m * (t - tau * (-math.expm1(-t / tau)))


def value(knots, t, tau=0.0):
    t = max(0.0, t)
    if not tau:
        k = bisect.bisect_right([p[0] for p in knots], t) - 1
        if k == len(knots) - 1:
            return knots[k][1]
        a, b = knots[k], knots[k + 1]
        return a[1] + (b[1] - a[1]) * (t - a[0]) / (b[0] - a[0])
    y = knots[0][1]
    for i, (start, u) in enumerate(knots):
        end, v = knots[i + 1] if i + 1 < len(knots) else (t, u)
        stop = min(t, end)
        if stop > start:
            m = (v - u) / (end - start) if end > start else 0.0
            dt = stop - start
            y = u + m * (dt - tau) + (y - u + m * tau) * math.exp(-dt / tau)
        if t <= end:
            return y
    return y


def levels(events, initial, rise, fall=None, delay=0.0):
    result = [(0.0, initial)]
    old = initial
    for t, target in events:
        if target != old:
            edge = rise if target > old else (fall if fall is not None else rise)
            result.extend([(t + delay, old), (t + delay + edge, target)])
        old = target
    return result


def edge_response(t, duration, tau):
    if t <= 0:
        return 0.0
    if not tau:
        return min(1.0, t / duration)
    if t < duration:
        return (t - tau * (-math.expm1(-t / tau))) / duration
    return 1 - tau / duration * math.exp(-(t - duration) / tau) * (-math.expm1(-duration / tau))


def envelope(knots, t, tau, time_budget):
    # Superposition gives each finite ramp its own early/late time. Shifting
    # the complete periodic waveform together would miss independent jitters
    # of rising and falling edges, particularly in an RC observation branch.
    lower = upper = knots[0][1]
    for (start, a), (end, b) in zip(knots, knots[1:]):
        if a == b:
            continue
        x = (b - a) * edge_response(t - start - time_budget, end - start, tau)
        y = (b - a) * edge_response(t - start + time_budget, end - start, tau)
        lower += min(x, y)
        upper += max(x, y)
    return lower, upper


def score_wave(wave, cfg):
    errors, maximum = [], {}
    required = {"time", *cfg.get("inputs", {}), *cfg["signals"]}
    if not required <= set(wave) or not wave["time"]:
        return {"passed": False, "errors": ["missing vectors"]}
    n = len(wave["time"])
    if any(len(wave[k]) != n or any(not math.isfinite(v) for v in wave[k]) for k in required):
        return {"passed": False, "errors": ["nonfinite/inconsistent vectors"]}
    if any(a > b for a, b in zip(wave["time"], wave["time"][1:])):
        errors.append("nonmonotone time")
    if abs(wave["time"][-1] - cfg["stop"]) > 1e-15:
        errors.append("missing stop")
    for name, inp in cfg.get("inputs", {}).items():
        e = max(abs(v - ramp_input(inp, t)) for t, v in zip(wave["time"], wave[name]))
        maximum[name] = e
        if e > VOLTAGE_BUDGET:
            errors.append(name + " external input RC")
    for name, signal in cfg["signals"].items():
        excess = 0.0
        for t, actual in zip(wave["time"], wave[name]):
            lower, upper = envelope(signal["knots"], t, signal.get("tau", 0), signal.get("time_budget", TIME_BUDGET))
            excess = max(excess, lower - actual, actual - upper)
        maximum[name] = excess
        if excess > signal.get("voltage_budget", VOLTAGE_BUDGET):
            errors.append(name + " waveform outside event-time envelope")
    return {"passed": not errors, "errors": errors, "max_excess_V": maximum, "points": n}


def accepted_trace(path):
    frames, errors = {}, 0
    with open_trace(path) as stream:
        for row in csv.DictReader(stream):
            t = float(row["accepted_time"])
            if t in frames and frames[t]["prev_hash"] != row["prev_hash"]:
                errors += 1
            frames[t] = row
    return sorted(frames.items()), errors


def score_states(path, expected, indices, initial=None, integer=False):
    frames, lineage_errors = accepted_trace(path)
    observed, prior = [], None
    for t, row in frames:
        states = [float(row["prev_s" + str(i)]) for i in indices]
        if not math.isfinite(t) or any(not math.isfinite(s) for s in states):
            return {"passed": False, "errors": ["nonfinite accepted state"]}
        if prior is not None and states != prior:
            observed.append((t, states))
        prior = states
    errors = []
    if not frames:
        return {"passed": False, "errors": ["missing accepted frames"]}
    if initial is not None:
        first = [float(frames[0][1]["prev_s" + str(i)]) for i in indices]
        if any(abs(a - b) > VOLTAGE_BUDGET for a, b in zip(first, initial)):
            errors.append("initial state")
    if integer and any(float(row["prev_s" + str(i)]) != math.trunc(float(row["prev_s" + str(i)]))
                       for _, row in frames for i in indices):
        errors.append("noninteger counter state")
    if lineage_errors:
        errors.append("accepted history lineage")
    if len(observed) != len(expected):
        errors.append("event count")
    time_error = max((abs(a[0] - b[0]) for a, b in zip(observed, expected)), default=0.0)
    state_error = max((abs(x - y) for a, b in zip(observed, expected) for x, y in zip(a[1], b[1])), default=0.0)
    if time_error > TIME_BUDGET:
        errors.append("event time")
    if state_error > VOLTAGE_BUDGET:
        errors.append("captured state")
    return {"passed": not errors, "errors": errors, "observed": observed,
            "expected": expected, "max_time_error_s": time_error,
            "max_state_error": state_error, "lineage_errors": lineage_errors}


def comparator_root(drive, reference=0.5, feedback=0.01):
    lo, hi = -1.0, 1.0
    for _ in range(70):
        mid = (lo + hi) / 2
        if mid < math.tanh(1000 * (drive - reference - feedback * mid)):
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def score_tanh(wave, drive, feedback=True):
    errors, maximum = [], {}
    if not wave.get("time") or any(not math.isfinite(t) for t in wave["time"]):
        return {"passed": False, "errors": ["missing/nonfinite times"]}
    if abs(wave["time"][-1] - drive[-1][0]) > 1e-15:
        errors.append("missing stop")
    if any(a > b for a, b in zip(wave["time"], wave["time"][1:])):
        errors.append("nonmonotone time")
    for name in (["open", "out"] if feedback else ["open"]):
        if name not in wave or len(wave[name]) != len(wave["time"]) or any(not math.isfinite(v) for v in wave[name]):
            errors.append(name + " missing/nonfinite")
            continue
        e = 0.0
        for t, actual in zip(wave["time"], wave[name]):
            d = value(drive, t)
            expected = comparator_root(d) if name == "out" else math.tanh(1000 * (d - 0.5))
            e = max(e, abs(actual - expected))
        maximum[name] = e
        if e > VOLTAGE_BUDGET:
            errors.append(name + " nonlinear relation")
    return {"passed": not errors, "errors": errors, "max_error_V": maximum}


def score_tanh_derivatives(path):
    maximum, count, regions = 0.0, 0, set()
    with open_trace(path) as stream:
        for row in csv.DictReader(stream):
            a, b = float(row["input0"]), float(row["input1"])
            if not math.isfinite(a) or not math.isfinite(b):
                return {"passed": False, "errors": ["nonfinite derivative input"]}
            argument = 1000 * (a - b)
            expected = 1000 / math.cosh(argument) ** 2
            p, n = float(row["partial0_0"]), float(row["partial0_1"])
            if not all(math.isfinite(x) for x in (p, n)):
                return {"passed": False, "errors": ["nonfinite derivative"]}
            maximum = max(maximum, abs(p - expected), abs(n + expected))
            regions.add("high" if argument > 3 else "low" if argument < -3 else "transition")
            count += 1
    passed = count > 0 and maximum < 1e-6 and regions == {"high", "low", "transition"}
    return {"passed": passed, "max_derivative_error": maximum, "rows": count, "regions": sorted(regions)}

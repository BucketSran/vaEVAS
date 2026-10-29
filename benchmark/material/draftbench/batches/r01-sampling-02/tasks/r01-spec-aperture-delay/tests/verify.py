"""Independent aperture-delay track-and-hold contract; reads only saved waveforms.

Each rising crossing of vth by V(clk) at t_k schedules a capture at
c_k = t_k + taperture. The expected held value is the range of vin over
c_k +/- TAU_S, taken from the saved stimulus rows. No candidate source,
reference model or reference waveform is read.
"""
from v2_runtime import main

EPS_V = 2e-3     # voltage error, V
TAU_S = 2e-12    # capture-time tolerance, s
TAU_T = 5e-12    # output-timing tolerance, s
DEFAULTS = {"vth": 0.45, "taperture": 200e-12, "tedge": 50e-12}
REQUIRED = ("clk", "vin", "vout")
FAILURE_LIMIT = 20


def interpolate(times, values, i, t):
    """Linear value at t between rows i and i + 1."""
    t0, t1 = times[i], times[i + 1]
    return values[i] + (values[i + 1] - values[i]) * (t - t0) / (t1 - t0)


def rising_crossings(times, clk, vth):
    found = []
    for i in range(len(times) - 1):
        if clk[i] < vth <= clk[i + 1]:
            found.append(times[i] + (times[i + 1] - times[i]) * (vth - clk[i]) / (clk[i + 1] - clk[i]))
    return found


def value_range(times, values, start, end):
    """Min and max of the piecewise-linear trace on [start, end]."""
    seen = []
    for i in range(len(times) - 1):
        t0, t1 = times[i], times[i + 1]
        if t1 < start or t0 > end:
            continue
        for t in (max(t0, start), min(t1, end)):
            seen.append(interpolate(times, values, i, t))
    return min(seen), max(seen)


def rows_between(times, start, end):
    return [i for i, t in enumerate(times) if start <= t <= end]


def monotone(samples, direction=0):
    """True when samples never reverse by more than EPS_V: upward (+1), downward (-1),
    or in one of the two directions (0)."""
    def within(sign):
        extreme = sign * samples[0]
        for v in samples:
            extreme = max(extreme, sign * v)
            if sign * v < extreme - EPS_V:
                return False
        return True
    return within(direction) if direction else within(1) or within(-1)


def evaluate(rows, case, work):
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    params = {**DEFAULTS, **case.get("params", {})}
    vth, aperture, edge = params["vth"], params["taperture"], params["tedge"]
    if not (aperture > 0 and edge > 0):
        raise ValueError("parameters outside the public contract")
    if len(rows) < 2 or any(name not in row for row in rows for name in REQUIRED):
        raise ValueError("missing required waveform")
    times = [r["time"] for r in rows]
    clk, vin, vout = ([r[n] for r in rows] for n in REQUIRED)
    # Resolution is an environment obligation; a coarse trace is not a model failure.
    if max(b - a for a, b in zip(times, times[1:])) > case.get("resolution", 2e-12) * 1.05:
        raise ValueError("insufficient waveform resolution")
    if clk[0] == vth:
        raise ValueError("stimulus outside contract: clk starts at vth")
    triggers = rising_crossings(times, clk, vth)
    if any(b - a <= aperture for a, b in zip(triggers, triggers[1:])):
        raise ValueError("stimulus outside contract: triggers not more than taperture apart")
    stop = times[-1]
    # Held values in order: the initial vin, then one per observed capture instant.
    held = [(0.0, vin[0], vin[0])]
    held += [(c, *value_range(times, vin, c - TAU_S, c + TAU_S))
             for c in (t + aperture for t in triggers) if c <= stop]
    failures, checks, summary = [], 0, []

    def fail(**info):
        if len(failures) < FAILURE_LIMIT:
            failures.append(info)

    previous = None  # band that vout may still be leaving at the next capture
    for k, (start, lo, hi) in enumerate(held):
        following = held[k + 1][0] if k + 1 < len(held) else None
        hold_end = following - TAU_T if following is not None else stop
        if k == 0:
            # Time 0 is always observed, even when the first capture comes within TAU_T of it.
            hold_start, hold_end = 0.0, max(hold_end, 0.0)
        else:
            hold_start = start + edge + TAU_T
        if k:
            # Transition window: bounded by the old and new held values; monotone after c_k,
            # toward the new accepted range when vout at c_k lies clear of it.
            window_end = min(hold_start, hold_end, stop)
            low, high = min(previous[0], lo), max(previous[1], hi)
            for i in rows_between(times, start - TAU_T, window_end):
                checks += 1
                if not low - EPS_V <= vout[i] <= high + EPS_V:
                    fail(kind="transition_bound", capture=start, time=times[i], vout=vout[i], low=low, high=high)
            moving = [vout[i] for i in rows_between(times, start + TAU_T, window_end)]
            if moving:
                checks += 1
                near = [vout[i] for i in rows_between(times, start - TAU_T, start + TAU_T)]
                direction = (-1 if near and min(near) > hi + EPS_V else
                             1 if near and max(near) < lo - EPS_V else 0)
                if not monotone(moving, direction):
                    kind = "transition_direction" if direction and monotone(moving) else "transition_not_monotone"
                    fail(kind=kind, capture=start, window_end=window_end, expected=[lo, hi],
                         direction={1: "up", -1: "down", 0: "either"}[direction])
        observed = None
        if hold_start <= hold_end:
            values = [vout[i] for i in rows_between(times, hold_start, hold_end)]
            if values:
                checks += 1
                smallest, largest = min(values), max(values)
                observed = [smallest, largest]
                # One held value h in [lo, hi] must lie within EPS_V of every hold sample.
                if max(lo, largest - EPS_V) > min(hi, smallest + EPS_V):
                    fail(kind="initial_hold" if k == 0 else "hold", capture=start, hold_start=hold_start,
                         hold_end=hold_end, expected=[lo, hi], observed=observed)
        # An interrupted transition leaves vout between every value since the last completed hold.
        previous = (lo, hi) if k == 0 or hold_start <= hold_end else (min(previous[0], lo), max(previous[1], hi))
        summary.append({"capture": start, "expected": [lo, hi], "hold": [hold_start, hold_end], "observed": observed})
    if checks == 0:
        raise ValueError("no scored observations")
    return {"passed": not failures, "checks": checks, "failures": failures,
            "triggers": len(triggers), "captures": summary[:40]}


if __name__ == "__main__":
    main(evaluate)

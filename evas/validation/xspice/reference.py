"""Independent exact RC response to affine forcing and hybrid event calendar.
No compiler/runtime imports; time in seconds, voltage in volts.
"""

import math


def rc(y, u, m, dt, tau):
    return u + m * (dt - tau) + (y - u + m * tau) * math.exp(-dt / tau)


def expected(cfg, stop=8.4e-6):
    # Segments retain the actual output level and slope, not runtime frames.
    low = cfg.get("clock_low", 0.0)
    high = cfg.get("clock_high", 1.8)
    threshold = cfg.get("threshold", 0.9)
    t = 0.0
    held = 0.1
    count = ticks = 0
    order = 0
    clk = low + (0.02 if cfg.get("clock_feedback") else 0.0)
    din = 0.3
    out = 0.1
    slope = 0.0
    endpoint = math.inf
    origin = target = 0.1
    active = False
    pending = []
    events = []
    segments = []
    next_timer = cfg["timer_start"]
    timer_index = 0
    pulse = []
    for i in range(3):
        s = 1e-6 + 3e-6 * i
        pulse.extend(
            [
                (s, low, (high - low) / 1e-8),
                (s + 1e-8, high, 0.0),
                (s + 1.01e-6, high, -(high - low) / 1e-8),
                (s + 1.02e-6, low, 0.0),
            ]
        )
    pi = 0
    pv = low
    pm = 0.0
    while t < stop - 1e-18:
        next_pulse = pulse[pi][0] if pi < len(pulse) else math.inf
        end = min(
            stop,
            next_pulse,
            next_timer,
            pending[0][0] if pending else math.inf,
            endpoint,
        )
        dt = end - t

        def clock_at(h):
            return (
                rc(clk, pv + 0.2 * out, pm + 0.2 * slope, h, 1e-7)
                if cfg.get("clock_feedback")
                else pv + pm * h
            )

        cend = clock_at(dt)
        crossing = False
        if clk < threshold and cend >= threshold and dt > 1e-18:
            lo, hi = 0.0, dt
            for _ in range(70):
                mid = (lo + hi) / 2
                if clock_at(mid) < threshold:
                    lo = mid
                else:
                    hi = mid
            hit = t + (lo + hi) / 2
            if hit < end - 1e-18:
                end = hit
                dt = end - t
                cend = threshold
            crossing = True
        segments.append(
            {
                "start": t,
                "end": end,
                "out": out,
                "slope": slope,
                "din": din,
                "clk": clk,
                "pulse": pv,
                "pulse_slope": pm,
            }
        )
        din = rc(din, out + 0.2, slope, dt, 1e-6)
        out += slope * dt
        pv += pm * dt
        clk = cend
        t = end
        # Distinct event times are fixed by the contract. No tie writer assumption.
        if crossing:
            held = din if cfg.get("feedback") else 0.1 + 1e5 * t
            count += 1
            order = 10 * order + 1
            events.append(
                {
                    "time": t,
                    "held": held,
                    "count": count,
                    "ticks": ticks,
                    "order": order,
                    "kind": "cross",
                }
            )
            pending.append((t + cfg["delay"], held))
            # prevent floating round-off from rediscovering the identical root
            clk = threshold
        if abs(t - next_timer) < 1e-18:
            held = cfg.get("reset_value", 0.05)
            ticks += 1
            order = 10 * order + 2
            events.append(
                {
                    "time": t,
                    "held": held,
                    "count": count,
                    "ticks": ticks,
                    "order": order,
                    "kind": "timer",
                }
            )
            pending.append((t + cfg["delay"], held))
            timer_index += 1
            next_timer = cfg["timer_start"] + timer_index * 3e-6
        if abs(t - endpoint) < 1e-18:
            out = target
            slope = 0.0
            active = False
            endpoint = math.inf
        while pending and pending[0][0] <= t + 1e-18:
            _, q = pending.pop(0)
            if q == target:
                continue
            if q == out:
                out = q
                slope = 0.0
                target = q
                active = False
                endpoint = math.inf
                continue
            # LRM 4.5.8: same direction retains historical origin; reversal
            # uses the old destination. Independent scalar construction.
            if not active:
                origin = out
            elif (q - out) * slope <= 0:
                origin = target
            duration = cfg["rise"] if q > out else cfg["fall"]
            target = q
            slope = (q - origin) / duration
            endpoint = t + (q - out) / slope
            active = True
        if abs(t - next_pulse) < 1e-18:
            _, pv, pm = pulse[pi]
            pi += 1
            if not cfg.get("clock_feedback"):
                clk = pv
    return {"events": events, "segments": segments, "stop": stop}


def value(answer, cfg, t, node):
    import bisect

    if node in ("held", "count", "ticks", "order", "stamp"):
        es = answer["events"]
        j = bisect.bisect_right([x["time"] for x in es], t) - 1
        if j < 0:
            return {"held": 0.1, "count": 0, "ticks": 0, "order": 0, "stamp": -1.0}[
                node
            ]
        return es[j]["time"] * 1e6 if node == "stamp" else es[j][node]
    ss = answer["segments"]
    j = bisect.bisect_right([x["start"] for x in ss], t) - 1
    s = ss[max(0, j)]
    dt = t - s["start"]
    if node == "out":
        return s["out"] + s["slope"] * dt
    if node == "din":
        return (
            rc(s["din"], s["out"] + 0.2, s["slope"], dt, 1e-6)
            if cfg.get("feedback")
            else 0.1 + 1e5 * t
        )
    if node == "clk":
        return (
            rc(
                s["clk"],
                s["pulse"] + 0.2 * s["out"],
                s["pulse_slope"] + 0.2 * s["slope"],
                dt,
                1e-7,
            )
            if cfg.get("clock_feedback")
            else s["pulse"] + s["pulse_slope"] * dt
        )
    raise KeyError(node)

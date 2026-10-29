"""Independent programmable-delay-cell contract; reads only saved waveforms.

Input crossings of vth, located by linear interpolation between saved samples,
and the code bits observed at each load crossing give the expected output edges:
an accepted pulse latches delay_min + delay_lsb * code at its rising crossing and
uses it for both of its edges; reset cancels every pending edge and pulls a high
output low. No candidate source, reference model or reference waveform is read.
"""
import bisect
import math
from fractions import Fraction

from v2_runtime import main

EPS_V = 2e-3      # voltage error, V
TAU_T = 2e-12     # output timing tolerance, s
SAME = 1e-12      # load and in_clk crossings closer than this are the same instant, s
GUARD = 20e-12    # stimulus separations of the public contract, s
PRECISION = 1e-13 # 0.1 ps: largest rounding bound with which a separation at its minimum is still judged, s
UNIT = 2.0 ** -53 # relative rounding of the time unit (such as 1e-12 for ps) the stimulus times share
DEFAULTS = {"vth": 0.45, "vdd": 0.9, "vss": 0.0, "delay_min": 20e-12, "delay_lsb": 3e-12, "tr": 10e-12}
BITS = ("code_5", "code_4", "code_3", "code_2", "code_1", "code_0")
REQUIRED = ("in_clk", "load", "rst", *BITS, "out_clk")
FAILURE_LIMIT = 20


def outside(reason):
    return ValueError("stimulus outside contract: " + reason)


def stamp(x):
    """A binary64 input as (exact value, bound): it stands for a value within half a unit in its last place."""
    return Fraction(x), Fraction(math.ulp(x)) / 2


def after(later, earlier):
    """later - earlier of two (exact time, bound, crossing it comes from) stamps, as (value, bound).

    The unit rounding of the stimulus times scales the span between the two crossings by up to UNIT.
    """
    return later[0] - earlier[0], later[1] + earlier[1] + UNIT * abs(later[2] - earlier[2])


def apart(a, b):
    """|a - b| of two stamps, as (value, bound)."""
    gap, bound = after(a, b)
    return abs(gap), bound


def undecided(gap, limit):
    """True when the saved times cannot tell gap from limit, two (exact value, bound) pairs.

    That is so when the difference lies within the bounds and the bounds total more than PRECISION;
    within PRECISION such a difference is taken as equality.
    """
    excess, bound = gap[0] - limit[0], gap[1] + limit[1]
    return bound > PRECISION and -bound <= excess < bound


def imprecise(gap, limit):
    """An evidence failure, not a model failure: the saved times are too coarse to judge the stimulus."""
    return ValueError(f"evidence precision insufficient: rounding of up to {float(gap[1] + limit[1]):.3g} s, above "
                      f"{PRECISION:g} s, leaves a {float(gap[0]):.6g} s stimulus separation undecided against "
                      f"{float(limit[0]):.6g} s")


def short(gap, minimum):
    """True when gap, a separation of the observed inputs, is shorter than a public minimum.

    Both are (exact value, bound) pairs, so the comparison itself adds no rounding; the bounds cover
    the binary64 rounding of the saved samples, the parameters and the time unit. A separation equal
    to the minimum is legal, and one within the bounds of it cannot be told from equality.
    """
    if undecided(gap, minimum):
        raise imprecise(gap, minimum)
    return gap[0] + gap[1] + minimum[1] < minimum[0]


def crossings(times, values, level):
    """(time, direction) of every crossing of level, by linear interpolation."""
    found = []
    for i in range(len(times) - 1):
        a, b = values[i], values[i + 1]
        if a < level <= b or a > level >= b:
            found.append((times[i] + (times[i + 1] - times[i]) * (level - a) / (b - a), 1 if b > a else -1))
    return found


def exact_crossings(times, values, level):
    """(time, bound) of each crossing that crossings() finds, in the same order, in rational arithmetic.

    The time interpolates the saved samples exactly. The bound covers every value it depends on standing
    for one within half a unit in its last place. The times involved, the two samples' and those of the
    stimulus corners the samples lie between, come no later than the end of the edge (the first saved
    sample at which the input stops moving), so they move the crossing by at most the half unit there.
    The voltages and level move it by the interval times the change of the interpolation fraction.
    """
    found, (lv, h_lv) = [], stamp(level)
    for i in range(len(times) - 1):
        a, b = values[i], values[i + 1]
        if a < level <= b or a > level >= b:
            end = i + 1
            while end + 1 < len(values) and (values[end + 1] - values[end]) * (b - a) > 0:
                end += 1
            t0, t1, h_t = Fraction(times[i]), Fraction(times[i + 1]), stamp(times[end])[1]
            (va, h_a), (vb, h_b) = stamp(a), stamp(b)
            t = t0 + (t1 - t0) * (lv - va) / (vb - va)
            room = abs(vb - va) - h_a - h_b
            if room > 0:
                move = (h_lv + max(h_a, h_b)) / room        # bound on the change of the fraction
                found.append((t, h_t * (1 + 2 * move) + (t1 - t0) * move))
            else:                                           # the voltages do not place it in the interval
                found.append((t, t1 - t0 + h_t))
    return found


def logic_crossings(name, times, values, vth):
    """Threshold crossings of one logic input, which must alternate from its initial level."""
    if abs(values[0] - vth) < 1e-9:
        raise outside(name + " starts at vth")
    found = crossings(times, values, vth)
    expected = -1 if values[0] > vth else 1
    for _, direction in found:
        if direction != expected:
            raise outside(name + " stops on vth")
        expected = -direction
    return found


def value_at(times, values, t):
    i = min(max(bisect.bisect_right(times, t) - 1, 0), len(times) - 2)
    t0, t1 = times[i], times[i + 1]
    return values[i] + (values[i + 1] - values[i]) * (t - t0) / (t1 - t0)


def rows_between(times, start, end):
    return range(bisect.bisect_left(times, start), bisect.bisect_right(times, end))


def expected_edges(times, sig, p):
    """Apply the public rules to the observed inputs; return edges, pulses and the state timeline."""
    vth, tr = p["vth"], p["tr"]
    dmin, lsb = p["delay_min"], p["delay_lsb"]
    found = {n: logic_crossings(n, times, sig[n], vth) for n in ("in_clk", "load", "rst", *BITS)}
    clk, rst = found["in_clk"], found["rst"]
    loads = [t for t, d in found["load"] if d > 0]
    bit_x = {b: [t for t, _ in found[b]] for b in BITS}
    rises = [t for t, d in clk if d > 0]
    # The minimum separations of the legal stimuli are checked on exact stamps of the same crossings.
    exact = {}
    for n, pairs in found.items():
        for (t, _), (u, bound) in zip(pairs, exact_crossings(times, sig[n], vth)):
            exact[n, t] = u, bound, u
    if len(exact) < sum(map(len, found.values())):
        raise ValueError("evidence precision insufficient: two crossings of one input round to the same time")
    guard, same_x, (tr_x, h_tr) = stamp(GUARD), stamp(SAME), stamp(tr)
    four_tr = 4 * tr_x, 4 * h_tr
    g_rst = max(guard[0], four_tr[0]), max(guard[1], four_tr[1])
    (dmin_x, h_dmin), (lsb_x, h_lsb) = stamp(dmin), stamp(lsb)

    def out_stamp(q, edge):
        """Stamp of the output edge that pulse q schedules from its input crossing q[edge]."""
        t, bound, _ = exact["in_clk", q[edge]]
        return t + dmin_x + lsb_x * q["code"], bound + h_dmin + h_lsb * q["code"], t

    def edge_stamp(edge):
        """Stamp of an expected output edge (time, direction, cause, pulse index)."""
        t, direction, cause, k = edge
        return exact["rst", t] if cause == "reset" else out_stamp(pulses[k], "rise_in" if direction > 0 else "fall_in")

    events = [(t, 0, "rst", d) for t, d in rst]
    for t in loads:
        # Crossings less than 1 ps apart are the same instant: compared exactly, with the precision check of short().
        same = [r for r in rises if short(apart(exact["load", t], exact["in_clk", r]), same_x)]
        if any(r not in same and short(apart(exact["load", t], exact["in_clk", r]), guard) for r in rises):
            raise outside("load rising crossing within 20 ps of an in_clk rising crossing")
        if any(short(apart(exact["load", t], exact[b, u]), guard) for b in BITS for u in bit_x[b]):
            raise outside("code bit changes within 20 ps of a load rising crossing")
        events.append((same[0] if same else t, 1, "load", t))
    events += [(t, 2, "clk", d) for t, d in clk]
    for t, _ in rst:
        if (any(short(apart(exact["rst", t], exact["in_clk", u]), g_rst) for u, _ in clk)
                or any(short(apart(exact["rst", t], exact["load", u]), g_rst) for u in loads)):
            raise outside("rst crossing too close to an in_clk or load crossing")
    events.sort(key=lambda e: (e[0], e[1]))
    rst_high, loaded, code, current, last_rise = sig["rst"][0] > vth, False, None, None, None
    pulses, forced, timeline = [], [], [(0.0, "reset" if sig["rst"][0] > vth else "unloaded")]
    for t, _, kind, info in events:
        if kind == "rst" and info > 0:
            rst_high, loaded, current = True, False, None
            timeline.append((t, "reset"))
            for q in pulses:
                if q["cancelled"]:
                    continue
                if q["rise_out"] > t:
                    q["cancelled"] = "before_rise"
                elif q["fall_out"] is None or q["fall_out"] > t:
                    q["cancelled"] = "fall"
                    forced.append(t)
        elif kind == "rst":
            rst_high = False
            timeline.append((t, "unloaded"))
        elif kind == "load":
            if not rst_high:
                bits = [1 if value_at(times, sig[b], info) > vth else 0 for b in BITS]
                code, loaded = sum(bit << (5 - i) for i, bit in enumerate(bits)), True
                timeline.append((t, "loaded"))
        elif info > 0:
            last_rise = t
            if any(not q["cancelled"] and short(after(exact["in_clk", t], out_stamp(q, "rise_in")), guard)
                   for q in pulses):
                raise outside("in_clk rising crossing while a rising output edge is pending")
            current = None
            if not rst_high and loaded:
                delay = dmin + lsb * code
                current = {"rise_in": t, "code": code, "delay": delay, "rise_out": t + delay,
                           "fall_in": None, "fall_out": None, "cancelled": None}
                pulses.append(current)
        else:
            if last_rise is not None and short(after(exact["in_clk", t], exact["in_clk", last_rise]), four_tr):
                raise outside("in_clk high time shorter than 4*tr")
            if any(q is not current and not q["cancelled"] and q["fall_out"] is not None
                   and short(after(exact["in_clk", t], out_stamp(q, "fall_in")), guard) for q in pulses):
                raise outside("in_clk falling crossing while a falling output edge is pending")
            if current is not None:
                current["fall_in"], current["fall_out"] = t, t + current["delay"]
                current = None
    scheduled = [q["rise_out"] for q in pulses] + [q["fall_out"] for q in pulses if q["fall_out"] is not None]
    pending = [out_stamp(q, "rise_in") for q in pulses]
    pending += [out_stamp(q, "fall_in") for q in pulses if q["fall_in"] is not None]
    if any(short(apart(exact["rst", t], s), g_rst) for t, _ in rst for s in pending):
        raise outside("rst crossing too close to a scheduled output edge")
    # (time, direction, cause, pulse index); a reset pulls a high output low at its crossing.
    edges = [(t, -1, "reset", None) for t in forced]
    for k, q in enumerate(pulses):
        if q["cancelled"] != "before_rise":
            edges.append((q["rise_out"], 1, "pulse", k))
            if q["cancelled"] is None and q["fall_out"] is not None:
                edges.append((q["fall_out"], -1, "pulse", k))
    edges.sort(key=lambda e: e[0])
    level = -1
    for a, b in zip(edges, edges[1:]):
        if short(after(edge_stamp(b), edge_stamp(a)), four_tr):
            raise outside("output edges closer than 4*tr")
    for t, d, _, _ in edges:
        if d == level:
            raise outside("output edges out of order")
        level = d
    return edges, pulses, timeline, scheduled


def evaluate(rows, case, work):
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    p = {**DEFAULTS, **case.get("params", {})}
    if not (p["vss"] < p["vdd"] and p["delay_min"] > 0 and p["delay_lsb"] >= 0 and p["tr"] > 0):
        raise ValueError("parameters outside the public contract")
    if len(rows) < 2 or any(name not in row for row in rows for name in REQUIRED):
        raise ValueError("missing required waveform")
    times = [r["time"] for r in rows]
    # Resolution is an environment obligation; a coarse trace is not a model failure.
    if max(b - a for a, b in zip(times, times[1:])) > case.get("resolution", 2e-12) * 1.05:
        raise ValueError("insufficient waveform resolution")
    sig = {n: [r[n] for r in rows] for n in REQUIRED}
    edges, pulses, timeline, scheduled = expected_edges(times, sig, p)
    out, stop, tr = sig["out_clk"], times[-1], p["tr"]
    levels = {-1: p["vss"], 1: p["vdd"]}
    lo_band, hi_band = p["vss"] - EPS_V, p["vdd"] + EPS_V
    failures, checks = [], 0

    def state_at(t):
        return [s for u, s in timeline if u <= t][-1]

    def nearest(t):
        near = min(edges, key=lambda e: abs(e[0] - t), default=None)
        ghost = min(scheduled, key=lambda s: abs(s - t), default=None)
        return {"nearest_expected_edge": None if near is None else
                {"time": near[0], "direction": "rise" if near[1] > 0 else "fall", "cause": near[2], "pulse": near[3]},
                "nearest_scheduled_time": ghost}

    def fail(**info):
        if len(failures) < FAILURE_LIMIT:
            failures.append(info)

    def hold(start, end, level):
        nonlocal checks
        index = rows_between(times, start, end)
        if not len(index):
            return
        checks += 1
        bad = [i for i in index if abs(out[i] - levels[level]) > EPS_V]
        if bad:
            i = bad[0]
            fail(kind="hold", start=start, end=end, expected="high" if level > 0 else "low",
                 expected_v=levels[level], first_time=times[i], first_value=out[i], rows=len(bad),
                 max_error=max(abs(out[j] - levels[level]) for j in bad), state=state_at(times[i]),
                 **nearest(times[i]))

    def unexplained(index, group):
        """First row of an edge window that the window's edges, taken in order, cannot explain.

        Phase j at a row: the edges before j are complete and those after j have not started.
        Each edge moves monotonically (back by at most EPS_V) and only inside its own window: a
        row at or after t_e + tr + TAU_T needs it complete, a row at or before t_e - TAU_T needs
        it not started. The holds own the two outer ends, so a lone edge is the monotone check.
        """
        n = len(group)
        begin = [e[0] - TAU_T for e in group]
        end = [e[0] + tr + TAU_T for e in group]
        reach = None    # per phase: running extreme of the edge's movement, None if impossible
        for i in index:
            t, v = times[i], out[i]
            now, earlier = [], reach is None
            for j, (_, d, _, _) in enumerate(group):
                r = None
                if not ((j + 1 < n - 1 and t >= end[j + 1]) or (j > 1 and t <= begin[j - 1])
                        or (j < n - 1 and t >= end[j] and abs(v - levels[d]) > EPS_V)
                        or (j > 0 and t <= begin[j] and abs(v - levels[-d]) > EPS_V)):
                    if earlier:
                        r = v           # the earlier edges finished between rows; this one may start
                    elif reach[j] is not None and d * (reach[j] - v) <= EPS_V:
                        r = max(reach[j], v) if d > 0 else min(reach[j], v)
                now.append(r)
                earlier = earlier or reach[j] is not None
            if all(r is None for r in now):
                return t
            reach = now
        return None

    start, level = 0.0, -1
    # Edges whose windows overlap (possible only when tr < 4/3 ps) are checked as one window.
    groups = []
    for edge in edges:
        if groups and edge[0] - TAU_T < groups[-1][-1][0] + tr + TAU_T:
            groups[-1].append(edge)
        else:
            groups.append([edge])
    for group in groups:
        t, last = group[0][0], group[-1][0]
        hold(start, min(t - TAU_T, stop), level)
        index = rows_between(times, t - TAU_T, min(last + tr + TAU_T, stop))
        if len(index):
            checks += 1
            samples = [out[i] for i in index]
            reversed_at = unexplained(index, group)
            if min(samples) < lo_band or max(samples) > hi_band or reversed_at is not None:
                _, direction, why, k = group[0]
                fail(kind="edge", edge_time=t, direction="rise" if direction > 0 else "fall", cause=why, pulse=k,
                     window=[t - TAU_T, last + tr + TAU_T], edges_in_window=len(group), minimum=min(samples),
                     maximum=max(samples), reversed_at=reversed_at)
        start, level = last + tr + TAU_T, group[-1][1]
    hold(start, stop, level)
    if checks == 0:
        raise ValueError("no scored observations")
    # Diagnostics only: measured midpoint crossings matched to the expected edges.
    measured = crossings(times, out, (p["vdd"] + p["vss"]) / 2)
    used, report = set(), []
    for t, direction, why, k in edges:
        match = next((j for j, (u, d) in enumerate(measured)
                      if j not in used and d == direction and t - 50e-12 <= u <= t + tr + 50e-12), None)
        if match is not None:
            used.add(match)
        report.append({"time": t, "direction": "rise" if direction > 0 else "fall", "cause": why, "pulse": k,
                       "measured_midpoint_lag": None if match is None else measured[match][0] - t})
    extra = [{"time": u, "direction": "rise" if d > 0 else "fall"} for j, (u, d) in enumerate(measured) if j not in used]
    return {"passed": not failures, "checks": checks, "failures": failures,
            "accepted_pulses": len(pulses), "expected_edges": report[:60], "extra_crossings": extra[:20],
            "pulses": pulses[:40]}


if __name__ == "__main__":
    main(evaluate)

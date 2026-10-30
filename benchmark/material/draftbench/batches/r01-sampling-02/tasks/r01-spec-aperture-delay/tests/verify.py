"""Independent aperture-delay track-and-hold contract; reads saved waveforms and the case netlist's sources.

Each rising crossing of vth by V(clk) at t_k schedules a capture at
c_k = t_k + taperture. The expected held value is the range of vin over
c_k +/- TAU_S, taken from the saved stimulus rows. No candidate source,
reference model or reference waveform is read. A bench whose clk starts or
rests at vth, touches it and returns, or moves less than 50 mV from vth
between successive crossings is outside the contract; that is judged on the
clk definition in the case netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

EPS_V = 2e-3     # voltage error, V
TAU_S = 2e-12    # capture-time tolerance, s
TAU_T = 5e-12    # output-timing tolerance, s
CROSSING_EXCURSION = 50e-3   # clk moves at least this far from vth between successive crossings, V
SAMPLE_SLACK = 1e-3          # the error is raised below CROSSING_EXCURSION less this, V (value of the row check)
DEFAULTS = {"vth": 0.45, "taperture": 200e-12, "tedge": 50e-12}
REQUIRED = ("clk", "vin", "vout")
FAILURE_LIMIT = 20


# Bench obligations on the stimulus definitions (v417-bench-fix-r1; netlist conventions v4.21, section 0.5 item 20,
# way A). The start, rest, touch and excursion obligations of each checked input are judged on its stimulus definition
# in case['netlist'], the case netlist that the runtime writes as tb.scs, never on saved rows: a root that any module
# locates on the same input and threshold can leave a saved row exactly on the threshold. A voltage source is read as
# written: numbers with at most one scale factor, and no parameter name, expression, unit or comment; pwl points,
# pulse levels and corners (all six parameters), a dc value, or a sine (offset +- amplitude and its start value). A
# checked quantity is linear between the knots of its sources over [0, stop]. A definition point is on the threshold
# when it equals the threshold as written, or after both are rounded to binary64, or in a reading of the binary64 node
# values that the quantity's forms give: the comparison as the checker, the reference and the instruction write it,
# where a node on stacked sources has two values (the exact sum rounded once, and the sources rounded and added from
# ground) and every combination counts. A source that cannot be read this way, or a checked node that no voltage
# source drives, is a bench error as well. A bench error raises ValueError: the runtime records checker_error and the
# case gets no verdict.
STIMULUS_SCALE = {"T": 12, "G": 9, "M": 6, "Meg": 6, "K": 3, "k": 3, "m": -3, "u": -6, "n": -9, "p": -12, "f": -15,
                  "a": -18}


def written(x):
    """A float constant or parameter as written (its shortest decimal), exactly."""
    return Fraction(repr(float(x)))


def stimulus_number(text):
    """A netlist number, exactly. An exponent followed by a scale factor is not read: Spectre stops on it or silently
    keeps the parameter's default."""
    m = re.fullmatch(r"([-+]?(?:\d+\.?\d*|\.\d+)([eE][-+]?\d+)?)(Meg|[TGMKkmunpfa])?", text)
    if not m or m[2] and m[3]:
        raise ValueError(f"cannot read the number {text}")
    return Fraction(m[1]) * Fraction(10) ** STIMULUS_SCALE.get(m[3], 0)


def stimulus_source(text, stop):
    """('pts', [(t, v)]) of a dc, pwl or pulse source, held before its first and after its last point, or ('sine',
    (offset, amplitude, frequency, phase in degrees))."""
    wave = re.search(r"\bwave\s*=\s*\[([^\]]*)\]", text)
    rest = text[:wave.start()] + text[wave.end():] if wave else text
    fields = dict(re.findall(r"(\w+)\s*=\s*(\S+)", rest))
    if re.sub(r"(\w+)\s*=\s*(\S+)", "", rest).strip():
        raise ValueError(f"cannot read {text.strip()[:80]}")
    kind = fields.pop("type", "dc" if "dc" in fields else "")
    v = {k: stimulus_number(x) for k, x in fields.items()}
    if kind == "dc" and set(v) == {"dc"}:
        return "pts", [(Fraction(0), v["dc"])]
    if kind == "pwl" and wave and set(v) <= {"dc"}:
        w = [stimulus_number(x) for x in wave[1].split()]
        pts = list(zip(w[0::2], w[1::2]))
        if pts and len(w) % 2 == 0 and all(a[0] < b[0] for a, b in zip(pts, pts[1:])):
            return "pts", pts
    pulse = {"val0", "val1", "rise", "fall", "width", "period"}
    if kind == "pulse" and pulse <= set(v) <= pulse | {"delay", "dc"}:
        v0, v1, d = v["val0"], v["val1"], v.get("delay", Fraction(0))
        r, f, w, per = v["rise"], v["fall"], v["width"], v["period"]
        if d >= 0 and r > 0 and f > 0 and w >= 0 and r + w + f <= per and (stop - d) / per < 10 ** 4:
            pts, k = [(Fraction(0), v0)] * (d > 0), 0
            while d + k * per <= stop:
                for t, x in ((0, v0), (r, v1), (r + w, v1), (r + w + f, v0)):
                    if not pts or pts[-1][0] < d + k * per + t:
                        pts.append((d + k * per + t, x))
                k += 1
            return "pts", pts
    if kind == "sine" and {"sinedc", "ampl", "freq"} <= set(v) <= {"sinedc", "ampl", "freq", "sinephase", "dc"}:
        return "sine", (v["sinedc"], v["ampl"], v["freq"], v.get("sinephase", Fraction(0)))
    raise ValueError(f"cannot read {text.strip()[:80]}")


def stimulus_at(xs, pts, t):
    """Value at t of points pts with times xs, linear between them and held outside them."""
    j = bisect.bisect_right(xs, t) - 1
    if j < 0:
        return pts[0][1]
    if j + 1 == len(pts):
        return pts[-1][1]
    (a, u), (b, w) = pts[j], pts[j + 1]
    return u + (w - u) * (t - a) / (b - a)


def stimulus_circuit(case):
    """The case netlist's stop time, its voltage sources {name: (node, node, definition or the error reading it)},
    and the path of sources from ground to each driven node {node: {source: +1 or -1}}, in order from ground."""
    if not isinstance(case.get("netlist"), str):
        raise ValueError("bench error: the case has no netlist to read the stimulus definitions from")
    text = re.sub(r"\\\n", " ", case["netlist"])
    m = re.search(r"^\s*\S+\s+tran\b[^\n]*?\bstop\s*=\s*(\S+)", text, re.M)
    try:
        stop = stimulus_number(m[1])
    except (TypeError, ValueError):
        stop = written(case["stop"])
    found, names = {}, {}
    for line in text.split("\n"):
        e = re.match(r"\s*([^\s(]+)\s*\(([^)]*)\)", line)
        if e and not e[1].startswith(("//", "*")):
            for node in e[2].split():
                names.setdefault(node.lower(), set()).add(node)
        m = re.match(r"\s*([^\s(]+)\s*\(\s*(\S+)\s+(\S+)\s*\)\s*vsource\b(.*)", line)
        if m and not m[1].startswith(("//", "*")):
            try:
                found[m[1]] = (m[2].lower(), m[3].lower(), stimulus_source(m[4], stop))
            except ValueError as exc:
                found[m[1]] = (m[2].lower(), m[3].lower(), exc)
    # Saved signals are matched in lower case, but Spectre's names are case sensitive.
    for spelled in names.values():
        if len(spelled) > 1:
            raise ValueError("bench error: the case netlist has nodes whose names differ only in case: "
                             + ", ".join(sorted(spelled)))
    path, grow = {g: {} for g in ("0", "gnd", "gnd!")}, True
    while grow:
        grow = False
        for k, (a, b, _) in found.items():
            if b in path and a not in path:
                path[a], grow = {**path[b], k: path[b].get(k, 0) + 1}, True
            elif a in path and b not in path:
                path[b], grow = {**path[a], k: path[a].get(k, 0) - 1}, True
    return stop, found, path


def stimulus_node_values(p, value):
    """The binary64 values of a node with path p, value(source) giving each source's exact level: the exact sum
    rounded once, and the sources rounded and added from ground one operation at a time (one value for one source)."""
    acc = 0.
    for k, x in p.items():
        acc += x * float(value(k))
    return {float(sum((x * value(k) for k, x in p.items()), Fraction(0))), acc}


def stimulus_points(label, thr, pts, on, R, start_margin, excursion):
    """Judge a quantity linear between its definition points pts [(t, exact value)] over [0, stop]. on[k]: whether
    point k is on the threshold R (exact, as written) in one of the readings. start_margin and excursion (exact or
    None): the least distance from R at t = 0 and the least excursion from R between two successive crossings."""
    side = [(v > R) - (v < R) for _, v in pts]

    def where(k):
        return f"{float(pts[k][0]):.12g} s"
    if on[0]:
        raise ValueError(f"bench error: {label} starts on {thr} at 0 s")
    if start_margin is not None and abs(pts[0][1] - R) < start_margin:
        raise ValueError(f"bench error: {label} starts {float(abs(pts[0][1] - R)):.6g} V from {thr}, closer than "
                         f"{float(start_margin):.8g} V")
    for k in range(1, len(pts)):
        if on[k] and on[k - 1]:
            raise ValueError(f"bench error: {label} rests on {thr} from {where(k - 1)}")
        if on[k] and k + 1 < len(pts) and not on[k + 1] and side[k - 1] == side[k + 1]:
            raise ValueError(f"bench error: {label} touches {thr} and returns to the same side at {where(k)}")
    if excursion is None:
        return
    cross, last = [], None
    for k in range(len(pts)):
        if not on[k]:
            if last is not None and side[k] != side[last]:
                cross.append((last, k))
            last = k
    for (a, b), (c, d) in zip(cross, cross[1:]):
        peak = max(abs(pts[k][1] - R) for k in range(b, c + 1))
        if peak < excursion:
            raise ValueError(f"bench error: {label} moves only {float(peak):.6g} V away from {thr} between the "
                             f"crossings near {where(a)} and {where(d)}, less than {float(excursion):.8g} V")


def stimulus_sine(label, thr, const, ampl, freq, phase, R, stop, alt, start_margin, excursion):
    """const + ampl*sin(2*pi*freq*t + phase degrees): it starts at const + ampl*sin(phase) and turns at const +- |ampl|.
    alt(t, s): whether the binary64 node values at time t, with the sine at s, put the quantity on the threshold."""
    if ampl == 0:
        level = [(Fraction(0), const), (stop, const)]
        return stimulus_points(label, thr, level, [v == R or float(v) == float(R) or alt(t, Fraction(0))
                                                   for t, v in level], R, start_margin, excursion)
    top, bottom = const + abs(ampl) - R, const - abs(ampl) - R
    s0 = Fraction(round(math.sin(math.radians(phase)))) if phase % 90 == 0 else Fraction(math.sin(math.radians(phase)))
    start = const + ampl * s0
    if start == R or float(start) == float(R) or alt(Fraction(0), s0):
        raise ValueError(f"bench error: {label} starts on {thr} at 0 s")
    if start_margin is not None and abs(start - R) < start_margin:
        raise ValueError(f"bench error: {label} starts {float(abs(start - R)):.6g} V from {thr}, closer than "
                         f"{float(start_margin):.8g} V")
    th0, th1 = math.radians(phase), 2 * math.pi * freq * float(stop) + math.radians(phase)
    if (th1 - th0) / math.pi > 1e4:
        raise ValueError(f"bench error: cannot read the stimulus definition of {label}: too many sine periods")
    for k in range(math.floor((th0 - math.pi / 2) / math.pi) + 1, math.ceil((th1 - math.pi / 2) / math.pi)):
        th = math.pi / 2 + math.pi * k
        turn = top if math.sin(th) * ampl > 0 else bottom
        t = (th - th0) / (2 * math.pi * freq)
        if turn == 0 or float(turn + R) == float(R) or alt(Fraction(t), Fraction(1 if math.sin(th) > 0 else -1)):
            raise ValueError(f"bench error: {label} touches {thr} and returns to the same side at {t:.12g} s")
    if excursion is None or not bottom < 0 < top:
        return
    u = math.asin(float((R - const) / ampl))
    roots = sorted(x + 2 * math.pi * k for x in (u, math.pi - u)
                   for k in range(math.floor((th0 - x) / (2 * math.pi)), math.ceil((th1 - x) / (2 * math.pi)) + 1)
                   if th0 < x + 2 * math.pi * k < th1)
    for a, b in zip(roots, roots[1:]):
        peak = top if math.sin((a + b) / 2) * ampl > 0 else -bottom
        if peak < excursion:
            raise ValueError(f"bench error: {label} moves only {float(peak):.6g} V away from {thr} between two "
                             f"crossings, less than {float(excursion):.8g} V")


def stimulus_quantity(label, thr, parts, R, forms, stop, found, start_margin, excursion):
    """parts: [(path, +1 or -1)] of the quantity's nodes; forms(values): whether binary64 values of these nodes, in this
    order, put the quantity on the threshold. Every source on these paths must be readable, also one whose terms
    cancel."""
    terms = {}
    for p, c in parts:
        for k, x in p.items():
            terms[k] = terms.get(k, 0) + c * x
    for k in terms:
        if isinstance(found[k][2], ValueError):
            raise ValueError(f"bench error: cannot read the stimulus definition of {label}: {found[k][2]}")
    knots = {k: [t for t, _ in found[k][2][1]] for k in terms if found[k][2][0] == "pts"}

    def level(k, t, fixed):
        kind, w = found[k][2]
        if kind == "pts":
            return stimulus_at(knots[k], w, t)
        if k in fixed:
            return w[0] + w[1] * fixed[k]
        return w[0] + w[1] * Fraction(math.sin(2 * math.pi * float(w[2]) * float(t) + math.radians(float(w[3]))))

    def binary(t, fixed=None):
        combos = [()]
        for p, _ in parts:
            combos = [q + (v,) for q in combos for v in stimulus_node_values(p, lambda k: level(k, t, fixed or {}))]
        return any(forms(q) for q in combos)
    waves = [(c, found[k][2]) for k, c in terms.items() if c]
    sines = [(c, w[1]) for c, w in waves if w[0] == "sine"]
    pwls = [(c, w[1]) for c, w in waves if w[0] == "pts"]
    if sines:
        if len(sines) > 1 or any(len({x for _, x in w}) > 1 for _, w in pwls):
            raise ValueError(f"bench error: cannot read the stimulus definition of {label}: a sine with another "
                             f"changing source")
        (c, (off, amp, fr, ph)), = sines
        s = next(k for k, c2 in terms.items() if c2 and found[k][2][0] == "sine")
        const = c * off + sum((c2 * w[0][1] for c2, w in pwls), Fraction(0))
        return stimulus_sine(label, thr, const, c * amp, float(fr), float(ph), R, stop, lambda t, u: binary(t, {s: u}),
                             start_margin, excursion)
    xs = [[t for t, _ in w] for _, w in pwls]
    times = sorted({Fraction(0), stop} | {t for x in xs for t in x if 0 < t < stop})
    pts = [(t, sum((c * stimulus_at(x, w, t) for (c, w), x in zip(pwls, xs)), Fraction(0))) for t in times]
    on = [v == R or float(v) == float(R) or binary(t) for t, v in pts]
    stimulus_points(label, thr, pts, on, R, start_margin, excursion)


def check_stimulus(case, quantities):
    """Bench obligations of the checked quantities, judged on the case netlist's source definitions. quantities:
    [(label, threshold name, [(node, +1 or -1)], threshold, forms, start margin, excursion)]; forms(values, r) tells
    whether binary64 node values put the quantity on the binary64 threshold r; the margins are exact or None."""
    stop, found, path = stimulus_circuit(case)
    for label, thr, nodes, threshold, forms, start_margin, excursion in quantities:
        for node, _ in nodes:
            if node not in path:
                raise ValueError(f"bench error: {node} is not driven by a voltage source of the case netlist")
        r = float(threshold)
        stimulus_quantity(label, thr, [(path[n], c) for n, c in nodes], written(threshold),
                          lambda q, r=r, forms=forms: forms(q, r), stop, found, start_margin, excursion)


def single(q, r):
    """One node on its threshold."""
    return q[0] == r


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
    # clk starts off vth, crosses it without resting on it or touching it and returning, and between
    # successive crossings moves at least 50 mV away from it, far beyond the cross() expression
    # tolerance. These are judged on the clk definition in the case netlist (check_stimulus), so a
    # saved row at a located root never enters them; the error is raised below 50 mV less SAMPLE_SLACK.
    check_stimulus(case, [("clk", "vth", [("clk", 1)], vth, single, None,
                           written(CROSSING_EXCURSION) - written(SAMPLE_SLACK))])
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

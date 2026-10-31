"""Independent programmable-delay-cell contract; reads saved waveforms and the case netlist's sources.

Input crossings of vth, located by linear interpolation between saved samples,
and the code bits observed at each load crossing give the expected output edges:
an accepted pulse latches delay_min + delay_lsb * code at its rising crossing and
uses it for both of its edges; reset cancels every pending edge and pulls a high
output low. No candidate source, reference model or reference waveform is read.
Every input starts away from vth and passes through it without stopping on it or
touching it and returning: that is judged on the input's definition in the case
netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

EPS_V = 2e-3      # voltage error, V
TAU_T = 2e-12     # output timing tolerance, s
LEAD = 1e-12      # a load rising crossing at least this long before an in_clk rising crossing applies to it, s
GUARD = 20e-12    # stimulus separations of the public contract, s
PRECISION = 1e-13 # 0.1 ps: largest rounding bound with which a separation at its minimum is still judged, s
UNIT = 2.0 ** -53 # relative rounding of the time unit (such as 1e-12 for ps) the stimulus times share
DEFAULTS = {"vth": 0.45, "vdd": 0.9, "vss": 0.0, "delay_min": 20e-12, "delay_lsb": 3e-12, "tr": 10e-12}
BITS = ("code_5", "code_4", "code_3", "code_2", "code_1", "code_0")
REQUIRED = ("in_clk", "load", "rst", *BITS, "out_clk")
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
    found = {n: crossings(times, sig[n], vth) for n in ("in_clk", "load", "rst", *BITS)}
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
    guard, lead, (tr_x, h_tr) = stamp(GUARD), stamp(LEAD), stamp(tr)
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
        # Relative to each rising in_clk crossing a load comes at least 1 ps before or at least 20 ps after it;
        # the same instant is neither. Compared exactly, with the precision check of short().
        for r in rises:
            ahead = after(exact["in_clk", r], exact["load", t])
            if ahead[0] > 0:
                if short(ahead, lead):
                    raise outside("load rising crossing less than 1 ps before an in_clk rising crossing")
            elif short(after(exact["load", t], exact["in_clk", r]), guard):
                raise outside("load rising crossing at the same instant as, or less than 20 ps after, "
                              "an in_clk rising crossing")
        if any(short(apart(exact["load", t], exact[b, u]), guard) for b in BITS for u in bit_x[b]):
            raise outside("code bit changes within 20 ps of a load rising crossing")
        events.append((t, 1, "load", t))
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
    # Every input starts away from vth (by at least 1 nV) and passes through it without stopping on it or
    # touching it and returning: judged on the input's definition in the case netlist (check_stimulus).
    check_stimulus(case, [(n, "vth", [(n, 1)], p["vth"], single, written(1e-9), None)
                          for n in ("in_clk", "load", "rst", *BITS)])
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

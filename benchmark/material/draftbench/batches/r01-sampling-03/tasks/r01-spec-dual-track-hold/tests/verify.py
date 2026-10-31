"""Independent waveform contract for dual_track_sample_hold; reads saved waveforms and the netlist's sources.

No candidate source, reference model or reference waveform is read. Every value is
measured from vss. The ticks are t_k = k*tick from t = 0. At each tick the clock level
comes from the recorded crossings of clk - vss through vth (none lies within 50 ps of a
tick), and the input u_k and the span s_k come from the recorded rows, linear between
saved rows. A low tick sets a += alpha_in*(u_k - a); a high tick sets
b += alpha_out*(a - b) with a from before the tick; both are then limited to [0, s_k].
Both start at vinit. vout - vss must show b, and phase must show vdd while the clock is
high and vss while it is low, except within 1.25*tedge after a tick that changes b by
more than DELTA (vout) or after a crossing (phase). A change of DELTA or less opens no
unscored window, and the row at t = 0 is always scored against vinit. Extra simulator
rows only refine the inputs. Whether clk - vss starts within 50 mV of vth, rests on
it, touches it and returns, or moves less than 50 mV away from it between successive
crossings is judged on the definitions of clk and vss in the case netlist, never on
saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

SIGNALS = ('vdd', 'vss', 'clk', 'vin', 'vout', 'phase')
DEFAULTS = {'vth': 0.45, 'tick': 0.5e-9, 'alpha_in': 0.45, 'alpha_out': 0.55, 'tedge': 50e-12, 'vinit': 0.0}
TICK_GUARD = 50e-12          # every clk crossing to every tick
START_MARGIN = .05           # clk - vss at t = 0 is at least this far from vth
CROSSING_EXCURSION = .05     # clk - vss moves at least this far from vth between successive crossings
SAMPLE_SLACK = 2e-3          # the error is raised below CROSSING_EXCURSION less this (value of the row check)
RAIL_STEP = 1e-3             # vss and the span each change by at most this within any tick-long interval
DELTA = 1e-4                 # the change threshold of the instruction: b computed from saved samples
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
STIMULUS_SCALE = {'T': 12, 'G': 9, 'M': 6, 'Meg': 6, 'K': 3, 'k': 3, 'm': -3, 'u': -6, 'n': -9, 'p': -12, 'f': -15,
                  'a': -18}


def written(x):
    """A float constant or parameter as written (its shortest decimal), exactly."""
    return Fraction(repr(float(x)))


def stimulus_number(text):
    """A netlist number, exactly. An exponent followed by a scale factor is not read: Spectre stops on it or silently
    keeps the parameter's default."""
    m = re.fullmatch(r'([-+]?(?:\d+\.?\d*|\.\d+)([eE][-+]?\d+)?)(Meg|[TGMKkmunpfa])?', text)
    if not m or m[2] and m[3]:
        raise ValueError(f'cannot read the number {text}')
    return Fraction(m[1]) * Fraction(10) ** STIMULUS_SCALE.get(m[3], 0)


def stimulus_source(text, stop):
    """('pts', [(t, v)]) of a dc, pwl or pulse source, held before its first and after its last point, or ('sine',
    (offset, amplitude, frequency, phase in degrees))."""
    wave = re.search(r'\bwave\s*=\s*\[([^\]]*)\]', text)
    rest = text[:wave.start()] + text[wave.end():] if wave else text
    fields = dict(re.findall(r'(\w+)\s*=\s*(\S+)', rest))
    if re.sub(r'(\w+)\s*=\s*(\S+)', '', rest).strip():
        raise ValueError(f'cannot read {text.strip()[:80]}')
    kind = fields.pop('type', 'dc' if 'dc' in fields else '')
    v = {k: stimulus_number(x) for k, x in fields.items()}
    if kind == 'dc' and set(v) == {'dc'}:
        return 'pts', [(Fraction(0), v['dc'])]
    if kind == 'pwl' and wave and set(v) <= {'dc'}:
        w = [stimulus_number(x) for x in wave[1].split()]
        pts = list(zip(w[0::2], w[1::2]))
        if pts and len(w) % 2 == 0 and all(a[0] < b[0] for a, b in zip(pts, pts[1:])):
            return 'pts', pts
    pulse = {'val0', 'val1', 'rise', 'fall', 'width', 'period'}
    if kind == 'pulse' and pulse <= set(v) <= pulse | {'delay', 'dc'}:
        v0, v1, d = v['val0'], v['val1'], v.get('delay', Fraction(0))
        r, f, w, per = v['rise'], v['fall'], v['width'], v['period']
        if d >= 0 and r > 0 and f > 0 and w >= 0 and r + w + f <= per and (stop - d) / per < 10 ** 4:
            pts, k = [(Fraction(0), v0)] * (d > 0), 0
            while d + k * per <= stop:
                for t, x in ((0, v0), (r, v1), (r + w, v1), (r + w + f, v0)):
                    if not pts or pts[-1][0] < d + k * per + t:
                        pts.append((d + k * per + t, x))
                k += 1
            return 'pts', pts
    if kind == 'sine' and {'sinedc', 'ampl', 'freq'} <= set(v) <= {'sinedc', 'ampl', 'freq', 'sinephase', 'dc'}:
        return 'sine', (v['sinedc'], v['ampl'], v['freq'], v.get('sinephase', Fraction(0)))
    raise ValueError(f'cannot read {text.strip()[:80]}')


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
    if not isinstance(case.get('netlist'), str):
        raise ValueError('bench error: the case has no netlist to read the stimulus definitions from')
    text = re.sub(r'\\\n', ' ', case['netlist'])
    m = re.search(r'^\s*\S+\s+tran\b[^\n]*?\bstop\s*=\s*(\S+)', text, re.M)
    try:
        stop = stimulus_number(m[1])
    except (TypeError, ValueError):
        stop = written(case['stop'])
    found, names = {}, {}
    for line in text.split('\n'):
        e = re.match(r'\s*([^\s(]+)\s*\(([^)]*)\)', line)
        if e and not e[1].startswith(('//', '*')):
            for node in e[2].split():
                names.setdefault(node.lower(), set()).add(node)
        m = re.match(r'\s*([^\s(]+)\s*\(\s*(\S+)\s+(\S+)\s*\)\s*vsource\b(.*)', line)
        if m and not m[1].startswith(('//', '*')):
            try:
                found[m[1]] = (m[2].lower(), m[3].lower(), stimulus_source(m[4], stop))
            except ValueError as exc:
                found[m[1]] = (m[2].lower(), m[3].lower(), exc)
    # Saved signals are matched in lower case, but Spectre's names are case sensitive.
    for spelled in names.values():
        if len(spelled) > 1:
            raise ValueError('bench error: the case netlist has nodes whose names differ only in case: '
                             + ', '.join(sorted(spelled)))
    path, grow = {g: {} for g in ('0', 'gnd', 'gnd!')}, True
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
        return f'{float(pts[k][0]):.12g} s'
    if on[0]:
        raise ValueError(f'bench error: {label} starts on {thr} at 0 s')
    if start_margin is not None and abs(pts[0][1] - R) < start_margin:
        raise ValueError(f'bench error: {label} starts {float(abs(pts[0][1] - R)):.6g} V from {thr}, closer than '
                         f'{float(start_margin):.8g} V')
    for k in range(1, len(pts)):
        if on[k] and on[k - 1]:
            raise ValueError(f'bench error: {label} rests on {thr} from {where(k - 1)}')
        if on[k] and k + 1 < len(pts) and not on[k + 1] and side[k - 1] == side[k + 1]:
            raise ValueError(f'bench error: {label} touches {thr} and returns to the same side at {where(k)}')
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
            raise ValueError(f'bench error: {label} moves only {float(peak):.6g} V away from {thr} between the '
                             f'crossings near {where(a)} and {where(d)}, less than {float(excursion):.8g} V')


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
        raise ValueError(f'bench error: {label} starts on {thr} at 0 s')
    if start_margin is not None and abs(start - R) < start_margin:
        raise ValueError(f'bench error: {label} starts {float(abs(start - R)):.6g} V from {thr}, closer than '
                         f'{float(start_margin):.8g} V')
    th0, th1 = math.radians(phase), 2 * math.pi * freq * float(stop) + math.radians(phase)
    if (th1 - th0) / math.pi > 1e4:
        raise ValueError(f'bench error: cannot read the stimulus definition of {label}: too many sine periods')
    for k in range(math.floor((th0 - math.pi / 2) / math.pi) + 1, math.ceil((th1 - math.pi / 2) / math.pi)):
        th = math.pi / 2 + math.pi * k
        turn = top if math.sin(th) * ampl > 0 else bottom
        t = (th - th0) / (2 * math.pi * freq)
        if turn == 0 or float(turn + R) == float(R) or alt(Fraction(t), Fraction(1 if math.sin(th) > 0 else -1)):
            raise ValueError(f'bench error: {label} touches {thr} and returns to the same side at {t:.12g} s')
    if excursion is None or not bottom < 0 < top:
        return
    u = math.asin(float((R - const) / ampl))
    roots = sorted(x + 2 * math.pi * k for x in (u, math.pi - u)
                   for k in range(math.floor((th0 - x) / (2 * math.pi)), math.ceil((th1 - x) / (2 * math.pi)) + 1)
                   if th0 < x + 2 * math.pi * k < th1)
    for a, b in zip(roots, roots[1:]):
        peak = top if math.sin((a + b) / 2) * ampl > 0 else -bottom
        if peak < excursion:
            raise ValueError(f'bench error: {label} moves only {float(peak):.6g} V away from {thr} between two '
                             f'crossings, less than {float(excursion):.8g} V')


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
            raise ValueError(f'bench error: cannot read the stimulus definition of {label}: {found[k][2]}')
    knots = {k: [t for t, _ in found[k][2][1]] for k in terms if found[k][2][0] == 'pts'}

    def level(k, t, fixed):
        kind, w = found[k][2]
        if kind == 'pts':
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
    sines = [(c, w[1]) for c, w in waves if w[0] == 'sine']
    pwls = [(c, w[1]) for c, w in waves if w[0] == 'pts']
    if sines:
        if len(sines) > 1 or any(len({x for _, x in w}) > 1 for _, w in pwls):
            raise ValueError(f'bench error: cannot read the stimulus definition of {label}: a sine with another '
                             f'changing source')
        (c, (off, amp, fr, ph)), = sines
        s = next(k for k, c2 in terms.items() if c2 and found[k][2][0] == 'sine')
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
                raise ValueError(f'bench error: {node} is not driven by a voltage source of the case netlist')
        r = float(threshold)
        stimulus_quantity(label, thr, [(path[n], c) for n, c in nodes], written(threshold),
                          lambda q, r=r, forms=forms: forms(q, r), stop, found, start_margin, excursion)


def single(q, r):
    """One node on its threshold."""
    return q[0] == r


def crossings(times, values, level):
    """(time, rising) for each pass of values through level, linear between rows.

    Rows are compared with the level exactly; a row on the level is on neither side. A
    crossing is a change of side between successive rows off the level, at the single
    row on the level between them if there is one. A touch, with rows on the same side
    around a row on the level, is no crossing. Starting, resting or touching the level is a
    bench obligation judged on the stimulus definition (check_stimulus), not here. A row on
    the level that ends the record after a row off it is a crossing in the direction of
    arrival; a row on the level that begins the record is none.
    """
    found, last = [], None
    for j, v in enumerate(values):
        if v == level:
            continue
        if last is not None and (v > level) != (values[last] > level):
            t = times[j - 1] if j - last == 2 else \
                times[last] + (level - values[last]) * (times[j] - times[last]) / (v - values[last])
            found.append((t, v > level))
        last = j
    if last == len(values) - 2 and values[-1] == level:
        found.append((times[-1], values[last] < level))
    return found


def largest_change(times, values, width):
    """Largest |v(t2) - v(t1)| with |t2 - t1| <= width, linear between rows.

    For a piecewise-linear record the largest change over a window of fixed width is
    reached with one window end on a row, so windows starting and ending on rows suffice.
    """
    def ranged(ts, vs):
        worst, j, n = 0., 0, len(ts)
        for i in range(n):
            end = ts[i] + width
            j = max(j, i)
            while j + 1 < n and ts[j + 1] <= end:
                j += 1
            seg = vs[i:j + 1]
            lo, hi = min(seg), max(seg)
            if j + 1 < n:
                e = vs[j] + (vs[j + 1] - vs[j]) * (end - ts[j]) / (ts[j + 1] - ts[j])
                lo, hi = min(lo, e), max(hi, e)
            worst = max(worst, hi - lo)
        return worst
    return max(ranged(times, values), ranged([-t for t in reversed(times)], list(reversed(values))))


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    vth, tick, alpha_in, alpha_out, tedge, vinit = (float(p[k]) for k in
                                                    ('vth', 'tick', 'alpha_in', 'alpha_out', 'tedge', 'vinit'))
    atol = float(case.get('atol', .002))
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    if len(rows) < 2 or any(not {'time', *SIGNALS}.issubset(r) for r in rows):
        raise ValueError('missing required signals')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('nonfinite evidence')
    ts = [r['time'] for r in rows]
    if any(x >= y for x, y in zip(ts, ts[1:])):
        raise ValueError('waveform time must increase')
    if ts[0] > 1e-15 or abs(ts[-1] - case['stop']) > max(1e-15, case['stop'] * 1e-6):
        raise ValueError('incomplete transient')
    # Resolution, parameters and the stimulus domain are bench obligations. A candidate
    # cannot repair them, so they are not candidate failures.
    if not (.1 - 1e-12 <= vth <= .8 + 1e-12 and .25e-9 * (1 - 1e-9) <= tick <= 5e-9 * (1 + 1e-9)
            and 0 < alpha_in <= 1 and 0 < alpha_out <= 1 and 10e-12 * (1 - 1e-9) <= tedge <= tick / 4 * (1 + 1e-9)):
        raise ValueError('case parameters outside the public contract')
    if max(y - x for x, y in zip(ts, ts[1:])) > tedge / 4 * 1.05:
        raise ValueError('insufficient waveform resolution')
    vss = [r['vss'] for r in rows]
    span = [r['vdd'] - r['vss'] for r in rows]
    if any(abs(v) > .5 + 1e-9 for v in vss) or any(not .4 - 1e-9 <= v <= 1.5 + 1e-9 for v in span):
        raise ValueError('rails outside the public contract')
    if largest_change(ts, vss, tick) > RAIL_STEP + 1e-9 or largest_change(ts, span, tick) > RAIL_STEP + 1e-9:
        raise ValueError('a rail changes by more than 1 mV within one tick')
    if any(not -.5 - 1e-9 <= r['vin'] - r['vss'] <= s + .5 + 1e-9 for r, s in zip(rows, span)):
        raise ValueError('vin outside the public contract')
    # The rails come from voltage sources and are exact at t = 0; the 1e-9 V slack only absorbs
    # the rounding of the recorded span, e.g. 0.407 - (-0.493) = 0.8999999999999999 against vinit 0.9.
    if not -1e-9 <= vinit <= span[0] + 1e-9:
        raise ValueError('vinit outside the rail span at t = 0')
    clock = [r['clk'] - r['vss'] for r in rows]
    # clk - vss starts at least 50 mV from vth, never rests on it, never touches it and returns, and
    # between successive crossings moves at least 50 mV away from it, far beyond the cross() expression
    # tolerance. These are judged on the definitions of clk and vss (check_stimulus); the error is raised
    # below 50 mV less SAMPLE_SLACK. On the threshold reads exactly, in binary64, and as V(clk) - V(vss)
    # in binary64 against vth, as this checker, the reference and the instruction write it.
    check_stimulus(case, [('V(clk, vss)', 'vth', [('clk', 1), ('vss', -1)], vth, lambda q, r: q[0] - q[1] == r,
                           written(START_MARGIN) * written(1 - 1e-6),
                           written(CROSSING_EXCURSION) - written(SAMPLE_SLACK))])
    edges = crossings(ts, clock, vth)
    edge_times = [t for t, _ in edges]
    if any(y - x < 4 * tedge * (1 - 1e-6) for x, y in zip(edge_times, edge_times[1:])):
        raise ValueError('clk crossings closer than 4*tedge')
    if any(abs(t - round(t / tick) * tick) < TICK_GUARD * (1 - 1e-6) for t in edge_times):
        raise ValueError('clk crossing within 50 ps of a tick')

    def level(t, values):
        j = max(0, min(len(ts) - 2, bisect.bisect_right(ts, t) - 1))
        return values[j] + (values[j + 1] - values[j]) * (t - ts[j]) / (ts[j + 1] - ts[j])

    start_high = clock[0] > vth

    def high_at(t):
        i = bisect.bisect_right(edge_times, t) - 1
        return edges[i][1] if i >= 0 else start_high

    vin_rel = [r['vin'] - r['vss'] for r in rows]
    ticks, a, b = [], vinit, vinit
    k = 0
    while k * tick <= ts[-1] * (1 + 1e-12):
        t = k * tick
        s, u, high = level(t, span), level(t, vin_rel), high_at(t)
        new_a, new_b = (a, b + alpha_out * (a - b)) if high else (a + alpha_in * (u - a), b)
        lim_a, lim_b = min(max(new_a, 0.), s), min(max(new_b, 0.), s)
        ticks.append({'time': t, 'high': high, 'a': lim_a, 'b': lim_b, 'b_changed': abs(lim_b - b) > DELTA,
                      'limited': lim_a != new_a or lim_b != new_b})
        a, b = lim_a, lim_b
        k += 1
    tick_times = [x['time'] for x in ticks]
    skip = 1.25 * tedge

    failures, checks, worst, bad = [], {'vout': 0, 'phase': 0}, {'vout': 0., 'phase': 0.}, {}
    for j, r in enumerate(rows):
        t = r['time']
        k = bisect.bisect_right(tick_times, t) - 1
        # The initial state is checked on its own: no unscored window covers the row at t = 0.
        if j == 0 or not (ticks[k]['b_changed'] and t < tick_times[k] + skip):
            expected = r['vss'] + (vinit if j == 0 else ticks[k]['b'])
            error = abs(r['vout'] - expected)
            checks['vout'] += 1
            worst['vout'] = max(worst['vout'], error)
            if error > atol:
                bad[('vout', k)] = max(bad.get(('vout', k), 0.), error)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': 'vout', 'expected': expected, 'actual': r['vout'],
                                     'tick': k, 'tick_time': tick_times[k], 'b': ticks[k]['b'], 'a': ticks[k]['a'],
                                     'clock_high_at_tick': ticks[k]['high'], 'initial_state': j == 0})
        i = bisect.bisect_right(edge_times, t) - 1
        if i >= 0 and t < edge_times[i] + skip:
            continue
        high = edges[i][1] if i >= 0 else start_high
        expected = r['vdd'] if high else r['vss']
        error = abs(r['phase'] - expected)
        checks['phase'] += 1
        worst['phase'] = max(worst['phase'], error)
        if error > atol:
            bad[('phase', i)] = max(bad.get(('phase', i), 0.), error)
            if len(failures) < FAILURE_LIMIT:
                failures.append({'time': t, 'node': 'phase', 'expected': expected, 'actual': r['phase'],
                                 'crossing': i, 'crossing_time': edge_times[i] if i >= 0 else None,
                                 'clock_high': high})
    if not checks['vout'] or not checks['phase']:
        raise ValueError('no scored observations')
    summary = [{'node': node, 'index': index,
                'event_time': (tick_times[index] if node == 'vout' else edge_times[index] if index >= 0 else None),
                'max_error': e} for (node, index), e in sorted(bad.items(), key=lambda x: (x[0][0], x[0][1]))[:FAILURE_LIMIT]]
    bounds = [0.] + edge_times + [ts[-1] * (1 + 1e-12)]
    empty = sum(1 for lo, hi in zip(bounds, bounds[1:])
                if bisect.bisect_left(tick_times, hi) == bisect.bisect_left(tick_times, lo))
    return {'passed': not failures, 'checks': checks['vout'] + checks['phase'], 'checks_by_output': checks,
            'failures': failures, 'failed_intervals': summary, 'failed_interval_count': len(bad),
            'max_error': max(worst.values()), 'max_error_by_output': worst, 'atol': atol,
            'ticks': len(ticks), 'high_ticks': sum(x['high'] for x in ticks),
            'limited_ticks': sum(x['limited'] for x in ticks), 'clock_crossings': len(edges),
            'vout_windows': sum(x['b_changed'] for x in ticks),
            'phases_without_tick': empty, 'unscored_after_event_s': skip}


if __name__ == '__main__':
    main(evaluate)

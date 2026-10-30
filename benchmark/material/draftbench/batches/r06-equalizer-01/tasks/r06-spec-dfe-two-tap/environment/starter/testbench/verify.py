"""Independent waveform contract for the two-tap DFE receiver; reads saved waveforms and the netlist's sources.

No candidate source, reference model or reference waveform is read. Crossings
through vth are taken from the saved rows, linear between rows; a touch that
returns to the same side is no crossing. A decision event is a rising clk
crossing with rst low. It reads the tap codes k1, k2 and V(vin) at the crossing,
takes fb = tap_lsb*(k1*h1 + k2*h2) from the two history slots (+1 high, -1 low,
0 empty), decides high when V(vin) - fb >= vcm, reports fb and V(vin) - fb, and
only then shifts the decision into the history. A rising rst crossing, and t = 0,
empty both slots and set decision to vss and both metrics to 0 V. Points less
than 1.25*tr after an event that changes an output's expected value by more
than DELTA are not scored for that output. A change of DELTA or less is no
change, and the expected value keeps its previous value. decision and fb_metric
come from the history and the tap codes and are compared exactly; slicer_in_dbg,
computed from the sampled vin, with DELTA. Whether a control input starts within 50 mV
of vth, rests on it, or touches it and returns is judged on its definition in the case
netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

SIGNALS = ('vin', 'clk', 'rst', 'tap1_1', 'tap1_0', 'tap2_1', 'tap2_0', 'decision', 'fb_metric', 'slicer_in_dbg')
CONTROLS = ('clk', 'rst', 'tap1_1', 'tap1_0', 'tap2_1', 'tap2_0')
TAPS = ('tap1_1', 'tap1_0', 'tap2_1', 'tap2_0')
DEFAULTS = {'vdd': .9, 'vss': 0., 'vcm': .45, 'vth': .45, 'tap_lsb': 20e-3, 'tr': 200e-12}
RANGES = {'vdd': (.5, 1.5), 'vss': (-.5, .5), 'vcm': (.2, .7), 'vth': (.2, .7),
          'tap_lsb': (5e-3, 50e-3), 'tr': (10e-12, 1e-9)}
SWING_MIN = .4               # vdd - vss
LOGIC_HIGH = .9              # controls switch between 0 V and 0.9 V
START_MARGIN = .05           # controls at t = 0 at least this far from vth
LEVEL_MARGIN = .1            # rst and tap inputs at a rising clk crossing, from vth
MIN_SPACING = .5e-9          # successive crossings of one control
MIN_EDGE_SPACING = 2e-9      # successive rising clk crossings
GUARD = .5e-9                # rst and tap crossings to rising clk crossings
VIN_SPAN = .4                # vin within vcm +- 0.4 V
VIN_WINDOW = 100e-12         # vin stillness around a rising clk crossing
VIN_STILL = .25e-3
SLICER_MARGIN = 5e-3         # every expected slicer input from vcm
DELTA = 1e-4                 # change threshold of the instruction: slicer_in_dbg
FAILURE_LIMIT = 20
REL = 1 - 1e-6


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


def inside(value, lo, hi):
    slack = 1e-6 * max(abs(lo), abs(hi))
    return lo - slack <= value <= hi + slack


def crossings(rows, node, level):
    """(time, rising) for each pass of node through level, linear between rows.

    Rows are compared with the level exactly; a row on the level is on neither side. A
    crossing is a change of side between successive rows off the level, at the single
    row on the level between them if there is one. A touch, with rows on the same side
    around a row on the level, is no crossing. Starting, resting or touching the level is a
    bench obligation judged on the stimulus definition (check_stimulus), not here. A row on
    the level that ends the record after a row off it is a crossing in the direction of
    arrival; a row on the level that begins the record is none.
    """
    found, last = [], None
    for j, r in enumerate(rows):
        if r[node] == level:
            continue
        if last is not None and (r[node] > level) != (rows[last][node] > level):
            a = rows[last]
            t = rows[j - 1]['time'] if j - last == 2 else \
                a['time'] + (level - a[node]) * (r['time'] - a['time']) / (r[node] - a[node])
            found.append((t, r[node] > level))
        last = j
    if last == len(rows) - 2 and rows[-1][node] == level:
        found.append((rows[-1]['time'], rows[last][node] < level))
    return found


class Wave:
    """Saved rows of one case with linear interpolation."""

    def __init__(self, rows):
        self.rows, self.ts = rows, [r['time'] for r in rows]

    def level(self, t, node):
        j = max(0, min(len(self.rows) - 2, bisect.bisect_right(self.ts, t) - 1))
        a, b = self.rows[j], self.rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    def still(self, t, node, window):
        """Largest movement of node within window of t."""
        lo, hi = bisect.bisect_left(self.ts, t - window), bisect.bisect_right(self.ts, t + window)
        ref = self.level(t, node)
        near = [self.level(t - window, node), self.level(t + window, node)] + [r[node] for r in self.rows[lo:hi]]
        return max(abs(v - ref) for v in near)


def control_crossings(w, vth, case):
    """Bench obligations of the logic inputs; returns their crossings."""
    found = {}
    for name in CONTROLS:
        if any(not -1e-3 <= r[name] <= LOGIC_HIGH + 1e-3 for r in w.rows):
            raise ValueError(f'{name} outside 0 V to 0.9 V')
        # start (at least 50 mV from vth), rest and touch: on the input's definition in the case netlist
        check_stimulus(case, [(name, 'vth', [(name, 1)], vth, single, written(START_MARGIN) * written(REL), None)])
        xs = crossings(w.rows, name, vth)
        high0 = w.rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 0.5 ns')
        found[name] = xs
    if w.rows[0]['clk'] > vth:
        raise ValueError('clk must start low')
    rises = [t for t, up in found['clk'] if up]
    if any(b - a < MIN_EDGE_SPACING * REL for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 2 ns')
    return found


def apart(times, others, gap, message):
    for t in times:
        k = bisect.bisect_left(others, t)
        for o in others[max(0, k - 1):k + 1]:
            if abs(t - o) < gap * REL:
                raise ValueError(message)


def run_dfe(w, p, events, rst_high):
    """The receiver contract on the merged events. Returns output change lists and decisions."""
    vdd, vss, vcm, vth, lsb = (p[k] for k in ('vdd', 'vss', 'vcm', 'vth', 'tap_lsb'))
    h1 = h2 = 0
    since_reset = 0
    changes = {'decision': [(0., vss, 'initial state')], 'fb_metric': [(0., 0., 'initial state')],
               'slicer_in_dbg': [(0., 0., 'initial state')]}
    decisions, resets, edges_in_reset = [], 0, 0

    def put(t, cause, **values):
        for node, v in values.items():
            changes[node].append((t, v, cause))

    for t, kind in events:
        if kind == 'rst_up':
            rst_high = True
            resets += 1
            h1 = h2 = 0
            since_reset = 0
            put(t, 'rst rising crossing', decision=vss, fb_metric=0., slicer_in_dbg=0.)
            continue
        if kind == 'rst_down':
            rst_high = False
            continue
        if rst_high:
            edges_in_reset += 1
            continue
        k1 = 2 * (w.level(t, 'tap1_1') > vth) + (w.level(t, 'tap1_0') > vth)
        k2 = 2 * (w.level(t, 'tap2_1') > vth) + (w.level(t, 'tap2_0') > vth)
        if w.still(t, 'vin', VIN_WINDOW) >= VIN_STILL:
            raise ValueError('vin moves by 0.25 mV or more within 100 ps of a rising clk crossing')
        x = w.level(t, 'vin')
        fb = lsb * (k1 * h1 + k2 * h2)
        s = x - fb
        d = 1 if s >= vcm else -1
        since_reset += 1
        n = len(decisions)
        decisions.append({'time': t, 'vin': x, 'k1': k1, 'k2': k2, 'h1': h1, 'h2': h2, 'fb': fb, 's': s, 'd': d,
                          'after_reset': since_reset})
        put(t, f'decision {n} (h1={h1:+d}, h2={h2:+d}, k1={k1}, k2={k2})',
            decision=vdd if d > 0 else vss, fb_metric=fb, slicer_in_dbg=s)
        h2, h1 = h1, d
    return changes, decisions, resets, edges_in_reset


def distinct(changes, delta=None):
    """Keep only entries that change the value: an unchanged output opens no unscored window.

    With delta (a value computed from the sampled vin), a change of delta or less is no change."""
    out = changes[:1]
    for entry in changes[1:]:
        if (entry[1] != out[-1][1]) if delta is None else (abs(entry[1] - out[-1][1]) > delta):
            out.append(entry)
    return out


def score(w, expected, skip, atol):
    """expected[node] = [(t, value, cause)]; skip = unscored time after a change of that node."""
    instants = {n: [c[0] for c in ch] for n, ch in expected.items()}
    failures, checks, worst, bad = [], 0, 0., {}
    for r in w.rows:
        t = r['time']
        for node, ch in expected.items():
            k = bisect.bisect_right(instants[node], t) - 1
            if k > 0 and t < instants[node][k] + skip:
                continue
            want = ch[k][1]
            checks += 1
            error = abs(r[node] - want)
            worst = max(worst, error)
            if error > atol:
                bad[(node, k)] = max(bad.get((node, k), 0.), error)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': node, 'expected': want, 'actual': r[node],
                                     'change_time': instants[node][k], 'cause': ch[k][2]})
    summary = [{'node': n, 'change_time': instants[n][k], 'cause': expected[n][k][2], 'expected': expected[n][k][1],
                'max_error': e} for (n, k), e in sorted(bad.items())[:FAILURE_LIMIT]]
    return failures, checks, worst, summary, len(bad)


def coverage(decisions, vcm):
    """Counts that show what a case exercises; they are not scored."""
    pairs = 0
    for i, a in enumerate(decisions):
        for b in decisions[i + 1:]:
            if (abs(a['vin'] - b['vin']) < 1e-3 and (a['k1'], a['k2']) == (b['k1'], b['k2'])
                    and (a['h1'], a['h2']) != (b['h1'], b['h2']) and a['d'] != b['d']):
                pairs += 1
    changed = sum(1 for a, b in zip(decisions, decisions[1:])
                  if (a['k1'], a['k2']) != (b['k1'], b['k2']) and b['after_reset'] > 1)
    return {'decisions': len(decisions),
            'first_after_reset': sum(d['after_reset'] == 1 for d in decisions),
            'second_after_reset': sum(d['after_reset'] == 2 for d in decisions),
            'decided_against_raw_input': sum(d['d'] != (1 if d['vin'] >= vcm else -1) for d in decisions),
            'same_input_different_history_pairs': pairs,
            'first_decision_after_tap_change': changed,
            'tap_codes': sorted({(d['k1'], d['k2']) for d in decisions}),
            'histories': sorted({(d['h1'], d['h2']) for d in decisions}),
            'min_slicer_margin_mV': min(abs(d['s'] - vcm) for d in decisions) * 1e3}


def evaluate(rows, case, work):
    p = {k: float(v) for k, v in {**DEFAULTS, **case.get('params', {})}.items()}
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    if len(rows) < 2 or any(not {'time', *SIGNALS}.issubset(r) for r in rows):
        raise ValueError('missing required signals')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('nonfinite evidence')
    ts = [r['time'] for r in rows]
    if any(a >= b for a, b in zip(ts, ts[1:])):
        raise ValueError('waveform time must increase')
    if ts[0] > 1e-15 or abs(ts[-1] - case['stop']) > max(1e-15, case['stop'] * 1e-6):
        raise ValueError('incomplete transient')
    # Resolution and the stimulus domain are bench obligations. A candidate
    # cannot repair them, so they are not candidate failures.
    vdd, vss, vcm, vth, tr = (p[k] for k in ('vdd', 'vss', 'vcm', 'vth', 'tr'))
    if any(not inside(p[k], lo, hi) for k, (lo, hi) in RANGES.items()) or vdd - vss < SWING_MIN * REL:
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(abs(r['vin'] - vcm) > VIN_SPAN + 1e-9 for r in rows):
        raise ValueError('vin outside vcm +- 0.4 V')
    w = Wave(rows)
    found = control_crossings(w, vth, case)
    rises = [t for t, up in found['clk'] if up]
    if not rises:
        raise ValueError('no rising clk crossing')
    apart([t for t, _ in found['rst']], rises, GUARD, 'rst crossing within 0.5 ns of a rising clk crossing')
    apart([t for n in TAPS for t, _ in found[n]], rises, GUARD, 'tap crossing within 0.5 ns of a rising clk crossing')
    for t in rises:
        if any(abs(w.level(t, n) - vth) < LEVEL_MARGIN * REL for n in ('rst',) + TAPS):
            raise ValueError('rst or a tap input is in transition at a rising clk crossing')
    events = sorted([(t, 'rst_up' if up else 'rst_down') for t, up in found['rst']] + [(t, 'clk') for t in rises])
    changes, decisions, resets, edges_in_reset = run_dfe(w, p, events, w.rows[0]['rst'] > vth)
    if not decisions:
        raise ValueError('no decision event')
    margin = min(abs(d['s'] - vcm) for d in decisions)
    if margin < SLICER_MARGIN * REL:
        raise ValueError('a slicer input within 5 mV of vcm')
    expected = {n: distinct(ch, DELTA if n == 'slicer_in_dbg' else None) for n, ch in changes.items()}
    skip = 1.25 * tr
    atol = float(case.get('atol', .002))
    failures, checks, worst, summary, nbad = score(w, expected, skip, atol)
    if checks == 0:
        raise ValueError('no scored observations')
    stats = dict(coverage(decisions, vcm), resets=resets, clk_edges_in_reset=edges_in_reset,
                 output_changes={n: len(ch) - 1 for n, ch in expected.items()})
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': nbad, 'max_error': worst, 'atol': atol, 'stats': stats,
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

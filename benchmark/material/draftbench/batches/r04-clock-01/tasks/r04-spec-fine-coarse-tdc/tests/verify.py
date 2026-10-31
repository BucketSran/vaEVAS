"""Independent waveform contract for fine_coarse_tdc; reads saved waveforms and the case netlist's sources.

No candidate source, reference model or reference waveform is read. Rising and
falling crossings through vth come from the saved rows, taken as linear between
rows; an input that touches vth and returns to the same side does not cross.
T_ref is the spacing of the recorded rising ref_clk crossings, which the bench
keeps constant; two crossings give it. With fewer the converter never becomes
ready, so the outputs stay low and no fine code is needed. A fine code is
floor(16*(t - r)/T_ref) with r the latest ref crossing at or before t; N counts
ref crossings after the start and at or before the stop; a stop publishes
D = 16*N + q_e - q_s, and the 16th crossing without a stop publishes 255 with
overflow. Warm-up needs two ref crossings after t = 0 or the last rst release;
rst clears and ends a measurement. Points less than 1.25*tr after a change of
the expected outputs are not scored. A bench whose input starts within 50 mV of
vth, rests on it, touches it and returns, or moves less than 50 mV from vth
between successive crossings is outside the contract; that is judged on the
input's definition in the case netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

BITS = ('code_7', 'code_6', 'code_5', 'code_4', 'code_3', 'code_2', 'code_1', 'code_0')
OUTPUTS = BITS + ('valid', 'overflow')
INPUTS = ('start', 'stop', 'ref_clk', 'rst')
DEFAULTS = {'vth': .45, 'vdd': .9, 'tr': 200e-12}
RANGES = {'vth': (.2, .7), 'vdd': (.5, 1.5), 'tr': (10e-12, 1e-9)}
PERIOD_RANGE = (1e-9, 20e-9)
FINE = 16
OVERFLOW_EDGE = 16
START_MARGIN = .05          # each input at t = 0 is at least this far from vth
MIN_SPACING = 100e-12       # successive crossings of one input; start to stop
CODE_MARGIN = 20e-12        # start and stop events to every r + k*T_ref/16
RST_GUARD = 100e-12         # rst crossings to rising start, stop and ref crossings
PERIOD_JITTER = 1e-12       # allowed spread of the recorded ref spacing
CROSSING_EXCURSION = .05    # each input moves at least this far from vth between successive crossings
SAMPLE_SLACK = 1e-3         # the error is raised below CROSSING_EXCURSION less this (value of the row check)
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


def expected_changes(edges, rst_high, period, stop):
    """Changes of the expected output vector (code, valid, overflow) and the measurements."""
    order = {'ref': 0, 'rst_up': 1, 'rst_down': 1, 'start': 2, 'stop': 2}   # a ref crossing counts as before
    events = sorted(edges, key=lambda e: (e[0], order[e[1]]))
    out, changes, measurements = (0, 0, 0), [(0., (0, 0, 0), 'initial state')], []
    seen, armed, last = 0, None, None

    def publish(t, value, cause):
        nonlocal out
        if value != out:
            out = value
            changes.append((t, value, cause))

    def fine(t):
        return math.floor(FINE * (t - last) / period)

    for t, kind in events:
        if t > stop:
            break
        if kind == 'rst_up':
            rst_high, seen = True, 0
            if armed is not None:
                armed['outcome'] = 'ended by reset'
            armed = None
            publish(t, (0, 0, 0), 'rst rising crossing')
        elif kind == 'rst_down':
            rst_high, seen = False, 0
        elif kind == 'ref':
            if rst_high:
                continue
            last, seen = t, min(seen + 1, 2)
            if armed is not None:
                armed['n'] += 1
                if armed['n'] == OVERFLOW_EDGE:
                    armed.update(outcome='overflow', end=t, code=255)
                    publish(t, (255, 1, 1), f"overflow of the measurement started at {armed['start']:.6g} s")
                    armed = None
        elif kind == 'start':
            if rst_high or seen < 2:
                measurements.append({'start': t, 'outcome': 'start ignored (reset)' if rst_high else 'start ignored (warm-up)'})
                continue
            if armed is not None:
                armed['outcome'] = 'cancelled by a new start'
            armed = {'start': t, 'q_s': fine(t), 'n': 0, 'outcome': 'running at stop'}
            measurements.append(armed)
            publish(t, (0, 0, 0), 'start event clears the result')
        elif kind == 'stop':
            if armed is None:
                continue
            q_e = fine(t)
            code = FINE * armed['n'] + q_e - armed['q_s']
            armed.update(outcome='result', end=t, q_e=q_e, code=code,
                         interval_in_fine_steps=FINE * (t - armed['start']) / period)
            publish(t, (code, 1, 0), f"stop of the measurement started at {armed['start']:.6g} s")
            armed = None
    return changes, measurements


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    vth, vdd, tr = (float(p[k]) for k in ('vth', 'vdd', 'tr'))
    atol = float(case.get('atol', .01))
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    if len(rows) < 2 or any(not {'time', *INPUTS, *OUTPUTS}.issubset(r) for r in rows):
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
    if any(not lo * REL <= float(p[k]) <= hi / REL for k, (lo, hi) in RANGES.items()):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(not -1e-3 <= r[n] <= .9 + 1e-3 for r in rows for n in INPUTS):
        raise ValueError('an input outside 0 V to 0.9 V')
    # Every input starts at least 50 mV from vth, never rests on it, never touches it and returns, and
    # between successive crossings moves at least 50 mV away from it, far beyond the cross() expression
    # tolerance. These are judged on the input's definition in the case netlist (check_stimulus); the
    # error is raised below 50 mV less SAMPLE_SLACK.
    check_stimulus(case, [(n, 'vth', [(n, 1)], vth, single, written(START_MARGIN) * written(REL),
                           written(CROSSING_EXCURSION) - written(SAMPLE_SLACK)) for n in INPUTS])
    if rows[0]['ref_clk'] > vth:
        raise ValueError('ref_clk must start low')

    found = {n: crossings(rows, n, vth) for n in INPUTS}
    for name, xs in found.items():
        high0 = rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 100 ps')
    refs = [t for t, up in found['ref_clk'] if up]
    # Two rising crossings give T_ref. With fewer the warm-up never completes, so no
    # measurement begins and no fine code is needed: the outputs must stay low.
    period = None
    if len(refs) >= 2:
        spacing = [b - a for a, b in zip(refs, refs[1:])]
        period = sum(spacing) / len(spacing)
        if max(spacing) - min(spacing) > PERIOD_JITTER or not PERIOD_RANGE[0] * REL <= period <= PERIOD_RANGE[1] / REL:
            raise ValueError('ref_clk period not constant or outside 1 ns to 20 ns')
    starts = [t for t, up in found['start'] if up]
    stops = [t for t, up in found['stop'] if up]
    if any(abs(a - b) < MIN_SPACING * REL for a in starts for b in stops):
        raise ValueError('start and stop events closer than 100 ps')
    if period is not None:
        step = period / FINE
        for t in starts + stops:
            k = bisect.bisect_right(refs, t) - 1
            if k < 0:
                continue
            offset = (t - refs[k]) % step
            if offset < CODE_MARGIN * REL or step - offset < CODE_MARGIN * REL:
                raise ValueError('a start or stop event within 20 ps of a fine-code boundary')
    rising = refs + starts + stops
    if any(abs(t - x) < RST_GUARD * REL for t, _ in found['rst'] for x in rising):
        raise ValueError('rst crossing within 100 ps of a rising start, stop or ref_clk crossing')

    edges = ([(t, 'ref') for t in refs] + [(t, 'start') for t in starts] + [(t, 'stop') for t in stops]
             + [(t, 'rst_up' if up else 'rst_down') for t, up in found['rst']])
    changes, measurements = expected_changes(edges, rows[0]['rst'] > vth, period, ts[-1])
    instants = [c[0] for c in changes]
    skip = 1.25 * tr
    failures, checks, worst, bad = [], 0, 0., {}
    for r in rows:
        t = r['time']
        k = bisect.bisect_right(instants, t) - 1
        if k > 0 and t < instants[k] + skip:
            continue
        code, valid, overflow = changes[k][1]
        want = {b: vdd * ((code >> (7 - j)) & 1) for j, b in enumerate(BITS)}
        want.update(valid=vdd * valid, overflow=vdd * overflow)
        checks += 1
        for node, expected in want.items():
            error = abs(r[node] - expected)
            worst = max(worst, error)
            if error > atol:
                bad[k] = max(bad.get(k, 0.), error)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': node, 'expected': expected, 'actual': r[node],
                                     'expected_code': code, 'expected_valid': valid, 'expected_overflow': overflow,
                                     'output_change': k, 'change_time': instants[k], 'cause': changes[k][2]})
    if checks == 0:
        raise ValueError('no scored observations')
    summary = [{'output_change': k, 'change_time': instants[k], 'cause': changes[k][2],
                'expected': {'code': changes[k][1][0], 'valid': changes[k][1][1], 'overflow': changes[k][1][2]},
                'max_error': e} for k, e in sorted(bad.items())[:FAILURE_LIMIT]]
    results = [m for m in measurements if m['outcome'] == 'result']
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': len(bad), 'max_error': worst, 'atol': atol,
            'ref_period_s': period, 'output_changes': len(changes) - 1,
            'measurements': {'results': len(results),
                             'overflows': sum(m['outcome'] == 'overflow' for m in measurements),
                             'borrows': sum(m['q_e'] < m['q_s'] for m in results),
                             'same_period': sum(m['n'] == 0 for m in results),
                             'cancelled_by_start': sum(m['outcome'] == 'cancelled by a new start' for m in measurements),
                             'ended_by_reset': sum(m['outcome'] == 'ended by reset' for m in measurements),
                             'ignored_starts': sum(m['outcome'].startswith('start ignored') for m in measurements),
                             'max_quantization_difference': max((abs(m['code'] - m['interval_in_fine_steps'])
                                                                 for m in results), default=None)},
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

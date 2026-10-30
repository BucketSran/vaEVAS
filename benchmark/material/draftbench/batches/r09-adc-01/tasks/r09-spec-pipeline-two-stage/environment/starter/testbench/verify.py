"""Independent waveform contract for pipeline_adc_two_stage; reads saved waveforms and the netlist's sources.

No candidate source, reference model or reference waveform is read. Crossings of
clk, rst and valid_i through vth and the sampled vin come from the saved rows,
taken as linear between rows; an input that touches vth and returns to the same
side does not cross. A clock edge is a rising clk crossing while rst is
low, and it takes a sample when valid_i is high. A sample x (vin limited to
[vss, vref]) has coarse code k, residue r = (vss + vref)/2 + 4*(x - c_k) about
the bin center c_k, and fine code f of r. Its code 4*k + f is published two clock
edges later with valid_o high; residue_dbg shows the r that stage 1 holds. A
rising rst crossing discards samples in progress and clears the outputs. Points
less than 1.25*tr after a change of the expected outputs are not scored. The
codes and valid_o compare exactly; the expected residue_dbg, taken from the
sampled vin, changes only by more than DELTA, and after a smaller move it keeps
its previous value. Whether clk, rst or valid_i starts within 50 mV of vth, rests on
it, touches it and returns, or moves less than 50 mV away from it between successive
crossings is judged on its definition in the case netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

BITS = ('code_3', 'code_2', 'code_1', 'code_0')
OUTPUTS = BITS + ('valid_o', 'residue_dbg')
CONTROLS = ('clk', 'rst', 'valid_i')
DEFAULTS = {'vdd': .9, 'vss': 0., 'vref': .9, 'vth': .45, 'tr': 200e-12}
RANGES = {'vss': (-.5, .5), 'vth': (.2, .7), 'tr': (10e-12, 1e-9)}
SPAN_RANGE = (.4, 2.)       # vref - vss
SWING_RANGE = (.5, 2.)      # vdd - vss
VIN_MARGIN = .2             # vin stays within vss - 0.2 V and vref + 0.2 V
START_MARGIN = .05          # each control input at t = 0 is at least this far from vth
MIN_SPACING = 100e-12       # successive crossings of one control input
MIN_EDGE_SPACING = 4e-9     # successive rising clk crossings
GUARD = 100e-12             # valid_i and rst crossings to every rising clk crossing
VIN_STILL = .25e-3          # vin movement within GUARD of a rising clk crossing
CODE_MARGIN = 3e-3          # sampled x to every code boundary vss + j*span/16
CROSSING_EXCURSION = .05    # each control input moves at least this far from vth between its crossings
SAMPLE_SLACK = 1e-3         # the error is raised below CROSSING_EXCURSION less this (value of the row check)
DELTA = .25e-3              # change threshold of the instruction for the expected residue_dbg
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


def quarter(v, vss, span):
    """Number of the thresholds vss + span/4, vss + span/2, vss + 3*span/4 at or below v."""
    return sum(v >= vss + j * span / 4 for j in (1, 2, 3))


def convert(x, vss, vref):
    """Coarse code, residue and fine code of a limited sample x."""
    span = vref - vss
    k = quarter(x, vss, span)
    r = (vss + vref) / 2 + 4 * (x - (vss + (k + .5) * span / 4))
    return k, r, quarter(r, vss, span)


def expected_changes(events, rst_high, level, vth, vss, vref):
    """Changes of the expected output vector (code, valid, residue) and the samples."""
    out = (0, 0, vss)
    changes, samples = [(0., out, 'initial state')], []
    held = {'r': vss, 'sample': None}      # stage 1: the held sample; x = vss when cleared
    fresh = None                           # sample taken at the latest clock edge
    stage2 = None                          # sample decided by stage 2 at the latest clock edge
    edge = 0

    def publish(t, value, cause):
        nonlocal out
        # The code and valid_o come from integer states and compare exactly. The residue comes from the
        # sampled vin: a change of DELTA or less is no change, and the previous expected value stays.
        if value[:2] != out[:2] or abs(value[2] - out[2]) > DELTA:
            out = value
            changes.append((t, value, cause))

    for t, kind in events:
        if kind == 'rst_up':
            rst_high = True
            for s in (fresh, stage2):
                if s is not None:
                    s['outcome'] = 'discarded by reset'
            held, fresh, stage2 = {'r': vss, 'sample': None}, None, None
            publish(t, (0, 0, vss), 'rst rising crossing')
            continue
        if kind == 'rst_down':
            rst_high = False
            continue
        if rst_high:
            continue
        edge += 1
        code, valid = out[0], 0
        if stage2 is not None:
            code, valid = 4 * stage2['k'] + stage2['f'], 1
            stage2.update(outcome='published', published_edge=edge, published_time=t)
            cause = f"edge {edge}: publish sample {stage2['index']} taken at edge {stage2['edge']}"
        else:
            cause = f'edge {edge}: no result'
        stage2 = fresh
        if stage2 is not None:
            stage2['f'] = held['f']
        fresh = None
        if level(t, 'valid_i') > vth:
            x = min(max(level(t, 'vin'), vss), vref)
            k, r, f = convert(x, vss, vref)
            fresh = {'index': len(samples), 'edge': edge, 'time': t, 'x': x, 'k': k, 'r': r,
                     'outcome': 'in progress at stop'}
            samples.append(fresh)
            held = {'r': r, 'f': f, 'sample': fresh['index']}
            cause += f"; take sample {fresh['index']}"
        publish(t, (code, valid, held['r']), cause)
    return changes, samples, edge


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    vdd, vss, vref, vth, tr = (float(p[k]) for k in ('vdd', 'vss', 'vref', 'vth', 'tr'))
    span = vref - vss
    atol = float(case.get('atol', .002))
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    if len(rows) < 2 or any(not {'time', 'vin', *CONTROLS, *OUTPUTS}.issubset(r) for r in rows):
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
    if (any(not inside(float(p[k]), lo, hi) for k, (lo, hi) in RANGES.items())
            or not inside(span, *SPAN_RANGE) or not inside(vdd - vss, *SWING_RANGE)):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(not vss - VIN_MARGIN - 1e-9 <= r['vin'] <= vref + VIN_MARGIN + 1e-9 for r in rows):
        raise ValueError('vin outside vss - 0.2 V to vref + 0.2 V')
    if any(not -1e-3 <= r[n] <= .9 + 1e-3 for r in rows for n in CONTROLS):
        raise ValueError('a control input outside 0 V to 0.9 V')
    # Each control input starts at least 50 mV from vth, never rests on it, never touches it and returns,
    # and between successive crossings moves at least 50 mV away from it, far beyond the cross() expression
    # tolerance. These are judged on its definition in the case netlist (check_stimulus); the error is
    # raised below 50 mV less SAMPLE_SLACK.
    check_stimulus(case, [(n, 'vth', [(n, 1)], vth, single, written(START_MARGIN) * written(REL),
                           written(CROSSING_EXCURSION) - written(SAMPLE_SLACK)) for n in CONTROLS])
    if rows[0]['clk'] > vth:
        raise ValueError('clk must start low')

    found = {n: crossings(rows, n, vth) for n in CONTROLS}
    for name, xs in found.items():
        high0 = rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 100 ps')
    rises = [t for t, up in found['clk'] if up]
    if not rises:
        raise ValueError('no rising clk crossing')
    if any(b - a < MIN_EDGE_SPACING * REL for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 4 ns')
    for name in ('valid_i', 'rst'):
        if any(abs(t - c) < GUARD * REL for t, _ in found[name] for c in rises):
            raise ValueError(f'{name} crossing within 100 ps of a rising clk crossing')

    def level(t, node):
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        a, b = rows[j], rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    still = 0.
    for c in rises:
        lo, hi = bisect.bisect_left(ts, c - GUARD), bisect.bisect_right(ts, c + GUARD)
        near = [level(c - GUARD, 'vin'), level(c + GUARD, 'vin')] + [r['vin'] for r in rows[lo:hi]]
        still = max(still, max(abs(v - level(c, 'vin')) for v in near))
    if still >= VIN_STILL:
        raise ValueError('vin moves by 0.25 mV or more within 100 ps of a rising clk crossing')

    events = sorted([(t, 'clk') for t in rises] + [(t, 'rst_up' if up else 'rst_down') for t, up in found['rst']])
    changes, samples, edges = expected_changes(events, rows[0]['rst'] > vth, level, vth, vss, vref)
    boundaries = [vss + j * span / 16 for j in range(1, 16)]
    margin = min((min(abs(s['x'] - b) for b in boundaries) for s in samples), default=None)
    if margin is not None and margin < CODE_MARGIN * REL:
        raise ValueError('a sample within 3 mV of a code boundary')

    instants = [c[0] for c in changes]
    skip = 1.25 * tr
    failures, checks, worst, bad = [], 0, 0., {}
    for r in rows:
        t = r['time']
        k = bisect.bisect_right(instants, t) - 1
        if k > 0 and t < instants[k] + skip:
            continue
        code, valid, residue = changes[k][1]
        want = {b: vdd if (code >> (3 - j)) & 1 else vss for j, b in enumerate(BITS)}
        want.update(valid_o=vdd if valid else vss, residue_dbg=residue)
        checks += 1
        for node, expected in want.items():
            error = abs(r[node] - expected)
            worst = max(worst, error)
            if error > atol:
                bad[k] = max(bad.get(k, 0.), error)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': node, 'expected': expected, 'actual': r[node],
                                     'expected_code': code, 'expected_valid': valid, 'expected_residue': residue,
                                     'output_change': k, 'change_time': instants[k], 'cause': changes[k][2]})
    if checks == 0:
        raise ValueError('no scored observations')
    summary = [{'output_change': k, 'change_time': instants[k], 'cause': changes[k][2],
                'expected': {'code': changes[k][1][0], 'valid': changes[k][1][1], 'residue': changes[k][1][2]},
                'max_error': e} for k, e in sorted(bad.items())[:FAILURE_LIMIT]]
    published = [s for s in samples if s['outcome'] == 'published']
    taken_edges = {s['edge'] for s in samples}
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': len(bad), 'max_error': worst, 'atol': atol,
            'output_changes': len(changes) - 1,
            'pipeline': {'clock_edges': edges, 'edges_in_reset': len(rises) - edges, 'samples': len(samples),
                         'published': len(published),
                         'discarded_by_reset': sum(s['outcome'] == 'discarded by reset' for s in samples),
                         'in_progress_at_stop': sum(s['outcome'] == 'in progress at stop' for s in samples),
                         'back_to_back': sum(s['edge'] - 1 in taken_edges for s in samples),
                         'edges_without_sample': edges - len(samples),
                         'codes_published': sorted({4 * s['k'] + s['f'] for s in published}),
                         'min_code_margin_mV': None if margin is None else margin * 1e3,
                         'max_vin_move_near_edges_mV': still * 1e3},
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

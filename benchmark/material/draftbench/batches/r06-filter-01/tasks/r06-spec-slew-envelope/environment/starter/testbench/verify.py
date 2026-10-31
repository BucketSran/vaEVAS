"""Independent waveform contract for slew_envelope_tracker; reads saved waveforms and the netlist's sources.

No candidate source, reference model or reference waveform is read. The envelope is
rebuilt from the recorded rst and clk crossings and the recorded vin and mode at each
crossing. Each output's trajectory starts at 0 V and moves toward its target (env for
out, env/0.8 for metric) with slope +rise_rate or -fall_rate, stopping on it. Every
event may take effect up to EVENT_TOL before or after its crossing. The dynamics are
order preserving, so the allowed values at time t lie between the responses to the
lowest and the highest target that the shifted events allow; a saved point passes
when it is within atol of that range. Whether clk, mode or rst starts within 50 mV
of vth, rests on it, or touches it and returns is judged on its definition in the
case netlist, never on saved rows.
"""
import bisect
import math
import re
from fractions import Fraction

from v2_runtime import main

SIGNALS = ('vin', 'clk', 'mode', 'rst', 'out', 'metric')
DEFAULTS = {'vth': 0.45, 'rise_rate': 8e8, 'fall_rate': 3e8}
ENV_MAX = 0.8                # envelope clamp; metric target = env / ENV_MAX
SCALES = {'out': 1.0, 'metric': 1.0 / ENV_MAX}
EVENT_TOL = 50e-12           # an event may take effect this much early or late
MIN_RISE_SPACING = 5e-9      # successive rising clk crossings
CONTROL_GUARD = 1e-9         # mode/rst crossing to any rising clk crossing
START_MARGIN = .05           # clk, mode and rst at t = 0 are at least this far from vth
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


def response(steps, rise, fall, stop):
    """Breakpoints (t, y) of the slew-limited response to target steps (t, target), from 0 V, up to stop.

    A step at or after stop cannot move a saved point, so it is dropped; the breakpoint
    times then never decrease.
    """
    points, y, t0, target = [(0.0, 0.0)], 0.0, 0.0, 0.0
    for t, new in [s for s in steps if s[0] < stop] + [(stop, None)]:
        if y != target:
            rate = rise if target > y else fall
            t_end = t0 + abs(target - y) / rate
            if t_end < t:
                points.append((t_end, target))
                y = target
            else:
                y += math.copysign(rate * (t - t0), target - y)
        points.append((t, y))
        t0 = t
        if new is not None:
            target = new
    return points


def shifted(steps, tol, pick):
    """Target steps of min (pick=min) or max over a +-tol window of the step target."""
    def target_at(t):
        k = bisect.bisect_right(times, t) - 1
        return steps[k][1] if k >= 0 else 0.0
    times = [t for t, _ in steps]
    edges = sorted({max(0.0, t + d) for t in times for d in (-tol, tol)})
    found, last = [], 0.0
    for a, b in zip(edges, edges[1:] + [edges[-1] + 2 * tol]):
        mid = (a + b) / 2
        inside = [target_at(mid - tol), target_at(mid + tol)] + [v for t, v in steps if mid - tol < t < mid + tol]
        value = pick(inside)
        if value != last:
            found.append((a, value))
            last = value
    return found


def value(points, times, t):
    j = max(0, min(len(points) - 2, bisect.bisect_right(times, t) - 1))
    (ta, ya), (tb, yb) = points[j], points[j + 1]
    return ya if tb == ta else ya + (yb - ya) * (t - ta) / (tb - ta)


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    vth, rise, fall = float(p['vth']), float(p['rise_rate']), float(p['fall_rate'])
    atol = float(case.get('atol', .002))
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    if len(rows) < 2 or any(not {'time', *SIGNALS}.issubset(r) for r in rows):
        raise ValueError('missing required signals')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('nonfinite evidence')
    ts = [r['time'] for r in rows]
    if any(a >= b for a, b in zip(ts, ts[1:])):
        raise ValueError('waveform time must increase')
    stop = case['stop']
    if ts[0] > 1e-15 or abs(ts[-1] - stop) > max(1e-15, stop * 1e-6):
        raise ValueError('incomplete transient')
    # Resolution and the stimulus domain are bench obligations. A candidate
    # cannot repair them, so they are not candidate failures.
    if max(b - a for a, b in zip(ts, ts[1:])) > case.get('resolution', 5e-11) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if not (1e8 <= rise <= 4e9 and 1e8 <= fall <= 4e9 and 0 < vth < .9):
        raise ValueError('case parameters outside the public contract')
    if any(not -.5 - 1e-9 <= r['vin'] <= 1.2 + 1e-9 for r in rows):
        raise ValueError('vin outside the public contract')
    # clk, mode and rst start at least 50 mV from vth, never rest on it and never touch it and return: judged
    # on their definitions in the case netlist (check_stimulus).
    check_stimulus(case, [(n, 'vth', [(n, 1)], vth, single, written(START_MARGIN) * written(1 - 1e-6), None)
                          for n in ('clk', 'mode', 'rst')])

    def level(t, node):
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        a, b = rows[j], rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    clk = crossings(rows, 'clk', vth)
    if not clk or clk[0][1] is not True or rows[0]['clk'] >= vth:
        raise ValueError('clk must start low and produce a sample event')
    rises = [t for t, up in clk if up]
    if any(b - a < MIN_RISE_SPACING * (1 - 1e-6) for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 5 ns')
    for node in ('mode', 'rst'):
        if any(abs(t - s) < CONTROL_GUARD * (1 - 1e-6) for t, _ in crossings(rows, node, vth) for s in rises):
            raise ValueError(f'{node} crossing within 1 ns of a sample event')

    # Envelope events in time order: a rising rst crossing clears, a rising clk crossing samples.
    env, events, log = 0.0, [], []
    clears = [(t, 'clear') for t, up in crossings(rows, 'rst', vth) if up]
    for t, kind in sorted(clears + [(t, 'sample') for t in rises]):
        if kind == 'clear' or level(t, 'rst') > vth:
            env = 0.0
            kind = 'clear' if kind == 'clear' else 'sample_in_reset'
        else:
            vin, release = level(t, 'vin'), level(t, 'mode') > vth
            env = min(ENV_MAX, max(0.0, vin if release else max(env, vin)))
            kind = 'release' if release else 'peak_hold'
        events.append((t, env))
        log.append({'time': t, 'kind': kind, 'env': env})

    starts = [t for t, _ in events]
    failures, checks, summary = [], 0, {}
    worst = {n: 0. for n in SCALES}
    nominal_error = {n: 0. for n in SCALES}
    for node, scale in SCALES.items():
        steps = [(t, e * scale) for t, e in events]
        nominal = response(steps, rise, fall, ts[-1])
        low = response(shifted(steps, EVENT_TOL, min), rise, fall, ts[-1])
        high = response(shifted(steps, EVENT_TOL, max), rise, fall, ts[-1])
        grids = [[t for t, _ in pts] for pts in (nominal, low, high)]
        for r in rows:
            t, v = r['time'], r[node]
            lo, hi = value(low, grids[1], t), value(high, grids[2], t)
            nominal_error[node] = max(nominal_error[node], abs(v - value(nominal, grids[0], t)))
            excess = max(lo - v, v - hi, 0.)
            checks += 1
            if excess > atol:
                worst[node] = max(worst[node], excess)
                k = bisect.bisect_right(starts, t) - 1
                summary[(node, k)] = max(summary.get((node, k), 0.), excess)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': node, 'actual': v, 'allowed_low': lo, 'allowed_high': hi,
                                     'event': k, 'event_time': starts[k] if k >= 0 else None,
                                     'event_kind': log[k]['kind'] if k >= 0 else None})
    if checks == 0:
        raise ValueError('no scored observations')
    failed = [{'node': n, 'event': k, 'event_time': starts[k] if k >= 0 else None,
               'event_kind': log[k]['kind'] if k >= 0 else None, 'max_error': e}
              for (n, k), e in sorted(summary.items(), key=lambda item: (item[0][1], item[0][0]))[:FAILURE_LIMIT]]
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_events': failed,
            'failed_event_count': len(summary), 'max_error': max(worst.values()), 'max_error_by_node': worst,
            'max_error_from_nominal': nominal_error, 'atol': atol, 'event_time_tolerance_s': EVENT_TOL,
            'events': len(events), 'event_kinds': {k: sum(e['kind'] == k for e in log) for k in
                                                     ('clear', 'sample_in_reset', 'release', 'peak_hold')}}


if __name__ == '__main__':
    main(evaluate)

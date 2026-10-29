"""Independent waveform contract for the four-bit SAR ADC system; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Crossings
through vth (and the zero crossings of the comparator input difference) are
taken from the saved rows, linear between rows; a touch that returns to the same
side is no crossing. A 'top' case instantiates
sar_adc_top: a start request arms a conversion, the next clock edge samples vin,
and four clock edges decide bits 3..0 by x >= DAC(T) with DAC(c) = vss +
(vref - vss)*c/16. A 'modules' case instantiates the DAC, the comparator, the
sample-and-hold and the controller each on its own, on prefixed nodes. Points
less than 1.25 times an output's deadline after a change of that output's
expected value by more than DELTA are not scored; the deadline is tr, and 2*tr
for dac_dbg of the top module. A change of DELTA or less is no change, and the
expected value keeps its previous value. Values computed from integer state are
compared exactly; the held sample, taken from vin, with DELTA.
"""
import bisect
import math

from v2_runtime import main

DEFAULTS = {'vdd': .9, 'vss': 0., 'vref': .9, 'vth': .45, 'tr': 200e-12}
RANGES = {'vss': (-.5, .5), 'vth': (.2, .7), 'tr': (10e-12, 1e-9)}
SPAN_RANGE = (.4, 2.)        # vref - vss
SWING_RANGE = (.5, 2.)       # vdd - vss
VTH_RAIL_MARGIN = .1         # vth above vss and below vdd
VIN_MARGIN = .2              # vin within vss - 0.2 V and vref + 0.2 V
START_MARGIN = .05           # logic inputs at t = 0 at least this far from vth
MIN_SPACING = 100e-12        # successive crossings of one input
MIN_EDGE_SPACING = 4e-9      # successive rising clk crossings
GUARD = 100e-12              # control crossings to rising clk crossings
VIN_STILL = .25e-3           # vin movement within GUARD of a sampling edge
CODE_MARGIN = 3e-3           # top-level sample to every DAC(j), j = 1..15
DIFF_START = 5e-3            # comparator difference at t = 0
DIFF_SPACING = 1e-9          # successive comparator zero crossings
SAME = 5e-12                 # DAC bit crossings within 5 ps of one another are simultaneous
DELTA = 1e-4                 # change threshold of the instruction: the held sample
FAILURE_LIMIT = 20
TOP_INPUTS = ('vin', 'clk', 'rst', 'start')
TOP_OUTPUTS = ('code_3', 'code_2', 'code_1', 'code_0', 'done', 'sample_dbg', 'dac_dbg')
# Node names of the stand-alone instances in a 'modules' case.
BLOCKS = {
    'cdac': (('cb_3', 'cb_2', 'cb_1', 'cb_0'), ('cdac_o', 'cdac_dbg')),
    'comparator': (('cmp_s', 'cmp_d'), ('cmp_o',)),
    'sample_hold': (('sh_vin', 'sh_clk', 'sh_rst', 'sh_en'), ('sh_o', 'sh_dbg')),
    'controller': (('ct_clk', 'ct_rst', 'ct_start', 'ct_cmp'),
                   ('ct_en', 'ct_t3', 'ct_t2', 'ct_t1', 'ct_t0', 'ct_c3', 'ct_c2', 'ct_c1', 'ct_c0', 'ct_done')),
}
REL = 1 - 1e-6


def inside(value, lo, hi):
    slack = 1e-6 * max(abs(lo), abs(hi))
    return lo - slack <= value <= hi + slack


def crossings(rows, node, level):
    """(time, rising) for each pass of node through level, linear between rows.

    Rows are compared with the level exactly; a row on the level is on neither side. A
    crossing is a change of side between successive rows off the level, at the single
    row on the level between them if there is one. A touch, with rows on the same side
    around a row on the level, is no crossing. Two successive rows on the level mean that
    the input rests there, which the bench must not do. A row on the level that ends the
    record after a row off it is a crossing in the direction of arrival; a row on the
    level that begins the record is none.
    """
    found, last = [], None
    for j, r in enumerate(rows):
        if r[node] == level:
            if j and rows[j - 1][node] == level:
                raise ValueError(f'{node} rests at the threshold')
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

    def still(self, t, node):
        """Largest movement of node within GUARD of t."""
        lo, hi = bisect.bisect_left(self.ts, t - GUARD), bisect.bisect_right(self.ts, t + GUARD)
        ref = self.level(t, node)
        near = [self.level(t - GUARD, node), self.level(t + GUARD, node)] + [r[node] for r in self.rows[lo:hi]]
        return max(abs(v - ref) for v in near)


def check_logic_inputs(w, names, vth, clock=None):
    """Bench obligations of logic inputs; returns their crossings."""
    found = {}
    for name in names:
        if any(not -1e-3 <= r[name] <= .9 + 1e-3 for r in w.rows):
            raise ValueError(f'{name} outside 0 V to 0.9 V')
        if abs(w.rows[0][name] - vth) < START_MARGIN * REL:
            raise ValueError(f'{name} starts within 50 mV of vth')
        xs = crossings(w.rows, name, vth)
        high0 = w.rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 100 ps')
        found[name] = xs
    if clock is not None:
        if w.rows[0][clock] > vth:
            raise ValueError(f'{clock} must start low')
        rises = [t for t, up in found[clock] if up]
        if any(b - a < MIN_EDGE_SPACING * REL for a, b in zip(rises, rises[1:])):
            raise ValueError(f'rising {clock} crossings closer than 4 ns')
    return found


def apart(times, others, gap, message):
    for t in times:
        k = bisect.bisect_left(others, t)
        for o in others[max(0, k - 1):k + 1]:
            if abs(t - o) < gap * REL:
                raise ValueError(message)


def sar_events(clock_rises, rst_x, start_rises, rst_high):
    """Merged control events in time order."""
    return sorted([(t, 'rst_up' if up else 'rst_down') for t, up in rst_x]
                  + [(t, 'clk') for t in clock_rises] + [(t, 'start') for t in start_rises])


def run_sar(events, rst_high, decide, sample=None, vss=0.):
    """The controller contract. decide(t, T, b) -> bit kept; sample(t) -> held value at a sample edge.

    Returns the change lists of T, R, sample_en, done (and the held sample when sample is given) and the
    conversions."""
    state = {'T': 0, 'R': 0, 'en': 0, 'done': 0}
    cleared = dict(state)
    if sample is not None:
        state['held'] = cleared['held'] = vss
    changes = {k: [(0., v, 'initial state')] for k, v in state.items()}
    phase, bitpos, conv, conversions, edge = 'idle', 3, None, [], 0

    def put(t, cause, **values):
        for k, v in values.items():
            # held is a sample of vin: a change of DELTA or less is no change; the rest are integers
            if (abs(v - state[k]) > DELTA) if k == 'held' else v != state[k]:
                state[k] = v
                changes[k].append((t, v, cause))

    for t, kind in events:
        if kind == 'rst_up':
            rst_high = True
            if conv is not None:
                conv['outcome'] = 'abandoned by reset'
            conv, phase = None, 'idle'
            put(t, 'rst rising crossing', **cleared)
            continue
        if kind == 'rst_down':
            rst_high = False
            continue
        if rst_high:
            continue
        if kind == 'start':
            if conv is not None:
                conv['outcome'] = 'abandoned by a new start'
            conv = {'start': t, 'outcome': 'in progress at stop', 'trials': []}
            conversions.append(conv)
            phase = 'armed'
            put(t, f'start request (conversion {len(conversions) - 1})', T=0, R=0, en=1, done=0)
            continue
        edge += 1
        if phase == 'armed':
            conv.update(sample_edge=t, trials=[8])
            phase, bitpos = 'converting', 3
            if sample is not None:
                x = sample(t)
                conv['x'] = x
                put(t, f'sample edge of conversion {len(conversions) - 1}', en=0, T=8, held=x)
            else:
                put(t, f'sample edge of conversion {len(conversions) - 1}', en=0, T=8)
        elif phase == 'converting':
            T = state['T']
            keep = decide(t, T, bitpos)
            R = T if keep else T - (1 << bitpos)
            cause = f'decision of bit {bitpos} in conversion {len(conversions) - 1}'
            if bitpos > 0:
                bitpos -= 1
                put(t, cause, R=R, T=R + (1 << bitpos))
                conv['trials'].append(R + (1 << bitpos))
            else:
                put(t, cause, R=R, T=R, done=1)
                conv.update(outcome='done', code=R, done_edge=t)
                conv, phase = None, 'idle'
    return changes, conversions, edge


def score(w, expected, skips, atol):
    """expected[node] = [(t, value, cause)]; skips[node] = unscored time after a change."""
    instants = {n: [c[0] for c in ch] for n, ch in expected.items()}
    failures, checks, worst, bad = [], 0, 0., {}
    for r in w.rows:
        t = r['time']
        for node, ch in expected.items():
            k = bisect.bisect_right(instants[node], t) - 1
            if k > 0 and t < instants[node][k] + skips[node]:
                continue
            want = ch[k][1]
            checks += 1
            error = abs(r[node] - want)
            worst = max(worst, error)
            if error > atol:
                key = (node, k)
                bad[key] = max(bad.get(key, 0.), error)
                if len(failures) < FAILURE_LIMIT:
                    failures.append({'time': t, 'node': node, 'expected': want, 'actual': r[node],
                                     'change_time': instants[node][k], 'cause': ch[k][2]})
    summary = [{'node': n, 'change_time': instants[n][k], 'cause': expected[n][k][2], 'expected': expected[n][k][1],
                'max_error': e} for (n, k), e in sorted(bad.items(), key=lambda x: (x[0][0], x[0][1]))[:FAILURE_LIMIT]]
    return failures, checks, worst, summary, len(bad)


def distinct(changes):
    """Keep only entries that change the value: an unchanged output opens no unscored window."""
    out = changes[:1]
    for entry in changes[1:]:
        if entry[1] != out[-1][1]:
            out.append(entry)
    return out


def bits(changes, nodes, hi, lo):
    """Per-bit expected levels of a 4-bit code change list."""
    return {n: distinct([(t, hi if (v >> (3 - j)) & 1 else lo, c) for t, v, c in changes]) for j, n in enumerate(nodes)}


def logic(changes, hi, lo):
    return distinct([(t, hi if v else lo, c) for t, v, c in changes])


def evaluate_top(w, p, case):
    vdd, vss, vref, vth, tr = (p[k] for k in ('vdd', 'vss', 'vref', 'vth', 'tr'))
    span = vref - vss
    if any(not vss - VIN_MARGIN - 1e-9 <= r['vin'] <= vref + VIN_MARGIN + 1e-9 for r in w.rows):
        raise ValueError('vin outside vss - 0.2 V to vref + 0.2 V')
    found = check_logic_inputs(w, ('clk', 'rst', 'start'), vth, clock='clk')
    rises = [t for t, up in found['clk'] if up]
    starts = [t for t, up in found['start'] if up]
    apart([t for t, _ in found['rst']], rises, GUARD, 'rst crossing within 100 ps of a rising clk crossing')
    apart(starts, rises, max(GUARD, 2 * tr), 'start request within max(100 ps, 2*tr) of a rising clk crossing')
    apart([t for t, _ in found['start']], sorted(t for t, _ in found['rst']), GUARD,
          'start crossing within 100 ps of a rst crossing')
    # Reset recovery: the controller pulls sample_en low within tr of a rising rst
    # crossing, so a clock edge that rst lets through comes at least 2*tr after it.
    rst_high = w.rows[0]['rst'] > vth
    for c in rises:
        before = [(t, up) for t, up in found['rst'] if t < c]
        if not (before[-1][1] if before else rst_high) and any(
                up and c - t < 2 * tr * REL for t, up in before):
            raise ValueError('a clock edge with rst low within 2*tr after a rising rst crossing')
    # Reset after a clock edge: a rising rst crossing comes at least tr after the preceding rising
    # clk crossing, so the controller's outputs have reached the levels of that edge before a reset.
    for t, up in found['rst']:
        k = bisect.bisect_left(rises, t)
        if up and k and t - rises[k - 1] < tr * REL:
            raise ValueError('a rising rst crossing within tr after the preceding rising clk crossing')

    def dac(c):
        return vss + span * c / 16

    def sample(t):
        if w.still(t, 'vin') >= VIN_STILL:
            raise ValueError('vin moves by 0.25 mV or more within 100 ps of a sampling edge')
        return w.level(t, 'vin')

    held = {}

    def decide(t, T, b):
        return held['x'] >= dac(T)

    def sample_and_keep(t):
        held['x'] = sample(t)
        return held['x']

    rst0 = w.rows[0]['rst'] > vth
    events = sar_events(rises, found['rst'], starts, rst0)
    changes, conversions, edges = run_sar(events, rst0, decide, sample_and_keep, vss)
    xs = [c['x'] for c in conversions if 'x' in c]
    margin = min((min(abs(x - dac(j)) for j in range(1, 16)) for x in xs), default=None)
    if margin is not None and margin < CODE_MARGIN * REL:
        raise ValueError('a sample within 3 mV of a DAC level')
    expected = bits(changes['R'], ('code_3', 'code_2', 'code_1', 'code_0'), vdd, vss)
    expected['done'] = logic(changes['done'], vdd, vss)
    expected['sample_dbg'] = changes['held']
    expected['dac_dbg'] = [(t, dac(v), c) for t, v, c in changes['T']]
    skips = {n: 1.25 * tr for n in expected}
    skips['dac_dbg'] = 2.5 * tr
    failures, checks, worst, summary, nbad = score(w, expected, skips, float(case.get('atol', .002)))
    done = [c for c in conversions if c['outcome'] == 'done']
    stats = {'clock_edges': edges, 'start_requests': len(conversions), 'completed': len(done),
             'abandoned_by_start': sum(c['outcome'] == 'abandoned by a new start' for c in conversions),
             'abandoned_by_reset': sum(c['outcome'] == 'abandoned by reset' for c in conversions),
             'codes': sorted({c['code'] for c in done}),
             'samples_outside_range': sum(not vss <= c['x'] <= vref for c in conversions if 'x' in c),
             'min_code_margin_mV': None if margin is None else margin * 1e3}
    return failures, checks, worst, summary, nbad, {'top': stats}, skips


def evaluate_modules(w, p, case):
    vdd, vss, vref, vth, tr = (p[k] for k in ('vdd', 'vss', 'vref', 'vth', 'tr'))
    expected, stats = {}, {}
    blocks = case.get('blocks', list(BLOCKS))
    if 'cdac' in blocks:
        names = BLOCKS['cdac'][0]
        found = check_logic_inputs(w, names, vth)
        xs = sorted((t, n, up) for n in names for t, up in found[n])
        # simultaneous: within SAME of one another, with the relative slack REL of the other bounds
        if any(SAME / REL < b[0] - a[0] < MIN_SPACING * REL for a, b in zip(xs, xs[1:])):
            raise ValueError('DAC bit crossings neither simultaneous nor 100 ps apart')
        code = sum(8 >> j for j, n in enumerate(names) if w.rows[0][n] > vth)
        ch = [(0., code, 'initial state')]
        i = 0
        while i < len(xs):
            t = xs[i][0]
            while i < len(xs) and xs[i][0] - t <= SAME / REL:
                _, n, up = xs[i]
                bit = 8 >> names.index(n)
                code = code | bit if up else code & ~bit
                i += 1
            # a chain of crossings, each within SAME of the next, must not span more than SAME
            if i < len(xs) and xs[i][0] - xs[i - 1][0] <= SAME / REL:
                raise ValueError('DAC bit crossings that change together spread over more than 5 ps')
            if code != ch[-1][1]:
                ch.append((t, code, f'bit inputs give code {code}'))
        for out in BLOCKS['cdac'][1]:
            expected[out] = [(t, vss + (vref - vss) * c / 16, cause) for t, c, cause in ch]
        stats['cdac'] = {'codes': sorted({c for _, c, _ in ch}), 'changes': len(ch) - 1}
    if 'comparator' in blocks:
        rows = [dict(time=r['time'], diff=r['cmp_s'] - r['cmp_d']) for r in w.rows]
        if abs(rows[0]['diff']) < DIFF_START * REL:
            raise ValueError('comparator difference starts within 5 mV of 0')
        xs = crossings(rows, 'diff', 0.)
        if any(b - a < DIFF_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError('comparator zero crossings closer than 1 ns')
        high = rows[0]['diff'] >= 0
        ch = [(0., vdd if high else vss, 'initial state')]
        for t, up in xs:
            ch.append((t, vdd if up else vss, 'difference crosses 0 ' + ('upward' if up else 'downward')))
        expected['cmp_o'] = ch
        stats['comparator'] = {'zero_crossings': len(xs)}
    if 'sample_hold' in blocks:
        found = check_logic_inputs(w, ('sh_clk', 'sh_rst', 'sh_en'), vth, clock='sh_clk')
        rises = [t for t, up in found['sh_clk'] if up]
        apart([t for t, _ in found['sh_rst']] + [t for t, _ in found['sh_en']], rises, GUARD,
              'sh_rst or sh_en crossing within 100 ps of a rising sh_clk crossing')
        events = sorted([(t, 'rst_up' if up else 'rst_down') for t, up in found['sh_rst']] + [(t, 'clk') for t in rises])
        rst_high = w.rows[0]['sh_rst'] > vth
        held, ch, samples = vss, [(0., vss, 'initial state')], 0
        for t, kind in events:
            if kind == 'rst_up':
                rst_high, held = True, vss
                cause = 'sh_rst rising crossing'
            elif kind == 'rst_down':
                rst_high = False
                continue
            else:
                if rst_high or w.level(t, 'sh_en') <= vth:
                    continue
                if w.still(t, 'sh_vin') >= VIN_STILL:
                    raise ValueError('sh_vin moves by 0.25 mV or more within 100 ps of a sampling edge')
                held, samples = w.level(t, 'sh_vin'), samples + 1
                cause = 'sampling edge'
            if abs(held - ch[-1][1]) > DELTA:
                ch.append((t, held, cause))
        expected['sh_o'] = ch
        expected['sh_dbg'] = list(ch)
        stats['sample_hold'] = {'samples': samples, 'changes': len(ch) - 1}
    if 'controller' in blocks:
        found = check_logic_inputs(w, ('ct_clk', 'ct_rst', 'ct_start', 'ct_cmp'), vth, clock='ct_clk')
        rises = [t for t, up in found['ct_clk'] if up]
        starts = [t for t, up in found['ct_start'] if up]
        apart([t for t, _ in found['ct_rst']] + [t for t, _ in found['ct_cmp']] + starts, rises, GUARD,
              'ct_rst, ct_cmp or ct_start crossing within 100 ps of a rising ct_clk crossing')
        apart([t for t, _ in found['ct_start']], sorted(t for t, _ in found['ct_rst']), GUARD,
              'ct_start crossing within 100 ps of a ct_rst crossing')
        rst0 = w.rows[0]['ct_rst'] > vth
        changes, conversions, edges = run_sar(sar_events(rises, found['ct_rst'], starts, rst0), rst0,
                                              lambda t, T, b: w.level(t, 'ct_cmp') > vth)
        expected.update(bits(changes['T'], ('ct_t3', 'ct_t2', 'ct_t1', 'ct_t0'), vdd, vss))
        expected.update(bits(changes['R'], ('ct_c3', 'ct_c2', 'ct_c1', 'ct_c0'), vdd, vss))
        expected['ct_en'] = logic(changes['en'], vdd, vss)
        expected['ct_done'] = logic(changes['done'], vdd, vss)
        done = [c for c in conversions if c['outcome'] == 'done']
        stats['controller'] = {'clock_edges': edges, 'start_requests': len(conversions), 'completed': len(done),
                               'abandoned_by_start': sum(c['outcome'] == 'abandoned by a new start' for c in conversions),
                               'abandoned_by_reset': sum(c['outcome'] == 'abandoned by reset' for c in conversions),
                               'codes': sorted({c['code'] for c in done})}
    if not expected:
        raise ValueError('no module block in the case')
    skips = {n: 1.25 * tr for n in expected}
    failures, checks, worst, summary, nbad = score(w, expected, skips, float(case.get('atol', .002)))
    return failures, checks, worst, summary, nbad, stats, skips


def evaluate(rows, case, work):
    p = {k: float(v) for k, v in {**DEFAULTS, **case.get('params', {})}.items()}
    rows = [{k.lower(): v for k, v in r.items()} for r in rows]
    kind = case.get('kind', 'top')
    needed = set(TOP_INPUTS + TOP_OUTPUTS) if kind == 'top' else {
        n for b in case.get('blocks', list(BLOCKS)) for group in BLOCKS[b] for n in group}
    if len(rows) < 2 or any(not {'time', *needed}.issubset(r) for r in rows):
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
    vdd, vss, vref, vth, tr = (p[k] for k in ('vdd', 'vss', 'vref', 'vth', 'tr'))
    if (any(not inside(p[k], lo, hi) for k, (lo, hi) in RANGES.items())
            or not inside(vref - vss, *SPAN_RANGE) or not inside(vdd - vss, *SWING_RANGE)
            or vth < vss + VTH_RAIL_MARGIN * REL or vth > vdd - VTH_RAIL_MARGIN * REL):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    w = Wave(rows)
    if kind == 'top':
        failures, checks, worst, summary, nbad, stats, skips = evaluate_top(w, p, case)
    elif kind == 'modules':
        failures, checks, worst, summary, nbad, stats, skips = evaluate_modules(w, p, case)
    else:
        raise ValueError(f'unknown case kind {kind!r}')
    if checks == 0:
        raise ValueError('no scored observations')
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': nbad, 'max_error': worst, 'atol': float(case.get('atol', .002)),
            'kind': kind, 'stats': stats, 'unscored_after_change_s': skips}


if __name__ == '__main__':
    main(evaluate)

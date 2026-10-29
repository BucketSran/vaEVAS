"""Independent waveform contract for sample_hold_droop; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Clock crossings
through V(vss) + vth are taken from the saved rows, linear between rows; a touch that
returns to the same side is no crossing. A trigger is a rising clk crossing at t_k; its
sample instant is c_k = t_k + taperture. At c_k the held value h (from V(vss)) becomes
V(vin) - V(vss) clamped to [0, V(vdd) - V(vss)] at c_k, coarse becomes high when
h > vth, and valid is high until c_k + valid_width. At each droop update instant
j*dt (j >= 1) from t = 0 at which clk is low, h becomes h*exp(-dt/tau). vout is
V(vss) + h; valid and coarse are V(vdd) when high and V(vss) when low. Points less than
1.25*trf after an instant at which an output's expected value changes by more than DELTA
are not scored for that output; a smaller change opens no unscored window, and every
scored point is compared with the expected value of that time. A record without any
trigger is scored on the initial state. A clk transition, the time during which
clk - vss is more than LEVEL_BAND away from both levels, must not last longer than
200 ps: the rows strictly inside it give a lower bound on its length.
"""
import bisect
import math

from v2_runtime import main

SIGNALS = ('vdd', 'vss', 'clk', 'vin', 'vout', 'valid', 'coarse')
OUTPUTS = ('vout', 'valid', 'coarse')
DEFAULTS = {'vth': .45, 'trf': 40e-12, 'tau': 90e-9, 'dt': .5e-9, 'taperture': 200e-12, 'valid_width': 2e-9}
RANGES = {'vth': (.2, .7), 'trf': (10e-12, 200e-12), 'tau': (10e-9, 1e-6), 'dt': (.2e-9, 5e-9),
          'taperture': (20e-12, 2e-9), 'valid_width': (.5e-9, 10e-9)}
CLK_SWING = .9               # clk switches between V(vss) and V(vss) + 0.9 V
LEVEL_BAND = 1e-3            # clk - vss within 1 mV of 0 V or 0.9 V is at that level
EDGE_MAX = 200e-12           # longest clk transition between the two levels
VSS_RANGE = (-.2, .2)
SPAN_RANGE = (.8, 1.5)       # V(vdd) - V(vss)
START_MARGIN = .05           # clk at t = 0 at least this far from the threshold
MIN_SPACING = 1e-9           # successive clk crossings
TRIGGER_MARGIN = .5e-9       # triggers at least max(taperture, valid_width) + this apart
UPDATE_GUARD = 50e-12        # clk crossings and sample instants to any droop update instant
RAIL_WINDOW = .5e-9          # vdd constant within this of a sample instant
VIN_SPAN = (-.5, 1.8)
STILL_FRACTION = .25         # vin stillness within trf/4 of a sample instant
STILL = .25e-3
DECISION_MARGIN = 5e-3       # every sampled h from vth
DELTA = 1e-4                 # the change threshold of the instruction: outputs computed from saved samples
FAILURE_LIMIT = 20
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

    def span(self, t0, t1, node):
        """Largest movement of node over [t0, t1], from its value at t0."""
        lo, hi = bisect.bisect_left(self.ts, t0), bisect.bisect_right(self.ts, t1)
        ref = self.level(t0, node)
        near = [self.level(t1, node)] + [r[node] for r in self.rows[lo:hi]]
        return max(abs(v - ref) for v in near)


def apart(times, others, gap, message):
    others = sorted(others)
    for t in times:
        k = bisect.bisect_left(others, t)
        for o in others[max(0, k - 1):k + 1]:
            if abs(t - o) < gap * REL:
                raise ValueError(message)


def transitions(ts, values, lo, hi, band):
    """(first, last) row time of each run of rows more than band away from both levels.

    A run is a stretch of the record in which the input is between the levels; the
    true transition contains the run, so last - first is a lower bound on its length
    whatever the row placement. A run that starts at the first row or ends at the last
    one is cut by the record.
    """
    found, start = [], None
    for t, v in zip(ts, values):
        inside = lo + band < v < hi - band
        if inside and start is None:
            start = t
        if inside:
            last = t
        elif start is not None:
            found.append((start, last))
            start = None
    if start is not None:
        found.append((start, last))
    return found


def update_instants(dt, stop):
    found, j = [], 1
    while j * dt <= stop * (1 + 1e-12):
        found.append(j * dt)
        j += 1
    return found


def run_front_end(w, p, vss, rises, updates):
    """The front-end contract on the merged events.

    Returns, per output, the expected value after every event that acts on it,
    [(t, value, cause, opens_window)] starting with the initial state at t = 0, and the
    sample records. An event opens an unscored window for an output when it changes that
    output's expected value by more than DELTA.
    """
    vth, alpha = p['vth'], math.exp(-p['dt'] / p['tau'])
    window = STILL_FRACTION * p['trf']
    events = sorted([(t + p['taperture'], 0, 'sample') for t in rises] + [(t, 1, 'update') for t in updates])
    h = 0.
    changes = {'vout': [(0., vss, 'initial state', False)], 'valid': [(0., vss, 'initial state', False)],
               'coarse': [(0., vss, 'initial state', False)]}
    samples, offs, droops = [], [], 0

    def put(node, t, value, cause):
        changes[node].append((t, value, cause, abs(value - changes[node][-1][1]) > DELTA))

    k = 0
    while k < len(events):
        t, _, kind = events[k]
        k += 1
        # valid falls that are due before this event
        while offs and offs[0][0] <= t:
            tf, n = offs.pop(0)
            put('valid', tf, vss, f'end of valid pulse {n}')
        if kind == 'sample':
            if w.span(t - window, t + window, 'vin') >= STILL:
                raise ValueError('vin moves by 0.25 mV or more within trf/4 of a sample instant')
            if w.span(t - RAIL_WINDOW, t + RAIL_WINDOW, 'vdd') >= STILL:
                raise ValueError('vdd changes within 0.5 ns of a sample instant')
            top = w.level(t, 'vdd') - vss
            x = w.level(t, 'vin') - vss
            h = min(max(x, 0.), top)
            if abs(h - vth) < DECISION_MARGIN * REL:
                raise ValueError('a sampled value within 5 mV of vth')
            n = len(samples)
            high = vss + top
            samples.append({'time': t, 'input': x, 'h': h, 'top': top, 'clamped': abs(x - h) > DELTA,
                            'coarse': h > vth,
                            'clk_low': w.level(t, 'clk') - vss < vth})
            put('vout', t, vss + h, f'sample {n}')
            put('coarse', t, high if h > vth else vss, f'sample {n}')
            put('valid', t, high, f'sample {n}')
            offs.append((t + p['valid_width'], n))
        else:
            if w.level(t, 'clk') - vss < vth:
                droops += abs(h) > DELTA
                h *= alpha
                put('vout', t, vss + h, f'droop update at {t * 1e9:.6g} ns')
    for tf, n in offs:
        if tf <= w.ts[-1]:
            put('valid', tf, vss, f'end of valid pulse {n}')
    return changes, samples, droops


def score(w, expected, skip, atol):
    """expected[node] = [(t, value, cause, opens_window)]; skip = unscored time after a window opens."""
    instants = {n: [c[0] for c in ch] for n, ch in expected.items()}
    windows = {n: [c[0] for c in ch if c[3]] for n, ch in expected.items()}
    failures, checks, worst, bad = [], 0, 0., {}
    for r in w.rows:
        t = r['time']
        for node, ch in expected.items():
            i = bisect.bisect_right(windows[node], t) - 1
            if i >= 0 and t < windows[node][i] + skip:
                continue
            k = bisect.bisect_right(instants[node], t) - 1
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
    # Resolution, rails and the stimulus domain are bench obligations. A candidate
    # cannot repair them, so they are not candidate failures.
    vth, trf, dt = p['vth'], p['trf'], p['dt']
    if any(not inside(p[k], lo, hi) for k, (lo, hi) in RANGES.items()) or trf > dt / 4 * (1 + 1e-6):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', trf / 4), trf / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    vss = rows[0]['vss']
    if any(abs(r['vss'] - vss) > 1e-9 for r in rows) or not inside(vss, *VSS_RANGE):
        raise ValueError('vss is not a constant between -0.2 V and +0.2 V')
    if any(not SPAN_RANGE[0] * REL <= r['vdd'] - vss <= SPAN_RANGE[1] / REL for r in rows):
        raise ValueError('vdd - vss outside 0.8 V to 1.5 V')
    if any(not VIN_SPAN[0] - 1e-9 <= r['vin'] <= VIN_SPAN[1] + 1e-9 for r in rows):
        raise ValueError('vin outside -0.5 V to +1.8 V')
    if any(not -1e-3 <= r['clk'] - vss <= CLK_SWING + 1e-3 for r in rows):
        raise ValueError('clk outside V(vss) to V(vss) + 0.9 V')
    runs = transitions(ts, [r['clk'] - vss for r in rows], 0., CLK_SWING, LEVEL_BAND)
    if any(b - a > EDGE_MAX / REL for a, b in runs):
        raise ValueError('a clk transition lasts longer than 200 ps')
    level = vss + vth
    if abs(rows[0]['clk'] - level) < START_MARGIN * REL:
        raise ValueError('clk starts within 50 mV of the threshold')
    w = Wave(rows)
    xs = crossings(rows, 'clk', level)
    high0 = rows[0]['clk'] > level
    if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
        raise ValueError('clk crossings do not alternate from its initial level')
    if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
        raise ValueError('successive clk crossings closer than 1 ns')
    # A record without a trigger is legal: the outputs keep the initial state.
    rises = [t for t, up in xs if up]
    spacing = max(p['taperture'], p['valid_width']) + TRIGGER_MARGIN
    if any(b - a < spacing * REL for a, b in zip(rises, rises[1:])):
        raise ValueError('successive triggers closer than max(taperture, valid_width) + 0.5 ns')
    updates = update_instants(dt, ts[-1])
    apart([t for t, _ in xs], updates, UPDATE_GUARD, 'clk crossing within 50 ps of a droop update instant')
    apart([t + p['taperture'] for t in rises], updates, UPDATE_GUARD, 'sample instant within 50 ps of a droop update')
    rises = [t for t in rises if t + p['taperture'] <= ts[-1]]
    changes, samples, droops = run_front_end(w, p, vss, rises, updates)
    # vdd may change only while valid and coarse are both low
    for node in ('valid', 'coarse'):
        ch = changes[node]
        for i, (t, value, _, _) in enumerate(ch):
            if value - vss > SPAN_RANGE[0] / 2:
                end = ch[i + 1][0] if i + 1 < len(ch) else ts[-1]
                if w.span(t, end, 'vdd') >= STILL:
                    raise ValueError('vdd changes while valid or coarse is high')
    skip = 1.25 * trf
    atol = float(case.get('atol', .002))
    failures, checks, worst, summary, nbad = score(w, changes, skip, atol)
    if checks == 0:
        raise ValueError('no scored observations')
    stats = {'samples': len(samples), 'clamped_high': sum(s['clamped'] and s['input'] > s['h'] for s in samples),
             'clamped_low': sum(s['clamped'] and s['input'] < s['h'] for s in samples),
             'coarse_high': sum(s['coarse'] for s in samples),
             'samples_with_clk_low': sum(s['clk_low'] for s in samples),
             'droop_updates_applied': droops, 'update_instants': len(updates),
             'min_decision_margin_mV': min(abs(s['h'] - vth) for s in samples) * 1e3 if samples else None,
             'sample_tops': sorted({round(s['top'], 6) for s in samples}),
             'output_changes': {n: sum(c[3] for c in ch) for n, ch in changes.items()}}
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': nbad, 'max_error': worst, 'atol': atol, 'stats': stats,
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

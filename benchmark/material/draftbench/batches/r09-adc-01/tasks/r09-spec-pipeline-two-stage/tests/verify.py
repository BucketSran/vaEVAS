"""Independent waveform contract for pipeline_adc_two_stage; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Crossings of
clk, rst and valid_i through vth and the sampled vin come from the saved rows,
taken as linear between rows; an input that touches vth and returns to the same
side does not cross. A clock edge is a rising clk crossing while rst is
low, and it takes a sample when valid_i is high. A sample x (vin limited to
[vss, vref]) has coarse code k, residue r = (vss + vref)/2 + 4*(x - c_k) about
the bin center c_k, and fine code f of r. Its code 4*k + f is published two clock
edges later with valid_o high; residue_dbg shows the r that stage 1 holds. A
rising rst crossing discards samples in progress and clears the outputs. Points
less than 1.25*tr after a change of the expected outputs are not scored.
"""
import bisect
import math

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
        if value != out:
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
    if any(abs(rows[0][n] - vth) < START_MARGIN * REL for n in CONTROLS):
        raise ValueError('a control input starts within 50 mV of vth')
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

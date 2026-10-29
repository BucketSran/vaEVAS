"""Independent waveform contract for fine_coarse_tdc; reads only saved waveforms.

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
the expected outputs are not scored.
"""
import bisect
import math

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
FAILURE_LIMIT = 20
REL = 1 - 1e-6


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
    if any(abs(rows[0][n] - vth) < START_MARGIN * REL for n in INPUTS):
        raise ValueError('an input starts within 50 mV of vth')
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

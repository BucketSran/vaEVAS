"""Independent waveform contract for dual_track_sample_hold; reads only saved waveforms.

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
rows only refine the inputs.
"""
import bisect
import math

from v2_runtime import main

SIGNALS = ('vdd', 'vss', 'clk', 'vin', 'vout', 'phase')
DEFAULTS = {'vth': 0.45, 'tick': 0.5e-9, 'alpha_in': 0.45, 'alpha_out': 0.55, 'tedge': 50e-12, 'vinit': 0.0}
TICK_GUARD = 50e-12          # every clk crossing to every tick
START_MARGIN = .05           # clk - vss at t = 0 is at least this far from vth
CROSSING_EXCURSION = .05     # clk - vss moves at least this far from vth between successive crossings
SAMPLE_SLACK = 2e-3          # saved clk and vss rows may each lie 1 mV off the source waveform
RAIL_STEP = 1e-3             # vss and the span each change by at most this within any tick-long interval
DELTA = 1e-4                 # the change threshold of the instruction: b computed from saved samples
FAILURE_LIMIT = 20


def crossings(times, values, level):
    """(time, rising) for each pass of values through level, linear between rows.

    Rows are compared with the level exactly; a row on the level is on neither side. A
    crossing is a change of side between successive rows off the level, at the single
    row on the level between them if there is one. A touch, with rows on the same side
    around a row on the level, is no crossing. Two successive rows on the level mean that
    the input rests there, which the bench must not do. A row on the level that ends the
    record after a row off it is a crossing in the direction of arrival; a row on the
    level that begins the record is none.
    """
    found, last = [], None
    for j, v in enumerate(values):
        if v == level:
            if j and values[j - 1] == level:
                raise ValueError('clk rests at the threshold')
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
    if abs(clock[0] - vth) < START_MARGIN * (1 - 1e-6):
        raise ValueError('clk starts within 50 mV of vth')
    edges = crossings(ts, clock, vth)
    edge_times = [t for t, _ in edges]
    if any(y - x < 4 * tedge * (1 - 1e-6) for x, y in zip(edge_times, edge_times[1:])):
        raise ValueError('clk crossings closer than 4*tedge')
    # Between successive crossings the bench moves clk - vss at least 50 mV away from vth, far beyond the
    # cross() expression tolerance. Only saved rows are read: an extremum between two rows is
    # underestimated, so benches put extrema on plateaus or on rows. The error is raised only below
    # 50 mV less SAMPLE_SLACK, so such a bench passes with clk and vss each sampled 1 mV off the source.
    for (t0, _), (t1, _) in zip(edges, edges[1:]):
        inner = clock[bisect.bisect_right(ts, t0):bisect.bisect_left(ts, t1)]
        if max((abs(v - vth) for v in inner), default=0.) < CROSSING_EXCURSION - SAMPLE_SLACK:
            raise ValueError('clk moves less than 50 mV away from vth between successive crossings')
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

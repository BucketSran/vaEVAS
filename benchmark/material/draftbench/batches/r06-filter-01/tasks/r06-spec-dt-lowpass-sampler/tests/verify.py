"""Independent waveform contract for dt_lowpass_sampler; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. The update
instants are t_k = k*tupdate from t = 0. x_k is the recorded vin at t_k, taken as
linear between saved rows, and y_k = 0.25*x_k + 0.75*y_(k-1) with y_(-1) = vin(0).
At each recorded rising clk crossing the expected held value is the y_k of the
latest update instant before the crossing, or 0 V when rst is high; it is 0 V
before the first sample event. Extra simulator rows only refine vin.
"""
import bisect
import math

from v2_runtime import main

B0, A1 = 0.25, 0.75          # H(z) = B0 / (1 - A1 z^-1)
SIGNALS = ('vin', 'clk', 'rst', 'out')
DEFAULTS = {'tupdate': 100e-9, 'vth': 0.45, 'tr': 200e-12}
MIN_RISE_SPACING = 5e-9      # successive rising clk crossings
UPDATE_GUARD = 0.5e-9        # rising clk crossing to any update instant
RESET_GUARD = 1e-9           # rst crossing to any rising clk crossing
START_MARGIN = .05           # clk and rst at t = 0 are at least this far from vth
FAILURE_LIMIT = 20


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


def updates(level, tupdate, stop):
    """(t_k, y_k) for every update instant in [0, stop], equilibrium start."""
    y, found, k = level(0.0, 'vin'), [], 0
    while k * tupdate <= stop * (1 + 1e-12):
        t = k * tupdate
        y = B0 * level(t, 'vin') + A1 * y
        found.append((t, y))
        k += 1
    return found


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    tupdate, vth, tr = float(p['tupdate']), float(p['vth']), float(p['tr'])
    atol = float(case.get('atol', .002))
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
    if max(b - a for a, b in zip(ts, ts[1:])) > case.get('resolution', tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if not (20e-9 <= tupdate <= 1e-6 and 10e-12 <= tr <= 1e-9 and 0 < vth < .9):
        raise ValueError('case parameters outside the public contract')
    if any(abs(r['vin']) > 1 + 1e-9 for r in rows):
        raise ValueError('vin outside the public contract')
    if any(abs(rows[0][n] - vth) < START_MARGIN * (1 - 1e-6) for n in ('clk', 'rst')):
        raise ValueError('clk or rst starts within 50 mV of vth')

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
    if any(abs(t - round(t / tupdate) * tupdate) < UPDATE_GUARD * (1 - 1e-6) for t in rises):
        raise ValueError('rising clk crossing within 0.5 ns of an update instant')
    if any(abs(t - s) < RESET_GUARD * (1 - 1e-6) for t, _ in crossings(rows, 'rst', vth) for s in rises):
        raise ValueError('rst crossing within 1 ns of a sample event')

    filtered = updates(level, tupdate, ts[-1])
    instants = [t for t, _ in filtered]
    events = []
    for t in rises:
        reset = level(t, 'rst') > vth
        latest = bisect.bisect_left(instants, t) - 1   # last update instant strictly before t
        events.append({'time': t, 'reset': reset, 'update': latest,
                       'held': 0. if reset else filtered[latest][1]})

    starts = [e['time'] for e in events]
    skip = 1.25 * tr
    failures, checks, worst, bad_events = [], 0, 0., {}
    for r in rows:
        t = r['time']
        k = bisect.bisect_right(starts, t) - 1
        if k >= 0 and t < starts[k] + skip:
            continue
        expected = events[k]['held'] if k >= 0 else 0.
        error = abs(r['out'] - expected)
        checks += 1
        worst = max(worst, error)
        if error > atol:
            bad_events[k] = max(bad_events.get(k, 0.), error)
            if len(failures) < FAILURE_LIMIT:
                failures.append({'time': t, 'node': 'out', 'expected': expected, 'actual': r['out'],
                                 'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                                 'reset_sample': events[k]['reset'] if k >= 0 else None,
                                 'update_index': events[k]['update'] if k >= 0 else None})
    if checks == 0:
        raise ValueError('no scored hold observations')
    summary = [{'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                'reset_sample': events[k]['reset'] if k >= 0 else None,
                'update_index': events[k]['update'] if k >= 0 else None,
                'expected': events[k]['held'] if k >= 0 else 0., 'max_error': e}
               for k, e in sorted(bad_events.items())[:FAILURE_LIMIT]]
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': len(bad_events), 'max_error': worst, 'atol': atol,
            'sample_events': len(events), 'reset_samples': sum(e['reset'] for e in events),
            'update_instants': len(filtered), 'unscored_after_event_s': skip}


if __name__ == '__main__':
    main(evaluate)

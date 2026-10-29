"""Independent waveform contract for ct_lowpass_sampler.

No candidate source or reference model is read. The expected held value is the
exact response of tau*dy/dt = vin - y, with y(0) = vin(0), to the recorded vin
taken as linear between saved rows. It is evaluated at each recorded rising clk
crossing; a reset sample holds 0 V. Extra simulator rows only refine vin.
"""
import bisect
import math

SIGNALS = ('vin', 'clk', 'rst', 'out')


def advance(y0, a, b, t, tau):
    """Filter value at t in [a, b] for vin linear between rows a and b."""
    h = t - a['time']
    if h <= 0:
        return y0
    slope = (b['vin'] - a['vin']) / (b['time'] - a['time'])
    decay = -math.expm1(-h / tau)
    return y0 + (a['vin'] - y0) * decay + slope * (h - tau * decay)


def crossings(rows, node, level):
    found = []
    for a, b in zip(rows, rows[1:]):
        if a[node] < level <= b[node] or a[node] > level >= b[node]:
            t = a['time'] + (level - a[node]) * (b['time'] - a['time']) / (b[node] - a[node])
            found.append((t, b[node] > a[node]))
    return found


def evaluate(rows, case, work):
    p = case.get('params', {})
    tau, vth, tr = float(p.get('tau', 100e-9)), float(p.get('vth', .45)), float(p.get('tr', 2e-10))
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
    if not (20e-9 <= tau <= 1e-6 and 10e-12 <= tr <= 1e-9 and 0 < vth < .9):
        raise ValueError('case parameters outside the public contract')
    if any(abs(r['vin']) > 1 + 1e-9 for r in rows):
        raise ValueError('vin outside the public contract')

    def level(t, node):
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        a, b = rows[j], rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    clk = crossings(rows, 'clk', vth)
    if not clk or clk[0][1] is not True or rows[0]['clk'] >= vth:
        raise ValueError('clk must start low and produce a sample event')
    rises = [t for t, up in clk if up]
    if any(b - a < 5e-9 * (1 - 1e-6) for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 5 ns')
    if any(abs(t - s) < 1e-9 * (1 - 1e-6) for t, _ in crossings(rows, 'rst', vth) for s in rises):
        raise ValueError('rst crossing within 1 ns of a sample event')

    # Exact filter values at saved rows, then at each sample event.
    y = [rows[0]['vin']]
    for a, b in zip(rows, rows[1:]):
        y.append(advance(y[-1], a, b, b['time'], tau))
    events = []
    for t in rises:
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        reset = level(t, 'rst') > vth
        events.append({'time': t, 'reset': reset,
                       'held': 0. if reset else advance(y[j], rows[j], rows[j + 1], t, tau)})

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
            if len(failures) < 20:
                failures.append({'time': t, 'node': 'out', 'expected': expected, 'actual': r['out'],
                                 'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                                 'reset_sample': events[k]['reset'] if k >= 0 else None})
    if checks == 0:
        raise ValueError('no scored hold observations')
    summary = [{'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                'reset_sample': events[k]['reset'] if k >= 0 else None,
                'expected': events[k]['held'] if k >= 0 else 0., 'max_error': e}
               for k, e in sorted(bad_events.items())[:20]]
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': len(bad_events), 'max_error': worst, 'atol': atol,
            'sample_events': len(events), 'reset_samples': sum(e['reset'] for e in events),
            'unscored_after_event_s': skip}

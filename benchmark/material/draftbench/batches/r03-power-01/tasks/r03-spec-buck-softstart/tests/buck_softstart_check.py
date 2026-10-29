"""Independent per-edge contract for buck_ctrl_top. No candidate source or reference is read.

Expected states come from the recorded inputs at each recorded rising clk crossing:
clear when rst is high or enable is low, otherwise duty_up from vfb against the soft
reference held before the edge, soft-start step toward vref, clamped duty in 0.05
units, modulo-20 carrier and a saturating three-edge power-good count. All four outputs
are scored outside 1.25*tr after each edge. Bench obligations, including the no-tie
margins of the public contract, raise errors instead of producing a candidate verdict.
"""
import bisect
import math

INPUTS = ('vfb', 'vref', 'clk', 'rst', 'enable')
OUTPUTS = ('pwm', 'duty_metric', 'soft_ref', 'pgood')
STEP = 0.05
MODULUS = 20


def crossings(rows, node, level):
    found = []
    for a, b in zip(rows, rows[1:]):
        if a[node] < level <= b[node] or a[node] > level >= b[node]:
            t = a['time'] + (level - a[node]) * (b['time'] - a['time']) / (b[node] - a[node])
            found.append((t, b[node] > a[node]))
    return found


def evaluate(rows, case, work):
    p = case.get('params', {})
    vdd, vss, vth = float(p.get('vdd', .9)), float(p.get('vss', 0.)), float(p.get('vth', .45))
    dmin, dmax = float(p.get('duty_min', .05)), float(p.get('duty_max', .95))
    step, tol, tr = float(p.get('soft_step', .025)), float(p.get('pgood_tol', .025)), float(p.get('tr', 2e-10))
    atol, tie = float(case.get('atol', .002)), float(case.get('tie_margin', .002))
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
    # Resolution, parameter domain and stimulus domain are bench obligations.
    if max(b - a for a, b in zip(ts, ts[1:])) > case.get('resolution', tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    nmin, nmax = round(dmin / STEP), round(dmax / STEP)
    if not (vss < vdd and 0 < vth < .9 and abs(nmin * STEP - dmin) < 1e-9 and abs(nmax * STEP - dmax) < 1e-9
            and 0 <= nmin < nmax <= MODULUS and .005 - 1e-12 <= step <= .1 + 1e-12
            and .005 - 1e-12 <= tol <= .1 + 1e-12 and 10e-12 <= tr <= 1e-9):
        raise ValueError('case parameters outside the public contract')
    if any(not (vss - 1e-9 <= r[n] <= vdd + 1e-9) for r in rows for n in ('vfb', 'vref')):
        raise ValueError('vfb or vref outside the public contract')

    def level(t, node):
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        a, b = rows[j], rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    clk = crossings(rows, 'clk', vth)
    if rows[0]['clk'] >= vth or not clk or not clk[0][1]:
        raise ValueError('clk must start low and produce a sample event')
    rises = [t for t, up in clk if up]
    if any(b - a < 5e-9 * (1 - 1e-6) for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 5 ns')
    for node in ('rst', 'enable'):
        if any(abs(t - s) < 1e-9 * (1 - 1e-6) for t, _ in crossings(rows, node, vth) for s in rises):
            raise ValueError(node + ' crossing within 1 ns of a sample event')
    moving = [(a['time'], b['time']) for a, b in zip(rows, rows[1:])
              if abs(a['vfb'] - b['vfb']) > 1e-9 or abs(a['vref'] - b['vref']) > 1e-9]
    guard = 1e-9 * (1 - 1e-6)
    if any(ta < s + guard and tb > s - guard for ta, tb in moving for s in rises):
        raise ValueError('vfb or vref changes within 1 ns of a sample event')

    soft, n, carrier, count, pwm, pgood = vss, 0, 0, 0, vss, vss
    events = []
    for k, t in enumerate(rises):
        fb, ref = level(t, 'vfb'), level(t, 'vref')
        clear = level(t, 'rst') > vth or level(t, 'enable') <= vth
        if clear:
            soft, n, carrier, count, pwm, pgood = vss, 0, 0, 0, vss, vss
        else:
            if abs(fb - soft) < tie or abs(abs(fb - ref) - tol) < tie:
                raise ValueError(f'comparison within the {tie * 1e3:g} mV no-tie margin at sample event {k}')
            up = fb < soft
            soft = ref if abs(ref - soft) <= step else soft + (step if ref > soft else -step)
            n = min(nmax, max(nmin, n + (1 if up else -1)))
            carrier = (carrier + 1) % MODULUS
            pwm = vdd if carrier < n else vss
            count = min(3, count + 1) if abs(fb - ref) <= tol else 0
            pgood = vdd if count >= 3 else vss
        events.append({'time': t, 'clear': clear, 'carrier': carrier, 'duty': n * STEP,
                       'expected': {'pwm': pwm, 'duty_metric': n * STEP, 'soft_ref': soft, 'pgood': pgood}})
    initial = {'pwm': vss, 'duty_metric': 0., 'soft_ref': vss, 'pgood': vss}

    starts = [e['time'] for e in events]
    skip = 1.25 * tr
    failures, checks, worst, bad = [], 0, {o: 0. for o in OUTPUTS}, {}
    for r in rows:
        t = r['time']
        k = bisect.bisect_right(starts, t) - 1
        if k >= 0 and t < starts[k] + skip:
            continue
        expected = events[k]['expected'] if k >= 0 else initial
        for node in OUTPUTS:
            error = abs(r[node] - expected[node])
            checks += 1
            worst[node] = max(worst[node], error)
            if error > atol:
                bad.setdefault(node, set()).add(k)
                if len(failures) < 20:
                    failures.append({'time': t, 'node': node, 'expected': expected[node], 'actual': r[node],
                                     'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                                     'event_kind': ('clear' if events[k]['clear'] else 'update') if k >= 0 else 'initial'})
    if checks == 0:
        raise ValueError('no scored hold observations')
    first_bad = {node: [{'sample_event': k, 'event_time': starts[k] if k >= 0 else None,
                         'event_kind': ('clear' if events[k]['clear'] else 'update') if k >= 0 else 'initial',
                         'expected': (events[k]['expected'] if k >= 0 else initial)[node]}
                        for k in sorted(ks)[:5]] for node, ks in bad.items()}
    return {'passed': not failures, 'checks': checks, 'failures': failures,
            'failed_events_by_output': {node: len(ks) for node, ks in bad.items()}, 'first_failed_events': first_bad,
            'max_error': worst, 'atol': atol, 'sample_events': len(events),
            'clear_events': sum(e['clear'] for e in events),
            'pgood_assert_events': sum(1 for a, b in zip([initial] + [e['expected'] for e in events], events)
                                       if a['pgood'] != b['expected']['pgood'] == vdd),
            'unscored_after_event_s': skip}

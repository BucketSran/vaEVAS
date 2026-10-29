"""Independent waveform contract for debounce_latch; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Crossings of
sig and rst_n through vth come from the saved rows, taken as linear between rows;
an input that touches vth and returns to the same side does not cross. A rising
sig crossing while rst_n is high starts a qualification that completes
stable later unless a falling crossing of sig or rst_n comes first. Completion
sets the ideal level to vdd; such a falling crossing sets it to 0 V and cancels
the qualification for good. The ideal level is 0 V at t = 0, and sig high at
t = 0 or at reset release starts nothing. Points less than 1.25*tr after a change
of the ideal level are not scored. Extra simulator rows only refine the inputs.
"""
import bisect
import math

from v2_runtime import main

SIGNALS = ('sig', 'rst_n', 'out')
DEFAULTS = {'vth': .45, 'vdd': .9, 'stable': 12e-9, 'tr': 500e-12}
RANGES = {'vth': (.2, .7), 'vdd': (.5, 1.5), 'stable': (2e-9, 1e-6), 'tr': (10e-12, 1e-9)}
INPUT_LOW, INPUT_HIGH = 0., .9
START_MARGIN = .05           # each input at t = 0 is at least this far from vth
MIN_SPACING = .5e-9          # successive crossings of one input
RISE_RESET_GUARD = .5e-9     # rising sig crossing to any rst_n crossing
END_GUARD = .3e-9            # falling sig or rst_n crossing to any t_r + stable
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


def ideal_changes(sig, rst, rst_high, stable, stop):
    """Changes of the ideal level as (time, high, cause), and every qualification."""
    events = sorted([(t, 'sig', up) for t, up in sig] + [(t, 'rst_n', up) for t, up in rst])
    changes, quals, ignored, running, high = [(0., False, 'initial state')], [], [], None, False
    for t, node, up in events + [(math.inf, None, None)]:
        if running is not None and running['end'] <= min(t, stop):
            high = True
            changes.append((running['end'], True, f"completion of the qualification started at {running['start']:.6g} s"))
            running['outcome'] = 'completed'
            running = None
        if node is None:
            break
        if node == 'sig' and up:
            if rst_high:
                running = {'start': t, 'end': t + stable, 'outcome': 'running at stop'}
                quals.append(running)
            else:
                ignored.append(t)
        elif up:
            rst_high = True
        else:
            if running is not None:
                running['outcome'] = 'cancelled'
                running['cancelled_at'] = t
                running['cancelled_by'] = node
                running = None
            if high:
                high = False
                changes.append((t, False, f'{node} falling crossing'))
            if node == 'rst_n':
                rst_high = False
    return changes, quals, ignored


def evaluate(rows, case, work):
    p = {**DEFAULTS, **case.get('params', {})}
    vth, vdd, stable, tr = (float(p[k]) for k in ('vth', 'vdd', 'stable', 'tr'))
    atol = float(case.get('atol', .01))
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
    if any(not lo * REL <= float(p[k]) <= hi / REL for k, (lo, hi) in RANGES.items()):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(not INPUT_LOW - 1e-3 <= r[n] <= INPUT_HIGH + 1e-3 for r in rows for n in ('sig', 'rst_n')):
        raise ValueError('sig or rst_n outside 0 V to 0.9 V')
    if any(abs(rows[0][n] - vth) < START_MARGIN * REL for n in ('sig', 'rst_n')):
        raise ValueError('an input starts within 50 mV of vth')

    sig, rst = crossings(rows, 'sig', vth), crossings(rows, 'rst_n', vth)
    for name, found, start_high in (('sig', sig, rows[0]['sig'] > vth), ('rst_n', rst, rows[0]['rst_n'] > vth)):
        if any(up != (k % 2 == (1 if start_high else 0)) for k, (_, up) in enumerate(found)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(found, found[1:])):
            raise ValueError(f'successive {name} crossings closer than 0.5 ns')
    rises = [t for t, up in sig if up]
    falls = [t for t, up in sig + rst if not up]
    if any(abs(t - r) < RISE_RESET_GUARD * REL for t in rises for r, _ in rst):
        raise ValueError('rising sig crossing within 0.5 ns of a rst_n crossing')
    if any(abs(f - (t + stable)) < END_GUARD * REL for t in rises for f in falls):
        raise ValueError('falling crossing within 0.3 ns of a qualification end instant')

    def level(t, node):
        j = max(0, min(len(rows) - 2, bisect.bisect_right(ts, t) - 1))
        a, b = rows[j], rows[j + 1]
        return a[node] + (b[node] - a[node]) * (t - a['time']) / (b['time'] - a['time'])

    changes, quals, ignored = ideal_changes(sig, rst, rows[0]['rst_n'] > vth, stable, ts[-1])
    starts = [c[0] for c in changes]
    skip = 1.25 * tr
    failures, checks, worst, bad = [], 0, 0., {}
    for r in rows:
        t = r['time']
        k = bisect.bisect_right(starts, t) - 1
        if k > 0 and t < starts[k] + skip:
            continue
        expected = vdd if changes[k][1] else 0.
        error = abs(r['out'] - expected)
        checks += 1
        worst = max(worst, error)
        if error > atol:
            bad[k] = max(bad.get(k, 0.), error)
            if len(failures) < FAILURE_LIMIT:
                failures.append({'time': t, 'node': 'out', 'expected': expected, 'actual': r['out'],
                                 'level_change': k, 'change_time': starts[k], 'cause': changes[k][2]})
    if checks == 0:
        raise ValueError('no scored observations')
    summary = [{'level_change': k, 'change_time': starts[k], 'cause': changes[k][2],
                'expected': vdd if changes[k][1] else 0., 'max_error': e}
               for k, e in sorted(bad.items())[:FAILURE_LIMIT]]
    # A cancelled qualification whose end instant finds both inputs high again shows a
    # stale completion; the stimulus counts these chances.
    stale = sum(1 for q in quals if q['outcome'] == 'cancelled' and q['end'] <= ts[-1]
                and level(q['end'], 'sig') > vth and level(q['end'], 'rst_n') > vth)
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': len(bad), 'max_error': worst, 'atol': atol,
            'level_changes': len(changes) - 1,
            'qualifications': {'started': len(quals),
                               'completed': sum(q['outcome'] == 'completed' for q in quals),
                               'cancelled': sum(q['outcome'] == 'cancelled' for q in quals),
                               'cancelled_with_both_inputs_high_at_end': stale},
            'rises_while_reset': len(ignored), 'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

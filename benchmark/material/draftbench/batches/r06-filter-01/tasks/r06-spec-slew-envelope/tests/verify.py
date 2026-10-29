"""Independent waveform contract for slew_envelope_tracker; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. The envelope is
rebuilt from the recorded rst and clk crossings and the recorded vin and mode at each
crossing. Each output's trajectory starts at 0 V and moves toward its target (env for
out, env/0.8 for metric) with slope +rise_rate or -fall_rate, stopping on it. Every
event may take effect up to EVENT_TOL before or after its crossing. The dynamics are
order preserving, so the allowed values at time t lie between the responses to the
lowest and the highest target that the shifted events allow; a saved point passes
when it is within atol of that range.
"""
import bisect
import math

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
    if any(abs(rows[0][n] - vth) < START_MARGIN * (1 - 1e-6) for n in ('clk', 'mode', 'rst')):
        raise ValueError('a control starts within 50 mV of vth')

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

"""Independent waveform contract for leaky_hold; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Crossings
through vth are taken from the saved rows, linear between rows; a touch that
returns to the same side is no crossing. The held value h starts at 0 V. The
leak update instants are k*leak_period (k >= 1) from t = 0, independent of the
inputs; at each one h becomes decay*h. A capture is a rising sample crossing
with rst low and sets h to V(vin) at the crossing. A rising rst crossing sets h
to 0 V at once; while rst is high nothing is captured, and its falling crossing
changes nothing. Points less than 1.25*tr after an instant at which the expected h
changes by more than DELTA are not scored; a smaller change opens no unscored window,
and every scored point is compared with the expected h of that time. A control
transition, the time during which it is more than LEVEL_BAND away from both logic
levels, must not last longer than 200 ps: the rows strictly inside it give a lower
bound on its length.
"""
import bisect
import math

from v2_runtime import main

SIGNALS = ('sample', 'rst', 'vin', 'vout')
CONTROLS = ('sample', 'rst')
DEFAULTS = {'vth': .45, 'decay': .985, 'leak_period': 1e-9, 'tr': 500e-12}
RANGES = {'vth': (.1, .8), 'decay': (.5, 1.), 'leak_period': (.5e-9, 10e-9), 'tr': (10e-12, 1e-9)}
LOGIC_HIGH = .9              # controls switch between 0 V and 0.9 V
LEVEL_BAND = 1e-3            # a control within 1 mV of 0 V or 0.9 V is at that level
EDGE_MAX = 200e-12           # longest transition between the two levels
START_MARGIN = .05           # controls at t = 0 at least this far from vth
LEVEL_MARGIN = .1            # rst at a rising sample crossing, from vth
MIN_SPACING = .5e-9          # successive crossings of one control
LEAK_GUARD = 50e-12          # rising sample crossing to any leak update instant
RESET_GUARD = .5e-9          # rst crossing to any rising sample crossing
VIN_SPAN = 1.                # |vin| at most 1 V
VIN_WINDOW = 100e-12         # vin stillness around a rising sample crossing
VIN_STILL = .25e-3
DELTA = 1e-4                 # the change threshold of the instruction: h is computed from saved vin
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

    def still(self, t, node, window):
        """Largest movement of node within window of t."""
        lo, hi = bisect.bisect_left(self.ts, t - window), bisect.bisect_right(self.ts, t + window)
        ref = self.level(t, node)
        near = [self.level(t - window, node), self.level(t + window, node)] + [r[node] for r in self.rows[lo:hi]]
        return max(abs(v - ref) for v in near)


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


def control_crossings(w, vth):
    """Bench obligations of the logic inputs; returns their crossings."""
    found = {}
    for name in CONTROLS:
        if any(not -1e-3 <= r[name] <= LOGIC_HIGH + 1e-3 for r in w.rows):
            raise ValueError(f'{name} outside 0 V to 0.9 V')
        runs = transitions(w.ts, [r[name] for r in w.rows], 0., LOGIC_HIGH, LEVEL_BAND)
        if any(b - a > EDGE_MAX / REL for a, b in runs):
            raise ValueError(f'a {name} transition lasts longer than 200 ps')
        if abs(w.rows[0][name] - vth) < START_MARGIN * REL:
            raise ValueError(f'{name} starts within 50 mV of vth')
        xs = crossings(w.rows, name, vth)
        high0 = w.rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 0.5 ns')
        found[name] = xs
    return found


def apart(times, others, gap, message):
    others = sorted(others)
    for t in times:
        k = bisect.bisect_left(others, t)
        for o in others[max(0, k - 1):k + 1]:
            if abs(t - o) < gap * REL:
                raise ValueError(message)


def leak_instants(period, stop):
    found, k = [], 1
    while k * period <= stop * (1 + 1e-12):
        found.append(k * period)
        k += 1
    return found


def run_hold(w, p, events, rst_high):
    """The hold contract on the merged events.

    Returns the expected h after every event, [(t, h, cause, opens_window)], starting with the
    initial state at t = 0, and event records. An event opens an unscored window when it
    changes h by more than DELTA.
    """
    decay = p['decay']
    h = 0.
    changes = [(0., 0., 'initial state', False)]
    record = {'captures': [], 'blocked': 0, 'resets': 0, 'resets_clearing': 0, 'leaks_changing': 0}

    def put(t, value, cause):
        changes.append((t, value, cause, abs(value - changes[-1][1]) > DELTA))

    for t, _, kind in events:
        if kind == 'rst_up':
            rst_high = True
            record['resets'] += 1
            record['resets_clearing'] += abs(h) > DELTA
            h = 0.
            put(t, h, 'rst rising crossing')
        elif kind == 'rst_down':
            rst_high = False
        elif kind == 'sample':
            if rst_high:
                record['blocked'] += 1
                continue
            if w.still(t, 'vin', VIN_WINDOW) >= VIN_STILL:
                raise ValueError('vin moves by 0.25 mV or more within 100 ps of a rising sample crossing')
            h = w.level(t, 'vin')
            n = len(record['captures'])
            record['captures'].append({'time': t, 'value': h})
            put(t, h, f'capture {n}')
        else:
            old, h = h, h * decay
            record['leaks_changing'] += abs(h - old) > DELTA
            put(t, h, f'leak update at {t * 1e9:.6g} ns')
    return changes, record


def score(w, changes, skip, atol):
    instants = [c[0] for c in changes]
    windows = [c[0] for c in changes if c[3]]
    failures, checks, worst, bad = [], 0, 0., {}
    for r in w.rows:
        t = r['time']
        i = bisect.bisect_right(windows, t) - 1
        if i >= 0 and t < windows[i] + skip:
            continue
        k = bisect.bisect_right(instants, t) - 1
        want = changes[k][1]
        checks += 1
        error = abs(r['vout'] - want)
        worst = max(worst, error)
        if error > atol:
            bad[k] = max(bad.get(k, 0.), error)
            if len(failures) < FAILURE_LIMIT:
                failures.append({'time': t, 'node': 'vout', 'expected': want, 'actual': r['vout'],
                                 'change_time': instants[k], 'cause': changes[k][2]})
    summary = [{'change_time': instants[k], 'cause': changes[k][2], 'expected': changes[k][1], 'max_error': e}
               for k, e in sorted(bad.items())[:FAILURE_LIMIT]]
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
    # Resolution and the stimulus domain are bench obligations. A candidate
    # cannot repair them, so they are not candidate failures.
    vth, period, tr = p['vth'], p['leak_period'], p['tr']
    if any(not inside(p[k], lo, hi) for k, (lo, hi) in RANGES.items()) or tr > period / 2 * (1 + 1e-6):
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(abs(r['vin']) > VIN_SPAN + 1e-9 for r in rows):
        raise ValueError('vin outside -1 V to +1 V')
    w = Wave(rows)
    found = control_crossings(w, vth)
    rises = [t for t, up in found['sample'] if up]
    leaks = leak_instants(period, ts[-1])
    apart(rises, leaks, LEAK_GUARD, 'rising sample crossing within 50 ps of a leak update instant')
    apart([t for t, _ in found['rst']], rises, RESET_GUARD, 'rst crossing within 0.5 ns of a rising sample crossing')
    for t in rises:
        if abs(w.level(t, 'rst') - vth) < LEVEL_MARGIN * REL:
            raise ValueError('rst is in transition at a rising sample crossing')
    events = sorted([(t, 0, 'rst_up' if up else 'rst_down') for t, up in found['rst']]
                    + [(t, 1, 'leak') for t in leaks] + [(t, 2, 'sample') for t in rises])
    changes, record = run_hold(w, p, events, w.rows[0]['rst'] > vth)
    skip = 1.25 * tr
    atol = float(case.get('atol', .002))
    failures, checks, worst, summary, nbad = score(w, changes, skip, atol)
    if checks == 0:
        raise ValueError('no scored observations')
    phases = [(c['time'] / period) % 1. for c in record['captures']]
    stats = {'captures': len(record['captures']), 'sample_rises_in_reset': record['blocked'],
             'rst_rising_crossings': record['resets'], 'resets_clearing_a_nonzero_value': record['resets_clearing'],
             'leak_updates': len(leaks), 'leak_updates_changing_h': record['leaks_changing'],
             'negative_captures': sum(c['value'] < 0 for c in record['captures']),
             'capture_phases_in_leak_period': [round(x, 4) for x in phases],
             'output_changes': sum(c[3] for c in changes),
             'events_without_window': sum(1 for c in changes[1:] if not c[3])}
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': nbad, 'max_error': worst, 'atol': atol, 'stats': stats,
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

"""Independent waveform contract for the two-tap DFE receiver; reads only saved waveforms.

No candidate source, reference model or reference waveform is read. Crossings
through vth are taken from the saved rows, linear between rows; a touch that
returns to the same side is no crossing. A decision event is a rising clk
crossing with rst low. It reads the tap codes k1, k2 and V(vin) at the crossing,
takes fb = tap_lsb*(k1*h1 + k2*h2) from the two history slots (+1 high, -1 low,
0 empty), decides high when V(vin) - fb >= vcm, reports fb and V(vin) - fb, and
only then shifts the decision into the history. A rising rst crossing, and t = 0,
empty both slots and set decision to vss and both metrics to 0 V. Points less
than 1.25*tr after an event that changes an output's expected value by more
than DELTA are not scored for that output. A change of DELTA or less is no
change, and the expected value keeps its previous value. decision and fb_metric
come from the history and the tap codes and are compared exactly; slicer_in_dbg,
computed from the sampled vin, with DELTA.
"""
import bisect
import math

from v2_runtime import main

SIGNALS = ('vin', 'clk', 'rst', 'tap1_1', 'tap1_0', 'tap2_1', 'tap2_0', 'decision', 'fb_metric', 'slicer_in_dbg')
CONTROLS = ('clk', 'rst', 'tap1_1', 'tap1_0', 'tap2_1', 'tap2_0')
TAPS = ('tap1_1', 'tap1_0', 'tap2_1', 'tap2_0')
DEFAULTS = {'vdd': .9, 'vss': 0., 'vcm': .45, 'vth': .45, 'tap_lsb': 20e-3, 'tr': 200e-12}
RANGES = {'vdd': (.5, 1.5), 'vss': (-.5, .5), 'vcm': (.2, .7), 'vth': (.2, .7),
          'tap_lsb': (5e-3, 50e-3), 'tr': (10e-12, 1e-9)}
SWING_MIN = .4               # vdd - vss
LOGIC_HIGH = .9              # controls switch between 0 V and 0.9 V
START_MARGIN = .05           # controls at t = 0 at least this far from vth
LEVEL_MARGIN = .1            # rst and tap inputs at a rising clk crossing, from vth
MIN_SPACING = .5e-9          # successive crossings of one control
MIN_EDGE_SPACING = 2e-9      # successive rising clk crossings
GUARD = .5e-9                # rst and tap crossings to rising clk crossings
VIN_SPAN = .4                # vin within vcm +- 0.4 V
VIN_WINDOW = 100e-12         # vin stillness around a rising clk crossing
VIN_STILL = .25e-3
SLICER_MARGIN = 5e-3         # every expected slicer input from vcm
DELTA = 1e-4                 # change threshold of the instruction: slicer_in_dbg
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


def control_crossings(w, vth):
    """Bench obligations of the logic inputs; returns their crossings."""
    found = {}
    for name in CONTROLS:
        if any(not -1e-3 <= r[name] <= LOGIC_HIGH + 1e-3 for r in w.rows):
            raise ValueError(f'{name} outside 0 V to 0.9 V')
        if abs(w.rows[0][name] - vth) < START_MARGIN * REL:
            raise ValueError(f'{name} starts within 50 mV of vth')
        xs = crossings(w.rows, name, vth)
        high0 = w.rows[0][name] > vth
        if any(up != (k % 2 == (1 if high0 else 0)) for k, (_, up) in enumerate(xs)):
            raise ValueError(f'{name} crossings do not alternate from its initial level')
        if any(b - a < MIN_SPACING * REL for (a, _), (b, _) in zip(xs, xs[1:])):
            raise ValueError(f'successive {name} crossings closer than 0.5 ns')
        found[name] = xs
    if w.rows[0]['clk'] > vth:
        raise ValueError('clk must start low')
    rises = [t for t, up in found['clk'] if up]
    if any(b - a < MIN_EDGE_SPACING * REL for a, b in zip(rises, rises[1:])):
        raise ValueError('rising clk crossings closer than 2 ns')
    return found


def apart(times, others, gap, message):
    for t in times:
        k = bisect.bisect_left(others, t)
        for o in others[max(0, k - 1):k + 1]:
            if abs(t - o) < gap * REL:
                raise ValueError(message)


def run_dfe(w, p, events, rst_high):
    """The receiver contract on the merged events. Returns output change lists and decisions."""
    vdd, vss, vcm, vth, lsb = (p[k] for k in ('vdd', 'vss', 'vcm', 'vth', 'tap_lsb'))
    h1 = h2 = 0
    since_reset = 0
    changes = {'decision': [(0., vss, 'initial state')], 'fb_metric': [(0., 0., 'initial state')],
               'slicer_in_dbg': [(0., 0., 'initial state')]}
    decisions, resets, edges_in_reset = [], 0, 0

    def put(t, cause, **values):
        for node, v in values.items():
            changes[node].append((t, v, cause))

    for t, kind in events:
        if kind == 'rst_up':
            rst_high = True
            resets += 1
            h1 = h2 = 0
            since_reset = 0
            put(t, 'rst rising crossing', decision=vss, fb_metric=0., slicer_in_dbg=0.)
            continue
        if kind == 'rst_down':
            rst_high = False
            continue
        if rst_high:
            edges_in_reset += 1
            continue
        k1 = 2 * (w.level(t, 'tap1_1') > vth) + (w.level(t, 'tap1_0') > vth)
        k2 = 2 * (w.level(t, 'tap2_1') > vth) + (w.level(t, 'tap2_0') > vth)
        if w.still(t, 'vin', VIN_WINDOW) >= VIN_STILL:
            raise ValueError('vin moves by 0.25 mV or more within 100 ps of a rising clk crossing')
        x = w.level(t, 'vin')
        fb = lsb * (k1 * h1 + k2 * h2)
        s = x - fb
        d = 1 if s >= vcm else -1
        since_reset += 1
        n = len(decisions)
        decisions.append({'time': t, 'vin': x, 'k1': k1, 'k2': k2, 'h1': h1, 'h2': h2, 'fb': fb, 's': s, 'd': d,
                          'after_reset': since_reset})
        put(t, f'decision {n} (h1={h1:+d}, h2={h2:+d}, k1={k1}, k2={k2})',
            decision=vdd if d > 0 else vss, fb_metric=fb, slicer_in_dbg=s)
        h2, h1 = h1, d
    return changes, decisions, resets, edges_in_reset


def distinct(changes, delta=None):
    """Keep only entries that change the value: an unchanged output opens no unscored window.

    With delta (a value computed from the sampled vin), a change of delta or less is no change."""
    out = changes[:1]
    for entry in changes[1:]:
        if (entry[1] != out[-1][1]) if delta is None else (abs(entry[1] - out[-1][1]) > delta):
            out.append(entry)
    return out


def score(w, expected, skip, atol):
    """expected[node] = [(t, value, cause)]; skip = unscored time after a change of that node."""
    instants = {n: [c[0] for c in ch] for n, ch in expected.items()}
    failures, checks, worst, bad = [], 0, 0., {}
    for r in w.rows:
        t = r['time']
        for node, ch in expected.items():
            k = bisect.bisect_right(instants[node], t) - 1
            if k > 0 and t < instants[node][k] + skip:
                continue
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


def coverage(decisions, vcm):
    """Counts that show what a case exercises; they are not scored."""
    pairs = 0
    for i, a in enumerate(decisions):
        for b in decisions[i + 1:]:
            if (abs(a['vin'] - b['vin']) < 1e-3 and (a['k1'], a['k2']) == (b['k1'], b['k2'])
                    and (a['h1'], a['h2']) != (b['h1'], b['h2']) and a['d'] != b['d']):
                pairs += 1
    changed = sum(1 for a, b in zip(decisions, decisions[1:])
                  if (a['k1'], a['k2']) != (b['k1'], b['k2']) and b['after_reset'] > 1)
    return {'decisions': len(decisions),
            'first_after_reset': sum(d['after_reset'] == 1 for d in decisions),
            'second_after_reset': sum(d['after_reset'] == 2 for d in decisions),
            'decided_against_raw_input': sum(d['d'] != (1 if d['vin'] >= vcm else -1) for d in decisions),
            'same_input_different_history_pairs': pairs,
            'first_decision_after_tap_change': changed,
            'tap_codes': sorted({(d['k1'], d['k2']) for d in decisions}),
            'histories': sorted({(d['h1'], d['h2']) for d in decisions}),
            'min_slicer_margin_mV': min(abs(d['s'] - vcm) for d in decisions) * 1e3}


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
    vdd, vss, vcm, vth, tr = (p[k] for k in ('vdd', 'vss', 'vcm', 'vth', 'tr'))
    if any(not inside(p[k], lo, hi) for k, (lo, hi) in RANGES.items()) or vdd - vss < SWING_MIN * REL:
        raise ValueError('case parameters outside the public contract')
    if max(b - a for a, b in zip(ts, ts[1:])) > min(case.get('resolution', tr / 4), tr / 4) * 1.05:
        raise ValueError('insufficient waveform resolution')
    if any(abs(r['vin'] - vcm) > VIN_SPAN + 1e-9 for r in rows):
        raise ValueError('vin outside vcm +- 0.4 V')
    w = Wave(rows)
    found = control_crossings(w, vth)
    rises = [t for t, up in found['clk'] if up]
    if not rises:
        raise ValueError('no rising clk crossing')
    apart([t for t, _ in found['rst']], rises, GUARD, 'rst crossing within 0.5 ns of a rising clk crossing')
    apart([t for n in TAPS for t, _ in found[n]], rises, GUARD, 'tap crossing within 0.5 ns of a rising clk crossing')
    for t in rises:
        if any(abs(w.level(t, n) - vth) < LEVEL_MARGIN * REL for n in ('rst',) + TAPS):
            raise ValueError('rst or a tap input is in transition at a rising clk crossing')
    events = sorted([(t, 'rst_up' if up else 'rst_down') for t, up in found['rst']] + [(t, 'clk') for t in rises])
    changes, decisions, resets, edges_in_reset = run_dfe(w, p, events, w.rows[0]['rst'] > vth)
    if not decisions:
        raise ValueError('no decision event')
    margin = min(abs(d['s'] - vcm) for d in decisions)
    if margin < SLICER_MARGIN * REL:
        raise ValueError('a slicer input within 5 mV of vcm')
    expected = {n: distinct(ch, DELTA if n == 'slicer_in_dbg' else None) for n, ch in changes.items()}
    skip = 1.25 * tr
    atol = float(case.get('atol', .002))
    failures, checks, worst, summary, nbad = score(w, expected, skip, atol)
    if checks == 0:
        raise ValueError('no scored observations')
    stats = dict(coverage(decisions, vcm), resets=resets, clk_edges_in_reset=edges_in_reset,
                 output_changes={n: len(ch) - 1 for n, ch in expected.items()})
    return {'passed': not failures, 'checks': checks, 'failures': failures, 'failed_intervals': summary,
            'failed_interval_count': nbad, 'max_error': worst, 'atol': atol, 'stats': stats,
            'unscored_after_change_s': skip}


if __name__ == '__main__':
    main(evaluate)

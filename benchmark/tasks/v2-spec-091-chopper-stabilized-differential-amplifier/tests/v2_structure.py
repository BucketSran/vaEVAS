"""Fixed public helper replacement contracts, checked from actual waveforms.

No candidate parser, source similarity, or private instance name is used.
Component harnesses and replacements are fixed task assets, not reference oracles.
"""
import bisect
from v2_spec import evaluate as external

IDENTIFIERS = {
    '091': {'voutp': .22, 'voutn': .67, 'settled': .9, 'offset_residual': .14},
    '307': {'vout': .63, 'phase_metric': .22, 'valid': 0.},
    '308': {'vout': .61, 'offset_dbg': .23, 'valid': .9},
}


def evaluate(rows, case, work):
    sid = case['source_id']
    mode = case.get('structure_probe')
    if mode == 'consumer':
        # Run the ordinary evidence validation before checking the replacement.
        # Its circuit verdict is irrelevant here: these are published sentinel
        # outputs, deliberately different from ordinary circuit behavior.
        external(rows, case, work)
        failures = []
        checks = 0
        for row in rows:
            for node, expected in IDENTIFIERS[sid].items():
                checks += 1
                if abs(row[node] - expected) > .002:
                    if len(failures) < 20:
                        failures.append(dict(time=row['time'], node=node,
                                             expected=expected, actual=row[node]))
        return dict(passed=not failures, checks=checks, failures=failures,
                    source_id=sid, structure_probe=mode)
    if mode == 'producer':
        # A producer replacement supplies the published constant sample while
        # retaining normal control/reset/strobe semantics. The original
        # consumer must use this sample, rather than reconstructing vin.
        converted = [dict(row) for row in rows]
        adapted = {**case, 'params': dict(case.get('params', {}))}
        if sid == '091':
            adapted['params']['vos_amp'] = 0.
            for row in converted:
                row['vinp'] = .45 + .16 / adapted['params'].get('gain', 3.)
                row['vinn'] = .45
        elif sid == '307':
            for row in converted:
                row['vin'] = .62
        elif sid == '308':
            for row in converted:
                if row['sample_reset'] > .45:
                    row['vin'] = .31
        else:
            raise ValueError('unknown replacement source')
        verdict = external(converted, adapted, work)
    else:
        verdict = external(rows, case, work)
    if sid == '091' and mode == 'component-producer':
        stage = check_chopper_boundary(rows, case)
        verdict['passed'] = verdict['passed'] and stage['passed']
        verdict['checks'] += stage['checks']
        verdict['failures'] = (verdict['failures'] + stage['failures'])[:20]
        verdict['core_boundary'] = stage
    if mode:
        verdict['structure_probe'] = mode
    return verdict


def check_chopper_boundary(rows, case):
    """Check the fixed component harness's core ports, including notification.

    These names belong to the checker-owned component harness. The candidate
    top and its private net/instance names are never inspected.
    """
    p = case.get('params', {})
    tr, th = p.get('tr', 1e-10), p.get('vth', .45)
    gain, offset = p.get('gain', 3.), p.get('vos_amp', .02)
    keys = {'sample': 'IDUT.demod_sample_i', 'ref': 'IDUT.baseband_ref_i',
            'strobe': 'IDUT.event_strobe_i'}
    if any(not set(keys.values()).issubset(row) for row in rows):
        raise ValueError('missing component core boundary evidence')
    ts = [row['time'] for row in rows]
    resolution = case.get('resolution', tr / 4)

    def at(t, node):
        j = max(0, min(len(rows)-2, bisect.bisect_right(ts, t)-1))
        a, b = rows[j], rows[j+1]
        return a[node] + (b[node]-a[node]) * (t-a['time'])/(b['time']-a['time'])

    def crossings(node):
        found = []
        for a, b in zip(rows, rows[1:]):
            av, bv = a[node]-th, b[node]-th
            if av < 0 <= bv or av > 0 >= bv:
                found.append((a['time']+(b['time']-a['time'])*(-av)/(bv-av), bv > av))
        return found

    events = []
    for node in ('chop_clk', 'rst', 'enable'):
        events += [(t, node, rising) for t, rising in crossings(node)]
    events.sort()
    history = [(0., 0., 0.)]
    notifications = []
    strobe = 0
    for t, node, rising in events:
        reset = at(t+resolution, 'rst') > th or at(t+resolution, 'enable') <= th
        if (node == 'rst' and rising) or (node == 'enable' and not rising):
            history.append((t, 0., 0.))
            if strobe:
                notifications.append((t+2*tr, 0))
            strobe = 0
        elif node == 'chop_clk' and not reset and at(t, 'hold') <= th:
            polarity = 1 if rising else -1
            ref = gain*(at(t, 'vinp')-at(t, 'vinn'))
            history.append((t, ref+polarity*gain*offset, ref))
            strobe = 1-strobe
            notifications.append((t+2*tr, strobe))
    failures = []
    checks = 0
    cursor = 0
    for row in rows:
        t = row['time']
        while cursor+1 < len(history) and history[cursor+1][0] <= t:
            cursor += 1
        when, sample, ref = history[cursor]
        # The public requirement is that the sample is established before the
        # notification starts, not a mandated internal contribution waveform.
        if t > when+2*tr:
            for node, expected in ((keys['sample'], sample), (keys['ref'], ref)):
                checks += 1
                if abs(row[node]-expected) > .002 and len(failures) < 20:
                    failures.append(dict(time=t, node=node, expected=expected, actual=row[node]))
    actual = crossings(keys['strobe'])
    expected = [(t+tr/2, bool(state)) for t, state in notifications]
    checks += max(len(actual), len(expected))
    if len(actual) != len(expected) or any(
            direction != want_direction or abs(t-want) > 2*resolution
            for (t, direction), (want, want_direction) in zip(actual, expected)):
        failures.append(dict(node=keys['strobe'], reason='core notification count/timing',
                             expected=expected[:20], actual=actual[:20]))
    return dict(passed=not failures, checks=checks, failures=failures)

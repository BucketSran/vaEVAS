"""Finite callback evidence from separately identified Spectre trace attempts.

The caller verifies the installed producer, manifests and native double export.
Every trace is retained. No waveform interpolation, callback fitting, interval
clipping or original assessment change is permitted here.
"""
from copy import deepcopy
from fractions import Fraction as F
import math

from breadth_callback_trace import COUNTERS, instrument, parse


def qualify(card, executed_source, log, rows, *, producer_qualified=False, format_version=2):
    records = []
    try:
        if not producer_qualified:
            raise ValueError('installed producer and direct double export are unreviewed')
        if executed_source != instrument(card, format_version=format_version)[0]:
            raise ValueError('executed source is not the exact reviewed instrumentation')
        records = parse(log)
        required = {'time', *card['inputs'], *card['outputs'], *card['counter_channels']}
        if len(rows) < 3 or any(any(type(row.get(name)) not in (int, float)
                                   or not math.isfinite(row[name]) for name in required) for row in rows):
            raise ValueError('missing or nonfinite native observations')
        if any(b['time'] <= a['time'] for a, b in zip(rows, rows[1:])):
            raise ValueError('native times are not strictly increasing')
        if card['id'] in ('EC06-v1', 'EC06-v2'):
            mapping = {('n0', 'dut.acell'): 'n', ('n0', 'dut.bcell'): 'hidden_bcell_n'}
        elif card['id'] == 'EC20-v1':
            mapping = {('a', 'dut'): 'na', ('b', 'dut'): 'nb'}
        else:
            if len(COUNTERS[card['id']]) != 1 or len(card['counter_channels']) != 1:
                raise ValueError('counter mapping is outside the reviewed source scope')
            mapping = {(COUNTERS[card['id']][0], 'dut'): next(iter(card['counter_channels']))}
        visible = set(mapping.values()) - {'hidden_bcell_n'}
        if visible != set(card['counter_channels']):
            raise ValueError('counter inventory differs from the reviewed mapping')
        if any(event['counter'] not in visible for event in card['events']):
            raise ValueError('event has no reviewed counter channel')
        ids = [event['id'] for event in card['events']]
        if len(set(ids)) != len(ids):
            raise ValueError('event identities are not unique')
        by_channel = {name: [] for name in mapping.values()}
        previous = -math.inf
        for record in records:
            key = (record['counter_symbol'], record['instance'])
            if key not in mapping:
                raise ValueError('unmapped counter or instance; no trace may be discarded')
            time = float(record['time_token'])
            if not math.isfinite(time) or not 0 <= time <= card['stop_s'] or time < previous:
                raise ValueError('invalid or reversed actual callback time')
            previous = time
            by_channel[mapping[key]].append({**record, 'time_s': time})
        # Both instances are logged. The unused child's callbacks must exactly
        # match the two schedules; they are not silently filtered out.
        if 'hidden_bcell_n' in by_channel:
            child = [(r['index'], r['time_s']) for r in by_channel['hidden_bcell_n']]
            visible = [(r['index'], r['time_s']) for r in by_channel['n']]
            if child != visible:
                raise ValueError('child schedule differs; separate hidden-channel reference required')
        bounds = {}
        # Reuse the frozen checker's represented-window endpoints and 16-ULP
        # allowance. Do not silently make the new adapter stricter than science.
        # The full actual point is retained, and the same allowance remains in
        # science's input/reference/output error budget; no box is clipped.
        ut = 16 * math.ulp(card['stop_s'])
        for name, state in card['counter_channels'].items():
            channel = by_channel[name]
            expected = [e for e in card['events'] if e['counter'] == name]
            if len(channel) != len(expected):
                raise ValueError('missing or repeated actual callback')
            for i, (record, event) in enumerate(zip(channel, expected, strict=True)):
                if record['index'] != state['initial'] + i + 1 or event['index'] != record['index']:
                    raise ValueError('counter sequence differs from the frozen events')
                nominal = event['nominal_s']
                lower = F(nominal - event['early_s']) - F(ut)
                upper_value = nominal + event['late_s']
                if event['kind'] == 'cross':
                    slope = event['slope_V_s']
                    tolerance = event['expression_tolerance_V']
                    if not math.isfinite(slope) or slope == 0 or not math.isfinite(tolerance) or tolerance < 0:
                        raise ValueError('invalid cross slope or expression tolerance')
                    upper_value = min(upper_value, nominal + tolerance / abs(slope))
                upper = F(upper_value) + F(ut)
                time = F(record['time_s'])
                if not lower <= time <= upper:
                    raise ValueError('actual callback is outside the frozen legal window: ' + event['id'])
                bounds[event['id']] = [record['time_s'], record['time_s']]
            values = [round(row[name]) for row in rows]
            if values[0] != state['initial'] or values[-1] != state['final']:
                raise ValueError('initial or final counter differs')
            if any(abs(row[name] - value) > 1e-9 for row, value in zip(rows, values, strict=True)):
                raise ValueError('native counter is not integral')
            if any(b - a not in (0, 1) for a, b in zip(values, values[1:])):
                raise ValueError('native counter skips or repeats an event')
            for row, value in zip(rows, values, strict=True):
                minimum = state['initial'] + sum(r['time_s'] < row['time'] - ut for r in channel)
                maximum = state['initial'] + sum(r['time_s'] <= row['time'] + ut for r in channel)
                if not minimum <= value <= maximum:
                    raise ValueError('native counter contradicts the logged callback')
        if card.get('order_evidence_required'):
            for a, b in zip(card['events'], card['events'][1:]):
                if bounds[a['id']][1] >= bounds[b['id']][0]:
                    raise ValueError('required cross-channel strict order is not proved')
        return {'status': 'qualified', 'event_bounds_s': bounds, 'records': records,
                'time_observation_allowance_s': ut,
                'claim': 'actual callbacks of this separately identified trace attempt; finite observations only'}
    except (ValueError, KeyError, TypeError, IndexError, ArithmeticError) as error:
        return {'status': 'unknown', 'reason': str(error), 'records': records}


def reanalyze(science, card, executed_source, log, rows, contract, *, producer_qualified=False, format_version=2):
    old = science.assess(card, rows, contract)
    proof = qualify(card, executed_source, log, rows, producer_qualified=producer_qualified,
                    format_version=format_version)
    result = {'original_assessment': old, 'callback_evidence': proof}
    if proof['status'] != 'qualified':
        return result
    if not all(key in old.get('behavior', {}) for key in ('errors', 'issues')):
        result['reanalyze_status'] = 'original waveform assessment is incomplete'
        return result
    reference = science._reference(card)

    def actual_reference(c, t, unused):
        return reference(c, t, deepcopy(proof['event_bounds_s']))

    new = science.assess(card, rows, contract, reference=actual_reference)
    resolved = set()
    for event in card['events']:
        resolved.add('full callback bracket does not fit legal window: ' + event['id'])
        resolved.add('callback outside legal window: ' + event['id'])
    if card.get('order_evidence_required'):
        resolved.add('independent callback order evidence unavailable')
        resolved.add('cross-channel callback order is unresolved')
    keep = lambda issues: [x for x in issues if x not in resolved]
    new['behavior']['errors'] = keep(new['behavior']['errors'])
    new['behavior']['issues'] = keep(new['behavior']['issues'])
    new['behavior']['status'] = ('behavior_error' if new['behavior']['errors'] else
                                'unknown' if new['behavior']['issues'] else 'pass')
    new['event_bounds_s'] = deepcopy(proof['event_bounds_s'])
    new['observation_issues'] = keep(new['observation_issues'])
    new['evidence'] = {'status': 'evidence_insufficient' if new['observation_issues'] else 'complete',
                       'issues': new['observation_issues']}
    for tier in new['tiers'].values():
        tier['evidence']['issues'] = keep(tier['evidence']['issues'])
        tier['evidence']['status'] = 'evidence_insufficient' if tier['evidence']['issues'] else 'complete'
        tier['behavior'] = deepcopy(new['behavior'])
        tier['status'] = ('behavior_error' if new['behavior']['errors'] else
                          'numerical_error' if tier['numerical']['status'] == 'numerical_error' else
                          'evidence_insufficient' if tier['evidence']['issues'] else tier['numerical']['status'])
    result['new_assessment'] = new
    return result

"""Shared finite-observation grading for independent breadth references.

This module never reads simulator tolerances or fits callback times to outputs.
Native export and effective-setting provenance are separate runner obligations.
"""
from bisect import bisect_left
from copy import deepcopy
from fractions import Fraction
import importlib
import json
import math
from pathlib import Path

from precision_reference import pwl_range, slope_bound



def _validate_card(card):
    for field in ('scale_V', 'unit_s', 'stop_s'):
        if type(card[field]) not in (float, int) or not math.isfinite(card[field]) or card[field] <= 0:
            raise ValueError('invalid positive card field: ' + field)
    outputs = card['outputs']
    if not outputs or len(set(outputs)) != len(outputs):
        raise ValueError('missing or duplicate outputs')
    for field in ('input_gain_bound', 'output_slope_bound_V_s'):
        value = card[field]
        if isinstance(value, dict):
            if any(name not in value for name in outputs if name not in card.get('counter_channels', {})):
                raise ValueError('missing per-output uncertainty bound: ' + field)
            values = value.values()
        else:
            values = [value]
        if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in values):
            raise ValueError('invalid uncertainty bound: ' + field)
    for name, points in card['inputs'].items():
        if not points or any(len(p) != 2 or any(type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points):
            raise ValueError('invalid input PWL: ' + name)
        if any(b[0] <= a[0] for a, b in zip(points, points[1:])):
            raise ValueError('input timestamps must strictly increase: ' + name)
    events = card.get('events', [])
    if len({e['id'] for e in events}) != len(events):
        raise ValueError('duplicate event identity')
    indexes = [(e.get('counter'), e['index']) for e in events if e.get('counter')]
    if len(set(indexes)) != len(indexes):
        raise ValueError('duplicate counter event index')
    channels = card.get('counter_channels', {})
    for states in channels.values():
        if any(type(states[k]) is not int for k in ('initial', 'final')) or states['final'] < states['initial']:
            raise ValueError('invalid counter initial/final state')
    for e in events:
        if type(e['index']) is not int:
            raise ValueError('event index must be an integer')
        for field in ('nominal_s', 'early_s', 'late_s'):
            if type(e[field]) not in (float, int) or not math.isfinite(e[field]) or e[field] < 0:
                raise ValueError('invalid event time/tolerance: ' + field)
        if e['nominal_s'] > card['stop_s'] or e['nominal_s'] - e['early_s'] < 0:
            raise ValueError('event outside run extent')
        if e.get('counter'):
            if e['counter'] not in channels:
                raise ValueError('undeclared counter channel: ' + e['counter'])
            states = channels[e['counter']]
            if not states['initial'] < e['index'] <= states['final']:
                raise ValueError('event index outside declared counter extent')
    for p in card.get('undefined_points', []):
        if any(type(p[k]) not in (float, int) or not math.isfinite(p[k]) for k in ('time_s', 'left_s', 'right_s')):
            raise ValueError('invalid undefined-point time')
        if not 0 <= p['left_s'] < p['time_s'] < p['right_s'] <= card['stop_s']:
            raise ValueError('invalid one-sided undefined-point obligations')
        if not p['outputs'] or len(set(p['outputs'])) != len(p['outputs']) or any(name not in outputs for name in p['outputs']):
            raise ValueError('invalid undefined-point output obligation')


def load_contract(*, cards=None):
    """Reuse frozen Q budgets; optional explicit cards support calibration."""
    old = json.loads(Path(__file__).with_name('precision-v2.json').read_text())
    if cards is None:
        cards = []
        for family in ('foundation', 'composition'):
            cards.extend(importlib.import_module('precision_breadth_' + family).cards())
        expected = {f'F{i:02}' for i in range(1, 21)} | {f'EC{i:02}' for i in range(1, 25)}
        if {c['group_id'] for c in cards} != expected:
            raise ValueError('breadth group inventory is incomplete')
    cards = deepcopy(cards)
    for card in cards:
        _validate_card(card)
    if len({c['id'] for c in cards}) != len(cards):
        raise ValueError('duplicate variant identity')
    return {'schema_version': 1, 'id': 'precision-breadth-v1', 'cards': cards,
            'denominator': len({c['group_id'] for c in cards}),
            **{key: deepcopy(old[key]) for key in ('tiers', 'budgets', 'observation', 'profiles', 'controls')}}


def critical_points(card):
    points = [{'id': 'start', 'time_s': 0.}, {'id': 'stop', 'time_s': card['stop_s']}]
    points.extend({'id': f'input:{name}:{i}', 'time_s': t}
                  for name, knots in card['inputs'].items() for i, (t, _) in enumerate(knots))
    points.extend({'id': f'critical:{i}', 'time_s': t} for i, t in enumerate(card.get('critical_times_s', [])))
    for e in card.get('events', []):
        for label, t in (('nominal', e['nominal_s']), ('early', e['nominal_s'] - e['early_s']),
                         ('late', e['nominal_s'] + e['late_s'])):
            points.append({'id': f"event:{e['id']}:{label}", 'time_s': t})
    for i, p in enumerate(card.get('undefined_points', [])):
        points.extend({'id': f'undefined:{i}:{side}', 'time_s': p[key], 'sides': side == 'center'}
                      for side, key in (('center', 'time_s'), ('left', 'left_s'), ('right', 'right_s')))
    return [p for p in points if 0 <= p['time_s'] <= card['stop_s']]


def observation_plan(card, contract):
    _validate_card(card)
    config = contract['observation']; stop = card['stop_s']
    step = Fraction(card['unit_s']) * Fraction(config['global_request_units'])
    times = {float(i * step) for i in range(math.ceil(Fraction(stop) / step) + 1)}
    critical = critical_points(card)
    for p in list(critical):
        t = p['time_s']; times.add(t)
        for side, delta in (('left', -config['padding_s']), ('right', config['padding_s'])):
            q = t + delta
            if 0 <= q <= stop:
                times.add(q); critical.append({'id': p['id'] + ':' + side, 'time_s': q})
    # Timing requests target Q3 and propagate input amplification. They never
    # select a callback time; counter changes in actual rows provide that fact.
    gain = card['input_gain_bound']
    gains = list(gain.values()) if isinstance(gain, dict) else [gain]
    slope = card['output_slope_bound_V_s']
    slopes = list(slope.values()) if isinstance(slope, dict) else [slope]
    sensitivity = max(slopes, default=0.) + max(gains, default=0.) * max((slope_bound(p) for p in card['inputs'].values()), default=0.)
    target = (contract['budgets']['absolute_V'] + contract['budgets']['relative'] * card['scale_V']) * .1
    sensitivity = card.get('event_sensitivity_bound_V_s', sensitivity)
    if sensitivity is not None and (not math.isfinite(sensitivity) or sensitivity < 0):
        raise ValueError('invalid event-time sensitivity')
    interval = min(config['constant_interval_s'], target * config['observation_fraction'] / sensitivity) if sensitivity else config['constant_interval_s']
    grids = []
    events = card.get('events', [])
    dense_cap = 20000
    for index, e in enumerate(events):
        a = max(0., e['nominal_s'] - e['early_s'] - config['padding_s'])
        b = min(stop, e['nominal_s'] + e['late_s'] + config['padding_s'])
        n = max(1, math.ceil((Fraction(b) - Fraction(a)) / Fraction(interval)))
        wanted = n
        allocated_points = dense_cap // len(events) + (index < dense_cap % len(events))
        n = min(n, max(1, allocated_points - 1))
        grids.append({'event': e['id'], 'sensitivity_bound_V_s': sensitivity,
                      'requested_intervals': wanted, 'planned_intervals': n,
                      'request_density_capped': wanted != n, 'sensitivity_known': sensitivity is not None,
                      'possible_evidence_insufficiency': wanted != n or sensitivity is None,
                      'planned_interval_s': (b - a) / n,
                      'claim': 'request density only; actual rows and reference intervals still determine evidence'})
        times.update(float(Fraction(a) + (Fraction(b) - Fraction(a)) * i / n) for i in range(n + 1))
    return {'id': 'breadth-native-v1', 'target_tier': 'Q3', 'times_s': sorted(t for t in times if 0 <= t <= stop),
            'critical': critical, 'event_grids': grids, 'dense_request_cap': dense_cap,
            'claim': 'requests only; actual rows are qualified separately'}


def _uncertainty(value, scale, ulps):
    return ulps * math.ulp(max(abs(value), scale))


def _bound(value, output):
    return value[output] if isinstance(value, dict) else value


def _reference(card):
    return importlib.import_module('precision_breadth_' + card['family']).reference



def _event_history(card, rows, ut, count_tolerance):
    """Derive brackets from counter changes, never intersect with legal windows."""
    errors = []; issues = []; bounds = {}; transitions = {}
    channels = card.get('counter_channels', {})
    for name, states in channels.items():
        values = [round(r[name]) for r in rows]
        if any(abs(r[name] - n) > count_tolerance for r, n in zip(rows, values)):
            errors.append('noninteger counter: ' + name)
        if values[0] != states['initial'] or values[-1] != states['final']:
            errors.append('incorrect initial/final event count: ' + name)
        if any(b - a not in (0, 1) for a, b in zip(values, values[1:])):
            errors.append('missing, repeated or reversed event: ' + name)
        transitions[name] = {n: [rows[i - 1]['time'] - ut, rows[i]['time'] + ut]
                             for i, n in enumerate(values) if i and n != values[i - 1]}
    events = card.get('events', [])
    declared = {(e.get('counter'), e['index']) for e in events if e.get('counter')}
    for name, observed in transitions.items():
        if any((name, index) not in declared for index in observed):
            errors.append('undeclared event: ' + name)
    for e in events:
        early = e['nominal_s'] - e['early_s']; late = e['nominal_s'] + e['late_s']
        if e.get('kind') == 'cross' and e.get('slope_V_s') and 'expression_tolerance_V' in e:
            late = min(late, e['nominal_s'] + e['expression_tolerance_V'] / abs(e['slope_V_s']))
        channel = e.get('counter')
        if channel not in channels:
            bounds[e['id']] = [early, late]
            issues.append('callback lacks observable counter: ' + e['id'])
            continue
        bracket = transitions[channel].get(e['index'])
        if bracket is None:
            errors.append('missing observable event: ' + e['id'])
            bounds[e['id']] = [early, late]
            continue
        bounds[e['id']] = bracket
        if bracket[1] < early - ut or bracket[0] > late + ut:
            errors.append('callback outside legal window: ' + e['id'])
        elif bracket[0] < early - ut or bracket[1] > late + ut:
            issues.append('full callback bracket does not fit legal window: ' + e['id'])
    # Same-channel increments establish order even when their brackets touch.
    # Different channels require disjoint observed brackets to prove strict order.
    for previous, current in zip(events, events[1:]):
        if previous.get('counter') not in channels or current.get('counter') not in channels:
            # Declared legal windows cannot establish observed callback order.
            # Missing-counter issues above already keep this history unknown.
            continue
        if previous.get('counter') == current.get('counter') and previous.get('counter') in channels:
            if current['index'] <= previous['index']:
                errors.append('declared same-channel event order is reversed')
            continue
        a = bounds[previous['id']]; b = bounds[current['id']]
        if a[0] > b[1]:
            errors.append('observed callback order is reversed')
        elif a[1] >= b[0]:
            issues.append('cross-channel callback order is unresolved')
    if card.get('timing_evidence_required') and not events:
        issues.append('required callback timing evidence unavailable')
    status = 'behavior_error' if errors else 'unknown' if issues else 'pass'
    return bounds, {'status': status, 'errors': errors, 'issues': issues}, issues


def assess(card, rows, contract, *, reference=None):
    """Grade actual times, all outputs and one counter-derived event history."""
    _validate_card(card)
    budgets = contract['budgets']; scale = card['scale_V']
    result = {'schema_version': 1, 'condition': card['id'], 'group_id': card['group_id'],
              'claim': 'finite actual observations; no whole-trajectory or settings proof',
              'setting_evidence': {'status': 'unknown', 'reason': 'effective settings require runner evidence'},
              'behavior': {'status': 'pass'}, 'outputs': {}, 'tiers': {}}
    issues = []
    result['phase_evidence'] = {'status': 'unknown' if card.get('phase_obligations') else 'not_required'}
    result['input_gain_evidence'] = {'status': 'unknown' if card.get('input_gain_evidence_required') else 'not_required'}
    if card.get('phase_obligations'):
        issues.append('DC/transient phase requires independent adapter evidence')
    if card.get('order_evidence_required'):
        issues.append('independent callback order evidence unavailable')
    if card.get('input_exact_evidence_required'):
        issues.append('exact input identity requires independent export evidence')
    if card.get('input_gain_evidence_required'):
        issues.append('input derivative or topology requires independent adapter evidence')
    required = ['time', *card['inputs'], *card['outputs'], *card.get('counter_channels', {})]
    malformed = False
    if len(rows) < 3 or any(any(type(r.get(k)) not in (int, float) or not math.isfinite(r[k]) for k in required) for r in rows):
        issues.append('missing or nonfinite observations'); malformed = True
    elif any(b['time'] <= a['time'] for a, b in zip(rows, rows[1:])):
        issues.append('timestamps are not strictly increasing'); malformed = True
    if malformed:
        result.update(behavior={'status': 'unknown'}, observation_issues=issues,
                      evidence={'status': 'evidence_insufficient', 'issues': issues})
        result['tiers'] = {q['id']: {'status': 'evidence_insufficient', 'numerical': {'status': 'unknown'},
                                    'evidence': result['evidence'], 'behavior': result['behavior']} for q in contract['tiers']}
        return result
    times = [r['time'] for r in rows]
    ut = _uncertainty(card['stop_s'], card['stop_s'], budgets['time_serialization_ulps'])
    if abs(times[0]) > ut or abs(times[-1] - card['stop_s']) > ut:
        issues.append('incomplete start/stop coverage')
    if max(b - a for a, b in zip(times, times[1:])) > card['unit_s'] * budgets['global_gap_units'] + 2 * ut:
        issues.append('observation gap exceeds frozen limit')
    distance = budgets['boundary_distance_s']
    for p in critical_points(card):
        t = p['time_s']; i = bisect_left(times, t); near = times[max(0, i - 2):i + 3]
        if not near or min(abs(q - t) for q in near) > distance + ut:
            issues.append('missing boundary: ' + p['id'])
        if p.get('sides', True) and 0 < t < card['stop_s'] and (not any(t - distance - ut <= q < t - ut for q in near)
                                    or not any(t + ut < q <= t + distance + ut for q in near)):
            issues.append('missing boundary sides: ' + p['id'])
    input_errors = {}
    for name, pts in card['inputs'].items():
        errors = []
        for row in rows:
            lo, hi, rounding = pwl_range(pts, row['time'], row['time'])
            errors.append(max(abs(row[name] - lo), abs(row[name] - hi)) + rounding
                          + _uncertainty(row[name], scale, budgets['voltage_serialization_ulps'])
                          + slope_bound(pts) * ut)
        input_errors[name] = max(errors)
    result['input_error_upper_V'] = input_errors
    result['time_observation_allowance_s'] = ut
    event_bounds, behavior, event_issues = _event_history(card, rows, ut, budgets['count_V'])
    result['event_bounds_s'] = event_bounds
    result['behavior'] = behavior
    issues.extend(event_issues)
    reference = reference or _reference(card)
    reference_card = deepcopy(card)
    reference_card['reference_time_uncertainty_s'] = ut
    result['reference_time_uncertainty_s'] = ut
    answers = []; reference_ok = True
    result['undefined_observations'] = []
    result['unqualified_observations'] = []
    try:
        for row in rows:
            # Only validated counters condition the current discrete phase.
            # Full callback boxes remain unchanged for all continuous history.
            stages = ({name: round(row[name]) for name in card.get('counter_channels', {})}
                      if not behavior['errors'] else {})
            current_card = deepcopy(reference_card)
            current_card['reference_counter_stages'] = stages
            current_card['reference_event_stages'] = {e['id']: stages[e['counter']] >= e['index']
                                                       for e in card.get('events', []) if e.get('counter') in stages}
            answer = reference(current_card, row['time'], deepcopy(result['event_bounds_s']))
            rounding = answer['numerical_uncertainty_V']
            if type(rounding) not in (int, float) or not math.isfinite(rounding) or rounding < 0:
                raise ValueError('invalid numerical reference uncertainty')
            for output in card['outputs']:
                if output in card.get('counter_channels', {}):
                    continue
                reason = answer.get('undefined', {}).get(output)
                if reason:
                    declared = [p for p in card.get('undefined_points', [])
                                if output in p['outputs'] and abs(row['time'] - p['time_s']) <= math.ulp(p['time_s']) / 2]
                    if not declared or not isinstance(reason, str):
                        raise ValueError('undeclared mathematical undefined point: ' + output)
                    for p in declared:
                        if not 0 <= p['left_s'] < p['time_s'] < p['right_s'] <= card['stop_s']:
                            raise ValueError('invalid one-sided undefined-point obligations')
                        if not any(t < p['time_s'] - ut and abs(t - p['left_s']) <= distance + ut for t in times):
                            issues.append('missing undefined left obligation: ' + output)
                        if not any(t > p['time_s'] + ut and abs(t - p['right_s']) <= distance + ut for t in times):
                            issues.append('missing undefined right obligation: ' + output)
                    result['undefined_observations'].append({'time_s': row['time'], 'output': output, 'reason': reason})
                    continue
                lo, hi = answer['outputs'][output]
                if any(type(v) not in (int, float) or not math.isfinite(v) for v in (lo, hi)) or lo > hi:
                    raise ValueError('invalid reference interval: ' + output)
            answers.append(answer)
    except (NotImplementedError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        reference_ok = False
        issues.append('reference unavailable or invalid: ' + str(exc))
    if card.get('support_probe_only') or card.get('probe_only'):
        reference_ok = False
        issues.append('semantic support probe is not a qualification')
    for output in card['outputs']:
        if output in card.get('counter_channels', {}):
            continue
        lower = upper = rounding_max = unresolved = 0.; witness = None
        conditional_lower = conditional_upper = 0.; unqualified = 0
        gain_obligation = card.get('input_gain_evidence_required')
        gain_unknown = output in gain_obligation if isinstance(gain_obligation, dict) else bool(gain_obligation)
        phase = card.get('phase_obligations')
        dc = phase.get('dc', {}) if isinstance(phase, dict) else {}
        phase_outputs = dc.get('outputs', card['outputs'])
        phase_time = dc.get('time_s', 0.)
        gain = _bound(card['input_gain_bound'], output)
        slope = _bound(card['output_slope_bound_V_s'], output)
        input_u = max(input_errors.values(), default=0.) * gain
        observed = 0
        for row, answer in zip(rows, answers if reference_ok else []):
            if answer.get('undefined', {}).get(output):
                continue
            lo, hi = answer['outputs'][output]; rounding = answer['numerical_uncertainty_V']
            export = _uncertainty(row[output], scale, budgets['voltage_serialization_ulps'])
            if answer.get('time_uncertainty_included') is not True:
                export += slope * ut
            uncertainty = rounding + export + input_u
            low = max(0., lo - row[output] - uncertainty, row[output] - hi - uncertainty)
            high = max(abs(row[output] - lo), abs(row[output] - hi)) + uncertainty
            conditional_lower = max(conditional_lower, low); conditional_upper = max(conditional_upper, high)
            phase_unknown = bool(phase and output in phase_outputs and abs(row['time'] - phase_time) <= ut)
            if gain_unknown or phase_unknown:
                unqualified += 1
                result['unqualified_observations'].append({'time_s': row['time'], 'output': output,
                    'reasons': (['input derivative or topology is unproved'] if gain_unknown else [])
                             + (['DC/transient phase is unproved'] if phase_unknown else [])})
                continue
            observed += 1
            lower = max(lower, low); rounding_max = max(rounding_max, rounding)
            unresolved = max(unresolved, (hi - lo) / 2 + export)
            if high > upper:
                upper = high; witness = {'time_s': row['time'], 'actual_V': row[output], 'reference_V': [lo, hi]}
        if not observed:
            issues.append('no qualified defined reference observations: ' + output)
        result['outputs'][output] = {'defined_observations': observed, 'unqualified_observations': unqualified,
                                     'conditional_error_lower_V': conditional_lower, 'conditional_error_upper_V': conditional_upper,
                                     'error_lower_V': lower, 'error_upper_V': upper,
                                     'reference_uncertainty_V': rounding_max, 'unresolved_uncertainty_V': unresolved,
                                     'input_uncertainty_V': input_u, 'worst': witness}
    result['observation_issues'] = issues
    result['evidence'] = {'status': 'evidence_insufficient' if issues else 'complete', 'issues': issues}
    for q in contract['tiers']:
        budget = (budgets['absolute_V'] + budgets['relative'] * scale) * q['factor']
        lower = max((r['error_lower_V'] for r in result['outputs'].values()), default=0.)
        upper = max((r['error_upper_V'] for r in result['outputs'].values()), default=0.)
        numerical = ('numerical_error' if reference_ok and lower > budget else
                     'unknown' if not reference_ok or any(r['unqualified_observations'] for r in result['outputs'].values()) else
                     'pass' if upper <= budget else 'evidence_insufficient')
        tier_issues = list(issues)
        if any(e > budget * contract['observation']['input_fraction'] for e in input_errors.values()):
            tier_issues.append('input uncertainty exceeds B/100')
        for r in result['outputs'].values():
            if r['input_uncertainty_V'] > budget * contract['observation']['input_fraction']:
                tier_issues.append('amplified input uncertainty exceeds B/100')
            if r['reference_uncertainty_V'] > budget * contract['observation']['reference_fraction']:
                tier_issues.append('reference uncertainty exceeds B/100')
            if r['unresolved_uncertainty_V'] > budget * contract['observation']['observation_fraction']:
                tier_issues.append('timing or export uncertainty exceeds B/10')
        evidence = {'status': 'evidence_insufficient' if tier_issues else 'complete', 'issues': tier_issues}
        status = ('behavior_error' if result['behavior']['status'] == 'behavior_error' else
                  numerical if numerical == 'numerical_error' else
                  'evidence_insufficient' if tier_issues else numerical)
        result['tiers'][q['id']] = {'status': status, 'voltage_budget_V': budget,
                                   'numerical': {'status': numerical, 'error_lower_V': lower, 'error_upper_V': upper},
                                   'behavior': result['behavior'], 'evidence': evidence}
    return result

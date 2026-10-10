"""Qualify these two rational trajectories without rewriting native timestamps.

The legacy checker stays authoritative for its exact-anchor contract. This adds a
separate, explicitly bounded continuous-anchor observation contract; it is not a
generic nearest-neighbor matcher or an event-boundary exception.
"""
from fractions import Fraction
import math

from check import check_dynamic

BUDGETS = {'z': 1e-7, 'low': 1e-7, 'amp': 1e-3}
ANCHOR_OFFSET_S = 1e-12


def rational_values(time, event=False):
    t = Fraction(time)
    z = 1 / (Fraction(1, 2) + 2 * t) if event and t > Fraction(1, 2) else 1 / (1 + t)
    return {'z': z, 'low': z - Fraction(1, 2), 'amp': 10000 * (z - Fraction(1, 2))}


def qualify_dynamic(rows, event=False, events=None, tolerances=None):
    legacy = check_dynamic(rows, event, events)
    result = {'legacy': legacy, 'qualified_finite_observations': False}
    if any(f['kind'] in ('invalid_time_observation', 'invalid_signal', 'outside_stop')
           for f in legacy['failures']):
        return result
    maxima = {name: Fraction(0) for name in BUDGETS}
    ratio = Fraction(0)
    for row in rows:
        for name, expected in rational_values(row['time'], event).items():
            error = abs(Fraction(row[name]) - expected)
            maxima[name] = max(maxima[name], error)
            if tolerances is not None:
                budget = Fraction(tolerances['absolute']) + Fraction(tolerances['relative']) * abs(expected)
                if budget <= 0:
                    raise ValueError('positive request voltage budget required')
                ratio = max(ratio, error / budget)
    native_pass = all(maxima[n] <= Fraction(b) for n, b in BUDGETS.items())
    required = [0., .125, .25, .5, .75, 1.]
    if event:
        required.append(.5 + 1e-8)
    anchors = []
    for target in sorted(required):
        # Endpoints and the event boundary retain exact-time obligations.
        exact_required = target in (0., .5, 1.)
        candidates = [row for row in rows
                      if (row['time'] == target if exact_required else
                          abs(Fraction(row['time']) - Fraction(target)) <= Fraction(ANCHOR_OFFSET_S)
                          and (not event or (row['time'] > .5) == (target > .5)))]
        if not candidates:
            anchors.append({'target_s': target, 'pass': False, 'reason': 'missing_anchor_observation'})
            continue
        row = min(candidates, key=lambda r: (abs(Fraction(r['time']) - Fraction(target)), r['time']))
        at_native = rational_values(row['time'], event)
        at_target = rational_values(target, event)
        bounds, shifts = {}, {}
        for name in BUDGETS:
            shifts[name] = abs(at_native[name] - at_target[name])
            # Triangle inequality bounds the requested-anchor error. Neither
            # output values nor their native observation times are changed.
            bounds[name] = abs(Fraction(row[name]) - at_native[name]) + shifts[name]
        passed = all(bounds[n] <= Fraction(b) for n, b in BUDGETS.items())
        anchors.append({'target_s': target, 'native_s': row['time'],
                        'offset_s': float(Fraction(row['time']) - Fraction(target)),
                        'exact_time': row['time'] == target, 'pass': passed,
                        'voltage_time_shift_V': {n: float(v) for n, v in shifts.items()},
                        'anchor_error_bound_V': {n: float(v) for n, v in bounds.items()}})
    # Never drop waveform, count, event-bracket or native-event failures.
    other_failures = [f for f in legacy['failures'] if f['kind'] != 'missing_anchor']
    result.update(native_math_pass=native_pass,
                  rational_max_error_V={n: float(v) for n, v in maxima.items()},
                  anchors=anchors, continuous_anchor_contract_pass=all(a['pass'] for a in anchors),
                  max_request_budget_ratio=float(ratio) if tolerances is not None else None,
                  request_budget_pass=ratio <= 1 if tolerances is not None else None,
                  qualified_finite_observations=not other_failures and native_pass
                      and all(a['pass'] for a in anchors) and (tolerances is None or ratio <= 1))
    return result


def compare_native(evas_rows, spectre_rows):
    """Paired voltages only; each backend must separately qualify its reference."""
    if not evas_rows or len(evas_rows) != len(spectre_rows):
        return {'pass': False, 'reason': 'row_count_mismatch'}
    maxima = {name: Fraction(0) for name in BUDGETS}
    for left, right in zip(evas_rows, spectre_rows):
        if left.get('time') != right.get('time'):
            return {'pass': False, 'reason': 'time_mismatch'}
        for name in BUDGETS:
            if not all(isinstance(r.get(name), (int, float)) and math.isfinite(r[name])
                       for r in (left, right)):
                return {'pass': False, 'reason': 'invalid_voltage'}
            maxima[name] = max(maxima[name], abs(Fraction(left[name]) - Fraction(right[name])))
    return {'pass': all(maxima[n] <= Fraction(b) for n, b in BUDGETS.items()),
            'max_error_V': {n: float(v) for n, v in maxima.items()}, 'rows': len(evas_rows)}

"""Supplemental finite Gnucap output bounds; never replaces original assessments.

The producer's reviewed source, binary identity and rounding environment are
external premises. This module does not check or grant producer qualification.
The 71-position audit driver separately rejects events/counter channels and
enforces F03/F04 constant-consumer certificates. Direct calls bypass those
guards; a returned arithmetic pass is conditional on the caller proving them.
Passing these arithmetic gates does not establish accepted
history, effective solver settings, or whole-trajectory accuracy.
"""
from bisect import bisect_left
from fractions import Fraction as F
import math

RHO = F(1, 2**43)
TINY = F(1, 10**99)


def finite(value):
    if not math.isfinite(value):
        raise ValueError('nonfinite observation')
    return F(value)


def up(value):
    value = F(value)
    rounded = float(value)
    if not math.isfinite(rounded):
        raise ValueError('nonfinite bound')
    return math.nextafter(rounded, math.inf) if F(rounded) < value else rounded


def inverse_radius(printed):
    """Exact rational inverse of |p-x| <= rho*|x| + tiny."""
    return (RHO * abs(finite(printed)) + TINY) / (1-RHO)


def pwl_slope(points):
    if not points or any(b[0] <= a[0] for a, b in zip(points, points[1:])):
        raise ValueError('invalid PWL')
    return max([abs((finite(b[1])-finite(a[1]))/(finite(b[0])-finite(a[0])))
                for a, b in zip(points, points[1:])] + [F(0)])


def tick_coverage(card, rows, dtmin, critical_points, contract):
    """Recover only unique source-lattice values; keep all native rows intact.

    dtmin must separately be bound to the original source/control path. Restrict
    tick integers to <=2**53, where integer-to-binary64 conversion is exact.
    """
    step = finite(dtmin)
    if step <= 0 or not rows:
        raise ValueError('missing rows or invalid tick size')
    actual, ambiguous = [], []
    for index, row in enumerate(rows):
        printed = finite(row['time'])
        tick = round(printed/step)
        radius = inverse_radius(row['time'])
        if tick < 0 or tick + 2 > 2**53 or radius >= step/2:
            ambiguous.append({'row': index, 'reason': 'outside unique binary64 tick domain'})
            continue
        candidates = [float(k)*dtmin for k in range(max(0, tick-2), tick+3)
                      if abs(F(float(k)*dtmin)-printed) <= radius]
        if len(candidates) != 1:
            ambiguous.append({'row': index, 'candidate_count': len(candidates)})
        else:
            actual.append(F(candidates[0]))
    result = {'native_rows': len(rows), 'unique_tick_rows': len(actual),
              'ambiguous_rows': ambiguous, 'source_runtime_dtmin_s': dtmin,
              'native_rows_unchanged': True, 'accepted_time_chain_proved': False}
    if ambiguous:
        result['complete'] = False
        return result
    stop = finite(card['stop_s'])
    tolerance = F(contract['budgets']['time_serialization_ulps'])*F(math.ulp(card['stop_s']))
    distance = F(contract['budgets']['boundary_distance_s'])
    result.update(start_stop=abs(actual[0]) <= tolerance and abs(actual[-1]-stop) <= tolerance,
                  monotone=all(b>a for a,b in zip(actual,actual[1:])),
                  gap=max([b-a for a,b in zip(actual,actual[1:])]+[F(0)]) <=
                      F(card['unit_s'])*F(contract['budgets']['global_gap_units'])+2*tolerance)
    points = []
    for point in critical_points:
        t = finite(point['time_s'])
        i = bisect_left(actual, t)
        near = actual[max(0,i-2):i+3]
        close = bool(near) and min(abs(x-t) for x in near) <= distance+tolerance
        sides = not point.get('sides', True) or not 0<t<stop or (
            any(t-distance-tolerance <= x < t-tolerance for x in near) and
            any(t+tolerance < x <= t+distance+tolerance for x in near))
        points.append({'id': point.get('id'), 'time_s': float(t), 'close': close, 'both_sides': sides})
    result['critical_points'] = points
    result['all_critical'] = all(p['close'] and p['both_sides'] for p in points)
    result['actual_first_s'], result['actual_last_s'] = float(actual[0]), float(actual[-1])
    result['complete'] = all(result[k] for k in ('start_stop','monotone','gap','all_critical'))
    return result


def additive_budget(card, rows, original, contract, *, coverage_complete):
    """Add full new allowance to every original bound, including old 8ULP.

    F03/F04 constant-consumer certificates are enforced only by the external
    audit driver, not by this arithmetic interface. Calling this function
    directly does not qualify those discontinuous selectors or validate their
    gain premise. The caller must independently prove each bound applies.
    Scalar and per-output dictionaries are both supported for gain and slope.
    """
    names = ['time', *card['inputs'], *card['outputs']]
    if not rows:
        raise ValueError('empty observations')
    radii = {n: max(inverse_radius(r[n]) for r in rows) for n in names}
    dt = radii['time']
    def bound(field, name):
        values = card[field]
        if isinstance(values, dict):
            if name not in values:
                raise ValueError('missing per-output uncertainty bound: ' + field + ':' + name)
            values = values[name]
        value = finite(values)
        if value < 0:
            raise ValueError('negative gain or slope')
        return value
    input_extra = {n: radii[n]+pwl_slope(p)*dt for n,p in card['inputs'].items()}
    input_total = {n: finite(original['input_error_upper_V'][n])+input_extra[n] for n in card['inputs']}
    max_input_extra = max(input_extra.values(), default=F(0))
    outputs = {}
    for name in card['outputs']:
        old = original['outputs'][name]
        gain = bound('input_gain_bound', name)
        slope = bound('output_slope_bound_V_s', name)
        amplified_extra = gain*max_input_extra
        observation_extra = radii[name]+slope*dt
        total_extra = observation_extra+amplified_extra
        outputs[name] = {
            'error_upper_V': up(finite(old['error_upper_V'])+total_extra),
            # Deliberately also include amplified input in observation allocation.
            'unresolved_uncertainty_V': up(finite(old['unresolved_uncertainty_V'])+total_extra),
            'input_uncertainty_V': up(finite(old['input_uncertainty_V'])+amplified_extra),
            'reference_uncertainty_V': old['reference_uncertainty_V'],
            'extra_formatter_V': up(total_extra),
            'observation_formatter_extra_V': up(observation_extra),
            'amplified_input_formatter_extra_V': up(amplified_extra)}
    tiers = {}
    for tier, old in original['tiers'].items():
        budget = finite(old['voltage_budget_V'])
        ib = budget*F(contract['observation']['input_fraction'])
        ob = budget*F(contract['observation']['observation_fraction'])
        rb = budget*F(contract['observation']['reference_fraction'])
        gates = {'old_all_row_assessment_pass': old['status']=='pass',
                 'input_B100': all(x<=ib for x in input_total.values()),
                 'amplified_input_B100': all(F(o['input_uncertainty_V'])<=ib for o in outputs.values()),
                 'reference_B100': all(F(o['reference_uncertainty_V'])<=rb for o in outputs.values()),
                 'observation_B10': all(F(o['unresolved_uncertainty_V'])<=ob for o in outputs.values()),
                 'total_B': all(F(o['error_upper_V'])<=budget for o in outputs.values()),
                 'actual_tick_coverage_original_rules': coverage_complete}
        tiers[tier] = {'gates': gates, 'status': 'pass' if all(gates.values()) else 'pending',
                       'budget_V': float(budget), 'error_upper_V': max(o['error_upper_V'] for o in outputs.values())}
    return {'max_time_formatter_radius_s': up(dt),
            'input_formatter_extra_V': {k: up(v) for k,v in input_extra.items()},
            'input_total_V': {k: up(v) for k,v in input_total.items()}, 'outputs': outputs,
            'new_additive_tiers': tiers, 'old_8ULP_allowance_retained': True,
            'old_8ULP_bound_certified': False, 'historical_scores_unchanged': True,
            'accepted_time_chain_proved': False}

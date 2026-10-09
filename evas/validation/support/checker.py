"""Finite observations against equations fixed before any backend execution.

This checker does not certify interpolation or full-domain support. Discontinuous
boundary windows are an explicit separate outcome, including their raw values.
"""
import math


def pwl(points, x):
    if x <= points[0][0]:
        return points[0][1]
    for (a, y), (b, z) in zip(points, points[1:]):
        if x <= b:
            return y + (z-y)*(x-a)/(b-a)
    return points[-1][1]


def expected(card, x):
    oracle = card['oracle']
    inputs = {n: pwl(p, x) for n, p in card['inputs'].items()}
    u, r = inputs.get('u', 0), inputs.get('r', 0)
    kind = oracle['kind']
    if kind == 'pwl':
        return {n: pwl(p, x) for n, p in oracle['answers'].items()}
    if kind == 'pole_ramp':
        p = oracle['pole_x']
        return {'y': x - math.expm1(p*x)/p}
    if kind == 'linear':
        return {'y': r + oracle['gain']*(u-r) + oracle['offset']}
    if kind == 'cubic':
        # y + y^3/2 is strictly increasing; bisection does not use EVAS code.
        low, high = -4., 4.
        for _ in range(80):
            m = (low+high)/2
            if m + .5*m**3 < u-r:
                low = m
            else:
                high = m
        return {'y': r+(low+high)/2}
    if kind == 'ddt':
        return {'y': 0 if x == 0 or x >= 3 else 2 if x < 1 else -2}
    if kind == 'functions':
        return {'y': min(.9, max(0, u)), 'z': 1-u if u > .5 else u}
    if kind == 'array_events':
        seed = 40 if .25 <= x < .5 else 0
        return {'y': 2*seed+1, 'qzero': seed, 'qone': seed+1, 'qlast': seed+1}
    raise ValueError('unknown independent oracle: '+kind)


def assess(card, rows):
    required = ['time', *card['inputs'], *card['outputs']]
    result = {'formal_qualification': False, 'status': 'observation_invalid',
              'output_target_V': card['output_target_V'], 'input_target_V': card['input_target_V']}
    if len(rows) < 3 or any(any(type(r.get(n)) not in (int, float) or not math.isfinite(r[n]) for n in required) for r in rows):
        return {**result, 'reason': 'missing/nonfinite observations'}
    unit, stop = card['unit_s'], card['stop_x']*card['unit_s']
    times = [r['time'] for r in rows]
    if any(b <= a for a, b in zip(times, times[1:])):
        return {**result, 'reason': 'nonincreasing time'}
    if abs(times[0]) > 32*math.ulp(stop) or abs(times[-1]-stop) > 32*math.ulp(stop):
        return {**result, 'reason': 'incomplete time extent', 'extent_s': [times[0], times[-1]]}
    gap = max(b-a for a, b in zip(times, times[1:]))
    if gap > card['grid_x']*unit*1.01:
        return {**result, 'reason': 'coverage gap', 'max_gap_s': gap}
    maxima, input_max = {n: 0. for n in card['outputs']}, {n: 0. for n in card['inputs']}
    worst, boundaries, checked = {}, [], 0
    for row in rows:
        x = row['time']/unit
        for n, points in card['inputs'].items():
            input_max[n] = max(input_max[n], abs(row[n]-pwl(points, x)))
        values = expected(card, x)
        if any(abs(x-c) <= card['exclusion_radius_x'] for c in card['excluded_centers_x']):
            boundaries.append({'observed': row, 'nominal': values})
            continue
        checked += 1
        for n, value in values.items():
            error = abs(row[n]-value)
            if error > maxima[n]:
                maxima[n] = error
                worst[n] = {'time_s': row['time'], 'actual_V': row[n], 'expected_V': value}
    status = ('observation_invalid' if max(input_max.values(), default=0) > card['input_target_V'] or not checked else
              'observed_difference' if max(maxima.values(), default=0) > card['output_target_V'] else 'observed_within_target')
    return {**result, 'status': status, 'row_count': len(rows), 'checked_rows': checked,
            'max_gap_s': gap, 'max_error_V': maxima, 'input_max_error_V': input_max,
            'worst': worst, 'boundary_rows': boundaries,
            'boundary_status': 'not_graded' if boundaries else 'not_applicable'}

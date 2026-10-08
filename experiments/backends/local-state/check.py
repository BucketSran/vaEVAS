"""Frozen local-state formulas and native-stage checks; no interpolation."""
from decimal import Decimal
from fractions import Fraction as Q
import re

ABSOLUTE = 1e-7
RELATIVE = 1e-5
EVENT = Q(1, 2)
WINDOW = (EVENT, EVENT + Q(1, 10**12))
TIMES = tuple(Q(i, 8) for i in range(9))
NODES = ('u', 'y1', 'z1', 'h1', 'q1', 'y2', 'z2', 'h2', 'q2', 'yc', 'qc')
OBSERVERS = ('q1', 'q2', 'qc')


def rational(token):
    value = Decimal(str(token))
    if not value.is_finite():
        raise ValueError('nonfinite native token')
    return Q(value)


def parse_psf(text):
    lines = [line.strip() for line in text.splitlines()]
    if lines.count('VALUE') != 1 or lines[-1] != 'END':
        raise ValueError('missing/truncated PSF VALUE section')
    rows = []
    for line in lines[lines.index('VALUE')+1:-1]:
        match = re.fullmatch(r'"([^"\n]+)"\s+(\S+)', line)
        if not match:
            raise ValueError('unsupported VALUE line: ' + line)
        name, token = match.groups()
        rational(token)
        if name == 'time':
            rows.append({'time': token, 'voltages': {}})
        elif not rows or name in rows[-1]['voltages']:
            raise ValueError('duplicate signal or missing time')
        else:
            rows[-1]['voltages'][name] = token
    if not rows or any(set(NODES)-set(row['voltages']) for row in rows):
        raise ValueError('missing saved node')
    times = [rational(row['time']) for row in rows]
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError('native time order decreases')
    return rows


def expected(time, phase):
    # The supplemental terminal query holds the original PWL endpoint at 1.
    u = min(time, Q(1))
    q1, q2, qc = Q(1+phase), Q(3+phase), Q(1)+Q(phase, 2)
    return dict(u=u, q1=q1, q2=q2, qc=qc,
                y1=u+q1, z1=3*u+q1, h1=3*time+Q(1,4)+q1,
                y2=2*u+q2, z2=6*u+q2, h2=3*time+Q(1,4)+q2, yc=u+qc)


def error(value, exact):
    difference = abs(float(rational(value)-exact))
    limit = ABSOLUTE + RELATIVE*abs(float(exact))
    return difference, limit, difference/limit


def phase_of(row):
    phases = [phase for phase in (0, 1)
              if all(error(row['voltages'][node], expected(Q(0), phase)[node])[2] <= 1
                     for node in OBSERVERS)]
    return phases[0] if len(phases) == 1 else None


def assess(rows):
    times = [rational(row['time']) for row in rows]
    phases = [phase_of(row) for row in rows]
    failures, maximum = [], {'ratio': 0., 'absolute': 0., 'row': None, 'node': None}
    for index, (row, time, phase) in enumerate(zip(rows, times, phases)):
        if phase is None:
            failures.append(dict(row=index, reason='observers do not share a permitted stage'))
            continue
        if not WINDOW[0] <= time <= WINDOW[1] and phase != int(time >= EVENT):
            failures.append(dict(row=index, reason='state stage outside frozen event window'))
        for node, exact in expected(time, phase).items():
            difference, limit, ratio = error(row['voltages'][node], exact)
            if ratio > maximum['ratio']:
                maximum = dict(ratio=ratio, absolute=difference, row=index, node=node)
            if ratio > 1:
                failures.append(dict(row=index, node=node, error=difference, limit=limit,
                                     reason='independent formula mismatch'))
    transitions = [i for i in range(1, len(phases)) if phases[i] != phases[i-1]]
    valid_transition = (len(transitions) == 1 and phases[0] == 0 and phases[-1] == 1
                        and all(phase in (0, 1) for phase in phases))
    bracket = None
    if valid_transition:
        i = transitions[0]
        compatible = max(times[i-1], WINDOW[0]) <= min(times[i], WINDOW[1])
        bracket = dict(before_row=i-1, after_row=i,
                       before_token=rows[i-1]['time'], after_token=rows[i]['time'],
                       intersects_frozen_window=compatible,
                       limit='Native change bracket; not a callback-time certificate.')
        if not compatible:
            failures.append(dict(reason='event bracket outside frozen window'))
    else:
        failures.append(dict(reason='missing/nonmonotone/multiple native stage transitions'))
    points = []
    for wanted in TIMES:
        exact_rows = [i for i, time in enumerate(times) if time == wanted]
        nearest = min(range(len(times)), key=lambda i: abs(times[i]-wanted))
        left = [i for i, time in enumerate(times) if time < wanted]
        right = [i for i, time in enumerate(times) if time > wanted]
        points.append(dict(requested=str(float(wanted)), exact_decimal_rows=exact_rows,
                           nearest_row=nearest, nearest_time_token=rows[nearest]['time'],
                           decimal_offset=str(Decimal(rows[nearest]['time'])-Decimal(str(float(wanted)))),
                           nearest_stage=phases[nearest],
                           left_row=left[-1] if left else None, right_row=right[0] if right else None,
                           interpolated=False))
    initial = times[0] == 0 and phases[0] == 0
    exact_stop = any(time == 1 for time in times)
    return dict(rows=len(rows), checked_values=len(rows)*len(NODES),
                formula_and_stage_status='P' if not failures else 'F', failures=failures,
                max_error=maximum, phase_counts={str(p): phases.count(p) for p in (0,1,None)},
                shared_observer_stage=all(phase is not None for phase in phases),
                event_bracket=bracket, required_points=points,
                initial_status='P' if initial else 'I', exact_stop_status='P' if exact_stop else 'I',
                exact_required_point_count=sum(bool(p['exact_decimal_rows']) for p in points),
                required_point_status='P' if all(p['exact_decimal_rows'] for p in points) else 'I',
                strict_observation_status='P' if initial and exact_stop and all(p['exact_decimal_rows'] for p in points) else 'I')


def pair(native, candidate):
    by_time = {rational(row['time']): row for row in candidate}
    phases, failures, maximum, compared = [], [], 0., 0
    for index, row in enumerate(native):
        time = rational(row['time'])
        # Candidate times are binary64 and PSF times are decimal export tokens.
        actual = next((r for t, r in by_time.items() if float(t) == float(time)), None)
        if actual is None:
            failures.append(dict(row=index, reason='missing candidate native-time query'))
            continue
        left, right = phase_of(row), phase_of(actual)
        if left is None or right is None:
            failures.append(dict(row=index, reason='unqualified observer stage in pair'))
            continue
        if left != right:
            phases.append(dict(row=index, native_phase=left, candidate_phase=right,
                               raw_time=row['time'], inside_frozen_window=WINDOW[0] <= time <= WINDOW[1]))
            continue
        for node in NODES:
            a, b = rational(row['voltages'][node]), rational(actual['voltages'][node])
            limit = ABSOLUTE + RELATIVE*abs(float(expected(time, left)[node]))
            ratio = float(abs(a-b))/limit
            maximum = max(maximum, ratio)
            compared += 1
            if ratio > 1:
                failures.append(dict(row=index, node=node, reason='same-stage pair voltage mismatch', ratio=ratio))
    return dict(queried_native_rows=len(native), same_stage_values_compared=compared,
                maximum_pair_ratio=maximum, phase_differences=phases, failures=failures,
                voltage_status='P' if not failures else 'F',
                phase_status='P' if not phases else 'I')

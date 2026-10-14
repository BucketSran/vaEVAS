"""Independent answers and one strict checker for bounded regular event chains.

This is not an interrupted-transition simulator. Each regular target lasts exactly
one rise/fall time. Integral answers use rational polygon areas. Filter answers
sum the continuous-time convolution over those known affine source segments;
there is no recurrence over EVAS states or accepted steps.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
from functools import lru_cache
import math

BUDGET = Decimal('1e-12')


def decimal(value):
    if isinstance(value, Fraction):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal(value)


def held(index, amplitude):
    return amplitude if index >= 2 and index % 2 == 0 else Fraction(0)


def regular_answers(times, period, amplitude, precision=80):
    """Answers for h=sampled alternating 0/A, s=transition(h,0,T,T).

    f solves tau*f'+f=s, tau=T/2, f(0)=0. On a segment [a,b], s=u+g*(t-a),
    its contribution to f(t) is
    (u+g*(b-a-tau))*exp(-(t-b)/tau) + (-u+g*tau)*exp(-(t-a)/tau).
    All constants are exact rationals of the submitted binary64 values.
    """
    period, amplitude = Fraction(period), Fraction(amplitude)
    assert period > 0 and amplitude > 0
    tau = period / 2
    with localcontext() as context:
        context.prec = precision

        @lru_cache(None)
        def decay(x):
            return (-decimal(x)).exp()

        answers = []
        for time in map(Fraction, times):
            assert time >= 0
            index = int(time // period)
            s = held(index - 1, amplitude)
            s += (held(index, amplitude) - s) * (time - index * period) / period
            integral, filtered = Fraction(0), Decimal(0)
            for k in range(index + 1):
                a, b = k * period, min(time, (k + 1) * period)
                if a == b:
                    continue
                u = held(k - 1, amplitude)
                slope = (held(k, amplitude) - u) / period
                duration = b - a
                integral += u * duration + slope * duration**2 / 2
                filtered += decimal(u + slope * (duration - tau)) * decay((time - b) / tau)
                filtered += decimal(-u + slope * tau) * decay((time - a) / tau)
            answers.append(dict(s=s, y=integral, f=filtered, h=held(index, amplitude)))
        return answers


def pwl_area(points, time):
    """Exact area under the submitted linear source, up to time."""
    time = Fraction(time)
    points = [tuple(map(Fraction, point)) for point in points]
    assert points[0][0] <= time <= points[-1][0]
    total = Fraction(0)
    for (a, u), (b, v) in zip(points, points[1:]):
        end = min(time, b)
        if end > a:
            right = u + (v - u) * (end - a) / (b - a)
            total += (u + right) * (end - a) / 2
    return total


def check_result(result, times, answers, scales, events):
    """Check the full query identity before values, then exact event sequence.

    events is [(time, event_id, complete_after_state), ...]. Every compared node
    uses the unchanged error/scale <= 1e-12 requirement. Non-finite data, omitted
    rows and malformed rows fail before zip can hide them.
    """
    assert times and len(times) == len(answers), 'oracle shape'
    assert len(result['solutions']) == len(times), 'query count'
    assert result['transient']['times'] == list(times), 'query times'
    names = result['nodes']
    assert len(set(names)) == len(names), 'duplicate node'
    index = {name: names.index(name) for name in scales}
    worst = {name: Decimal(0) for name in scales}
    with localcontext() as context:
        context.prec = 80
        for row, expected in zip(result['solutions'], answers):
            assert set(expected) == set(scales), 'oracle nodes'
            assert len(row['voltages']) == len(names), 'voltage shape'
            assert all(math.isfinite(v) for v in row['voltages']), 'nonfinite voltage'
            assert math.isfinite(row['max_residual_ratio']) and 0 <= row['max_residual_ratio'] <= 1, 'residual'
            for name, scale in scales.items():
                assert scale > 0, 'scale'
                error = abs(Decimal(row['voltages'][index[name]]) - decimal(expected[name]))
                worst[name] = max(worst[name], error / decimal(scale))
                assert worst[name] <= BUDGET, f'{name} normalized error {worst[name]}'
    actual = [(Fraction(e['time']), e['event'], tuple(map(Fraction, e['after'])))
              for e in result['transient']['events']]
    assert actual == events, 'event sequence/state'
    return worst

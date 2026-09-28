"""Check v2 draft mathematics only; no VA compilation or simulator execution.

Fractions check PWL roots, state tables and polynomial integrals exactly.
The low-pass closed form is cross-checked against numerical convolution.
This is not a waveform checker and does not qualify the proposed observations.
"""
from fractions import Fraction as F
import json
import math
from pathlib import Path


def fraction(value):
    return F(str(value))


def held_at(time, initial, sample_times, value, reset_intervals):
    """Independent nominal state recurrence; intervals never race with clocks."""
    events = [(t, 'sample') for t in sample_times]
    events += [(a, 'reset') for a, _ in reset_intervals]
    state = initial
    for t, kind in sorted(events):
        if t > time:
            break
        if kind == 'reset' or any(a <= t <= b for a, b in reset_intervals):
            state = initial
        else:
            state = value(t)
    return state


def simpson(function, a, b, intervals=1000):
    if b <= a:
        return 0.0
    h = (b-a)/intervals
    total = function(a)+function(b)
    total += sum((4 if i % 2 else 2)*function(a+i*h)
                 for i in range(1, intervals))
    return total*h/3


def lowpass(x):
    def ramp(z):
        return 0 if z <= 0 else z + math.expm1(-2*z)/2
    return .6*(ramp(x-1)-ramp(x-2))


def main():
    doc = (Path(__file__).parent/'NEXT_CASE_CARDS.md').read_text()
    results = {}

    # Each E1 root follows from the affine segment endpoints, not a time grid.
    widths = []
    for shift, slope in [(F(0), F(2)), (F(37, 10**6), F(2)), (F(0), F(1, 2))]:
        for index, nominal in enumerate([F(1, 2), F(3, 2), F(5, 2)]):
            root = nominal+shift
            a, b = root-F(1, 10)/slope, root+F(1, 10)/slope
            left, right = (F(2, 5), F(3, 5)) if index != 1 else (F(3, 5), F(2, 5))
            assert a+(F(1, 2)-left)*(b-a)/(right-left) == root
        widths.append(min(F(1, 10000), F(1, 10000)/slope))
    assert widths == [F(1, 20000), F(1, 20000), F(1, 10000)]
    roots = [F(1, 2), F(3, 2), F(5, 2)]
    counts = [(sum(t > roots[i] for i in (0, 2)), int(t > roots[1]))
              for t in map(fraction, [.25, .75, 1.75, 2.75])]
    assert counts == [(0, 0), (1, 0), (1, 1), (2, 1)]
    results['E1'] = {'location_width_over_T': [float(w) for w in widths], 'counts': counts}

    clocks = list(map(fraction, [.5, 1.5, 2.5, 3.5]))
    data_a = lambda x: F(4, 5)-x/10
    reset_a = [(F(43, 20), F(57, 20))]
    observations = list(map(fraction, [.25, .75, 1.75, 2.75, 3.05, 3.75]))
    for name, resets, expected in [
        ('low', reset_a, [.1, .75, .65, .1, .1, .45]),
        ('clock-high', reset_a, [.1, .75, .65, .1, .1, .45]),
        ('reset-high', [(F(0), F(23, 20))]+reset_a, [.1, .1, .65, .1, .1, .45]),
    ]:
        actual = [held_at(t, F(1, 10), clocks, data_a, resets) for t in observations]
        assert actual == list(map(fraction, expected))
        results['E2-'+name] = list(map(float, actual))
    assert held_at(F(13, 10), F(1, 10), clocks, data_a,
                   [(F(0), F(23, 20))]+reset_a) == F(1, 10)

    clocks_b = list(map(fraction, [.75, 1.75, 2.75, 3.75]))
    data_b = lambda x: F(1, 5)+x/10
    values_b = [held_at(t, F(3, 10), clocks_b, data_b, [])
                for t in map(fraction, [1, 2, 3, 3.95])]
    assert values_b == list(map(fraction, [.275, .375, .475, .575]))
    assert held_at(F(11, 4), F(1, 10), clocks, data_a, reset_a) == F(1, 10)
    assert held_at(F(11, 4), F(1, 10), clocks, data_a, []) == F(11, 20)
    results['C1'] = {'B_values': list(map(float, values_b)), 'A_reset_contrast': [.1, .55]}

    lowpass_values = []
    for x, printed in [(1.5, '0.1103638324'), (2.5, '0.5045722882'), (3.5, '0.5870852636')]:
        assert printed in doc and abs(lowpass(x)-float(printed)) < 5e-11
        # Impulse-response convolution, split at input breakpoints.
        integrand = lambda s: 2*math.exp(-2*(x-s))*.6*min(1, max(0, s-1))
        knots = sorted({0., min(1., x), min(2., x), x})
        integral = sum(simpson(integrand, a, b) for a, b in zip(knots, knots[1:]))
        assert abs(integral-lowpass(x)) < 1e-11
        lowpass_values.append(lowpass(x))
    stale_error = lowpass(1.5)-lowpass(1.49)
    assert stale_error > .0035  # Above the proposed 1 mV goal plus observation budget.
    results['C2'] = {'anchors_v': lowpass_values, 'stale_0_01T_error_v': stale_error}

    area = lambda x: x/5-x*x/20
    reset_release = F(5, 2)
    times = list(map(F, [0, 1, 2, 3, 4]))
    free = [F(1, 4)+area(x) for x in times]
    reset = [F(1, 4)+(area(x) if x < F(3, 2) else
                      0 if x <= reset_release else area(x)-area(reset_release)) for x in times]
    assert free == list(map(fraction, [.25, .4, .45, .4, .25]))
    assert reset == list(map(fraction, [.25, .4, .25, .2125, .0625]))
    # Independent trapezoid area is exact for the affine input.
    for a, b in [(F(0), F(4)), (reset_release, F(3)), (reset_release, F(4))]:
        assert (F(1, 5)-a/10+F(1, 5)-b/10)*(b-a)/2 == area(b)-area(a)
    results['D1'] = {'free': list(map(float, free)), 'reset': list(map(float, reset))}

    for alpha, expected in [(F(0), [.125, .625, 1.125, 1.625, 2.125]),
                            (F(1, 4), [.125, .75, 1.625, 2.75, 4.125])]:
        phase = [F(1, 8)+x/2+alpha*x*x/2 for x in times]
        assert phase == list(map(fraction, expected))
        assert all(F(1, 8)+(F(1, 2)+F(1, 2)+alpha*x)*x/2 == p
                   for x, p in zip(times, phase))
        results['D2-'+str(alpha)] = list(map(float, phase))
    voltage_bound = 2*math.pi*.8*1e-4
    assert voltage_bound < .00051
    assert F(1, 8)+(F(1, 2)+F(1, 4)*4)*4 == F(49, 8)
    results['D2-voltage-bound-v'] = voltage_bound

    u = list(map(fraction, [0, .4, .4, -.2, -.2]))
    v = list(map(fraction, [-.2, -.2, .3, .3, -.1]))
    for name, gains, expected in [
        ('default', [1.5, -.5, .125], [.225, .825, .575, -.325, -.125]),
        ('override', [-.5, 2, -.25], [-.65, -.85, .15, .45, -.35]),
    ]:
        g1, g2, bias = map(fraction, gains)
        actual = [g1*a+g2*b+bias for a, b in zip(u, v)]
        assert actual == list(map(fraction, expected))
        results['S1-'+name] = list(map(float, actual))

    # Exact interval intersection for the deliberately inconsistent history.
    epsilon = F(1, 100)
    intervals = [(t-y-epsilon, t-y+epsilon)
                 for t, y in [(F(1, 4), F(1, 4)), (F(3, 4), F(13, 20))]]
    assert max(F(0), *(a for a, _ in intervals)) > min(F(1, 10), *(b for _, b in intervals))
    witness = F(1, 20)
    assert all(abs(y-(t-witness)) <= epsilon
               for t, y in [(F(1, 4), F(1, 5)), (F(3, 4), F(7, 10))])
    def verdict(error):
        bound, target = F(2, 10000), F(1, 1000)
        return 'P' if error+bound <= target else 'F' if error-bound > target else 'I'
    assert [verdict(F(n, 10000)) for n in [7, 9, 13]] == ['P', 'I', 'F']
    results['method_controls'] = 'common-history contradiction and legal witness; P/I/F margins'
    print(json.dumps({'scope': 'design mathematics only; not simulator qualification', 'checks': results}, indent=2))


if __name__ == '__main__':
    main()

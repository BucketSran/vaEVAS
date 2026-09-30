"""Exact-rational calibration for DYNAMICS_CONTRACTS.md; no EVAS imports/runs.

All fixtures and closed forms are derived here from integrals, not simulator
outputs. Passing this file establishes mathematics/calibration only. In
particular the retry identities below do not exercise a simulator's rollback.
"""
from fractions import Fraction as F
import unittest


def segment(z0, u0, slope, h):
    """Integral of u0 + slope*s on 0 <= s <= h, with exact inputs."""
    z0, u0, slope, h = map(F, (z0, u0, slope, h))
    if h < 0:
        raise ValueError("elapsed time must be nonnegative")
    return z0+u0*h+slope*h*h/2


def pwl_integral(knots, z0, time):
    """Exact trapezoid areas, split at semantic knots, no extrapolation.

    Deliberately uses endpoint areas rather than the segment polynomial. The
    function accepts rationals (or exact binary64 values via Fraction(float));
    it does not round nominal decimal stimuli into a simulator request.
    """
    points = tuple((F(t), F(u)) for t, u in knots)
    time, total = F(time), F(z0)
    if (len(points) < 2 or any(b[0] <= a[0] for a, b in zip(points, points[1:]))
            or not points[0][0] <= time <= points[-1][0]):
        raise ValueError("need increasing knots and a query inside their domain")
    for (a, ua), (b, ub) in zip(points, points[1:]):
        if time <= a:
            break
        end = min(time, b)
        at_end = ua+(ub-ua)*(end-a)/(b-a)
        total += (ua+at_end)*(end-a)/2
    return total


MULTI = ((0, 0), (1, 2), (3, -2), (4, -2), (5, 0))
MULTI_ANCHORS = ((F(0), F(3, 4)), (F(1, 2), F(1)), (F(1), F(7, 4)),
                 (F(2), F(11, 4)), (F(3), F(7, 4)), (F(4), F(-1, 4)),
                 (F(5), F(-5, 4)))


def verdict(error, uncertainty, target):
    """Observation margin only; the caller must justify uncertainty separately."""
    if min(error, uncertainty, target) < 0:
        raise ValueError("margins must be nonnegative")
    return "P" if error+uncertainty <= target else "F" if error-uncertainty > target else "I"


class DynamicsMath(unittest.TestCase):
    def test_constant_and_signed_ramps_with_nonzero_initial_values(self):
        cases = (
            (F(5, 4), F(-3, 2), F(0), (0, F(1, 2), 2), (F(5, 4), F(1, 2), F(-7, 4))),
            (F(1, 4), F(-1), F(2), (0, F(1, 2), 1, 2), (F(1, 4), F(0), F(1, 4), F(9, 4))),
            (F(-1, 2), F(2), F(-3, 2), (0, 1, 2, 4), (F(-1, 2), F(3, 4), F(1, 2), F(-9, 2))),
        )
        for z0, u0, slope, times, answers in cases:
            for t, answer in zip(times, answers):
                with self.subTest(z0=z0, slope=slope, time=t):
                    self.assertEqual(segment(z0, u0, slope, t), answer)
                    self.assertEqual(pwl_integral(((0, u0), (4, u0+4*slope)), z0, t), answer)

    def test_multisegment_continuity_and_interior_quadratic_values(self):
        for t, answer in MULTI_ANCHORS:
            self.assertEqual(pwl_integral(MULTI, F(3, 4), t), answer)
        z = F(3, 4)
        for (a, ua), (b, ub) in zip(MULTI, MULTI[1:]):
            for t in (F(a), F(a+b, 2), F(b)):
                self.assertEqual(segment(z, ua, F(ub-ua, b-a), t-a),
                                 pwl_integral(MULTI, F(3, 4), t))
            z = segment(z, ua, F(ub-ua, b-a), b-a)

    def test_two_call_sites_and_instances_have_separate_initial_conditions(self):
        for t in (F(0), F(1, 2), F(1), F(2)):
            first = pwl_integral(((0, 0), (2, 2)), F(1, 4), t)
            second = pwl_integral(((0, 2), (2, 0)), F(-1, 2), t)
            other_instance = pwl_integral(((0, 0), (2, -4)), F(3, 4), t)
            self.assertEqual(first, F(1, 4)+t*t/2)
            self.assertEqual(second, F(-1, 2)+2*t-t*t/2)
            self.assertEqual(first+second, F(-1, 4)+2*t)
            self.assertEqual(other_instance, F(3, 4)-t*t)
        self.assertNotEqual(first, second)  # Equal-target-slot or shared-instance histories fail.
        self.assertNotEqual(first, other_instance)

    def test_time_and_amplitude_scales_and_local_origin(self):
        for scale in (F(1, 10**9), F(1, 2**20), F(1), F(2**20)):
            for amplitude in (F(1), F(-3, 2)):
                knots = tuple((scale*t, amplitude*u/scale) for t, u in MULTI)
                for t, answer in MULTI_ANCHORS:
                    self.assertEqual(pwl_integral(knots, amplitude*F(3, 4), scale*t), amplitude*answer)
        origin = F(2**54)
        shifted = tuple((origin+t, u) for t, u in MULTI)
        for t, answer in MULTI_ANCHORS:
            self.assertEqual(pwl_integral(shifted, F(3, 4), origin+t), answer)

    def test_partition_observation_and_retry_identities_only(self):
        # This is algebra, not a mock engine and not a rollback test.
        z0, u0, slope = F(1, 4), F(-1), F(2)
        target = segment(z0, u0, slope, 2)
        for split in (F(0), F(1, 4), F(1), F(7, 4), F(2)):
            accepted_at_split = segment(z0, u0, slope, split)
            self.assertEqual(segment(accepted_at_split, u0+slope*split, slope, 2-split), target)
        discarded = segment(z0, u0, slope, F(1, 2))
        self.assertEqual(discarded, F(0))
        self.assertEqual(segment(z0, u0, slope, F(1, 2)), discarded)
        self.assertNotEqual(segment(discarded, u0, slope, F(1, 2)), discarded)
        # Same trial time and same accepted endpoint input, different future
        # slope: a time-only result cache is wrong without rewriting the past.
        self.assertEqual(segment(z0, u0, 8, 1), F(13, 4))
        self.assertEqual(segment(z0, u0, slope, 1), F(1, 4))
        refined = tuple(sorted((*MULTI, (F(1, 2), F(1)), (F(2), F(0)))))
        for t, answer in MULTI_ANCHORS:
            self.assertEqual(pwl_integral(refined, F(3, 4), t), answer)

    def test_cancelled_area_does_not_erase_initial_value_or_error(self):
        self.assertEqual(pwl_integral(((0, 1), (2, -1)), F(7, 4), 2), F(7, 4))
        # A uniform integrand error eps still integrates to 2*eps even when
        # the nominal signed area is zero; current output/residual cannot bound it.
        eps = F(1, 1000)
        actual = pwl_integral(((0, 1+eps), (2, -1+eps)), F(7, 4), 2)
        self.assertEqual(actual-F(7, 4), 2*eps)

    def test_wrong_integrals_and_linear_output_interpolation_are_detected(self):
        # u=t, z(0)=0; z(1/2)=1/8. Left/right rectangles, a missing 1/2,
        # and interpolation of z(0),z(1) are deliberately incorrect references.
        answer, tolerance = F(1, 8), F(1, 10**12)
        self.assertEqual(pwl_integral(((0, 0), (1, 1)), 0, F(1, 2)), answer)
        for wrong in (F(0), F(1, 4), F(1, 2)):
            self.assertEqual(verdict(abs(wrong-answer), F(0), tolerance), "F")
        self.assertEqual(verdict(F(0), F(0), tolerance), "P")

    def test_uncertainty_margins_preserve_inconclusive_results(self):
        target, bound = F(1, 1000), F(1, 5000)
        self.assertEqual([verdict(F(k, 10000), bound, target) for k in (7, 9, 13)], ["P", "I", "F"])
        self.assertEqual(verdict(target-bound, bound, target), "P")
        self.assertEqual(verdict(target+bound, bound, target), "I")

    def test_reference_domain_is_explicit(self):
        for knots, time in ((((0, 0),), 0), (((0, 0), (0, 1)), 0),
                            (((1, 1), (0, 0)), 0), (((0, 0), (1, 1)), -1),
                            (((0, 0), (1, 1)), 2)):
            with self.assertRaises(ValueError):
                pwl_integral(knots, 0, time)
        with self.assertRaises(ValueError):
            segment(0, 0, 0, -1)


if __name__ == "__main__":
    print("Pure mathematics/calibration only; no simulator execution or rollback verification.", flush=True)
    unittest.main(verbosity=2)

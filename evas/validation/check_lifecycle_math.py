"""Independent lifecycle answers and calibration; no simulator imports.

Time x is normalized by T=2**-20 seconds. The binary64 stimuli, timer
constants and rate 1/T therefore have an exact rational interpretation.
These checks establish mathematics, not runtime rollback or qualification.
"""
from fractions import Fraction as Q
import math
import unittest


UNIT = 2.0**-20


def crossing_window(start, end, stop, ttol, etol):
    start, end, stop, ttol, etol = map(Q, (start, end, stop, ttol, etol))
    slope = (end-start)/stop
    if not slope > 0 or not start < Q(1, 2) < end:
        raise ValueError("need one increasing interior crossing")
    root = (Q(1, 2)-start)/slope
    return root, root+min(ttol, etol/slope)


def integral_after_event(x, event, sampled, *, reset=False, release=None):
    """z'=1, z(0)=1; then sampled slope, optionally reset/hold/release."""
    x, event, sampled = map(Q, (x, event, sampled))
    if x < event:
        return 1+x
    if not reset:
        return 1+event+sampled*(x-event)
    if release is None or x <= Q(release):
        return Q(1)
    return 1+sampled*(x-Q(release))


def filter_segment(z0, y0, slope, elapsed):
    """Solution of y'+y=z0+slope*h, with given physical y0."""
    return z0+slope*elapsed+(y0-z0)*math.exp(-elapsed)-slope*(-math.expm1(-elapsed))


def filter_after_event(x, event, sampled, *, reset=False, release=None):
    x, event, sampled = map(float, (x, event, sampled))
    if x < event:
        return x+math.exp(-x)
    y0 = event+math.exp(-event)
    if not reset:
        return filter_segment(1+event, y0, sampled, x-event)
    if release is None or x <= release:
        return filter_segment(1, y0, 0, x-event)
    at_release = filter_segment(1, y0, 0, release-event)
    return filter_segment(1, at_release, sampled, x-release)


def common_event_interval(stamp, held, allowance):
    """clock=x, data=.2+.6*x: one x must explain BOTH observations."""
    stamp, held, allowance = map(Q, (stamp, held, allowance))
    a, slope = Q(.2), Q(.8)-Q(.2)
    lo = max(stamp-allowance, (held-allowance-a)/slope)
    hi = min(stamp+allowance, (held+allowance-a)/slope)
    return (lo, hi) if lo <= hi else None


class LifecycleMathematics(unittest.TestCase):
    def test_cross_trigger_can_follow_the_root_and_change_a_strict_condition(self):
        root, end = crossing_window(.2, .8, UNIT, UNIT/128, 1/128)
        self.assertLess(root, Q(UNIT)/2)
        self.assertEqual(root, (Q(.5)-Q(.2))*Q(UNIT)/(Q(.8)-Q(.2)))
        for time in (root, (root+end)/2, end):
            guard = Q(.2)+(Q(.8)-Q(.2))*time/Q(UNIT)-Q(.5)
            self.assertLessEqual(time-root, Q(UNIT/128))
            self.assertLessEqual(abs(guard), Q(1/128))
            self.assertEqual(guard > 0, time > root)

    def test_zero_reset_preserves_state_and_uses_a_new_future_slope(self):
        e = Q(1, 2)
        self.assertEqual(integral_after_event(e, e, 1+e), 1+e)
        self.assertEqual(integral_after_event(1, e, 1+e), Q(9, 4))
        # Reinitializing to IC, or using a post-event value as the event sample,
        # would fail these independently derived anchors.
        self.assertNotEqual(integral_after_event(1, e, 1+e), 1+(1+e)*(1-e))

    def test_reset_hold_release_distinguishes_pre_and_post_reset_sampling(self):
        e, release = Q(1, 2), Q(3, 4)
        for sample, final in [(Q(1), Q(5, 4)), (Q(3, 2), Q(11, 8))]:
            self.assertEqual(integral_after_event(e, e, sample, reset=True), 1)
            self.assertEqual(integral_after_event(release, e, sample, reset=True), 1)
            self.assertEqual(integral_after_event(1, e, sample, reset=True, release=release), final)
        # Joint post-reset closure q=z+, rst=1 forces z+=IC=1 and q=1.
        # This algebra does not, on its own, mandate that VA samples z+.
        self.assertEqual(integral_after_event(1, e, 1, reset=True, release=release), Q(5, 4))

    def test_filter_restart_keeps_physical_history_instead_of_repeating_dc(self):
        e = .5
        old_y = e+math.exp(-e)
        self.assertAlmostEqual(filter_after_event(e, e, 1, reset=True), old_y, places=15)
        self.assertNotAlmostEqual(old_y, 1, places=3)
        self.assertAlmostEqual(filter_after_event(.75, e, 1, reset=True),
                               1+(old_y-1)*math.exp(-.25), places=15)
        # Two independent forms of the linear segment solution agree.
        self.assertAlmostEqual(filter_segment(1+e, old_y, 1+e, .5),
                               (1+e)*.5+old_y*math.exp(-.5), places=15)

    def test_cold_initialization_and_warm_nonlinear_ivp_have_distinct_obligations(self):
        # Cold z(0)=3, filter y'+y=z => y(0)=3 and y=2+x+exp(-x).
        for x in [0, .25, .5, 1]:
            self.assertAlmostEqual(filter_segment(3, 3, 1, x), 2+x+math.exp(-x), places=15)
        # After e=1/4, known y(e)=1 and y'=(y-2)^2/4.
        for h in [Q(0), Q(1, 8), Q(1, 4), Q(3, 4)]:
            y = 2-4/(4+h)
            derivative = 4/(4+h)**2
            self.assertEqual(derivative, (y-2)**2/4)
        # The cold equation y=.25*y^2+1 only has y=2; it cannot reset
        # the warm physical initial state y=1 without changing the problem.
        self.assertNotEqual(Q(1), Q(1, 4)*Q(1)**2+1)

    def test_one_event_history_rejects_individually_plausible_mixed_samples(self):
        a = Q(1, 10**8)
        good = common_event_interval(Q(1, 2), (Q(.2)+Q(.8))/2, a)
        self.assertIsNotNone(good)
        self.assertLessEqual(good[0], Q(1, 2))
        self.assertLessEqual(Q(1, 2), good[1])
        # Both times fit the loose cross window, but cannot be one callback.
        self.assertIsNone(common_event_interval(Q(1, 2), Q(.2)+(Q(.8)-Q(.2))*Q(501, 1000), a))

    def test_small_algebraic_residual_does_not_bound_wrong_history(self):
        actual, wrong, epsilon = Q(5, 4), Q(11, 8), Q(1, 10**9)
        self.assertEqual(wrong-wrong, 0)  # Solving v=wrong has zero residual.
        self.assertGreater(abs(wrong-actual), epsilon)


if __name__ == "__main__":
    unittest.main()

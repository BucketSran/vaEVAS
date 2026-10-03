"""Independent accept/reject calibration for the rational diagnostic inspector."""
from fractions import Fraction as Q
import math
import unittest

from analog_boundaries import cases, inspect


class RationalBoundaryCalibration(unittest.TestCase):
    controls = dict(vabstol=1e-9, reltol=1e-10)

    def test_exact_anchors(self):
        by_id = {c["id"]: c for c in cases()}
        self.assertEqual(len(by_id), 6)
        for name, expected in [("knot-equality", Q(12)), ("large-cancellation", Q(1)),
                               ("pwl-threshold", Q(1)), ("gain-plain", Q(10**16, 3*2**52))]:
            data = by_id[name]["expected"]
            self.assertEqual(Q(data["numerator"], data["denominator"]), expected)

    def test_accept_exact_and_small_perturbation(self):
        for value in [1., math.nextafter(1., math.inf)]:
            self.assertEqual(inspect(value, Q(1), self.controls)["status"], "within_rational_target")

    def test_reject_branch_flip_and_lost_sub_ulp_input(self):
        for reference in [Q(1), Q(10**16, 3*2**52)]:
            self.assertEqual(inspect(0., reference, self.controls)["status"], "outside_rational_target")

    def test_nonfinite_is_invalid(self):
        for value in [math.nan, math.inf, -math.inf]:
            self.assertEqual(inspect(value, Q(0), self.controls)["status"], "observation_invalid")

    def test_exact_budget_boundary(self):
        controls = dict(vabstol=.125, reltol=0.)
        self.assertEqual(inspect(.125, Q(0), controls)["status"], "within_rational_target")
        self.assertEqual(inspect(math.nextafter(.125, math.inf), Q(0), controls)["status"], "outside_rational_target")


if __name__ == "__main__":
    unittest.main()

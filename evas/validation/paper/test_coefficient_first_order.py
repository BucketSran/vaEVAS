"""Hand calibration for the exact-binary64 coefficient reference.

Expected values come from direct integration, not from the helper under test.
This policy is not the v1 Decimal(str) replay.
"""
from decimal import Decimal, localcontext
from fractions import Fraction
import unittest

from coefficient_first_order import CoefficientFirstOrder


# y' + y = 2t, y(0) = 0 integrates to y(1) = 2/e.
# 2.718281828 < e < 2.718281829.
E_LO = Fraction("2.718281828")
E_HI = Fraction("2.718281829")
Y_LO = Fraction(2) / E_HI
Y_HI = Fraction(2) / E_LO


class CoefficientFirstOrderCalibration(unittest.TestCase):
    def test_ramp_bounds_contain_hand_integrated_answer_and_reject_lagless_endpoint(self):
        model = CoefficientFirstOrder([(0.0, 0.0), (1.0, 1.0)], b0=2.0, d0=1.0, d1=1.0)
        lo, hi = model.bounds(1.0)
        self.assertLessEqual(Fraction(lo), Y_HI)
        self.assertGreaterEqual(Fraction(hi), Y_LO)
        self.assertLess(Fraction(hi) - Fraction(lo), Fraction(1, 10**12))
        self.assertLess(hi, 2.0)
        self.assertGreater(lo, 0.0)
        self.assertEqual(model.initial, "dc_equilibrium")
        self.assertEqual(model.numeric_policy, "exact_binary64_directed_interval")

    def test_constant_input_stays_at_dc_equilibrium(self):
        model = CoefficientFirstOrder([(0.0, 1.0), (1.0, 1.0)], b0=2.0, d0=1.0, d1=1.0)
        lo, hi = model.bounds(1.0)
        self.assertGreater(lo, 1.9)
        self.assertLess(hi, 2.1)
        self.assertLessEqual(Fraction(lo), Fraction(2))
        self.assertGreaterEqual(Fraction(hi), Fraction(2))

    def test_coefficient_ratio_uses_exact_binary64_not_decimal_token(self):
        model = CoefficientFirstOrder([(0.0, 0.0), (1.0, 0.0)], b0=1.0, d0=1.0, d1=0.1)
        lo, hi = model.coefficient_decimals()["tau"]
        value = Fraction(0.1)
        with localcontext() as ctx:
            ctx.prec = value.numerator.bit_length() + value.denominator.bit_length() + 5
            exact = Decimal(value.numerator) / Decimal(value.denominator)
        self.assertGreater(exact, Decimal("0.1"))
        self.assertLessEqual(lo, exact)
        self.assertGreaterEqual(hi, exact)
        self.assertGreater(lo, Decimal("0.1"))

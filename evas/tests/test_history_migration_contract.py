"""Checker calibration, not simulator success or native ln acceptance."""
GUARDS = ["LANG", "ANALOG", "TIMED-OPERATOR"]
from decimal import Decimal, localcontext
from fractions import Fraction
import math
import unittest
from history_migration_contract import (rn, input_at, selected_ln_x,
    selected_ln_oracle, strict_equal, legacy_program, source_cases)


class HistoryMigrationContract(unittest.TestCase):
    def test_fixed_c8_programs_remain_native28(self):
        self.assertEqual(len(source_cases()), 3)
        for case in source_cases():
            self.assertEqual(legacy_program(case['name'])['schema_version'], 28)

    def test_json_types_keys_and_order_are_not_ignored(self):
        for old,new in [(1,True),(1,1.0),([1,2],[2,1]),([1],[1,2]),
                        ({'a':1},{'a':1,'new':0}),({'a':1},{'b':1})]:
            with self.subTest(old=old,new=new):
                with self.assertRaises(AssertionError):strict_equal(old,new)
        strict_equal({'a':[1,2.0]}, {'a':[1,2.0]})

    def test_integer_quotient_rounding_ties_even(self):
        for sign in (-1,1):
            self.assertEqual(rn(sign*(Fraction(1)+Fraction(1,2**53))), sign*1.0)
            self.assertEqual(rn(sign*(Fraction(1)+Fraction(3,2**53))), sign*float.fromhex('0x1.0000000000002p0'))
        self.assertEqual(rn(Fraction(1,2**1075)),0.0)
        self.assertEqual(math.copysign(1,rn(-Fraction(1,2**1075))),-1)
        self.assertEqual(rn(Fraction(3,2**1075)),float.fromhex('0x0.0000000000002p-1022'))

    def test_rational_rounding_matches_independent_python_transport(self):
        for index in range(1001):
            time=Fraction(index,1000)
            exact=Fraction.from_float(.7)+(Fraction.from_float(-.3)-Fraction.from_float(.7))*time
            self.assertEqual(rn(exact),float(exact))

    def test_source_stores_do_not_become_continuous_affine_math(self):
        self.assertEqual(selected_ln_x(0),math.nextafter(.5,-math.inf))
        self.assertEqual(selected_ln_x(.5),.1)
        for t in [0,.125,.25,.375,.5,.625,.75,.875,1]:
            # Independent host-double sequence, no compiler expressions.
            sampled=float(Fraction.from_float(.7)+(Fraction.from_float(-.3)-Fraction.from_float(.7))*Fraction.from_float(t))
            x=abs(sampled-.2)
            if x<.1:x=.1
            self.assertEqual(selected_ln_x(t),x)
            self.assertEqual(input_at(t),sampled)
        with localcontext() as context:
            context.prec=100
            self.assertNotEqual(selected_ln_oracle(0),Decimal('.5').ln())
            self.assertEqual(selected_ln_oracle(0),Decimal.from_float(math.nextafter(.5,-math.inf)).ln())

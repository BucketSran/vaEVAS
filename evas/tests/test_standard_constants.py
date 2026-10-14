"""Bundled constants.vams admission, independently specified by VAMS LRM 2.4 Annex D.3.

Expected values are Decimal source strings transcribed from the standard
(PDF p407), not simulator headers or Python math module values.
"""
GUARDS = ['LANG']

import unittest
from decimal import Decimal
from math import nextafter

from evas import CompileError, Instance, compile_sources
from evas.standard_headers import STANDARD_ENVIRONMENT

# VAMS LRM 2.4 Annex D.3 mathematical constant definitions (Accellera).
# M_PI keeps the historical short literal; it rounds to the same binary64
# value as the standard's 3.14159265358979323846.
LRM_D3 = {
    'M_E': '2.7182818284590452354',
    'M_LOG2E': '1.4426950408889634074',
    'M_LOG10E': '0.43429448190325182765',
    'M_LN2': '0.69314718055994530942',
    'M_LN10': '2.30258509299404568402',
    'M_PI': '3.14159265358979323846',
    'M_TWO_PI': '6.28318530717958647693',
    'M_PI_2': '1.57079632679489661923',
    'M_PI_4': '0.78539816339744830962',
    'M_1_PI': '0.31830988618379067154',
    'M_2_PI': '0.63661977236758134308',
    'M_2_SQRTPI': '1.12837916709551257390',
    'M_SQRT2': '1.41421356237309504880',
    'M_SQRT1_2': '0.70710678118654752440',
}

BODY = 'module m(y); output y; electrical y; analog begin V(y)<+VALUE; end endmodule'
INSTANCE = Instance('dut', 'm', {'y': 'y'})


class StandardConstants(unittest.TestCase):
    def compile(self, value, prefix='`include "disciplines.vams"\n`include "constants.vams"\n', headers=None):
        return compile_sources({'dut.va': prefix + BODY.replace('VALUE', value), **(headers or {})}, [INSTANCE])

    def contributed(self, value, **kwargs):
        # A contribution V(y)<+E keeps E as the negated affine constant.
        return -self.compile(value, **kwargs).contributions[0].rhs.constant

    def assert_correctly_rounded(self, value, decimal_text):
        expected = Decimal(decimal_text)
        # The compiled binary64 value must be the nearest float to the
        # standard's decimal text; both neighbors must be strictly farther.
        neighbors = (nextafter(value, float('-inf')), value, nextafter(value, float('inf')))
        nearest = min(neighbors, key=lambda candidate: abs(Decimal(candidate) - expected))
        self.assertIs(nearest, value, f'{decimal_text}: {value!r} is not the nearest binary64 value')

    def test_explicit_include_provides_all_fourteen_lrm_constants(self):
        self.assertEqual(len(LRM_D3), 14)
        for name, text in LRM_D3.items():
            with self.subTest(macro=name):
                self.assert_correctly_rounded(self.contributed(f'`{name}'), text)
        self.assertEqual(STANDARD_ENVIRONMENT, 'evas-voltage-vams-v2')

    def test_constants_compose_in_compile_output(self):
        self.assert_correctly_rounded(self.contributed('0.5 * `M_SQRT1_2 + `M_LN2'),
                                      Decimal('0.5') * Decimal(LRM_D3['M_SQRT1_2']) + Decimal(LRM_D3['M_LN2']))
        self.assertEqual(self.contributed('`M_TWO_PI'), 2 * self.contributed('`M_PI'))

    def test_no_include_leaves_standard_macros_undefined(self):
        # The original v4-299 failure mode stays: without an explicit include,
        # M_TWO_PI is an undefined macro even though disciplines are supplied.
        for name in ('M_TWO_PI', 'M_E'):
            with self.subTest(macro=name), self.assertRaisesRegex(CompileError, r'undefined or unsupported macro'):
                self.compile(f'`{name}', prefix='`include "disciplines.vams"\n')

    def test_caller_header_overrides_the_bundled_definitions(self):
        self.assertEqual(self.contributed('`M_TWO_PI', headers={'constants.vams': '`define M_TWO_PI 3\n'}), 3)
        # A caller header is authoritative, not merged: it defines only M_E.
        self.assertEqual(self.contributed('`M_E', headers={'constants.vams': '`define M_E 0.25\n'}), 0.25)
        with self.assertRaisesRegex(CompileError, r'undefined or unsupported macro'):
            self.compile('`M_LN2', headers={'constants.vams': '`define M_E 0.25\n'})

    def test_repeated_includes_are_guarded_and_stable(self):
        prefix = '`include "disciplines.vams"\n`include "constants.vams"\n`include "constants.vams"\n'
        program = compile_sources({'dut.va': prefix + BODY.replace('VALUE', '`M_LOG2E')}, [INSTANCE])
        self.assert_correctly_rounded(-program.contributions[0].rhs.constant, LRM_D3['M_LOG2E'])

    def test_macros_do_not_cross_independent_roots(self):
        a = ('`include "disciplines.vams"\n`include "constants.vams"\n'
             + BODY.replace('module m(', 'module A(').replace('VALUE', '1'))
        b = '`include "disciplines.vams"\n' + BODY.replace('module m(', 'module B(').replace('VALUE', '`M_TWO_PI')
        bindings = [Instance('a', 'A', {'y': 'a'}), Instance('b', 'B', {'y': 'b'})]
        for roots in ({'a.va': a, 'b.va': b}, {'b.va': b, 'a.va': a}):
            with self.subTest(order=list(roots)), self.assertRaisesRegex(CompileError, r'b\.va:2:.*undefined or unsupported macro'):
                compile_sources(roots, bindings)


if __name__ == '__main__':
    unittest.main()

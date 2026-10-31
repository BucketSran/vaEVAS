"""$rtoi truncates toward zero; `analog` accepts one statement without begin/end (LRM 5.2, 9.11)."""
GUARDS = ['LANG']

import math
from fractions import Fraction as F
import unittest

from evas import CompileError, compile_sources, solve
from test_affine import KERNEL, instance, model

LONE = '`include "disciplines.vams"\nmodule m(u,y,r); input u; output y; inout r; electrical u,y,r; analog {} endmodule'


def values(program, inputs):
    result = solve(program, ['u'], [[x] for x in inputs], kernel=KERNEL)
    return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]


class Rtoi(unittest.TestCase):
    def test_truncates_toward_zero_at_exact_and_adjacent_boundaries(self):
        inputs = [-3., -2., math.nextafter(-1., -math.inf), -1., -.5, -0., 0., .5,
                  math.nextafter(1., -math.inf), 1., 1.5, 3.]
        program = compile_sources({'rtoi.va': model('c=V(u,r);if(c< -2)c=-2;if(c>2)c=2;q=$rtoi(c);V(y,r)<+q;',
                                                    'real c; integer q;')}, [instance()])
        expected = []
        for value in inputs:
            exact = max(F(-2), min(F(2), F.from_float(value)))
            expected.append(math.trunc(exact))
        self.assertEqual(values(program, inputs), expected)

    def test_unbounded_argument_is_refused_like_floor(self):
        with self.assertRaises(CompileError):
            compile_sources({'rtoi.va': model('q=$rtoi(V(u,r));V(y,r)<+q;', 'integer q;')}, [instance()])


class LoneAnalogStatement(unittest.TestCase):
    def test_contribution_without_begin_matches_the_block_form(self):
        inputs = [-1., 0., .25, 2.]
        for body in ('V(y,r)<+2*V(u,r)+1;', 'V(y,r)<+(V(u,r)>0.5)?1:0;'):
            with self.subTest(body=body):
                lone = compile_sources({'lone.va': LONE.format(body)}, [instance()])
                block = compile_sources({'block.va': model(body)}, [instance()])
                self.assertEqual(values(lone, inputs), values(block, inputs))

    def test_conditional_statement_without_begin(self):
        lone = compile_sources({'lone.va': LONE.format('if(V(u,r)>0) V(y,r)<+1; else V(y,r)<+-1;')}, [instance()])
        self.assertEqual(values(lone, [-1., 1.]), [-1., 1.])

    def test_only_one_statement_belongs_to_the_block(self):
        with self.assertRaises(CompileError):
            compile_sources({'lone.va': LONE.format('V(y,r)<+1; V(y,r)<+2;')}, [instance()])


if __name__ == '__main__':
    unittest.main()

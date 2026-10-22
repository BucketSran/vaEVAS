"""Saved SCS rows follow the model's constant $bound_step mesh.

LRM 9.17.2 makes $bound_step the model's own maximum time step. The answers
are authored by hand; negative controls show that larger, conditional or absent
requests leave the grid unchanged and that an oversized grid is refused.
"""
GUARDS = ["LANG", "DEV:scs-input"]

import tempfile
from pathlib import Path
import unittest

from evas import CompileError
from evas.scs import simulate_scs
from test_affine import KERNEL


def module(body):
    return ('`include "disciplines.vams"\nmodule m(u,y,r); input u; output y; inout r; electrical u,y,r; '
            + body + ' endmodule\n')


class BoundStepOutputRows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / 'tb.scs'

    def deck(self, body, tran='tran tran stop=1 maxstep=.5', source='Vin (u 0) vsource type=pwl wave=[0 0 1 1]'):
        (self.root / 'm.va').write_text(module(body))
        self.path.write_text('simulator lang=spectre\nglobal 0\nahdl_include "m.va"\n'
                             + source + '\nDUT (u y 0) m\n' + tran + '\nsave y\n')
        return self.path

    def test_constant_bound_step_sets_the_row_spacing(self):
        # y = u = t; each row of the k/8 mesh is written with its exact value.
        self.deck('analog begin $bound_step(0.125); V(y,r)<+V(u); end')
        result = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(result['saved']['times'], [k / 8 for k in range(9)])
        self.assertEqual([row[0] for row in result['saved']['values']], [k / 8 for k in range(9)])
        self.assertEqual(result['testbench']['bound_step_output_spacing_s'], .125)

    def test_smallest_constant_request_wins(self):
        self.deck('analog begin $bound_step(0.375); $bound_step(0.125); V(y,r)<+V(u); end')
        self.assertEqual(simulate_scs(self.path, kernel=KERNEL)['saved']['times'], [k / 8 for k in range(9)])

    def test_bound_step_larger_than_maxstep_adds_no_rows(self):
        self.deck('analog begin $bound_step(2); V(y,r)<+V(u); end')
        result = simulate_scs(self.path, kernel=KERNEL)
        self.assertEqual(result['saved']['times'], [0, .5, 1])
        self.assertNotIn('bound_step_output_spacing_s', result['testbench'])

    def test_conditional_or_absent_request_adds_no_rows(self):
        self.deck('analog begin if (V(u) > 0.25) $bound_step(0.125); V(y,r)<+V(u); end')
        self.assertEqual(simulate_scs(self.path, kernel=KERNEL)['saved']['times'], [0, .5, 1])
        self.deck('analog begin V(y,r)<+V(u); end')
        self.assertEqual(simulate_scs(self.path, kernel=KERNEL)['saved']['times'], [0, .5, 1])

    def test_bound_step_grid_beyond_point_budget_refuses_with_location(self):
        self.deck('analog begin $bound_step(1e-6); V(y,r)<+V(u); end')
        with self.assertRaisesRegex(CompileError, r'tb\.scs:\d+:\d+: output point budget \(100000\) exceeded by the \$bound_step'):
            simulate_scs(self.path, kernel=KERNEL)


if __name__ == '__main__':
    unittest.main()

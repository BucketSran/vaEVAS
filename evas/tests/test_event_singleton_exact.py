"""A certified singleton sample is an exact binary64 value in event branches.

0.45 + (0.28 - 0.73) is exactly 2**-54 for binary64 inputs, so `x < 0` is
decided (false) without a tolerance. The sampled 0.73 arrives through a settled
transition node, whose certified enclosure is a single point.
"""
GUARDS = ["LANG", "EVENT-ORDER", "EVENT-CONDITIONS"]

import os
from fractions import Fraction as Q
from pathlib import Path
import unittest

from evas import Instance, compile_sources, transient
from evas.errors import KernelError

KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))

SOURCE = '''`include "disciplines.vams"
module hold(vin, clk, q);
    input vin, clk; output q; electrical vin, clk, q;
    real a;
    analog begin
        @(initial_step) a = 0.0;
        @(cross(V(clk) - 0.45, +1)) if (a == 0.0) a = V(vin);
        V(q) <+ transition(a, 0, 1n, 1n);
    end
endmodule
module diff(vin, clk, held, y);
    input vin, clk, held; output y; electrical vin, clk, held, y;
    real s, x, r;
    integer n;
    analog begin
        @(initial_step) begin r = 0.45; n = 0; end
        @(cross(V(clk) - 0.45, +1)) begin
            n = n + 1;
            if (n == 2) begin
                s = V(held);
                x = 0.45 + (V(vin) - s);
                if (x < 0.0) r = -1.0; else r = x;
            end
        end
        V(y) <+ transition(r, 0, 1n, 1n);
    end
endmodule
'''

# clk rises through 0.45 at 1.5 and 11.5; vin is flat at each sample.
CLK = [[0., 0.], [1., 0.], [2., 0.9], [5., 0.9], [6., 0.], [11., 0.], [12., 0.9], [20., 0.9]]


def run(vin, source=SOURCE):
    program = compile_sources({'m.va': source}, [
        Instance('h', 'hold', dict(vin='vin', clk='clk', q='held')),
        Instance('d', 'diff', dict(vin='vin', clk='clk', held='held', y='y'))])
    times = [0., 10., 11.4, 20.]
    result = transient(program, {'vin': vin, 'clk': CLK}, times, stop=20., max_step=0.25,
                       vabstol=1e-12, reltol=0, kernel=KERNEL)
    return times, [frame['voltages'][result['nodes'].index('y')]
                   for frame in result['solutions']]


class SingletonSampleExactBranch(unittest.TestCase):
    def test_binary64_near_tie_takes_the_exactly_decided_branch(self):
        self.assertEqual(Q(0.45) + (Q(0.28) - Q(0.73)), Q(1, 2**54))
        vin = [[0., 0.73], [8., 0.73], [9., 0.28], [20., 0.28]]
        times, y = run(vin)
        self.assertEqual(y[:3], [0.45, 0.45, 0.45])
        # The branch chose r = x = 2**-54, never the r = -1 arm.
        self.assertAlmostEqual(y[-1], 0.0, delta=1e-12)

    def test_nonsingleton_sample_still_refuses_the_branch(self):
        # Hold 0.73/3 (no binary64 point) and compare 0.45 + (0.28 - 3*s).
        # The settled node is an enclosure, not a singleton, so no exact
        # value is manufactured and the near-tie remains uncertified.
        source = (SOURCE.replace('a = V(vin);', 'a = V(vin) / 3.0;')
                  .replace('(V(vin) - s)', '(V(vin) - 3.0 * s)'))
        vin = [[0., 0.73], [8., 0.73], [9., 0.28], [20., 0.28]]
        with self.assertRaises(KernelError) as caught:
            run(vin, source)
        self.assertIn('cannot certify Lt condition', str(caught.exception))


if __name__ == '__main__':
    unittest.main()

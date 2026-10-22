"""Identically triggered event blocks run in source order (LRM 2.4 sequential analog).

Two ``@(cross(V(clk)-0.5,+1))`` blocks fire together. The second reads ``p``
and ``q`` written by the first in the same evaluation, so it sees the
previous edge index, never the current one. The oracle below replays the
blocks by hand: after edge k (k = 1, 2, 3), ``y`` holds 10*(k-1) + k.
"""
GUARDS = ["LANG", "EVENT-ORDER"]

import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient

KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))

SOURCE = '''`include "disciplines.vams"
module seq(clk, d, y);
    input clk, d; output y; electrical clk, d, y;
    real p, q, r;
    analog begin
        @(initial_step) begin p = 0; q = 0; r = 0; end
        @(cross(V(clk) - 0.5, +1)) begin
            p = q;
            q = q + 1;
        end
        @(cross(V(d) - 0.5, +1)) r = r + 100;
        @(cross(V(clk) - 0.5, +1)) begin
            r = 10 * p + q;
        end
        V(y) <+ transition(r, 0, 1n, 1n);
    end
endmodule
'''

# clk rises through 0.5 at 1.5, 5.5 and 9.5; d never does.
CLK = [[0., 0.], [1., 0.], [2., 1.], [3., 1.], [4., 0.], [5., 0.], [6., 1.], [7., 1.],
       [8., 0.], [9., 0.], [10., 1.], [12., 1.]]
D = [[0., 0.], [12., 0.]]
TIMES = [1., 3., 7., 11.]


def run(source=SOURCE):
    program = compile_sources({'seq.va': source}, [
        Instance('u', 'seq', dict(clk='clk', d='d', y='y'))])
    result = transient(program, {'clk': CLK, 'd': D}, TIMES, stop=12., max_step=.25,
                       vabstol=1e-12, reltol=0, kernel=KERNEL)
    return [frame['voltages'][result['nodes'].index('y')] for frame in result['solutions']]


class SameTriggerSequentialBlocks(unittest.TestCase):
    def test_later_block_reads_earlier_writes_of_the_same_event(self):
        expected = [0.] + [10. * (k - 1) + k for k in (1, 2, 3)]
        self.assertEqual(run(), expected)

    def test_ordinary_statement_between_blocks_keeps_the_refusal(self):
        # An ordinary assignment between the blocks may change what the later
        # block reads; those blocks are not joined and remain refused.
        source = SOURCE.replace('        @(cross(V(d) - 0.5, +1)) r = r + 100;\n',
                                '        @(cross(V(d) - 0.5, +1)) r = r + 100;\n        s = V(d);\n'
                                ).replace('real p, q, r;', 'real p, q, r, s;')
        with self.assertRaisesRegex(KernelError, r'reads? state written by another selected block'):
            run(source)

    def test_displaying_block_is_not_moved_across_another_event(self):
        source = SOURCE.replace('            r = 10 * p + q;\n',
                                '            r = 10 * p + q;\n            $display("%g", r);\n')
        with self.assertRaisesRegex(KernelError, r'reads? state written by another selected block'):
            run(source)


if __name__ == '__main__':
    unittest.main()

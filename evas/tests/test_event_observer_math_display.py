"""Observer-math gates read through IR33's RN boundaries (NF-11).

Card: requirement:event-observer-math-isolation v3 (standards line). IR33 wraps
event arithmetic in real_binary nodes and samples in real_boundary nodes. They
round values; they do not change which operations a body applies. A source
floor shown by $display in a physical (contributing) event was admitted before
#243 (2a790344) and is admitted again. A floor whose argument only scales by a
power of two was never a source floor; it keeps the isolated-observer gate.
Expected values are computed by hand: each input below puts (v/0.9)*15+0.5
inside one floor bin both for the exact value and when every operation rounds,
so the answer does not depend on that choice.
"""
GUARDS = ['LANG', 'EVENT-CONDITIONS']

import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

FLOOR = 'floor((V(u,r)/0.9)*15+0.5)'


def run(body, value):
    text = model('@(initial_step) begin q=0; p=0; end @(timer(0.25)) begin ' + body + ' end V(y,r)<+q;',
                 'integer q, p;')
    program = compile_sources({'observer_math.va': text}, [instance()])
    return transient(program, {'u': [[0, value], [1, value]]}, [0, .5, 1], stop=1, max_step=.125,
                     kernel=KERNEL)


class FloorDisplay(unittest.TestCase):
    def test_source_floor_display_in_a_physical_event(self):
        # v = 0.3, 0.5, -0.3 give 5.5, 8.8333.. and -4.5: floors 5, 8 and -5.
        body = f'q={FLOOR}; $display("floor=%d direct=%g",q,{FLOOR}); if(q<1) p=7; else p=8;'
        for value, expected in [(.3, 5), (.5, 8), (-.3, -5)]:
            with self.subTest(value=value):
                result = run(body, value)
                self.assertEqual([d['text'] for d in result['transient']['display_records']],
                                 [f'floor={expected} direct={expected}'])
                y = result['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in result['solutions']], [0, expected, expected])
                names = result['transient']['state_names']
                after = dict(zip(names, result['transient']['events'][-1]['after']))
                self.assertEqual(after['dut:p'], 7 if expected < 1 else 8)

    def test_binary_scale_floor_display_keeps_the_observer_gate(self):
        for argument in ('floor(2*V(u,r))', 'floor(V(u,r))'):
            with self.subTest(argument=argument), \
                    self.assertRaisesRegex(KernelError, 'pure event mathematics requires an isolated observer'):
                run(f'q=1; $display("f=%d",{argument});', .3)


if __name__ == '__main__':
    unittest.main()

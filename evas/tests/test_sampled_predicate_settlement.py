"""Sampled state and a live input jointly select a physical output mode."""
GUARDS = ['LANG', 'EVENT-ORDER', 'EVENT-CONDITIONS', 'COMPOSE', 'TRANSITION']
from pathlib import Path
import unittest
from test_affine import KERNEL

from evas import Instance, compile_sources, transient


class SampledPredicateSettlement(unittest.TestCase):
    def test_driven_sample_selects_live_input_mode_and_preserves_history(self):
        # u(t)=t, so q becomes1/2 at t=1/4. The strict metric predicate
        # 1/2-t>1/8 is true at1/4 and5/16, false at/after3/8.
        # The independent transition is a line from0 to1/2 over[1/4,3/8].
        source = Path(__file__).with_name('fixtures').joinpath('driven-sampled-predicate.va').read_text()
        p = compile_sources({'driven-sampled-predicate.va': source},
                            [Instance('dut', 'sampled_predicate',
                                      {'u': 'u', 'y': 'y', 'z': 'z'})])
        times = [0., 0.125, 0.25, 0.3125, 0.5, 1.]
        result = transient(p, {'u': [[0., 0.], [1., 1.]]}, times,
                           stop=1., max_step=0.125,
                           kernel=KERNEL,
                           vabstol=1e-10, reltol=0.)
        actual = lambda name: [row['voltages'][result['nodes'].index(name)]
                               for row in result['solutions']]
        self.assertEqual(actual('y'), [0., 0., 1., 1., 0., 0.])
        self.assertEqual(actual('z'), [0., 0., 0., 0.25, 0.5, 0.5])


if __name__ == '__main__':
    unittest.main()

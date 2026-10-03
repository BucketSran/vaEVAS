"""Public contracts for repeated solves; expected values do not use EVAS algebra."""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["LIN", "SPARSE", "DEV:sparse-reuse"]

import unittest

from evas import KernelError, compile_sources, solve
from test_affine import KERNEL, instance, model


class RepeatedSolves(unittest.TestCase):
    def test_coupled_batch_matches_individual_solves_and_hand_answers(self):
        source = model('V(y,r)<+gain*V(u,r)+bias;',
                       'parameter real gain=.5; parameter real bias=0;')
        instances = [
            instance('a', connections=dict(u='b', y='a', r='u')),
            instance('b', connections=dict(u='a', y='b', r='u'),
                     parameters=dict(gain=.25, bias=1)),
        ]
        program = compile_sources({'reuse.va': source}, instances)
        samples = [[0], [1], [-2], [0], [1e3]]
        batch = solve(program, ['u'], samples, kernel=KERNEL)
        for inputs, result in zip(samples, batch['solutions']):
            single = solve(program, ['u'], [inputs], kernel=KERNEL)
            self.assertEqual(result, single['solutions'][0])
            row = dict(zip(batch['nodes'], result['voltages']))
            self.assertAlmostEqual(row['a'], inputs[0] + 4 / 7, delta=1e-10)
            self.assertAlmostEqual(row['b'], inputs[0] + 8 / 7, delta=1e-10)

    def test_cached_factor_does_not_skip_redundant_constraint_on_later_sample(self):
        source = model('V(y,r)<+V(u,r);')
        instances = [instance('a'), instance('b', connections=dict(u='v', y='y', r='0'))]
        program = compile_sources({'redundant.va': source}, instances)
        with self.assertRaises(KernelError) as caught:
            solve(program, ['u', 'v'], [[1, 1], [-2, -2], [1, 2]], kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'residual_failure')
        self.assertEqual(caught.exception.detail['sample'], 2)

    def test_all_driven_circuit_checks_each_sample_without_unknowns(self):
        program = compile_sources({'driven.va': model('V(y,r)<+2*V(u,r);')}, [instance()])
        with self.assertRaises(KernelError) as caught:
            solve(program, ['u', 'y'], [[1, 2], [-2, -4], [3, 5]], kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'residual_failure')
        self.assertEqual(caught.exception.detail['sample'], 2)

    def test_nonlinear_samples_keep_independent_iterates_and_accuracy(self):
        program = compile_sources({'cubic.va': model('V(y,r)<+V(u,r)-pow(V(y,r),3);')},
                                  [instance()])
        # Exact roots .5, -1, 0, .5: u = y + y**3.
        samples = [[.625], [-2], [0], [.625]]
        batch = solve(program, ['u'], samples, kernel=KERNEL)
        for inputs, result, expected in zip(samples, batch['solutions'], [.5, -1, 0, .5]):
            single = solve(program, ['u'], [inputs], kernel=KERNEL)
            self.assertEqual(result, single['solutions'][0])
            row = dict(zip(batch['nodes'], result['voltages']))
            self.assertAlmostEqual(row['y'], expected, delta=1e-10)
            self.assertLessEqual(result['max_voltage_correction_ratio'], 1)


if __name__ == '__main__':
    unittest.main()

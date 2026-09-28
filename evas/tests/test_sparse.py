"""Sparse-size public circuits with independently constructed voltage answers."""
import unittest

from evas import KernelError, compile_sources, solve
from test_affine import KERNEL, instance, model


class SparseContracts(unittest.TestCase):
    def test_coupled_ring_reference_voltage_and_repeated_rhs(self):
        source = model('V(y,r)<+bias+V(v,r)+.25*V(u,r);',
                       'parameter real bias=0;', ports='u,v,y,r',
                       directions='input u,v; output y; inout r;')
        count = 64
        roots = [(i % 7 - 3) / 8 for i in range(count)]
        cells = [instance(f'cell{i:03}',
                          connections=dict(u=f'y{(i+1)%count}', v='v', y=f'y{i}', r='r'),
                          parameters=dict(bias=roots[i]-.25*roots[(i+1)%count]))
                 for i in range(count)]
        program = compile_sources({'ring.va': source}, cells)
        samples = [[1, .5], [-2, -.7], [1, .5]]
        result = solve(program, ['v', 'r'], samples, kernel=KERNEL)
        for inputs, solution in zip(samples, result['solutions']):
            values = dict(zip(result['nodes'], solution['voltages']))
            for i, root in enumerate(roots):
                self.assertAlmostEqual(values[f'y{i}'],
                                       inputs[1]+root+(inputs[0]-inputs[1])/.75,
                                       delta=1e-10)
        self.assertEqual(result['solutions'][0], result['solutions'][2])

    def test_nonlinear_jacobian_gains_new_nonzeros_after_zero_start(self):
        # Off-diagonal dF_i/dy_(i+1) is zero initially and becomes nonzero.
        source = model('V(y,r)<+bias-pow(V(y,r),3)-.125*pow(V(u,r),2);',
                       'parameter real bias=0;')
        count = 40
        roots = [.125+.0625*(i % 5) for i in range(count)]
        cells = [instance(f'cell{i:03}',
                          connections=dict(u=f'y{(i+1)%count}', y=f'y{i}', r='0'),
                          parameters=dict(bias=roots[i]+roots[i]**3+.125*roots[(i+1)%count]**2))
                 for i in range(count)]
        program = compile_sources({'coupled.va': source}, cells)
        result = solve(program, [], [[]], kernel=KERNEL)
        solution = result['solutions'][0]
        values = dict(zip(result['nodes'], solution['voltages']))
        for i, root in enumerate(roots):
            self.assertAlmostEqual(values[f'y{i}'], root, delta=1e-10)
        for metric in ('max_residual_ratio', 'max_scaled_residual_ratio',
                       'max_voltage_correction_ratio'):
            self.assertLessEqual(solution[metric], 1)

    def test_scaled_nonlinear_rows_keep_small_residual_and_voltage_accuracy(self):
        source = model('V(y,r)<+V(y,r)-s*(V(y,r)+pow(V(y,r),3)-V(u,r));',
                       'parameter real s=1e-13;')
        cells = [instance(f'cell{i:03}', connections=dict(u='u', y=f'y{i}', r='0'),
                          parameters=dict(s=[1e-13, 1, 1e6][i % 3])) for i in range(40)]
        program = compile_sources({'scaled.va': source}, cells)
        result = solve(program, ['u'], [[.625], [-2], [0]], kernel=KERNEL)
        for solution, root in zip(result['solutions'], [.5, -1, 0]):
            values = dict(zip(result['nodes'], solution['voltages']))
            for i in range(40):
                self.assertAlmostEqual(values[f'y{i}'], root, delta=1e-10)

    def test_redundant_constraint_and_singular_system_remain_errors(self):
        source = model('V(y,r)<+V(u,r);')
        cells = [instance(f'cell{i:03}', connections=dict(u='u', y=f'y{i}', r='0'))
                 for i in range(40)]
        cells.append(instance('redundant', connections=dict(u='v', y='y0', r='0')))
        program = compile_sources({'parallel.va': source}, cells)
        with self.assertRaises(KernelError) as error:
            solve(program, ['u', 'v'], [[1, 1], [-2, -2], [1, 2]], kernel=KERNEL)
        self.assertEqual(error.exception.detail['kind'], 'residual_failure')
        self.assertEqual(error.exception.detail['sample'], 2)
        cells.pop()
        cells[0] = instance('cell000', connections=dict(u='y0', y='y0', r='0'))
        program = compile_sources({'singular.va': source}, cells)
        with self.assertRaises(KernelError) as error:
            solve(program, ['u'], [[1]], kernel=KERNEL)
        self.assertEqual(error.exception.detail['kind'], 'singular_system')
        self.assertIn('singular.va:', error.exception.detail['message'])


if __name__ == '__main__':
    unittest.main()

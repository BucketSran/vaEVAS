"""Sparse-size event/operator integration with independent mathematical answers."""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["SPARSE", "DEV:sparse-reuse"]

from fractions import Fraction as F
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from test_timed_composition import SOURCE, exact


class SparseTransientContracts(unittest.TestCase):
    def test_idt_sparse_chain_matches_exact_integrals_and_preserves_sampling(self):
        # 40 unknowns / 79 coefficients select sparse LU. Each call has its own
        # input gain, offset and IC; the integral input remains directly driven.
        source = model('V(y,r)<+idt(g*V(u,r)+b,ic)+.25*V(v,r);',
                       'parameter real g=1; parameter real b=0; parameter real ic=0;',
                       ports='u,v,y,r', directions='input u,v; output y; inout r;')
        cells = [instance(f'cell{i:02}', connections=dict(u='u',
                     v=f'y{i-1}' if i else '0', y=f'y{i}', r='0'),
                     parameters=dict(g=[1,2,-1][i%3], b=(i%3)/8, ic=(i%5)/8))
                 for i in range(40)]
        anchors = [0,1,2,2.1,3]
        baseline = None
        for order, step, times in [(cells,3,anchors),
                                   (cells[::-1],.125,sorted(set(anchors+[i/8 for i in range(25)])))]:
            program = compile_sources({'cell.va': source}, order)
            result = transient(program, {'u': [[0,-1],[1,-1],[3,3]]}, times,
                               stop=3, max_step=step, vabstol=1e-10, reltol=0, kernel=KERNEL)
            by_time = {}
            for time, solution in zip(times,result['solutions']):
                volts = dict(zip(result['nodes'],solution['voltages']))
                by_time[time] = [volts[f'y{i}'] for i in range(40)]
                t = F(time)
                # u=-1 until t=1, then u=-1+2(t-1). Exact original-PWL area.
                area = -t if t <= 1 else -1-(t-1)+(t-1)**2
                expected = F(0)
                for i, actual in enumerate(by_time[time]):
                    expected = F(i%5,8)+[1,2,-1][i%3]*area+F(i%3,8)*t+expected/4
                    self.assertLessEqual(abs(F(actual)-expected), F(1e-10))
                self.assertLessEqual(solution['max_residual_ratio'], 1)
            chosen = [by_time[t] for t in anchors]
            if baseline is None:
                baseline = chosen
            else:
                self.assertEqual(chosen, baseline)
        # Iterative refinement can now satisfy the point residual, but cannot
        # erase the original integral/history uncertainty at this budget.
        with self.assertRaises(KernelError) as caught:
            transient(program, {'u': [[0,-1],[1,-1],[3,3]]}, [0,2.1,3], stop=3,
                      max_step=3, vabstol=1e-20, reltol=0, kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'waveform_accuracy')

    def test_internal_cross_chain_preserves_root_and_original_relations(self):
        count = 40
        cell = model('V(y,r)<+V(u,r)+.25*V(v,r);', ports='u,v,y,r',
                     directions='input u,v; output y; inout r;')
        # y_i = g_i*u with g_i = 1+g_(i-1)/4. The last guard has root 1/2.
        gains = []
        for _ in range(count):
            gains.append(1 + (gains[-1] if gains else F(0))/4)
        observer = model('''@(initial_step) n=0;
            @(cross(V(u,r)-threshold,+1,1e-10,1e-9)) n=n+1;
            V(y,r)<+n;''', 'integer n; parameter real threshold=0;')
        observer = observer.replace('module m(', 'module observer(')
        cells = [instance(f'cell{i:02}', connections=dict(u='u',
                    v=f'y{i-1}' if i else '0', y=f'y{i}', r='0'))
                 for i in range(count)]
        cells.append(instance('observer', 'observer', dict(u='y39', y='out', r='0'),
                              dict(threshold=float(gains[-1]/2))))
        for order, step in [(cells, 1), (cells[::-1], .125)]:
            program = compile_sources({'cell.va': cell, 'observer.va': observer}, order)
            times = [0, .25, .75, 1]
            result = transient(program, {'u': [[0,0],[1,1]]}, times,
                               stop=1, max_step=step, kernel=KERNEL)
            self.assertEqual(len(result['transient']['events']), 1)
            self.assertAlmostEqual(result['transient']['events'][0]['time'], .5, delta=1e-10)
            self.assertEqual(result['transient']['states'], [[0],[0],[1],[1]])
            for time, solution in zip(times, result['solutions']):
                volts = dict(zip(result['nodes'], solution['voltages']))
                for i, gain in enumerate(gains):
                    self.assertLessEqual(abs(F(volts[f'y{i}']) - gain*F(time)), F(1e-12))
                self.assertLessEqual(solution['max_residual_ratio'], 1)

    def test_same_time_ring_uses_new_voltage_and_sequential_assignments(self):
        count = 40
        roots = [F(i % 7 - 3, 8) for i in range(count)]
        source = model('''@(initial_step) s=0;
            @(timer(.5,.5,1e-9)) begin s=V(u,r); s=.25*s+bias+V(v,r); end
            V(y,r)<+s;''', 'real s; parameter real bias=0;', ports='u,v,y,r',
            directions='input u,v; output y; inout r;')
        cells = [instance(f'cell{i:02}', connections=dict(u=f'y{(i+1)%count}',
                    v='v', y=f'y{i}', r='r'),
                    parameters=dict(bias=float(roots[i]-roots[(i+1)%count]/4)))
                 for i in range(count)]
        for order, step in [(cells, 1), (cells[::-1], .125)]:
            program = compile_sources({'ring.va': source}, order)
            times = [0, .5, .75, 1]
            result = transient(program, {'v': [[0,.5],[1,1.5]], 'r': [[0,.5],[1,.5]]},
                               times, stop=1, max_step=step, kernel=KERNEL)
            self.assertEqual(len(result['transient']['events']), 2*count)
            for time, states, solution in zip(times, result['transient']['states'], result['solutions']):
                volts = dict(zip(result['nodes'], solution['voltages']))
                memory = dict(zip(result['transient']['state_names'], states))
                sample = F(1) if time == 1 else F(1,2)
                for i, root in enumerate(roots):
                    # (I-P/4)s = bias + sample; P*1=1, hence s=root+4*sample/3.
                    expected = root + 4*sample/3 if time else F(0)
                    self.assertLessEqual(abs(F(memory[f'cell{i:02}:s'])-expected), F(1e-12))
                    self.assertLessEqual(abs(F(volts[f'y{i}'])-expected-F(1,2)), F(1e-12))
                self.assertLessEqual(solution['max_residual_ratio'], 1)

    def test_sparse_size_composition_keeps_callsite_histories_and_grid_invariance(self):
        # Twelve distinct instances, 36 unknown nodes: diagonal sparse solves,
        # but the complete interval certificate and operator histories remain active.
        cells = [instance(f'c{i:02}', connections=dict(u='u', y=f'y{i}', z=f'z{i}',
                    h=f'h{i}', r='0'), parameters=dict(gain=1+i%3)) for i in range(12)]
        for order, step, times in [(cells, 8, [0,1,1.5,3,3.5,5,7,8]),
                                    (cells[::-1], .5, [k/2 for k in range(17)])]:
            program = compile_sources({'composition.va': SOURCE}, order)
            result = transient(program, {'u': [[0,0],[2,4],[4,-4],[8,-4]]}, times,
                               stop=8, max_step=step, kernel=KERNEL)
            self.assertEqual(len(result['transient']['events']), 12*9)
            for time, states, solution in zip(times, result['transient']['states'], result['solutions']):
                volts = dict(zip(result['nodes'], solution['voltages']))
                memory = dict(zip(result['transient']['state_names'], states))
                for i in range(12):
                    expected_v, expected_s = exact(F(time), F(1+i%3))
                    for name, expected in zip(['y','z','h'], expected_v):
                        self.assertLessEqual(abs(F(volts[f'{name}{i}'])-expected), F(3e-12))
                    for name, expected in zip(['n','c','q'], expected_s):
                        self.assertLessEqual(abs(F(memory[f'c{i:02}:{name}'])-expected), F(3e-12))
                self.assertLessEqual(solution['max_residual_ratio'], 1)

    def test_held_guard_and_history_dependency_remain_distinct_in_sparse_networks(self):
        cell = model('V(y,r)<+V(u,r);')
        for expression in ['n', 'n-n', '1e-300*(1e-300*n)']:
            driver = model(f'''@(initial_step) n=0;
                @(cross(V(u,r)-.5,+1)) n=n+1; V(y,r)<+{expression};''', 'integer n;')
            driver = driver.replace('module m(', 'module driver(')
            cells = [instance(f'cell{i:02}', connections=dict(u=f'y{i-1}', y=f'y{i}', r='0'))
                     for i in range(1,40)]
            cells.append(instance('driver', 'driver', dict(u='y39', y='y0', r='0')))
            program = compile_sources({'cell.va': cell, 'driver.va': driver}, cells)
            # With no external drive, q stays zero and the held affine guard
            # remains -.5. The new epoch scheduler correctly has no events.
            result = transient(program, {}, [0,1], stop=1, max_step=1, kernel=KERNEL)
            self.assertEqual(result['transient']['events'], [])
            self.assertEqual(result['transient']['states'], [[0],[0]])
            self.assertEqual(result['solutions'][-1]['voltages'][result['nodes'].index('y39')],0)
            # A history relay remains outside the relocalization contract even
            # when its input cancels or underflows numerically.
            driver = driver.replace(f'V(y,r)<+{expression};',
                                    f'V(y,r)<+transition({expression},0,.1,.1);')
            program = compile_sources({'cell.va': cell, 'driver.va': driver}, cells)
            with self.assertRaises(KernelError) as caught:
                transient(program, {}, [0,1], stop=1, max_step=1, kernel=KERNEL)
            self.assertEqual(caught.exception.detail['kind'], 'unsupported_cross')


if __name__ == '__main__':
    unittest.main()

"""IR18 initialization and shared writes retain exact physical query phases."""
GUARDS = ['LANG', 'TIMER', 'EVENT-ORDER']

import unittest
import math
from fractions import Fraction

from test_continuous_dynamics import compile_model, run, values


class InitializedEventComposition(unittest.TestCase):
    def test_falling_source_root_and_equivalent_or_share_the_exact_time(self):
        root = (Fraction(0.7)-Fraction(3))/(Fraction(0)-Fraction(3))*Fraction(6e-6)
        before = math.nextafter(float(root), -math.inf)
        after = math.nextafter(float(root), math.inf)
        self.assertLess(Fraction(before), root)
        self.assertGreater(Fraction(after), root)
        for guard in ['cross(V(u,r)-0.7,-1,1e-12,1e-9)',
                      'cross(V(u,r)-0.7,-1,1e-12,1e-9) or cross(2*(V(u,r)-0.7),-1,1e-12,1e-9)']:
            with self.subTest(guard=guard):
                program = compile_model('@(initial_step) n=0; @('+guard+') n=n+1; V(y,r)<+n;', 'integer n;')
                result = run(program, {'u': [[0,3],[6e-6,0]]}, [0,before,after,6e-6], stop=6e-6)
                self.assertEqual(values(result), [0,0,1,1])
                self.assertEqual(len(result['transient']['events']), 1)

    def test_original_affine_cross_keeps_query_phase_and_transition_sample(self):
        # The original binary-rational root lies just after the nominal query;
        # rounded endpoint guards must not erase that provable ordering.
        root = Fraction(0.7) * Fraction(6e-6) / 3
        query = 1.4e-6
        self.assertLess(Fraction(query), root)
        self.assertLess(root, Fraction(math.nextafter(query, math.inf)))
        program = compile_model(
            '@(initial_step) q=0; '
            '@(cross(V(u,r)-0.7,1,1e-12,1e-9)) q=V(u,r); '
            'V(y,r)<+q; V(z,r)<+transition(q,2.5e-7,1e-6,1e-6);',
            'real q; electrical z;')
        times = [0, query, math.nextafter(query, math.inf), 2e-6, 6e-6]
        result = run(program, {'u': [[0, 0], [6e-6, 3]]}, times,
                     stop=6e-6, vabstol=1e-6, reltol=1e-8)
        self.assertEqual(values(result)[:2], [0, 0])
        for value in values(result)[2:]:
            self.assertAlmostEqual(value, 0.7, delta=1e-7)
        self.assertEqual(len(result['transient']['events']), 1)
        for t, value in zip(times, values(result, 'dut:z')):
            expected = 0.7 * min(1, max(0, float((Fraction(t)-root-Fraction(2.5e-7))/Fraction(1e-6))))
            self.assertAlmostEqual(value, expected, delta=1e-6)

    def test_input_initialization_shared_counter_and_neighbor_clocks_share_one_history(self):
        # Independent binary-rational ordering: the second periodic event lies
        # strictly between the two adjacent query values, before the single timer.
        periodic = Fraction(0.1) + Fraction(0.2)
        self.assertLess(Fraction(0.3), periodic)
        self.assertLess(periodic, Fraction(0.30000000000000004))
        body = ('@(initial_step) n=INITIAL; '
                '@(timer(0.1,0.2,1e-12)) n=n+1; '
                '@(timer(0.30000000000000004,0,1e-12)) n=n+1; V(y,r)<+n;')
        inputs = {'u': [[0, 0.9], [0.4, 0.9]]}
        dense = [0, 0.1, 0.3, 0.30000000000000004, 0.4]
        sparse = [0, 0.1, 0.30000000000000004, 0.4]
        for initial in ['(V(u,r)>0.65)', '1']:
            with self.subTest(initial=initial):
                program = compile_model(body.replace('INITIAL', initial), 'real n;')
                result = run(program, inputs, dense, stop=0.4)
                self.assertEqual(values(result), [1, 2, 2, 4, 4])
                self.assertEqual(len(result['transient']['events']), 3)
                result_sparse = run(program, inputs, sparse, stop=0.4)
                self.assertEqual(values(result_sparse), [1, 2, 4, 4])
                self.assertEqual(result_sparse['transient']['events'], result['transient']['events'])

"""Held-state predicate certification through public compile/transient entry."""
GUARDS = ["DEV:scs-input", "TIMED-OPERATOR", "EVENT-ORDER", "COMPOSE"]

import os
from pathlib import Path
import unittest
from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, model, instance

KERNEL = Path(os.environ.get('EVAS_TEST_KERNEL', str(KERNEL)))

class SourceStatePredicates(unittest.TestCase):
    def test_interval_held_predicate_accepts_determinate_true_and_false(self):
        # The exact recurrence is q[k]=1-(24/25)**k. Its first
        # post-timer value exceeds .01 and stays below .9 over this run.
        for threshold, expected in [('0.01', .9), ('0.9', 0.)]:
            with self.subTest(threshold=threshold):
                program = compile_sources({'held.va': model(f"""
                    @(initial_step) q=0;
                    @(timer(0,1n)) q=q+0.04*(V(u,r)-q);
                    V(y,r)<+transition(($abstime>1n && q>{threshold})?0.9:0,0,300p,300p);
                """, 'real q;')}, [instance()])
                times = [0, 0.5e-9, 1.5e-9, 2.5e-9, 3e-9]
                def run(points, forced=False):
                    return transient(program, {'u':[[0,1],[3e-9,1]]}, points,
                                     stop=3e-9,max_step=500e-12,kernel=KERNEL,timeout=120,
                                     strobetimes=points if forced else [])
                sparse = run([0,3e-9])
                dense = run(times)
                forced = run(times, True)
                for response in [sparse, dense, forced]:
                    self.assertAlmostEqual(response['solutions'][-1]['voltages'][program.nodes.index('y')], expected, places=10)
                self.assertEqual(sparse['transient']['events'], dense['transient']['events'])
                self.assertEqual(dense['transient']['events'], forced['transient']['events'])
                self.assertEqual(dense['solutions'], forced['solutions'])

    def test_held_predicate_straddling_threshold_refuses_instead_of_selecting_center(self):
        # Three outward additions of binary64 0.1 enclose the 0.3 threshold.
        # A scalar representative must not decide this interval predicate.
        program = compile_sources({'uncertain.va': model("""
            @(initial_step) q=0;
            @(timer(1n,1n)) q=q+0.1;
            V(y,r)<+transition(($abstime>1n && q>0.3)?0.9:0,0,300p,300p);
        """, 'real q;')}, [instance()])
        with self.assertRaises(KernelError) as error:
            transient(program, {'u':[[0,0.5],[4e-9,0.5]]}, [0,4e-9],
                      stop=4e-9,max_step=500e-12,
                      kernel=KERNEL,timeout=120)
        self.assertEqual(error.exception.detail['kind'], 'condition_precision')

    def test_unselected_nonheld_leaf_remains_structurally_rejected(self):
        program = compile_sources({'masked.va': model("""
            V(y,r)<+transition(($abstime>1n)?0.9:V(u,r),0,300p,300p);
        """)}, [instance()])
        times = [2e-9,3e-9]
        result = transient(program, {'u':[[0,.5],[3e-9,.5]]}, times,
                           stop=3e-9,max_step=3e-9,kernel=KERNEL)
        for solution in result['solutions']:
            self.assertAlmostEqual(solution['voltages'][program.nodes.index('y')], .9,
                                   delta=2e-12)
        # The source changes only after its arm is unselected. Whole-domain
        # auditing must still reject it, even though all queries select 0.9.
        with self.assertRaises(KernelError) as caught:
            transient(program, {'u':[[0,.5],[1e-9,.5],[2e-9,.7],[3e-9,.7]]}, times,
                      stop=3e-9,max_step=3e-9,kernel=KERNEL)
        self.assertEqual(caught.exception.diagnostic['code'], 'kernel.unsupported_operator')

if __name__ == '__main__':
    unittest.main()

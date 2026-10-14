"""Independent contracts for the timing-scoped causal split."""
GUARDS = ["DYNAMICS", "TRANSITION", "TIMER", "COMPOSE"]
import math
import os
from pathlib import Path
import unittest
from evas import compile_sources, transient, KernelError
from test_affine import KERNEL as DEFAULT_KERNEL, model, instance
KERNEL=Path(os.environ.get("EVAS_CAUSAL_KERNEL",DEFAULT_KERNEL))

TIMES=[0.,0.125,0.25,0.375,0.5,0.75,1.]

def execute(core,extra='',times=TIMES,forced=False):
    source=model('@(timer(0.25,0,0.001)) n=1;'+core+'V(y,r)<+transition(n,0,0.25);'+extra,'integer n;electrical z,f;')
    p=compile_sources({'n09-causal.va':source},[instance()])
    return transient(p,{'u':[[0.,1.],[1.,1.]]},times,stop=1.,max_step=0.125,
                     strobetimes=times if forced else [],vabstol=1e-8,reltol=0.,kernel=KERNEL)

def col(result,name):
    node=result['nodes'].index(name)
    return [row['voltages'][node] for row in result['solutions']]

class CausalStateReadout(unittest.TestCase):
    def test_nonlinear_state_and_independent_transition_keep_own_histories(self):
        core='V(z,r)<+idt((V(u,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);V(f,r)<+V(z,r);'
        for forced in [False,True]:
            result=execute(core,forced=forced)
            for time,value in zip(TIMES,col(result,'dut:z')):
                self.assertAlmostEqual(value,1-0.75*math.exp(-time/2),places=8)
            self.assertEqual(col(result,'dut:z'),col(result,'dut:f'))
            self.assertEqual(col(result,'y'),[min(1,max(0,4*time-1)) for time in TIMES])

    def test_source_forced_integral_keeps_accuracy_target(self):
        result=execute('V(z,r)<+idt(V(u,r)*V(u,r),0.25);V(f,r)<+V(z,r);')
        for time,value in zip(TIMES,col(result,'dut:z')):
            self.assertAlmostEqual(value,0.25+time,places=8)

    def test_same_branch_hidden_feedback_is_not_dropped(self):
        core='V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);V(f,r)<+V(z,r);'
        for extra in ['V(z,r)<+0*V(y,r);','V(z,r)<+(V(u,r)>2?V(y,r):0);']:
            with self.subTest(extra=extra),self.assertRaises(KernelError) as caught:
                execute(core,extra)
            self.assertEqual(caught.exception.detail["kind"],"unsupported_operator")

    def test_sparse_dense_queries_do_not_reset_state(self):
        core='V(z,r)<+idt((V(u,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);V(f,r)<+V(z,r);'
        sparse=execute(core,times=[0.,0.375,1.]);dense=execute(core)
        for time,solution in zip([0.,0.375,1.],sparse['solutions']):
            self.assertEqual(solution,dense['solutions'][TIMES.index(time)])
        self.assertEqual(sparse['transient']['events'],dense['transient']['events'])

    def test_timed_bound_feedback_including_zero_term_keeps_rejection(self):
        core='V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);V(f,r)<+V(z,r);'
        for bound in ['0.01+0.001*V(y,r)','0.125+0*V(y,r)']:
            with self.subTest(bound=bound),self.assertRaises(KernelError) as caught:
                execute(core,extra='$bound_step('+bound+');')
            self.assertEqual(caught.exception.detail['kind'],'unsupported_operator')

    def test_full_output_gain_cannot_borrow_internal_accuracy_budget(self):
        core='V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);V(f,r)<+V(z,r);'
        with self.assertRaises(KernelError) as caught:
            execute(core,extra='V(y,r)<+1e12*V(z,r);')
        self.assertIn(caught.exception.detail['kind'],['event_accuracy','waveform_accuracy'])

    def test_interleaved_global_operator_ids_keep_two_different_initial_conditions(self):
        source=model('@(timer(0.25,0,0.001)) n=1;'
            'V(z0,r)<+idt(V(u,r)*V(u,r),0.25);'
            'V(y,r)<+transition(n,0,0.25);'
            'V(z1,r)<+idt(2*V(u,r)*V(u,r),0.75);',
            'integer n;electrical z0,z1;')
        p=compile_sources({'two-ic.va':source},[instance()])
        self.assertEqual([op['kind'] for op in p.to_dict()['operators']],['idt','transition','idt'])
        for forced in [False,True]:
            result=transient(p,{'u':[[0,1],[1,1]]},TIMES,stop=1,max_step=0.125,
                strobetimes=TIMES if forced else [],vabstol=1e-8,reltol=0,kernel=KERNEL)
            self.assertEqual(col(result,'dut:z0'),[0.25+t for t in TIMES])
            self.assertEqual(col(result,'dut:z1'),[0.75+2*t for t in TIMES])
            self.assertEqual(col(result,'y'),[min(1,max(0,4*t-1)) for t in TIMES])

"""Independent continuous state and timed readout keep their physical histories."""
GUARDS=['DYNAMICS','TIMED-OPERATOR','COMPOSE','EVENT-ORDER']
import math
import unittest
from evas import compile_sources,transient,KernelError
from test_affine import model,instance,KERNEL

TIMES=[0.,0.125,0.25,0.375,0.5,0.75,1.]
def simulate(core,output,extra='',times=TIMES,forced=False):
    source=model('@(timer(0.25,0,0)) n=1; '+core+'V(y,r)<+'+output+';'+extra,'integer n; electrical z;')
    p=compile_sources({'timed-readout.va':source},[instance()])
    return transient(p,{'u':[[0.,1.],[1.,1.]]},times,stop=1.,max_step=0.125,
                     strobetimes=times if forced else [],vabstol=1e-8,reltol=0.,kernel=KERNEL)

def column(r,name):return [row['voltages'][r['nodes'].index(name)] for row in r['solutions']]
def ramp(t):return min(1.,max(0.,(t-0.25)/0.25))

class IndependentTimedReadout(unittest.TestCase):
    def test_static_voltage_times_transition_reads_current_voltage(self):
        for forced in [False,True]:
            r=simulate('V(z,r)<+2*V(u,r)+0.25;','V(z,r)*transition(n,0,0.25)',forced=forced)
            for t,v in zip(TIMES,column(r,'y')):self.assertAlmostEqual(v,2.25*ramp(t),places=8)

    def test_unrelated_transition_does_not_enter_nonlinear_state_network(self):
        r=simulate('V(z,r)<+idt((V(u,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);','transition(n,0,0.25)')
        for t,v in zip(TIMES,column(r,'dut:z')):self.assertAlmostEqual(v,1-0.75*math.exp(-t/2),places=8)
        for t,v in zip(TIMES,column(r,'y')):self.assertAlmostEqual(v,ramp(t),places=8)

    def test_readout_multiplies_current_state_without_resampling_or_reset(self):
        core='V(z,r)<+idt((V(u,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);'
        for forced in [False,True]:
            r=simulate(core,'V(z,r)*transition(n,0,0.25)',forced=forced)
            for t,v in zip(TIMES,column(r,'y')):self.assertAlmostEqual(v,(1-0.75*math.exp(-t/2))*ramp(t),places=8)
            for t,v in zip(TIMES,column(r,'dut:z')):self.assertAlmostEqual(v,1-0.75*math.exp(-t/2),places=8)
            self.assertEqual([e['time'] for e in r['transient']['events']],[0.25])

    def test_source_forced_integral_retains_a_numerical_target_without_internal_equations(self):
        r=simulate('V(z,r)<+idt(V(u,r)*V(u,r),0.25);','V(z,r)*transition(n,0,0.25)')
        for t,v in zip(TIMES,column(r,'y')):self.assertAlmostEqual(v,(0.25+t)*ramp(t),places=8)

    def test_full_branch_sum_defines_the_continuous_initial_voltage(self):
        r=simulate('V(z,r)<+idt(1-V(z,r),0.25);V(z,r)<+0.125;','V(z,r)*transition(n,0,0.25)')
        for t,v in zip(TIMES,column(r,'dut:z')):self.assertAlmostEqual(v,1-0.625*math.exp(-t),places=8)
        for t,v in zip(TIMES,column(r,'y')):self.assertAlmostEqual(v,(1-0.625*math.exp(-t))*ramp(t),places=8)

    def test_unused_branch_and_zero_feedback_remain_structural_dependencies(self):
        for extra in ['V(z,r)<+0*V(y,r);','V(z,r)<+(V(u,r)>2?V(y,r):0);']:
            with self.subTest(extra=extra),self.assertRaises(KernelError):
                simulate('V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);',
                         'V(z,r)*transition(n,0,0.25)',extra=extra)

    def test_full_output_error_budget_survives_the_causal_split(self):
        with self.assertRaises(KernelError) as caught:
            simulate('V(z,r)<+idt((1-V(z,r))/(1+V(u,r)*V(u,r)),0.25);',
                     '1e12*V(z,r)*transition(n,0,0.25)')
        self.assertIn(caught.exception.detail['kind'],['event_accuracy','waveform_accuracy'])

    def test_observation_density_does_not_reinitialize_the_state(self):
        core='V(z,r)<+idt((V(u,r)-V(z,r))/(1+V(u,r)*V(u,r)),0.25);'
        out='V(z,r)*transition(n,0,0.25)'
        sparse=simulate(core,out,times=[0.,0.375,1.]);dense=simulate(core,out)
        for t,a in zip([0.,0.375,1.],sparse['solutions']):
            b=dense['solutions'][TIMES.index(t)]
            self.assertEqual(a,b)
        self.assertEqual(sparse['transient']['events'],dense['transient']['events'])

    def test_timed_readout_feedback_is_not_dropped_from_state_equation(self):
        with self.assertRaises(KernelError):
            simulate('V(z,r)<+idt(V(y,r),0.25);','V(z,r)*transition(n,0,0.25)')

    def test_general_voltage_product_does_not_borrow_timed_coefficient_admission(self):
        with self.assertRaises(KernelError):
            simulate('V(z,r)<+2*V(u,r);','V(z,r)*V(y,r)')

if __name__=='__main__':unittest.main()

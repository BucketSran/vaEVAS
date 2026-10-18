"""Independent whole-domain DC targets; answers use exact dyadic ramps."""
GUARDS = ["TRANSITION", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]

from fractions import Fraction as F
from pathlib import Path
import os,unittest
from evas import CompileError, KernelError,compile_sources,transient
from test_affine import KERNEL as DEFAULT_KERNEL,model,instance
KERNEL=Path(os.environ.get('EVAS_DC_TARGET_KERNEL',DEFAULT_KERNEL))
def program(body='V(y)<+transition(s?V(u):0,0,0.125,0.125);',connections=None,name='dut'):
    text=model('@(initial_step)s=0; @(timer(0.5))s=1; '+body,
        declarations='integer s;',ports='u,y,r',directions='input u; output y; inout r;')
    return compile_sources({'dc_target.va':text},[instance(name,connections=connections or dict(u='u',y='y',r='0'))])
def run(body=None,sources=None,errors=None,times=None,atol=1e-12):
    p=program() if body is None else program(body)
    return transient(p,sources or {'u':[[0,1],[1,1]]},times or [0,0.5,0.5625,0.625,1],stop=1,max_step=1,
        source_errors=errors,vabstol=atol,reltol=0,kernel=KERNEL)
def volts(a,node='y'):
    i=a['nodes'].index(node);return [r['voltages'][i] for r in a['solutions']]
class DcTransition(unittest.TestCase):
    def test_held_flip_preserves_ramp(self):
        self.assertEqual(volts(run()),[0,0,0.5,1,1])
    def test_two_callsites_keep_independent_targets(self):
        self.assertEqual(volts(run('V(y)<+transition(s?V(u):0,0,0.125,0.125)+transition(s?0:V(u),0,0.25,0.25);')),[1,1,1.25,1.5,1])
    def test_instances_keep_local_held_states_and_sources(self):
        text=model('@(initial_step)s=0; @(timer(t0))s=1; V(y)<+transition(s?V(u):0,0,0.125,0.125);',
            declarations='integer s;parameter real t0=0.5;',ports='u,y,r',directions='input u;output y;inout r;')
        p=compile_sources({'instances.va':text},[
            instance('a',connections=dict(u='ua',y='ya',r='0')),
            instance('b',connections=dict(u='ub',y='yb',r='0'),parameters=dict(t0=0.75))])
        a=transient(p,{'ua':[[0,1],[1,1]],'ub':[[0,2],[1,2]]},[0,0.5625,0.8125,1],
            stop=1,max_step=1,vabstol=1e-12,reltol=0,kernel=KERNEL)
        self.assertEqual(volts(a,'ya'),[0,0.5,1,1])
        self.assertEqual(volts(a,'yb'),[0,0,1,2])
    def test_reset_reverses_held_target(self):
        text=model('@(initial_step)s=0; @(timer(0.25))s=1; @(timer(0.75))s=0; V(y)<+transition(s?V(u):0,0,0.125,0.125);',
            declarations='integer s;')
        p=compile_sources({'reset.va':text},[instance()])
        a=transient(p,{'u':[[0,1],[1,1]]},[0,0.3125,0.5,0.75,0.8125,0.875,1],stop=1,max_step=1,kernel=KERNEL,vabstol=1e-12,reltol=0)
        self.assertEqual(volts(a),[0,0.5,1,1,0.5,0,0])
    def test_future_and_middle_pulse_rejected(self):
        for points in [[[0,1],[0.75,1],[0.875,2],[1,1]],[[0,1],[0.25,2],[1,1]]]:
            with self.subTest(points=points),self.assertRaises(KernelError):
                run(sources={'u':points},times=[0,0.125])
    def test_error_and_zero_weight_dependency_rejected(self):
        for term in ['V(u)','0*V(u)']:
            with self.subTest(term=term),self.assertRaises(KernelError):
                run('V(y)<+transition(s?'+term+':0,0,0.125,0.125);',errors={'u':1e-9})
    def test_internal_target_rejected(self):
        for term in ['V(r)','0*V(r)']:
            p=program('V(r)<+1; V(y)<+transition(s?'+term+':0,0,0.125,0.125);',
                      connections=dict(u='u',y='y',r='internal'))
            with self.subTest(term=term),self.assertRaises(KernelError) as caught:
                transient(p,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
            self.assertEqual(caught.exception.detail['kind'],'unsupported_operator')
            self.assertIn('original driven nodes',caught.exception.detail['message'])
    def test_product_error_survives_gain(self):
        exact=F(0.9)*F(0.06666666666666667); rounded=float(exact)
        body=f'V(y)<+1073741824*(transition(s?V(u)*0.06666666666666667:0,0,0.125,0.125)-{rounded!r});'
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(body,sources={'u':[[0,0.9],[1,0.9]]},times=[0.75,1],atol=1e-10)
        result=run(body,sources={'u':[[0,0.9],[1,0.9]]},times=[0.75,1],atol=1e-5)
        for actual in volts(result):
            self.assertLessEqual(abs(F(actual)-2**30*(exact-F(rounded))),F(1e-5))
    def test_nonzero_shape_tube_stays_rejected(self):
        shape=[dict(time_numerator=str(t),time_denominator='1',value_V=1) for t in [0,1]]
        p=program()
        options=dict(stop=1,max_step=1,kernel=KERNEL,vabstol=1e-12,reltol=0,
                     source_shapes={'u':shape})
        with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
            transient(p,{'u':[[0,1],[1,1]]},[0,1],source_errors={'u':0.25},**options)
        a=transient(p,{'u':[[0,1],[1,1]]},[0,0.5625,1],source_errors={'u':0},**options)
        self.assertEqual(volts(a),[0,0.5,1])
    def test_old_held_and_source_selected_constant(self):
        self.assertEqual(volts(run('V(y)<+transition(s,0,0.125,0.125);')),[0,0,0.5,1,1])
        self.assertEqual(volts(run('V(y)<+transition(V(u)>0.5?1:0,0,0.125,0.125);')),[1]*5)
if __name__=='__main__':unittest.main()

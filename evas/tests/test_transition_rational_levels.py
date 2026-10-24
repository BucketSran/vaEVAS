"""Held rational transition levels survive interruption and retain error."""
GUARDS = ['TRANSITION', 'EVENT-ORDER', 'TIMER', 'COMPOSE', 'DYNAMICS']

import unittest
from fractions import Fraction as Q
from pathlib import Path
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

def compile_model(body,declarations='real a,b;'):
    return compile_sources({'rational-levels.va':'`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'+declarations+'analog begin '+body+' end endmodule'},[Instance('dut','m',dict(u='u',y='y'))])

def output(result):
    return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]

def program(target='0.5*a',extra='',expr='a',delay='0',gain='1'):
    return compile_model('@(initial_step)begin a=0;b=0;end @(timer(0.1))begin a=0.45*V(u);b=2*a;end @(timer(0.15))begin a='+target+';b=2*a;end '+extra+' V(y)<+'+gain+'*(transition('+expr+','+delay+',0.2,0.2)+transition(2*('+expr+'),'+delay+',0.2,0.2));')

def run(p,times=(0,.125,.175,.2,.249,.3,.5),**kwargs):
    args=dict(stop=.6,max_step=.05,kernel=KERNEL,vabstol=1e-12,reltol=0)
    args.update(kwargs)
    assert Path(args['kernel']).resolve()==KERNEL
    return transient(p,{'u':[[0,.16],[1,.16]]},list(times),**args)

def oracle(t,half=Q(1,2)):
    A=Q(.45)*Q(.16)
    t=Q(t)
    start=Q(.1)
    change=Q(.15)
    duration=Q(.2)
    if t<start:return Q(0)
    if t<change:return 3*A*(t-start)/duration
    value=A*(change-start)/duration
    origin=Q(0) if half>value/A else A
    target=half*A
    slope=(target-origin)/duration
    raw=value+slope*(t-change)
    return 3*(min(raw,target) if slope>0 else max(raw,target))

class RationalTransitionLevels(unittest.TestCase):
    def assert_oracle(self,result,expected,tol=Q(1,10**12)):
        for actual,want in zip(output(result),expected,strict=True):
            self.assertLessEqual(abs(Q(actual)-want),tol,(actual,str(want)))
    def test_interrupted_rational_levels_recover_matching_ends(self):
        times=[0,.125,.175,.2,.249,.3,.5]
        self.assert_oracle(run(program(),times),[oracle(t) for t in times])
    def test_reversal_uses_original_target_not_nominal_origin(self):
        times=[0,.125,.175,.2,.249,.3,.5]
        self.assert_oracle(run(program('-0.5*a'),times),[oracle(t,Q(-1,2)) for t in times])
    def test_held_selection_uses_original_selected_expression(self):
        times=[0,.125,.175,.2,.249,.3,.5]
        self.assert_oracle(run(program(expr='(a>0?a:0)'),times),[oracle(t) for t in times])
    def test_true_source_error_does_not_become_an_exact_level(self):
        with self.assertRaises(KernelError) as caught:
            run(program(),source_errors={'u':.001},vabstol=.01)
        self.assertEqual(caught.exception.detail['kind'],'unsupported_source_uncertainty')
    def test_internal_sample_uses_source_rounding_and_certified_transition_levels(self):
        p=compile_model('@(initial_step)begin a=0;b=0;end @(timer(0.1))a=V(z);@(timer(0.15))a=0.5*a;V(z)<+0.45*V(u);V(y)<+transition(a,0,0.2,0.2)+transition(2*a,0,0.2,0.2);',declarations='real a,b;electrical z;')
        result=run(p);y=result['nodes'].index('y')
        times=[0,.125,.175,.2,.249,.3,.5]
        self.assertEqual(result['transient']['times'],times)
        self.assertEqual(len(result['solutions']),len(times))
        self.assertEqual(len(result['transient']['states']),len(times))
        self.assertEqual(len(result['observation_evidence']['voltage_bounds_V']),len(times))
        # Physical z is the exact product of the binary64 literals. Sampling
        # rounds that product once; Fraction-to-float provides an independent
        # ties-even conversion. The later multiplication by1/2 is exact.
        A=Q(float(Q(.45)*Q(.16)));start=Q(.1);change=Q(.15);duration=Q(.2)
        events=result['transient']['events']
        expected=[('initial_step',0.,[0.,0.],[0.,0.]),('timer',.1,[0.,0.],[float(A),0.]),('timer',.15,[float(A),0.],[float(A/2),0.])]
        self.assertEqual([(e['kind'],e['time'],[v.hex() for v in e['before']],[v.hex() for v in e['after']]) for e in events],
                         [(kind,time,[v.hex() for v in before],[v.hex() for v in after]) for kind,time,before,after in expected])
        for time,solution,box in zip(times,result['solutions'],result['observation_evidence']['voltage_bounds_V'],strict=True):
            t=Q(time)
            if t<start:want=Q(0)
            elif t<change:want=3*A*(t-start)/duration
            else:
                held=A*(change-start)/duration;target=A/2
                want=3*min(held+target*(t-change)/duration,target)
            self.assertLessEqual(Q(box[y][0]),want);self.assertLessEqual(want,Q(box[y][1]))
            actual=Q(solution['voltages'][y])
            self.assertLessEqual(Q(box[y][0]),actual);self.assertLessEqual(actual,Q(box[y][1]))
            self.assertLessEqual(abs(actual-want),Q(1,10**12))
    def test_future_amplification_keeps_inherited_sample_error(self):
        p=compile_model('@(initial_step)begin a=0;b=0;c=0;end @(timer(0.1))a=0.45*V(u);@(timer(0.15))a=0.5*a;@(timer(0.175))b=V(z);@(timer(0.4))c=1000000000000*b;V(z)<+transition(a,0,0.2,0.2);V(y)<+c;',declarations='real a,b,c;electrical z;')
        with self.assertRaises(KernelError) as caught:
            run(p,times=[0,.125,.2,.5],vabstol=1e-8)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
        self.assertIn('forward error',caught.exception.detail['message'])
    def test_adjacent_distinct_end_levels_are_not_silently_coalesced(self):
        # The exact ends differ although their enclosures overlap. Keep the
        # existing independent-continuous-end policy; evaluate both lines.
        p=compile_model('@(initial_step)begin a=0;b=0;end @(timer(0.1))begin a=0.45*V(u);b=2*a;end @(timer(0.15))begin b=1.0000000000000002*a;a=0.5*a;end V(y)<+transition(a,0,0.2,0.2)+transition(b,0,0.2,0.2);')
        times=[0,.125,.175,.249,.3,.5]
        result=run(p,times)
        A=Q(.45)*Q(.16);d=Q(.2);t1=Q(.1);t2=Q(.15)
        wants=[]
        for t in map(Q,times):
            if t<t1:wants.append(Q(0));continue
            if t<t2:wants.append(3*A*(t-t1)/d);continue
            av=A*(t2-t1)/d;bv=2*av
            wants.append(min(A/2,av+A/2*(t-t2)/d)+min(Q(1.0000000000000002)*A,bv+Q(1.0000000000000002)*A*(t-t2)/d))
        self.assert_oracle(result,wants)

if __name__ == '__main__':
    unittest.main()

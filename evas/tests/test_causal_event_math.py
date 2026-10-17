"""Nonlinear event data remains causal while the electrical solve stays affine."""
GUARDS=['EVENT-CONDITIONS','COMPOSE','TIMED-OPERATOR']
from fractions import Fraction as Q
import json
import subprocess
import unittest
from evas import KernelError,compile_sources,transient
from test_affine import model,instance,KERNEL

class CausalEventMath(unittest.TestCase):
    def test_raw_predicate_math_cannot_piggyback_on_a_causal_product(self):
        # Raw IR must keep observer-only math out of every physical event
        # expression, even when another assignment selects sampled arithmetic.
        for start in [0.,.25]:
            for product in [False,True]:
                source=model(f'''@(initial_step) q=0;
                  @(timer({start},0,1e-12)) begin
                    {'a=V(u,r)*V(u,r);' if product else ''}
                    if(V(u,r)>0) q=1; else q=2;
                  end V(y,r)<+q;''','real a,q;')
                p=compile_sources({'predicate-math.va':source},[instance()]).to_dict()
                conditional=p['events'][0]['body'][-1]
                conditional['left']=dict(op='event_math',function='sqrt',
                    args=[conditional['left']],origin=p['events'][0]['origin'])
                request=dict(program=p,driven=['u'],samples=[],transient=dict(
                    pwl=[[[0,1],[1,1]]],output_times=[0,1],stop=1,max_step=1))
                with self.subTest(start=start,product=product):
                    r=subprocess.run([str(KERNEL)],input=json.dumps(request),text=True,capture_output=True)
                    self.assertNotEqual(r.returncode,0)
                    self.assertEqual(json.loads(r.stderr)['kind'],'unsupported_transient')

    def test_clocked_product_keeps_old_state_order_feedback_and_transition(self):
        source=model('''@(initial_step) q=0.1;
          @(timer(0.25,0.25,1e-12)) begin a=V(u,r)*V(u,r); q=a+0.25*q; end
          V(y,r)<+0.5*V(y,r)+transition(q,0,0.03125,0.03125);''','real a,q;')
        p=compile_sources({'causal.va':source},[instance()])
        times=[0,.375,.625,.875,1]
        r=transient(p,{'u':[[0,.5],[1,.5]]},times,stop=1,max_step=.25,kernel=KERNEL)
        level=Q(.1);expected=[2*level]
        for _ in range(3):level=Q(1,4)+level/4;expected.append(2*level)
        expected.append(expected[-1]) # The t=1 callback starts a continuous edge.
        for row,answer in zip(r['solutions'],expected):
            self.assertLessEqual(abs(Q(row['voltages'][p.nodes.index('y')])-answer),Q(1e-11))

    def test_input_band_survives_event_product_and_downstream_amplification(self):
        p=compile_sources({'gain.va':model('''@(initial_step) q=0;
          @(timer(0.25,0,1e-12)) q=V(u,r)*V(u,r); V(y,r)<+1000*q;''','real q;')},[instance()])
        args=dict(stop=1,max_step=1,kernel=KERNEL,source_errors={'u':.01},reltol=0)
        with self.assertRaisesRegex(KernelError,'at y'):
            transient(p,{'u':[[0,.5],[1,.5]]},[0,.5,1],vabstol=.1,**args)
        r=transient(p,{'u':[[0,.5],[1,.5]]},[0,.5,1],vabstol=20,**args)
        self.assertEqual(r['solutions'][-1]['voltages'][p.nodes.index('y')],250)

    def test_nonlinear_same_time_electrical_feedback_still_refuses(self):
        p=compile_sources({'loop.va':model('''@(initial_step) q=0.1;
          @(timer(0.25,0,1e-12)) q=V(y,r)*V(y,r); V(y,r)<+q;''','real q;')},[instance()])
        with self.assertRaisesRegex(KernelError,'unsupported_transient'):
            transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

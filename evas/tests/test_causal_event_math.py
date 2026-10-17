"""Nonlinear event data remains causal while the electrical solve stays affine."""
GUARDS=['EVENT-CONDITIONS','COMPOSE','TIMED-OPERATOR']
from fractions import Fraction as Q
import json
import subprocess
import unittest
from evas import KernelError,compile_sources,transient
from test_affine import model,instance,KERNEL

class CausalEventMath(unittest.TestCase):
    def test_normalized_sample_clipping_keeps_order_state_and_transition(self):
        # GAP06 original supply-normalization pattern. With u=.75, vss=.25,
        # vdd=1.25, x=1/2. q starts1/8 and follows(q+x)/2 at each timer.
        source=model('''@(initial_step) q=0.125;
          @(timer(0.25,0.25,1e-12)) begin
            span=V(vdd,r)-V(vss,r);
            if(span<0.125) span=0.125;
            x=clip01((V(u,r)-V(vss,r))/span);
            q=0.5*q+0.5*x;
          end V(y,r)<+transition(q,0,0.03125,0.03125);''',
          '''real span,x,q;
          analog function real clip01;
            input x; real x; begin
              if(x<0.0) clip01=0.0;
              else if(x>1.0) clip01=1.0; else clip01=x;
            end endfunction''',ports='u,vdd,vss,y,r',
          directions='input u,vdd,vss; output y; inout r;')
        p=compile_sources({'normalized-sampling.va':source},[instance(connections={
            'u':'u','vdd':'vdd','vss':'vss','y':'y','r':'0'})])
        result=transient(p,{'u':[[0,.75],[1,.75]],'vdd':[[0,1.25],[1,1.25]],
            'vss':[[0,.25],[1,.25]]},[0,.375,.625,.875,1],
            stop=1,max_step=.25,kernel=KERNEL)
        for row,answer in zip(result['solutions'],[Q(1,8),Q(5,16),Q(13,32),Q(29,64),Q(29,64)]):
            self.assertLessEqual(abs(Q(row['voltages'][p.nodes.index('y')])-answer),Q(1e-12))

        # Both clipping arms and the positive floor must use the same ordered
        # event values. Each case has a separate rational recurrence oracle.
        for u,vdd,vss,x in [(-.25,1.25,.25,Q(0)),(1.75,1.25,.25,Q(1)),
                              (.3125,.25,.25,Q(1,2))]:
            with self.subTest(u=u,vdd=vdd,vss=vss):
                result=transient(p,{'u':[[0,u],[1,u]],'vdd':[[0,vdd],[1,vdd]],
                    'vss':[[0,vss],[1,vss]]},[0,.375,.625,.875,1],
                    stop=1,max_step=.25,kernel=KERNEL)
                q=Q(1,8); answers=[q]
                for _ in range(3):q=(q+x)/2;answers.append(q)
                answers.append(q)
                for row,answer in zip(result['solutions'],answers):
                    self.assertLessEqual(abs(Q(row['voltages'][p.nodes.index('y')])-answer),Q(1e-12))

    def test_counter_ratio_reads_incremented_count_and_reset(self):
        # Samples see hit=1,0,1; the fourth timer resets. The mean is exactly
        # 1, 1/2, 2/3, 0 and each transition is finished before observation.
        p=compile_sources({'counter-ratio.va':model('''@(initial_step) begin n=0;hits=0;q=0;end
          @(timer(0.125,0.25,1e-12)) begin
            if(V(u,r)<0) begin n=0;hits=0;q=0;end
            else begin
              n=n+1;if(V(u,r)>0.5) hits=hits+1;
              if(n>0) q=(1.0*hits)/n;else q=0;
            end
          end V(y,r)<+transition(q,0,0.03125,0.03125);''',
          'integer n,hits;real q;')},[instance()])
        r=transient(p,{'u':[[0,1],[.25,1],[.3,0],[.5,0],[.55,1],[.75,1],[.8,-1],[1,-1]]},
          [0,.2,.45,.7,.95,1],stop=1,max_step=.25,kernel=KERNEL)
        for row,answer in zip(r['solutions'],[Q(0),Q(1),Q(1,2),Q(2,3),Q(0),Q(0)]):
            self.assertLessEqual(abs(Q(row['voltages'][p.nodes.index('y')])-answer),Q(1e-12))

    def test_division_uses_driven_values_and_retains_denominator_uncertainty(self):
        p=compile_sources({'denominator.va':model('''@(timer(0.25,0,1e-12)) begin
          span=V(u,r);q=1.0/span;end V(y,r)<+1000*q;''','real span,q;')},[instance()])
        r=transient(p,{'u':[[0,2],[1,2]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(r['solutions'][-1]['voltages'][p.nodes.index('y')],500)
        # A nominally positive divisor cannot erase a source band containing 0.
        with self.assertRaisesRegex(KernelError,'event_domain'):
            transient(p,{'u':[[0,2],[1,2]]},[0,.5,1],stop=1,max_step=1,
                      kernel=KERNEL,source_errors={'u':2.1},vabstol=3,reltol=0)
        # The nonzero denominator band must survive storage and amplification.
        with self.assertRaisesRegex(KernelError,'at y'):
            transient(p,{'u':[[0,2],[1,2]]},[0,.5,1],stop=1,max_step=1,
                      kernel=KERNEL,source_errors={'u':.1},vabstol=1,reltol=0)

    def test_unselected_division_arm_is_lazy_but_selected_zero_refuses(self):
        for condition in ['V(u,r)>0','V(u,r)<0']:
            p=compile_sources({'lazy-division.va':model(f'''@(timer(0.25,0,1e-12))
              q=({condition})?1.0:1.0/0.0;V(y,r)<+q;''','real q;')},[instance()])
            with self.subTest(condition=condition):
                if condition=='V(u,r)>0':
                    r=transient(p,{'u':[[0,2],[1,2]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
                    self.assertEqual(r['solutions'][-1]['voltages'][p.nodes.index('y')],1)
                else:
                    with self.assertRaisesRegex(KernelError,'division denominator is zero|event_domain'):
                        transient(p,{'u':[[0,2],[1,2]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)

    def test_division_by_electrical_unknown_still_refuses(self):
        p=compile_sources({'unknown-division.va':model('''@(timer(0.25,0,1e-12))
          q=1.0/V(y,r); V(y,r)<+q;''','real q;')},[instance()])
        with self.assertRaisesRegex(KernelError,'unsupported_transient'):
            transient(p,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

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

"""A proved unchanged t=0 seed retains the full ordinary event transaction."""
import os
from fractions import Fraction as Q
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient

GUARDS=['TRANSITION','EVENT-CONDITIONS','COMPOSE','EVENT-ORDER']
KERNEL=Path(os.environ.get('EVAS_INITIAL_SEED_KERNEL',str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))


def program(body,decl='real q,a,due;integer count;'):
    source='`include "disciplines.vams"\nmodule seed(u,y);input u;output y;electrical u,y,x;'+decl+'analog begin '+body+' end endmodule'
    return compile_sources({'initial-seed.va':source},[Instance('D','seed',dict(u='u',y='y'))])


def run(p,u=1.,times=(0,.25,1.25),sources=None,**options):
    args=dict(stop=1.5,max_step=.05,kernel=KERNEL,vabstol=1e-8,reltol=0)
    args.update(options)
    result=transient(p,sources or {'u':[[0,u],[2,u]]},list(times),**args)
    return result,[row['voltages'][result['nodes'].index('y')] for row in result['solutions']]


class InitialSeedInvariance(unittest.TestCase):
    def test_held_calendar_keeps_complete_zero_callback_once(self):
        p=program('@(initial_step)begin q=0;due=-1;count=0;end @(timer(0,1))begin if(V(u)>0)q=0;else q=0.5;count=count+1;end @(timer(due))q=1;V(y)<+transition(q,0,0.1,0.1)+count;')
        result,y=run(p)
        self.assertEqual(y,[1,1,2])
        self.assertEqual(sum(event['time']==0 for event in result['transient']['events']),1)
    def test_unselected_initial_internal_arm_runs_after_source_changes(self):
        p=program('@(initial_step)begin q=0;a=0.5;end @(timer(0,1))begin if(V(u)>0)q=0;else q=V(x);end V(x)<+transition(a,0,0.1,0.1);V(y)<+transition(q,0,0.1,0.1);')
        _,y=run(p,sources={'u':[[0,1],[.5,1],[.6,-1],[2,-1]]})
        self.assertEqual(y,[0,0,.5])
    def test_unknown_nonseed_history_condition_can_join_before_a_proved_reset(self):
        p=program('@(initial_step)begin q=0.5;a=0;end @(timer(0,1))begin if(V(x)>0)count=1;else count=2;if(V(u)>0)q=0.5;else q=0.125*count;end V(x)<+transition(a,0,0.1,0.1);V(y)<+transition(q,0,0.1,0.1)+count;')
        _,y=run(p)
        self.assertEqual(y,[2.5,2.5,2.5])
    def test_reachable_history_dependent_seed_change_keeps_bootstrap_rejection(self):
        p=program('@(initial_step)begin q=0;a=0.5;end @(timer(0,1))begin if(V(u)>0)q=0;else q=V(x);end V(x)<+transition(a,0,0.1,0.1);V(y)<+transition(q,0,0.1,0.1);')
        with self.assertRaisesRegex(KernelError,'bootstrap events must read only held state'):
            run(p,u=-1.)
    def test_rational_changed_seed_retains_bounded_history(self):
        body='@(initial_step)q=0;@(timer(0,1))q=q+0.03+0.09*V(u);V(y)<+transition(q,0,0.1,0.1);'
        delta=Q(.03)+Q(.09)*Q(.2)
        self.assertNotEqual(delta,Q(float(delta)))
        result,y=run(program(body),u=.2)
        node=result['nodes'].index('y')
        boxes=result['observation_evidence']['voltage_bounds_V']
        for actual,box,want in zip(y,boxes,[delta,delta,2*delta],strict=True):
            self.assertLessEqual(abs(Q(actual)-want),Q(1e-8))
            lo,hi=map(Q,box[node])
            self.assertLessEqual(lo,want)
            self.assertGreaterEqual(hi,want)
        self.assertLess(boxes[0][node][0],boxes[0][node][1])
        amplified=body.replace('V(y)<+transition','V(y)<+1000000000000*transition')
        with self.assertRaises(KernelError) as caught:
            run(program(amplified),u=.2)
        self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
        self.assertIn('forward error',caught.exception.detail['message'])
    def test_initial_timer_or_is_not_proved_by_replaying_one_body_twice(self):
        body='begin if(V(u)>0)q=1-q;else q=0;end V(y)<+transition(q,0,0.1,0.1);'
        with self.assertRaisesRegex(CompileError,'mixed initialization'):
            program('@(initial_step or timer(0))'+body)
        # The raw shared IR also retains the boundary even if a producer does
        # not perform the frontend's earlier mixed-initialization rejection.
        p=program('@(timer(0))'+body).to_dict()
        timer=p['events'][0]['trigger']
        p['events'][0]['trigger']={'kind':'or','triggers':[{'kind':'initial_step'},timer]}
        from evas import runtime
        with self.assertRaisesRegex(KernelError,'cannot order an initial/timer OR body'):
            runtime._invoke(dict(program=p,driven=['u'],samples=[],transient=dict(
                pwl=[[[0,1],[2,1]]],output_times=[0,.25,1.25],stop=1.5,max_step=.05)),KERNEL,120)
    def test_changed_point_seed_keeps_held_calendar_bootstrap_rejection(self):
        p=program('@(initial_step)begin q=0;due=2;end @(timer(0))q=1;@(timer(due))q=0;V(y)<+transition(q,0,0.1,0.1);')
        with self.assertRaisesRegex(KernelError,'calendar independent of held state'):
            run(p)
    def test_ordinary_zero_integer_failure_is_not_skipped(self):
        p=program('@(initial_step)begin q=0;due=2;count=2147483647;end @(timer(0))begin count=count+1;if(V(u)>0)q=0;else q=1;end @(timer(due))q=1;V(y)<+transition(q,0,0.1,0.1);')
        with self.assertRaises(KernelError) as caught:
            run(p)
        self.assertEqual(caught.exception.detail['kind'],'state_range')
    def test_proved_equal_seed_does_not_hide_later_nominal_roundoff(self):
        for gain in [1,10**12]:
            with self.subTest(gain=gain):
                p=program('@(initial_step)begin q=0.45;p=0;due=2;end @(timer(0))q=q+0.1-0.1;@(timer(0.5))p='+str(gain)+'*q;@(timer(due))q=0;V(y)<+transition(q,0,0.1,0.1)+p;',decl='real q,p,due;')
                if gain==1:
                    _,y=run(p,times=(0,.25,.75))
                    self.assertAlmostEqual(y[-1],.9,places=12)
                else:
                    with self.assertRaises(KernelError) as caught:
                        run(p,times=(0,.25,.75))
                    self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
                    self.assertIn('forward error',caught.exception.detail['message'])
    def test_nonseed_initial_error_survives_future_amplification(self):
        for gain in [1,10**12]:
            with self.subTest(gain=gain):
                p=program('@(initial_step)begin q=0;a=0;p=0;due=2;end @(timer(0))begin if(V(u)>0)q=0;else q=1;a=0.45*V(u);end @(timer(0.25))q=1;@(timer(0.5))p='+str(gain)+'*a;@(timer(due))q=0;V(y)<+transition(q,0,0.125,0.5)+p;',decl='real q,a,p,due;')
                if gain==1:
                    _,y=run(p,u=.16,times=(0,.375,.75))
                    self.assertAlmostEqual(y[-1],1.072,places=12)
                else:
                    with self.assertRaises(KernelError) as caught:
                        run(p,u=.16,times=(0,.375,.75))
                    self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
                    self.assertIn('forward error',caught.exception.detail['message'])


if __name__=='__main__':unittest.main()

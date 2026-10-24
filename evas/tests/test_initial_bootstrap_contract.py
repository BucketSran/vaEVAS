"""IR33 cold seeds preserve the ordinary timer calendar and unrelated history."""
import unittest
from evas import KernelError
from test_initial_seed_invariance import program, run
import test_transition_initialization as initialization_tests
from test_transition import run_transition

class InitialBootstrapContract(unittest.TestCase):
    def test_changed_seed_preserves_the_unique_zero_occurrence_and_future_due(self):
        # q becomes 1 at zero. due=2 is after stop, so every sample is 1.
        # IR33 also retains the actual initial assignment record separately.
        p=program('@(initial_step)begin q=0;due=2;end @(timer(0))q=1;@(timer(due))q=0;V(y)<+transition(q,0,0.1,0.1);')
        result,y=run(p)
        self.assertEqual(y,[1,1,1])
        initial=[e for e in result['transient']['events'] if e['kind']=='initial_step']
        timers=[e for e in result['transient']['events'] if e['kind']!='initial_step']
        self.assertEqual(len(initial),1)
        self.assertEqual([(e['time'],e['before'],e['after']) for e in timers],[(0,[0,2],[1,2])])
        # Extending this independent request must actually retain timer(due).
        result,y=run(p,times=(0,.25,1.25,2.25),stop=2.5,sources={'u':[[0,1],[3,1]]})
        self.assertEqual(y,[1,1,1,0])
        self.assertEqual([e['time'] for e in result['transient']['events'] if e['kind']!='initial_step'],[0,2])

    def test_changed_transition_keeps_unrelated_integral_ic_and_future_held_timer(self):
        result=run_transition('@(initial_step)begin a=0;b=0.5;end @(timer(0,0,0.001))a=1;@(timer(b,0,0.001))b=b+1;V(y,r)<+transition(a,0,0.5,0.5)+idt(1,0.75);',[0,.25,1],1)
        self.assertEqual(initialization_tests.FinalInitialHistory().values(result),[1.75,2,2.75])
        self.assertEqual([e['time'] for e in result['transient']['events'] if e['kind']!='initial_step'],[0,.5])

    def test_unchanged_zero_seed_retains_initial_gate_and_complete_callback(self):
        p=program('@(initial_step)begin q=0;due=-1;count=0;end @(timer(0,1))begin if(V(u)>0)q=0;else q=0.5;count=count+1;end @(timer(due))q=1;V(y)<+transition(q,0,0.1,0.1)+count;')
        result,y=run(p)
        self.assertEqual(y,[1,1,2])
        self.assertEqual([e['time'] for e in result['transient']['events'] if e['kind']!='initial_step'],[0,1])

    def test_selected_internal_history_seed_read_keeps_bootstrap_rejection(self):
        p=program('@(initial_step)begin q=0;a=0.5;end @(timer(0,1))begin if(V(u)>0)q=0;else q=V(x);end V(x)<+transition(a,0,0.1,0.1);V(y)<+transition(q,0,0.1,0.1);')
        with self.assertRaisesRegex(KernelError,'bootstrap events must read only held state'):
            run(p,u=-1)

    def test_changed_seed_does_not_admit_a_history_dependent_cross_calendar(self):
        with self.assertRaises(KernelError):
            run_transition('@(initial_step)begin a=0;b=0.5;end @(timer(0,0,0.001))a=1;@(cross(V(u,r)-V(e,r),1))b=b+1;V(e,r)<+idt(1,0.75);V(y,r)<+transition(a,0,0.5,0.5);',[0,1],1,declarations='real a,b;electrical e;')

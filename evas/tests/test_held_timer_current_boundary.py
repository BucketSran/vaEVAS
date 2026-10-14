"""Changed held calendars must retain current leaf-consumption identity."""
GUARDS = ['TIMER', 'EVENT-ORDER', 'COMPOSE']
import unittest
from evas import KernelError
from test_transition_initialization import execute, assert_exact_node


class HeldTimerCurrentBoundary(unittest.TestCase):
    def test_new_current_leaf_is_not_silently_dropped(self):
        cases = [
            ('@(initial_step) begin b=0.5; n=0; end @(timer(0,0,0)) b=0; @(timer(b,0,0.001)) n=n+1;', 'real b; integer n;'),
            ('@(initial_step) begin b=0.75; n=0; end @(timer(0.5,0,0)) b=0.5; @(timer(b,0,0.001)) n=n+1;', 'real b; integer n;'),
            ('@(initial_step) begin b=0.5; en=0; n=0; end @(timer(0.5,0,0)) en=1; @(timer(b,0,0.001,en)) n=n+1;', 'real b; integer en,n;'),
            ('@(initial_step) begin b=0; n=0; end @(timer(0.5,0,0)) b=0.5; @(timer(b,0,0.001)) n=n+1;', 'real b; integer n;'),
            ('@(initial_step) begin b=0.75; n=0; end @(timer(0.5,0,0) or timer(b,0,0.001)) begin b=0.5; n=n+1; end', 'real b; integer n;'),
        ]
        for body, decl in cases:
            for suffix in ['V(z,r)<+n;', 'V(z,r)<+idt(V(u,r),0); @(cross(V(z,r)-2,1)) n=n;']:
                with self.subTest(body=body, history='idt' in suffix), self.assertRaises(KernelError) as caught:
                    execute(body+' V(y,r)<+n; '+suffix, decl)
                self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
                self.assertIn('unconsumed held timer', caught.exception.detail['message'])

    def test_current_consumed_leaf_can_change_period(self):
        for body, count, times in [
            ('@(initial_step) begin b=0; p=0.5; n=0; end @(timer(b,p,0.001)) begin n=n+1; p=0.25; end', lambda t: 1+t//(1/4), [0.,.25,.5,.75,1.]),
            ('@(initial_step) begin b=0; p=0.5; n=0; end @(timer(b,p,0.001)) begin n=n+1; if(n==2) p=0.25; end', lambda t: 1+(t>=.5)+(t>=.75)+(t>=1), [0.,.5,.75,1.]),
        ]:
            result=execute(body+' V(y,r)<+n; V(z,r)<+n;', 'real b,p; integer n;')
            assert_exact_node(self,result,'y',count)
            self.assertEqual([e['time'] for e in result['transient']['events']], times)

    def test_past_future_and_noop_keep_their_original_calendar(self):
        for start, update, expected in [(.75,.25,[.5]), (.75,.875,[.5,.875]), (.75,.75,[.5,.75])]:
            result=execute(f'@(initial_step) begin b={start}; n=0; end @(timer(0.5,0,0)) b={update}; @(timer(b,0,0.001)) n=n+1; V(y,r)<+n; V(z,r)<+n;', 'real b; integer n;')
            self.assertEqual([e['time'] for e in result['transient']['events']], expected)
            assert_exact_node(self,result,'y',lambda t: int(update>=.5 and t>=update))


if __name__ == '__main__': unittest.main()

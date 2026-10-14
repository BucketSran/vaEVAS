"""Exact-zero held calendars commit their consumed identity and final seed."""
GUARDS=['TRANSITION','EVENT-ORDER','TIMER','DYNAMICS']
import unittest
from fractions import Fraction as Q
from evas import KernelError
from test_transition_initialization import execute, assert_exact_node, TIMES

class HeldTransitionInitialization(unittest.TestCase):
    def test_dynamic_zero_and_independent_integral(self):
        for start in ['0','s']:
            r=execute('@(initial_step) begin s=0; q=0; end '
                f'@(timer({start},0,0.001)) q=1; '
                'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+idt(V(u,r),0.75);','real s,q;')
            assert_exact_node(self,r,'y',lambda t: 1)
            assert_exact_node(self,r,'z',lambda t: Q(3,4)+t*t/2)
            self.assertEqual(len(r['transient']['events']),1)

    def test_self_disable_consumes_original_zero(self):
        r=execute('@(initial_step) begin s=0; en=1; n=0; end '
            '@(timer(s,0.25,0.001,en)) begin n=n+1; en=0; end '
            'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s; integer en,n;')
        assert_exact_node(self,r,'y',lambda t: 1)
        assert_exact_node(self,r,'z',lambda t: 1)
        self.assertEqual([e['time'] for e in r['transient']['events']],[0.])

    def test_move_start_replaces_future(self):
        r=execute('@(initial_step) begin s=0; en=1; n=0; end '
            '@(timer(s,0,0.001,en)) begin n=n+1; if(n==1) s=0.5; else en=0; end '
            'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s; integer en,n;')
        assert_exact_node(self,r,'z',lambda t: 1+(t>=Q(1,2)))
        assert_exact_node(self,r,'y',lambda t: 1+min(Q(1),max(Q(0),8*(t-Q(1,2)))))
        self.assertEqual([e['time'] for e in r['transient']['events']],[0.,.5])

    def test_period_change_consumes_zero_once(self):
        r=execute('@(initial_step) begin s=0; p=0.5; n=0; end '
            '@(timer(s,p,0.001)) begin n=n+1; p=0.25; end '
            'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s,p; integer n;')
        assert_exact_node(self,r,'z',lambda t: 1+t//Q(1,4))
        self.assertEqual([e['time'] for e in r['transient']['events']],[0.,.25,.5,.75,1.])

    def test_other_future_timer_and_declaration_order(self):
        first='@(timer(s,0,0.001)) begin q=1; b=0.75; end '
        second='@(timer(b,0,0.001)) n=n+1; '
        for ordered in [first+second,second+first]:
            r=execute('@(initial_step) begin s=0; b=0.5; q=0; n=0; end '+ordered+
                'V(y,r)<+transition(q,0,0.125,0.125); V(z,r)<+n;', 'real s,b,q; integer n;')
            assert_exact_node(self,r,'y',lambda t: 1)
            assert_exact_node(self,r,'z',lambda t: int(t>=Q(3,4)))
            self.assertEqual([e['time'] for e in r['transient']['events']],[0.,.75])

    def test_duplicate_or_zero_runs_body_once(self):
        r=execute('@(initial_step) begin s=0; n=0; end '
            '@(timer(s,0,0.001) or timer(0,0,0)) n=n+1; '
            'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s; integer n;')
        assert_exact_node(self,r,'y',lambda t: 1)
        assert_exact_node(self,r,'z',lambda t: 1)
        events=r['transient']['events'];self.assertEqual(len(events),1)
        self.assertEqual(len(events[0]['fired_triggers']),2)

    def test_seed_noop_cannot_hide_new_zero_timer(self):
        for body in ['b=0;', 'b=0; n=0;', 'b=0; if(s==0) n=n; else n=1;']:
            with self.subTest(body=body), self.assertRaises(KernelError) as caught:
                execute('@(initial_step) begin s=0; b=0.5; n=0; end '
                    '@(timer(s,0,0.001)) begin '+body+' end '
                    '@(timer(b,0,0.001)) n=n+1; '
                    'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s,b; integer n;')
            self.assertEqual(caught.exception.detail['kind'],'unsupported_initial_history')
            self.assertIn('unconsumed same-time',caught.exception.detail['message'])

    def test_new_zero_timer_is_not_silently_lost(self):
        with self.assertRaises(KernelError) as caught:
            execute('@(initial_step) begin s=0; b=0.5; n=0; end '
                '@(timer(s,0,0.001)) begin n=n+1; b=0; end '
                '@(timer(b,0,0.001)) n=n+1; '
                'V(y,r)<+transition(n,0,0.125,0.125); V(z,r)<+n;', 'real s,b; integer n;')
        self.assertEqual(caught.exception.detail['kind'],'unsupported_initial_history')
        self.assertIn('unconsumed same-time',caught.exception.detail['message'])

if __name__=='__main__': unittest.main()

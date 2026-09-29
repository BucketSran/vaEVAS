"""Independent affine simultaneous-event equations and rejection controls."""
from fractions import Fraction as Q
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from test_timer import run_timer


class SettlementContracts(unittest.TestCase):
    def test_two_stage_chain_is_independent_of_block_order(self):
        blocks=['@(timer(0.5,0,0.001)) n=n+1;',
                '@(timer(0.5,0,0.001)) a=V(y,r);',
                '@(timer(0.5,0,0.001)) b=V(z,r);']
        for order in [blocks,blocks[::-1]]:
            source=model('''@(initial_step) begin n=0; a=0; b=0; end
                '''+''.join(order)+'V(y,r)<+n; V(z,r)<+a; V(w,r)<+b;',
                'integer n; real a,b; electrical z,w;')
            result=run_timer(source,stop=1,times=[0,0.5,1])
            self.assertEqual(result['transient']['states'],[[0,0,0],[1,1,1],[1,1,1]])

    def test_cross_instance_chain_is_independent_of_instance_order(self):
        producer=model('''@(initial_step) n=0; @(timer(0.5,0,0.001)) n=n+1;
                            V(y,r)<+n;''','integer n;')
        receiver=model('''@(initial_step) s=0; @(timer(0.5,0,0.001)) s=V(u,r);
                            V(y,r)<+s;''','real s;').replace('module m(', 'module reader(')
        inst=[instance('a',connections=dict(u='u',y='a',r='0')),
              instance('b','reader',dict(u='a',y='b',r='0')),
              instance('c','reader',dict(u='b',y='c',r='0'))]
        for order in [inst,inst[::-1]]:
            p=compile_sources({'a.va':producer,'b.va':receiver},order)
            r=transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)
            volts=dict(zip(r['nodes'],r['solutions'][-1]['voltages']))
            self.assertEqual([volts[n] for n in ['a','b','c']],[1,1,1])

    def test_unique_feedback_including_noncontractive_has_closed_form(self):
        for gain in [0.5,-0.5,2.0]:
            source=model(f'''@(initial_step) begin n=0; s=0; end
                @(timer(0.5,0.5,0.001)) begin n=n+1; s={gain}*V(y,r)+n; end
                V(y,r)<+s;''','integer n; real s;')
            r=run_timer(source,stop=1,times=[0,0.5,1])
            for count,states in enumerate(r['transient']['states']):
                self.assertEqual(states[0],count)
                self.assertAlmostEqual(states[1],float(Q(count)/(1-Q(gain))),places=12)
            self.assertEqual(len(r['transient']['events']),2)

    def test_local_statement_order_is_preserved_without_double_commit(self):
        source=model('''@(initial_step) begin n=0; s=0; end
            @(timer(0.5,0,0.001)) begin n=n+1; n=n+1; s=V(y,r); s=0.5*s+n; end
            V(y,r)<+s;''','integer n; real s;')
        r=run_timer(source,stop=1,times=[0,1])
        self.assertEqual(r['transient']['states'][-1],[2,4])

    def test_no_unique_same_time_solution_is_rejected(self):
        for bias in [0,1]:
            source=model(f'''@(initial_step) s=0;
                @(timer(0.5,0,0.001)) s=V(y,r)+{bias}; V(y,r)<+s;''','real s;')
            with self.assertRaises(KernelError) as caught:
                run_timer(source,stop=1,times=[0,1])
            self.assertEqual(caught.exception.detail['kind'],'singular_system')

    def test_inactive_event_state_is_held_during_another_event(self):
        source=model('''@(initial_step) begin n=0; s=-1; end
            @(timer(0.5,0,0.001)) n=n+1;
            @(timer(0.75,0,0.001)) s=V(y,r);
            V(y,r)<+n; V(z,r)<+s;''','integer n; real s; electrical z;')
        r=run_timer(source,stop=1,times=[0,0.5,0.75,1])
        self.assertEqual(r['transient']['states'],[[0,-1],[1,-1],[1,1],[1,1]])

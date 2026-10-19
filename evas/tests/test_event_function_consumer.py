"""Public event consumers of typed function assignments, with independent answers."""
GUARDS = ["LANG", "LIN", "CROSS", "COMPOSE"]
import os, unittest
from pathlib import Path
from fractions import Fraction
from evas import compile_sources, Instance, transient, CompileError, KernelError
EVAS=Path(__file__).resolve().parents[1]
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(EVAS/'rust_core/target/debug/evas-kernel')))
PREFIX='`include "disciplines.vams"\nmodule m(y); output y; electrical y; real s; '
def program(definition, rhs):
    text=PREFIX+definition+' analog begin @(initial_step) s=0; @(timer(0.25)) s='+rhs+'; V(y)<+s; end endmodule'
    return compile_sources({'event-function-consumer.va':text},[Instance('dut','m',{'y':'y'})])
def values(p):
    r=transient(p,{},[0,.5,1],stop=1,max_step=.1,kernel=KERNEL)
    return [row['voltages'][r['nodes'].index('y')] for row in r['solutions']]
class EventFunctionConsumer(unittest.TestCase):
    def test_legacy_real_formal_local_return_assignments_reach_event_runtime(self):
        # x=3, t=3/2, f=t+1/4=7/4, then hold the event result.
        definition='analog function real f; input x; real x,t; begin t=x/2; f=t+0.25; end endfunction'
        self.assertEqual(values(program(definition,'f(3)')),[0,float(Fraction(7,4)),float(Fraction(7,4))])
    def test_legacy_real_branch_and_nested_function_resource_tree(self):
        definition=('analog function real h; input x; real x; begin if(x>1) h=1; else h=x; end endfunction '
                    'analog function real f; input x; real x,t; begin t=h(x); f=2*t; f=f+h(0.25); end endfunction')
        self.assertEqual(values(program(definition,'f(3)+0.5')),[0,2.75,2.75])
    def test_integer_formal_local_return_assignment_boundaries_in_event(self):
        # +2.5 formal rounds to3; local 3/2 truncates to1; result1/2 is0.
        definition='analog function integer f; input x; integer x,t; begin t=x/2; f=t/2; end endfunction'
        self.assertEqual(values(program(definition,'f(2.5)+1')),[0,1,1])
    def test_integer_real_formal_rounds_at_return_and_signed_ties(self):
        definition='analog function integer f; input x; real x; begin f=x; end endfunction'
        for actual,expected in [('2.5',3),('-2.5',-3),('2147483647.4999998',2147483647),('-2147483648.4999995',-2147483648)]:
            with self.subTest(actual=actual):self.assertEqual(values(program(definition,'f('+actual+')')),[0,expected,expected])
    def test_hidden_function_history_and_missing_names_stay_rejected(self):
        for rhs in ('transition(x,0,1,1)','ddt(x)','missing','V(y)','function_assign(x)'):
            definition='analog function real f; input x; real x,t; begin t='+rhs+'; f=1; end endfunction'
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):program(definition,'f(1)')
    def test_unused_copy_in_and_hidden_integer_overflow_stay_rejected(self):
        pairs=[('analog function integer f; input x; integer x; begin f=1; end endfunction','f(2147483647.5)'),
               ('analog function integer f; input x; integer x,t; begin t=x+1; f=1; end endfunction','f(2147483647)')]
        for definition,rhs in pairs:
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):program(definition,rhs)
    def test_hidden_event_operator_and_unknown_node_stay_rejected(self):
        for rhs in ('1+0*transition(1,0,1,1)','1+0*V(undeclared)'):
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):program('',rhs)
    def test_function_sample_keeps_original_source_error_box(self):
        text=('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; real s; '
              'analog function real f; input x; real x; begin f=x/2; end endfunction '
              'analog begin @(initial_step) s=0; @(timer(0.25)) s=f(V(u)); V(y)<+s; end endmodule')
        p=compile_sources({'function-source-box.va':text},[Instance('dut','m',{'u':'u','y':'y'})])
        result=transient(p,{'u':[[0,1],[1,1]]},[0,.5,1],stop=1,max_step=.1,kernel=KERNEL)
        self.assertEqual([v['voltages'][result['nodes'].index('y')] for v in result['solutions']],[0,.5,.5])
        amplified=text.replace('V(y)<+s','V(y)<+1e6*s')
        p=compile_sources({'function-amplified-box.va':amplified},[Instance('dut','m',{'u':'u','y':'y'})])
        # Original +/-0.01 input band gives +/-5000 V after the gain.
        with self.assertRaisesRegex(KernelError,'(event|waveform)_accuracy'):
            transient(p,{'u':[[0,1],[1,1]]},[0,.5,1],stop=1,max_step=.1,
                      source_errors={'u':.01},kernel=KERNEL)
    def test_function_expansion_budget_survives_two_fresh_public_retries(self):
        definition='analog function real f; input x; real x; begin f=x+x; end endfunction'
        rhs='1'
        for _ in range(20):rhs='f('+rhs+')'
        for _ in range(2):
            with self.assertRaises(CompileError) as caught:program(definition,rhs)
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
    def test_real_function_parameter_condition_keeps_dead_math_unexecuted(self):
        definition='analog function real f; input x; real x; begin f=x; end endfunction'
        text=PREFIX+definition+' analog begin @(initial_step) s=0; @(timer(0.25)) if(f(0)>0) s=sqrt(-1.0); else s=2; V(y)<+s; end endmodule'
        p=compile_sources({'function-dead-math.va':text},[Instance('dut','m',{'y':'y'})])
        self.assertEqual(values(p),[0,2,2])
    def test_twelve_real_function_choices_keep_original_compact_source_consumer(self):
        definition='analog function real f; input x; real x; begin f=(x>0)?1.0:0.0; end endfunction'
        choices='+'.join('f(V(u)-'+str(k+1)+'.0/16)' for k in range(12))
        text=('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; real s; '+definition+
              ' analog begin @(initial_step) s=0; @(timer(0.25)) s='+choices+'; V(y)<+s; end endmodule')
        p=compile_sources({'function-compact-source.va':text},[Instance('dut','m',{'u':'u','y':'y'})])
        result=transient(p,{'u':[[0,.6],[1,.6]]},[0,.5,1],stop=1,max_step=.1,kernel=KERNEL)
        # 0.6 exceeds exactly9 thresholds, k/16 for k=1..9.
        self.assertEqual([v['voltages'][result['nodes'].index('y')] for v in result['solutions']],[0,9,9])
    def test_real_event_work_shares_activated_original_owner_and_does_not_refund(self):
        from unittest.mock import patch
        from evas.native_audit import NativeAudit
        original=NativeAudit.__init__
        owners=[]
        def remember(owner):
            original(owner)
            owners.append(owner)
        first=('module first(y); output y; electrical y; integer n; analog begin '
               '@(initial_step) n=0; @(timer(0.5)) if(n<255)n=n+1; '
               'V(y)<+transition((n/2)%2,0,0.01,0.01); end endmodule ')
        definition='analog function real f; input x; real x; begin f=x/2; end endfunction '
        events=''.join('@(timer('+str((k+1)/1024)+')) s=f(1);' for k in range(400))
        text=('`include "disciplines.vams"\n'+first+'module second(z);output z;electrical z;real s; '+definition+
              'analog begin @(initial_step)s=0;'+events+'V(z)<+s;end endmodule')
        for _ in range(2):
            with patch.object(NativeAudit,'__init__',remember):
                with self.assertRaises(CompileError) as caught:
                    compile_sources({'same-owner-event.va':text},[Instance('A','first',{'y':'y'}),Instance('B','second',{'z':'z'})])
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
            owner=owners[-1]
            self.assertTrue(owner.active)
            self.assertGreater(owner.used,100000)
            self.assertGreater(owner.counts['function_assignment_metadata'],0)
            self.assertTrue(all(view.owner is owner for view in owner.event_views.values()))
            used=owner.used
            for _ in range(2):
                with self.assertRaises(CompileError):owner.debit('failed_request_recheck',0)
                self.assertEqual(owner.used,used)
            print('real function event exhaustion used=',used,'new_metadata=',owner.counts['function_assignment_metadata'])
if __name__=='__main__':unittest.main()

"""Bounded self updates shared by event blocks, with independent count answers."""
GUARDS = ['CROSS', 'EVENT-ORDER', 'EVENT-CONDITIONS']
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

from paper_case_inputs import case_source

HC01 = case_source('EV-HC-01')


class SharedCounter(unittest.TestCase):
    def test_original_constant_initialization_hysteresis_counts(self):
        p=compile_sources({'hc01.va':HC01},[Instance('dut','paper_hc',{'in':'in','out':'out','count':'count'})])
        result=transient(p,{'in':[[0,.1],[2e-6,.9],[4e-6,.1]]},[0,2e-6,4e-6],stop=4e-6,max_step=4e-6,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[0,0],[1,1],[0,2]])
        self.assertEqual([e['event'] for e in result['transient']['events']],[0,1])

    def test_self_updates_keep_statement_order_and_instance_isolation(self):
        source=model('''@(initial_step) n=4;
          @(timer(0.25)) begin n=n+1; n=n+2; end
          @(timer(0.75)) n=n-1; V(y,r)<+n;''','integer n;')
        p=compile_sources({'counter.va':source},[instance('a',connections=dict(u='u',y='a',r='0')),instance('b',connections=dict(u='u',y='b',r='0'))])
        result=transient(p,{'u':[[0,0],[1,0]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[4,4],[7,7],[6,6]])

    def test_simultaneous_self_updates_are_atomic_conflicts(self):
        source=model('''@(initial_step) n=0;
            @(timer(0)) n=n+1; @(timer(0)) n=n+1; V(y,r)<+n;''','real n;')
        p=compile_sources({'counter-conflict.va':source},[instance()])
        with self.assertRaisesRegex(KernelError,'event_conflict'):
            transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_integer_self_updates_check_intermediate_range(self):
        source=model('@(initial_step) n=2147483647;\n            @(timer(0)) begin n=n+1; n=n-1; end\n            @(timer(0.75)) n=n-1; V(y,r)<+n;', 'integer n;')
        p=compile_sources({'counter-range.va':source},[instance()])
        with self.assertRaisesRegex(KernelError,'state_range'):
            transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_shared_scaled_self_update_uses_previous_accepted_state(self):
        source=model('''@(initial_step) begin n=0; q=1; end
          @(timer(0.25)) begin n=n+1; q=2; end
          @(timer(0.75)) n=2*n+1; V(y,r)<+n;''','real n,q;')
        p=compile_sources({'counter-scaled.va':source},[instance()])
        result=transient(p,{'u':[[0,0],[1,0]]},[0,.5,1],stop=1,max_step=1,kernel=KERNEL)
        self.assertEqual(result['transient']['states'],[[0,1],[1,2],[3,2]])

    def test_later_block_reads_accepted_states_and_direct_source(self):
        cases = [('q-q', 0), ('0*q', 0), ('(1e-200*1e-200)*q', 0),
                 ('n+q-q', 1), ('n+0*q', 1), ('0*n+1', 1), ('n+V(u,r)', 1.75)]
        for rhs, final in cases:
            source=model(f'''@(initial_step) begin n=0; q=1; end
              @(timer(0.25)) begin n=n+1; q=2; end
              @(timer(0.75)) n={rhs}; V(y,r)<+n;''','real n,q;')
            with self.subTest(rhs=rhs):
                p=compile_sources({'counter-accepted.va':source},[instance()])
                result=transient(p,{'u':[[0,0],[1,1]]},[0,.5,1],
                                 stop=1,max_step=1,kernel=KERNEL)
                self.assertEqual(result['transient']['states'],[[0,1],[1,2],[final,2]])
                self.assertEqual([e['event'] for e in result['transient']['events']],[0,1])
                y=result['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in result['solutions']],[0,1,final])

    def test_simultaneous_other_state_reads_keep_structural_dependencies(self):
        # Cancellation, zero factors and underflow cannot erase another
        # selected block's writer from a same-time read dependency.
        for rhs in ['q-q', '0*q', '(1e-200*1e-200)*q', 'n+q-q', 'n+0*q']:
            source=model(f'''@(initial_step) begin n=1; q=1; end
              @(timer(0.75)) q=2;
              @(timer(0.75)) n={rhs}; V(y,r)<+n;''','real n,q;')
            with self.subTest(rhs=rhs):
                p=compile_sources({'counter-simultaneous.va':source},[instance()])
                with self.assertRaisesRegex(KernelError,'unsupported_cross'):
                    transient(p,{'u':[[0,0],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

    def test_waveform_operator_in_event_assignment_stays_rejected(self):
        source=model('''@(initial_step) begin n=0; q=1; end
          @(timer(0.25)) begin n=n+1; q=2; end
          @(timer(0.75)) n=n+idt(V(u,r),0); V(y,r)<+n;''','real n,q;')
        with self.assertRaises(CompileError):
            compile_sources({'counter-operator.va':source},[instance()])

"""Bounded self updates shared by event blocks, with independent count answers."""
GUARDS = ['CROSS', 'EVENT-ORDER', 'EVENT-CONDITIONS']
import unittest
from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

HC01 = """`include "disciplines.vams"
`include "constants.vams"
module paper_hc(in, out, count);
 inout in, out, count;
 electrical in, out, count;
 real q,n;
 analog begin
  @(initial_step) begin q=0; n=0; end
  @(cross(V(in)-0.65,+1,1e-9,2e-4)) begin q=1; n=n+1; end
  @(cross(V(in)-0.35,-1,1e-9,2e-4)) begin q=0; n=n+1; end
  V(out)<+0.1+0.8*q;
  V(count)<+n;
 end
endmodule
"""


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

    def test_other_state_hidden_dependencies_and_scaling_remain_rejected(self):
        for rhs in ['q-q', '0*q', '(1e-200*1e-200)*q', 'n+q-q', 'n+0*q',
                    '2*n+1', '0*n+1', 'n+V(u,r)', 'n+idt(V(u,r),0)']:
            source=model(f'''@(initial_step) begin n=0; q=1; end
              @(timer(0.25)) begin n=n+1; q=2; end
              @(timer(0.75)) n={rhs}; V(y,r)<+n;''','real n,q;')
            with self.subTest(rhs=rhs):
                try:
                    p=compile_sources({'counter-bad.va':source},[instance()])
                except CompileError:
                    continue
                with self.assertRaisesRegex(KernelError,'unsupported_cross'):
                    transient(p,{'u':[[0,0],[1,0]]},[0,1],stop=1,max_step=1,kernel=KERNEL)

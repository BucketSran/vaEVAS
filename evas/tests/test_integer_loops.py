"""Bounded scalar integer loops retain the procedural control variable."""
GUARDS = ['LANG', 'EVENT-ORDER']
import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


def execute(body):
    program = compile_sources({'integer-loop.va':model(body,'integer n,i,j;')},[instance()])
    return transient(program,{'u':[[0,1],[1,1]]},[0,1],stop=1,max_step=1,kernel=KERNEL)


class IntegerLoops(unittest.TestCase):
    def test_event_loop_records_each_index_and_exit_value(self):
        result = execute('''@(timer(0.5)) begin
            for(i=0;i<3;i=i+1) begin n=n+i; $display("i=%d n=%d",i,n); end
            $display("exit=%d",i); end V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']],
                         ['i=0 n=0','i=1 n=1','i=2 n=3','exit=3'])

    def test_zero_trip_loop_still_initializes_control(self):
        result = execute('''@(initial_step) i=7;
            @(timer(0.5)) begin for(i=2;i<2;i=i+1) n=99;
            $display("i=%d n=%d",i,n); end V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']],['i=2 n=0'])

    def test_nested_loop_retains_both_exit_values(self):
        result = execute('''@(timer(0.5)) begin
            for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) n=n+1;
            $display("i=%d j=%d n=%d",i,j,n); end V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']],['i=2 j=2 n=4'])

    def test_initial_loop_final_control_is_visible_to_timer(self):
        result = execute('''@(initial_step) for(i=0;i<3;i=i+1) n=i;
            @(timer(0)) $display("i=%d n=%d",i,n); V(y,r)<+n;''')
        self.assertEqual([r['text'] for r in result['transient']['display_records']],['i=3 n=2'])

    def test_body_write_or_runtime_bound_is_explicitly_rejected(self):
        # A runtime bound without a proven trip count stays rejected here;
        # this one never terminates once n>0 (test_while_loops covers proofs).
        for body in ['for(i=0;i<2;i=i+1) i=i+1;',
                     'begin n=n+1; for(i=0;i<n;i=i+1) n=n+1; end']:
            with self.subTest(body=body),self.assertRaises(CompileError):
                compile_sources({'integer-loop.va':model('@(timer(0.5)) '+body+' V(y,r)<+n;','integer n,i;')},[instance()])

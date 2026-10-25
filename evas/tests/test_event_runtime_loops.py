"""Bounded event loops and checked array access through the public frontend."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-ORDER']
import unittest
from evas import CompileError, KernelError, Instance, compile_sources, transient
from test_affine import KERNEL, instance, model


FIXED = '\nmodule fixed(y);output y;electrical y;analog begin V(y)<+0;end endmodule'


def compile_body(body, declarations='integer i,n,a[0:3];'):
    return compile_sources({'runtime.va': model(body, declarations) + FIXED},
                           [instance(), Instance('source','fixed',dict(y='y'))])


class RuntimeLoopFrontend(unittest.TestCase):
    def test_state_limit_stays_one_wire_body(self):
        p = compile_body('@(initial_step) n=3; @(final_step) for(i=0;i<n;i=i+1) $display("%d",i);')
        loop = p.to_dict()['events'][-1]['body'][0]
        self.assertEqual(loop['kind'], 'loop')
        self.assertEqual(loop['relation'], 'lt')
        self.assertEqual(len(loop['body']), 1)
        self.assertEqual(loop['body'][0]['kind'], 'display')

    def test_unproven_index_retains_runtime_bounds(self):
        p = compile_body('@(timer(1,1)) begin n=n+1; a[n]=7; end')
        dispatch = p.to_dict()['events'][0]['body'][1]
        self.assertEqual(dispatch['kind'], 'array_write')
        self.assertEqual(dispatch['index']['op'], 'checked_index')
        self.assertEqual((dispatch['first'], dispatch['last']), (0,3))

    def test_direction_and_control_body_write_rejected(self):
        for header, body in [('i=0;i<n;i=i-1', '$display("%d",i);'),
                             ('i=0;i<n;i=i+1', 'i=i+1;')]:
            with self.subTest(header=header, body=body), self.assertRaises(CompileError):
                compile_body('@(final_step) for('+header+') '+body)

    def test_parameter_dead_branch_keeps_original_integer_audit(self):
        with self.assertRaises(CompileError):
            compile_body('@(initial_step) n=2147483647; @(timer(0.5)) if(mode==0) x=(n+1)-1; else x=2;',
                         'parameter mode=1; integer n; real x;')

    def test_noninteger_loop_control_rejected(self):
        with self.assertRaises(CompileError):
            compile_body('@(final_step) for(i=0;i<n;i=i+1) $display("%g",i);', 'real i; integer n;')


def run(program, times=(0,1)):
    result=transient(program, {'u':[[0,0],[1,0]]}, list(times),stop=1,max_step=1,kernel=KERNEL)
    final = result['transient']['states'][-1]
    for event in result['transient']['events']:
        if event['kind'] == 'final_step':
            final = event['after']
    return dict(zip(result['transient']['state_names'],final)),result


class RuntimeLoopExecution(unittest.TestCase):
    def test_zero_one_and_source_order_are_query_independent(self):
        for n, expected in [(0,0),(1,1),(3,6)]:
            p=compile_body(f'@(initial_step) n={n}; @(final_step) for(i=0;i<n;i=i+1) begin q=q+i+1; $display("%d:%d",i,q); end',
                           'integer i,n,q;')
            sparse,s=run(p);dense,d=run(p,(0,.2,.5,.8,1))
            self.assertEqual(sparse,dense)
            self.assertEqual((sparse['dut:i'],sparse['dut:q']),(n,expected))
            self.assertEqual(s['transient']['display_records'],d['transient']['display_records'])

    def test_condition_reads_the_bound_after_each_body_update(self):
        p=compile_body('@(initial_step) n=4; @(final_step) for(i=0;i<n;i=i+1) begin n=n-1; q=q+1; end',
                       'integer i,n,q;')
        states,_=run(p)
        self.assertEqual((states['dut:i'],states['dut:n'],states['dut:q']),(2,2,2))

    def test_total_loop_budget_is_shared_by_two_loops(self):
        for n,fail in [(2048,False),(2049,True)]:
            p=compile_body(f'@(initial_step) n={n}; @(final_step) begin for(i=0;i<n;i=i+1) q=q+1; for(i=0;i<n;i=i+1) q=q+1; end',
                           'integer i,n,q;')
            if fail:
                with self.assertRaisesRegex(KernelError,'event_loop_budget'):run(p)
            else:
                states,_=run(p);self.assertEqual(states['dut:q'],4096)

    def test_fixed_integer_inner_loop_shares_the_runtime_iteration_budget(self):
        for loops in [
                'for(i=0;i<n;i=i+1) for(j=0;j<2;j=j+1) q=q+1;',
                'for(i=0;i<2;i=i+1) for(j=0;j<n;j=j+1) q=q+1;']:
            p=compile_body('@(initial_step) n=2048; @(final_step) '+loops,
                           'integer i,j,n,q;')
            with self.subTest(loops=loops), self.assertRaisesRegex(KernelError,'event_loop_budget'):run(p)

    def test_iteration_allowance_belongs_to_each_event_activation(self):
        # Each event performs 3000 iterations, below its own 4096 limit. A
        # procedure-wide counter would incorrectly reject the second event.
        for second in ('final_step', 'timer(0.25)'):
            with self.subTest(second=second):
                p=compile_body('@(initial_step) n=3000; '
                               '@(timer(0.25)) for(i=0;i<n;i=i+1) q=q+1; '
                               '@('+second+') for(i=0;i<n;i=i+1) q=q+1;',
                               'integer i,n,q;')
                states,_=run(p)
                self.assertEqual(states['dut:q'],6000)

    def test_compact_array_statement_reads_previous_writes_with_descending_declaration(self):
        p=compile_body('@(initial_step) n=3; @(final_step) for(i=-1;i<n-1;i=i+1) begin a[i]=i+2; q=q+a[i]; end',
                       'integer i,n,q,a[1:-1];')
        states,_=run(p)
        self.assertEqual([states[f'dut:a[{i}]'] for i in [-1,0,1]],[1,2,3])
        self.assertEqual(states['dut:q'],6)

    def test_single_slot_array_and_both_outside_neighbors_fail_at_runtime(self):
        for index in [-1,0,1]:
            p=compile_body(f'@(timer(0.5)) begin n={index}; a[n]=7; end','integer n,a[0:0];')
            if index==0:
                states,_=run(p);self.assertEqual(states['dut:a[0]'],7)
            else:
                # Sequential assignment can prove this failure statically;
                # observer execution retains an explicit checked operation.
                with self.assertRaisesRegex(KernelError,'array_index_range'):run(p)

    def test_unselected_array_arm_remains_lazy(self):
        p=compile_body('@(timer(0.5)) begin n=9; q=(n<0 ? a[n] : 4); end','integer n,q,a[0:1];')
        states,_=run(p);self.assertEqual(states['dut:q'],4)

    def test_each_integer_operation_keeps_overflow_before_cancellation(self):
        p=compile_body('@(initial_step) n=2147483647; @(timer(0.5)) q=(n+1)-1;','integer n,q;')
        with self.assertRaisesRegex(KernelError,'integer_range'):run(p)

    def test_checked_arithmetic_keeps_proven_bounds_for_integer_quotients(self):
        for declarations in ('integer n,q,rem;', 'integer n; real q,rem;'):
            for n,q,rem in [(5,3,0),(-5,-2,0)]:
                p=compile_body(f'@(initial_step) n={n}; @(timer(0.5)) begin q=(n+1)/2; rem=(n+1)%2; end',
                               declarations)
                states,_=run(p)
                self.assertEqual((states['dut:q'],states['dut:rem']),(q,rem))

    def test_integer_quotient_and_remainder_truncate_toward_zero(self):
        for n,d,q,r in [(5,2,2,1),(-5,2,-2,-1),(5,-2,-2,1),(-5,-2,2,-1)]:
            p=compile_body(f'@(initial_step) n={n}; @(timer(0.5)) begin q=n/({d}); rem=n%({d}); end','integer n,q,rem;')
            states,_=run(p)
            self.assertEqual((states['dut:q'],states['dut:rem']),(q,r))

    def test_instance_state_and_array_mapping_stay_separate(self):
        src=model('@(initial_step) n=N; @(final_step) for(i=0;i<n;i=i+1) a[i]=i+N;',
                  'parameter integer N=1; integer i,n,a[0:2];')
        p=compile_sources({'instances.va':src+FIXED},[instance('one',parameters={'N':1}),instance('two',parameters={'N':2}), Instance('source','fixed',dict(y='y'))])
        states,_=run(p)
        self.assertEqual((states['one:a[0]'],states['one:a[1]'],states['two:a[0]'],states['two:a[1]']),(1,0,2,3))


class InheritedObserverIndexCases(unittest.TestCase):
    """The seven original observer counterexamples now execute their own paths.

    The measurement VA bodies are unchanged. A separate stateless instance
    supplies the public kernel's required voltage equation.
    """
    def test_original_safe_paths_complete_and_invalid_active_paths_fail(self):
        from test_r01_event_arrays import event_model
        cases = [
            ('entry_write', 'integer a[0:1],b;',
             ['@(initial_step) b=1;', '@(timer(0.5,0,1e-12)) begin a[b]=1; b=5; end'],
             {'dut:a[1]':1,'dut:b':5}),
            ('final_write', 'integer a[0:1],b;',
             ['@(initial_step) b=1;', '@(timer(0.5,0,1e-12)) a[b]=1;', '@(final_step) b=7;'],
             {'dut:a[1]':1,'dut:b':7}),
            ('uncertain_entry', 'integer a[0:1],b;',
             ['@(initial_step) b=0;', '@(timer(0.25,0,1e-12)) a[b]=1;', '@(timer(0.5,0,1e-12)) b=3;'],
             {'dut:a[0]':1,'dut:b':3}),
            ('read_range', 'real held[0:1]; integer b;',
             ['@(initial_step) b=0;', '@(timer(0.5,0,1e-12)) held[b]=1.0;', '@(timer(0.75,0,1e-12)) b=3;'],
             {'dut:held[0]':1,'dut:b':3}),
            ('weak_update', 'integer a[0:1],b,i; integer x[0:1];',
             ['@(initial_step) begin b=0; a[1]=5; end', '@(timer(0.5,0,1e-12)) begin a[b]=1; i=a[1]; x[i]=2; end'],
             None),
            ('negative_remainder','integer a[0:2],b;',
             ['@(initial_step) b=-2;', '@(timer(0.5,0,1e-12)) a[b%3]=1;'],None),
            ('extra_writer','integer a[1:4],counter,target,pending;',
             ['@(initial_step) begin counter=0; target=0; pending=0; end',
              '@(timer(0.25,0.25,1e-12)) begin target=(V(u,r)>=0); if(target) counter=counter+1; end',
              '@(timer(0.3,0.25,1e-12)) if(target) pending=1;',
              '@(timer(0.1,0.25,1e-12)) if(pending) if(counter<=4) a[counter]=1;',
              '@(timer(0.5)) counter=0;'],'event_conflict'),
        ]
        for name,declarations,events,expected in cases:
            with self.subTest(case=name):
                source=event_model(declarations,events,contribution=None)
                p=compile_sources({'arrays.va':source,'fixed.va':'`include "disciplines.vams"\n'+FIXED},
                                  [instance(),Instance('source','fixed',dict(y='y'))])
                if expected is None or isinstance(expected,str):
                    # The extra writer conflicts at t=.5 before reaching the
                    # later invalid index. It proves conflict preservation,
                    # and is not counted as an executed array-boundary test.
                    with self.assertRaisesRegex(KernelError,expected or 'array_index_range'):run(p)
                else:
                    states,_=run(p)
                    for key,value in expected.items():self.assertEqual(states[key],value)

"""Static event-body iteration through the public compiler and Rust runtime."""
GUARDS = ["LANG", "COMPOSE", "TIMER", "CROSS", "EVENT-ORDER", "EVENT-CONDITIONS", "case:static_loop", "case:variable_array"]

import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def compile_loop(body, declarations='genvar i; integer n; parameter integer N=3;', instances=None):
    return compile_sources({'event-loop.va': model(body, declarations)}, instances or [instance()])


def run(program, times=(0, .5, 1.5, 2.5), sources=None):
    return transient(program, sources or {'u': [[0, 0], [2.5, 0]]}, list(times),
                     stop=2.5, max_step=2.5, kernel=KERNEL)


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class EventBodyLoops(unittest.TestCase):
    def test_periodic_timer_preserves_iteration_order_and_current_state(self):
        program = compile_loop('''@(initial_step) n=0;
          @(timer(1,1,1e-12)) for(i=0;i<N;i=i+1) n=10*n+i+1;
          V(y,r)<+n;''')
        result = run(program)
        self.assertEqual(values(result), [0, 0, 123, 123123])
        self.assertEqual([event['time'] for event in result['transient']['events']], [1, 2])

    def test_parameter_bounds_are_instance_local_for_timer_and_cross(self):
        a = instance('a', connections={'u': 'u', 'y': 'a', 'r': '0'}, parameters={'N': 2})
        b = instance('b', connections={'u': 'u', 'y': 'b', 'r': '0'}, parameters={'N': 3})
        for trigger in ('timer(1,0,1e-12)', 'cross(V(u,r)-1,1,1e-12,1e-9)'):
            for order in ([a, b], [b, a]):
                with self.subTest(trigger=trigger, order=[inst.name for inst in order]):
                    program = compile_loop(f'''@(initial_step) n=0;
                      @({trigger}) for(i=0;i<N;i=i+1) n=10*n+i+1;
                      V(y,r)<+n;''', instances=order)
                    result = run(program, sources={'u': [[0, 0], [2.5, 2.5]]})
                    self.assertEqual(values(result, 'a'), [0, 0, 12, 12])
                    self.assertEqual(values(result, 'b'), [0, 0, 123, 123])

    def test_descending_zero_and_nested_iteration_keep_statement_order(self):
        for loop, expected in (
            ('for(i=3;i>0;i=i-1) n=10*n+i;', 321),
            ('for(i=0;i<0;i=i+1) n=99;', 0),
            ('for(i=0;i<2;i=i+1) for(j=0;j<2;j=j+1) n=10*n+2*i+j+1;', 1234),
        ):
            with self.subTest(loop=loop):
                program = compile_loop(f'@(initial_step) n=0; @(timer(1)) {loop} V(y,r)<+n;',
                                       'genvar i,j; integer n;')
                self.assertEqual(values(run(program)), [0, 0, expected, expected])

    def test_static_array_indices_are_substituted_before_state_lowering(self):
        source = model('''@(initial_step) begin n[0]=0; n[1]=0; n[2]=0; end
          @(timer(1)) for(i=2;i>=0;i=i-1) n[i]=11+i;
          V(y,r)<+n[0]; V(z,r)<+n[1]; V(w,r)<+n[2];''',
          'genvar i; integer n[0:2];', ports='u,y,z,w,r',
          directions='input u; output y,z,w; inout r;')
        program = compile_sources({'event-array.va': source}, [instance(connections={
            'u': 'u', 'y': 'y', 'z': 'z', 'w': 'w', 'r': '0'})])
        result = run(program)
        for node, expected in [('y', 11), ('z', 12), ('w', 13)]:
            self.assertEqual(values(result, node), [0, 0, expected, expected])

    def test_supported_input_conditional_keeps_existing_selected_writer_behavior(self):
        program = compile_loop('''@(initial_step) n=0;
          @(timer(1)) for(i=0;i<3;i=i+1)
            if(V(u,r)>.5) n=10*n+i+1; else n=10*n+3-i;
          V(y,r)<+n;''')
        self.assertEqual(values(run(program)), [0, 0, 321, 321])
        self.assertEqual(values(run(program, sources={'u': [[0, 1], [2.5, 1]]})), [0, 0, 123, 123])

    def test_invalid_iteration_is_rejected_before_runtime(self):
        cases = [
            ('for(i=0;i<2;i=i) n=i;', 'nonterminating'),
            ('for(i=0;i<2;i=i-1) n=i;', 'budget'),
            ('for(i=0;i<V(u,r);i=i+1) n=i;', 'instance-constant'),
            ('for(i=0;i<n;i=i+1) n=i;', 'instance-constant'),
            ('for(k=0;k<2;k=k+1) n=k;', 'declared genvar'),
            ('for(i=0;i<2;i=i+1) for(i=0;i<2;i=i+1) n=i;', 'unshadowed'),
            ('for(i=0;i<2;i=i+1) i=1;', 'for control'),
            ('for(i=0;i<2;i=i+.5) n=i;', 'signed 32-bit'),
            ('for(i=2147483647;i<=2147483647;i=i+1) n=0;', 'signed 32-bit'),
            ('for(i=0;i<4096;i=i+1) for(j=0;j<2;j=j+1) begin end', 'total static iteration budget'),
            ('for(i=0;i<4096;i=i+1) n=i;', 'statement budget'),
        ]
        for loop, diagnostic in cases:
            with self.subTest(loop=loop), self.assertRaisesRegex(CompileError, diagnostic):
                compile_loop(f'@(initial_step) n=0; @(timer(1)) {loop} V(y,r)<+n;',
                             'genvar i,j; integer n;')

    def test_event_body_restrictions_survive_loop_admission(self):
        for body in (
            'V(y,r)<+1;',
            'n=idt(V(u,r),0);',
            '@(timer(2)) n=1;',
            'if(n>0) n=1;',
            'if(idt(V(u,r),0)>0) n=1;',
        ):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_loop(f'''@(initial_step) n=0;
                  @(timer(1)) for(i=0;i<2;i=i+1) {body} V(y,r)<+n;''')

    def test_empty_loop_cannot_hide_unsupported_event_expressions(self):
        for body in ('n=idt(V(u,r),0);', 'if(n>0) n=1;', 'if(idt(V(u,r),0)>0) n=1;'):
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_loop(f'''@(initial_step) n=0;
                  @(timer(1)) for(i=0;i<0;i=i+1) {body} V(y,r)<+n;''')

    def test_empty_outer_loop_cannot_hide_invalid_nested_controls_or_predicates(self):
        for body in (
            'if(V(u,r)*V(u,r)>0) n=1;',
            'if(V(y,r)>0) n=1;',
            'for(j=0;j<2;j=V(u,r)) n=1;',
            'for(j=0;j<2;j=j+.5) n=1;',
        ):
            for count in (0, 1):
                with self.subTest(body=body, count=count), self.assertRaises((CompileError, KernelError)):
                    run(compile_loop(f'''@(initial_step) n=0;
                      @(timer(1)) for(i=0;i<{count};i=i+1) {body} V(y,r)<+n;''',
                                     'genvar i,j; integer n;'))

    def test_affine_input_and_stateless_output_conditions_remain_supported(self):
        for predicate in ('2*V(u,r)-1', 'V(y,r)'):
            for count in (0, 1):
                program = compile_loop(f'''@(initial_step) n=0;
                  @(timer(1)) for(i=0;i<{count};i=i+1) if({predicate}>.5) n=n+1;
                  V(y,r)<+V(u,r);''')
                result = run(program, sources={'u': [[0, 1], [2.5, 1]]})
                self.assertEqual(result['transient']['states'][-1], [count])

    def test_vector_predicate_dependencies_keep_stateless_bits_separate(self):
        for count in (0, 1):
            program = compile_loop(f'''@(initial_step) n=0;
              @(timer(1)) for(i=0;i<{count};i=i+1) if(V(bus[1],r)>.5) n=1;
              V(bus[0],r)<+n; V(bus[1],r)<+V(u,r); V(y,r)<+n;''',
                                   'genvar i; integer n; electrical [0:1] bus;')
            result = run(program, sources={'u': [[0, 1], [2.5, 1]]})
            self.assertEqual(result['transient']['states'][-1], [count])

    def test_erased_predicates_retain_indirect_and_cancelled_feedback_dependencies(self):
        for rhs in ('V(y,r)', 'V(y,r)-V(y,r)', '0*V(y,r)'):
            with self.subTest(rhs=rhs), self.assertRaises(CompileError):
                compile_loop(f'''@(initial_step) n=0;
                  @(timer(1)) for(i=0;i<0;i=i+1) if(V(z,r)>0) n=1;
                  V(z,r)<+{rhs}; V(y,r)<+n;''',
                             'genvar i; integer n; electrical z;')

    def test_runtime_integer_overflow_and_same_time_conflicts_remain_errors(self):
        for body, diagnostic in (
            ('@(timer(1)) for(i=0;i<10;i=i+1) n=10*n+9;', 'integer'),
            ('@(timer(1)) for(i=0;i<2;i=i+1) n=i; @(timer(1)) n=7;', 'event_conflict'),
        ):
            program = compile_loop(f'@(initial_step) n=0; {body} V(y,r)<+n;')
            with self.subTest(body=body), self.assertRaisesRegex(KernelError, diagnostic):
                run(program)

    def test_loop_does_not_enable_reads_from_another_event_writer(self):
        program = compile_loop('''@(initial_step) n=0;
          @(timer(.5)) n=7;
          @(timer(1)) for(i=0;i<2;i=i+1) n=10*n+i;
          V(y,r)<+n;''')
        with self.assertRaisesRegex(KernelError, 'unsupported_cross'):
            run(program)


if __name__ == '__main__':
    unittest.main()

"""Small source programs for R01 procedural semantics, without model rewrites."""
GUARDS = ["LANG", "EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest
from evas import CompileError, compile_sources, transient
from test_affine import KERNEL, instance, model


def run(body, declarations, *, input_value=1):
    program = compile_sources({'r01-runtime.va': model(body, declarations)}, [instance()])
    return transient(program, {'u': [[0, input_value], [1, input_value]]}, [0, .5, 1],
                     stop=1, max_step=1, kernel=KERNEL)


def output(result):
    index = result['nodes'].index('y')
    return [row['voltages'][index] for row in result['solutions']]


class R01RuntimeFrontend(unittest.TestCase):
    def test_integer_operation_overflow_survives_folding_and_boolean_conversion(self):
        bodies = [
            'n=2147483647; n=(n+1)-1; V(y,r)<+n;',
            'n=2147483647; flag=(n+1)>0; V(y,r)<+flag;',
            '@(initial_step) begin n=2147483647; n=(n+1)-1; end V(y,r)<+n;',
            '@(initial_step) begin n=2147483647; flag=(n+1)>0; end V(y,r)<+flag;',
            '@(timer(0.5)) n=(2147483647+1)-1; V(y,r)<+n;',
            '@(timer(0.5)) flag=(2147483647+1)>0; V(y,r)<+flag;',
            '@(initial_step) n=0; @(timer(0.5)) n=(n+1)-1; V(y,r)<+n;',
            '@(initial_step) n=0; @(timer(0.5)) begin n=n+1; flag=(n+1)>0; end V(y,r)<+flag;',
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, 'integer intermediate.*signed 32-bit'):
                compile_sources({'r01-runtime.va': model(body, 'integer n,flag;')}, [instance()])
        observer='@(timer(0.5)) begin n=n+1; m=m+1; k=k+1; end V(y,r)<+n+m+k;'
        with self.assertRaisesRegex(CompileError, 'integer intermediate signed 32-bit range is unproven'):
            compile_sources({'r01-runtime.va': model(observer, 'integer n,m,k;')}, [instance()])
        self.assertEqual(output(run(observer.replace('n+m+k;', '1.0*n+1.0*m+1.0*k;'), 'integer n,m,k;')), [0,3,3])
        for prefix in ('', '@(initial_step) begin ', '@(timer(0.5)) begin '):
            suffix = ' end' if prefix else ''
            body = prefix+'n=2147483647; flag=(n+1)>0; n=(n+1)-1;'+suffix+' V(y,r)<+n;'
            expected = [0,2147483647,2147483647] if 'timer' in prefix else [2147483647]*3
            self.assertEqual(output(run(body, 'real n; integer flag;')), expected)

    def test_initial_condition_reads_prior_write_and_repeated_write(self):
        body = '''@(initial_step) begin n=1; n=n+1;
            if(n==2 && V(u,r)>0) n=n+3; else n=7; end
            V(y,r)<+n;'''
        self.assertEqual(output(run(body, 'integer n;')), [5,5,5])
        self.assertEqual(output(run(body, 'integer n;', input_value=-1)), [7,7,7])

    def test_initial_sum_of_selected_integer_values(self):
        body = '''@(initial_step) n=(V(u,r)>0 ? 1 : 0)+(V(u,r)>0.5 ? 2 : 0);
            V(y,r)<+n;'''
        self.assertEqual(output(run(body, 'integer n;')), [3,3,3])
        self.assertEqual(output(run(body, 'integer n;', input_value=.25)), [1,1,1])

    def test_event_predicate_reads_same_event_prior_assignment(self):
        body = '''@(timer(0.5)) begin n=n+1;
            if(n==1) n=4; else n=8; end V(y,r)<+n;'''
        self.assertEqual(output(run(body, 'integer n;')), [0,4,4])

    def test_event_math_choices_keep_affine_predicates_and_order(self):
        body = '''@(timer(0.5)) begin q=abs(V(u,r));
            if(max(q,2)>min(q,3)) q=q+10; else q=q+20;
            end V(y,r)<+q;'''
        self.assertEqual(output(run(body, 'real q;', input_value=-1)), [0,11,11])
        self.assertEqual(output(run(body, 'real q;', input_value=-4)), [0,14,14])
        self.assertEqual(output(run(body, 'real q;', input_value=2)), [0,22,22])

    def test_event_selected_integer_rhs_and_ordinary_boolean_local(self):
        body = '''@(initial_step) n=0; @(timer(0.5)) n=(V(u,r)>0 ? 2 : 3);
            flag=n==2 && V(u,r)>0; V(y,r)<+flag;'''
        self.assertEqual(output(run(body, 'integer n,flag;')), [0,1,1])

    def test_unconditional_transition_boolean_target(self):
        body = "@(initial_step) n=0; @(timer(0.5)) n=1; V(y,r)<+transition(n==1,0,0.25);"
        self.assertEqual(output(run(body, 'integer n;')), [0,0,1])

    def test_transition_selected_held_values_keep_continuous_target_rejection(self):
        for guard in ('V(u,r)>0', 'a>0'):
            body = f'''@(initial_step) begin a=2; b=3; end
                @(timer(0.5)) a=4;
                V(y,r)<+transition({guard}?a:b,0,0.25);'''
            if guard == 'a>0':
                self.assertEqual(output(run(body, 'real a,b;')), [2,2,4])
            else:
                # Source-selected held arms are frontend-valid; the current
                # transient mode controller has a separate runtime restriction.
                self.assertTrue(compile_sources({'r01-runtime.va': model(body, 'real a,b;')}, [instance()]).operators)
        for value, prefix in (
            ('V(u,r)', ''),
            ('V(u,r)>0?V(u,r):a', ''),
            ('a>0?a:V(u,r)', ''),
            ('q', 'q=V(u,r);'),
        ):
            body = '@(initial_step) a=2;'+prefix+f'V(y,r)<+transition({value},0,0.25);'
            with self.subTest(value=value), self.assertRaisesRegex(CompileError, 'continuous voltage targets'):
                compile_sources({'r01-runtime.va': model(body, 'real a,q;')}, [instance()])

    def test_integer_division_and_modulo_truncate_toward_zero(self):
        for numerator, divisor, quotient, remainder in [(7,2,3,1), (-7,2,-3,-1),
                (7,-2,-3,1), (-7,-2,3,-1), (-1,2,0,-1), (1,-2,0,1)]:
            for operator, expected in [("/", quotient), ("%", remainder)]:
                with self.subTest(numerator=numerator, divisor=divisor, operator=operator):
                    body = f"n={numerator}; V(y,r)<+n {operator} ({divisor});"
                    self.assertEqual(output(run(body, 'integer n;')), [expected]*3)
        self.assertEqual(output(run("n=-7; V(y,r)<+n/2;", 'real n;')), [-3.5]*3)
        self.assertEqual(output(run("n=-7; V(y,r)<+n/2.0;", 'integer n;')), [-3.5]*3)
        function = 'analog function real f; input x; real x; begin f=7; end endfunction '
        self.assertEqual(output(run('V(y,r)<+f(0)/2;', function)), [3.5]*3)
        self.assertEqual(output(run('V(y,r)<+(f(0)+2)/2;', function)), [4.5]*3)

    def test_bounded_state_division_crosses_negative_and_positive_bins(self):
        for operator, positive, negative in [("/", [-1,1,1], [-1,-1,-1]),
                                             ("%", [-1,1,1], [-1,0,0])]:
            body = f"@(initial_step) n=-3; @(timer(0.5)) n=V(u,r)>0 ? 3 : -2; V(y,r)<+n{operator}2;"
            with self.subTest(operator=operator):
                self.assertEqual(output(run(body, 'integer n;')), positive)
                self.assertEqual(output(run(body, 'integer n;', input_value=-1)), negative)

    def test_integer_division_requires_bounded_nonrecursive_state(self):
        body = "@(initial_step) n=0; @(timer(0.5)) n=n+1; V(y,r)<+n/2;"
        with self.assertRaisesRegex(CompileError, 'quotient-bin budget'):
            compile_sources({'r01-runtime.va': model(body, 'integer n;')}, [instance()])
        with self.assertRaisesRegex(CompileError, 'integer typed operands'):
            compile_sources({'r01-runtime.va': model('n=7; V(y,r)<+n%2;', 'real n;')}, [instance()])

    def test_conditional_math_admission_keeps_history_rejection(self):
        # This assertion is frontend admission, not a dynamic math alignment claim.
        source = model('if(V(u,r)>0) q=exp(-V(u,r)); else q=0; V(y,r)<+q;', 'real q;')
        self.assertTrue(compile_sources({'r01-runtime.va': source}, [instance()]).operators)
        source = model('if(V(u,r)>0) q=exp(idt(V(u,r),0)); else q=0; V(y,r)<+q;', 'real q;')
        with self.assertRaisesRegex(CompileError, 'history waveform'):
            compile_sources({'r01-runtime.va': source}, [instance()])

    def test_real_to_integer_conversion_is_rejected(self):
        for body in ['n=V(u,r); V(y,r)<+n;',
                     '@(initial_step) n=0.5; V(y,r)<+n;',
                     '@(timer(0.5)) n=V(u,r)>0 ? 0.5 : 1; V(y,r)<+n;']:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, 'integral'):
                compile_sources({'r01-runtime.va': model(body, 'integer n;')}, [instance()])

    def test_integer_intermediate_overflow_is_not_erased_by_later_write(self):
        for body in ['@(initial_step) begin n=2147483647; n=n+1; n=0; end V(y,r)<+n;',
                     'n=2147483647; n=n+1; n=0; V(y,r)<+n;']:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, 'signed 32-bit'):
                compile_sources({'r01-runtime.va': model(body, 'integer n;')}, [instance()])

    def test_initial_output_feedback_and_event_history_are_rejected(self):
        for body in ['@(initial_step) q=V(y,r); V(y,r)<+q;',
                     '@(timer(0.5)) q=idt(V(u,r),0); V(y,r)<+q;',
                     'V(y,r)<+ V(u,r)>0 ? transition(1,0,0.25) : 0;']:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_sources({'r01-runtime.va': model(body, 'real q;')}, [instance()])

"""VAMS 2.4 §§4.2.9/4.2.11 through public compilation and execution."""
GUARDS = ["LANG", "EVENT-ORDER"]

import unittest
from evas import CompileError, Instance, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


class IntegerBitops(unittest.TestCase):
    def test_composed_bitwise_modulo_keeps_constant_ir_and_checked_arithmetic(self):
        for initial, expression, expected in [(7, '(n&3)%2', 1), (-7, '(-(n&3))%3', -1)]:
            source = model('@(initial_step)n='+str(initial)+'; @(timer(0.25))n='+expression+'; V(y,r)<+n;', 'integer n;')
            program = compile_sources({'composed-modulo.va': source}, [instance()])
            result = transient(program, {'u': [[0,0],[.5,0]]}, [0,.25,.5],
                               stop=.5, max_step=.25, kernel=KERNEL)
            y = result['nodes'].index('y')
            self.assertEqual([row['voltages'][y] for row in result['solutions']], [initial,expected,expected])
        for expression in ('(n&3)%0', '((n&3)+2147483647)%2'):
            source = model('@(initial_step)n=1; @(timer(0.25))n='+expression+'; V(y,r)<+n;', 'integer n;')
            with self.subTest(expression=expression), self.assertRaises(CompileError):
                compile_sources({'bad-composed-modulo.va': source}, [instance()])

    def test_signed32_logic_shifts_wrap_and_zero_fill(self):
        # Fixed 32-bit patterns: logical right shift of all ones clears the
        # sign bit; shifting 1 into bit31 sets the signed minimum. Counts
        # >=32, including a negative count interpreted unsigned, remove all bits.
        cases = [('(-1)>>1', 2147483647), ('(-2147483648)>>31', 1),
                 ('1<<31', -2147483648), ('(-1)>>32', 0), ('1<<(-1)', 0),
                 ('~(-1)', 0), ('~0', -1), ('(-2)^1', -1),
                 ('(-2)|1', -1), ('(-1)&8', 8), ('1+1<<2', 8),
                 ('1|2^3&1', 3), ('1|2==2', 1)]
        for expression, expected in cases:
            with self.subTest(expression=expression):
                program = compile_sources({'bits.va': model('V(y,r)<+' + expression + ';')}, [instance()])
                result = solve(program, ['u'], [[0]], kernel=KERNEL)
                self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], expected)

    def test_integer_parameter_default_preserves_bitwise_type(self):
        program = compile_sources({'parameter-bits.va': model('V(y,r)<+mask;',
            'parameter integer seed=3; parameter integer mask=(seed<<2)|1;')}, [instance()])
        result = solve(program, ['u'], [[0]], kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], 13)

    def test_finite_masks_in_ordinary_analog_values(self):
        # The mask truth table for 5(0101), 10(1010), -2(...1110).
        for value, expected in [(5, 4), (10, 2), (-2, 6)]:
            source = model('if(V(u,r)>0) n=5; else if(V(u,r)<0) n=-2; else n=10; '
                           'V(y,r)<+((n&4)+(n&2));', 'integer n;')
            program = compile_sources({'mask.va': source}, [instance()])
            stimulus = 1 if value == 5 else -1 if value == -2 else 0
            result = solve(program, ['u'], [[stimulus]], kernel=KERNEL)
            self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')], expected)

    def test_real_operands_unknown_ranges_and_runtime_shift_counts_refuse(self):
        cases = [('V(y,r)<+(1.0&1);', ''),
                 ('@(timer(0.5)) n=n+1; V(y,r)<+(n&1);', 'integer n;'),
                 ('@(initial_step) n=1; V(y,r)<+(1<<n);', 'integer n;')]
        for body, declarations in cases:
            with self.subTest(body=body), self.assertRaises(CompileError) as caught:
                compile_sources({'reject-bits.va': model(body, declarations)}, [instance()])
            self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_integer_bitwise')
            self.assertEqual(caught.exception.diagnostic['category'], 'unsupported')
            self.assertEqual(caught.exception.diagnostic['capability'], 'LANG')
        # Integer overflow in a child may not disappear behind a zero mask.
        with self.assertRaisesRegex(CompileError, 'integer intermediate'):
            compile_sources({'reject-bits.va': model('V(y,r)<+((2147483647+1)&0);')}, [instance()])

    def test_checked_intermediate_cannot_disappear_in_singleton_bitwise_fold(self):
        # At the second timer, n+MAX is 2147483648. Intersecting a checked
        # node's successful values with signed32 leaves singleton MAX, but
        # folding that singleton may not erase the failed execution path.
        source = model('''@(initial_step) n=0;
            @(timer(0.25,0.25,1e-12)) n=(n+2147483647)&1;''', 'integer n;')
        source += '\nmodule fixed(y); output y; electrical y; analog begin V(y)<+1; end endmodule'
        with self.assertRaises(CompileError) as caught:
            compile_sources({'checked-bitops.va': source},
                [instance(), Instance('source', 'fixed', dict(y='y'))])
        self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_integer_bitwise')
        # A closed {0,1} invariant proves n+1 safe at every callback. Checked
        # arithmetic is accepted when its original range is already sound.
        safe = source.replace('(n+2147483647)&1', '(n+1)&1')
        program = compile_sources({'checked-bitops.va': safe},
            [instance(), Instance('source', 'fixed', dict(y='y'))])
        result = transient(program, {'u': [[0,0],[1,0]]}, [0,.25,.5,.75,1],
                           stop=1, max_step=.25, kernel=KERNEL)
        self.assertEqual(result['transient']['states'], [[0],[1],[0],[1],[0]])

    def test_singleton_fold_retains_same_batch_state_read(self):
        # Both writes preserve n=0, but the original read of n still conflicts
        # with another selected block's same-time write. A constant table leaf
        # cannot erase that structural requirement.
        source = model('''@(timer(0.25)) if(V(u,r)>0) n=0;
            @(timer(0.25)) q=n&1;''', 'integer n,q;')
        source += '\nmodule fixed(y); output y; electrical y; analog begin V(y)<+1; end endmodule'
        program = compile_sources({'singleton-bits.va': source},
            [instance(), Instance('source', 'fixed', dict(y='y'))])
        with self.assertRaisesRegex(KernelError, 'cannot read state written'):
            transient(program, {'u': [[0,1],[1,1]]}, [0,.25,.5],
                      stop=1, max_step=.25, kernel=KERNEL)
        result = transient(program, {'u': [[0,-1],[1,-1]]}, [0,.25,.5],
                           stop=1, max_step=.25, kernel=KERNEL)
        self.assertEqual(result['transient']['states'], [[0,0],[0,0],[0,0]])

    def test_singleton_wrapper_retains_array_and_index_predicate_reads(self):
        # The Boolean value is always zero, but its original predicate reads
        # both the selected array slot and its state-valued index.
        for writer in ('a[0]=0;', 'i=0;'):
            source = model('@(timer(0.25)) if(V(u,r)>0) '+writer+
                ' @(timer(0.25)) q=((a[i]>0)?0:0)&1;', 'integer i,q,a[0:1];')
            source += '\nmodule fixed(y); output y; electrical y; analog begin V(y)<+1; end endmodule'
            program = compile_sources({'array-bit-wrapper.va': source},
                [instance(), Instance('source', 'fixed', dict(y='y'))])
            with self.subTest(writer=writer), self.assertRaisesRegex(KernelError, 'cannot read state written'):
                transient(program, {'u': [[0,1],[1,1]]}, [0,.25,.5],
                          stop=1, max_step=.25, kernel=KERNEL)
            result = transient(program, {'u': [[0,-1],[1,-1]]}, [0,.25,.5],
                               stop=1, max_step=.25, kernel=KERNEL)
            self.assertTrue(all(all(value == 0 for value in row) for row in result['transient']['states']))

    def test_ordinary_singleton_wrapper_keeps_original_predicate_scope(self):
        for guard, accepted in [('V(u,r)>0', True), ('V(y,r)>0', False)]:
            source = model('n=('+guard+'?0:0); V(y,r)<+(n&1);', 'integer n;')
            if accepted:
                program = compile_sources({'ordinary-bit-wrapper.va': source}, [instance()])
                result = solve(program, ['u'], [[-1],[1]], kernel=KERNEL)
                y = result['nodes'].index('y')
                self.assertEqual([row['voltages'][y] for row in result['solutions']], [0,0])
            else:
                with self.assertRaisesRegex(CompileError, 'input/inout'):
                    compile_sources({'ordinary-bit-wrapper.va': source}, [instance()])

    def test_bitwise_table_preserves_bounded_runtime_divisor_semantics(self):
        for operator, expected in (('/',[3,1,1]), ('%',[3,0,0])):
            for divisor in ('d', '(d&3)'):
                source = model('@(initial_step) begin n=3; d=1; end '
                    '@(timer(0.25)) n=(n'+operator+divisor+')&1; V(y,r)<+n;', 'integer n,d;')
                with self.subTest(operator=operator, divisor=divisor):
                    program = compile_sources({'runtime-divisor-bits.va': source},[instance()])
                    result = transient(program, {'u': [[0,0],[.5,0]]}, [0,.25,.5],
                                       stop=.5, max_step=.25, kernel=KERNEL)
                    y = result['nodes'].index('y')
                    self.assertEqual([row['voltages'][y] for row in result['solutions']], expected)
        # An instance-constant divisor retains finite integer truncation.
        source = model('@(initial_step) n=3; @(timer(0.25,0.25,1e-12)) n=(n/2)&1; V(y,r)<+n;', 'integer n;')
        program = compile_sources({'constant-divisor-bits.va': source}, [instance()])
        result = transient(program, {'u': [[0,0],[.5,0]]}, [0,.25,.5],
                           stop=.5, max_step=.25, kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [3,1,0])

    def test_composed_prbs_recurrence_uses_one_finite_state_decision(self):
        # Primitive polynomial x^3+x^2+1 visits all seven nonzero states.
        # These seven steps are hand-expanded truth-table answers, not values
        # calculated by the compiler or its bitwise helper.
        source = model('''@(initial_step) n=7;
            @(timer(0.25,0.25,1e-12)) begin
                feedback=((n>>2)&1)^((n>>1)&1);
                n=((n&3)<<1)|feedback;
            end V(y,r)<+n;''', 'integer n,feedback;')
        program = compile_sources({'prbs-bits.va': source}, [instance()])
        times = [0,.25,.5,.75,1,1.25,1.5,1.75]
        result = transient(program, {'u': [[0,0],[1.75,0]]}, times,
                           stop=1.75, max_step=.25, kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [7,6,4,1,2,5,3,7])

    def test_constant_seed_and_event_xor_keep_sequential_bit_state(self):
        # Two-bit shift register: 11 -> 01 -> 10. Answers follow the XOR
        # truth table, independently of expression lowering.
        body = '''@(initial_step) begin a=(seed >> 0)&1; b=(seed >> 1)&1; end
            @(timer(0.25,0.25,1e-12)) begin f=a^b; b=a; a=f; end
            V(y,r)<+a+2*b;'''
        program = compile_sources({'integer-bitops.va': model(
            body, 'parameter integer seed=3; integer a,b,f;')}, [instance()])
        result = transient(program, {'u': [[0,0],[0.5,0]]}, [0,.25,.5],
                           stop=.5, max_step=.25, kernel=KERNEL)
        y = result['nodes'].index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']], [3,2,1])


if __name__ == '__main__':
    unittest.main()

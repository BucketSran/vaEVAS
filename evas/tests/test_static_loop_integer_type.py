"""Static integer substitutions retain source type and procedural order."""
GUARDS = ["LANG", "EVENT-ORDER", "case:static_loop"]

import unittest
from fractions import Fraction
from evas import CompileError, Instance, compile_sources, transient
from test_affine import KERNEL

def compile_body(loop, declarations='integer j; integer q;'):
    source = ('`include "disciplines.vams"\nmodule m(u,y,r); input u; output y; inout r; '
              'electrical u,y,r; ' + declarations + ' analog begin @(initial_step) q=0; '
              '@(timer(1)) ' + loop + ' V(y,r)<+q; end endmodule')
    return compile_sources({'typed-loop.va': source}, [Instance('dut', 'm', {'u':'u','y':'y','r':'0'}, {})])

def assigned_constants(program):
    q = next(i for i,s in enumerate(program.states) if s.name == 'q')
    def exact(e):
        # Independent rational interpretation of constant public IR, no EVAS evaluator.
        if e.op == 'affine':
            assert not e.terms
            return Fraction.from_float(e.constant)
        a, b = exact(e.left), exact(e.right)
        if e.op == 'add': return a+b
        if e.op == 'multiply': return a*b
        if e.op == 'divide': return a/b
        raise AssertionError('Unexpected nonconstant IR: '+repr(e))
    return [exact(a.rhs) for e in program.events for a in e.body
            if getattr(a, 'kind', None) == 'assign' and a.state == q]

class StaticLoopIntegerType(unittest.TestCase):
    def test_typed_loop_remainder_reaches_the_public_kernel_consumer(self):
        program = compile_body('for(j=-2;j<2;j=j+1) begin q=j%16; $display("q=%d",q); end')
        result = transient(program, {'u': [[0, 0], [2, 0]]}, [0, 1, 2],
                           stop=2, max_step=2, kernel=KERNEL)
        self.assertEqual([r['text'] for r in result['transient']['display_records']],
                         ['q=-2', 'q=-1', 'q=0', 'q=1'])
        self.assertEqual([r['voltages'][program.nodes.index('y')] for r in result['solutions']],
                         [0, 1, 1])

    def test_integer_loop_remainder_preserves_negative_source_order(self):
        p = compile_body('for(j=-2;j<2;j=j+1) q=j%16;')
        # Signed remainder truncates toward zero, not Python's nonnegative mod.
        self.assertEqual(assigned_constants(p), [-2, -1, 0, 1])

    def test_nested_integer_and_genvar_controls_bind_each_iteration(self):
        p = compile_body('for(j=0;j<2;j=j+1) for(k=0;k<2;k=k+1) q=(j*2+k)%16;', 'integer j,q; genvar k;')
        self.assertEqual(assigned_constants(p), [0, 1, 2, 3])

    def test_genvar_existing_integral_remainder_remains_supported(self):
        p = compile_body('for(j=0;j<4;j=j+1) q=j%2;', 'genvar j; integer q;')
        self.assertEqual(assigned_constants(p), [0, 1, 0, 1])

    def test_real_operands_do_not_become_integer_by_numeric_value(self):
        for rhs in ['1.0%16', '(j+1.0)%16', 'x%16']:
            with self.subTest(rhs=rhs), self.assertRaises(CompileError):
                compile_body('for(j=0;j<1;j=j+1) q='+rhs+';', 'integer j,q; real x;')

    def test_original_intermediate_overflow_precedes_outer_remainder_or_zero(self):
        for rhs in ['(2147483647+j)%16', '0*((2147483647+j)%16)']:
            with self.subTest(rhs=rhs), self.assertRaisesRegex(CompileError, '32-bit|overflow|range'):
                compile_body('for(j=1;j<2;j=j+1) q='+rhs+';')

    def test_original_control_writer_and_expansion_limits_stay_rejected(self):
        for loop in ['for(j=0;j<2;j=j+1) j=1;', 'for(j=0;j<4096;j=j+1) for(k=0;k<2;k=k+1) q=0;',
                     'for(j=2147483647;j<=2147483647;j=j+1) q=0;']:
            with self.subTest(loop=loop), self.assertRaises(CompileError):
                compile_body(loop, 'integer j,q; genvar k;')

if __name__ == '__main__': unittest.main(verbosity=2)

"""Independent public producer/consumer contracts. Baseline integer failures stay red."""
from pathlib import Path
import unittest

GUARDS = ["LANG", "LIN", "COMPOSE"]
from evas import CompileError, Instance, compile_sources, solve
ROOT=Path(__file__).resolve().parents[2]
KERNEL=ROOT/'evas/rust_core/target/debug/evas-kernel'
PREFIX='`include "disciplines.vams"\nmodule m(y); output y; electrical y; '

def program(definition, value):
    return compile_sources({'function-contract.va':PREFIX+definition+' analog begin V(y)<+'+value+'; end endmodule'},
                           [Instance('dut','m',{'y':'y'},{})])

def output(definition, value):
    result=solve(program(definition,value),[],[[]],kernel=KERNEL)
    return result['solutions'][0]['voltages'][result['nodes'].index('y')]

class IntegerFunctionContract(unittest.TestCase):
    def test_integer_formal_rounds_before_division(self):
        # +2.5 copies into integer x as 3; integer 3/2 truncates to 1.
        self.assertEqual(output('analog function integer f; input x; integer x; begin f=x/2; end endfunction','f(2.5)'),1)
    def test_real_formal_widens_integer_actual_before_division(self):
        # Real formal x forces real division 3.0/2 = 1.5; integer result rounds to 2.
        self.assertEqual(output('analog function integer f; input x; real x; begin f=x/2; end endfunction','f(3)'),2)
    def test_local_assignment_conversion_precedes_next_statement(self):
        # Integer t receives -2.5 as -3; signed remainder is -1, quotient is -1.
        self.assertEqual(output('analog function integer f; input x; real x; integer t; begin t=x; f=10*(t/2)+(t%2); end endfunction','f(-2.5)'),-11)
    def test_return_assignment_rounds_before_subsequent_use(self):
        # Return variable is itself integer: first 2.5 -> 3; then integer 3/2 -> 1.
        self.assertEqual(output('analog function integer f; input x; real x; begin f=x; f=f/2; end endfunction','f(2.5)'),1)
    def test_integer_formal_is_not_real_arithmetic_on_integer_actual(self):
        self.assertEqual(output('analog function real f; input x; integer x; begin f=x/2; end endfunction','f(-3)'),-1)
    def test_integer_signed_decode_keeps_both_arms(self):
        definition='analog function integer f; input x; integer x; begin if(x>=16) f=-(x-15); else f=x; end endfunction'
        self.assertEqual(output(definition,'f(16)+f(15)'),14)

class AdditionalContracts(unittest.TestCase):
    def test_unused_integer_formal_still_performs_copy_in_conversion(self):
        with self.assertRaises(CompileError):
            program('analog function integer f; input x; integer x; begin f=1; end endfunction','f(2147483647.5)')
    def test_unused_integer_definition_still_validates_hidden_branch(self):
        with self.assertRaises(CompileError):
            program('analog function integer f; input x; integer x; begin if(x>0) f=x; else f=missing(x); end endfunction','1')
    def test_hidden_integer_division_by_zero_after_discard_rejects(self):
        with self.assertRaises(CompileError):
            program('analog function integer f; input x; integer x,t; begin t=x/0; f=1; end endfunction','f(1)')
    def test_closed_parameter_context_is_rejected_before_unchecked_folding(self):
        source=(PREFIX+'parameter real p=f(2147483647); '
                'analog function integer f; input x; integer x,t; '
                'begin t=(x+1)-1; f=1; end endfunction '
                'analog begin V(y)<+p; end endmodule')
        with self.assertRaises(CompileError) as error:
            compile_sources({'closed.va':source},[Instance('dut','m',{'y':'y'},{})])
        self.assertEqual(error.exception.diagnostic['code'],'unsupported_function_conversion')
    def test_integer_function_natural_budget_exhausts_twice(self):
        definition='analog function integer f; input x; integer x; begin f=x+x; end endfunction'
        value='1'
        for _ in range(20): value='f('+value+')'
        for _ in range(2):
            with self.assertRaises(CompileError) as error: program(definition,value)
            self.assertEqual(error.exception.diagnostic['code'],'resource_budget')
    def test_source_spelling_does_not_invoke_internal_assignment_ast(self):
        with self.assertRaises(CompileError): program('','function_assign(1)')
    def test_nearest_conversion_preserves_adjacent_tie_values_and_signed_edges(self):
        definition='analog function integer f; input x; real x; begin f=x; end endfunction'
        for value,expected in [('2.4999999999999996',2),('-2.4999999999999996',-2),
                               ('2147483647.4999998',2147483647),('-2147483648.4999995',-2147483648)]:
            with self.subTest(value=value): self.assertEqual(output(definition,'f('+value+')'),expected)
    def test_integer_default_return_initializes_to_zero(self):
        self.assertEqual(output('analog function integer f; input x; integer x; begin if(x>0) f=x; end endfunction','f(-2)'),0)
    def test_integer_return_variable_is_readable_before_first_assignment(self):
        self.assertEqual(output('analog function integer f; input x; integer x; begin f=f+x; end endfunction','f(7)'),7)
    def test_real_formal_integer_actual_uses_real_division(self):
        self.assertEqual(output('analog function real f; input x; real x; begin f=x/2; end endfunction','f(3)'),1.5)
    def test_integer_assignment_signed32_out_of_range_rejects(self):
        for value in ('2147483647.5','-2147483648.5'):
            with self.subTest(value=value), self.assertRaises(CompileError):
                program('analog function integer f; input x; integer x; begin f=x; end endfunction','f('+value+')')
    def test_hidden_overflow_before_final_result_rejects(self):
        with self.assertRaises(CompileError):
            program('analog function integer f; input x; integer x,t; begin t=x+1; f=1; end endfunction','f(2147483647)')
    def test_nested_function_result_copies_with_declared_type(self):
        definition=('analog function integer f; input x; integer x; begin f=x/2; end endfunction '
                    'analog function integer g; input x; real x; integer t; begin t=f(x); g=t/2; end endfunction')
        self.assertEqual(output(definition,'g(-5.5)'),-1)
    def test_dynamic_real_conversion_is_explicitly_rejected(self):
        source=('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; '
                'analog function integer f; input x; real x; begin f=x; end endfunction '
                'analog begin V(y)<+f(V(u)); end endmodule')
        with self.assertRaises(CompileError) as error:
            compile_sources({'dynamic.va':source},[Instance('dut','m',{'u':'u','y':'y'},{})])
        self.assertEqual(error.exception.diagnostic['code'],'unsupported_function_conversion')
    def test_function_result_preserves_index_source_rejection(self):
        source=('`include "disciplines.vams"\nmodule m(y); output y; electrical y; integer a[0:1],n; '
                'analog function integer f; input x; integer x; begin f=x; end endfunction '
                'analog begin @(initial_step) begin n=0; a[0]=0; a[1]=1; end '
                '@(timer(1)) n=a[f(0)]; V(y)<+n; end endmodule')
        with self.assertRaises(CompileError) as error:
            compile_sources({'index.va':source},[Instance('dut','m',{'y':'y'},{})])
        self.assertEqual(error.exception.diagnostic['code'],'array_index_type')
    def test_dynamic_typed_integer_state_consumes_existing_ir(self):
        from evas import transient
        source=('`include "disciplines.vams"\nmodule m(y); output y; electrical y; integer n; '
                'analog function integer f; input x; integer x; begin f=x/2; end endfunction '
                'analog begin @(initial_step) n=3; @(timer(1)) n=-3; V(y)<+f(n); end endmodule')
        p=compile_sources({'state.va':source},[Instance('dut','m',{'y':'y'},{})])
        r=transient(p,{},[0,1,2],stop=2,max_step=1,kernel=KERNEL)
        self.assertEqual([row['voltages'][r['nodes'].index('y')] for row in r['solutions']],[1,-1,-1])

class ExistingControls(unittest.TestCase):
    def test_real_function_parameter_result_uses_real_division(self):
        # VAMS 2.4 4.7.3 copies 3 into real x before the real return is
        # divided. Its quotient is 1.5; the separate exact integer default is 1.
        source=(PREFIX+'parameter real ratio=identity(3)/2; '
                'parameter integer exact=identity(2)/2; '
                'analog function real identity; input x; real x; begin identity=x; end endfunction '
                'analog begin V(y)<+ratio+exact; end endmodule')
        compiled=compile_sources({'real-function-parameter.va':source},[Instance('dut','m',{'y':'y'},{})])
        result=solve(compiled,[],[[]],kernel=KERNEL)
        self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')],2.5)
    def test_real_function_parameter_keeps_integer_intermediate_and_assignment_guards(self):
        definition='analog function real identity; input x; real x; begin identity=x; end endfunction '
        for value,code in [('identity((2147483647+1)-1)','unsupported_integer_arithmetic'),
                           ('identity(3)/2','parameter_type')]:
            source=PREFIX+definition+'parameter integer n='+value+'; analog begin V(y)<+n; end endmodule'
            with self.subTest(value=value), self.assertRaises(CompileError) as raised:
                compile_sources({'real-function-parameter.va':source},[Instance('dut','m',{'y':'y'},{})])
            self.assertEqual(raised.exception.diagnostic['code'],code)
    def test_old_real_function_through_rust(self):
        self.assertEqual(output('analog function real f; input x; real x,t; begin t=x/2; f=t; end endfunction','f(3.0)'),1.5)
    def test_unused_real_function_cannot_hide_voltage_access(self):
        with self.assertRaises(CompileError):
            program('analog function real f; input x; real x; begin if(x>0) f=x; else f=V(y); end endfunction','1')
    def test_hidden_invalid_arm_is_checked_after_discard(self):
        with self.assertRaises(CompileError):
            program('analog function real f; input x; real x,t; begin if(x>0) t=missing(x); else t=x; f=1; end endfunction','f(0)')
    def test_natural_expression_budget_exhausts_on_two_fresh_retries(self):
        definition='analog function real f; input x; real x; begin f=x+x; end endfunction'
        value='1'
        for _ in range(20): value='f('+value+')'
        for _ in range(2):
            with self.assertRaises(CompileError) as context: program(definition,value)
            self.assertEqual(context.exception.diagnostic['code'],'resource_budget')

if __name__=='__main__': unittest.main()

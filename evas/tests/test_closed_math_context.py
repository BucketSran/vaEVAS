"""Closed math must retain its existing lexical decision and index callbacks."""
GUARDS = ['LANG', 'EVENT-CONDITIONS']
import unittest
from evas import compile_sources,Instance,CompileError


def compile_function(op='exp',argument='1.0',trigger='@(timer(1))'):
    source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;real q;'
            'analog function real f;input x;real x;begin if(x>0)x=1.0;else x=2.0;f='+op+'(x);end endfunction '
            'analog begin @(initial_step)q=0;'+trigger+'q=f('+argument+');V(y)<+q;end endmodule')
    return compile_sources({'context.va':source},[Instance('dut','m',dict(u='u',y='y'))])


class ClosedMathContext(unittest.TestCase):
    def test_closed_function_operand_condition_survives_all_closed_math_routes(self):
        for op in ('cos','exp','ln','sqrt'):
            with self.subTest(op=op):compile_function(op).to_dict()

    def test_initial_function_operand_condition_keeps_the_same_context(self):
        compile_function(trigger='@(initial_step)').to_dict()

    def test_nonconstant_event_math_is_retained_inside_the_explicit_call(self):
        for op in ('cos','exp'):
            with self.subTest(op=op):compile_function(op,argument='V(u)').to_dict()
        # tanh still has its pre-existing source-event qualification refusal.
        with self.assertRaisesRegex(CompileError,'event bodies do not support history/operator calls'):
            compile_function('tanh',argument='V(u)')

    def test_function_argument_operator_qualification_is_unchanged(self):
        with self.assertRaisesRegex(CompileError,'event bodies do not support history/operator calls'):
            compile_function('tanh')
        with self.assertRaisesRegex(CompileError,'function arguments cannot contain history'):
            compile_function(argument='exp(1.0)')

    def test_static_names_and_direct_unconditional_domains_still_reject(self):
        with self.assertRaises(CompileError):compile_function(argument='missing')
        with self.assertRaises(CompileError):compile_function(op='missingfn')
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;'
                'analog begin @(initial_step)q=ln(-1.0);V(y)<+q;end endmodule')
        with self.assertRaisesRegex(CompileError,'finite function domain'):
            compile_sources({'context.va':source},[Instance('dut','m',dict(y='y'))])

"""Compile-only disabled system calls retain source guards and diagnostics."""
GUARDS = ["LANG"]
import json
import unittest
from evas import CompileError,Instance,compile_sources


def model(body,parameters='parameter real gate=0;'):
    return ('`include "disciplines.vams"\nmodule m(u,y,r);\n'
            'input u; output y; inout r; electrical u,y,r;\n'+parameters+'\n'
            'real q; integer seed;\nanalog begin\n'+body+'\nV(y,r)<+q;\nend\nendmodule\n')


def compile(body,parameters='parameter real gate=0;',overrides=None):
    return compile_sources({'disabled.va':model(body,parameters)},[Instance('dut','m',{'u':'u','y':'y','r':'0'},overrides or {})]).to_dict()


class DisabledSystemCalls(unittest.TestCase):
    def test_disabled_parameter_call_and_selected_else_compile_without_call_ir(self):
        body='@(initial_step) begin seed=1; q=2; if(gate>0) q=$anything(seed,0,1.0); else q=3; end'
        for gate in [0,-1]:
            program=compile(body,overrides={'gate':gate})
            self.assertNotIn('unsupported_system_call',json.dumps(program))
            self.assertNotIn('anything',json.dumps(program))

    def test_true_parameter_unselected_else_call_is_disabled(self):
        compile('@(initial_step) begin q=2; if(gate>0) q=3; else q=$anything(7); end',overrides={'gate':1})

    def test_nested_disabled_guard_inside_unknown_branch(self):
        compile('@(initial_step) begin q=2; if(V(u,r)>0) begin if(gate>0) q=$anything(seed,0,1.0); end end')

    def test_active_or_unknown_call_retains_original_diagnostic_and_source(self):
        body='@(initial_step) begin q=2; if(gate>0) q=$anything(seed,0,1.0); end'
        for guard,overrides in [('gate>0',{'gate':1}),('V(u,r)>0',{}),('q>0',{})]:
            with self.subTest(guard=guard):
                actual=body.replace('gate>0',guard)
                with self.assertRaises(CompileError) as got:compile(actual,overrides=overrides)
                self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')
                location=got.exception.diagnostic['location']
                self.assertEqual(location['source'],'disabled.va')
                self.assertEqual(location['line'],7)
                self.assertEqual(location['column'],actual.index('$')+1)
                self.assertIn('$anything',str(got.exception))

    def test_no_algebraic_or_invalid_predicate_can_hide_an_active_call(self):
        for expression in ['0*$anything(1)','(1.0/0.0)>0 ? $anything(1) : 0']:
            with self.subTest(expression=expression):
                with self.assertRaises(CompileError) as got:compile('@(initial_step) q='+expression+';')
                self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_malformed_call_is_still_a_parse_failure_in_dead_branch(self):
        for call in ['$anything(1,)', '$anything(1) 2', '$anything(1;']:
            with self.subTest(call=call):
                with self.assertRaises(CompileError):compile('@(initial_step) begin q=2; if(gate>0) q='+call+'; end')

    def test_each_instance_requires_its_own_parameter_proof(self):
        source=model('@(initial_step) begin q=2; if(gate>0) q=$anything(1); end')
        instances=[Instance('off','m',{'u':'u','y':'off','r':'0'},{}),Instance('on','m',{'u':'u','y':'on','r':'0'},{'gate':1})]
        for order in [instances,list(reversed(instances))]:
            with self.assertRaises(CompileError) as got:compile_sources({'disabled.va':source},order)
            self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')
            self.assertEqual(got.exception.diagnostic.get('instance'),'on')

    def test_arithmetic_guard_does_not_assume_a_real_rounding_contract(self):
        with self.assertRaises(CompileError) as got:
            compile('@(initial_step) begin q=2; if((10000000000000000.0+gate)-10000000000000000.0>0) q=$anything(1); end',overrides={'gate':1})
        self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_qualified_source_preserves_all_process_views_and_writer_structure(self):
        from evas.frontend import parse_sources
        from evas.parameters import bind_parameters
        from evas.native_audit import NativeAudit
        from evas.unreachable_system_calls import qualify
        from evas.syntax import Expr,Conditional,Token
        from dataclasses import fields,is_dataclass
        original=parse_sources({'disabled.va':model('@(initial_step) begin q=2; if(gate>0) q=$anything(1); end')})['m']
        owner=NativeAudit()
        result=qualify(original,bind_parameters(original,{},'off'),'off',owner)
        def calls(value):
            if isinstance(value,Token):return 0
            if isinstance(value,Expr) and value.op=='unsupported_system_call':return 1
            if is_dataclass(value):return sum(calls(getattr(value,f.name)) for f in fields(value))
            if isinstance(value,dict):return sum(calls(v) for v in value.values())
            if isinstance(value,(tuple,list)):return sum(calls(v) for v in value)
            return 0
        self.assertGreater(calls(original),0)
        self.assertEqual(calls(result),0)
        self.assertTrue(result.procedure)
        self.assertIsInstance(result.initial[1],Conditional)
        self.assertTrue(owner.active)
        self.assertGreater(owner.counts['dead_call_source_visit'],0)
        self.assertGreater(owner.counts['dead_call_dataclass_copy'],0)

    def test_native_audit_owner_is_shared_and_exhaustion_stays_sticky(self):
        from evas.frontend import parse_sources
        from evas.parameters import bind_parameters
        from evas.native_audit import NativeAudit
        from evas.unreachable_system_calls import qualify
        original=parse_sources({'disabled.va':model('@(initial_step) begin q=2; if(gate>0) q=$anything(1); end')})['m']
        parameters=bind_parameters(original,{},'off')
        owner=NativeAudit()
        owner.debit('previous_actual_work',99990)
        used=owner.used
        for attempt in range(2):
            with self.assertRaises(CompileError) as got:qualify(original,parameters,'off',owner)
            self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
            self.assertGreaterEqual(owner.used,used)
            if attempt == 1:
                self.assertEqual(owner.used,used)  # activation fails before new work
            used=owner.used
        self.assertGreater(owner.counts['previous_actual_work'],0)

    def test_public_compile_keeps_same_owner_and_plain_route_is_inactive(self):
        from evas.native_audit import NativeAudit
        from unittest.mock import patch
        import evas.frontend as frontend
        owner=NativeAudit()
        with patch.object(frontend,'NativeAudit',return_value=owner):
            program=compile_sources({'disabled.va':model('@(initial_step) begin q=2; if(gate>0) q=$anything(1); end')},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        self.assertIs(program._native_audit,owner)
        self.assertGreater(owner.counts['dead_call_source_visit'],0)
        plain=compile_sources({'plain.va':model('@(initial_step) q=2;')},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        self.assertEqual(plain._native_audit.counts['dead_call_source_visit'],0)

    def test_unselected_ternary_call_is_qualified_but_unknown_one_is_not(self):
        compile('@(initial_step) q=gate>0 ? $anything(1) : 2;')
        with self.assertRaises(CompileError) as got:
            compile('@(initial_step) q=V(u,r)>0 ? $anything(1) : 2;')
        self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_unlisted_system_identifier_without_parentheses_keeps_diagnostic(self):
        compile('@(initial_step) begin q=2; if(gate>0) q=$unlisted; end')
        with self.assertRaises(CompileError) as got:
            compile('@(initial_step) q=$unlisted;')
        self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_shared_ast_dead_occurrence_cannot_discharge_live_occurrence(self):
        from dataclasses import replace
        from evas.frontend import parse_sources
        from evas.parameters import bind_parameters
        from evas.native_audit import NativeAudit
        from evas.unreachable_system_calls import qualify
        original=parse_sources({'disabled.va':model('@(initial_step) begin q=2; if(gate>0) q=$anything(1); end')})['m']
        condition=original.initial[1]
        shared=replace(condition,else_body=condition.then_body)
        changed=replace(original,initial=[original.initial[0],shared])
        with self.assertRaises(CompileError) as got:
            qualify(changed,bind_parameters(changed,{},'off'),'off',NativeAudit())
        self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')


    def test_dead_call_arguments_keep_static_name_node_and_function_legality(self):
        for argument in ['missing', 'V(missing)', 'missingfn(1.0)']:
            with self.subTest(argument=argument):
                with self.assertRaises(CompileError) as got:
                    compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+argument+'); end')
                self.assertIn('missing',str(got.exception))

    def test_dead_call_valid_arguments_are_not_evaluated(self):
        for argument in ['seed', 'V(u,r)', '1.0/0.0', 'sqrt(-1.0)']:
            with self.subTest(argument=argument):
                compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+argument+'); end')

    def test_dead_call_arguments_keep_array_and_electrical_static_indices(self):
        declarations='parameter real gate=0; real values[0:1]; electrical [0:1] bus;'
        for argument in ['missing_values[0]', 'values[99]', 'V(missing_bus[0])', 'V(bus[99])', 'V(bus)']:
            with self.subTest(argument=argument):
                with self.assertRaises(CompileError):
                    compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+argument+'); end',declarations)
        for argument in ['values[0]', 'V(bus[1])']:
            with self.subTest(argument=argument):
                compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+argument+'); end',declarations)

    def test_dead_call_cannot_hide_invalid_dynamic_index_or_history_context(self):
        declarations='parameter real gate=0; real values[0:1];'
        for argument in ['values[q]', 'values[1/0]', 'idt(V(u,r),0.0)']:
            with self.subTest(argument=argument):
                with self.assertRaises(CompileError):
                    compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+argument+'); end',declarations)

    def test_function_local_shadow_does_not_prove_a_module_parameter_dead(self):
        function='analog function real f; input gate; real gate; begin if(gate>0) f=$anything(gate); else f=0.0; end endfunction\n'
        source=model('@(initial_step) q=f(1.0);').replace('analog begin\n',function+'analog begin\n',1)
        with self.assertRaises(CompileError) as got:
            compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
        self.assertEqual(got.exception.diagnostic['code'],'unsupported_system_function')

    def test_dead_call_cannot_hide_analog_function_arity(self):
        function='analog function real f; input x; real x; begin f=x; end endfunction\n'
        source=model('@(initial_step) begin q=2; if(gate>0) q=$anything(f(1.0,2.0)); end').replace('analog begin\n',function+'analog begin\n',1)
        with self.assertRaises(CompileError):
            compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])


    def test_dead_call_keeps_static_integer_operand_types(self):
        for expression in ['1.0&1', 'q&1', '1.0<<1', 'q<<1', '~q', '1|q', '1^q', 'q>>1', 'q%1']:
            with self.subTest(expression=expression):
                with self.assertRaises(CompileError):
                    compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+expression+'); end')

    def test_dead_integer_arguments_check_types_without_evaluating_values(self):
        for expression in ['seed&1', '1<<1', 'seed%1', '2147483647+1', '1/0']:
            with self.subTest(expression=expression):
                compile('@(initial_step) begin q=2; if(gate>0) q=$anything('+expression+'); end')

    def test_dead_array_operand_keeps_declared_element_type(self):
        for declaration,accepted in [('integer values[0:1];',True),('real values[0:1];',False)]:
            with self.subTest(declaration=declaration):
                body='@(initial_step) begin q=2; if(gate>0) q=$anything(values[0]&1); end'
                if accepted:compile(body,'parameter real gate=0;'+declaration)
                else:
                    with self.assertRaises(CompileError):compile(body,'parameter real gate=0;'+declaration)

    def test_dead_function_argument_type_respects_local_shadowing(self):
        for local_type,accepted in [('real',False),('integer',True)]:
            function=('analog function real f; input gate; '+local_type+' gate; '
                      'begin if(0>0) f=$anything(gate&1); else f=0.0; end endfunction\n')
            source=model('@(initial_step) q=2;','parameter integer gate=0;').replace('analog begin\n',function+'analog begin\n',1)
            with self.subTest(local_type=local_type):
                if accepted:
                    compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()
                else:
                    with self.assertRaises(CompileError) as got:
                        compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
                    self.assertEqual(got.exception.diagnostic['code'],'unsupported_integer_bitwise')

    def test_dead_function_result_keeps_declared_return_type(self):
        for return_type,accepted in [('real',False),('integer',True)]:
            function=('analog function '+return_type+' f; input x; integer x; '
                      'begin f=x; end endfunction\n')
            source=model('@(initial_step) begin q=2; if(gate>0) q=$anything(f(1)&1); end').replace('analog begin\n',function+'analog begin\n',1)
            with self.subTest(return_type=return_type):
                if accepted:
                    compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})]).to_dict()
                else:
                    with self.assertRaises(CompileError) as got:
                        compile_sources({'disabled.va':source},[Instance('dut','m',{'u':'u','y':'y','r':'0'})])
                    self.assertEqual(got.exception.diagnostic['code'],'unsupported_integer_bitwise')

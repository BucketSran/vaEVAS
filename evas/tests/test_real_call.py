"""Executable pure calls preserve assignments independently of return use."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
import unittest
from evas import compile_sources, Instance, CompileError

def compile_call(function='if(x>0)z=1.0/0.0;else z=0.0;f=2.0;', argument='1.0', body=None, extra='', wire=True):
    source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;real q,a;'
      +extra+'analog function real f;input x;real x,z;begin '+function+'end endfunction '
      'analog begin '+(body or '@(initial_step)q=f('+argument+');')+'V(y)<+q;end endmodule')
    program=compile_sources({'call.va':source},[Instance('dut','m',dict(u='u',y='y'))])
    return program.to_dict() if wire else program

def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,(tuple,list)):
        for child in value:yield from nodes(child)

class RealCallContract(unittest.TestCase):
    def test_identity_retains_source_sample_and_copy_return_boundaries(self):
        p=compile_call('f=x;', argument='V(u)-1.0')
        self.assertFalse(p['real_bindings'])
        self.assertFalse(any(n.get('op')=='real_call' for n in nodes(p)))
        expression=p['events'][0]['body'][0]['rhs']
        boundaries=[n for n in nodes(expression) if n.get('op')=='real_boundary']
        self.assertIn('argument',[n['kind'] for n in boundaries])
        self.assertIn('return',[n['kind'] for n in boundaries])
        self.assertIn('sample',[n['kind'] for n in boundaries])
        subtract=next(n for n in nodes(expression) if n.get('operation')=='subtract')
        self.assertEqual(subtract['left']['kind'],'sample')
        for boundary in boundaries:
            self.assertEqual(boundary['origin']['instance'],'dut')
        returned=next(n for n in boundaries if n['kind']=='return')
        self.assertEqual(returned['value']['kind'],'argument')
        self.assertTrue(returned['origin']['expansion'])
        # A differential voltage must be sampled as one physical expression,
        # before any function copy/return rounding (not as two RN voltages).
        differential=compile_call('f=x;',body='@(timer(1))q=f(V(u,y));')
        samples=[n for n in nodes(differential['events'])
                 if n.get('op')=='real_boundary' and n.get('kind')=='sample']
        self.assertTrue(any(len(n['value'].get('terms',()))==2 for n in samples))

    def test_identity_does_not_elide_fault_effect_argument(self):
        extra=('analog function real g;input v;real v,z;begin '
               'if(v>0)z=1.0/0.0;else z=0.0;g=2.0;end endfunction ')
        p=compile_call('f=x;',argument='g(1.0)',extra=extra)
        calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),1)
        self.assertTrue(any(n.get('operation')=='divide' for n in nodes(calls[0])))
        with self.assertRaisesRegex(CompileError,'division by zero'):
            compile_call('f=x;',argument='1.0/0.0')

    def test_identity_qualification_excludes_additional_body_effects(self):
        for body in ('z=x;f=x;', 'f=x;f=x;', 'if(x>0)f=x;else f=x;'):
            p=compile_call(body)
            self.assertTrue(any(n.get('op')=='real_call' for n in nodes(p['events'])))

    def test_closed_call_math_keeps_all_source_effects(self):
        for body in ('f=x+1.0;', 'z=x+1.0;z=x+2.0;f=z;',
                     'if(x>0)z=1.0/0.0;else z=0.0;f=2.0;'):
            p=compile_call(body,body='@(timer(1))q=cos(f(1.0));')
            calls=[n for n in nodes(p['operators']) if n.get('op')=='real_call']
            self.assertEqual(len(calls),1)
            self.assertEqual(p['operators'][-1]['function'],'cos')
            if '1.0/0.0' in body:
                self.assertTrue(any(n.get('operation')=='divide' for n in nodes(calls[0])))

    def test_call_math_keeps_unknown_argument_and_guard_for_native_proof(self):
        for body in ('f=2.0;', 'z=x;z=0.0;f=2.0;', 'if(x>0)f=2.0;else f=2.0;'):
            p=compile_call(body,body='@(timer(1))q=cos(f(V(u)));')
            call=p['operators'][-1]['input']
            self.assertEqual(call['op'],'real_call')
            self.assertTrue(any(n.get('kind')=='sample' for n in nodes(call)))
            self.assertEqual(p['operators'][-1]['function'],'cos')

    def test_call_math_unselected_bad_native_domain_is_retained_lazily(self):
        for argument in ('-1.0','1.0','V(u)'):
            p=compile_call('if(x>0)f=2.0;else f=ln(-1.0);',
                          body='@(timer(1))q=cos(f('+argument+'));')
            self.assertEqual([o.get('function') for o in p['operators']],['ln','cos'])
            call=p['operators'][-1]['input']
            branch=next(n for n in nodes(call) if n.get('kind')=='procedure_if')
            self.assertTrue(any(n.get('op')=='operator' for n in nodes(branch['else_body'])))
            self.assertFalse(any(n.get('op')=='operator' for n in nodes(branch['then_body'])))

    def test_later_math_consumer_discovers_inner_call_operator_scope(self):
        for body in ('f=exp(x);', 'if(x>0)f=2.0;else f=ln(x);'):
            p=compile_call(body,body='@(timer(1))q=cos(f(V(u)));')
            self.assertEqual(p['operators'][-1]['function'],'cos')
            self.assertEqual(p['operators'][-1]['input']['op'],'real_call')
            self.assertTrue(any(n.get('op')=='real_local' for n in nodes(p['operators'][0])))

    def test_nested_call_inside_operator_discovers_complete_enclosing_scope(self):
        extra='analog function real g;input v;real v;begin g=exp(v);end endfunction '
        p=compile_call('f=exp(g(x));',body='@(timer(1))q=cos(f(V(u)));',extra=extra)
        self.assertEqual([o['function'] for o in p['operators']],['exp','exp','cos'])
        self.assertEqual(sum(n.get('op')=='real_call' for n in nodes(p['operators'])),2)

    def test_operator_discovery_does_not_waive_escape_or_cross_call_checks(self):
        from dataclasses import replace
        p=compile_call('f=exp(x);',body='@(timer(1))begin q=cos(f(V(u)));q=cos(f(1.0));end ',wire=False)
        first,second=p.operators[1].input,p.operators[3].input
        with self.assertRaisesRegex(CompileError,'external local|escapes|ownership'):
            replace(p,operators=(replace(p.operators[0],input=second.result),*p.operators[1:])).to_dict()
        with self.assertRaisesRegex(CompileError,'escapes|syntactic owning'):
            replace(p,operators=(p.operators[0],replace(p.operators[1],input=first.result),*p.operators[2:])).to_dict()

    def test_call_operator_discovery_uses_same_owner_and_sticky_limit(self):
        p=compile_call('f=exp(x);',body='@(timer(1))q=cos(f(V(u)));',wire=False)
        owner=p._native_audit;p.to_dict()
        self.assertGreater(owner.counts['program_real_discovery_visit'],0)
        for _ in range(1000):
            try:p.to_dict()
            except CompileError:break
        else:self.fail('discovery did not use original request cap')
        for _ in range(2):
            before=owner.used
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(owner.used,before)
        fresh=compile_call('f=exp(x);',body='@(timer(1))q=cos(f(V(u)));',wire=False)
        self.assertIsNot(fresh._native_audit,owner);fresh.to_dict()

    def test_call_math_scan_prepays_container_and_uses_existing_schema(self):
        from unittest.mock import patch
        import inspect
        from evas.native_audit import NativeAudit
        original=NativeAudit.debit
        observed=set()
        def charged(owner,kind,*args,**kwargs):
            frame=inspect.currentframe().f_back
            if frame.f_code.co_name=='function_math_value':
                if kind=='function_math_call_scan_container':
                    self.assertNotIn('pending',frame.f_locals)
                    observed.add('container')
                if kind=='function_math_call_scan_fields':
                    self.assertIsInstance(frame.f_locals['descriptor'],dict)
                    observed.add('fields')
            return original(owner,kind,*args,**kwargs)
        with patch.object(NativeAudit,'debit',charged):
            compile_call('f=x+1.0;',body='@(timer(1))q=cos(1.0+f(V(u)));')
        self.assertEqual(observed,{'container','fields'})

    def test_all_existing_math_consumers_lower_call_argument_only_once(self):
        for function in ('cos','exp','ln','sqrt','tanh'):
            trigger='initial_step' if function=='tanh' else 'timer(1)'
            with self.subTest(function=function):
                p=compile_call('f=x+1.0;',body='@('+trigger+')q='+function+'(f(1.0));')
                calls=[n for n in nodes(p['operators']) if n.get('op')=='real_call']
                self.assertEqual(len(calls),1)
                self.assertEqual(len(calls[0]['bindings']),len(p['real_bindings']))
                self.assertEqual(p['operators'][-1]['function'],function)
                self.assertEqual(calls[0]['origin']['instance'],'dut')
                self.assertTrue(calls[0]['origin']['expansion'])
        for function in ('cos','exp','ln','sqrt'):
            with self.subTest(function=function,argument='input'):
                p=compile_call('f=x+1.0;',body='@(timer(1))q='+function+'(f(V(u)));')
                self.assertEqual(p['operators'][-1]['function'],function)
                self.assertEqual(sum(n.get('op')=='real_call' for n in nodes(p)),1)
                self.assertFalse(any(n.get('op')=='event_math' for n in nodes(p)))

    def test_sqrt_ln_call_consumption_preserves_selected_unused_and_overwritten_effects(self):
        for function in ('ln','sqrt'):
            p=compile_call('z=x;z=0.0;if(x>0)z=1.0/0.0;else z=0.0;f=2.0;',
                          body='@(timer(1))q='+function+'(f(1.0));')
            call=p['operators'][-1]['input']
            self.assertEqual(call['op'],'real_call')
            self.assertTrue(any(n.get('operation')=='divide' for n in nodes(call)))
            self.assertEqual(len(call['body']),5)
            self.assertEqual(call['body'][1]['action']['binding'],call['body'][2]['action']['binding'])

    def test_ln_sqrt_identity_and_noncall_samples_keep_legacy_representation(self):
        for function in ('ln','sqrt'):
            identity=compile_call('f=x;',body='@(timer(1))q='+function+'(f(1.0));')
            self.assertFalse(identity['operators']);self.assertFalse(identity['real_bindings'])
            self.assertTrue(any(n.get('kind')=='argument' for n in nodes(identity)))
            sample=compile_call('f=x;',body='@(timer(1))q='+function+'(V(u));')
            self.assertTrue(any(n.get('function')==function for n in nodes(sample)))
            self.assertFalse(sample['real_bindings'])
        # This patch does not widen the old event-body tanh source gate.
        with self.assertRaises(CompileError):
            compile_call('f=x+1.0;',body='@(timer(1))q=tanh(f(1.0));')

    def test_unused_selected_rhs_is_an_effect_step(self):
        p=compile_call();calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),1);call=calls[0]
        self.assertEqual([s['expanded_statement_ordinal'] for s in call['body']],[0,1,4])
        self.assertEqual(call['body'][0]['action']['value']['kind'],'argument')
        branch=call['body'][1]['action'];self.assertEqual(branch['kind'],'procedure_if')
        self.assertEqual(branch['then_body'][0]['action']['value']['value']['operation'],'divide')
        self.assertEqual(branch['then_body'][0]['expanded_statement_ordinal'],2)
        self.assertEqual(branch['else_body'][0]['expanded_statement_ordinal'],3)
        self.assertEqual(call['result']['binding'],call['body'][-1]['action']['binding'])
        self.assertEqual(len(p['real_bindings']),3) # no compatibility-preview orphans

    def test_false_true_unknown_keep_the_same_body_and_domain(self):
        for argument in ('-1.0','1.0','V(u)'):
            with self.subTest(argument=argument):
                p=compile_call(argument=argument)
                call=next(n for n in nodes(p['events']) if n.get('op')=='real_call')
                self.assertTrue(any(n.get('operation')=='divide' for n in nodes(call['body'])))

    def test_overwritten_and_discarded_arguments_keep_source_order(self):
        p=compile_call('z=x+1.0;z=x+2.0;f=2.0;',body='a=1.0;q=f(a);')
        call=next(n for n in nodes(p['procedures']) if n.get('op')=='real_call')
        actions=[s['action'] for s in call['body']]
        self.assertEqual([a['value']['kind'] for a in actions],['argument','store','store','return'])
        self.assertEqual(actions[1]['binding'],actions[2]['binding'])
        self.assertNotEqual(actions[0]['binding'],actions[-1]['binding'])

    def test_nested_call_has_an_independent_namespace_and_owned_slots(self):
        extra='analog function real g;input v;real v;begin g=v+1.0;end endfunction '
        p=compile_call('z=g(x);f=z+1.0;',extra=extra)
        calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),2)
        self.assertFalse(set(calls[0]['bindings']) & set(calls[1]['bindings']))
        self.assertEqual(calls[1]['body'][0]['expanded_statement_ordinal'],0)
        self.assertGreater(len(calls[1]['origin']['expansion']),len(calls[0]['origin']['expansion']))

    def test_call_as_arithmetic_operand_does_not_lose_effects(self):
        p=compile_call(body='@(initial_step)q=f(1.0)+1.0;')
        self.assertTrue(any(n.get('op')=='real_call' for n in nodes(p['events'])))

    def test_all_arm_static_errors_and_original_purity_stay_visible(self):
        for rhs in ('missing','missingfn(x)','1.0&1','V(missing)','idt(x,0)'):
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):
                compile_call('if(x>0)z='+rhs+';else z=0.0;f=2.0;',argument='-1.0')

    def test_math_input_reads_owned_snapshot_and_call_occurrences_are_distinct(self):
        p=compile_call('f=exp(x);',body='a=1.0;q=f(a);a=2.0;q=f(a);')
        calls=[n for n in nodes(p['procedures']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),2);self.assertFalse(set(calls[0]['bindings'])&set(calls[1]['bindings']))
        self.assertEqual(len(p['operators']),2)
        for call,operator in zip(calls,p['operators']):
            self.assertIn(operator['input']['binding'],call['bindings'])
        self.assertNotEqual(calls[0]['origin']['expansion'],calls[1]['origin']['expansion'])

    def test_integer_formal_copy_in_retains_existing_half_away_conversion(self):
        for argument,want in (('1.5',2.0),('-1.5',-2.0)):
            source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;'
              'analog function real f;input x;integer x;begin f=x;end endfunction '
              'analog begin @(initial_step)q=f('+argument+');V(y)<+q;end endmodule')
            p=compile_sources({'integer.va':source},[Instance('dut','m',dict(y='y'))]).to_dict()
            call=next(n for n in nodes(p['events']) if n.get('op')=='real_call')
            value=call['body'][0]['action']['value']['value']
            self.assertTrue(any(n.get('constant')==want for n in nodes(value)))

    def test_nested_integer_implicit_return_is_an_explicit_assignment(self):
        extra='analog function integer g;input v;integer v;begin if(v>0)g=7;end endfunction '
        p=compile_call('f=g(x);',argument='-1.5',extra=extra)
        calls=[n for n in nodes(p['events']) if n.get('op')=='real_call']
        self.assertEqual(len(calls),2)
        child=calls[1];default=child['body'][1]['action']
        self.assertEqual(default['binding'],child['result']['binding'])
        self.assertEqual(default['value']['value']['constant'],0.0)
        self.assertTrue(any(n.get('constant')==-2.0 for n in nodes(child['body'][0]['action']['value'])))

    def test_typed_wire_rejects_duplicate_or_uninitialised_call_slots(self):
        from dataclasses import replace
        program=compile_call(wire=False)
        assignment=program.events[0].body[0]
        call=assignment.rhs.value
        for bad in (replace(call,bindings=(*call.bindings,call.bindings[0])),
                    replace(call,body=call.body[:-1])):
            event=replace(program.events[0],body=(replace(assignment,rhs=replace(assignment.rhs,value=bad)),))
            with self.subTest(bad=bad.bindings),self.assertRaisesRegex(CompileError,'IR33:'):
                replace(program,events=(event,)).to_dict()

    def test_original_owner_charges_call_work_and_failed_retry_is_sticky(self):
        program=compile_call(wire=False);owner=program._native_audit
        self.assertTrue(owner.active)
        self.assertGreater(owner.counts['real_call_statement'],0)
        self.assertGreater(owner.counts['real_call_source_copy'],0)
        for _ in range(100):
            try:program.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('real validation did not reach unchanged request limit')
        used=owner.used
        for _ in range(2):
            with self.assertRaises(CompileError):program.to_dict()
            self.assertGreater(owner.used,used);used=owner.used
        fresh=compile_call(wire=False)
        self.assertIsNot(fresh._native_audit,owner)
        fresh.to_dict()

    def test_function_ternary_and_short_circuit_keep_lazy_numeric_arms(self):
        for function in ('f=(x>0)?1.0/0.0:2.0;', 'f=(x>0)&&(1.0/0.0>0);'):
            for argument in ('-1.0','1.0','V(u)'):
                with self.subTest(function=function,argument=argument):
                    p=compile_call(function,argument)
                    self.assertTrue(any(n.get('operation')=='divide' for n in nodes(p['events'])))

    def test_unconditional_literal_zero_and_dead_integer_domain_keep_old_refusal(self):
        with self.assertRaisesRegex(CompileError,'division by zero'):
            compile_call('z=1.0/0.0;f=2.0;')
        with self.assertRaises(CompileError):
            compile_call('f=(x>0)?(1/0):2;',argument='-1.0')

    def test_branch_guard_keeps_its_predicate_degree(self):
        function='if(x>0)f=1.0;else f=2.0;'
        compile_call(function,body='if(f(V(u))>0)q=1;else q=2;')
        with self.assertRaises(CompileError):
            compile_call(function,body='if(f(V(u))*V(u)>0)q=1;else q=2;')

    def test_final_dependency_union_charges_accumulated_source_entries(self):
        names=['u'+str(i) for i in range(10)]
        args=['a'+str(i) for i in range(10)]
        total='+'.join('V('+name+')' for name in names)
        source=('`include "disciplines.vams"\nmodule m('+','.join([*names,'y'])+');'
          'input '+','.join(names)+';output y;electrical '+','.join([*names,'y'])+';real q;'
          'analog function real f;input '+','.join(args)+';real '+','.join(args)+';begin f=a0;end endfunction '
          'analog begin @(initial_step)q=f('+','.join([total]*10)+');V(y)<+q;end endmodule')
        p=compile_sources({'dependencies.va':source},[Instance('dut','m',{name:name for name in [*names,'y']})])
        owner=p._native_audit
        self.assertEqual(len(p.real_bindings),11)
        # Ten actuals and the return each retain all ten inputs plus ground.
        self.assertEqual(owner.counts['real_call_result_dependency_entry'],2*11*11)
        self.assertEqual(owner.counts['real_call_result_dependency_handle'],2*11)
        self.assertEqual(owner.counts['real_call_result_dependency_container'],1)
        p.to_dict()

    def test_same_object_call_in_two_serialized_positions_is_rejected(self):
        from dataclasses import replace
        p=compile_call(wire=False);event=p.events[0];assignment=event.body[0]
        # Python DAG sharing cannot waive the two wire-level occurrences.
        duplicate=replace(p,events=(replace(event,body=(assignment,assignment)),))
        with self.assertRaisesRegex(CompileError,'binding shared between calls'):
            duplicate.to_dict()

    def test_same_call_in_two_expression_positions_is_rejected(self):
        from dataclasses import replace
        from evas.ir import RealBinary
        p=compile_call(wire=False);event=p.events[0];assignment=event.body[0]
        boundary=assignment.rhs;call=boundary.value
        expression=RealBinary('add',call,call,call.origin)
        forged=replace(p,events=(replace(event,body=(replace(assignment,rhs=replace(boundary,value=expression)),)),))
        with self.assertRaisesRegex(CompileError,'binding shared between calls'):
            forged.to_dict()

    def test_one_dynamic_loop_body_call_is_one_syntactic_owner(self):
        source=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;integer i,n;'
          'analog function real f;input x;real x;begin f=x+1.0;end endfunction '
          'analog begin @(initial_step)n=2;@(timer(1))begin for(i=1;i<=n;i=i+1)q=f(i);end end endmodule')
        p=compile_sources({'loop.va':source},[Instance('dut','m',dict(y='y'))]).to_dict()
        calls=[node for node in nodes(p['events']) if node.get('op')=='real_call']
        self.assertEqual(len(calls),1)
        self.assertEqual(len(p['real_bindings']),2)

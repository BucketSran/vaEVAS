"""Source real arithmetic and captures survive compilation to the public IR.

These are compiler/transport checks. Numeric execution uses the independent
binary64 cases once the matching Rust consumer is available.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
import unittest

from evas import CompileError, Instance, compile_sources


def compile_body(body, declarations='real a,q;'):
    source=('`include "disciplines.vams"\nmodule m(u,y,r); '
            'input u; output y; inout r; electrical u,y,r; '
            +declarations+' analog begin '+body+' end endmodule')
    return compile_sources({'real.va':source},[Instance('dut','m',dict(u='u',y='y',r='0'),{})]).to_dict()


def nodes(value):
    if isinstance(value,dict):
        yield value
        for item in value.values():
            yield from nodes(item)
    elif isinstance(value,(list,tuple)):
        for item in value:
            yield from nodes(item)


class ProgramRealCompilerContracts(unittest.TestCase):
    def test_integer_initial_piecewise_leaf_arithmetic_keeps_guard_and_rn_tree(self):
        for operation in ('+1.0','-1.0','*2.0'):
            with self.subTest(operation=operation):
                program=compile_body('@(initial_step)i=((V(u,r)>0.5)?1.0:2.0)'+operation+'; V(y,r)<+i;',
                                     'integer i;')
                rhs=program['events'][0]['body'][0]['rhs']
                self.assertEqual(rhs['op'],'real_binary')
                self.assertEqual(rhs['left']['op'],'select')
                self.assertEqual(sum(n.get('op')=='select' for n in nodes(rhs)),1)
        for value in ('((V(u,r)>0.5)?1.0:2.0)/2.0',
                      '((V(u,r)>0.5)?2147483647.0:1.0)+1.0',
                      '((V(u,r)>0.5)?1.25:2.25)+1.0'):
            with self.subTest(value=value),self.assertRaises(CompileError):
                compile_body('@(initial_step)i='+value+'; V(y,r)<+i;','integer i;')

    def test_integer_initial_arms_recognize_closed_rounded_real_operations(self):
        for value in ('1.0+1.0',
                      '(9007199254740992.0+1.0)-9007199254740992.0',
                      '(3.0/10.0)-0.3'):
            with self.subTest(value=value):
                program=compile_body('@(initial_step) i='+value+'; V(y,r)<+i;','integer i;')
                initial=program['events'][0]
                self.assertEqual(initial['trigger']['kind'],'initial_step')
                self.assertEqual(program['states'][0]['initial'],0.0)
                self.assertEqual(initial['body'][0]['rhs']['op'],'real_binary')
        for value in ('1.0+0.5','2147483647.0+1.0','V(u,r)+1.0'):
            with self.subTest(value=value),self.assertRaises(CompileError):
                compile_body('@(initial_step) i='+value+'; V(y,r)<+i;','integer i;')

    def test_ir33_idt_pulse_keeps_original_reset_and_unique_source_bodies(self):
        for events in ('@(timer(1,1)) reset=1;',
                       '@(timer(1,1)) reset=1; @(timer(2,2)) reset=1;',
                       '@(timer(1,1) or cross(V(u,r)-0.5,+1)) reset=1;',
                       '@(timer(1,1)) if(V(u,r)>0.5) reset=1;'):
            with self.subTest(events=events):
                program=compile_body('reset=0; '+events+'V(y,r)<+idt(1.0,0.25,reset);','integer reset;')
                self.assertEqual([s['name'] for s in program['states']],['reset'])
                self.assertEqual(len(program['operators']),1)
                self.assertEqual(program['operators'][0]['kind'],'idt')
                self.assertEqual(program['operators'][0]['reset'],{'op':'state','state':0})
                ordinary=program['procedures'][0]['body'][0]['action']
                self.assertEqual(ordinary['kind'],'assign')
                self.assertEqual(ordinary['rhs']['constant'],0.0)
                assigns=[n for n in nodes(program['events']) if n.get('kind')=='assign']
                self.assertEqual(len(assigns),2 if events.count('@')==2 else 1)
                self.assertTrue(all(n['rhs']['constant']==1.0 for n in assigns))
        program=compile_body('reset=0; @(timer(1))reset=1; V(y,r)<+idt(1,0,reset); '
            '@(timer(1))reset=0; V(y,r)<+idt(2,0.5,reset);','integer reset;')
        self.assertEqual(len(program['operators']),2)
        self.assertTrue(all(o['reset']=={'op':'state','state':0} for o in program['operators']))
        self.assertNotEqual(program['operators'][0]['origin']['column'],program['operators'][1]['origin']['column'])
        self.assertEqual([s['action']['kind'] for s in program['procedures'][0]['body']],
                         ['assign','event_gate','contribution_capture','event_gate','contribution_capture'])

    def test_state_identity_function_boundaries_activate_without_closed_proof(self):
        from unittest.mock import patch
        from evas.program_real_facts import ProgramRealFacts
        def source(count):
            return ('`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; real q; '
                    'analog function real f; input x; real x; begin f=x; end endfunction analog begin '+
                    '@(timer(1)) q=f(q); '*count+'V(y,r)<+q; end endmodule')
        instances=[Instance('dut','m',dict(y='y',r='0'))]
        with patch.object(ProgramRealFacts,'query',side_effect=AssertionError('identity needs no closed proof')):
            program=compile_sources({'identity.va':source(100)},instances)
            wire=program.to_dict()
        owner=program._native_audit
        self.assertTrue(owner.active)
        self.assertFalse(program.real_bindings)
        self.assertFalse(any(n.get('op') in ('real_binary','select') for n in nodes(wire)))
        self.assertTrue(any(n.get('kind')=='argument' for n in nodes(wire)))
        with self.assertRaises(CompileError):
            program.to_dict()
        for _ in range(2):
            used=owner.used
            with self.assertRaises(CompileError):
                program.to_dict()
            self.assertGreater(owner.used,used)
        with self.assertRaises(CompileError):
            compile_sources({'identity.va':source(176)},instances).to_dict()

    def test_closed_function_guard_activates_owner_without_binary_or_binding(self):
        def source(count):
            return ('`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; real q; '
                    'analog function real f; input x; real x; begin f=x; end endfunction analog begin '+
                    '@(timer(1)) q=cos(f(1.0)); '*count+'V(y,r)<+q; end endmodule')
        instances=[Instance('dut','m',dict(y='y',r='0'))]
        program=compile_sources({'boundary.va':source(100)},instances)
        owner=program._native_audit
        self.assertTrue(owner.active)
        wire=program.to_dict()
        self.assertFalse(program.real_bindings)
        self.assertFalse(any(n.get('op')=='real_binary' for n in nodes(wire)))
        self.assertTrue(any(n.get('op')=='select' for n in nodes(wire)))
        with self.assertRaises(CompileError):
            program.to_dict()
        for _ in range(2):
            used=owner.used
            with self.assertRaises(CompileError):
                program.to_dict()
            self.assertGreater(owner.used,used)
        with self.assertRaises(CompileError):
            compile_sources({'boundary.va':source(176)},instances).to_dict()

    def test_closed_integer_alias_retains_original_evaluation_and_source_position(self):
        program=compile_body('a=2.0; i=a; a=3.0; V(y,r)<+i;', 'real a; integer i;')
        self.assertEqual(program['contributions'][0]['rhs']['constant'],-2.0)  # Canonical branch is r→y.
        bindings=[s['action'] for s in program['procedures'][0]['body'] if s['action']['kind']=='real_bind']
        self.assertEqual(len(bindings),3)
        self.assertEqual(bindings[1]['value']['value'],{'op':'real_local','binding':0})
        program=compile_body('a=2.0;i=a;@(timer(1))q=i;a=3.0;i=a;@(timer(2))q=i;V(y,r)<+q;',
                             'real a,q; integer i;')
        self.assertEqual([e['body'][0]['rhs']['value']['constant'] for e in program['events']],[2.0,3.0])
        program=compile_body('i=(9007199254740992.0+1.0)-9007199254740992.0; V(y,r)<+i;', 'integer i;')
        self.assertEqual(program['contributions'][0]['rhs']['constant'],0.0)
        self.assertEqual(program['procedures'][0]['body'][0]['action']['value']['value']['operation'],'subtract')
        for body in ('a=2.5;i=a;','a=2147483648.0;i=a;',
                     '@(initial_step)a=2; @(timer(1))a=3; i=a;',
                     'a=V(u,r);i=a;',
                     'if(V(u,r)>0.5)a=2.0;else a=2.0;i=a;'):
            with self.subTest(body=body),self.assertRaises(CompileError):
                compile_body(body+'V(y,r)<+i;', 'real a; integer i;')

    def test_integer_function_closed_real_conversion_keeps_existing_ties_away(self):
        declarations='''integer i; analog function integer f; input x; real x;
            begin f=x+0.5; end endfunction'''
        for argument,expected in (('1.0',2.0),('-2.0',-2.0)):
            program=compile_body('i=f('+argument+'); V(y,r)<+i;',declarations)
            self.assertEqual(program['contributions'][0]['rhs']['constant'],-expected)
            guard=next(n for n in nodes(program['procedures']) if n.get('op')=='select')
            self.assertEqual(guard['left']['op'],'real_binary')
            self.assertEqual(guard['left']['operation'],'add')
            self.assertEqual(guard['then_value']['constant'],expected)
        with self.assertRaises(CompileError):
            compile_body('i=f(2147483647.0);V(y,r)<+i;',declarations)

    def test_fixed_trigger_argument_activates_actual_shared_owner_and_sticky_limit(self):
        def source(count):
            return ('`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; '
                    'real q; analog begin '+'@(timer(1.0+1.0,2,0)) q=1; '*count+
                    'V(y,r)<+q; end endmodule')
        instances=[Instance('dut','m',dict(y='y',r='0'))]
        program=compile_sources({'fixed.va':source(100)},instances)
        owner=program._native_audit
        self.assertTrue(owner.active)
        self.assertEqual(len(program.real_bindings),100)
        program.to_dict()
        with self.assertRaises(CompileError) as failure:
            for _ in range(10):
                program.to_dict()
        self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')
        for _ in range(2):
            used=owner.used
            with self.assertRaises(CompileError):
                program.to_dict()
            self.assertGreater(owner.used,used)
        self.assertEqual(owner.used,sum(owner.counts.values()))
        with self.assertRaises(CompileError) as failure:
            compile_sources({'fixed.va':source(176)},instances).to_dict()
        self.assertEqual(failure.exception.diagnostic['code'],'resource_budget')

    def test_closed_initial_real_power_keeps_state_gate_and_native_boxes(self):
        program=compile_body('''@(initial_step)
            q=pow(((9007199254740992.0+1.0)-9007199254740992.0)+2.0,0.0+0.25);
            V(y,r)<+q;''', 'real q;')
        self.assertEqual(len(program['states']),1)
        self.assertEqual(program['states'][0]['initial'],0.0)
        self.assertEqual(len(program['events']),1)
        event=program['events'][0]
        self.assertEqual(event['trigger']['kind'],'initial_step')
        self.assertEqual(event['body'][0]['state'],0)
        self.assertEqual(event['body'][0]['rhs']['kind'],'store')
        self.assertEqual(event['body'][0]['rhs']['value']['kind'],'sample')
        self.assertEqual([o['function'] for o in program['operators']],['ln','exp'])
        base=program['operators'][0]['input']
        self.assertEqual(base['kind'],'argument')
        self.assertEqual(base['value']['operation'],'add')
        self.assertEqual(base['value']['left']['operation'],'subtract')
        exponent=program['operators'][1]['input']
        self.assertEqual(exponent['op'],'multiply')  # Synthetic native math, not a source real op.
        self.assertEqual(exponent['left']['kind'],'argument')
        self.assertEqual(exponent['left']['value']['operation'],'add')
        self.assertEqual(program['procedures'][0]['body'][0]['action'],{'kind':'event_gate','event':0})
        for base in ('0.0','-2.0','(9007199254740992.0+1.0)-9007199254740992.0'):
            with self.subTest(base=base),self.assertRaises(CompileError):
                compile_body('@(initial_step) q=pow('+base+',0.0+0.25); V(y,r)<+q;', 'real q;')

    def test_fixed_timer_preserves_closed_arguments_immediately_before_gate(self):
        program=compile_body('''@(timer((9007199254740992.0+1.0)-9007199254740992.0,
            1.0+1.0,0.0+0.0,1.0+0.0)) q=1; V(y,r)<+q;''')
        trigger=program['events'][0]['trigger']
        self.assertEqual(trigger['kind'],'timer')
        self.assertEqual(trigger['start'],0.0)
        self.assertEqual(trigger['period'],2.0)
        self.assertEqual(trigger['time_tolerance'],0.0)
        steps=program['procedures'][0]['body']
        self.assertEqual([s['action']['kind'] for s in steps[:5]],['real_bind']*4+['event_gate'])
        self.assertEqual([s['expanded_statement_ordinal'] for s in steps[:5]],list(range(5)))
        operations=[s['action']['value']['value']['operation'] for s in steps[:4]]
        self.assertEqual(operations,['subtract','add','add','add'])
        self.assertEqual(program['events'][0]['expanded_statement_ordinal'],4)
        self.assertTrue(all(s['action']['value']['kind']=='argument' for s in steps[:4]))
        with self.assertRaisesRegex(CompileError,'zero time_tol requires fixed'):
            compile_body('@(initial_step) a=1; @(timer(a,2,0)) q=1; V(y,r)<+q;')

    def test_cross_settings_retain_source_local_snapshot_and_argument_order(self):
        program=compile_body('a=1.0+1.0; @(cross(V(u,r)-0.5,1,a,a)) q=1; V(y,r)<+q;')
        trigger=program['events'][0]['trigger']
        self.assertEqual((trigger['time_tolerance'],trigger['expression_tolerance']),(2.0,2.0))
        steps=program['procedures'][0]['body']
        self.assertEqual([s['action']['kind'] for s in steps[:4]],['real_bind']*3+['event_gate'])
        self.assertEqual(steps[0]['action']['value']['kind'],'snapshot')
        for step in steps[1:3]:
            self.assertEqual(step['action']['value']['kind'],'argument')
            self.assertEqual(step['action']['value']['value'],{'op':'real_local','binding':0})
        for prefix in ('@(initial_step) a=2;', 'if(V(u,r)>0.5) a=2.0; else a=2.0;',
                       'a=2.0; a=3.0;'):
            with self.subTest(prefix=prefix),self.assertRaises(CompileError):
                compile_body(prefix+'@(cross(V(u,r)-0.5,1,a,a)) q=1; V(y,r)<+q;')
        with self.assertRaisesRegex(CompileError,'events under an analog conditional'):
            compile_body('if(V(u,r)>0.5) begin @(timer(1.0+1.0,2,0)) q=1; end V(y,r)<+q;')

    def test_readonly_source_local_facts_reach_initial_and_event_math(self):
        for prefix,expression in (
            ('a=2.0;','cos(a)'), ('a=1.0+1.0;','exp(a)'),
            ('a=2.0;','ln(a)'), ('a=1.0+1.0;','sqrt(a)'),
            ('a=2.0;','pow(4.0,a)'), ('a=1.0/2.0;','pow(4.0,a)')):
            for trigger in ('initial_step','timer(1)'):
                with self.subTest(prefix=prefix,expression=expression,trigger=trigger):
                    program=compile_body(prefix+'@('+trigger+') q='+expression+'; V(y,r)<+q;')
                    guards=[n for n in nodes(program['events']) if n.get('op')=='select']
                    self.assertTrue(any(n.get('left',{}).get('op')=='real_local' for n in guards))
                    self.assertEqual(program['procedures'][0]['body'][0]['action']['value']['kind'],'snapshot')
        for body in ('@(initial_step) q=cos(a); a=2.0; V(y,r)<+q;',
                     'if(V(u,r)>0.5) a=2.0; else a=2.0; @(timer(1)) q=cos(a); V(y,r)<+q;'):
            with self.subTest(body=body),self.assertRaises(CompileError):
                compile_body(body)

    def test_event_prefix_read_uses_definition_at_source_not_latest_writer(self):
        import math
        for prefix,suffix,expected in (('a=2.0;','a=3.0;',2.0),
                                       ('a=2.0; a=3.0;','',3.0),
                                       ('a=((9007199254740992.0+1.0)-9007199254740992.0)+2.0;','a=3.0;',2.0)):
            for expression,function in (('cos(a)',math.cos),('pow(4.0,a)',lambda a:4.0**a)):
                with self.subTest(prefix=prefix,expression=expression):
                    program=compile_body(prefix+'@(timer(1)) q='+expression+'; '+suffix+' V(y,r)<+q;')
                    guard=next(n for n in nodes(program['events']) if n.get('op')=='select')
                    self.assertEqual(guard['left']['op'],'real_local')
                    self.assertEqual(guard['then_value']['constant'],function(expected))

    def test_closed_math_retains_rounded_arguments_in_initial_and_event_paths(self):
        import math
        for name in ('cos','exp','ln','sqrt','tanh'):
            for trigger in ('initial_step','timer(1)'):
                if name=='tanh' and trigger=='timer(1)':
                    continue  # The original event audit does not admit tanh.
                with self.subTest(name=name, trigger=trigger):
                    program=compile_body('@('+trigger+') q='+name+'(1.0+1.0); V(y,r)<+q;')
                    guards=[n for n in nodes(program['events']) if n.get('op')=='select'
                            and n.get('left',{}).get('op')=='real_binary']
                    self.assertTrue(guards)
                    guard=guards[0]
                    self.assertEqual(guard['left']['operation'],'add')
                    expected=(math.log if name=='ln' else getattr(math,name))(2.0)
                    self.assertEqual(guard['then_value']['constant'],expected)
                    self.assertEqual(guard['then_value'],guard['else_value'])
        program=compile_body('@(initial_step) q=cos((9007199254740992.0+1.0)-9007199254740992.0); V(y,r)<+q;')
        guard=next(n for n in nodes(program['events']) if n.get('op')=='select')
        self.assertEqual(guard['left']['operation'],'subtract')
        self.assertEqual(guard['then_value']['constant'],1.0)
        with self.assertRaises(CompileError):
            compile_body('@(timer(1)) q=tanh(1.0+1.0); V(y,r)<+q;')

    def test_closed_power_exponent_keeps_source_operations(self):
        for exponent,expected in (('1.0+1.0',4.0),('1.0/2.0',2.0)):
            base='2.0' if expected==4.0 else '4.0'
            for trigger in ('initial_step','timer(1)'):
                with self.subTest(exponent=exponent,trigger=trigger):
                    program=compile_body('@('+trigger+') q=pow('+base+','+exponent+'); V(y,r)<+q;')
                    guard=next(n for n in nodes(program['events']) if n.get('op')=='select')
                    self.assertEqual(guard['left']['op'],'real_binary')
                    self.assertEqual(guard['then_value']['constant'],expected)
                    self.assertEqual(guard['then_value'],guard['else_value'])
        with self.assertRaises(CompileError):
            compile_body('@(initial_step) a=2; @(timer(1)) q=pow(2.0,a); V(y,r)<+q;')

    def test_transition_scope_sees_snapshot_and_round_wrappers(self):
        with self.assertRaisesRegex(CompileError,'transition target values must be held'):
            compile_body('a=V(y,r)+1.0; V(y,r)<+transition(a,0,1n);')
        with self.assertRaisesRegex(CompileError,'transition target values must be held'):
            compile_body('''@(initial_step) a=0; a=V(y,r)+1.0;
                @(timer(1)) a=1; V(y,r)<+transition(a,0,1n);''')
        for body in ('a=1.0+1.0; V(y,r)<+transition(a,0,1n);',
                     'a=V(u,r)+1.0; V(y,r)<+transition(a,0,1n);',
                     '@(initial_step) a=0; @(timer(1)) a=1; V(y,r)<+transition(a,0,1n);'):
            with self.subTest(body=body):
                program=compile_body(body)
                self.assertEqual(program['operators'][0]['kind'],'transition')

    def test_closed_rounded_floor_keeps_the_original_operand_tree(self):
        for phase,expected in (('0.0',0.0),('0.375',6.0),('-0.1',-2.0)):
            with self.subTest(phase=phase):
                program=compile_body('@(initial_step) q=floor(16*phase0); V(y,r)<+q;',
                                     'parameter real phase0='+phase+'; real q;')
                guards=[n for n in nodes(program['events']) if n.get('op')=='select']
                self.assertTrue(guards)
                self.assertEqual(guards[0]['left']['operation'],'multiply')
                self.assertEqual(guards[0]['then_value']['constant'],expected)
                self.assertEqual(guards[0]['else_value']['constant'],expected)
        program=compile_body('''@(initial_step)
            q=floor((9007199254740992.0+1.0)-9007199254740992.0); V(y,r)<+q;''')
        guard=next(n for n in nodes(program['events']) if n.get('op')=='select')
        self.assertEqual(guard['left']['operation'],'subtract')
        self.assertEqual(guard['then_value']['constant'],0.0)
        with self.assertRaises(CompileError):
            compile_body('@(initial_step) q=floor(16*V(u,r)); V(y,r)<+q;')

    def test_future_ordinary_writer_cannot_supply_an_occurrence_local(self):
        with self.assertRaisesRegex(CompileError,'not assigned before use'):
            compile_body('@(timer(0.5)) q=a; a=1.0; V(y,r)<+q;')
        program=compile_body('''@(initial_step) q=0; a=q; a=a+1.0;
            @(timer(0.5)) q=a; V(y,r)<+q;''')
        self.assertEqual(sum(n.get('kind')=='real_bind' for n in nodes(program['procedures'])),2)

    def test_selected_local_snapshot_keeps_pure_input_candidate_scope(self):
        for prefix,predicate in (
            ('if(V(u,r)>0.5) a=2.0; else a=2.0;', 'a*V(u,r)>0.5'),
            ('if(V(u,r)>0.5) a=2.0; else a=3.0;', 'a*V(u,r)>0.5'),
            ('a=2.0; a=V(u,r);', 'a*a>0.5')):
            with self.subTest(prefix=prefix):
                program=compile_body(prefix+'if('+predicate+') V(y,r)<+1; else V(y,r)<+0;', 'real a;')
                self.assertTrue(any(n.get('op')=='real_local' for n in nodes(program['procedures'])))

    def test_known_zero_snapshot_divisor_still_rejects_statically(self):
        for prefix in ('a=0.0;',
                       'a=(9007199254740992.0+1.0)-9007199254740992.0;',
                       'if(V(u,r)>0.5) a=0.0; else a=0.0;'):
            with self.subTest(prefix=prefix),self.assertRaisesRegex(CompileError,'division by zero'):
                compile_body(prefix+'if(V(u,r)/a>0.5) V(y,r)<+1; else V(y,r)<+0;', 'real a;')
        compile_body('a=0.0; a=2.0; if(V(u,r)/a>0.5) V(y,r)<+1; else V(y,r)<+0;', 'real a;')

    def test_constant_local_predicate_degree_does_not_inline_its_slot(self):
        for predicate in ('a*V(u,r)>0.5','V(u,r)/a>0.5',
                          'a*a>0.5','a*V(u,r)+b*V(u,r)>0.5'):
            with self.subTest(predicate=predicate):
                program=compile_body('a=2.0; b=3.0; if('+predicate+') '
                    'V(y,r)<+1; else V(y,r)<+0; a=V(u,r);', 'real a,b;')
                branch=next(n for n in nodes(program['procedures']) if n.get('kind')=='procedure_if')
                self.assertTrue(any(n.get('op')=='real_local' for n in nodes(branch['left'])))
                bindings=[n for n in nodes(program['procedures']) if n.get('kind')=='real_bind']
                self.assertEqual(len(bindings),3)
                self.assertEqual(bindings[0]['binding'],bindings[-1]['binding'])

    def test_closed_power_declaration_accepts_a_rounded_real_base(self):
        program=compile_body('@(timer(1)) q=q; V(y,r)<+q;',
                             'real q=pow(1.0+1.0,2);')
        seed=program['states'][0]['initial']
        self.assertEqual(seed['kind'],'store')
        self.assertEqual(seed['value']['op'],'power')
        self.assertEqual(seed['value']['base']['operation'],'add')

    def test_real_function_declaration_seed_keeps_boundaries(self):
        declarations='''real a=f(1.0),q;
            analog function real f; input x; real x;
              begin f=x+1.0; end
            endfunction'''
        for held in (False,True):
            with self.subTest(held=held):
                body=('@(timer(1)) begin a=a; q=a; end V(y,r)<+q;'
                      if held else 'V(y,r)<+a;')
                program=compile_body(body,declarations)
                boundaries=[n['kind'] for n in nodes(program) if n.get('op')=='real_boundary']
                self.assertIn('argument',boundaries)
                self.assertIn('return',boundaries)

    def test_integer_held_slot_does_not_become_a_current_alias(self):
        program=compile_body('''@(initial_step) q=0; V(y,r)<+q;
            if(V(u,r)>0.5) q=1;''','integer q;')
        self.assertEqual([(s['name'],s['kind']) for s in program['states']],[('q','integer')])
        kinds=[s['action']['kind'] for s in program['procedures'][0]['body']]
        self.assertLess(kinds.index('contribution_capture'),kinds.index('procedure_if'))
        self.assertEqual(len(program['events']),3)

    def test_declaration_seed_retains_source_real_operations(self):
        program=compile_body('''@(timer(1)) begin a=a; q=a; end V(y,r)<+q;''',
                             'real a=(9007199254740992.0+1.0)-9007199254740992.0,q;')
        seed=next(s['initial'] for s in program['states'] if s['name']=='a')
        self.assertEqual(seed['kind'],'store')
        self.assertEqual(seed['value']['operation'],'subtract')
        self.assertEqual(seed['value']['left']['operation'],'add')

    def test_ordinary_held_slot_uses_original_process_and_wakeup_gates(self):
        program=compile_body('''if(V(u,r)>0.5) q=1;
            V(y,r)<+q;''','real q;')
        self.assertEqual([s['name'] for s in program['states']],['q'])
        self.assertFalse(any(s['name'].endswith('$held') for s in program['states']))
        self.assertEqual(len([n for n in nodes(program['procedures'])
                              if n.get('kind')=='procedure_if']),1)
        self.assertEqual(len(program['events']),2)
        # A wakeup may restore the certified pre-side held value before the
        # original process runs. Its body length is not a transport contract;
        # numeric pulse/rounded-cell controls live in test_ordinary_held_state.
        gates=[n['event'] for n in nodes(program['procedures']) if n.get('kind')=='event_gate']
        self.assertEqual(sorted(gates),list(range(len(program['events']))))

    def test_step_bound_capture_stays_inside_the_selected_branch(self):
        program=compile_body('''@(initial_step) a=1;
            if(a>0) begin a=-1; $bound_step(a+2.0); end
            V(y,r)<+a;''')
        branch=next(n for n in nodes(program['procedures']) if n.get('kind')=='procedure_if')
        self.assertEqual([s['action']['kind'] for s in branch['then_body']],
                         ['assign','step_bound_capture'])
        bound=program['step_bounds'][branch['then_body'][1]['action']['step_bound']]
        self.assertEqual(bound['active']['constant'],1.0)
        self.assertEqual(bound['value']['kind'],'argument')

    def test_ordinary_conditional_binds_only_its_selected_source_arm(self):
        program=compile_body('''@(initial_step) a=1;
            if(a>0) snap=a; else snap=2;
            @(timer(1)) q=snap; V(y,r)<+q;''','real a,q,snap;')
        branch=next(n for n in nodes(program['procedures']) if n.get('kind')=='procedure_if')
        yes=branch['then_body'][0]['action']
        no=branch['else_body'][0]['action']
        self.assertEqual(yes['kind'],'real_bind')
        self.assertEqual(yes['binding'],no['binding'])
        event=next(e for e in program['events'] if e['trigger']['kind']=='timer')
        self.assertEqual(event['body'][0]['rhs']['value']['op'],'real_local')

    def test_mutated_branch_predicate_is_not_rechecked_at_contribution(self):
        program=compile_body('''@(initial_step) a=1;
            if(a>0) begin a=-1; V(y,r)<+a; end else V(y,r)<+0;
            @(timer(1)) q=a;''')
        branch=next(n for n in nodes(program['procedures']) if n.get('kind')=='procedure_if')
        self.assertEqual([s['action']['kind'] for s in branch['then_body']],
                         ['assign','contribution_capture'])
        capture=branch['then_body'][1]['action']['contribution']
        self.assertFalse(any(n.get('op')=='select' for n in nodes(program['contributions'][capture])))

    def test_runtime_division_is_not_replaced_by_reciprocal(self):
        program=compile_body('@(initial_step) begin a=3.0; q=0; end '
                             '@(timer(0.5)) q=(a/10.0)-0.3; V(y,r)<+q;')
        divisions=[n for n in nodes(program) if n.get('op')=='real_binary' and n['operation']=='divide']
        self.assertTrue(divisions,'the source divide must remain a rounded divide operation')
        self.assertEqual(divisions[0]['left']['op'],'state')

    def test_constant_arithmetic_keeps_each_source_rounding(self):
        program=compile_body('@(initial_step) q=(9007199254740992.0+1.0)-9007199254740992.0; V(y,r)<+q;')
        operations=[n['operation'] for n in nodes(program) if n.get('op')=='real_binary']
        self.assertIn('add',operations)
        self.assertIn('subtract',operations)

    def test_snapshot_is_an_executable_binding_between_event_gates(self):
        program=compile_body('@(initial_step) a=1; snap=0; '
            '@(timer(1)) a=a+1; snap=a; '
            '@(cross(V(u,r)-0.5,1)) begin q=10*snap+a; $display("q=%g",q); end '
            'V(y,r)<+q;','real a,q,snap;')
        self.assertEqual(len(program['procedures']),1)
        body=program['procedures'][0]['body']
        kinds=[step['action']['kind'] for step in body]
        self.assertIn('real_bind',kinds)
        self.assertEqual(kinds.count('event_gate'),3)
        self.assertIn('contribution_capture',kinds)
        ordinals=[step['expanded_statement_ordinal'] for step in body]
        self.assertEqual(ordinals,sorted(set(ordinals)))
        gates=[s['action']['event'] for s in body if s['action']['kind']=='event_gate']
        self.assertEqual(len(gates),len(set(gates)))

    def test_real_function_boundaries_survive_in_a_continuous_contribution(self):
        program=compile_body('''@(initial_step) a=9007199254740992.0;
            V(y,r)<+f(a);''','''real a,q;
            analog function real f;
              input x; real x;
              begin f=(x+1.0)-x; end
            endfunction''')
        boundaries=[n['kind'] for n in nodes(program) if n.get('op')=='real_boundary']
        self.assertIn('argument',boundaries)
        self.assertIn('return',boundaries)
        self.assertTrue(any(n.get('op')=='real_binary' and n['operation']=='subtract' for n in nodes(program)))

    def test_real_array_element_writes_retain_store_and_operation_boundaries(self):
        program=compile_body('''@(initial_step) begin i=0; values[0]=9007199254740992.0; values[1]=0; end
            @(timer(0.5)) values[i]=(values[i]+1.0)-values[i];
            V(y,r)<+values[0];''','real values[0:1]; integer i;')
        operations=[n['operation'] for n in nodes(program) if n.get('op')=='real_binary']
        self.assertIn('add',operations)
        self.assertIn('subtract',operations)
        self.assertTrue(any(n.get('op')=='real_boundary' and n['kind']=='store' for n in nodes(program)))

    def test_or_gate_owns_one_event_body(self):
        program=compile_body('''@(initial_step) q=0;
            @(timer(1) or cross(V(u,r)-0.5,1)) q=q+1.0; V(y,r)<+q;''')
        or_events=[(i,e) for i,e in enumerate(program['events']) if e['trigger']['kind']=='or']
        self.assertEqual(len(or_events),1)
        index,event=or_events[0]
        self.assertEqual(len(event['body']),1)
        gates=[n for n in nodes(program['procedures']) if n.get('kind')=='event_gate' and n['event']==index]
        self.assertEqual(len(gates),1)

    def test_mixed_initial_cross_has_one_body_and_declaration_seed(self):
        program=compile_body('''@(initial_step or cross(V(u,r)-0.5,1)) q=q+1.0;
            V(y,r)<+q;''')
        self.assertEqual(len(program['events']),1)
        leaves=program['events'][0]['trigger']['triggers']
        self.assertEqual([leaf['kind'] for leaf in leaves],['initial_step','cross'])
        self.assertEqual(program['states'][0]['initial'],0.)
        self.assertEqual(len(program['events'][0]['body']),1)

    def test_shared_source_does_not_merge_instance_procedures_or_bindings(self):
        source='''`include "disciplines.vams"
            module m(u,y,r); input u; output y; inout r; electrical u,y,r;
            real a,snap;
            analog begin @(initial_step) a=2; snap=a;
              @(timer(1)) a=snap+1.0; V(y,r)<+a; end endmodule'''
        instances=[Instance(n,'m',dict(u='u',y=n,r='0'),{}) for n in ['first','second']]
        program=compile_sources({'shared.va':source},instances).to_dict()
        self.assertEqual([p['instance'] for p in program['procedures']],['first','second'])
        self.assertEqual([p['procedure_id'] for p in program['procedures']],[0,1])
        self.assertEqual([b['procedure_id'] for b in program['real_bindings']],[0,1])

    def test_static_loop_event_order_uses_the_expanded_sequence(self):
        program=compile_body('''@(initial_step) q=0;
            for(k=0;k<2;k=k+1) begin @(timer(1)) q=q+(k+1.0); end
            V(y,r)<+q;''','real q; genvar k;')
        gates=[s for s in program['procedures'][0]['body'] if s['action']['kind']=='event_gate']
        self.assertEqual(len(gates),3)
        self.assertEqual([s['expanded_statement_ordinal'] for s in gates],list(range(3)))
        runtime=[e for e in program['events'] if e['trigger']['kind']=='timer']
        self.assertEqual([e['origin']['expansion'][-1][1] for e in runtime],[0,1])


if __name__=='__main__':
    unittest.main()

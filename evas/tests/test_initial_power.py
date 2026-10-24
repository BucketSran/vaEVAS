"""Closed general power belongs to the unique initial execution, not preview."""
GUARDS = ['LANG']
import unittest
from evas import compile_sources, Instance, CompileError

def program(body, declarations='real a,b;', parameters=''):
    source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'
            +parameters+declarations+'analog begin '+body+'V(y)<+a+b;end endmodule')
    return compile_sources({'power.va':source},[Instance('dut','m',dict(u='u',y='y'))])

def nodes(value):
    if isinstance(value,dict):
        yield value
        for child in value.values():yield from nodes(child)
    elif isinstance(value,(tuple,list)):
        for child in value:yield from nodes(child)

class InitialPower(unittest.TestCase):
    def test_multiple_assignments_have_no_preview_operators_or_orphan_slots(self):
        p=program('@(initial_step)begin a=pow(10.0,0.025);b=pow(10.0,-0.05);end ')
        w=p.to_dict()
        self.assertEqual([o['function'] for o in w['operators']],['ln','exp','ln','exp'])
        self.assertEqual(len(w['events']),1)
        self.assertFalse(w['real_bindings'])
        self.assertEqual([s['initial'] for s in w['states']],[0.0,0.0])
        self.assertEqual(sum(n.get('kind')=='event_gate' for n in nodes(w['procedures'])),1)
        self.assertEqual(len(w['events'][0]['body']),2)

    def test_operands_keep_per_source_RN_and_copy_boundaries(self):
        p=program('@(initial_step)begin a=pow(10.0,(9007199254740992.0+1.0)-9007199254740992.0);b=0;end ')
        w=p.to_dict()
        self.assertFalse(w['operators']) # RN exponent is exactly zero.
        self.assertTrue(any(n.get('operation')=='add' for n in nodes(w['events'])))
        self.assertTrue(any(n.get('operation')=='subtract' for n in nodes(w['events'])))
        self.assertTrue(any(n.get('kind')=='argument' for n in nodes(w['events'])))
        self.assertEqual(w['states'][0]['initial'],0.0)

    def test_repeated_state_writes_keep_distinct_source_call_origins(self):
        w=program('@(initial_step)begin a=pow(10.0,0.025);a=pow(10.0,0.05);b=a;end ').to_dict()
        self.assertEqual(len(w['operators']),4)
        self.assertNotEqual(w['operators'][0]['origin'],w['operators'][2]['origin'])
        self.assertEqual(len(w['events'][0]['body']),3)

    def test_unknown_inputs_and_seed_are_not_closed_operands(self):
        for body in ('@(initial_step)begin a=pow(10.0,V(u));b=0;end ',
                     '@(timer(1))begin a=pow(10.0,b);end ',
                     '@(initial_step)begin a=pow(10.0,(V(u)>0.5)?0.025:0.025);b=0;end '):
            with self.subTest(body=body),self.assertRaises(CompileError):program(body)

    def test_nonpositive_base_and_noninitial_general_power_keep_refusal(self):
        for body in ('@(initial_step)begin a=pow(-1.0,0.25);b=0;end ',
                     '@(timer(1))begin a=pow(10.0,0.25);b=0;end '):
            with self.subTest(body=body),self.assertRaises(CompileError):program(body)

    def test_fresh_request_and_same_owner_wire_exhaustion(self):
        text='@(initial_step)begin a=pow(10.0,0.025);b=0;end '
        p=program(text);owner=p._native_audit
        self.assertTrue(owner.active);p.to_dict()
        for _ in range(1000):
            try:p.to_dict()
            except CompileError:break
        else:self.fail('original cap not enforced')
        for _ in range(2):
            before=owner.used
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(owner.used,before)
        fresh=program(text);self.assertIsNot(fresh._native_audit,owner);fresh.to_dict()


class InitialPowerCallScope(unittest.TestCase):
    def build(self, function='f=pow(a,b);', body=None, wire=False):
        source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;real q;'
            'analog function real f;input a,b;real a,b;begin '+function+'end endfunction '
            'analog begin @(initial_step)begin '+(body or 'q=f(1.0000000000000002,0.5000000000000001);')+
            'end V(y)<+q;end endmodule')
        p=compile_sources({'call-power.va':source},[Instance('dut','m',dict(u='u',y='y'))])
        return p.to_dict() if wire else p

    def test_transitive_memoryless_inputs_keep_actual_function_scope(self):
        for function in ('f=pow(a,b);','f=pow(10.0,0.025);','f=exp(ln(a));'):
            with self.subTest(function=function):
                p=self.build(function);w=p.to_dict()
                self.assertEqual([o['function'] for o in w['operators']],['ln','exp'])
                self.assertEqual(len(w['real_bindings']),3)
                self.assertEqual(sum(n.get('op')=='real_call' for n in nodes(w['events'])),1)
                self.assertGreater(p._native_audit.counts['program_real_operator_use_record'],0)
        w=self.build('f=pow(10.0,0.025);',body='q=f(1.0,(V(u)>0.0)?1.0/0.0:0.0);',wire=True)
        call=next(n for n in nodes(w['events']) if n.get('op')=='real_call')
        self.assertTrue(any(n.get('operation')=='divide' for n in nodes(call['body'][:2])))

    def test_scope_propagation_does_not_allow_external_or_other_call_uses(self):
        from dataclasses import replace
        from evas.ir import OperatorRef, Binary
        p=self.build(body='q=f(1.0000000000000002,0.5000000000000001);q=f(10.0,0.025);')
        p.to_dict()
        with self.assertRaisesRegex(CompileError,'external|escapes|shared'):
            replace(p,operators=(replace(p.operators[0],input=p.operators[2].input),*p.operators[1:])).to_dict()
        contribution=p.contributions[0]
        for rhs in (OperatorRef(0),Binary('add',OperatorRef(0),OperatorRef(2))):
            with self.subTest(rhs=rhs),self.assertRaisesRegex(CompileError,'escapes'):
                replace(p,contributions=(replace(contribution,rhs=rhs),)).to_dict()

    def test_transitive_scope_checks_use_same_owner_and_sticky_cap(self):
        p=self.build();owner=p._native_audit;p.to_dict()
        self.assertGreater(owner.counts['program_real_operator_use_check'],0)
        for _ in range(1000):
            try:p.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('same owner did not exhaust original100000 cap')
        used=owner.used
        for _ in range(2):
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(owner.used,used)
        self.assertTrue(self.build(wire=True))

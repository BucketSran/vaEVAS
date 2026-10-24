"""Paid compatibility DAG reuse and source-ordered actual function calls."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import unittest
from dataclasses import fields,is_dataclass
from evas import compile_sources,Instance,CompileError
from evas.ir import RealCall,RealBinary,RealLocal,RealBoundary


def source(functions,expr):
    return '`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'+functions+'analog begin V(y)<+'+expr+';end endmodule'


def compile(functions,expr):
    return compile_sources({'dag.va':source(functions,expr)},[Instance('M','m',dict(u='u',y='y'))])


def nodes(root):
    pending=[root];seen=set()
    while pending:
        item=pending.pop()
        if id(item) in seen:continue
        seen.add(id(item));yield item
        if is_dataclass(item):pending.extend(getattr(item,f.name) for f in fields(item))
        elif isinstance(item,(tuple,list)):pending.extend(item)


class FunctionCompatibilityDAG(unittest.TestCase):
    twice='analog function real twice;input x;real x;begin twice=x+x;end endfunction '
    discard='analog function real discard;input x;real x,tmp;begin tmp=x+x;discard=1;end endfunction '

    def test_fourteen_layer_siblings_keep_linear_call_ownership_and_full_wire(self):
        value='V(u)'
        for _ in range(14):value='twice('+value+')'
        p=compile(self.twice,'('+value+'+'+value+')');wire=p.to_dict()
        calls=[n for n in nodes(p) if isinstance(n,RealCall)]
        self.assertEqual(len(calls),28)
        bindings=[b for c in calls for b in c.bindings]
        self.assertEqual(len(bindings),len(set(bindings)))
        for call in calls:
            actual=call.body[0].action
            self.assertIsInstance(actual.value,RealBoundary)
            self.assertEqual(actual.value.kind,'argument')
            operation=call.body[-1].action.value.value
            self.assertIsInstance(operation,RealBinary)
            self.assertEqual(operation.operation,'add')
            self.assertIsInstance(operation.left,RealLocal)
            self.assertEqual(operation.left.binding,operation.right.binding)
        self.assertLess(p._native_audit.used,100000)
        self.assertTrue(wire['procedures'])

    def test_discarded_and_overwritten_effects_remain_in_actual_call(self):
        function='analog function real f;input x;real x,tmp;begin tmp=1/(x-x);tmp=1;f=1;end endfunction '
        p=compile(function,'f(V(u))');p.to_dict();calls=[n for n in nodes(p) if isinstance(n,RealCall)]
        self.assertEqual(len(calls),1);self.assertEqual(len(calls[0].body),4)
        self.assertTrue(any(isinstance(n,RealBinary) and n.operation=='divide' for n in nodes(calls[0].body[1])))
        p=compile(self.discard,'discard(1/(V(u)-V(u)))');p.to_dict()
        calls=[n for n in nodes(p) if isinstance(n,RealCall)]
        self.assertTrue(any(isinstance(n,RealBinary) and n.operation=='divide' or getattr(n,'op',None)=='divide' for n in nodes(calls[0].body[0])))

    def test_all_source_obligations_remain_qualified_and_original_budget_is_finite(self):
        for expr in ('discard(unknown)','discard(idt(V(u),0))'):
            with self.subTest(expr=expr),self.assertRaises(CompileError):compile(self.discard,expr)
        function='analog function real f;input x;real x,tmp;begin if(x>0)tmp=missing(x);else tmp=1;f=1;end endfunction '
        with self.assertRaises(CompileError):compile(function,'f(0)')
        value='V(u)'
        for _ in range(15):value='twice('+value+')'
        for _ in range(2):
            with self.assertRaises(CompileError) as raised:compile(self.twice,value)
            self.assertEqual(raised.exception.diagnostic['code'],'resource_budget')

    def test_actual_real_arguments_keep_each_source_round_for_identity_and_call(self):
        identity='analog function real ident;input x;real x;begin ident=x;end endfunction '
        for function,name in ((identity,'ident'),(self.twice,'twice')):
            p=compile(function,name+'((V(u)+1.0)-V(u))');p.to_dict()
            operations=[n.operation for n in nodes(p.contributions) if isinstance(n,RealBinary)]
            self.assertIn('add',operations);self.assertIn('subtract',operations)
            self.assertFalse(any(getattr(n,'op',None)=='add' for n in nodes(p.contributions)))

    def test_physical_caller_keeps_its_own_arithmetic_role(self):
        identity='analog function real ident;input x;real x;begin ident=x;end endfunction '
        p=compile(identity,'ident((V(u)+1.0)-V(u))+V(u)');p.to_dict()
        self.assertTrue(any(getattr(n,'op',None)=='add' for n in nodes(p.contributions)))
        self.assertEqual(sum(isinstance(n,RealBinary) for n in nodes(p.contributions)),2)

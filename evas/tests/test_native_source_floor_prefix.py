"""Native source-floor prefix stores retain RN and original procedure order."""
GUARDS = ['LANG','EVENT-ORDER','EVENT-CONDITIONS','COMPOSE']
import hashlib
import unittest
from dataclasses import fields,is_dataclass
from pathlib import Path
from evas import CompileError,Instance,compile_sources
from evas.ir import Assignment,EventMath,RealBinary,RealBoundary,ProcedureConditional,EventGate
import test_ordinary_integer_event_prefix
from test_ordinary_integer_event_prefix import build,text


def walk(root):
    pending=[root];seen=set()
    while pending:
        item=pending.pop()
        if id(item) in seen:continue
        seen.add(id(item));yield item
        if is_dataclass(item):pending.extend(getattr(item,f.name) for f in fields(item))
        elif isinstance(item,(tuple,list)):pending.extend(item)


class NativeSourceFloorPrefix(unittest.TestCase):
    def test_original_joint_has_one_source_floor_store_before_three_timer_gates(self):
        fixtures=Path(test_ordinary_integer_event_prefix.__file__).resolve().parents[1]/'rust_core/tests/fixtures'
        source=(fixtures/'ordinary_integer_prefix_joint.va').read_text()
        self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),'90661323d08a953b0190224bd5bfa2a5504756930d5fd35b8738a5d2db1c06fe')
        p=compile_sources({'ordinary_integer_prefix_joint.va':source},[Instance('M','joint',dict(u='u',y='y',h='h'))]);p.to_dict()
        ratio=next(i for i,s in enumerate(p.states) if s.name=='ratio')
        steps=p.procedures[0].body
        self.assertIsInstance(steps[0].action,EventGate)
        store=steps[1].action;self.assertIsInstance(store,Assignment);self.assertEqual(store.state,ratio)
        self.assertIsInstance(store.rhs,EventMath);self.assertEqual(store.rhs.function,'floor')
        tree=store.rhs.args[0];self.assertIsInstance(tree,RealBinary);self.assertEqual(tree.operation,'add')
        self.assertEqual(tree.left.operation,'multiply');self.assertEqual(tree.left.left.operation,'divide')
        self.assertIsInstance(tree.left.left.left,RealBoundary)
        self.assertEqual(tree.left.left.left.kind,'sample')
        self.assertIsInstance(steps[2].action,ProcedureConditional)
        self.assertEqual(sum(isinstance(n,EventMath) and n.function=='floor' for n in walk(p.procedures)),1)
        self.assertFalse(any(isinstance(n,EventMath) and n.function=='floor' for n in walk(p.events)))
        self.assertEqual(sum(isinstance(n,Assignment) and n.state==ratio for n in walk(p.events)),0)
        self.assertLess(p._native_audit.used,100000)

    def test_qualified_store_keeps_clamps_and_full_source_qualification(self):
        p=build(text('ratio=$floor((V(u)/0.9)*15+0.5);if(ratio<1)ratio=1;if(ratio>7)ratio=7;'));p.to_dict()
        self.assertEqual(sum(isinstance(n,ProcedureConditional) for n in walk(p.procedures)),2)
        for prefix in ('ratio=$floor(q+V(u));','ratio=$floor(0*V(y)+V(u));','ratio=$floor($abstime+V(u));','ratio=$floor(V(u)/0);','ratio=$floor(V(u)+.5);if(ratio<1)ratio=missing;'):
            with self.subTest(prefix=prefix),self.assertRaises(CompileError):build(text(prefix))
        with self.assertRaises(CompileError):build(text(extra='V(y)<+0.0*ratio;'))
        with self.assertRaises(CompileError):build(text(prefix='',event='@(timer(.25))q=ratio;ratio=$floor(V(u)+.5);'))

    def test_actual_owner_wire_budget_is_sticky_and_fresh_source_still_works(self):
        p=build();p.to_dict();owner=p._native_audit;self.assertTrue(owner.active)
        while True:
            try:p.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        for _ in range(2):
            before=owner.used
            with self.assertRaises(CompileError):p.to_dict()
            self.assertGreater(owner.used,before)
        self.assertIsInstance(build().to_dict(),dict)

    def test_constant_denominator_certificate_uses_actual_per_operation_rounding(self):
        from test_source_floor_event import program
        p=program('d=3.0/10.0;q=floor(V(u,r)/d);', 'real d;integer q;', 'd=3.0/10.0;q=0;')
        p.to_dict()
        floors=[n for n in walk(p.events) if isinstance(n,EventMath) and n.function=='floor']
        self.assertEqual(len(floors),1)
        denominator=floors[0].args[0].right
        self.assertEqual(denominator.constant.hex(),(3.0/10.0).hex())
        self.assertNotEqual(denominator.constant.hex(),(3.0*(1.0/10.0)).hex())
        with self.assertRaises(CompileError):
            program('d=V(u,r);q=floor(V(u,r)/d);','real d;integer q;','d=3.0/10.0;q=0;')

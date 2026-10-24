"""Exact IR identity shares structures, never runtime values or contexts."""
GUARDS = ['LANG', 'COMPOSE']
from dataclasses import dataclass
import unittest
from evas import CompileError
from evas.ir import (Affine,Origin,MathFunction,RealBoundary,RealBinary,RealLocal,StateRef,Select)
from evas.memoryless_operators import Registry
from evas.native_audit import NativeAudit


class MemorylessIdentity(unittest.TestCase):
    def test_immutable_fields_read_once_on_postorder_and_not_on_cached_reuse(self):
        reads=[]
        @dataclass(frozen=True)
        class Node:
            left:object
            right:object
            def __getattribute__(self,name):
                if name in ('left','right'):reads.append(name)
                return object.__getattribute__(self,name)
        node=Node((1,2),(3,4));owner=NativeAudit();registry=Registry(owner)
        identity=registry.identity(node)
        self.assertEqual(reads,['left','right'])
        before=owner.used
        self.assertEqual(registry.identity(node),identity)
        self.assertEqual(reads,['left','right'])
        self.assertGreater(owner.used,before)
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_exact_structure_keeps_call_origin_and_instance_identity(self):
        owner=NativeAudit();registry=Registry(owner);operators=[]
        def spec(instance='dut',call=1):
            origin=Origin('helper.va',4,7,instance,(('function_call',call),))
            return MathFunction('exp',RealBinary('add',StateRef(0),Affine(1.,()),origin),origin)
        self.assertEqual(registry.register(spec(),operators),0)
        self.assertEqual(registry.register(spec(),operators),0)
        self.assertEqual(registry.register(spec(call=2),operators),1)
        self.assertEqual(registry.register(spec(instance='other'),operators),2)
        self.assertEqual(len(operators),3)
        self.assertIsNot(operators[0],operators[1])

    def test_zero_sign_boundaries_state_and_local_refs_never_merge(self):
        owner=NativeAudit();registry=Registry(owner)
        origin=Origin('helper.va',2,3,'dut')
        def identity(value):return registry.identity(MathFunction('cos',value,origin))
        self.assertNotEqual(identity(Affine(0.,())),identity(Affine(-0.,())))
        self.assertNotEqual(identity(StateRef(0)),identity(StateRef(1)))
        self.assertNotEqual(identity(RealLocal(0)),identity(RealLocal(1)))
        self.assertNotEqual(identity(RealLocal(0)),identity(StateRef(0)))
        self.assertNotEqual(identity(RealBoundary(StateRef(0),'store',origin)),
                            identity(RealBoundary(StateRef(0),'argument',origin)))
        self.assertNotEqual(identity(RealBinary('divide',StateRef(0),Affine(10.,()),origin)),
                            identity(RealBinary('multiply',StateRef(0),Affine(.1,()),origin)))

    def test_guard_order_and_arms_remain_exact(self):
        registry=Registry(NativeAudit());o=Origin('m.va',1,1,'dut')
        def guarded(relation,yes,no):return Select(relation,StateRef(0),Affine(0.,()),yes,no,o)
        a,b=Affine(1.,()),Affine(2.,())
        self.assertNotEqual(registry.identity(guarded('lt',a,b)),registry.identity(guarded('le',a,b)))
        self.assertNotEqual(registry.identity(guarded('lt',a,b)),registry.identity(guarded('lt',b,a)))

    def test_mutable_descendant_is_rejected_without_parent_identity(self):
        @dataclass(frozen=True)
        class Wrapper:
            child:object
        owner=NativeAudit();registry=Registry(owner);value=Wrapper([])
        with self.assertRaises(TypeError):registry.identity(value)
        self.assertNotIn(id(value),registry.identities)
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_actual_identity_work_exhausts_same_owner_and_fresh_request_recovers(self):
        owner=NativeAudit();owner.activate(None);registry=Registry(owner)
        with self.assertRaises(CompileError) as got:
            for i in range(5000):
                registry.identity((Origin('model.va',i+1,1,'dut',(('function_call',i),)),i))
        self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
        self.assertGreater(owner.used,100000)
        count=len(registry.identities)
        for _ in range(2):
            before=owner.used
            with self.assertRaises(CompileError):registry.identity((1,2))
            self.assertGreater(owner.used,before)
            self.assertEqual(len(registry.identities),count)
        fresh=NativeAudit();fresh.activate(None)
        self.assertGreater(Registry(fresh).identity((1,2)),0)
        self.assertLess(fresh.used,100000)


if __name__=='__main__':unittest.main()

"""Only negative immutable syntax relevance crosses qualification instances."""
GUARDS = ['LANG', 'COMPOSE']
import unittest
from copy import deepcopy
from evas import compile_sources, Instance, CompileError
from evas.frontend import parse_sources
from evas.native_audit import NativeAudit
from evas.unreachable_system_calls import qualify
from evas.syntax import Expr, Assignment

SOURCE='''`include "disciplines.vams"
module m(u,y);input u;output y;electrical u,y;parameter real gate=0;real q;
analog begin
q=V(u)+1.0;
if(gate>0) q=$anything(1);else q=2;
V(y)<+q;
end endmodule'''

class SharedSourceRelevance(unittest.TestCase):
    def parsed(self):return parse_sources({'source.va':SOURCE})['m']
    def warm(self,model,owner):
        for name in ('a','b','c'):qualify(model,{'gate':0.},name,owner)

    def test_model_revisit_shares_only_negative_certified_nodes(self):
        model=self.parsed();original=repr(model);owner=NativeAudit()
        qualify(model,{'gate':0.},'a',owner)
        self.assertFalse(hasattr(owner,'dead_call_immutable_irrelevance'))
        qualify(model,{'gate':0.},'b',owner)
        table=owner.dead_call_immutable_irrelevance
        self.assertTrue(table)
        self.assertFalse(any(isinstance(v[0],(dict,list)) or v[0] is model for v in table.values()))
        self.assertTrue(all(v[1] is False and id(v[0])==key for key,v in table.items()))
        before=owner.used;qualify(model,{'gate':0.},'c',owner);self.assertGreater(owner.used,before)
        with self.assertRaises(CompileError) as caught:qualify(model,{'gate':1.},'d',owner)
        self.assertEqual(caught.exception.diagnostic['code'],'unsupported_system_function')
        self.assertEqual(repr(model),original)
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_mutable_expr_descendant_cannot_make_parent_shared(self):
        model=self.parsed();token=model.analog[0].token
        children=[Expr('number',1.,(),token)]
        root=Expr('checked',None,children,token)
        added=Assignment('q',root,token);model.analog.append(added)
        model.procedure=(*model.procedure,added)
        owner=NativeAudit();self.warm(model,owner)
        self.assertNotIn(id(root),owner.dead_call_immutable_irrelevance)
        self.assertNotIn(id(added),owner.dead_call_immutable_irrelevance)
        children.append(Expr('unsupported_system_call','anything',(),token))
        with self.assertRaises(CompileError):qualify(model,{'gate':0.},'d',owner)

    def test_mutable_model_and_statement_containers_are_revisited(self):
        model=self.parsed();owner=NativeAudit();self.warm(model,owner)
        token=model.analog[0].token
        model.analog.append(Assignment('q',Expr('unsupported_system_call','anything',(),token),token))
        with self.assertRaises(CompileError):qualify(model,{'gate':0.},'d',owner)

    def test_dead_argument_static_obligations_remain_per_scope(self):
        for poison in ('1.0&1','unknown','V(missing)','missing(1)'):
            model=parse_sources({'source.va':SOURCE.replace('$anything(1)','$anything('+poison+')')})['m']
            owner=NativeAudit()
            for name in ('a','b','c'):
                with self.assertRaises(CompileError):qualify(model,{'gate':0.},name,owner)

    def test_seed_role_is_rechecked_after_mutable_declaration_change(self):
        source=SOURCE.replace('real q;', 'real q;integer seed;').replace('$anything(1)', '$rdist_normal(seed,0,0)')
        model=parse_sources({'source.va':source})['m'];owner=NativeAudit()
        self.warm(model,owner)
        model.variables['seed']='real'
        with self.assertRaises(CompileError) as caught:
            qualify(model,{'gate':0.},'changed',owner)
        self.assertEqual(caught.exception.diagnostic['code'],'unsupported_system_function')

    def test_resource_failure_is_sticky_even_with_warm_shared_facts(self):
        model=self.parsed();owner=NativeAudit();self.warm(model,owner)
        with self.assertRaises(CompileError):owner.debit('actual_work',100000)
        for _ in range(2):
            with self.assertRaises(CompileError) as caught:qualify(model,{'gate':0.},'d',owner)
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
        fresh=NativeAudit();qualify(model,{'gate':0.},'fresh',fresh)
        self.assertFalse(hasattr(fresh,'dead_call_immutable_irrelevance'))

    def test_shared_index_allocation_and_insert_are_prepaid(self):
        from unittest.mock import patch
        for target in ('dead_call_source_models_container', 'dead_call_shared_context_container', 'dead_call_shared_insert'):
            model=self.parsed();owner=NativeAudit()
            if target!='dead_call_source_models_container':qualify(model,{'gate':0.},'first',owner)
            old=owner.debit;length=[]
            def debit(kind, amount=1, item=None, **kwargs):
                if kind==target:
                    table=getattr(owner,'dead_call_immutable_irrelevance',{})
                    length.append(len(table))
                    old('actual_other_work',100000,item)
                return old(kind,amount,item,**kwargs)
            with patch.object(owner,'debit',debit):
                with self.assertRaises(CompileError):qualify(model,{'gate':0.},'failed',owner)
            self.assertTrue(length)
            if target=='dead_call_source_models_container':self.assertFalse(hasattr(owner,'dead_call_source_models'))
            elif target=='dead_call_shared_context_container':self.assertFalse(hasattr(owner,'dead_call_immutable_irrelevance'))
            else:self.assertEqual(len(owner.dead_call_immutable_irrelevance),length[0])

    def test_public_instance_parameters_cannot_reuse_dead_verdict(self):
        instances=[Instance(n,'m',dict(u='u',y=n),{'gate':0.}) for n in ('a','b','c')]
        p=compile_sources({'source.va':SOURCE},instances);p.to_dict()
        with self.assertRaises(CompileError):
            compile_sources({'source.va':SOURCE},instances+[Instance('d','m',dict(u='u',y='d'),{'gate':1.})])

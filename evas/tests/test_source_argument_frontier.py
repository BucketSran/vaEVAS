"""Expression arguments need a tuple record only at a real rewrite frontier."""
GUARDS = ['LANG', 'COMPOSE']
from dataclasses import replace
from unittest.mock import patch
import unittest
from evas import CompileError
from evas.frontend import parse_sources
from evas.native_audit import NativeAudit
from evas.syntax import Expr, Token, Assignment, Conditional
from evas.unreachable_system_calls import qualify

SOURCE = """`include "disciplines.vams"
module m(u,y);input u;output y;electrical u,y;parameter real gate=0;real q;
analog begin q=1;V(y)<+q;end endmodule"""


class SourceArgumentFrontier(unittest.TestCase):
    def model(self):return parse_sources({'frontier.va':SOURCE})['m']
    def number(self, token, value):return Expr('number',value,(),token)
    def attach(self, model, statement):
        model.analog.append(statement)
        model.procedure=(*model.procedure,statement)
    def conditional(self, token, body):
        return Conditional('>',Expr('parameter','gate',(),token),self.number(token,0.),tuple(body),(),token)

    def test_exact_tuple_shared_by_expressions_and_call_walk(self):
        model=self.model();token=model.declaration_token
        shared=(self.number(token,1.),self.number(token,2.))
        left=Expr('+',None,shared,token,source_call=('left',1,2))
        right=Expr('-',None,shared,token,expansion=(('i',-1),))
        call=Expr('unsupported_system_call','anything',shared,token)
        self.attach(model,self.conditional(token,[Assignment('q',x,token)for x in (left,right,call)]))
        original=repr(model);owner=NativeAudit()
        for name in ('a','b','c'):
            result=qualify(model,{'gate':0.},name,owner)
            body=result.analog[-1].then_body
            self.assertIs(body[0].rhs,left);self.assertIs(body[1].rhs,right)
            self.assertIs(body[0].rhs.args,shared);self.assertIs(body[1].rhs.args,shared)
            self.assertEqual(body[2].rhs.op,'number')
        self.assertEqual(repr(model),original)
        self.assertEqual(owner.used,sum(owner.counts.values()))
        with self.assertRaises(CompileError):qualify(model,{'gate':1.},'live',owner)

    def test_negative_expression_fact_does_not_typecheck_opaque_children(self):
        model=self.model();token=model.declaration_token
        shared=(Expr('parameter','missing',(),token),self.number(token,1.))
        root=Expr('+',None,shared,token)
        self.attach(model,Assignment('q',root,token))
        owner=NativeAudit()
        for name in ('a','b','c'):qualify(model,{'gate':0.},name,owner)
        self.assertIn(id(root),owner.dead_call_immutable_irrelevance)
        call=Expr('unsupported_system_call','anything',shared,token)
        self.attach(model,self.conditional(token,[Assignment('q',call,token)]))
        with self.assertRaisesRegex(CompileError,'unknown parameter'):
            qualify(model,{'gate':0.},'dead-but-illtyped',owner)

    def test_mutable_arguments_are_not_certified_as_immutable(self):
        model=self.model();token=model.declaration_token
        children=[self.number(token,1.)]
        root=Expr('checked',None,children,token)
        self.attach(model,Assignment('q',root,token));owner=NativeAudit()
        for name in ('a','b','c'):qualify(model,{'gate':0.},name,owner)
        self.assertNotIn(id(root),owner.dead_call_immutable_irrelevance)
        children.append(Expr('unsupported_system_call','anything',(),token))
        with self.assertRaises(CompileError):qualify(model,{'gate':0.},'changed',owner)

    def test_mutable_metadata_is_preserved_and_never_a_source_child(self):
        model=self.model();token=replace(model.declaration_token,expansion=[])
        metadata=['call',1,2]
        root=Expr('+',None,(self.number(token,1.),self.number(token,2.)),token,source_call=metadata)
        self.attach(model,Assignment('q',root,token));owner=NativeAudit()
        for name in ('a','b','c'):
            out=qualify(model,{'gate':0.},name,owner)
            self.assertIs(out.analog[-1].rhs,root)
            self.assertIs(out.analog[-1].rhs.source_call,metadata)
            self.assertIs(out.analog[-1].rhs.token,token)
        metadata.append('retained');token.expansion.append(('gen',-2))
        out=qualify(model,{'gate':0.},'changed-metadata',owner)
        self.assertEqual(out.analog[-1].rhs.source_call,['call',1,2,'retained'])
        self.assertEqual(out.analog[-1].rhs.token.expansion,[('gen',-2)])
        # This test only qualifies relevance. Later source metadata/type gates
        # remain responsible for malformed handwritten source objects.

    def test_all_child_edges_are_prepaid_before_first_visit(self):
        model=self.model();token=model.declaration_token
        child=self.number(token,12345.)
        root=Expr('+',None,(child,self.number(token,54321.)),token)
        self.attach(model,Assignment('q',root,token));owner=NativeAudit();old=owner.debit;seen=[]
        def debit(kind,amount=1,item=None,**kw):
            if kind=='dead_call_relevance_lookup' and item is child:seen.append('child')
            if kind=='dead_call_relevance_edges' and item is root:
                self.assertEqual(amount,2)
                old('actual_other_work',100000,item)
            return old(kind,amount,item,**kw)
        with patch.object(owner,'debit',debit):
            with self.assertRaises(CompileError)as error:qualify(model,{'gate':0.},'failed',owner)
        self.assertEqual(error.exception.diagnostic['code'],'resource_budget')
        self.assertEqual(seen,[])
        for _ in range(2):
            with self.assertRaises(CompileError):qualify(model,{'gate':0.},'retry',owner)
        qualify(model,{'gate':0.},'fresh',NativeAudit())

    def test_live_dead_and_owner_contexts_do_not_share_verdicts(self):
        model=self.model();token=model.declaration_token
        call=Expr('unsupported_system_call','anything',(self.number(token,1.),),token)
        self.attach(model,self.conditional(token,[Assignment('q',call,token)]))
        owner=NativeAudit()
        qualify(model,{'gate':0.},'dead',owner)
        with self.assertRaises(CompileError):qualify(model,{'gate':1.},'live',owner)
        foreign=NativeAudit();qualify(model,{'gate':0.},'fresh',foreign)
        self.assertFalse(hasattr(foreign,'dead_call_immutable_irrelevance'))

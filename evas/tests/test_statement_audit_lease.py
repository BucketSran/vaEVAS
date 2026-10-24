"""Completed source audits may be leased only inside one statement/frame."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
from dataclasses import replace
from types import SimpleNamespace
import unittest
from evas import compile_sources, Instance, CompileError
from evas.native_audit import NativeAudit
from evas.statement_audit_lease import StatementAuditLease, _MISSING
from evas.syntax import Expr, Token, Assignment


class StatementAuditReceipts(unittest.TestCase):
    def source(self):
        token=Token('^','symbol',1,1,'lease.va')
        a=Expr('parameter','a',(),token);b=Expr('parameter','b',(),token)
        root=Expr('^',None,(a,b),token)
        return Assignment('q',root,token)

    def compiler(self):
        class Compiler(SimpleNamespace):
            def symbol(self,name):return self.state_ids[name]
        owner=NativeAudit()
        c=Compiler(compilation=SimpleNamespace(native_audit=owner,states=[SimpleNamespace(kind='integer'),SimpleNamespace(kind='integer')]),
            model=SimpleNamespace(source='lease.va',variables={'a':'integer','b':'integer'}),instance=SimpleNamespace(name='dut'),
            state_ids={'a':0,'b':1},integer_state_ranges={0:(0,1),1:(0,1)},ordinary_integer_bounds=None,
            active_event_aliases={},local_variables=set(),node_ids={},procedure_builder=SimpleNamespace(bindings={}))
        return c,owner

    def test_success_role_and_statement_lifetimes(self):
        c,w=self.compiler();s=self.source();lease=StatementAuditLease.create(c,s,w.extra)
        value=object();self.assertIs(lease.get(s.rhs,(True,False)),_MISSING)
        lease.put(s.rhs,(True,False),value)
        self.assertIs(lease.get(s.rhs,(True,False)),value)
        self.assertIs(lease.get(s.rhs,(False,False)),_MISSING)
        other=StatementAuditLease.create(c,s,w.extra)
        self.assertIs(other.get(s.rhs,(True,False)),_MISSING)
        self.assertEqual(w.used,sum(w.counts.values()))

    def test_binding_range_and_resolver_mutations_end_the_lease(self):
        changes=[lambda c:c.active_event_aliases.update(a=2),lambda c:c.procedure_builder.bindings.update(a=1),
            lambda c:c.integer_state_ranges.update({0:(0,2)}),lambda c:c.model.variables.update(a='real'),
            lambda c:setattr(c,'ordinary_integer_bounds',{0:(0,1)}),lambda c:setattr(c,'node_ids',{}),
            lambda c:setattr(c,'symbol',lambda name:0),lambda c:setattr(c.model,'source','other.va'),lambda c:setattr(c.procedure_builder,'scope_generation',1),
            lambda c:setattr(c,'procedure_builder',SimpleNamespace(bindings={}))]
        for change in changes:
            c,w=self.compiler();s=self.source();lease=StatementAuditLease.create(c,s,w.extra)
            lease.put(s.rhs,(True,False),123);change(c)
            self.assertIs(lease.get(s.rhs,(True,False)),_MISSING)
            self.assertFalse(lease.valid)
            c.integer_state_ranges[0]=(0,1)
            self.assertIs(lease.get(s.rhs,(True,False)),_MISSING)

    def test_all_metadata_and_children_must_be_immutable_and_pure(self):
        for mutate in [lambda x:replace(x,source_call=('f',1,2)),lambda x:replace(x,args=list(x.args)),
            lambda x:replace(x,token=replace(x.token,expansion=[('i',0)])),
            lambda x:replace(x,expansion=(['i',0],)),
            lambda x:replace(x,args=(replace(x.args[0],op='unsupported_system_call'),x.args[1]))]:
            c,w=self.compiler();s=self.source();s=replace(s,rhs=mutate(s.rhs))
            self.assertIsNone(StatementAuditLease.create(c,s,w.extra))

    def test_warm_lookup_and_context_creation_remain_sticky_paid(self):
        c,w=self.compiler();s=self.source();lease=StatementAuditLease.create(c,s,w.extra)
        lease.put(s.rhs,(True,False),123);before=w.used
        self.assertEqual(lease.get(s.rhs,(True,False)),123);self.assertGreater(w.used,before)
        w.debit('fill',100000-w.used)
        for attempt in range(2):
            with self.assertRaises(CompileError) as caught:lease.get(s.rhs,(True,False))
            self.assertEqual(caught.exception.diagnostic['code'],'resource_budget')
        c,w=self.compiler();self.assertIsNotNone(StatementAuditLease.create(c,s,w.extra))

    def public(self,rhs,dead=''):
        source="""`include "disciplines.vams"
module m(y,r);output y;inout r;electrical y,r;integer a,b,q;parameter integer gate=1;
analog begin @(initial_step)begin a=0;b=1;q=0;end
@(timer(1))begin if(gate>0)begin q=RHS;end else begin DEAD end end
V(y,r)<+q;end endmodule"""
        return compile_sources({'lease.va':source.replace('RHS',rhs).replace('DEAD',dead)},[Instance('dut','m',{'y':'y','r':'0'})])

    def test_public_selected_integer_tables_and_allarm_static_checks(self):
        self.public('(a^b)+2*(a^b)').to_dict()
        for rhs,dead in [('(a^b)+2147483647',''),('((2147483647+(a^b))-2147483647)',''),('(a^b)','q=missing^1;'),('(a^b)','q=1.0&1;')]:
            with self.assertRaises(CompileError):self.public(rhs,dead).to_dict()

    def test_failed_qualification_never_publishes_a_receipt(self):
        c,w=self.compiler();s=self.source();lease=StatementAuditLease.create(c,s,w.extra)
        for flags in [(False,False),(True,True)]:self.assertIs(lease.get(s.rhs,flags),_MISSING)
        c.integer_state_ranges[0]=(-2147483648,2147483647)
        self.assertIsNone(StatementAuditLease.create(c,s,w.extra))
        c.active_event_aliases['a']=0
        self.assertIsNone(StatementAuditLease.create(c,s,w.extra))

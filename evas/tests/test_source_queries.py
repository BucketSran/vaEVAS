"""Structural DAG queries retain source obligations and compilation ownership."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import unittest
from evas import CompileError, Instance, compile_sources
from evas.native_audit import NativeAudit
from evas.source_queries import SourceQuery
from evas.syntax import Expr, Token


class SourceQueries(unittest.TestCase):
    def test_shared_nodes_are_paid_once_edges_and_cache_hits_still_paid(self):
        owner=NativeAudit();token=Token('x','name',1,1,'dag.va')
        root=Expr('time',None,(),token)
        for _ in range(24):root=Expr('+',None,(root,root),token)
        visited=[]
        def local(item):
            visited.append(item)
            return (True,False) if item.op=='time' else (False,True)
        query=SourceQuery(owner,'query_test',local,lambda item,value,children:any(children))
        self.assertTrue(query(root));self.assertEqual(len(visited),25)
        self.assertEqual(len(query.memo),25)
        self.assertTrue(all(value[0] is not None for value in query.memo.values()))
        before=owner.used;self.assertTrue(query(root));self.assertGreater(owner.used,before)
        self.assertEqual(len(visited),25);self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_contexts_and_pruning_do_not_share_facts(self):
        owner=NativeAudit();token=Token('x','name',1,1,'dag.va')
        time=Expr('time',None,(),token);root=Expr('sin',None,(time,),token)
        queries=[]
        for prune in (True,False):
            query=SourceQuery(owner,'context',lambda item,prune=prune:((False,False) if prune and item.op=='sin' else (True,False) if item.op=='time' else (False,True)),lambda item,value,children:any(children))
            queries.append(query)
        self.assertFalse(queries[0](root));self.assertTrue(queries[1](root))
        self.assertIsNot(queries[0].memo,queries[1].memo)

    def test_budget_failure_is_prepaid_sticky_and_fresh_query_works(self):
        token=Token('x','name',1,1,'dag.va');root=Expr('number',1.0,(),token)
        owner=NativeAudit();query=SourceQuery(owner,'limited',lambda item:(True,False),lambda *args:True)
        owner.debit('prior_work',100000-owner.used)
        for _ in range(2):
            with self.assertRaises(CompileError) as raised:query(root)
            self.assertEqual(raised.exception.diagnostic['code'],'resource_budget')
            self.assertFalse(query.memo)
        fresh=NativeAudit();self.assertTrue(SourceQuery(fresh,'fresh',lambda item:(True,False),lambda *args:True)(root))

    def test_public_time_and_discarded_checked_names_remain_visible(self):
        function='analog function real f;input x;real x,tmp;begin tmp=x+x;f=1.0;end endfunction '
        source='`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'+function+'analog begin V(y)<+f($abstime);end endmodule'
        p=compile_sources({'time.va':source},[Instance('M','m',dict(u='u',y='y'))]);wire=p.to_dict()
        self.assertIn('$abstime',wire['nodes']);self.assertTrue(p._native_audit.active)
        for rhs in ('f(unknown)','f(V(y)>0)','f(idt(V(u),0))'):
            with self.subTest(rhs=rhs),self.assertRaises(CompileError):
                compile_sources({'bad.va':source.replace('f($abstime)',rhs)},[Instance('M','m',dict(u='u',y='y'))])

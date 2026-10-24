"""Checked compatibility views reuse syntax, never current bound values."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import random
import unittest
from evas import CompileError
from evas.ir import Affine, Select, Origin
from evas.lowering import _SourceAuditMemo, _checked_source_fact, _has_bound_decision
from evas.native_audit import NativeAudit
from evas.syntax import Expr, Token, DECISION_NAMES

class CheckedSourceFacts(unittest.TestCase):
    def test_random_shared_graph_matches_original_dfs_decisions_and_name_order(self):
        token = Token('x','name',1,1,'facts.va');rng=random.Random(490)
        pool=[Expr('parameter',n,(),token) for n in ('p','q','r')]+[Expr('number',1.,(),token)]
        for _ in range(90):
            pool.append(Expr(rng.choice(('+','checked','function_assign','ternary')),None,
                             tuple(rng.choice(pool) for _ in range(rng.randrange(1,4))),token))
        owner=NativeAudit();memo=_SourceAuditMemo(owner.ir_work,(None,None,None,None))
        for root in pool:
            pending=[root];seen=set();decision=False;names=[]
            while pending:
                node=pending.pop()
                if id(node) in seen:continue
                seen.add(id(node))
                if node.op in DECISION_NAMES:decision=True;break
                if node.op=='parameter':names.append(node.value)
                pending.extend(node.args)
            fact=_checked_source_fact(memo,root)
            self.assertEqual(fact[0],decision)
            if not decision:self.assertEqual(tuple(read.value for read in fact[1]),tuple(names))
        self.assertTrue(all(k==id(v[0]) for k,v in memo.checked_source_query.memo.items()))
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_warm_names_resolve_current_bindings_in_original_dfs_order(self):
        token=Token('x','name',1,1,'bindings.va')
        p,q=(Expr('parameter',n,(),token) for n in ('p','q'))
        root=Expr('checked',None,(p,q,p),token)
        owner=NativeAudit();memo=_SourceAuditMemo(owner.ir_work,(None,None,None,None))
        self.assertEqual(_checked_source_fact(memo,root),(False,(p,q)))
        values={'p':Affine(1.,()),'q':Affine(2.,())};reads=[]
        def lookup(name):reads.append(name);return values[name]
        lookup.native_work=owner.ir_work
        names=_checked_source_fact(memo,root)[1]
        self.assertFalse(_has_bound_decision(root,lookup,names=names));self.assertEqual(reads,['p','q'])
        other_p=Expr('parameter','p',(),token)
        distinct=Expr('checked',None,(p,q,other_p),token)
        self.assertEqual(_checked_source_fact(memo,distinct)[1],(other_p,q,p))
        values['p']=Select('lt',Affine(0.,()),Affine(1.,()),Affine(2.,()),Affine(3.,()),Origin('bindings.va',1,1,'M'))
        reads.clear();self.assertTrue(_has_bound_decision(root,lookup,names=names));self.assertEqual(reads,['p'])
        other=_SourceAuditMemo(NativeAudit().ir_work,(None,None,None,None))
        _checked_source_fact(other,root)
        self.assertIsNot(other.checked_source_query,memo.checked_source_query)

    def test_cached_fact_remains_paid_and_sticky(self):
        token=Token('x','name',1,1,'budget.va');root=Expr('parameter','p',(),token)
        owner=NativeAudit();memo=_SourceAuditMemo(owner.ir_work,(None,None,None,None))
        _checked_source_fact(memo,root);before=owner.used
        self.assertEqual(_checked_source_fact(memo,root),(False,(root,)))
        self.assertGreater(owner.used,before)
        with self.assertRaises(CompileError):owner.debit('actual_work',100000)
        for _ in range(2):
            with self.assertRaises(CompileError):_checked_source_fact(memo,root)
        fresh=_SourceAuditMemo(NativeAudit().ir_work,(None,None,None,None))
        self.assertEqual(_checked_source_fact(fresh,root),(False,(root,)))

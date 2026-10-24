"""Held-role syntax queries share immutable graphs without sharing execution."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import random
import unittest
from types import SimpleNamespace
from evas import CompileError, Instance, compile_sources
from evas.native_audit import NativeAudit
from evas.ordinary_held_state import _HeldQueries, _reads, _ops, _all_reads
from evas.source_queries import SourceStructure
from evas.syntax import Expr, Token, Assignment

class HeldSourceQueries(unittest.TestCase):
    def compiler(self, owner, name='a', contexts=None):
        compilation = SimpleNamespace(native_audit=owner)
        if contexts is not None:
            compilation.source_structure_contexts = contexts
        return SimpleNamespace(compilation=compilation, instance=SimpleNamespace(name=name))

    def test_shared_graph_matches_distinct_read_and_voltage_pruned_op_contracts(self):
        token = Token('x', 'name', 1, 1, 'dag.va')
        rng = random.Random(471)
        pool = [Expr('parameter', 'a', (), token), Expr('parameter', 'b', (), token),
                Expr('number', 2., (), token)]
        for _ in range(65):
            pool.append(Expr(rng.choice(('+', 'checked', 'voltage', 'decision')),
                             None, tuple(rng.choice(pool) for _ in range(2)), token))
        query = _HeldQueries(self.compiler(NativeAudit()))
        for root in pool:
            self.assertEqual(query.reads(root), _reads(root))
            self.assertEqual(query.ops(root), _ops(root))
        item = Assignment('q', pool[-1], token)
        self.assertEqual(_all_reads((item,), reads=query.reads, owner=query.owner), _all_reads((item,)))
        self.assertTrue(all(key == id(record[0]) for key, record in query.structure.memo.items()))

    def test_deep_shared_graph_is_linear_and_context_is_instance_owned(self):
        token = Token('x', 'name', 1, 1, 'deep.va')
        root = Expr('parameter', 'x', (), token)
        for _ in range(55):
            root = Expr('+', None, (root, root), token)
        owner = NativeAudit(); query = _HeldQueries(self.compiler(owner))
        self.assertEqual(query.reads(root), {'x'})
        self.assertEqual(query.ops(root), {'+', 'parameter'})
        self.assertEqual(len(query.structure.memo), 56)
        self.assertEqual(len(query.operations.memo), 56)
        before = owner.used
        self.assertEqual(query.reads(root), {'x'})
        self.assertEqual(owner.used-before, 2)
        contexts = {'a': query.structure}
        other = _HeldQueries(self.compiler(owner, 'b', contexts))
        self.assertIsNot(other.structure, query.structure)
        same = _HeldQueries(self.compiler(owner, 'a', contexts))
        self.assertIs(same.structure, query.structure)
        self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_mutable_children_rejected_and_cached_queries_stay_sticky(self):
        token = Token('x', 'name', 1, 1, 'bad.va')
        owner = NativeAudit(); query = _HeldQueries(self.compiler(owner))
        bad = Expr('+', None, [], token)
        with self.assertRaises(TypeError): query.reads(bad)
        with self.assertRaises(TypeError): query.ops(bad)
        leaf = Expr('parameter', 'x', (), token)
        query.reads(leaf)
        with self.assertRaises(CompileError): owner.debit('natural_work', 100000)
        for _ in range(2):
            with self.assertRaises(CompileError): query.reads(leaf)
        fresh = _HeldQueries(self.compiler(NativeAudit()))
        self.assertEqual(fresh.reads(leaf), {'x'})

    def test_availability_rechecks_same_graph_at_each_source_position(self):
        from evas.procedural import ProcedureBuilder
        token = Token('q', 'name', 1, 1, 'scope.va')
        root = Expr('parameter', 'q', (), token)
        for _ in range(22):
            root = Expr('+', None, (root, root), token)
        owner = NativeAudit(); compiler = self.compiler(owner)
        query = _HeldQueries(compiler)
        self.assertEqual(query.reads(root), {'q'})
        compiler.model = SimpleNamespace(functions={'f': object()}, procedure=())
        builder = SimpleNamespace(compiler=compiler, bindings={'q': 0, 'a': 1})
        zero = Expr('number', 0., (), token)
        compiler.model.procedure = (Assignment('q', zero, token), Assignment('a', root, token))
        ProcedureBuilder.audit_local_availability(builder)
        # A warm immutable names fact must not cache the preceding definition.
        compiler.model.procedure = (Assignment('a', root, token), Assignment('q', zero, token))
        with self.assertRaises(CompileError) as caught:
            ProcedureBuilder.audit_local_availability(builder)
        self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_local_event')
        self.assertEqual(caught.exception.diagnostic['location']['source'], 'scope.va')

    def test_warm_name_aggregation_prepays_each_consumed_reference(self):
        token = Token('x', 'name', 1, 1, 'wide.va')
        for count in (1, 16, 64, 256):
            owner = NativeAudit(); query = _HeldQueries(self.compiler(owner))
            leaves = tuple(Expr('parameter', 'p'+str(n), (), token) for n in range(count))
            level = leaves
            while len(level) > 1:
                level = tuple(Expr('checked', None, level[n:n+2], token) for n in range(0, len(level), 2))
            root = level[0]
            query.reads(root)
            item = Assignment('q', root, token)
            before = owner.used
            self.assertEqual(len(_all_reads((item,), reads=query.reads, owner=owner)), count)
            self.assertEqual(owner.used-before, 3+2*count)
            owner.debit('actual_other_work', 100000-owner.used-2)
            out = {'existing'}
            with self.assertRaises(CompileError):
                _all_reads((item,), out, reads=query.reads, owner=owner)
            self.assertEqual(out, {'existing'})

    def test_public_held_acceptance_and_invalid_source_still_audited(self):
        prefix = '`include "disciplines.vams"\nmodule m(u,y); input u;output y;electrical u,y;real q;'
        helper = 'analog function real f;input x;real x;begin f=x;end endfunction '
        for body in ('if(V(u)>0.5)q=1; V(y)<+q;',
                     'q=f(V(u));V(y)<+q;'):
            source = prefix+helper+'analog begin '+body+' end endmodule'
            compile_sources({'held.va': source}, [Instance('M','m',dict(u='u',y='y'))]).to_dict()
        for expr in ('missing(1)', 'unknown', 'f(1,2)'):
            source = prefix+helper+'analog begin q='+expr+';V(y)<+q;end endmodule'
            with self.assertRaises(CompileError):
                compile_sources({'held.va': source}, [Instance('M','m',dict(u='u',y='y'))])

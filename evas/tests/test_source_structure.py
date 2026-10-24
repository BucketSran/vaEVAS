"""Joint syntax facts preserve array gates, source identity and paid ownership."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import random
import unittest
from evas import CompileError, Instance, compile_sources
from evas.frontend import parse_sources
from evas.array_elaboration import scalarize_arrays
from evas.native_audit import NativeAudit
from evas.source_queries import SourceStructure, SourceQuery
from evas.syntax import Expr, Token


class SourceStructureContracts(unittest.TestCase):
    def test_random_shared_dag_matches_independent_time_and_read_scans(self):
        token = Token('x', 'name', 1, 1, 'dag.va')
        rng = random.Random(8279)
        pool = [Expr('time', None, (), token), Expr('parameter', 'p', (), token),
                Expr('index', 'a', (Expr('parameter', 'i', (), token),), token),
                Expr('number', 1.0, (), token)]
        def expected(root, seen=None):
            seen = set() if seen is None else seen
            if id(root) in seen:
                return False, set(), set()
            seen.add(id(root))
            time = root.op == 'time'
            names = {root.value} if root.op == 'parameter' else set()
            indexed = {root.value} if root.op == 'index' else set()
            for child in root.args:
                t, n, i = expected(child, seen)
                time |= t; names.update(n); indexed.update(i)
            return time, names, indexed
        for _ in range(160):
            args = tuple(rng.choice(pool) for _ in range(rng.randrange(1, 5)))
            pool.append(Expr(rng.choice(('checked', '+', 'decision', 'function_assign')), None, args, token))
        owner = NativeAudit(); query = SourceStructure(owner)
        for root in pool:
            time, names, indexed = expected(root)
            self.assertEqual(query.fact(root), (time, frozenset(names), frozenset(indexed)))
            expanded = names | ({'a[-1]', 'a[0]', 'a[1]'} if 'a' in indexed else set())
            self.assertEqual(query.reads(root, {'a': range(-1, 2)}), expanded)
        self.assertTrue(all(record[0] is not None for record in query.memo.values()))
        self.assertEqual(owner.used, sum(owner.counts.values()))
        indexed = pool[2]
        self.assertEqual(query.reads(indexed, {'a': (7,)}), {'i', 'a[7]'})
        self.assertEqual(query.reads(indexed, {'a': (-2,)}), {'i', 'a[-2]'})

    def test_wide_cross_edges_and_unary_continuations_do_not_duplicate_facts(self):
        token = Token('x', 'name', 1, 1, 'wide.va')
        leaf = Expr('parameter', 'x', (), token)
        chain = leaf
        for _ in range(120):
            chain = Expr('function_assign', None, (chain,), token)
        root = Expr('checked', None, (leaf, chain, Expr('+', None, (chain, leaf), token)), token)
        owner = NativeAudit(); query = SourceStructure(owner)
        self.assertEqual(query.fact(root), (False, frozenset(('x',)), frozenset()))
        self.assertEqual(len(query.memo), 123)
        before = owner.used
        self.assertEqual(query.reads(root, {}), {'x'})
        self.assertEqual(owner.used-before, 2)
        other = Expr('parameter', 'x', (), token)
        query.fact(other)
        self.assertIs(query.memo[id(other)][0], other)
        self.assertIsNot(query.memo[id(other)][0], leaf)
        self.assertIsNot(SourceStructure(NativeAudit()).memo, query.memo)

    def test_single_query_results_and_cost_do_not_require_second_consumer(self):
        token = Token('x', 'name', 1, 1, 'single.va')
        root = Expr('parameter', 'x', (), token)
        for _ in range(48):
            root = Expr('checked', None, (root, root), token)
        time_owner = NativeAudit()
        old_time = SourceQuery(time_owner, 'old_time',
                               lambda item: (item.op == 'time', True),
                               lambda item, value, children: value or any(children))
        read_owner = NativeAudit()
        def names(item, value, children):
            result = set(value)
            for child in children:
                result.update(child)
            return frozenset(result)
        old_reads = SourceQuery(read_owner, 'old_reads',
                                lambda item: (frozenset((item.value,)) if item.op == 'parameter' else frozenset(), True),
                                names)
        for expected, old, field in ((False, old_time, 0), (frozenset(('x',)), old_reads, 1)):
            owner = NativeAudit(); query = SourceStructure(owner)
            self.assertEqual(query.fact(root)[field], expected)
            self.assertEqual(old(root), expected)
            self.assertLess(owner.used, old.owner.used)

    def test_natural_exhaustion_is_sticky_and_fresh_context_is_separate(self):
        token = Token('x', 'name', 1, 1, 'large.va')
        root = Expr('number', 1.0, (), token)
        for _ in range(12000):
            root = Expr('function_assign', None, (root,), token)
        owner = NativeAudit(); query = SourceStructure(owner)
        for _ in range(2):
            with self.assertRaises(CompileError) as raised:
                query.fact(root)
            self.assertEqual(raised.exception.diagnostic['code'], 'resource_budget')
        self.assertEqual(owner.used, sum(owner.counts.values()))
        fresh = SourceStructure(NativeAudit())
        self.assertEqual(fresh.fact(Expr('number', 1.0, (), token))[0], False)
        mutable = Expr('+', None, [root], token)
        with self.assertRaises(TypeError):
            fresh.fact(mutable)

    def test_array_pass_preserves_only_unchanged_exprs_in_each_dynamic_context(self):
        source = ('`include "disciplines.vams"\nmodule m(y);output y;electrical y;'
                  'real a[0:1],q;integer i;analog function real f;input x;real x;begin f=x;end endfunction '
                  'analog begin @(initial_step)q=f(1.0);@(timer(1))q=a[i];V(y)<+q;end endmodule')
        model = parse_sources({'array.va': source})['m']
        owner = NativeAudit(); owner.activate(None)
        def parameter(name):
            raise CompileError('dynamic state is not an instance parameter')
        result = scalarize_arrays(model, parameter, native_audit=owner)
        self.assertIn('a[0]', result.variables)
        self.assertIn('a[1]', result.variables)
        self.assertIs(result.procedure[0].body[0].rhs, model.procedure[0].body[0].rhs)
        self.assertIsNot(result.procedure[1].body[0].rhs, model.procedure[1].body[0].rhs)
        # The same source node may be admitted dynamically and rejected in an
        # initial context. Its completed dynamic rewrite cannot certify initial.
        from dataclasses import replace
        bad = replace(model, analog=[], initial=[], events=[], procedure=(
            model.procedure[1], replace(model.procedure[0], body=model.procedure[1].body)))
        with self.assertRaises(CompileError):
            scalarize_arrays(bad, parameter, native_audit=NativeAudit())
        for index in ('f(0)', '0.0', 'a[0]'):
            with self.subTest(index=index), self.assertRaises(CompileError):
                compile_sources({'array.va': source.replace('a[i]', 'a['+index+']')},
                                [Instance('M', 'm', dict(y='y'))])

    def test_original_hundred_closed_identity_math_guards_materialize(self):
        source = ('`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; real q; '
                  'analog function real f; input x; real x; begin f=x; end endfunction analog begin '
                  + '@(timer(1)) q=cos(f(1.0)); '*100 + 'V(y,r)<+q; end endmodule')
        program = compile_sources({'boundary.va': source}, [Instance('dut', 'm', dict(y='y', r='0'))])
        wire = program.to_dict()
        self.assertEqual(len(wire['events']), 100)
        self.assertTrue(program._native_audit.active)
        self.assertLessEqual(program._native_audit.used, 100000)
        self.assertEqual(program._native_audit.used, sum(program._native_audit.counts.values()))

    def test_context_is_created_lazily_without_an_extra_binding_scan(self):
        from unittest.mock import patch
        original = SourceStructure.__init__
        plain = 'module plain(y);output y;electrical y;analog begin V(y)<+0;end endmodule\n'
        fun = ('module fun(y);output y;electrical y;analog function real f;input x;real x;'
               'begin f=x;end endfunction analog begin V(y)<+f(1.0);end endmodule\n')
        for first_time in (False, True):
            with self.subTest(first_time=first_time):
                seen = []
                def init(query, owner):
                    seen.append(owner)
                    original(query, owner)
                text = plain.replace('V(y)<+0', 'V(y)<+$abstime') if first_time else plain
                source = '`include "disciplines.vams"\n'+text+fun
                instances = [Instance('a'+str(i), 'plain', dict(y='y'+str(i))) for i in range(48)]
                instances.append(Instance('last', 'fun', dict(y='last')))
                with patch.object(SourceStructure, '__init__', init):
                    p = compile_sources({'many.va': source}, instances)
                    wire = p.to_dict()
                self.assertEqual(len(wire['contributions']), 49)
                self.assertEqual(seen, [p._native_audit])
                self.assertEqual(p._native_audit.counts['source_structure_contexts_container'], 1)
                self.assertEqual(p._native_audit.counts['source_structure_contexts_retain'], 1)
                self.assertEqual('$abstime' in wire['nodes'], first_time)
        p = compile_sources({'plain.va': '`include "disciplines.vams"\n'+plain},
                            [Instance('M', 'plain', dict(y='y'))])
        p.to_dict()
        self.assertFalse(any(k.startswith('source_structure') for k in p._native_audit.counts))

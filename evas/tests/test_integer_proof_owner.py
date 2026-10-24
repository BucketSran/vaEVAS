"""One proof allowance covers baseline and atomic optional refinements."""
GUARDS = ['LANG', 'EVENT-CONDITIONS', 'COMPOSE', 'EVENT-ORDER']
import gc
import unittest
import weakref
from unittest.mock import patch
from evas.integer_invariants import (ProofWork, SourceProofRequest, proof_parameters,
    ProofBudgetExceeded, OptionalProofUnavailable)
from evas.limits import MAX_IR_ITEMS
from evas.condition_domains import compact_domains, ConditionPlans
from evas import event_index_domains as domains
from evas.syntax import Expr, Token


def expr(op, *args, value=None):
    return Expr(op, value, args, Token(op, 'symbol', 1, 1, 'owner.va'))


def debit(work, count):
    for _ in range(count):
        work.charge()


class IntegerProofOwner(unittest.TestCase):
    def test_optional_view_has_no_allowance_and_declines_before_next_unit(self):
        owner = SourceProofRequest()
        work = owner.instance()
        view = work.optional_view()
        debit(view, MAX_IR_ITEMS-work.used)
        self.assertEqual((work.used, view.used, owner.used), (MAX_IR_ITEMS,) * 3)
        for _ in range(2):
            with self.assertRaises(OptionalProofUnavailable): view.charge()
        self.assertEqual(owner.used, MAX_IR_ITEMS)
        with self.assertRaises(ProofBudgetExceeded): work.charge()
        for _ in range(2):
            with self.assertRaises(ProofBudgetExceeded): view.charge()
        self.assertEqual(work.used, MAX_IR_ITEMS + 1)

    def test_active_request_prefix_and_inactive_original_local_roles(self):
        owner = SourceProofRequest()
        first = owner.instance()
        debit(first, MAX_IR_ITEMS)
        second = owner.instance()
        second.charge()
        self.assertEqual(second.used, 1)
        with self.assertRaises(ProofBudgetExceeded): owner.activate()
        with self.assertRaises(ProofBudgetExceeded): second.optional_view().charge()
        fresh = SourceProofRequest()
        fresh.activate()
        local = fresh.instance()
        view = local.optional_view()
        debit(view, MAX_IR_ITEMS-local.used)
        with self.assertRaises(OptionalProofUnavailable): fresh.instance().optional_view().charge()
        self.assertEqual(fresh.used, MAX_IR_ITEMS)
        with self.assertRaises(ProofBudgetExceeded): fresh.instance().charge()
        with self.assertRaises(ProofBudgetExceeded): local.optional_view().charge()

    def test_lookup_preserves_same_work_floor_callback_and_identity(self):
        work = SourceProofRequest().instance()
        def parameters(name): return name
        parameters.real_floor_bounds = object()
        wrapped = proof_parameters(parameters, work)
        self.assertIs(proof_parameters(wrapped, work), wrapped)
        self.assertIs(wrapped.integer_proof_counter, work)
        self.assertIs(wrapped.real_floor_bounds, parameters.real_floor_bounds)
        optional = proof_parameters(wrapped, work.optional_view())
        optional.integer_proof_work()
        self.assertEqual(work.used, 2)
        self.assertEqual(optional('bound'), 'bound')

    def test_plan_environment_callbacks_and_source_owner_are_never_cached(self):
        x = expr('parameter', value='x')
        guard = expr('&&', expr('>=', x, expr('number', value=0)), expr('<', x, expr('number', value=3)))
        zero = expr('number', value=0)
        owner = ProofWork()
        def charge(n): debit(owner, n)
        def lookup(name): return 0
        params = proof_parameters(lookup, owner)
        for low, high in ((-4,-1),(-2,5),(1,1),(4,8)):
            env = {'x': (low,high)}
            seen = []
            def refine(op, a, b, current):
                seen.append((op, id(current)))
                return domains.refine(op,a,b,current,params,{})
            actual = compact_domains('>',guard,zero,env,refine=refine,hull=domains.hull,work=charge,plan_cache=owner.condition_plans)
            expected = compact_domains('>',guard,zero,env,refine=refine,hull=domains.hull,work=lambda n:None)
            self.assertEqual(actual,expected)
            self.assertTrue(seen)
        plans=owner.condition_plans(charge)
        self.assertEqual(len(plans.plans),1)
        foreign=ProofWork()
        other=foreign.condition_plans(lambda n:debit(foreign,n))
        self.assertIsNot(plans,other)
        same_name=expr('&&',expr('>=',x,expr('number',value=4)),expr('<',x,expr('number',value=8)))
        plans.get('>',same_name,zero,charge)
        self.assertEqual(len(plans.plans),2)

    def test_plan_full_metadata_mutability_and_retention(self):
        owner=ProofWork()
        charge=lambda n:debit(owner,n)
        cache=owner.condition_plans(charge)
        x=expr('parameter',value='x')
        guard=expr('<',x,expr('number',value=2))
        zero=expr('number',value=0)
        reference=weakref.ref(guard)
        self.assertIsNotNone(cache.get('>',guard,zero,charge))
        del guard
        gc.collect()
        self.assertIsNotNone(reference())
        bad=Expr('<',None,(x,expr('number',value=2)),Token('<','symbol',1,1,'bad.va'),expansion=[])
        self.assertIsNone(cache.get('>',bad,zero,charge))
        self.assertEqual(len(cache.plans),1)
        self.assertNotIn(id(bad),cache.immutable)

    def test_failed_plan_build_does_not_publish_and_owner_stays_exhausted(self):
        owner=ProofWork()
        cache=owner.condition_plans(lambda n:debit(owner,n))
        guard=expr('<',expr('parameter',value='x'),expr('number',value=2))
        debit(owner,MAX_IR_ITEMS-owner.used-1)
        view=owner.optional_view()
        with self.assertRaises(OptionalProofUnavailable):
            cache.get('>',guard,expr('number',value=0),lambda n:debit(view,n))
        self.assertFalse(cache.plans)
        self.assertEqual(owner.used,MAX_IR_ITEMS)
        with self.assertRaises(ProofBudgetExceeded):owner.charge()
        with self.assertRaises(ProofBudgetExceeded):cache.get('>',guard,guard,lambda n:debit(view,n))

    def test_partial_partition_reachability_never_replaces_baseline(self):
        from evas import compile_sources
        from evas.instance_compiler import InstanceCompiler
        from test_affine import model,instance
        observed=[]
        analyze=InstanceCompiler.analyze_event_index_domains
        use=domains.use_site_facts
        def incomplete(*a,**kw):
            if kw.get('partitioned') is not None:
                kw['reachable'].add(12345)
                raise OptionalProofUnavailable()
            return use(*a,**kw)
        def collect(self):
            analyze(self)
            observed.append(self.event_reachable_statements)
        source=model('@(initial_step)b=0;@(timer(1))b=(V(u,r)>0); V(y,r)<+b;', 'integer b;')
        with patch.object(domains,'use_site_facts',incomplete),patch.object(InstanceCompiler,'analyze_event_index_domains',collect):
            compile_sources({'partial.va':source},[instance()]).to_dict()
        self.assertEqual(observed,[None])


    def test_mandatory_entry_exhaustion_is_public_resource_and_sticky(self):
        from evas import CompileError, compile_sources
        from test_affine import model, instance
        owner = SourceProofRequest()
        owner.activate()
        work = owner.instance()
        debit(work, MAX_IR_ITEMS)
        source = model('@(initial_step)n=0;@(timer(1))n=n+1;V(y,r)<+n;', 'integer n;')
        with patch.object(SourceProofRequest, 'instance', lambda self: work):
            for used in (100001, 100002, 100003):
                with self.assertRaises(CompileError) as caught:
                    compile_sources({'entry-budget.va':source}, [instance()])
                self.assertEqual(caught.exception.diagnostic['code'], 'resource_budget')
                self.assertEqual(owner.used, used)
        fresh = compile_sources({'entry-budget.va':source}, [instance()])
        fresh.to_dict()

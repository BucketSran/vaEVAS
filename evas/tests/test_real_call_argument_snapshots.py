"""Long actual-call chains keep independent activations and entry order."""
GUARDS = ['LANG', 'COMPOSE', 'EVENT-CONDITIONS']
import unittest
from evas import compile_sources, Instance, CompileError
from evas.ir import RealCall, RealBind, RealBoundary
from test_function_compatibility_dag import compile, nodes


class ArgumentSnapshots(unittest.TestCase):
    function = 'analog function real f;input x;real x,tmp;begin tmp=x+x;f=x+1.0;end endfunction '

    @staticmethod
    def chain(count, value='V(u)'):
        return 'f('*count+value+')'*count

    def test_threshold_neighbors_and_longer_sources_keep_calls_and_distinct_slots(self):
        for count in (15, 16, 17, 20, 24, 32):
            with self.subTest(count=count):
                p = compile(self.function, self.chain(count)); p.to_dict()
                calls = [n for n in nodes(p) if isinstance(n, RealCall)]
                self.assertEqual(len(calls), count)
                owners = [binding for call in calls for binding in call.bindings]
                self.assertEqual(len(owners), len(set(owners)))
                self.assertEqual(set(owners), set(range(len(p.real_bindings))))
                self.assertTrue(all(p.real_bindings[b].lifetime == 'call' for b in owners))
                if count < 17:
                    self.assertTrue(all(len(call.bindings) == 3 for call in calls))
                else:
                    self.assertTrue(any(len(call.bindings) > 3 for call in calls))
                for call in calls:
                    self.assertEqual([s.expanded_statement_ordinal for s in call.body], list(range(len(call.body))))
                    ended = False
                    for step in call.body:
                        action = step.action
                        self.assertIsInstance(action, RealBind)
                        self.assertIsInstance(action.value, RealBoundary)
                        if action.value.kind == 'argument':
                            self.assertFalse(ended)
                        else:
                            ended = True
                self.assertLessEqual(p._native_audit.used, 100000)
                self.assertEqual(p._native_audit.used, sum(p._native_audit.counts.values()))

    def test_unrelated_public_source_depth_limit_is_not_changed(self):
        value = 'V(u)'
        for _ in range(40):
            value = '(V(u)>0?'+value+':0)'
        for _ in range(2):
            with self.assertRaises(CompileError) as raised:
                compile('', value)
            self.assertEqual(raised.exception.diagnostic['code'], 'resource_budget')
            self.assertIn('nesting limit (64)', str(raised.exception))

    def test_selected_body_and_unused_actual_effects_remain_in_all_child_calls(self):
        function = 'analog function real f;input x;real x,tmp;begin tmp=1.0/x;tmp=0.0;f=1.0;end endfunction '
        p = compile(function, self.chain(20)); p.to_dict()
        calls = [n for n in nodes(p) if isinstance(n, RealCall)]
        self.assertEqual(len(calls), 20)
        # Every child retains both writes to tmp and its explicit return.
        for call in calls:
            stores = [s.action for s in call.body if s.action.value.kind == 'store']
            self.assertEqual(len(stores), 2)
            self.assertEqual(stores[0].binding, stores[1].binding)

    def test_identity_original_hundred_budget_route_has_no_chain_facts(self):
        s = ('`include "disciplines.vams"\nmodule m(y,r); output y; inout r; electrical y,r; real q; '
             'analog function real f; input x; real x; begin f=x; end endfunction analog begin '
             + '@(timer(1)) q=cos(f(1.0)); '*100 + 'V(y,r)<+q; end endmodule')
        p = compile_sources({'boundary.va': s}, [Instance('dut', 'm', dict(y='y', r='0'))]); p.to_dict()
        self.assertEqual(p._native_audit.used, 99971)
        self.assertFalse(any(k.startswith('real_call_chain') for k in p._native_audit.counts))

    def test_copyout_temporary_cannot_escape_or_lose_its_activation_owner(self):
        from dataclasses import replace
        from evas.ir import RealLocal
        p = compile(self.function, self.chain(17)); p.to_dict()
        call = next(n for n in nodes(p) if isinstance(n, RealCall) and len(n.bindings) > 3)
        temporary = call.bindings[-1]
        escaped = replace(p, contributions=(replace(p.contributions[0], rhs=RealLocal(temporary)),))
        with self.assertRaises(CompileError) as raised:
            escaped.to_dict()
        self.assertEqual(raised.exception.diagnostic['code'], 'invalid_ir')
        from evas.program_real_validation import validate_program_ir
        stolen = replace(call, bindings=call.bindings[:-1])
        # Reconstruct only the enclosing expression at the exact call position.
        def swap(value):
            from dataclasses import fields, is_dataclass
            if value is call:
                return stolen
            if is_dataclass(value):
                return replace(value, **{f.name: swap(getattr(value, f.name)) for f in fields(value) if f.init})
            if isinstance(value, tuple):
                return tuple(swap(x) for x in value)
            return value
        with self.assertRaises(CompileError) as raised:
            validate_program_ir(swap(p))
        self.assertEqual(raised.exception.diagnostic['code'], 'invalid_ir')

    def test_natural_capacity_and_retry_keep_original_owner_and_fresh_request(self):
        p = compile(self.function, self.chain(40))
        for _ in range(2):
            with self.assertRaises(CompileError) as raised:
                p.to_dict()
            self.assertEqual(raised.exception.diagnostic['code'], 'resource_budget')
        self.assertGreater(p._native_audit.used, 100000)
        self.assertEqual(p._native_audit.used, sum(p._native_audit.counts.values()))
        fresh = compile(self.function, self.chain(17)); fresh.to_dict()
        self.assertIsNot(fresh._native_audit, p._native_audit)

    def test_chain_context_is_paid_before_it_is_created(self):
        from unittest.mock import patch
        from evas.native_audit import NativeAudit
        from evas.instance_compiler import InstanceCompiler
        original_debit = NativeAudit.debit
        original_init = InstanceCompiler.__init__
        compilers = []
        owners = []
        def init(compiler, *args, **kwargs):
            compilers.append(compiler)
            original_init(compiler, *args, **kwargs)
        def debit(owner, kind, amount=1, item=None, **kwargs):
            if kind == 'real_call_chain_context':
                owners.append(owner)
                original_debit(owner, 'injected_prior_work', 100000-owner.used, item)
            return original_debit(owner, kind, amount, item, **kwargs)
        with patch.object(InstanceCompiler, '__init__', init), patch.object(NativeAudit, 'debit', debit):
            with self.assertRaises(CompileError) as raised:
                compile(self.function, self.chain(17))
        self.assertEqual(raised.exception.diagnostic['code'], 'resource_budget')
        self.assertEqual(len(owners), 1)
        self.assertFalse(hasattr(compilers[-1], '_real_call_argument_chains'))
        self.assertEqual(owners[0].used, sum(owners[0].counts.values()))
        with self.assertRaises(CompileError):
            owners[0].debit('same_failed_owner_retry')

    def test_body_failure_leaf_does_not_regain_module_copyin_permission(self):
        from dataclasses import replace, fields, is_dataclass
        from evas.ir import UnsupportedSystemCall, Affine
        text = ('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;'
                'integer seed;'+self.function+'analog begin @(initial_step)seed=19;V(y)<+'+
                self.chain(17)+';end endmodule')
        p = compile_sources({'body-permission.va': text}, [Instance('M', 'm', dict(u='u', y='y'))]); p.to_dict()
        child = next(n for n in nodes(p) if isinstance(n, RealCall) and len(n.bindings) == 3)
        seed = next(i for i, state in enumerate(p.states) if state.name == 'seed')
        returned = child.body[-1]
        leaf = UnsupportedSystemCall('rdist_normal', seed, (Affine(0.0, ()), Affine(0.0, ())), child.origin)
        changed = replace(returned, action=replace(returned.action, value=replace(returned.action.value, value=leaf)))
        bad = replace(child, body=(*child.body[:-1], changed))
        def swap(value):
            if value is child:
                return bad
            if is_dataclass(value):
                return replace(value, **{f.name: swap(getattr(value, f.name)) for f in fields(value) if f.init})
            if isinstance(value, tuple):
                return tuple(swap(x) for x in value)
            return value
        with self.assertRaisesRegex(CompileError, 'system function seed requires'):
            swap(p).to_dict()

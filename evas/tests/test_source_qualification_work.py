"""Source qualification skips proven irrelevant work without changing roles."""
GUARDS = ['LANG', 'COMPOSE']
from types import SimpleNamespace
import unittest

from evas import CompileError
from evas.frontend import parse_sources
from evas.native_audit import NativeAudit
from evas.parameters import bind_parameters
from evas import held_power2, unreachable_system_calls


def source(body):
    return ('`include "disciplines.vams"\nmodule m(y); output y; electrical y;\n'
            'parameter real gate=0; integer n; real b; analog begin\n'
            + body + '\nend endmodule')


def parsed(body):
    return parse_sources({'qualification.va': source(body)})['m']


class SourceQualificationWork(unittest.TestCase):
    def test_unrelated_source_subtree_keeps_identity_and_needs_no_branch_proof(self):
        model = parsed('@(initial_step) begin if(n>0) b=1.0; '
                       'if(gate>0) b=$anything(1); end V(y)<+b;')
        owner = NativeAudit()
        result = unreachable_system_calls.qualify(
            model, bind_parameters(model, {}, 'off'), 'off', owner)
        control = parsed('@(initial_step) if(gate>0) b=$anything(1); V(y)<+b;')
        control_owner = NativeAudit()
        unreachable_system_calls.qualify(
            control, bind_parameters(control, {}, 'off'), 'off', control_owner)
        self.assertEqual(owner.counts['dead_call_proof_visit'],
                         control_owner.counts['dead_call_proof_visit'])
        self.assertIs(result.initial[0], model.initial[0])
        self.assertIs(result.analog[0], model.analog[0])
        self.assertIsNot(result.initial[1], model.initial[1])
        self.assertGreater(owner.counts['dead_call_relevance_fields'], 0)
        self.assertGreater(owner.counts['dead_call_relevance_read'], 0)
        self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_relevance_never_shares_instance_or_dead_path_verdict(self):
        model = parsed('@(initial_step) if(gate>0) b=$anything(1); V(y)<+b;')
        owner = NativeAudit()
        unreachable_system_calls.qualify(model, bind_parameters(model, {}, 'off'), 'off', owner)
        with self.assertRaises(CompileError) as got:
            unreachable_system_calls.qualify(
                model, bind_parameters(model, {'gate': 1}, 'on'), 'on', owner)
        self.assertEqual(got.exception.diagnostic['code'], 'unsupported_system_function')
        self.assertEqual(got.exception.diagnostic['instance'], 'on')
        self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_dead_call_rewrite_preserves_function_occurrence_and_rounding_metadata(self):
        from dataclasses import fields,is_dataclass
        text=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;'
              'parameter real gate=0;real b;analog function real f;input x;real x;'
              'begin f=x+1.0;end endfunction analog begin '
              '@(initial_step)if(gate>0)b=f($anything(1));V(y)<+b;end endmodule')
        model=parse_sources({'metadata.va':text})['m'];owner=NativeAudit()
        result=unreachable_system_calls.qualify(model,bind_parameters(model,{},'off'),'off',owner)
        def exprs(root):
            from evas.syntax import Expr,Token
            if isinstance(root,Expr):
                yield root
                for child in root.args:yield from exprs(child)
            elif isinstance(root,Token):return
            elif is_dataclass(root):
                for field in fields(root):yield from exprs(getattr(root,field.name))
            elif isinstance(root,(tuple,list)):
                for child in root:yield from exprs(child)
            elif isinstance(root,dict):
                for child in root.values():yield from exprs(child)
        original=[e for e in exprs(model.initial) if e.source_call is not None]
        rewritten=[e for e in exprs(result.initial) if e.source_call is not None]
        self.assertTrue(original);self.assertEqual(len(original),len(rewritten))
        for before,after in zip(original,rewritten):
            for field in ('op','value','token','expansion','result_type','real_boundary_kind','source_call'):
                self.assertEqual(getattr(before,field),getattr(after,field))
            self.assertIs(before.expansion,after.expansion)
            self.assertIs(before.source_call,after.source_call)
        self.assertEqual(owner.used,sum(owner.counts.values()))

    def test_unused_function_argument_obligations_keep_dead_and_static_checks(self):
        prefix=('`include "disciplines.vams"\nmodule m(y);output y;electrical y;'
                'parameter real gate=0;real b;analog function real f;input x,z;real x,z;'
                'begin f=2.0;end endfunction analog begin @(initial_step)if(gate>0)b=f(1.0,')
        suffix=');V(y)<+b;end endmodule'
        model=parse_sources({'unused.va':prefix+'$anything(1)'+suffix})['m']
        off=NativeAudit();unreachable_system_calls.qualify(model,bind_parameters(model,{},'off'),'off',off)
        with self.assertRaises(CompileError) as live:
            unreachable_system_calls.qualify(model,bind_parameters(model,{'gate':1.0},'on'),'on',NativeAudit())
        self.assertEqual(live.exception.diagnostic['code'],'unsupported_system_function')
        for argument in ('$anything(missing)', '$anything(1.0&1)'):
            with self.subTest(argument=argument),self.assertRaises(CompileError):
                broken=parse_sources({'unused.va':prefix+argument+suffix})['m']
                unreachable_system_calls.qualify(broken,bind_parameters(broken,{},'off'),'off',NativeAudit())

    def test_expression_metadata_does_not_create_opaque_semantic_children(self):
        from dataclasses import replace
        source_model=parsed('@(initial_step)if(gate>0)b=1.0+$anything(1);V(y)<+b;')
        conditional=source_model.initial[0];assignment=conditional.then_body[0]
        def with_expansion(length):
            expanded=replace(assignment.rhs,expansion=tuple(('macro',i) for i in range(length)))
            selected=replace(conditional,then_body=(replace(assignment,rhs=expanded),))
            return replace(source_model,initial=[selected],procedure=())
        costs=[]
        for length in (0,64):
            model=with_expansion(length);owner=NativeAudit()
            result=unreachable_system_calls.qualify(model,bind_parameters(model,{},'off'),'off',owner)
            self.assertEqual(result.initial[0].then_body[0].rhs.expansion,model.initial[0].then_body[0].rhs.expansion)
            costs.append(owner.used)
        self.assertEqual(costs[0],costs[1])

    def test_repeated_real_qualification_naturally_exhausts_same_owner(self):
        model=parsed('@(initial_step)if(gate>0)b=1.0+$anything(1);V(y)<+b;')
        parameters=bind_parameters(model,{},'off');owner=NativeAudit()
        for _ in range(1000):
            try:unreachable_system_calls.qualify(model,parameters,'off',owner)
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'],'resource_budget');break
        else:self.fail('qualification did not use original request cap')
        for _ in range(2):
            with self.assertRaises(CompileError) as error:
                unreachable_system_calls.qualify(model,parameters,'off',owner)
            self.assertEqual(error.exception.diagnostic['code'],'resource_budget')
            self.assertGreater(owner.used,100000)
        fresh=NativeAudit();unreachable_system_calls.qualify(model,parameters,'off',fresh)
        self.assertLess(fresh.used,100000)

    def aliases(self, body):
        model = parsed(body)
        owner = NativeAudit()
        compiler = SimpleNamespace(model=model, compilation=SimpleNamespace(
            native_audit=owner, has_waveform_operators=True))
        return held_power2.target_aliases(compiler, model.analog), owner, model

    def test_single_writer_transition_alias_still_requires_full_role_proof(self):
        aliases, owner, model = self.aliases('b=n%2; V(y)<+transition(b,0,1n);')
        self.assertEqual(set(aliases), {'b'})
        self.assertIs(aliases['b'], model.analog[0])
        self.assertGreater(owner.counts['held_power2_alias_visit'], 0)

    def test_multiple_unconditional_writes_disprove_alias_before_deep_scan(self):
        for rhs in ('n%2', 'n*1.0'):
            with self.subTest(rhs=rhs):
                aliases, owner, _ = self.aliases(
                    'b=n%2; b=' + rhs + '; V(y)<+transition(b,0,1n);')
                self.assertEqual(aliases, {})
                self.assertEqual(owner.counts['held_power2_alias_visit'], 0)
                self.assertGreater(owner.counts['held_power2_alias_shallow_writer'], 0)
                self.assertEqual(owner.used, sum(owner.counts.values()))

    def test_conditional_and_event_writers_still_need_and_fail_full_proof(self):
        for extra in ('if(n>0) b=n%2;', '@(timer(1)) b=n%2;'):
            with self.subTest(extra=extra):
                aliases, owner, _ = self.aliases(
                    'b=n%2;' + extra + 'V(y)<+transition(b,0,1n);')
                self.assertEqual(aliases, {})
                self.assertGreater(owner.counts['held_power2_alias_visit'], 0)

    def test_early_negative_remains_on_same_sticky_active_owner(self):
        model = parsed('b=n%2; b=n%2; V(y)<+transition(b,0,1n);')
        owner = NativeAudit()
        owner.activate(model)
        owner.debit('previous_work', 99980)
        compiler = SimpleNamespace(model=model, compilation=SimpleNamespace(
            native_audit=owner, has_waveform_operators=True))
        for _ in range(2):
            with self.assertRaises(CompileError) as got:
                held_power2.target_aliases(compiler, model.analog)
            self.assertEqual(got.exception.diagnostic['code'], 'resource_budget')
        self.assertEqual(owner.counts['previous_work'], 99980)
        self.assertEqual(owner.used, sum(owner.counts.values()))


if __name__ == '__main__':
    unittest.main()

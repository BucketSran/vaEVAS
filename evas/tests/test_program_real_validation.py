"""Malformed public IR must not cross the rounded/procedural transport boundary.

These independent structural contracts do not claim local dominance or lifetime
proofs, or mathematical correctness of source arithmetic.
"""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE']
from dataclasses import replace
import unittest

from evas.errors import CompileError
from evas.ir import (Affine, AnalogProcedure, Assignment, Binary, BranchIdentity,
                     Conditional, Contribution, ContributionCapture, Display, Event,
                     EventGate, Idt, Loop, Origin, ProcedureStep, Program, RealBind,
                     ProcedureConditional, ProcedureLoop, RealBinding,
                     RealBoundary, RealBinary, RealLocal, State,
                     StepBound, StepBoundCapture, TimerTrigger)
from evas.native_audit import NativeAudit
from evas.program_real_validation import validate_program_ir


O = Origin('contract.va', 1, 1, 'dut')
ZERO = Affine(0., ())


def fixture():
    contribution = Contribution(BranchIdentity('dut', 'y', '0'), 1, 0, RealLocal(0), O)
    body = (Assignment(0, RealBoundary(RealLocal(0), 'store', O)),)
    event = Event(TimerTrigger(.5, 0, 1e-12, True), body, O, 0, 1)
    procedure = AnalogProcedure(0, 'dut', (
        ProcedureStep(0, RealBind(0, RealBoundary(ZERO, 'snapshot', O), O)),
        ProcedureStep(1, EventGate(0)),
        ProcedureStep(2, ContributionCapture(0))))
    return Program(('0', 'y'), (contribution,), (State('dut', 'q', 'real', 0.),),
                   (event,), procedures=(procedure,),
                   real_bindings=(RealBinding(0, 'snap', O),))


class ProgramRealValidation(unittest.TestCase):
    def reject(self, program):
        with self.assertRaises(CompileError):
            validate_program_ir(program)

    def test_valid_procedure_and_legacy_math_program(self):
        validate_program_ir(fixture())
        legacy = Program(('0', 'y'), (Contribution(BranchIdentity('dut', 'y', '0'),
                         1, 0, Binary('add', ZERO, ZERO), O),))
        validate_program_ir(legacy)
        placeholder = replace(legacy.contributions[0], origin=Origin('manual', 0, 0, ''))
        validate_program_ir(replace(legacy, contributions=(placeholder,)))
        real = RealBinary('divide', ZERO, Affine(3., ()), O)
        validate_program_ir(replace(legacy, contributions=(replace(legacy.contributions[0], rhs=real),)))

    def test_schema_and_new_expression_tags_are_validated(self):
        p = fixture()
        self.reject(replace(p, schema_version=32))
        for operation in ('remainder', '', None):
            with self.subTest(operation=operation):
                self.reject(replace(p, contributions=(replace(p.contributions[0],
                    rhs=RealBinary(operation, ZERO, ZERO, O)),)))
        for kind in ('', 'later', None):
            with self.subTest(kind=kind):
                self.reject(replace(p, contributions=(replace(p.contributions[0],
                    rhs=RealBoundary(ZERO, kind, O)),)))
        bad = RealBinary('add', ZERO, ZERO, O)
        object.__setattr__(bad, 'op', 'add')
        self.reject(replace(p, contributions=(replace(p.contributions[0], rhs=bad),)))
        self.reject(replace(p, contributions=(replace(p.contributions[0],
                    rhs=Binary('real_binary', ZERO, ZERO)),)))
        for node in (RealLocal(0), RealBoundary(ZERO, 'snapshot', O)):
            object.__setattr__(node, 'op', 'affine')
            self.reject(replace(p, contributions=(replace(p.contributions[0], rhs=node),)))
        for position, attribute in ((0, 'kind'), (1, 'kind'), (2, 'kind')):
            proc = p.procedures[0]
            action = replace(proc.body[position].action)
            object.__setattr__(action, attribute, 'wrong')
            body = tuple(replace(step, action=action) if n == position else step
                         for n, step in enumerate(proc.body))
            self.reject(replace(p, procedures=(replace(proc, body=body),)))

    def test_origins_and_instances_are_not_guessed(self):
        p = fixture()
        # Expansion provenance also includes genvar values, not only macro
        # source lines. Zero and negative iteration values retain identity.
        for iteration in (0, -1):
            validate_program_ir(replace(p, contributions=(replace(p.contributions[0],
                rhs=RealBoundary(ZERO, 'snapshot', replace(O, expansion=(('k', iteration),)))),)))
        for origin in (None, replace(O, source=''), replace(O, line=True),
                       replace(O, line=0), replace(O, column=-1),
                       replace(O, instance='other'), replace(O, expansion=(('macro', False),))):
            with self.subTest(origin=origin):
                self.reject(replace(p, contributions=(replace(p.contributions[0],
                    rhs=RealBoundary(ZERO, 'snapshot', origin)),)))

    def test_procedure_ids_and_ordinals_are_strict_nonboolean_unique_integers(self):
        p = fixture()
        proc = p.procedures[0]
        for invalid in (True, -1, .5):
            with self.subTest(procedure_id=invalid):
                self.reject(replace(p, procedures=(replace(proc, procedure_id=invalid),)))
            with self.subTest(ordinal=invalid):
                steps = (replace(proc.body[0], expanded_statement_ordinal=invalid), *proc.body[1:])
                self.reject(replace(p, procedures=(replace(proc, body=steps),)))
        self.reject(replace(p, procedures=(proc, proc)))
        for ordinals in ((0, 0, 2), (2, 1, 3)):
            steps = tuple(replace(step, expanded_statement_ordinal=ordinal)
                          for step, ordinal in zip(proc.body, ordinals))
            self.reject(replace(p, procedures=(replace(proc, body=steps),)))

    def test_event_gate_range_unique_owner_and_metadata(self):
        p = fixture()
        proc = p.procedures[0]
        for index in (True, -1, 1):
            steps = (proc.body[0], replace(proc.body[1], action=EventGate(index)), proc.body[2])
            self.reject(replace(p, procedures=(replace(proc, body=steps),)))
        self.reject(replace(p, procedures=(replace(proc, body=(proc.body[0], proc.body[2])),)))
        self.reject(replace(p, procedures=(replace(proc, body=(*proc.body, ProcedureStep(3, EventGate(0)))),)))
        for change in (dict(procedure_id=1), dict(expanded_statement_ordinal=2),
                       dict(origin=replace(O, instance='other'))):
            with self.subTest(change=change):
                self.reject(replace(p, events=(replace(p.events[0], **change),)))

    def test_capture_range_owner_and_coverage(self):
        p = fixture()
        proc = p.procedures[0]
        for index in (True, -1, 1):
            self.reject(replace(p, procedures=(replace(proc, body=(*proc.body[:2],
                ProcedureStep(2, ContributionCapture(index)))),)))
        self.reject(replace(p, procedures=(replace(proc, body=proc.body[:2]),)))
        self.reject(replace(p, procedures=(replace(proc, body=(*proc.body,
            ProcedureStep(3, ContributionCapture(0)))),)))
        self.reject(replace(p, contributions=(replace(p.contributions[0],
            branch=replace(p.contributions[0].branch, instance='other')),)))

    def test_bindings_and_local_references_do_not_cross_procedures(self):
        p = fixture()
        for binding in (RealBinding(9, 'snap', O), RealBinding(0, '', O),
                        RealBinding(0, 'snap', replace(O, instance='other')),
                        RealBinding(0, 'snap', O, 'forever')):
            self.reject(replace(p, real_bindings=(binding,)))
        for index in (True, -1, 1):
            self.reject(replace(p, contributions=(replace(p.contributions[0], rhs=RealLocal(index)),)))
        other = AnalogProcedure(1, 'other', ())
        self.reject(replace(p, procedures=(*p.procedures, other),
            real_bindings=(RealBinding(1, 'snap', replace(O, instance='other')),)))
        self.reject(replace(p, procedures=(), events=(), contributions=()))

    def test_local_bind_without_owner_and_state_initial_local_are_rejected(self):
        p = fixture()
        self.reject(replace(p, procedures=(), events=(), real_bindings=()))
        self.reject(replace(p, states=(replace(p.states[0], initial=RealLocal(0)),)))
        bad = replace(p.procedures[0].body[0].action, binding=1)
        self.reject(replace(p, procedures=(replace(p.procedures[0], body=(
            ProcedureStep(0, bad), *p.procedures[0].body[1:])),)))

    def test_binding_statements_cannot_masquerade_as_expressions(self):
        p = fixture()
        for expression in (RealBind(0, ZERO, O), Binary('add', RealBind(0, ZERO, O), ZERO),
                           RealBinding(0, 'hidden', O)):
            self.reject(replace(p, contributions=(replace(p.contributions[0], rhs=expression),)))

    def test_every_conditional_arm_and_loop_phase_is_walked(self):
        p = fixture()
        bad = Assignment(0, RealBoundary(ZERO, 'unrecognised', O))
        for action in (
            Conditional('lt', ZERO, ZERO, (), (bad,), O),
            Loop((), 'lt', ZERO, ZERO, (), (bad,), O),
            Loop((bad,), 'lt', ZERO, ZERO, (), (), O),
            Loop((), 'lt', ZERO, ZERO, (bad,), (), O)):
            self.reject(replace(p, events=(replace(p.events[0], body=(action,)),)))
        # A bind in an unchosen branch is still subject to owner checks.
        conditional = Conditional('lt', ZERO, ZERO, (), (RealBind(99, ZERO, O),), O)
        self.reject(replace(p, events=(replace(p.events[0], body=(conditional,)),)))

    def test_operator_local_requires_unambiguous_process_owner(self):
        p = fixture()
        validate_program_ir(replace(p, operators=(Idt(RealLocal(0), 0., O),)))
        self.reject(replace(p, operators=(Idt(RealLocal(0), 0., replace(O, instance='other')),)))
        second = AnalogProcedure(1, 'dut', ())
        self.reject(replace(p, procedures=(*p.procedures, second),
                            operators=(Idt(RealLocal(0), 0., O),)))

    def test_nested_gate_without_its_own_statement_ordinal_is_refused(self):
        p = fixture()
        nested = Conditional('lt', ZERO, ZERO, (EventGate(0),), (), O)
        self.reject(replace(p, procedures=(replace(p.procedures[0], body=(
            p.procedures[0].body[0], ProcedureStep(1, nested), p.procedures[0].body[2])),)))

    def test_recursive_procedure_if_uses_global_dfs_ordinals(self):
        p = fixture()
        control = ProcedureConditional('lt', ZERO, ZERO,
            (ProcedureStep(2, EventGate(0)),),
            (ProcedureStep(3, ContributionCapture(0)),), O)
        body = (p.procedures[0].body[0], ProcedureStep(1, control))
        nested = replace(p, procedures=(replace(p.procedures[0], body=body),),
                         events=(replace(p.events[0], expanded_statement_ordinal=2),))
        validate_program_ir(nested)
        for ordinal in (1, 2):
            broken = replace(control, else_body=(ProcedureStep(ordinal, ContributionCapture(0)),))
            self.reject(replace(nested, procedures=(replace(p.procedures[0],
                body=(body[0], ProcedureStep(1, broken))),)))
        direct = replace(control, then_body=(EventGate(0),))
        self.reject(replace(nested, procedures=(replace(p.procedures[0],
            body=(body[0], ProcedureStep(1, direct))),)))
        self.reject(replace(nested, events=p.events))

    def test_recursive_procedure_loop_visits_initialize_body_update_in_order(self):
        p = fixture()
        control = ProcedureLoop((ProcedureStep(2, RealBind(0, ZERO, O)),),
            'lt', ZERO, ZERO, (ProcedureStep(3, EventGate(0)),),
            (ProcedureStep(4, ContributionCapture(0)),), O)
        body = (p.procedures[0].body[0], ProcedureStep(1, control))
        nested = replace(p, procedures=(replace(p.procedures[0], body=body),),
                         events=(replace(p.events[0], expanded_statement_ordinal=3),))
        validate_program_ir(nested)
        broken = replace(control, initialize=(ProcedureStep(4, RealBind(0, ZERO, O)),))
        self.reject(replace(nested, procedures=(replace(p.procedures[0],
            body=(body[0], ProcedureStep(1, broken))),)))
        for part in ('initialize', 'body', 'update'):
            # The bad node is after otherwise valid references, including in
            # a loop phase that could be unexecuted for a particular input.
            previous = getattr(control, part)
            bad = ProcedureStep(previous[-1].expanded_statement_ordinal,
                RealBind(0, RealBoundary(ZERO, 'missing-round-kind', O), O))
            changed = replace(control, **{part: (bad,)})
            self.reject(replace(nested, procedures=(replace(p.procedures[0],
                body=(body[0], ProcedureStep(1, changed))),)))

    def test_checked_deep_procedure_tree_needs_no_unbounded_stack(self):
        from evas.limits import check_ir
        p = fixture()
        nested = (ProcedureStep(22, EventGate(0)), ProcedureStep(23, ContributionCapture(0)))
        for ordinal in reversed(range(1, 22)):
            nested = (ProcedureStep(ordinal, ProcedureConditional('lt', ZERO, ZERO, nested, (), O)),)
        body = (p.procedures[0].body[0], *nested)
        program = replace(p, procedures=(replace(p.procedures[0], body=body),),
                          events=(replace(p.events[0], expanded_statement_ordinal=22),))
        check_ir(program)  # The validator relies on this established depth boundary.
        validate_program_ir(program)

    def test_supplied_work_owner_is_charged_and_exhaustion_is_sticky(self):
        p = fixture()
        audit = NativeAudit()
        audit.activate(None)
        before = audit.used
        validate_program_ir(p, work=audit.ir_work)
        self.assertGreater(audit.used, before)
        audit.debit('other_owner_work', 100000-audit.used)
        for _ in range(2):
            with self.assertRaises(CompileError) as caught:
                validate_program_ir(p, work=audit.ir_work)
            self.assertEqual(caught.exception.diagnostic['code'], 'resource_budget')
        validate_program_ir(p)  # An independent request does not inherit this owner.

    def test_original_native_integer_consumer_keeps_active_owner_budget_and_retry(self):
        # Existing source and cap, with no new language feature. This is the
        # original225-increment positive fixture, not a synthetic ledger
        # filled by the test. Compile and wire copies do the real work.
        import hashlib
        from evas import Instance, compile_sources
        from test_native_audit import source
        original = source(True)
        original225 = original.replace('n=n+1;', 'n=n+1;' * 225).replace('m=m+1;', 'm=m+1;' * 225)
        self.assertEqual(hashlib.sha256(original225.encode()).hexdigest(),
                         '2071555869fc4bb90e83e54ccc859aa9d89d7beaf934218acade489f9ffc12da')
        text = original225

        def compile_original():
            return compile_sources({'ledger.va': text},
                [Instance('dut', 'm', dict(y='y', z='z', r='0'))])

        program = compile_original()
        owner = program._native_audit
        self.assertTrue(owner.active)
        self.assertIsInstance(program.to_dict(), dict)
        self.assertGreater(owner.counts['program_real_visit'], 0)
        for _ in range(1001):
            try:
                program.to_dict()
            except CompileError as error:
                self.assertEqual(error.diagnostic['code'], 'resource_budget')
                break
        else:
            self.fail('actual validation/materialization did not exhaust unchanged100000 cap')
        exhausted = owner.used
        for _ in range(2):
            with self.assertRaises(CompileError):
                program.to_dict()
            self.assertGreater(owner.used, exhausted)
            exhausted = owner.used
        fresh = compile_original()
        self.assertIsNot(fresh._native_audit, owner)
        self.assertIsInstance(fresh.to_dict(), dict)

    def test_step_bound_capture_has_one_ranged_process_owner(self):
        p = fixture()
        bound = StepBound(RealLocal(0), Affine(1., ()), O)
        proc = replace(p.procedures[0], body=(*p.procedures[0].body,
                       ProcedureStep(3, StepBoundCapture(0))))
        p = replace(p, procedures=(proc,), step_bounds=(bound,))
        validate_program_ir(p)
        for reference in (True, -1, 1):
            broken = replace(proc, body=(*proc.body[:3], ProcedureStep(3, StepBoundCapture(reference))))
            self.reject(replace(p, procedures=(broken,)))
        self.reject(replace(p, procedures=(replace(proc, body=proc.body[:3]),)))
        self.reject(replace(p, procedures=(replace(proc, body=(*proc.body,
            ProcedureStep(4, StepBoundCapture(0)))),)))
        self.reject(replace(p, step_bounds=(replace(bound, origin=replace(O, instance='other')),)))
        self.reject(replace(p, step_bounds=(RealBoundary(ZERO, 'snapshot', O),)))
        # Existing hand-authored mathematical bounds need no process capture.
        validate_program_ir(Program(('0',), (), step_bounds=(StepBound(ZERO, ZERO, O),)))

    def test_step_bound_capture_is_allowed_in_step_bearing_if_and_loop(self):
        p = fixture()
        for control in (
            ProcedureConditional('lt', ZERO, ZERO, (ProcedureStep(4, StepBoundCapture(0)),), (), O),
            ProcedureLoop((), 'lt', ZERO, ZERO, (), (ProcedureStep(4, StepBoundCapture(0)),), O)):
            proc = replace(p.procedures[0], body=(*p.procedures[0].body, ProcedureStep(3, control)))
            validate_program_ir(replace(p, procedures=(proc,), step_bounds=(StepBound(ZERO, ZERO, O),)))

    def test_public_bound_step_keeps_each_original_capture_position(self):
        from evas import Instance, compile_sources
        source = ('`include "disciplines.vams"\nmodule m(y);output y;electrical y;real q;'
                  'analog begin q=0.125;$bound_step(q);q=0.25;$bound_step(q);V(y)<+q;end endmodule')
        program = compile_sources({'bound-position.va': source}, [Instance('dut', 'm', {'y': 'y'})])
        body = program.procedures[0].body
        self.assertEqual([step.action.kind for step in body],
                         ['real_bind', 'step_bound_capture', 'real_bind', 'step_bound_capture', 'contribution_capture'])
        self.assertIsInstance(program.to_dict(), dict)
        broken = replace(program.procedures[0], body=(body[0],
            replace(body[1], action=StepBoundCapture(99)), *body[2:]))
        self.reject(replace(program, procedures=(broken,)))

    def test_sparse_facts_preserve_statement_roles_and_owner_checks(self):
        from evas.limits import check_ir
        p = fixture()
        # Sparse children must retain field names: legacy controls cannot give
        # a nested gate an ordinal, even when its whole shape is immutable.
        illegal = Conditional('lt', ZERO, ZERO, (EventGate(0),), (), O)
        event = replace(p.events[0], body=(illegal,))
        wrong_state = replace(p, states=(replace(p.states[0], instance='other'),))
        wrong_local = replace(p, real_bindings=(replace(p.real_bindings[0],
                              procedure_id=1, origin=replace(O, instance='other')),),
                              procedures=(*p.procedures, AnalogProcedure(1, 'other', ())))
        for program in (p, replace(p, events=(event,)), wrong_state, wrong_local):
            audit = NativeAudit()
            check_ir(program, work=audit.ir_work, cache=audit.ir_cache)
            if program is p:
                validate_program_ir(program, work=audit.ir_work, facts=audit.ir_cache)
            else:
                with self.assertRaises(CompileError):
                    validate_program_ir(program, work=audit.ir_work, facts=audit.ir_cache)

    def test_shape_facts_cannot_hide_forged_tags_or_mutable_descendants(self):
        from evas.limits import check_ir
        p = fixture()
        for value in (Binary('real_binary', ZERO, ZERO), {'op': 'real_local', 'binding': 0}):
            forged = replace(p, contributions=(replace(p.contributions[0], rhs=value),))
            audit = NativeAudit()
            check_ir(forged, work=audit.ir_work, cache=audit.ir_cache)
            with self.assertRaises(CompileError):
                validate_program_ir(forged, work=audit.ir_work, facts=audit.ir_cache)
        # The list makes the Affine and every containing object transitively
        # mutable, so prior false facts may not erase its later new reference.
        terms = []
        affine = Affine(0., terms)
        legacy = Program(('0', 'y'), (replace(p.contributions[0], rhs=affine),))
        audit = NativeAudit()
        check_ir(legacy, work=audit.ir_work, cache=audit.ir_cache)
        terms.append(RealLocal(99))
        with self.assertRaises(CompileError):
            validate_program_ir(legacy, work=audit.ir_work, facts=audit.ir_cache)
        bad = RealBinary('unknown', ZERO, ZERO, O)
        forged = replace(p, contributions=(replace(p.contributions[0], rhs=bad),))
        for fact in ((ZERO, (1, 1, True, False)), (bad, (1, 1, True)),
                     (bad, (1, 1, False, False))):
            with self.assertRaises(CompileError):
                validate_program_ir(forged, facts={id(bad): fact})


if __name__ == '__main__':
    unittest.main()

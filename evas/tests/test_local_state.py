"""Sequential analog locals combined with held event state, public Rust path."""
GUARDS = ["LANG", "TIMER", "EVENT-ORDER", "DYNAMICS", "case:local_state"]

import unittest
import json
from pathlib import Path

from evas import CompileError, KernelError, Instance, compile_sources, transient
from test_affine import KERNEL, instance, model


def compile_local(body, declarations="real a,q;", instances=None):
    return compile_sources({"local-state.va": model(body, declarations)}, instances or [instance()])


def run(program, times=(0, .25, .5, .75, 1)):
    return transient(program, {"u": [[0, 0], [1, 1]]}, list(times),
                     stop=1, max_step=.25, kernel=KERNEL, vabstol=1e-10, reltol=0)


def values(result, node="y"):
    index = result["nodes"].index(node)
    return [row["voltages"][index] for row in result["solutions"]]


class LocalStateContracts(unittest.TestCase):
    def test_local_ramp_and_timer_state_have_independent_answer(self):
        program = compile_local("""@(initial_step) q=1; @(timer(0.5)) q=2;
                                a=V(u,r); V(y,r)<+a+q;""")
        self.assertEqual(values(run(program)), [1, 1.25, 2.5, 2.75, 3])
        self.assertEqual([(state.name, state.kind) for state in program.states], [("q", "real")])

    def test_program_order_captures_each_contribution_before_reassignment(self):
        program = compile_local("""@(initial_step) q=1; @(timer(0.5)) q=2;
                                a=V(u,r); V(y,r)<+a+q;
                                a=2*a; V(y,r)<+a;""")
        self.assertEqual(values(run(program)), [1, 1.75, 3.5, 4.25, 5])

    def test_input_reference_and_parameters_are_instance_local(self):
        source = model("""@(initial_step) q=OFFSET; @(timer(0.5)) q=OFFSET+1;
                           a=GAIN*V(u,r); V(y,r)<+a+q;""",
                       "real a,q; parameter real GAIN=1, OFFSET=1;")
        instances = [instance("first", connections=dict(u="u", y="first", r="0")),
                     instance("second", connections=dict(u="0", y="second", r="u"),
                              parameters=dict(GAIN=2, OFFSET=3))]
        program = compile_sources({"local-state.va": source}, instances)
        result = run(program)
        self.assertEqual(values(result, "first"), [1, 1.25, 2.5, 2.75, 3])
        # V(second,u)=2*V(0,u)+q, hence second=q-u.
        self.assertEqual(values(result, "second"), [3, 2.75, 3.5, 3.25, 3])
        self.assertEqual([(s.instance, s.name) for s in program.states],
                         [("first", "q"), ("second", "q")])

    def test_event_reads_direct_input_and_current_persistent_state(self):
        program = compile_local("""@(initial_step) q=1;
                                @(timer(0.5)) begin q=V(u,r); q=q+1; end
                                a=V(u,r); V(y,r)<+a+q;""")
        self.assertEqual(values(run(program)), [1, 1.25, 2, 2.25, 2.5])

    def test_event_cannot_capture_an_analog_local_at_an_ambiguous_sequence(self):
        for body in ("a=V(u,r); @(timer(0.5)) q=a;",
                     "@(timer(0.5)) q=a; a=V(u,r);",
                     "a=V(u,r); @(cross(a-0.5,1)) q=2;",
                     "a=0.5; @(timer(a)) q=2;",
                     "a=V(u,r); @(timer(0.5)) if(a>0) q=2;",
                     "a=0.125; @(timer(0.5,0,a)) q=2;"):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "event expressions cannot read ordinary analog local") as failure:
                compile_local("@(initial_step) q=1; " + body + " V(y,r)<+q;")
            self.assertEqual(failure.exception.diagnostic["code"], "unsupported_local_event")
            self.assertEqual(failure.exception.diagnostic["category"], "unsupported")
            self.assertEqual(failure.exception.diagnostic["capability"], "LANG")
            self.assertEqual(failure.exception.diagnostic["instance"], "dut")

    def test_local_reads_require_a_prior_assignment_even_with_events(self):
        for body in ("V(y,r)<+a+q; a=V(u,r);", "a=a+1; V(y,r)<+a+q;",
                     "V(y,r)<+a+q;"):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "not assigned before use"):
                compile_local("@(initial_step) q=1; @(timer(0.5)) q=2; " + body)

    def test_local_event_errors_keep_available_source_location(self):
        for event in ("@(timer(0.5)) q=a;", "@(cross(a-0.5,1)) q=2;",
                      "@(timer(0.5)) if(a>0) q=2;", "@(timer(0.5,0,a)) q=2;"):
            with self.subTest(event=event), self.assertRaises(CompileError) as failure:
                compile_local("@(initial_step) q=1;\na=V(u,r);\n" + event + "\nV(y,r)<+q;")
            diagnostic=failure.exception.diagnostic
            self.assertEqual(diagnostic['code'],'unsupported_local_event')
            self.assertEqual(diagnostic['location']['source'],'local-state.va')
            self.assertEqual(diagnostic['location']['line'],4)
            self.assertGreater(diagnostic['location']['column'],0)

    def test_state_predicate_and_constant_setting_dependency_are_explicit(self):
        for event in ("@(timer(0.5)) if(q>0) q=2;", "@(timer(0.5,0,q)) q=2;",
                      "@(cross(V(u,r)-0.5,q)) q=2;"):
            with self.subTest(event=event), self.assertRaises(CompileError) as failure:
                compile_local("@(initial_step) q=1;\n" + event + "\na=V(u,r); V(y,r)<+a+q;")
            diagnostic=failure.exception.diagnostic
            self.assertEqual(diagnostic['code'],'unsupported_event_state_dependency')
            self.assertEqual(diagnostic['category'],'unsupported')
            self.assertIn('persistent state',str(failure.exception))
            self.assertEqual(diagnostic['location']['line'],3)

    def test_ordinary_input_if_compiles_but_event_transient_stays_unsupported(self):
        program=compile_local("""@(initial_step) q=1; @(timer(0.5)) q=2;
                                if(V(u,r)>0.5) a=1; else a=2; V(y,r)<+a+q;""")
        with self.assertRaises(KernelError) as failure:
            run(program)
        self.assertEqual(failure.exception.detail['kind'],'unsupported_transient')
        # The integrated continuous-select gate rejects this model before the older conditional gate.
        self.assertEqual(failure.exception.detail['message'],
                         'continuous select requires a finite source-only affine clamp; '
                         'event/state/internal feedback and discontinuous selects are unsupported')

    def test_unread_unwritten_real_declaration_requires_no_initial_state(self):
        program=compile_local("@(initial_step) q=1; @(timer(0.5)) q=2; V(y,r)<+q;",'real q,dead;')
        self.assertEqual([state.name for state in program.states],['q'])
        self.assertEqual(values(run(program)),[1,1,2,2,2])

    def test_writer_roles_are_not_inferred_from_initialization_alone(self):
        for body in ("@(initial_step) q=1; @(timer(0.5)) a=2; V(y,r)<+q;",
                     "@(initial_step) q=1; @(timer(0.5)) if(V(u,r)>0) a=2; V(y,r)<+q;"):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, "every state requires one initial_step"):
                compile_local(body)
        with self.assertRaisesRegex(CompileError, "assignment target must be a local real"):
            compile_local("@(initial_step) begin a=0; q=1; end a=V(u,r); V(y,r)<+a+q;")
        with self.assertRaisesRegex(CompileError, "only support real variables"):
            compile_local("@(initial_step) q=1; a=1; V(y,r)<+a+q;", "integer a; real q;")
        with self.assertRaises(CompileError):
            compile_local("@(initial_step) q=1; @(timer(0.5)) if(q>0) q=2; a=V(u,r); V(y,r)<+a+q;")
        with self.assertRaisesRegex(CompileError, "predicates must be affine"):
            compile_local("@(initial_step) q=1; if(q>0) a=1; else a=2; V(y,r)<+a+q;")

    def test_integrator_histories_belong_to_call_sites_not_reassigned_local(self):
        program = compile_local("""@(initial_step) q=1; @(timer(0.5)) q=2;
                                a=idt(1,0); V(y,r)<+a+q;
                                a=idt(2,0.25); V(y,r)<+a;""")
        self.assertEqual(len(program.operators), 2)
        self.assertNotEqual(program.operators[0].origin, program.operators[1].origin)
        sparse = run(program, (0, .5, 1))
        dense = run(program, (0, .125, .25, .375, .5, .625, .75, .875, 1))
        # Independent integral: t + (2*t+.25) + q(t).
        self.assertEqual(values(sparse), [1.25, 3.75, 5.25])
        self.assertEqual(values(dense)[::4], values(sparse))
        self.assertEqual(dense["transient"]["events"], sparse["transient"]["events"])

    def test_integrator_call_sites_are_isolated_across_instances(self):
        source = model("""@(initial_step) q=1; @(timer(0.5)) q=2;
                           a=idt(GAIN,0); V(y,r)<+a+q;""",
                       "real a,q; parameter real GAIN=1;")
        program = compile_sources({"local-state.va": source}, [
            instance("first", connections=dict(u="u", y="first", r="0")),
            instance("second", connections=dict(u="u", y="second", r="0"), parameters=dict(GAIN=2))])
        self.assertEqual(len(program.operators), 2)
        result = run(program)
        self.assertEqual(values(result, "first"), [1, 1.25, 2.5, 2.75, 3])
        self.assertEqual(values(result, "second"), [1, 1.5, 3, 3.5, 4])

    def test_frozen_spectre_source_satisfies_hand_derived_formulas(self):
        directory = Path(__file__).resolve().parents[1] / "validation/cases/local_state"
        manifest = json.loads((directory / "manifest.json").read_text())
        program = compile_sources({"dut.va": (directory / "dut.va").read_text()},
                                  [Instance(**item) for item in manifest["instances"]])
        result = transient(program, manifest["input"], manifest["times"], kernel=KERNEL,
                           **manifest["EVAS"])
        for index, time in enumerate(manifest["times"]):
            step = int(time >= .5)
            expected = dict(y1=time+1+step, z1=3*time+1+step, h1=3*time+1.25+step,
                            y2=2*time+3+step, z2=6*time+3+step, h2=3*time+3.25+step,
                            q1=1+step, q2=3+step, qc=1+.5*step, yc=time+1+.5*step)
            for node, exact in expected.items():
                with self.subTest(time=time, node=node):
                    self.assertAlmostEqual(values(result, node)[index], exact, delta=1e-10)

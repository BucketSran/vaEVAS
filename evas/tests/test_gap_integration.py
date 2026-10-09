"""Cross-feature hand answers for the temporary gap integration checkpoint.

These are development combinations, not new conditions or an untouched holdout.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS", "COMPOSE"]

import math
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, model


def rows(program, sources, times, *, max_step):
    result = transient(program, sources, times, stop=times[-1], max_step=max_step,
                       kernel=KERNEL, vabstol=1e-10, reltol=1e-10)
    values = [dict(zip(result["nodes"], s["voltages"])) for s in result["solutions"]]
    return result, values


class GapIntegration(unittest.TestCase):
    def test_assignment_snapshots_and_laplace_share_one_frontend(self):
        source = model("""
            local = V(u,r);
            V(y,r) <+ local;
            local = local + 1;
            V(y,r) <+ local;
            V(filtered,r) <+ laplace_nd(V(u,r), '{1}, '{1,0.5});
        """, "real local;", ports="u,y,filtered,r",
            directions="input u; output y,filtered; inout r;")
        program = compile_sources({"snapshots.va": source}, [Instance("dut", "m",
                                  dict(u="u", y="y", filtered="filtered", r="0"))])
        _, actual = rows(program, {"u": [[0,.25],[2,.25]]}, [0,.5,1,2], max_step=2)
        for row in actual:
            self.assertAlmostEqual(row["y"], 1.5, delta=1e-10)
            # The constant-input DC equilibrium is the initial filter value.
            self.assertAlmostEqual(row["filtered"], .25, delta=1e-10)

    def test_multiple_writers_reset_integral_and_transition_commit_together(self):
        source = model("""
            @(initial_step) reset_flag=0;
            @(timer(1,0,1e-8)) reset_flag=1;
            @(timer(2,0,1e-8)) reset_flag=0;
            V(y,r) <+ idt(V(u,r),0.25,reset_flag);
            V(q,r) <+ transition(reset_flag,0,0.25,0.25);
        """, "integer reset_flag;", ports="u,y,q,r",
            directions="input u; output y,q; inout r;")
        program = compile_sources({"reset-transition.va": source}, [Instance("dut", "m",
                                  dict(u="u", y="y", q="q", r="0"))])
        sparse = [0,.5,1,1.25,2,2.125,2.25,3]
        baseline = None
        for times, step in [(sparse,3), ([k/8 for k in range(25)],.125)]:
            result, actual = rows(program, {"u": [[0,1],[3,1]]}, times, max_step=step)
            self.assertEqual([e["time"] for e in result["transient"]["events"]], [1,2])
            for t, row in zip(times, actual):
                expected = .25+t if t < 1 else .25 if t <= 2 else .25+t-2
                edge = min(1, max(0,4*(t-1)))-min(1,max(0,4*(t-2)))
                self.assertAlmostEqual(row["y"], expected, delta=1e-10)
                self.assertAlmostEqual(row["q"], edge, delta=1e-10)
            current = dict(zip(times,actual))
            if baseline is not None:
                for t in sparse:
                    for node in ("y","q"):
                        self.assertAlmostEqual(current[t][node], baseline[t][node], delta=1e-10)
            else:
                baseline = current

    def test_phase_aliases_and_filter_preserve_independent_histories(self):
        source = "`include \"constants.vams\"\n"+model("""
            accumulated = idt(V(u,r),0.125);
            phase = idtmod(V(u,r),0.125,1,0);
            V(y,r) <+ sin(2*`M_PI*phase);
            V(total,r) <+ accumulated;
            V(filtered,r) <+ laplace_nd(V(u,r), '{1}, '{1,0.5});
        """, "real accumulated,phase;", ports="u,y,total,filtered,r",
            directions="input u; output y,total,filtered; inout r;")
        program = compile_sources({"phase-filter.va": source}, [Instance("dut", "m",
                 dict(u="u", y="y", total="total", filtered="filtered", r="0"))])
        times = [0,.5,1,1.5,2,2.5,3,3.5,4]
        _, actual = rows(program, {"u": [[0,.25],[4,.25]]}, times, max_step=4)
        # Values at eighth-turn phases, derived from the unit circle.
        circle = [math.sqrt(.5),1,math.sqrt(.5),0,-math.sqrt(.5),-1,-math.sqrt(.5),0,math.sqrt(.5)]
        for t, expected, row in zip(times,circle,actual):
            self.assertAlmostEqual(row["y"], expected, delta=1e-10)
            self.assertAlmostEqual(row["total"], .125+.25*t, delta=1e-10)
            self.assertAlmostEqual(row["filtered"], .25, delta=1e-10)

    def test_nonlinear_event_coupling_keeps_explicit_rejection(self):
        source = model("""
            @(initial_step) n=0;
            @(timer(1,0,1e-8)) n=n+1;
            V(y,r) <+ V(u,r)-0.5*pow(V(y,r),3)+n;
        """, "integer n;")
        program = compile_sources({"nonlinear-state.va": source},
                                  [Instance("dut","m",dict(u="u",y="y",r="0"))])
        with self.assertRaises(KernelError) as caught:
            rows(program, {"u": [[0,0],[2,1]]}, [0,1,2], max_step=2)
        self.assertEqual(caught.exception.detail["kind"], "unsupported_transient")


    def test_sequential_operator_assignments_keep_separate_call_histories(self):
        source = model("""
            tmp=idt(V(u,r),1);
            V(y,r)<+tmp;
            tmp=idt(V(u,r),2);
            V(q,r)<+tmp;
        """, "real tmp;", ports="u,y,q,r",
            directions="input u; output y,q; inout r;")
        program=compile_sources({"call-sites.va":source}, [Instance("dut","m",dict(u="u",y="y",q="q",r="0"))])
        self.assertEqual(len(program.operators),2)
        for times in ([0,2],[0,.25,.5,1,2]):
            _,actual=rows(program,{"u":[[0,1],[2,1]]},times,max_step=2)
            for time,row in zip(times,actual):
                self.assertAlmostEqual(row["y"],1+time,delta=1e-10)
                self.assertAlmostEqual(row["q"],2+time,delta=1e-10)

    def test_dynamic_alias_cancellation_preserves_zero_feedback_semantics(self):
        source=model("tmp=V(y,r)-V(y,r); V(y,r)<+idt(tmp,0);", "real tmp;")
        program=compile_sources({"hidden-dependency.va":source},[Instance("dut","m",dict(u="u",y="y",r="0"))])
        _, actual=rows(program,{"u":[[0,0],[1,0]]},[0,.5,1],max_step=1)
        for row in actual:
            self.assertAlmostEqual(row["y"],0,delta=1e-12)

    def test_select_with_dynamic_operator_keeps_documented_rejection(self):
        source=model("tmp=V(u,r); if(V(u,r)>0.5) tmp=1; else tmp=0; V(y,r)<+tmp+idt(V(u,r),0);","real tmp;")
        program=compile_sources({"select-idt.va":source},[Instance("dut","m",dict(u="u",y="y",r="0"))])
        with self.assertRaisesRegex(KernelError,"unsupported_transient"):
            rows(program,{"u":[[0,0],[1,1]]},[0,1],max_step=1)


    def test_local_alias_cancellation_preserves_predicate_dependency(self):
        bodies=[
            "if(V(y,r)-V(y,r)+V(u,r)>0) b=1; else b=0; V(y,r)<+b;",
            "a=V(y,r)-V(y,r)+V(u,r); if(a>0) b=1; else b=0; V(y,r)<+b;",
        ]
        for body in bodies:
            with self.subTest(body=body), self.assertRaisesRegex(CompileError,"predicates must depend only"):
                compile_sources({"predicate-deps.va":model(body,"real a,b;")},[Instance("dut","m",dict(u="u",y="y",r="0"))])

    def test_polynomial_certificate_survives_unused_and_empty_conditions(self):
        from fractions import Fraction
        from test_nonlinear_transient import cubic_root
        for extra in ("", "if(V(u,r)>-2) begin end",
                      "unused=0; if(V(u,r)>-2) unused=1;"):
            with self.subTest(extra=extra):
                source = model("tmp=V(u,r)-0.25*pow(V(y,r),3); " + extra +
                               " V(y,r)<+tmp;", "real tmp,unused;")
                program = compile_sources({"poly-noop.va":source},
                                          [Instance("dut","m",dict(u="u",y="y",r="0"))])
                _, actual = rows(program, {"u":[[0,1],[3,2]]}, [1,3], max_step=3)
                for row, u in zip(actual, (Fraction(4,3), Fraction(2))):
                    self.assertAlmostEqual(row["y"], cubic_root(float(u), .25, 1), delta=1e-10)
                # Adding irrelevant source statements must not bypass the
                # original PWL error certificate on the polynomial path.
                high_gain = model("tmp=1e16*(V(u,r)-1)+1e-60*pow(V(y,r),3); " +
                                  extra + " V(y,r)<+tmp;", "real tmp,unused;")
                candidate = compile_sources({"poly-gain.va": high_gain},
                                            [Instance("dut","m",dict(u="u",y="y",r="0"))])
                with self.assertRaisesRegex(KernelError, "waveform_accuracy"):
                    transient(candidate, {"u":[[0,1],[3,2]]}, [1,3], stop=3, max_step=3,
                              kernel=KERNEL, vabstol=1e-12, reltol=0)

    def test_affine_redundant_constraints_keep_forward_certificate(self):
        from fractions import Fraction
        source = model("V(y,r)<+V(u,r);")
        program = compile_sources({"redundant.va":source},
                                  [Instance(name,"m",dict(u="u",y="y",r="0"))
                                   for name in ("a","b")])
        _, actual = rows(program, {"u":[[0,1],[3,2]]}, [1,3], max_step=3)
        self.assertLessEqual(abs(Fraction(actual[0]["y"])-Fraction(4,3)), Fraction(1,10**10))

    def test_reset_feedback_through_sin_operator_is_rejected(self):
        source = model("""
            @(initial_step) reset=0;
            @(timer(1,0,1e-8)) reset=V(y,r);
            V(y,r)<+sin(idt(V(u,r),0.25,reset));
        """, "real reset;")
        program = compile_sources({"reset-sin-feedback.va":source},
                                  [Instance("dut","m",dict(u="u",y="y",r="0"))])
        with self.assertRaisesRegex(KernelError, "unsupported_operator.*reset feedback"):
            rows(program, {"u":[[0,.25],[3,.25]]}, [0,1,3], max_step=3)

    def test_reset_filter_and_phase_retain_independent_histories(self):
        source = model("""
            @(initial_step) reset=0;
            @(timer(1,0,1e-8)) reset=1;
            @(timer(2,0,1e-8)) reset=0;
            V(y,r)<+idt(V(u,r),0.125,reset);
            V(filtered,r)<+laplace_nd(V(u,r), '{1}, '{1,0.5});
            V(phase,r)<+idtmod(V(u,r),0.125,1,0);
            V(sine,r)<+sin(idt(V(u,r),0.125,reset));
        """, "real reset;", ports="u,y,filtered,phase,sine,r",
                       directions="input u; output y,filtered,phase,sine; inout r;")
        program = compile_sources({"reset-filter-phase.va":source}, [Instance("dut","m",
                  dict(u="u", y="y", filtered="filtered", phase="phase", sine="sine", r="0"))])
        for times, step in (([0,.5,1,1.5,2,3],3), ([k/8 for k in range(25)],.125)):
            _, actual = rows(program, {"u":[[0,.25],[3,.25]]}, times, max_step=step)
            for time, row in zip(times, actual):
                reset_value = .125 + .25*time if time < 1 else .125 if time <= 2 else .125+.25*(time-2)
                self.assertAlmostEqual(row["y"], reset_value, delta=1e-10)
                self.assertAlmostEqual(row["sine"], math.sin(reset_value), delta=1e-10)
                self.assertAlmostEqual(row["filtered"], .25, delta=1e-10)
                self.assertAlmostEqual(row["phase"], .125+.25*time, delta=1e-10)

    def test_selected_polynomial_leaves_remain_outside_condition_contract(self):
        source = model("tmp=V(u,r); if(V(u,r)>0) tmp=V(u,r)-pow(V(y,r),3); V(y,r)<+tmp;", "real tmp;")
        program = compile_sources({"select-poly.va":source},
                                  [Instance("dut","m",dict(u="u",y="y",r="0"))])
        with self.assertRaisesRegex(KernelError, "unsupported_transient"):
            rows(program, {"u":[[0,1],[3,2]]}, [1,3], max_step=3)

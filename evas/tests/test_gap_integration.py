"""Cross-feature hand answers for the temporary gap integration checkpoint.

These are development combinations, not new conditions or an untouched holdout.
"""
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
            V(filtered,r) <+ laplace_nd(V(u,r), '{1}, '{1,.5});
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
            V(y,r) <+ idt(V(u,r),.25,reset_flag);
            V(q,r) <+ transition(reset_flag,0,.25,.25);
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
            accumulated = idt(V(u,r),.125);
            phase = idtmod(V(u,r),.125,1,0);
            V(y,r) <+ sin(2*`M_PI*phase);
            V(total,r) <+ accumulated;
            V(filtered,r) <+ laplace_nd(V(u,r), '{1}, '{1,.5});
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
            V(y,r) <+ V(u,r)-.5*pow(V(y,r),3)+n;
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

    def test_dynamic_alias_cancellation_cannot_hide_operator_dependency(self):
        source=model("tmp=V(y,r)-V(y,r); V(y,r)<+idt(tmp,0);", "real tmp;")
        program=compile_sources({"hidden-dependency.va":source},[Instance("dut","m",dict(u="u",y="y",r="0"))])
        with self.assertRaisesRegex(KernelError,"unsupported_operator"):
            rows(program,{"u":[[0,0],[1,0]]},[0,1],max_step=1)

    def test_select_with_dynamic_operator_keeps_documented_rejection(self):
        source=model("tmp=V(u,r); if(V(u,r)>.5) tmp=1; else tmp=0; V(y,r)<+tmp+idt(V(u,r),0);","real tmp;")
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

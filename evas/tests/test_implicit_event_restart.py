"""Finite index-one DAE restart: physical ICs and the branch survive a timer."""
GUARDS = ["DYNAMICS", "EVENT-ORDER", "COMPOSE"]
from pathlib import Path
import os
import unittest
from evas import Instance, KernelError, compile_sources, transient

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get("EVAS_DAE_EVENT_KERNEL", ROOT / "rust_core/target/debug/evas-kernel"))
SOURCE = (Path(__file__).parent/"fixtures/implicit-event-restart/dut.va").read_text()
TIMES = [0., .125, .25, .5, .625, .75, 1.]


def compile_case(source=SOURCE):
    return compile_sources({"dut.va": source}, [Instance("DUT", "dae_event", {"u":"u", "y":"y", "w":"w"})])


def execute(program, times=TIMES, **kwargs):
    return transient(program, {"u":[[0.,0.],[1.,0.]]}, times, stop=1., max_step=1.,
                     vabstol=1e-9, reltol=1e-9, kernel=KERNEL, **kwargs)


class ImplicitEventRestart(unittest.TestCase):
    def test_original_model_preserves_integrals_and_changes_rate(self):
        result = execute(compile_case())
        y, w = result["nodes"].index("y"), result["nodes"].index("w")
        bounds=result["observation_evidence"]["voltage_bounds_V"]
        for t, solution, frame_bounds in zip(TIMES,result["solutions"],bounds):
            expected = .25+t if t<=.5 else .75+2*(t-.5)
            for node, answer in [(y,expected),(w,3+t)]:
                actual=solution["voltages"][node]
                self.assertLessEqual(abs(actual-answer),1e-9+1e-9*abs(actual))
                lo,hi=frame_bounds[node]
                self.assertLessEqual(lo,answer)
                self.assertLessEqual(answer,hi)
        event, = result["transient"]["events"]
        self.assertEqual(event["time"],.5)
        self.assertEqual(event["before"],[1.])
        self.assertEqual(event["after"],[2.])



class ImplicitEventRestartBoundaries(unittest.TestCase):
    def test_extra_queries_preserve_history_event_and_common_values(self):
        program=compile_case()
        sparse=execute(program)
        dense_times=[i/32 for i in range(33)]
        dense=execute(program,dense_times)
        self.assertEqual(sparse['transient']['events'],dense['transient']['events'])
        self.assertEqual(sparse['transient']['accepted_steps'],dense['transient']['accepted_steps'])
        self.assertEqual(sparse['solutions'],[dense['solutions'][dense_times.index(t)] for t in TIMES])

    def test_old_field_is_not_built_past_the_timer_horizon(self):
        # The old rate=-1 flow folds at .75, but the actual .5 event changes
        # it to +1 before then. Constructing the old mode to stop is invalid.
        source=SOURCE.replace('@(initial_step) rate=1;','@(initial_step) rate=-1;').replace('@(timer(0.5)) rate=2;','@(timer(0.5)) rate=1;').replace('0.0625/rate','0.0625')
        result=execute(compile_case(source))
        y=result['nodes'].index('y')
        for t,row in zip(TIMES,result['solutions']):
            expected=.25-t if t<=.5 else -.25+(t-.5)
            self.assertAlmostEqual(row['voltages'][y],expected,delta=1e-8)

    def test_unrelated_filter_state_is_not_reinitialized_to_new_dc(self):
        import math
        source=SOURCE.replace('V(w)<+idt(1,3);',"V(w)<+laplace_nd(V(u),'{1},'{1,1});")
        program=compile_case(source)
        result=transient(program,{'u':[[0,1],[1,2]]},TIMES,stop=1,max_step=1,
                         vabstol=1e-9,reltol=1e-9,kernel=KERNEL)
        w=result['nodes'].index('w')
        # f'+f=1+t with the sole cold DC f(0)=1 gives f=t+exp(-t).
        for t,row in zip(TIMES,result['solutions']):
            self.assertAlmostEqual(row['voltages'][w],t+math.exp(-t),delta=1e-8)

    def test_filter_with_changed_forcing_keeps_its_accepted_physical_seed(self):
        import math
        source=SOURCE.replace('V(w)<+idt(1,3);',"V(w)<+laplace_nd(rate,'{1},'{1,1});")
        result=execute(compile_case(source))
        w=result['nodes'].index('w')
        # Only cold DC is 1. Recomputing DC=2 at .5 would create a jump.
        for t,row in zip(TIMES,result['solutions']):
            expected=1 if t<=.5 else 2-math.exp(-(t-.5))
            self.assertAlmostEqual(row['voltages'][w],expected,delta=1e-8)

    def test_multiroot_initial_constraint_retains_the_selected_regular_branch(self):
        # z0=.3125 admits .25 and -1.25. The cold solve certifies the local
        # regular branch near its initial guess, then continuity preserves it.
        split=SOURCE.replace('V(y)<+idt(rate*(1+2*V(y)),0.3125)-pow(V(y),2);','V(y)<+-pow(V(y),2);V(y)<+idt(rate*(1+2*V(y)),0.3125);')
        result=execute(compile_case(split))
        y=result['nodes'].index('y')
        self.assertAlmostEqual(result['solutions'][0]['voltages'][y],.25,delta=1e-8)
        self.assertAlmostEqual(result['solutions'][-1]['voltages'][y],1.75,delta=1e-8)

    def test_singular_initial_branch_is_rejected(self):
        with self.assertRaises(KernelError):
            execute(compile_case(SOURCE.replace('0.3125','-0.25')))

    def test_inconsistent_integral_ic_and_algebraic_relation_is_rejected(self):
        with self.assertRaises(KernelError):
            execute(compile_case(SOURCE.replace('V(w)<+idt(1,3);','V(w)<+idt(1,3);V(y,u)<+0.5;')))

    def test_parameter_to_constraint_jump_requires_a_separate_branch_certificate(self):
        source=SOURCE.replace('real rate;','real rate,shift;').replace('@(initial_step) rate=1;','@(initial_step) begin rate=1;shift=0;end').replace('@(timer(0.5)) rate=2;','@(timer(0.5)) begin rate=2;shift=2;end').replace('-pow(V(y),2);','-pow(V(y),2)-shift;')
        with self.assertRaisesRegex(KernelError,'unsupported_implicit_dynamics.*branch reselection'):
            execute(compile_case(source))

    def test_unselected_physical_reads_and_zero_terms_do_not_bypass_admission(self):
        for body in ['if(rate<0)rate=V(y);else rate=2;','rate=2+0*V(y);']:
            with self.subTest(body=body):
                with self.assertRaisesRegex(KernelError,'unsupported_implicit_dynamics.*physical reads'):
                    execute(compile_case(SOURCE.replace('rate=2;',body)))

    def test_nonpoint_clock_windows_remain_explicitly_unsupported(self):
        with self.assertRaisesRegex(KernelError,'unsupported_implicit_dynamics.*exactly representable'):
            execute(compile_case(SOURCE.replace('timer(0.5)','timer(0.1,0.2,1e-6)')))

    def test_same_time_conflicting_writers_keep_the_shared_rejection(self):
        source=SOURCE.replace('@(timer(0.5)) rate=2;','@(timer(0.5)) rate=2;@(timer(0.5)) rate=3;')
        with self.assertRaisesRegex(KernelError,'event_conflict'):
            execute(compile_case(source))


if __name__ == "__main__":
    unittest.main()

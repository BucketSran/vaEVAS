"""Event sampling must certify every possible root time, not only its representative."""
import math
import unittest

from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class EventWindowSamplingContracts(unittest.TestCase):
    def test_matching_fired_guard_proves_equality_at_the_actual_root(self):
        from fractions import Fraction as Q
        root = (Q(.5)-Q(.2))/(Q(.8)-Q(.2))
        for relation, expected_state in [('>=', 2), ('<=', 2), ('>', 3), ('<', 3)]:
            program = compile_model(
                "@(initial_step) q=0; @(cross(V(u,r)-.5,1,1e-9,1e-8)) "
                f"if (V(u,r){relation}.5) q=2; else q=3; V(y,r)<+idt(q*q,0);",
                "integer q;")
            with self.subTest(relation=relation):
                result = run(program, {"u": [[0,.2],[1,.8]]}, [0,1], stop=1,
                             vabstol=1e-8, reltol=0)
                self.assertEqual(result['transient']['events'][0]['after'], [expected_state])
                assert_close(self, values(result)[-1], float(expected_state**2*(1-root)), delta=1e-8)

    def test_or_guard_that_did_not_fire_cannot_certify_a_condition(self):
        from fractions import Fraction as Q
        root = (Q(.5)-Q(.2))/(Q(.8)-Q(.2))
        program = compile_model(
            "@(initial_step) q=0; @(cross(V(u,r)-.5,1,1e-9,1e-8) "
            "or cross(V(c,r)-.5,1,1e-9,1e-8)) "
            "if (V(c,r)>=.5) q=2; else q=3; V(y,r)<+idt(q*q,0);",
            "integer q;", ports="u,c,y,r", directions="input u,c; output y; inout r;")
        result = run(program, {"u": [[0,.2],[1,.8]], "c": [[0,.25],[1,.25]]}, [0,1],
                     stop=1, vabstol=1e-8, reltol=0)
        self.assertEqual(result['transient']['events'][0]['after'], [3])
        assert_close(self, values(result)[-1], float(9*(1-root)), delta=1e-8)

    def test_linear_input_sample_retains_time_error_in_future_integral(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(u,r); "
            "V(y,r)<+idt(q,0);", "real q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,1,1.75,2], stop=2,
                     vabstol=1e-7, reltol=1e-7)
        for t, actual in zip([0,1,1.75,2], values(result)):
            assert_close(self, actual, 0 if t<math.sqrt(2) else math.sqrt(2)*(t-math.sqrt(2)), delta=3e-7)

    def test_nonlinear_sample_controls_polynomial_flow_with_full_time_enclosure(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(u,r); "
            "V(y,r)<+idt(q*q,0);", "real q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,1,1.75,2], stop=2,
                     vabstol=1e-7, reltol=1e-7)
        for t, actual in zip([0,1,1.75,2], values(result)):
            assert_close(self, actual, 0 if t<math.sqrt(2) else 2*(t-math.sqrt(2)), delta=3e-7)

    def test_condition_is_accepted_only_when_one_arm_is_proved_over_root_window(self):
        program = compile_model(
            "@(initial_step) q=1; @(cross(pow(V(u,r),2)-2,1,1e-6,1e-5)) "
            "if (V(u,r)>1.5) q=2; else q=3; V(y,r)<+idt(q,0);", "integer q;")
        result = run(program, {"u": [[0,0],[2,2]]}, [0,2], stop=2, vabstol=1e-4, reltol=0)
        assert_close(self, values(result)[-1], 6-2*math.sqrt(2), delta=1e-4)
        ambiguous = compile_model(
            "@(initial_step) q=1; @(cross(pow(V(u,r),2)-2,1,1e-5,1e-4)) "
            "if (V(u,r)>1.414214) q=2; else q=3; V(y,r)<+idt(q,0);", "integer q;")
        with self.assertRaisesRegex(KernelError, "event_condition"):
            run(ambiguous, {"u": [[0,0],[2,2]]}, [0,2], stop=2, vabstol=1e-4, reltol=0)

    def test_loose_root_cannot_accept_amplified_sample_with_tight_budget(self):
        program = compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-5,1e-4)) q=1e6*V(u,r); "
            "V(y,r)<+idt(q*q,0);", "real q;")
        with self.assertRaisesRegex(KernelError, "waveform_accuracy"):
            run(program, {"u": [[0,0],[10,10]]}, [0,10], stop=10, vabstol=2e7, reltol=1e-10)

    def test_integral_history_sample_uses_event_instant_not_post_event_flow(self):
        # z(t)=t; q=z(sqrt(2)); y'=q^2 after that event. Resampling
        # candidate history at b after new-mode flow would change q's box.
        program=compile_model(
            "@(initial_step) q=0; @(cross(pow(V(u,r),2)-2,1,1e-9,1e-8)) q=V(z,r); "
            "V(z,r)<+idt(1,0); V(y,r)<+idt(q*q,0);", "real q; electrical z;")
        times=[0,1,1.75,2]
        result=run(program,{"u":[[0,0],[2,2]]},times,stop=2,vabstol=1e-7,reltol=1e-7)
        for t,row in zip(times,rows(result)):
            assert_close(self,row["dut:z"],t,delta=3e-7)
            assert_close(self,row["y"],0 if t<math.sqrt(2) else 2*(t-math.sqrt(2)),delta=3e-7)

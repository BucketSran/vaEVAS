"""Independent dynamic composition answers, separate from the frozen 31 cases."""
import math
import unittest

from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class InternalDerivativeContracts(unittest.TestCase):
    def test_internal_relay_and_direct_encodings_agree_in_dc_and_at_corners(self):
        sources = {"u": [[0, 2], [0.5, 3], [1, 2]]}
        times = [0, 0.25, 0.5, 0.75, 1]
        for body, decl in [
            ("V(y,r)<+ddt(2*V(u,r)+3);", ""),
            ("V(z,r)<+2*V(u,r)+3; V(y,r)<+ddt(V(z,r));", "electrical z;"),
        ]:
            result = run(compile_model(body, decl), sources, times, stop=1)
            for actual, expected in zip(values(result), [0, 4, -4, -4, -4]):
                assert_close(self, actual, expected, delta=1e-10)

    def test_derivative_of_integral_is_input_after_dc_observation(self):
        times = [0, 0.25, 0.5, 1]
        for body, decl in [
            ("V(y,r)<+ddt(idt(2+V(u,r),3));", ""),
            ("V(z,r)<+idt(2+V(u,r),3); V(y,r)<+ddt(V(z,r));", "electrical z;"),
        ]:
            result = run(compile_model(body, decl), {"u": [[0, 0], [1, 1]]}, times, stop=1)
            for t, actual in zip(times, values(result)):
                assert_close(self, actual, 0 if t == 0 else 2+t, delta=1e-10)

    def test_derivative_of_feedback_integral_uses_joint_state_equation(self):
        program = compile_model("V(z,r)<+idt(1-V(z,r),.25); V(y,r)<+ddt(V(z,r));", "electrical z;")
        times = [0, 0.125, 0.5, 1, 2]
        for step in [2, 0.125]:
            result = run(program, times=times, stop=2, max_step=step, vabstol=1e-10, reltol=0)
            for t, row in zip(times, rows(result)):
                assert_close(self, row["dut:z"], 1-.75*math.exp(-t), delta=1e-10)
                assert_close(self, row["y"], 0 if t == 0 else .75*math.exp(-t), delta=1e-10)

    def test_derivative_of_lowpass_has_analytic_ramp_answer(self):
        program = compile_model("V(y,r)<+ddt(laplace_nd(V(u,r),'{1},'{1,1}));")
        times = [0, .125, .5, 1, 2]
        result = run(program, {"u": [[0, 0], [2, 2]]}, times, stop=2)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1-math.exp(-t), delta=1e-10)

    def test_downstream_filter_dc_uses_zero_derivative_not_transient_limit(self):
        # Input d=ddt(idt(1,3)): d(DC)=0, d(t>0)=1. Lowpass
        # therefore starts at zero and gives 1-exp(-t), not a constant 1.
        program = compile_model("V(y,r)<+laplace_nd(ddt(idt(1,3)),'{1},'{1,1});")
        times = [0, .125, .5, 1, 2]
        result = run(program, times=times, stop=2)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1-math.exp(-t), delta=1e-10)

    def test_derivative_feedback_is_solved_as_algebraic_mass_relation(self):
        # z'=1-d, d=.5*z' => z'=2/3, d=1/3; DC derivative is 0.
        program = compile_model("V(z,r)<+idt(1-V(y,r),0); V(y,r)<+ddt(.5*V(z,r));", "electrical z;")
        times = [0, .25, .5, 1]
        result = run(program, times=times, stop=1)
        for t, row in zip(times, rows(result)):
            assert_close(self, row["dut:z"], 2*t/3, delta=1e-10)
            assert_close(self, row["y"], 0 if t == 0 else 1/3, delta=1e-10)

    def test_uncertified_derivative_order_and_impulses_are_rejected(self):
        cases = [
            "V(y,r)<+ddt(ddt(V(u,r)));",
            "V(z,r)<+ddt(V(u,r)); V(y,r)<+ddt(V(z,r));",
            "V(y,r)<+ddt(V(y,r));",
        ]
        for body in cases:
            with self.subTest(body=body):
                program = compile_model(body, "electrical z;")
                with self.assertRaises(KernelError):
                    run(program, {"u": [[0, 0], [.5, 1], [1, 0]]}, [0, .5, 1], stop=1)

    def test_singular_derivative_mass_relation_does_not_fabricate_solution(self):
        program = compile_model("V(z,r)<+idt(1+V(y,r),0); V(y,r)<+ddt(V(z,r));", "electrical z;")
        with self.assertRaises(KernelError):
            run(program, times=[0, .5, 1], stop=1)


class JointEventDynamicsContracts(unittest.TestCase):
    def test_event_input_change_preserves_integral_state_and_rebuilds_future(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(.5,0,1e-12)) q=2; "
            "V(y,r)<+idt(q-V(y,r),0);", "real q;")
        sparse = [0, .25, .5, .75, 1, 2]
        for times, step in [(sparse, 2), ([i/16 for i in range(33)], .125)]:
            result = run(program, times=times, stop=2, max_step=step, vabstol=1e-10, reltol=0)
            for t, actual in zip(times, values(result)):
                expected = 0 if t <= .5 else 2*(1-math.exp(-(t-.5)))
                assert_close(self, actual, expected, delta=1e-10)

    def test_joint_reset_holds_ic_then_resumes_feedback(self):
        program = compile_model(
            "@(initial_step) rst=0; @(timer(.5,0,1e-12)) rst=1; "
            "@(timer(1,0,1e-12)) rst=0; V(y,r)<+idt(1-V(y,r),.25,rst);", "integer rst;")
        times = [0, .25, .5, .75, 1, 1.25, 2]
        result = run(program, times=times, stop=2, vabstol=1e-10, reltol=0)
        for t, actual in zip(times, values(result)):
            expected = (1-.75*math.exp(-t) if t < .5 else
                        .25 if t <= 1 else 1-.75*math.exp(-(t-1)))
            assert_close(self, actual, expected, delta=1e-10)

    def test_reset_of_first_integrator_keeps_second_history(self):
        program = compile_model(
            "@(initial_step) rst=0; @(timer(1,0,1e-12)) rst=1; "
            "@(timer(1.5,0,1e-12)) rst=0; "
            "V(z,r)<+idt(1,0,rst); V(y,r)<+idt(V(z,r),0);", "integer rst; electrical z;")
        times = [0, .5, 1, 1.25, 1.5, 2, 3]
        result = run(program, times=times, stop=3, vabstol=1e-10, reltol=0)
        for t, row in zip(times, rows(result)):
            first = t if t < 1 else 0 if t <= 1.5 else t-1.5
            second = t*t/2 if t < 1 else .5 if t <= 1.5 else .5+(t-1.5)**2/2
            assert_close(self, row["dut:z"], first, delta=1e-10)
            assert_close(self, row["y"], second, delta=1e-10)

    def test_event_sampling_can_change_future_integrand_without_reset_loop(self):
        program = compile_model(
            "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=V(y,r); "
            "V(y,r)<+idt(q,0);", "real q;")
        times = [0, .25, .5, .75, 1]
        result = run(program, times=times, stop=1, vabstol=1e-10, reltol=1e-10)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, t if t <= .5 else .5+.5*(t-.5), delta=1e-10)

    def test_event_dependent_derivative_input_does_not_drop_impulses(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(.5,0,1e-12)) q=1; "
            "V(z,r)<+V(u,r)+q; V(y,r)<+ddt(V(z,r));", "real q; electrical z;")
        with self.assertRaisesRegex(KernelError, "unsupported_operator"):
            run(program, times=[0, .5, 1], stop=1)

    def test_structural_cancelled_state_input_keeps_zero_integral(self):
        for expression in ["q-q", "0*q"]:
            program = compile_model(
                "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=2; "
                f"V(y,r)<+idt({expression},.25);", "integer q;")
            result = run(program, times=[0, .25, .5, 1], stop=1)
            for actual in values(result):
                assert_close(self, actual, .25, delta=1e-10)


class NonlinearIntegralContracts(unittest.TestCase):
    def test_quadratic_decay_has_rational_answer(self):
        # y'=-y^2, y(0)=1 => y=1/(1+t).
        program = compile_model("V(y,r)<+idt(-V(y,r)*V(y,r),1);")
        times = [0, .125, .5, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-10, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1+t), delta=1e-10)

    def test_logistic_feedback_has_closed_form(self):
        program = compile_model("V(y,r)<+idt(V(y,r)*(1-V(y,r)),.25);")
        times = [0, .25, .5, 1, 2, 4]
        result = run(program, times=times, stop=4, vabstol=1e-10, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1+3*math.exp(-t)), delta=1e-10)

    def test_coupled_integrals_share_one_nonlinear_state_system(self):
        # y=1/(1+t), q'=y^2 and q(0)=0 => q=1-y.
        program = compile_model("V(y,r)<+idt(-pow(V(y,r),2),1); V(q,r)<+idt(pow(V(y,r),2),0);",
                                ports="u,y,q,r", directions="input u; output y,q; inout r;")
        times = [0, .25, .5, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-10, reltol=0)
        for t, row in zip(times, rows(result)):
            assert_close(self, row["y"], 1/(1+t), delta=1e-10)
            assert_close(self, row["q"], t/(1+t), delta=1e-10)

    def test_nonlinear_input_source_and_relay_have_exact_integral(self):
        for expression, decl, prefix in [("pow(V(u,r),2)", "", ""),
                                        ("pow(V(z,r),2)", "electrical z;", "V(z,r)<+V(u,r);")]:
            program = compile_model(prefix+f"V(y,r)<+idt({expression},.25);", decl)
            times = [0, .25, .5, 1, 2]
            result = run(program, {"u": [[0, 0], [2, 2]]}, times, stop=2, vabstol=1e-10, reltol=0)
            for t, actual in zip(times, values(result)):
                assert_close(self, actual, .25+t**3/3, delta=1e-10)

    def test_nonlinear_trajectory_does_not_depend_on_observation_grid(self):
        program = compile_model("V(y,r)<+idt(-pow(V(y,r),2),1);")
        sparse = [0, .25, .5, 1, 2]
        dense = [i/16 for i in range(33)]
        first = values(run(program, times=sparse, stop=2, max_step=2, vabstol=1e-10, reltol=0))
        result = run(program, times=dense, stop=2, max_step=.125, vabstol=1e-10, reltol=0)
        for t, value in zip(sparse, first):
            self.assertEqual(value, values(result)[dense.index(t)])

    def test_finite_time_blowup_is_not_reported_as_valid_waveform(self):
        program = compile_model("V(y,r)<+idt(pow(V(y,r),2),1);")
        with self.assertRaises(KernelError):
            run(program, times=[0, .5, 1, 2], stop=2)

    def test_event_changes_nonlinear_coefficient_without_reinitializing_state(self):
        program = compile_model(
            "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=2; "
            "V(y,r)<+idt(-q*pow(V(y,r),2),1);", "integer q;")
        times=[0,.25,.5,.75,1,2]
        result=run(program,times=times,stop=2,vabstol=1e-10,reltol=0)
        for t,actual in zip(times,values(result)):
            expected=1/(1+t) if t<=.5 else 1/(1.5+2*(t-.5))
            assert_close(self,actual,expected,delta=1e-10)

    def test_nonlinear_joint_reset_clamps_then_resumes_with_original_ic(self):
        program=compile_model(
            "@(initial_step) rst=0; @(timer(.5,0,1e-12)) rst=1; "
            "@(timer(1,0,1e-12)) rst=0; V(y,r)<+idt(-pow(V(y,r),2),1,rst);", "integer rst;")
        times=[0,.25,.5,.75,1,1.25,2]
        result=run(program,times=times,stop=2,vabstol=1e-10,reltol=0)
        for t,actual in zip(times,values(result)):
            expected=1/(1+t) if t<.5 else 1 if t<=1 else 1/t
            assert_close(self,actual,expected,delta=1e-10)

    def test_nonlinear_history_enclosure_is_used_after_voltage_amplification(self):
        program=compile_model("V(z,r)<+idt(-pow(V(z,r),2),1); V(y,r)<+1e8*V(z,r);", "electrical z;")
        with self.assertRaisesRegex(KernelError,"waveform_accuracy"):
            run(program,times=[1],stop=1,vabstol=1e-12,reltol=0)
        result=run(program,times=[1],stop=1,vabstol=1e-4,reltol=0)
        assert_close(self,values(result)[0],5e7,delta=1e-4)

    def test_nonlinear_contribution_permutations_preserve_the_model(self):
        bodies=["V(y,r)<+.25; V(y,r)<+idt(-pow(V(y,r),2),.75);",
                "V(y,r)<+idt(-pow(V(y,r),2),.75); V(y,r)<+.25;"]
        baseline=None
        for body in bodies:
            result=run(compile_model(body),times=[0,.25,.5,1],stop=1,vabstol=1e-10,reltol=0)
            for t,value in zip([0,.25,.5,1],values(result)):
                assert_close(self,value,1/(1+t),delta=1e-10)
            if baseline is None: baseline=values(result)
            self.assertEqual(values(result),baseline)

    def test_nonlinear_integral_guard_uses_certified_trajectory(self):
        program=compile_model(
            "@(initial_step) n=0; @(cross(V(z,r)-.5,-1,1e-9,1e-8)) n=n+1; "
            "V(z,r)<+idt(-pow(V(z,r),2),1); V(y,r)<+n;", "integer n; electrical z;")
        result=run(program,times=[0,2],stop=2,vabstol=1e-8,reltol=1e-8)
        self.assertEqual(values(result),[0,1])
        events=result["transient"]["events"]
        self.assertEqual(len(events),1)
        self.assertAlmostEqual(events[0]["time"],1,delta=1e-9)

    def test_nonlinear_mixed_filter_network_is_explicitly_rejected(self):
        program = compile_model(
            "V(z,r)<+idt(-pow(V(z,r),2),1); "
            "V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1});", "electrical z;")
        with self.assertRaisesRegex(KernelError, "nonlinear continuous network currently requires"):
            run(program, times=[0, .5, 1], stop=1)

    def test_uncertain_nonlinear_restart_does_not_discard_event_time_error(self):
        program = compile_model(
            "@(initial_step) q=1; @(cross(V(u,r)-.1,1,1e-9,1e-8)) q=2; "
            "V(y,r)<+idt(-q*pow(V(y,r),2),1);", "integer q;")
        with self.assertRaisesRegex(KernelError, "nonlinear event restart requires an exactly certified event time"):
            run(program, {"u": [[0, 0], [1, 3]]}, [0, 1], stop=1)


if __name__ == "__main__":
    unittest.main()

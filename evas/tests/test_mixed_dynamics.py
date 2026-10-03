"""Independent closed forms for nonlinear integral / filter composition."""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["DYNAMICS", "NONLINEAR-TRANSIENT"]

import math
import unittest
from fractions import Fraction

from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class MixedDynamicsContracts(unittest.TestCase):
    def test_inactive_reset_preserves_integral_sample_at_uncertain_event(self):
        # tau=sqrt(2); q samples z(tau)=tau. Reset stays zero, so z is
        # continuous and its new slope is tau, irrespective of a reset argument.
        tau = math.sqrt(2)
        times = [0, .5, 1, 1.5, 2]
        for nonlinear in [False, True]:
            for reset in ["", ",rst"]:
                with self.subTest(nonlinear=nonlinear, reset=reset):
                    body = (
                        "@(initial_step) begin q=1; rst=0; end "
                        "@(cross(pow(V(u,r),2)-2,1,1e-5,1e-4)) q=V(z,r); "
                        f"V(z,r)<+idt(q,0{reset}); "
                        "V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1});"
                    )
                    if nonlinear:
                        body += "V(n,r)<+idt(pow(V(u,r),2),0);"
                    declarations = "real q; integer rst; electrical z;"
                    if nonlinear:
                        declarations += "electrical n;"
                    result = run(compile_model(body, declarations),
                                 {"u": [[0, 0], [2, 2]]}, times, stop=2,
                                 vabstol=1e-3, reltol=1e-3)
                    for t, row in zip(times, rows(result)):
                        z = t if t <= tau else tau + tau*(t-tau)
                        y = (t-1+math.exp(-t) if t <= tau else
                             tau*t-tau*tau+(tau-1)*math.exp(-(t-tau))+math.exp(-t))
                        assert_close(self, row["dut:z"], z, delta=1e-3)
                        assert_close(self, row["y"], y, delta=1e-3)

    def test_event_restart_uses_known_filter_history_for_nonlinear_feedback(self):
        # Initial q=0 gives the unique DC state z=y=1. After tau=1/4,
        # y'=(y-2)^2/4 with y(tau)=1, hence y=2-4/(4+t-tau).
        program = compile_model(
            "@(initial_step) q=0; @(timer(.25,0,1e-12)) q=.5; "
            "V(z,r)<+idt(pow(V(u,r),2),1); "
            "V(y,r)<+laplace_nd(pow(q*V(y,r),2)+V(z,r),'{1},'{1,1});",
            "real q; electrical z;")
        times = [0, .125, .25, .375, .5]
        result = run(program, times=times, stop=.5, vabstol=1e-10, reltol=0)
        for t, row in zip(times, rows(result)):
            expected = (Fraction(1) if t <= .25 else
                        2-Fraction(4)/(4+Fraction.from_float(t)-Fraction(1, 4)))
            assert_close(self, row["dut:z"], 1, delta=1e-10)
            assert_close(self, row["y"], float(expected), delta=1e-10)

    def test_nonlinear_integral_and_filter_feedback_are_solved_together(self):
        # z'=1+y-z^2; y'+y=z^2+2z, z(0)=y(0)=0.
        # Substitution proves the joint solution z=t, y=t^2.
        program = compile_model(
            "V(z,r)<+idt(1+V(y,r)-pow(V(z,r),2),0); "
            "V(y,r)<+laplace_nd(pow(V(z,r),2)+2*V(z,r),'{1},'{1,1});",
            "electrical z;")
        times = [0, .125, .5, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-10, reltol=0)
        for t, row in zip(times, rows(result)):
            assert_close(self, row["dut:z"], t, delta=1e-10)
            assert_close(self, row["y"], t*t, delta=1e-10)

    def test_nonlinear_integral_and_first_order_filter_share_physical_states(self):
        # z'=t^2, z(0)=0; y'+y=z, y(0)=0.
        program = compile_model(
            "V(z,r)<+idt(pow(V(u,r),2),0); "
            "V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1});", "electrical z;")
        times = [0, .125, .5, 1, 2]
        result = run(program, {"u": [[0,0],[2,2]]}, times, stop=2, vabstol=1e-10, reltol=0)
        for t, row in zip(times, rows(result)):
            assert_close(self, row["dut:z"], t**3/3, delta=1e-10)
            assert_close(self, row["y"], t**3/3-t*t+2*t-2+2*math.exp(-t), delta=1e-10)

    def test_second_order_filter_state_count_is_independent_of_call_site_order(self):
        integral = "V(z,r)<+idt(pow(V(u,r),2),0);"
        filtering = "V(y,r)<+laplace_nd(V(z,r),'{1},'{1,2,1});"
        times = [0, .25, .5, 1, 2]
        common = None
        for body in [integral+filtering, filtering+integral]:
            result = run(compile_model(body, "electrical z;"), {"u": [[0,0],[2,2]]}, times,
                         stop=2, vabstol=1e-10, reltol=0)
            for t, actual in zip(times, values(result)):
                expected = t**3/3-2*t*t+6*t-8+(8+2*t)*math.exp(-t)
                assert_close(self, actual, expected, delta=1e-10)
            if common is None:
                common = values(result)
            else:
                for a, b in zip(common, values(result)):
                    assert_close(self, a, b, delta=1e-12)

    def test_filter_direct_feedthrough_and_dc_preserve_integral_ic(self):
        # z=3+t^3/3. H=(1+s)/(1+2s) => y=.5*z+.5*lowpass_tau2(z).
        program = compile_model(
            "V(z,r)<+idt(pow(V(u,r),2),3); "
            "V(y,r)<+laplace_nd(V(z,r),'{1,1},'{1,2});", "electrical z;")
        times = [0, .25, .5, 1, 2]
        result = run(program, {"u": [[0,0],[2,2]]}, times, stop=2, vabstol=1e-10, reltol=0)
        for t, actual in zip(times, values(result)):
            expected = 3+t**3/3-t*t+4*t-8+8*math.exp(-t/2)
            assert_close(self, actual, expected, delta=1e-10)

    def test_reset_preserves_filter_history_and_does_not_reinitialize_dc(self):
        # z'=1 while not reset. Include a genuinely nonlinear (zero-valued)
        # separate integrator so the common network uses polynomial propagation.
        program = compile_model(
            "@(initial_step) rst=0; @(timer(.5,0,1e-12)) rst=1; "
            "V(z,r)<+idt(1,0,rst); V(n,r)<+idt(pow(V(u,r),2),0); "
            "V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1});", "integer rst; electrical z,n;")
        times = [0,.25,.5,.75,1]
        result = run(program, times=times, stop=1, vabstol=1e-10, reltol=0)
        at_reset = .5-1+math.exp(-.5)
        for t, actual in zip(times, values(result)):
            expected = t-1+math.exp(-t) if t<.5 else at_reset*math.exp(-(t-.5))
            assert_close(self, actual, expected, delta=1e-10)

    def test_mixed_history_is_grid_independent_and_propagates_precision(self):
        program = compile_model(
            "V(z,r)<+idt(pow(V(u,r),2),0); V(y,r)<+laplace_nd(V(z,r),'{1},'{1,1});", "electrical z;")
        times = [0,.25,.5,1,2]
        first = values(run(program, {"u": [[0,0],[2,2]]}, times, stop=2, vabstol=1e-10, reltol=0))
        dense = [i/16 for i in range(33)]
        second = values(run(program, {"u": [[0,0],[2,2]]}, dense, stop=2, max_step=.125,
                            vabstol=1e-10, reltol=0))
        self.assertEqual(first, [second[dense.index(t)] for t in times])
        with self.assertRaisesRegex(KernelError, "waveform_accuracy"):
            run(program, {"u": [[0,0],[2,2]]}, times, stop=2, vabstol=1e-20, reltol=0)

    def test_strictly_proper_filter_accepts_polynomial_source_input(self):
        # y'+y=t^2; zero DC => y=t^2-2t+2-2exp(-t).
        program=compile_model("V(y,r)<+laplace_nd(pow(V(u,r),2),'{1},'{1,1});")
        times=[0,.125,.5,1,2]
        result=run(program,{"u":[[0,0],[2,2]]},times,stop=2,vabstol=1e-10,reltol=0)
        for t,actual in zip(times,values(result)):
            assert_close(self,actual,t*t-2*t+2-2*math.exp(-t),delta=1e-10)

    def test_filter_polynomial_input_uses_integral_ic_for_its_dc_state(self):
        # z=1+t, input=z^2+2z = (1+t)^2 + derivative((1+t)^2).
        # DC filter initial is input(0)=3, so y=(1+t)^2+2exp(-t).
        program=compile_model("V(z,r)<+idt(1,1); V(y,r)<+laplace_nd(pow(V(z,r),2)+2*V(z,r),'{1},'{1,1});", "electrical z;")
        times=[0,.125,.5,1]
        result=run(program,times=times,stop=1,vabstol=1e-10,reltol=0)
        for t,actual in zip(times,values(result)):
            assert_close(self,actual,(1+t)**2+2*math.exp(-t),delta=1e-10)

    def test_nonlinear_filter_dc_feedback_and_feedthrough_are_explicitly_rejected(self):
        for body in [
            "V(y,r)<+laplace_nd(pow(V(y,r),2)+1,'{1},'{1,1});",
            "V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{1,2});",
        ]:
            with self.subTest(body=body),self.assertRaisesRegex(KernelError,"unsupported_operator"):
                run(compile_model(body),times=[0,.5,1],stop=1)

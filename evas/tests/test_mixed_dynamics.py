"""Independent closed forms for nonlinear integral / filter composition."""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS", "LAPLACE", "COMPOSE"]

import math
import unittest
from fractions import Fraction

from evas.runtime import KernelError
from test_continuous_dynamics import compile_model, run, rows, values, assert_close


class MixedDynamicsContracts(unittest.TestCase):
    def test_nonlinear_filter_cold_root_and_event_reset_preserve_history(self):
        # Cold y=.75+.25y^2 selects the regular local root y=1.
        # At e=.25, removing the quadratic term gives y'=.75-y,
        # hence y=.75+.25*exp(-(t-e)); restarting DC would jump to .75.
        # Only z is reset, held at its explicit IC until release at .5.
        program=compile_model(
            '@(initial_step) begin q=0.25; rst=0; end '
            '@(timer(0.25,0,1e-12)) begin q=0; rst=1; end '
            '@(timer(0.5,0,1e-12)) rst=0; '
            "V(y,r)<+laplace_nd(0.75+q*pow(V(y,r),2),'{1},'{1,1}); "
            'V(z,r)<+idt(1,2,rst);','real q; integer rst; electrical z;')
        sparse=[0,.125,.25,.375,.5,.75,1]
        first=run(program,times=sparse,max_step=.0625,vabstol=1e-9,reltol=0)
        dense=[i/16 for i in range(17)]
        second=run(program,times=dense,max_step=.0625,vabstol=1e-9,reltol=0)
        self.assertEqual(values(first),[values(second)[dense.index(t)] for t in sparse])
        for t,row in zip(sparse,rows(first)):
            y=1 if t<=.25 else .75+.25*math.exp(-(t-.25))
            z=2+t if t<.25 else 2 if t<=.5 else 2+t-.5
            assert_close(self,row['y'],y,delta=1e-9)
            assert_close(self,row['dut:z'],z,delta=1e-9)

    def test_nonlinear_filter_cold_root_cannot_skip_voltage_accuracy(self):
        program=compile_model("V(y,r)<+laplace_nd(0.75+0.25*pow(V(y,r),2),'{1},'{1,1});")
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(program,times=[0,.5,1],vabstol=1e-20,reltol=0)

    def test_singular_nonlinear_filter_cold_root_is_rejected(self):
        # DC implies (y-.5)^2=0, so no regular isolated-root proof.
        program=compile_model("V(y,r)<+laplace_nd(0.25+pow(V(y,r),2),'{1},'{1,1});")
        with self.assertRaises(KernelError):
            run(program,times=[0,.5,1],vabstol=1e-9,reltol=0)

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
            "@(initial_step) q=0; @(timer(0.25,0,1e-12)) q=0.5; "
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
            "@(initial_step) rst=0; @(timer(0.5,0,1e-12)) rst=1; "
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

    def test_no_real_filter_dc_root_and_nonlinear_feedthrough_are_rejected(self):
        for body,reason in [
            # y^2-y+1 has discriminant -3: support for nonlinear DC
            # must not manufacture a real initial root for this model.
            ("V(y,r)<+laplace_nd(pow(V(y,r),2)+1,'{1},'{1,1});",
             "continuous DC initialization"),
            ("V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{1,2});",
             "strictly proper"),
        ]:
            with self.subTest(body=body),self.assertRaisesRegex(KernelError,reason):
                run(compile_model(body),times=[0,.5,1],stop=1)

"""Known-event horizons, checked against independent piecewise IVP answers."""

# Guarded conditions/capabilities: see docs/PROCESS.md and docs/TRACEABILITY.md
GUARDS = ["DYNAMICS"]

from fractions import Fraction
import math
import unittest

from test_continuous_dynamics import compile_model, run, values, assert_close


class KnownEventHorizonContracts(unittest.TestCase):
    def test_timer_stabilizes_quadratic_growth_before_predicted_blowup(self):
        # Before e=1/2: y'=y^2, y(0)=1 => y=1/(1-t).
        # Afterwards q=-1: y'=-y^2, y(e)=2 => y=1/t.
        program = compile_model(
            "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [0, .125, .25, .5, .75, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            expected = 1/(1-t) if t <= .5 else 1/t
            assert_close(self, actual, expected, delta=1e-9)
        self.assertEqual([e["time"] for e in result["transient"]["events"]], [.5])

    def test_noop_timer_extends_existing_history_before_later_change(self):
        # A same-value assignment at 1/4 still ends a prediction horizon.
        program = compile_model(
            "@(initial_step) q=1; @(timer(.25,0,1e-12)) q=1; "
            "@(timer(.5,0,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [0, .25, .375, .5, .75, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1-t) if t <= .5 else 1/t, delta=1e-9)
        self.assertEqual([e["time"] for e in result["transient"]["events"]], [.25, .5])

    def test_zero_time_event_precedes_future_propagation(self):
        # q=1 at initial_step would blow up. timer(0) sets decay before t>0.
        program = compile_model(
            "@(initial_step) q=1; @(timer(0,0,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [0, .25, .5, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1+t), delta=1e-9)
        self.assertEqual([e["time"] for e in result["transient"]["events"]], [0])

    def test_affine_input_cross_can_bound_a_nonlinear_network(self):
        program = compile_model(
            "@(initial_step) q=1; @(cross(V(u,r)-.5,1,1e-12,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [0, .25, .5, 1, 2]
        result = run(program, {"u": [[0, 0], [2, 2]]}, times, stop=2,
                     vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1-t) if t <= .5 else 1/t, delta=1e-9)

    def test_prediction_horizons_do_not_depend_on_output_grid_or_max_step(self):
        program = compile_model(
            "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        common = [0, .25, .5, 1, 2]
        sparse = run(program, times=common, stop=2, max_step=2,
                     vabstol=1e-9, reltol=0)
        dense_times = [i/16 for i in range(33)]
        dense = run(program, times=dense_times, stop=2, max_step=.0625,
                    vabstol=1e-9, reltol=0)
        self.assertEqual(values(sparse), [values(dense)[dense_times.index(t)] for t in common])
        self.assertEqual(sparse["transient"]["events"], dense["transient"]["events"])

    def test_periodic_mode_changes_preserve_one_physical_history(self):
        # 1/y=1-integral(q). q flips every 1/4, so the denominator
        # alternates linearly between 1 and 3/4 without a singularity.
        program = compile_model(
            "@(initial_step) q=1; @(timer(.25,.25,1e-12)) q=-q; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [i/16 for i in range(33)]
        result = run(program, times=times, stop=2, vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            n = int(t/.25)
            elapsed = Fraction.from_float(t)-Fraction(n,4)
            area = (Fraction(1,4) if n % 2 else Fraction(0)) + (-1 if n % 2 else 1)*elapsed
            assert_close(self, actual, float(1/(1-area)), delta=1e-9)
        self.assertEqual([e["time"] for e in result["transient"]["events"]],
                         [i/4 for i in range(1,9)])

    def test_nonpoint_source_cross_preserves_root_window_error(self):
        # tau=1/3; after the sign change y=1/(1+t-2*tau).
        program = compile_model(
            "@(initial_step) q=1; @(cross(3*V(u,r)-1,1,1e-10,1e-10)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1);", "integer q;")
        times = [0, .25, .5, 1, 2]
        result = run(program, {"u": [[0, 0], [2, 2]]}, times, stop=2,
                     vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            t_exact = Fraction.from_float(t)
            expected = 1/(1-t_exact) if t < 1/3 else 1/(t_exact+Fraction(1,3))
            assert_close(self, actual, float(expected), delta=1e-9)
        event = result["transient"]["events"][0]
        lo, hi = event["observation_time_bounds"]
        self.assertLess(lo, hi)
        self.assertLessEqual(Fraction.from_float(lo), Fraction(1,3))
        self.assertGreaterEqual(Fraction.from_float(hi), Fraction(1,3))

    def test_mixed_filter_state_survives_prediction_horizon_changes(self):
        # The independent ramp lowpass remains t-1+exp(-t) across
        # the nonlinear integrator's mode changes.
        program = compile_model(
            "@(initial_step) q=1; @(timer(.5,0,1e-12)) q=-1; "
            "V(y,r)<+idt(q*pow(V(y,r),2),1); "
            "V(f,r)<+laplace_nd(V(u,r),'{1},'{1,1});",
            "integer q;", ports="u,y,f,r", directions="input u; output y,f; inout r;")
        times = [0, .25, .5, 1, 2]
        result = run(program, {"u": [[0, 0], [2, 2]]}, times, stop=2,
                     vabstol=1e-9, reltol=0)
        for t, y, f in zip(times, values(result), values(result, "f")):
            assert_close(self, y, 1/(1-t) if t <= .5 else 1/t, delta=1e-9)
            assert_close(self, f, t-1+math.exp(-t), delta=1e-9)

    def test_unrelated_event_extends_event_independent_nonlinear_history(self):
        program = compile_model(
            "@(initial_step) n=0; @(timer(.25,.25,1e-12)) n=n+1; "
            "V(y,r)<+idt(-pow(V(y,r),2),1);", "integer n;")
        times = [0, .25, .5, 1, 2]
        result = run(program, times=times, stop=2, vabstol=1e-9, reltol=0)
        for t, actual in zip(times, values(result)):
            assert_close(self, actual, 1/(1+t), delta=1e-9)
        self.assertEqual(result["transient"]["states"][-1], [8])

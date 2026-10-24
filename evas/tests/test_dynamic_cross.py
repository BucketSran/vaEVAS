"""Independent roots: a parabola has two roots; an integral has sqrt roots.

A timer or external PWL can reverse the flow away from a cross, so the return
root has its own closed form. A product guard that flips its own slope inside
the consumed root window does not.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["CROSS", "EVENT-CONDITIONS", "DYNAMICS"]

import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model
from initial_record_contract import check_initial_record_batch


def run_guard(guard, *, extra="", points=None, times=None, step=4, direction=0):
    source = model(f"""
      @(initial_step) n=0;
      @(cross({guard},{direction},1e-9,1e-8)) n=n+1;
      {extra}
      V(y,r)<+n;
    """, "integer n;" + (" electrical z;" if extra else ""))
    program = compile_sources({"guard.va": source}, [instance()])
    points = points or [[0, 0], [2, 2]]
    result = transient(program, {"u": points}, times or [0, 2],
                     stop=points[-1][0], max_step=step, kernel=KERNEL)
    return check_initial_record_batch(result,program,[0],[0],1)


# The rejection names the window, the flow reversal, and why the return root
# has no separate identity. Query phase is a different refusal: the sample
# lands inside a root box.
CONSUMED_ROOT_WINDOW = (
    "bidirectional history cross reverses its own flow inside the consumed root window; "
    "return crossing cannot be distinguished from root uncertainty")
QUERY_PHASE = "output query cannot certify its physical event phase"
OVERLAPPING_BOUNDS = (
    "cannot certify ordering of distinct events with overlapping time bounds")


def root_box(case, event, exact, ttol):
    # Representative time is the upper end of the root box: not earlier than
    # the closed-form root, and not later by more than this cross's own ttol.
    bounds = event.get("observation_time_bounds", [event["time"], event["time"]])
    case.assertEqual(event["kind"], "cross")
    case.assertEqual(event["time"], bounds[1])
    case.assertLessEqual(bounds[0], exact)
    case.assertGreaterEqual(bounds[1], exact)
    case.assertLessEqual(bounds[1] - exact, ttol)


def run_cross(body, declarations, *, stop, times, step, control, before, after):
    program = compile_sources({"guard.va": model(body, declarations)}, [instance()])
    result = transient(program, {"u": control}, times, stop=stop, max_step=step,
                       kernel=KERNEL, vabstol=1e-8, reltol=0)
    return check_initial_record_batch(result, program, before, after, 1)


def voltage(result, node):
    return result["solutions"][-1]["voltages"][result["nodes"].index(node)]


def timer_reversal_body(slope, tau, threshold=0.5, ttol="1e-9", vtol="1e-8"):
    # z = slope*t until tau, then z = slope*(2*tau-t). Thresholds ±threshold.
    return f"""@(initial_step) begin slope={slope}; n=0; end
      @(timer({tau:.17g},0,1e-12)) slope={-slope};
      V(z,r)<+idt(slope,0);
      @(cross((V(z,r)-{threshold})*(V(z,r)+{threshold}),0,{ttol},{vtol})) n=n+1;
      V(y,r)<+n;"""


def pwl_reversal_body(threshold=0.5, ttol="1e-9", vtol="1e-8"):
    return f"""@(initial_step) n=0;
      V(z,r)<+V(u,r);
      @(cross((V(z,r)-{threshold})*(V(z,r)+{threshold}),0,{ttol},{vtol})) n=n+1;
      V(y,r)<+n;"""


def triangle(tau, stop):
    return [[0, 0], [tau, tau], [stop, 2 * tau - stop]]


class DynamicCrossContracts(unittest.TestCase):
    def test_same_sign_segment_endpoints_do_not_hide_two_roots(self):
        result = run_guard("(V(u,r)-0.5)*(V(u,r)-1.5)")
        events = result["transient"]["events"]
        self.assertEqual(len(events), 2)
        for event, exact in zip(events, [.5, 1.5]):
            self.assertGreaterEqual(event["time"], exact)
            self.assertLessEqual(event["time"] - exact, 1e-9)
        self.assertEqual(result["transient"]["states"][-1], [2])

    def test_nonlinear_direction_and_grid_invariance(self):
        a = run_guard("pow(V(u,r),2)-0.5", direction=1)
        b = run_guard("pow(V(u,r),2)-0.5", direction=1,
                      times=[0, .1, .3, 1, 2], step=.17)
        self.assertEqual(a["transient"]["events"], b["transient"]["events"])
        time = a["transient"]["events"][0]["time"]
        self.assertGreaterEqual(time, math.sqrt(.5))
        self.assertLessEqual(time - math.sqrt(.5), 1e-9)
        self.assertEqual(run_guard("pow(V(u,r),2)-0.5", direction=-1)
                         ["transient"]["events"], [])

    def test_operator_driven_voltage_guard(self):
        result = run_guard("V(z,r)-0.5", extra="V(z,r)<+idt(V(u,r),0);")
        time = result["transient"]["events"][0]["time"]
        self.assertGreaterEqual(time, 1)
        self.assertLessEqual(time - 1, 1e-9)

    def test_operator_call_in_guard_has_its_own_identity(self):
        result = run_guard("idt(V(u,r),0)-0.5")
        self.assertAlmostEqual(result["transient"]["events"][0]["time"], 1, delta=1e-9)

    def test_endpoint_root_does_not_hide_an_earlier_root(self):
        result = run_guard("(V(u,r)-0.5)*(V(u,r)-2)")
        self.assertEqual(len(result["transient"]["events"]), 2)
        for event, root in zip(result["transient"]["events"], [.5, 2]):
            self.assertAlmostEqual(event["time"], root, delta=1e-9)

    def test_directed_integral_reversal_at_exact_stop_preserves_query_phase(self):
        # z'=sign/2, z(0)=0: the increasing arrival is at 1 and the
        # decreasing arrival is at stop=3. Both roots are exact binary64
        # values even when the prediction interval uses non-dyadic splits.
        source = model("""
          @(initial_step) begin sign=1; n=0; end
          V(z,r)<+idt(0.5*sign*V(u,r),0);
          @(cross(V(z,r)-0.5,1,1e-10,1e-10) or
            cross(V(z,r)+0.5,-1,1e-10,1e-10)) begin
            sign=-sign; n=n+1;
          end
          V(y,r)<+n;
        """, "real sign; integer n; electrical z;")
        program = compile_sources({"endpoint.va": source}, [instance()])
        before_stop = math.nextafter(3.0, -math.inf)
        baseline = None
        for times in ([0, 1, 2, before_stop, 3],
                      [0, .333, .77, 1, 1.77, 2, 2.9, before_stop, 3]):
            result = transient(program, {"u": [[0, 1], [3, 1]]}, times,
                               stop=3, max_step=.005, vabstol=1e-8,
                               reltol=0, kernel=KERNEL)
            result = check_initial_record_batch(result,program,[0,0],[1,0],1)
            events = result["transient"]["events"]
            self.assertEqual([event["time"] for event in events], [1, 3])
            if baseline is not None:
                self.assertEqual(events, baseline)
            baseline = events
            y = result["nodes"].index("y")
            self.assertEqual([row["voltages"][y]
                              for row in result["solutions"]],
                             [int(time >= 1) + int(time >= 3) for time in times])
            self.assertEqual(result["transient"]["states"][-1], [1, 2])

    def test_sine_guard_uses_a_continuous_certified_operator_trajectory(self):
        result = run_guard("sin(V(u,r))-0.5")
        events = result["transient"]["events"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["time"], math.pi/6, delta=1e-9)

    def test_integral_feedback_guard_has_logarithmic_root(self):
        result = run_guard("pow(V(z,r),2)-0.25",
                           extra="V(z,r)<+idt(1-V(z,r),0);", direction=1)
        events = result["transient"]["events"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["time"], math.log(2), delta=1e-9)

    def test_strictly_proper_filter_of_ddt_has_continuous_guard(self):
        # u=t gives ddt(u)=1 for t>0; 1/(1+s) with DC state zero
        # produces z=1-exp(-t), which crosses .5 at log(2).
        result = run_guard("V(z,r)-0.5",
                           extra="V(z,r)<+laplace_nd(ddt(V(u,r)),'{1},'{1,1});", direction=1)
        events = result["transient"]["events"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["time"], math.log(2), delta=1e-9)

    def test_ddt_feedthrough_cannot_be_hidden_in_a_continuous_guard(self):
        # The guard stays positive, so this tests preflight continuity rather
        # than letting root search happen to reject a particular jump.
        with self.assertRaisesRegex(KernelError, "unsupported_cross"):
            run_guard("laplace_nd(ddt(V(u,r)),'{1,1},'{1,1})+0.5")

    def test_guard_only_operator_with_state_dependent_relay_uses_epoch_history(self):
        source = model("""
          @(initial_step) n=0;
          @(cross(idt(V(z,r),0)-0.5,1,1e-9,1e-8)) n=n+1;
          V(z,r)<+V(u,r)+0*n;
          V(y,r)<+n;
        """, "integer n; electrical z;")
        program = compile_sources({"guard-only.va": source}, [instance()])
        result = transient(program, {"u": [[0, 0], [2, 2]]}, [0, 2],
                           stop=2, max_step=2, kernel=KERNEL)
        result = check_initial_record_batch(result,program,[0],[0],1)
        events = result['transient']['events']
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]['time'], 1, delta=1e-9)

    def test_uncertifiable_tangent_fails_explicitly(self):
        with self.assertRaisesRegex(KernelError, "event_resolution"):
            run_guard("pow(V(u,r)-1,2)")

    def assert_timer_return(self, slope, tau, stop, roots, *, step, threshold=0.5,
                            ttol_text="1e-9", ttol=1e-9):
        # Hand answer: crossings at the threshold on the way out and at
        # 2*tau - threshold/|slope| on the way back. Stop is past the return.
        result = run_cross(
            timer_reversal_body(slope, tau, threshold, ttol_text),
            "real slope; integer n; electrical z;",
            stop=stop, times=[0, stop], step=step, control=[[0, 0], [stop, stop]],
            before=[0, 0], after=[slope, 0])
        events = result["transient"]["events"]
        self.assertEqual([event["kind"] for event in events], ["cross", "timer", "cross"])
        self.assertEqual(events[1]["time"], tau)
        self.assertEqual(events[0]["before"][0], slope)
        self.assertEqual(events[1]["after"][0], -slope)
        self.assertEqual(events[2]["before"][0], -slope)
        for event, exact in zip((events[0], events[2]), roots):
            root_box(self, event, exact, ttol)
        self.assertEqual(result["transient"]["states"][-1], [-slope, 2])
        self.assertAlmostEqual(voltage(result, "dut:z"), slope * (2 * tau - stop), delta=1e-8)
        self.assertEqual(voltage(result, "y"), 2)
        return result

    def test_timer_reversal_keeps_distinguishable_return_roots(self):
        # tau=0.75, both initial slopes. Roots 0.5 and 1.0. Endpoints are ±0.3.
        for slope in (1, -1):
            with self.subTest(slope=slope):
                self.assert_timer_return(
                    slope, 0.75, 1.2, (0.5, 1.0), step=0.05)

        # Roots 0.5 and 0.500002 stay distinct.
        tau = 0.500001
        with self.subTest(tau=tau):
            self.assert_timer_return(
                1, tau, 0.500004, (0.5, 2 * tau - 0.5), step=0.002)

        # One nanosecond between the roots is not deleted.
        tau = 0.5000000005
        with self.subTest(tau=tau):
            roots = (0.5, 2 * tau - 0.5)
            self.assertAlmostEqual(roots[1] - roots[0], 1e-9, delta=1e-15)
            self.assert_timer_return(1, tau, 0.50000006, roots, step=0.002)

    def test_timer_return_closer_than_ttol_is_kept(self):
        # ttol stays 1e-9. For the smaller delays the return root is less than
        # ttol after the first root, and both representatives are kept.
        ttol = 1e-9
        for delta in (1e-10, 2e-10, 5e-10, 1e-9):
            with self.subTest(delta=delta):
                tau = 0.5 + delta
                roots = (0.5, 2 * tau - 0.5)
                stop = 0.5 + max(1e-6, 8 * delta)
                result = self.assert_timer_return(1, tau, stop, roots, step=0.25)
                crosses = [event for event in result["transient"]["events"]
                           if event["kind"] == "cross"]
                self.assertEqual(len(crosses), 2)
                if roots[1] - roots[0] < ttol:
                    self.assertLess(crosses[1]["time"] - crosses[0]["time"], ttol)

    def test_nonexact_timer_threshold_keeps_both_roots(self):
        # Threshold 0.3 is not a dyadic. Rising root 0.3, return 2*0.8-0.3=1.3.
        tau, threshold, stop = 0.8, 0.3, 1.5
        self.assertEqual(2 * tau - threshold, 1.3)
        self.assert_timer_return(
            1, tau, stop, (threshold, 2 * tau - threshold),
            step=0.05, threshold=threshold)

    def test_pwl_reversal_keeps_distinguishable_return_roots(self):
        # External triangle, same closed form. Cross only counts.
        for tau, stop in ((0.75, 1.2), (0.500001, 0.500004)):
            with self.subTest(tau=tau):
                roots = (0.5, 2 * tau - 0.5)
                result = run_cross(
                    pwl_reversal_body(), "integer n; electrical z;",
                    stop=stop, times=[0, stop], step=0.05 if tau == 0.75 else 0.002,
                    control=triangle(tau, stop), before=[0], after=[0])
                events = result["transient"]["events"]
                self.assertEqual([event["kind"] for event in events], ["cross", "cross"])
                for event, exact in zip(events, roots):
                    root_box(self, event, exact, 1e-9)
                self.assertEqual(result["transient"]["states"][-1], [2])
                self.assertAlmostEqual(voltage(result, "dut:z"), 2 * tau - stop, delta=1e-8)

    def test_pwl_overlapping_bounds_reject_until_ttol_is_tightened(self):
        # Roots 1 ns apart. ttol=1e-9 leaves the time bounds overlapping.
        # Tightening ttol to 1e-11, not loosening it, separates them.
        # vtol stays 1e-8.
        tau, stop = 0.5000000005, 0.50000006
        roots = (0.5, 2 * tau - 0.5)
        control = triangle(tau, stop)
        with self.assertRaises(KernelError) as caught:
            run_cross(pwl_reversal_body(), "integer n; electrical z;",
                      stop=stop, times=[0, stop], step=0.002, control=control,
                      before=[0], after=[0])
        self.assertEqual(caught.exception.detail["kind"], "event_resolution")
        self.assertEqual(caught.exception.detail["message"], OVERLAPPING_BOUNDS)

        result = run_cross(
            pwl_reversal_body(ttol="1e-11"), "integer n; electrical z;",
            stop=stop, times=[0, stop], step=0.002, control=control,
            before=[0], after=[0])
        events = result["transient"]["events"]
        self.assertEqual(len(events), 2)
        for event, exact in zip(events, roots):
            root_box(self, event, exact, 1e-11)

    def test_safe_query_grids_share_the_return_root_record(self):
        # Grids that miss both root boxes keep one event record. A sample
        # exactly at the return root 1.0 stays in that box and is refused.
        body = timer_reversal_body(1, 0.75)
        declarations = "real slope; integer n; electrical z;"
        records = []
        for times in ([0, 1.2], [0, 0.25, 0.9, 1.2]):
            with self.subTest(times=times):
                result = run_cross(
                    body, declarations, stop=1.2, times=times, step=0.05,
                    control=[[0, 0], [1.2, 1.2]], before=[0, 0], after=[1, 0])
                events = result["transient"]["events"]
                self.assertEqual([event["kind"] for event in events],
                                 ["cross", "timer", "cross"])
                root_box(self, events[0], 0.5, 1e-9)
                root_box(self, events[2], 1.0, 1e-9)
                self.assertAlmostEqual(voltage(result, "dut:z"), 0.3, delta=1e-8)
                records.append(events)
        self.assertEqual(records[0], records[1])
        with self.assertRaises(KernelError) as caught:
            run_cross(body, declarations, stop=1.2, times=[0, 1.0, 1.2], step=0.05,
                      control=[[0, 0], [1.2, 1.2]], before=[0, 0], after=[1, 0])
        self.assertEqual(caught.exception.detail["kind"], "event_resolution")
        self.assertEqual(caught.exception.detail["message"], QUERY_PHASE)

    def test_product_guard_self_reversal_rejects_indistinguishable_history(self):
        # Direction 0, ttol=1e-9, vtol=1e-8, stop=2, max_step=0.05.
        # The event body is slope=-slope. None of the eight runs is a waveform.
        # Dense i/100 includes 0.5 and does not include the ±3 root at 1/6.
        # ±1 on that grid hits the root window first (query phase). The other
        # six refuse the return inside the consumed window.
        dense = [i / 100 for i in range(201)]
        self.assertEqual(dense[50], 0.5)
        self.assertNotIn(1 / 6, dense)
        stop = 2
        for slope in (1, -1, 3, -3):
            body = f"""@(initial_step) begin slope={slope}; n=0; end
              V(z,r)<+idt(slope,0);
              @(cross((V(z,r)-0.5)*(V(z,r)+0.5),0,1e-9,1e-8)) begin
                slope=-slope; n=n+1;
              end
              V(y,r)<+n;"""
            program = compile_sources(
                {"guard.va": model(body, "real slope; integer n; electrical z;")},
                [instance()])
            for grid, times in (("sparse", [0, stop]), ("dense", dense)):
                kind = ("event_resolution" if grid == "dense" and abs(slope) == 1
                        else "unsupported_cross")
                message = QUERY_PHASE if kind == "event_resolution" else CONSUMED_ROOT_WINDOW
                with self.subTest(slope=slope, grid=grid):
                    with self.assertRaises(KernelError) as caught:
                        transient(program, {"u": [[0, 0], [stop, stop]]}, times,
                                  stop=stop, max_step=0.05, kernel=KERNEL,
                                  vabstol=1e-8, reltol=0)
                    self.assertEqual(caught.exception.detail["kind"], kind)
                    self.assertEqual(caught.exception.detail["message"], message)


if __name__ == "__main__":
    unittest.main()

"""Initial observations stop old-flow prediction at certified future events.

The scalar ODE answers follow by integrating dz/z**2 or dz/z. An isolated
observer's initial display and held timer do not change either physical ODE.
"""
GUARDS = ["LANG", "TIMER", "EVENT-ORDER", "COMPOSE", "DYNAMICS"]

import math
import os
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, transient
from test_affine import KERNEL as DEFAULT_KERNEL

KERNEL = Path(os.environ.get("EVAS_INITIAL_OBSERVER_KERNEL", DEFAULT_KERNEL))
TIMES = [0., 0.25, 0.5, 1., 2.]
DENSE = [0., 0.125, 0.25, 0.375, 0.5, 0.75, 1., 1.5, 2.]


def program(*, nonlinear=True, initial=1., due=None, physical_display=False,
            observer_step=""):
    rate = "q*V(z)*V(z)" if nonlinear else "q*V(z)"
    display = '@(initial_step)$display("initial=%g",V(z));'
    physical = display if physical_display else ""
    text = f'''`include "disciplines.vams"
module physical(z);
    output z; electrical z; real q;
    analog begin
        @(initial_step)q=1;
        @(timer(0.5))q=-1;
        V(z)<+idt({rate},{initial});
        {physical}
    end
endmodule
'''
    instances = [Instance("physical", "physical", {"z": "z"})]
    if not physical_display:
        timer = "" if due is None else '''
        @(timer(due))begin
            count=count+1;$display("observer_timer=%d",count);
        end'''
        assignment = "" if due is None else f"due={due};"
        text += f'''module observer(z);
    input z; electrical z; real due; integer count;
    analog begin
        @(initial_step)begin
            $display("initial=%g",V(z));{assignment}
        end
        {timer}
        {observer_step}
    end
endmodule
'''
        instances.append(Instance("observer", "observer", {"z": "z"}))
    return compile_sources({"initial_observer_horizon.va": text}, instances)


def execute(p, *, times=TIMES, forced=False):
    return transient(p, {}, times, stop=2., max_step=0.05,
                     vabstol=1e-9, reltol=1e-6,
                     strobetimes=times if forced else [],
                     kernel=KERNEL, timeout=30.)


def answer(time, initial, nonlinear):
    # Before .5 the integrated positive rate is t; afterwards its net
    # integral is 1-t. No solver-produced answer enters this oracle.
    integral = time if time <= 0.5 else 1.-time
    return 1./(1./initial-integral) if nonlinear else initial*math.exp(integral)


class InitialObserverHorizon(unittest.TestCase):
    def assert_curve(self, result, times, *, initial, nonlinear):
        column = result["nodes"].index("z")
        self.assertEqual(result["transient"]["times"], times)
        for time, row in zip(times, result["solutions"]):
            self.assertAlmostEqual(row["voltages"][column],
                                   answer(time, initial, nonlinear), delta=1e-8)
            self.assertLessEqual(row["max_residual_ratio"], 1.)
        physical = [event for event in result["transient"]["events"]
                    if event["origin"].endswith("(physical)")]
        self.assertEqual([(e["time"], e["kind"]) for e in physical],
                         [(0.5, "timer")])
        state = result["transient"]["state_names"].index("physical:q")
        self.assertEqual((physical[0]["before"][state], physical[0]["after"][state]),
                         (1., -1.))

    def assert_observer(self, result, *, initial, timer_time=None):
        records = result["transient"]["display_records"]
        expected = [(0., f"initial={initial:g}")]
        if timer_time is not None:
            expected.append((timer_time, "observer_timer=1"))
        self.assertEqual([(r["time"], r["text"]) for r in records], expected)
        events = [e for e in result["transient"]["events"]
                  if e["origin"].endswith("(observer)")]
        self.assertEqual(len(events), len(expected))
        self.assertEqual(events[0]["kind"], "initial_step")
        if timer_time is not None:
            self.assertEqual(events[1]["time"], timer_time)
            self.assertIn(events[1]["kind"], ("timer", "held_timer"))

    def test_initial_observation_does_not_predict_riccati_past_fixed_timer(self):
        # Old q=1 would blow up at t=1; the actual .5 timer makes z=1/t.
        result = execute(program())
        self.assert_curve(result, TIMES, initial=1., nonlinear=True)
        self.assert_observer(result, initial=1.)

    def test_riccati_observation_is_stable_on_forced_and_dense_output_grids(self):
        p = program()
        for times, forced in [(TIMES, True), (DENSE, False)]:
            with self.subTest(forced=forced):
                result = execute(p, times=times, forced=forced)
                self.assert_curve(result, times, initial=1., nonlinear=True)
                self.assert_observer(result, initial=1.)

    def test_initial_held_due_rebuilds_calendar_then_extends_history(self):
        # due's default 0 is replaced by a future callback or a disabled
        # far-future time, or retained as the one ordinary zero-time callback.
        for nonlinear in [False, True]:
            for due, timer_time in [("0.25", 0.25), ("1e30", None), ("0", 0.)]:
                p = program(nonlinear=nonlinear, initial=0.25, due=due)
                for times, forced in [(TIMES, False), (TIMES, True), (DENSE, False)]:
                    with self.subTest(nonlinear=nonlinear, due=due,
                                      times=times, forced=forced):
                        result = execute(p, times=times, forced=forced)
                        self.assert_curve(result, times, initial=0.25,
                                          nonlinear=nonlinear)
                        self.assert_observer(result, initial=0.25,
                                             timer_time=timer_time)

    def test_physical_initial_display_keeps_existing_rejection(self):
        with self.assertRaises(CompileError) as caught:
            execute(program(initial=0.25, physical_display=True))
        self.assertIn("initial $display", str(caught.exception))
        self.assertIn("passive measurement", str(caught.exception))

    def test_observer_step_bound_keeps_its_invalid_request_guard(self):
        with self.assertRaises(KernelError) as caught:
            execute(program(initial=0.25, observer_step="$bound_step(V(z)-1);"))
        self.assertEqual(caught.exception.detail["kind"], "invalid_bound_step")


if __name__ == "__main__":
    unittest.main()

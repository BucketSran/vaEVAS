"""Independent roots: a parabola has two roots; an integral has sqrt roots."""
import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


def run_guard(guard, *, extra="", points=None, times=None, step=4, direction=0):
    source = model(f"""
      @(initial_step) n=0;
      @(cross({guard},{direction},1e-9,1e-8)) n=n+1;
      {extra}
      V(y,r)<+n;
    """, "integer n;" + (" electrical z;" if extra else ""))
    program = compile_sources({"guard.va": source}, [instance()])
    points = points or [[0, 0], [2, 2]]
    return transient(program, {"u": points}, times or [0, 2],
                     stop=points[-1][0], max_step=step, kernel=KERNEL)


class DynamicCrossContracts(unittest.TestCase):
    def test_same_sign_segment_endpoints_do_not_hide_two_roots(self):
        result = run_guard("(V(u,r)-.5)*(V(u,r)-1.5)")
        events = result["transient"]["events"]
        self.assertEqual(len(events), 2)
        for event, exact in zip(events, [.5, 1.5]):
            self.assertGreaterEqual(event["time"], exact)
            self.assertLessEqual(event["time"] - exact, 1e-9)
        self.assertEqual(result["transient"]["states"][-1], [2])

    def test_nonlinear_direction_and_grid_invariance(self):
        a = run_guard("pow(V(u,r),2)-.5", direction=1)
        b = run_guard("pow(V(u,r),2)-.5", direction=1,
                      times=[0, .1, .3, 1, 2], step=.17)
        self.assertEqual(a["transient"]["events"], b["transient"]["events"])
        time = a["transient"]["events"][0]["time"]
        self.assertGreaterEqual(time, math.sqrt(.5))
        self.assertLessEqual(time - math.sqrt(.5), 1e-9)
        self.assertEqual(run_guard("pow(V(u,r),2)-.5", direction=-1)
                         ["transient"]["events"], [])

    def test_operator_driven_voltage_guard(self):
        result = run_guard("V(z,r)-.5", extra="V(z,r)<+idt(V(u,r),0);")
        time = result["transient"]["events"][0]["time"]
        self.assertGreaterEqual(time, 1)
        self.assertLessEqual(time - 1, 1e-9)

    def test_operator_call_in_guard_has_its_own_identity(self):
        result = run_guard("idt(V(u,r),0)-.5")
        self.assertAlmostEqual(result["transient"]["events"][0]["time"], 1, delta=1e-9)

    def test_endpoint_root_does_not_hide_an_earlier_root(self):
        result = run_guard("(V(u,r)-.5)*(V(u,r)-2)")
        self.assertEqual(len(result["transient"]["events"]), 2)
        for event, root in zip(result["transient"]["events"], [.5, 2]):
            self.assertAlmostEqual(event["time"], root, delta=1e-9)

    def test_sine_guard_uses_a_continuous_certified_operator_trajectory(self):
        result = run_guard("sin(V(u,r))-.5")
        events = result["transient"]["events"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["time"], math.pi/6, delta=1e-9)

    def test_integral_feedback_guard_has_logarithmic_root(self):
        result = run_guard("pow(V(z,r),2)-.25",
                           extra="V(z,r)<+idt(1-V(z,r),0);", direction=1)
        events = result["transient"]["events"]
        self.assertEqual(len(events), 1)
        self.assertAlmostEqual(events[0]["time"], math.log(2), delta=1e-9)

    def test_guard_only_operator_does_not_erase_state_dependency_in_relay(self):
        source = model("""
          @(initial_step) n=0;
          @(cross(idt(V(z,r),0)-.5,1,1e-9,1e-8)) n=n+1;
          V(z,r)<+V(u,r)+0*n;
          V(y,r)<+n;
        """, "integer n; electrical z;")
        program = compile_sources({"guard-only.va": source}, [instance()])
        with self.assertRaisesRegex(KernelError, "unsupported"):
            transient(program, {"u": [[0, 0], [2, 2]]}, [0, 2],
                      stop=2, max_step=2, kernel=KERNEL)

    def test_uncertifiable_tangent_fails_explicitly(self):
        with self.assertRaisesRegex(KernelError, "event_resolution"):
            run_guard("pow(V(u,r)-1,2)")


if __name__ == "__main__":
    unittest.main()

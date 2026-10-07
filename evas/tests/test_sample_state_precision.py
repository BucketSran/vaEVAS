"""Public contracts for unit-free real state enclosures and their consumers."""

GUARDS = ["DEV:precision-chain", "EVENT-CONDITIONS"]

from fractions import Fraction
import math
import unittest

from evas import KernelError
from test_continuous_dynamics import compile_model, run, values


POINTS = [[0, 1], [3, math.nextafter(1, math.inf)]]
SAMPLE = Fraction(1, 3 * 2**52)


class SampleStatePrecision(unittest.TestCase):
    def test_near_zero_sample_is_certified_by_its_voltage_consumer(self):
        # The exact PWL sample at t=1 is 1+2^-52/3. Subtraction rounds
        # the point state to zero, but its output is within the voltage budget.
        for scale in (1, 1e12):
            with self.subTest(scale=scale):
                program = compile_model(
                    f"@(initial_step) q=0; @(timer(1,0,1e-12)) q={scale}*(V(u,r)-1); "
                    f"V(y,r)<+q/{scale};", "real q;")
                result = run(program, {"u": POINTS}, [0, 1, 2, 3],
                             vabstol=1e-7, reltol=0)
                for actual in values(result)[1:]:
                    self.assertLessEqual(abs(Fraction(actual)-SAMPLE), Fraction(1e-7))

    def test_current_output_amplification_still_rejects_uncertain_sample(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(1,0,1e-12)) q=V(u,r)-1; "
            "V(y,r)<+1e16*q;", "real q;")
        with self.assertRaisesRegex(KernelError, "event_accuracy"):
            run(program, {"u": POINTS}, [0, 1, 3], vabstol=1e-7, reltol=1e-5)

    def test_later_event_amplification_keeps_the_original_state_enclosure(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(1,1,1e-12)) q=1e16*q+V(u,r)-1; "
            "V(y,r)<+q;", "real q;")
        # t=1 is harmless; t=2 amplifies the saved 2^-52/3 uncertainty.
        result = run(program, {"u": POINTS}, [0, 1], stop=1,
                     vabstol=1e-7, reltol=1e-5)
        self.assertEqual(values(result), [0, 0])
        with self.assertRaisesRegex(KernelError, "event_accuracy"):
            run(program, {"u": POINTS}, [0, 1, 2, 3], vabstol=1e-7, reltol=1e-5)

    def test_state_dependent_event_condition_remains_explicitly_unsupported(self):
        program = compile_model(
            "@(initial_step) begin q=0; flag=0; end "
            "@(timer(1,1,1e-12)) begin "
            "if(V(z,r)>1e-17) flag=1; else flag=0; q=V(u,r)-1; end "
            "V(z,r)<+q; V(y,r)<+flag;", "real q; integer flag; electrical z;")
        with self.assertRaisesRegex(KernelError, "unsupported_condition"):
            run(program, {"u": POINTS}, [0, 1, 2, 3], vabstol=1e-7, reltol=1e-5)

    def test_later_integral_amplification_keeps_the_original_state_enclosure(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(1,0,1e-12)) q=V(u,r)-1; "
            "V(y,r)<+idt(1e16*q,0);", "real q;")
        result = run(program, {"u": POINTS}, [0, 1], stop=1,
                     vabstol=1e-7, reltol=1e-5)
        self.assertEqual(values(result), [0, 0])
        with self.assertRaisesRegex(KernelError, "waveform_accuracy"):
            run(program, {"u": POINTS}, [0, 1, 2, 3], vabstol=1e-7, reltol=1e-5)

    def test_future_cross_threshold_keeps_sample_uncertainty(self):
        program = compile_model(
            "@(initial_step) begin q=0; n=0; end "
            "@(timer(1,0,1e-12)) q=V(u,r)-1; "
            "@(cross(V(c,r)-2-1e14*q,1,1e-9,1e-8)) n=n+1; "
            "V(y,r)<+n;", "real q; integer n;", ports="u,c,y,r",
            directions="input u,c; output y; inout r;")
        with self.assertRaisesRegex(KernelError, "event_resolution"):
            run(program, {"u": POINTS, "c": [[0,0],[3,3]]}, [0,1,2,3],
                vabstol=1e-7, reltol=1e-5)

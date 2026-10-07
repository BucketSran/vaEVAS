"""Public contracts for unit-free real state enclosures and their consumers.

Answers use exact Fraction PWL samples and closed-form piecewise integrals at
the independently derived root sqrt(2), including nonzero ICs and reset.
"""

GUARDS = ["DEV:precision-chain", "EVENT-CONDITIONS", "DYNAMICS", "CROSS", "COMPOSE"]

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

    def test_sequential_sample_through_square_integral_preserves_history(self):
        # u=t crosses u^2=2 at r=sqrt(2). After the sequential event body,
        # q=2*r+1; the nonzero integral is 5+4*r+q^2*(t-r).
        root = math.sqrt(2)
        times = [0, 1, 1.75, 2]
        template = """@(initial_step) begin q=2; a=0; end
          @(cross(pow(V(u,r),2)-2,1,TTOL,ETOL)) begin
            a=V(u,r); if (V(u,r)>1) q=2*a+1; else q=0;
          end
          V(y,r)<+idt(q*q,5);"""
        program = compile_model(template.replace('TTOL', '1e-10').replace('ETOL', '1e-9'),
                                'real q,a;')
        sources = {'u': [[0,0], [2,2]]}
        sparse = run(program, sources, times, vabstol=1e-7, reltol=0)
        dense_times = [i/16 for i in range(33)]
        dense = run(program, sources, dense_times, vabstol=1e-7, reltol=0)
        for result, grid in [(sparse, times), (dense, dense_times)]:
            for actual, t in zip(values(result), grid, strict=True):
                expected = 5+4*t if t <= root else 5+4*root+(2*root+1)**2*(t-root)
                self.assertAlmostEqual(actual, expected, delta=1e-7)
        # max_step and physical inputs/events are identical; only requested
        # observations change. This path must not feed queries into history.
        self.assertEqual(sparse['transient']['events'], dense['transient']['events'])
        self.assertEqual(values(sparse), [values(dense)[dense_times.index(t)] for t in times])
        # A wider root window must not discard uncertainty before squaring q.
        wide = compile_model(template.replace('TTOL', '1e-5').replace('ETOL', '1e-4'),
                             'real q,a;')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            run(wide, sources, times, vabstol=1e-7, reltol=0)

    def test_reset_sample_keeps_unrelated_nonlinear_integral(self):
        root = math.sqrt(2)
        times = [0, 1, 1.75, 2]
        # The event closes against the asserted reset: z=3, then q=2*3+1.
        # y's distinct call-site history must keep its pre-event area and IC.
        for writes in ['rst=1; q=V(z,r);', 'q=V(z,r); rst=1;']:
            with self.subTest(writes=writes):
                program = compile_model(f"""@(initial_step) begin q=2; rst=0; end
                  @(cross(pow(V(u,r),2)-2,1,1e-10,1e-9)) begin
                    {writes} q=2*q+1;
                  end
                  @(timer(1.5,0,1e-12)) rst=0;
                  V(z,r)<+idt(q,3,rst); V(y,r)<+idt(q*q,5);""",
                  'real q; integer rst; electrical z;')
                result = run(program, {'u': [[0,0], [2,2]]}, times,
                             vabstol=1e-7, reltol=0)
                for y, z, t in zip(values(result), values(result, 'dut:z'), times, strict=True):
                    expected_y = 5+4*t if t <= root else 5+4*root+49*(t-root)
                    expected_z = 3+2*t if t < root else 3+7*max(0, t-1.5)
                    self.assertAlmostEqual(y, expected_y, delta=1e-7)
                    self.assertAlmostEqual(z, expected_z, delta=1e-7)

    def test_sampled_square_integral_drives_a_later_cross(self):
        root = math.sqrt(2)
        times = [0, 1, 1.75, 2]
        baseline = None
        for square in ['q*q', 'pow(q,2)']:
            with self.subTest(square=square):
                template = f"""@(initial_step) begin q=0; n=0; end
                  @(cross(pow(V(u,r),2)-2,1,TTOL,ETOL)) q=V(u,r);
                  V(z,r)<+idt({square},0);
                  @(cross(V(z,r)-1,1,1e-9,1e-8)) n=n+1;
                  V(y,r)<+n;"""
                program = compile_model(template.replace('TTOL', '1e-10').replace('ETOL', '1e-9'),
                                        'real q; integer n; electrical z;')
                result = run(program, {'u': [[0,0], [2,2]]}, times,
                             vabstol=1e-7, reltol=0)
                self.assertEqual(values(result), [0,0,0,1])
                for z, t in zip(values(result, 'dut:z'), times, strict=True):
                    self.assertAlmostEqual(z, 2*max(0, t-root), delta=1e-7)
                events = result['transient']['events']
                self.assertEqual(len(events), 2)
                for event, expected in zip(events, [root, root+.5], strict=True):
                    self.assertLessEqual(event['observation_time_bounds'][0], expected)
                    self.assertGreaterEqual(event['observation_time_bounds'][1], expected)
                    self.assertAlmostEqual(event['time'], expected, delta=1e-9)
                if baseline is not None:
                    # Both polynomial spellings select the same physical
                    # history path; do not generalize this to other solvers.
                    self.assertEqual(events, baseline)
                baseline = events
                wide = compile_model(template.replace('TTOL', '1e-5').replace('ETOL', '1e-4'),
                                     'real q; integer n; electrical z;')
                with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
                    run(wide, {'u': [[0,0], [2,2]]}, times, vabstol=1e-7, reltol=0)

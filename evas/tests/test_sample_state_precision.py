"""Public contracts for unit-free real state enclosures and their consumers.

Answers use exact Fraction PWL samples, piecewise integrals at sqrt(2), and
Decimal exponential filter responses, including nonzero histories and reset.
"""

GUARDS = ["DEV:precision-chain", "EVENT-CONDITIONS", "DYNAMICS", "CROSS", "COMPOSE"]

from fractions import Fraction
from decimal import Decimal, localcontext
import math
import unittest

from evas import Instance, KernelError
from test_continuous_dynamics import compile_model, run, values


POINTS = [[0, 1], [3, math.nextafter(1, math.inf)]]
SAMPLE = Fraction(1, 3 * 2**52)


class SampleStatePrecision(unittest.TestCase):
    def test_unrelated_filter_preserves_exact_affine_root_after_flow_change(self):
        # z=t until .25, then z=2*t-.25. Its z=.75 root is exactly .5.
        # x=3+t and DC f=2 are unrelated live physical states, not guards.
        body = ('@(initial_step) begin q=1; n=0; end '
                '@(timer(0.25,0,1e-12)) q=2; '
                '@(cross(V(z,r)-0.75,1,1e-10,1e-10)) n=n+1; '
                'V(z,r)<+idt(q,0); V(y,r)<+n;')
        sparse = [0, .499999, .5, .500001, .75, 1]
        dense = [0, .125, .25, .375, .499999, .5, .500001, .625, .75, 1]
        for extra in ['', "V(x,r)<+idt(1,3); V(f,r)<+laplace_nd(2,'{1},'{1,1});"]:
            with self.subTest(extra=bool(extra)):
                declarations = 'real q; integer n; electrical z'+(',x,f;' if extra else ';')
                program = compile_model(body+extra, declarations)
                first = run(program, times=sparse, max_step=1, vabstol=1e-8, reltol=0)
                second = run(program, times=dense, max_step=1, vabstol=1e-8, reltol=0)
                self.assertEqual(first['solutions'],
                                 [second['solutions'][dense.index(t)] for t in sparse])
                self.assertEqual(values(first), [0, 0, 1, 1, 1, 1])
                events = first['transient']['events']
                self.assertEqual(events, second['transient']['events'])
                self.assertEqual([event['time'] for event in events], [.25, .5])
                for t, actual in zip(dense, values(second, 'dut:z'), strict=True):
                    expected = Fraction(t) if t <= .25 else 2*Fraction(t)-Fraction(1, 4)
                    self.assertLessEqual(abs(Fraction(actual)-expected), Fraction(1e-8))
                if extra:
                    for t, actual in zip(dense, values(second, 'dut:x'), strict=True):
                        self.assertLessEqual(abs(Fraction(actual)-(3+Fraction(t))), Fraction(1e-8))
                    for actual in values(second, 'dut:f'):
                        self.assertAlmostEqual(actual, 2, delta=1e-8)

    def test_exact_affine_roots_keep_gain_direction_and_instance_identity(self):
        program = compile_model(
            '@(initial_step) begin q=1; n=0; end @(timer(0.25,0,1e-12)) q=2; '
            '@(cross(gain*(V(z,r)-threshold),direction,1e-10,1e-10)) n=n+1; '
            "V(z,r)<+idt(q,0); V(f,r)<+laplace_nd(2,'{1},'{1,1}); V(y,r)<+n;",
            'parameter real threshold=0.75; parameter real gain=1; '
            'parameter integer direction=1; real q; integer n; electrical z,f;',
            instances=[
                Instance('left', 'm', {'u':'u', 'y':'left', 'r':'0'},
                         {'threshold':.75, 'gain':4, 'direction':1}),
                Instance('right', 'm', {'u':'u', 'y':'right', 'r':'0'},
                         {'threshold':1.25, 'gain':-8, 'direction':-1}),
            ])
        result = run(program, times=[0, .5, .75, 1], vabstol=1e-8, reltol=0)
        self.assertEqual(values(result, 'left'), [0, 1, 1, 1])
        self.assertEqual(values(result, 'right'), [0, 0, 1, 1])
        crosses = [e for e in result['transient']['events'] if e['kind']=='cross']
        self.assertEqual([e['time'] for e in crosses], [.5, .75])

    def test_guard_depending_on_filter_keeps_an_inexact_root_enclosure(self):
        # z=t until .25 and 2*t-.25 afterwards. Its proper filter has
        # f=t-1+exp(-t), then 2*t-2.25+(1+exp(-.25))*exp(.25-t).
        # z+f=.75 has a transcendental root, not the affine z=.75 root .5.
        with localcontext() as context:
            context.prec = 100
            low, high = Decimal('0.25'), Decimal('0.5')
            for _ in range(160):
                middle = (low+high)/2
                filtered = (2*middle-Decimal('2.25')
                            +(1+Decimal('-0.25').exp())*(Decimal('0.25')-middle).exp())
                if 2*middle-Decimal('0.25')+filtered < Decimal('0.75'):
                    low = middle
                else:
                    high = middle
            program = compile_model(
                '@(initial_step) begin q=1; n=0; end @(timer(0.25,0,1e-12)) q=2; '
                '@(cross(V(z,r)+V(f,r)-0.75,1,1e-10,1e-10)) n=n+1; '
                "V(z,r)<+idt(q,0); V(f,r)<+laplace_nd(V(z,r),'{1},'{1,1}); V(y,r)<+n;",
                'real q; integer n; electrical z,f;')
            result = run(program, times=[0, .375, .5, 1], vabstol=1e-8, reltol=0)
            self.assertEqual(values(result), [0, 0, 1, 1])
            cross = [e for e in result['transient']['events'] if e['kind']=='cross'][0]
            lo, hi = map(Decimal.from_float, cross['observation_time_bounds'])
            self.assertLessEqual(lo, low)
            self.assertGreaterEqual(hi, high)
            self.assertLess(lo, hi)
            self.assertLessEqual(hi-lo, Decimal.from_float(1e-10))

    def test_near_zero_sample_gain_preserves_nonzero_filter_history_and_later_event(self):
        # u(k)-1 = k/(3*2^52). Each timer replaces the drive, while the
        # filter y'+y=q keeps y(1)=1 and its later nonzero physical history.
        gain = 10**8
        sparse = [0, .5, 1, 1.25, 1.5, 2, 2.25, 2.5, 3]
        dense = [i/16 for i in range(49)]
        for direct in [False, True]:
            with self.subTest(direct=direct):
                body = (f'@(initial_step) q=1; @(timer(1,1,1e-12)) '
                        f'q={gain}*(V(u,r)-1); '
                        "V(y,r)<+laplace_nd(q,'{1},'{1,1});")
                if direct:
                    body += 'V(a,r)<+q;'
                program = compile_model(body, 'real q; electrical a;' if direct else 'real q;')
                first = run(program, {'u': POINTS}, sparse, max_step=3,
                            vabstol=1e-7, reltol=0)
                second = run(program, {'u': POINTS}, dense, max_step=3,
                             vabstol=1e-7, reltol=0)
                self.assertEqual(first['solutions'],
                                 [second['solutions'][dense.index(t)] for t in sparse])
                events = first['transient']['events']
                self.assertEqual(events, second['transient']['events'])
                self.assertEqual([event['time'] for event in events], [1, 2, 3])
                with localcontext() as context:
                    context.prec = 100
                    drive = Decimal(gain)/Decimal(3*2**52)
                    at_two = drive+(1-drive)*Decimal(-1).exp()
                    for t, actual in zip(sparse, values(first), strict=True):
                        time = Decimal.from_float(t)
                        if t <= 1:
                            expected = Decimal(1)
                        elif t <= 2:
                            expected = drive+(1-drive)*(1-time).exp()
                        else:
                            expected = 2*drive+(at_two-2*drive)*(2-time).exp()
                        self.assertLessEqual(abs(Decimal.from_float(actual)-expected),
                                             Decimal.from_float(1e-7))
                    if direct:
                        for t, actual in zip(sparse, values(first, 'dut:a'), strict=True):
                            expected = Decimal(1) if t < 1 else int(t)*drive
                            self.assertLessEqual(abs(Decimal.from_float(actual)-expected),
                                                 Decimal.from_float(1e-7))

    def test_filter_consumes_sample_uncertainty_after_an_accepted_event(self):
        program = compile_model(
            '@(initial_step) q=1; @(timer(1,1,1e-12)) q=1e16*(V(u,r)-1); '
            "V(y,r)<+laplace_nd(q,'{1},'{1,1});", 'real q;')
        # The first event leaves filter voltage exactly 1, so it can pass.
        # Later its uncertain drive (~.74015 V) matters despite rounded q=0.
        prefix = run(program, {'u': POINTS}, [0, 1], stop=1, max_step=1,
                     vabstol=1e-7, reltol=0)
        self.assertEqual(values(prefix), [1, 1])
        self.assertEqual([event['time'] for event in prefix['transient']['events']], [1])
        for step in [3, 1/16]:
            with self.subTest(step=step):
                with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
                    run(program, {'u': POINTS}, [0, 1, 1.5, 3], max_step=step,
                        vabstol=1e-7, reltol=0)

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
        # A wider root window now refines before sampling and squaring q.
        # Preserve the source and budget, checking the old integral and IC.
        wide = compile_model(template.replace('TTOL', '1e-5').replace('ETOL', '1e-4'),
                             'real q,a;')
        wide_dense_times = sorted(set(dense_times+[1.4142, 1.41423]))
        wide_sparse = run(wide, sources, times, vabstol=1e-7, reltol=0)
        wide_dense = run(wide, sources, wide_dense_times, vabstol=1e-7, reltol=0)
        with localcontext() as context:
            context.prec = 70
            tau = Decimal(2).sqrt()
            for result, grid in [(wide_sparse, times), (wide_dense, wide_dense_times)]:
                for actual, t in zip(values(result), grid, strict=True):
                    t = Decimal.from_float(t)
                    expected = 5+4*t if t <= tau else 5+4*tau+(2*tau+1)**2*(t-tau)
                    self.assertLessEqual(abs(Decimal.from_float(actual)-expected), Decimal('1e-7'))
        self.assertEqual(wide_sparse['solutions'],
                         [wide_dense['solutions'][wide_dense_times.index(t)] for t in times])
        self.assertEqual(wide_sparse['transient']['events'], wide_dense['transient']['events'])
        # Root recovery does not bypass the nonlinear output certificate.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy.*nonlinear accumulated history'):
            run(wide, sources, times, vabstol=1e-14, reltol=0)

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

"""idt assert that is nonzero only at event instants (#230).

LRM 2.4 section 4.5.4: "Once assert becomes zero, idt() returns the integral of
the argument starting from the last instant where assert was nonzero"; its
ramp_generator example (cleared at the start of every evaluation, set by a
timer) notes that "the reset occurs instantaneously". The assert is therefore
nonzero exactly at each event instant and the output is a sawtooth.

Independent answer, fixed before the fix. With reset instants r_k and IC c,

    y(t) = c + gain * integral_{r(t)}^{t} u(s) ds,  r(t) = max{r_k <= t}, 0 before r_1.

The oracle integrates the original source polyline with exact rationals; it
does not read the kernel history or output grid. At a reset instant the event
evaluation sees assert != 0, so idt returns c there. `transient` reports the
post-event solution at an event time (as the level reset in test_idt does), so
y(r_k) = c. Exact reset instants are sampled only where binary64
start + k*period is exact (1 us = start, 2 us = start + start).
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS"]

from fractions import Fraction as F
import math
import unittest

from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


US = 1e-6
# Exact-rational oracle against binary64 kernel output: the reset instants
# (timer schedule start + k*period differs from k us by < 1e-21 s, times the
# 1e6 V/s slope) and binary64 prefix differences (|y| <= 4 V, a few ulps) both
# stay far below 1e-12 V. The never-reset answer differs by at least 0.25 V.
TIMER_TOL = 1e-12
# A cross root is localized within its default time tolerance of 1e-12 s; at a
# 1e6 V/s slope that moves y by at most 1e-6 V. Allow twice that bound.
CROSS_TOL = 2e-6


def integral(points, start, end):
    """Exact area of the binary64 source polyline on [start, end]."""
    def prefix(time):
        t, result = F(time), F(0)
        for (s, a), (e, b) in zip(points, points[1:]):
            s, a, e, b = map(F, (s, a, e, b))
            if t <= s:
                break
            stop = min(t, e)
            result += (a + a + (b - a) * (stop - s) / (e - s)) * (stop - s) / 2
        return result
    return prefix(end) - prefix(start)


def last_reset(time, resets):
    return max([F(0)] + [F(r) for r in resets if F(r) <= F(time)])


def sawtooth(times, resets, points, gain=1e6, ic=0.0):
    return [F(ic) + F(gain) * integral(points, last_reset(t, resets), t) for t in times]


def run(body, declarations='integer reset;', points=None, times=None, stop=4 * US, **options):
    program = compile_sources({'pulse.va': model(body, declarations)}, [instance()])
    points = points or [[0, 1], [stop, 1]]
    return transient(program, {'u': points}, times, stop=stop, max_step=stop,
                     kernel=KERNEL, **options), points


def values(result, node='y'):
    index = result['nodes'].index(node)
    return [row['voltages'][index] for row in result['solutions']]


class PulseAssertResets(unittest.TestCase):
    TIMES = [0, .25 * US, .5 * US, .999 * US, 1 * US, 1.001 * US, 1.5 * US, 2 * US,
             2.25 * US, 2.999 * US, 3.4 * US, 3.75 * US]

    def assertClose(self, actual, expected, tolerance, times):
        for t, a, e in zip(times, actual, expected):
            with self.subTest(t=t):
                self.assertTrue(math.isfinite(a))
                self.assertLessEqual(abs(F(a) - e), F(tolerance), (t, a, float(e)))

    def test_lrm_ramp_generator_timer_pulse_gives_sawtooth(self):
        # LRM 2.4 section 4.5.4 ramp_generator, time scaled by 1e-6.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        result, points = run(body, times=self.TIMES)
        expected = sawtooth(self.TIMES, [1 * US, 2 * US, 3 * US], [[0, 1], [4 * US, 1]])
        # Issue table: 0.5 us -> 0.5, 1.5 us -> 0.5, 2.25 us -> 0.25, 3.4 us -> 0.4.
        for index, nominal in [(2, 0.5), (6, 0.5), (8, 0.25), (10, 0.4)]:
            self.assertLess(abs(expected[index] - F(nominal)), F(TIMER_TOL))
        self.assertClose(values(result), expected, TIMER_TOL, self.TIMES)
        self.assertEqual(values(result)[4], 0.0)
        self.assertEqual(values(result)[7], 0.0)

    def test_nonzero_ic_and_driven_input_restart_from_each_pulse(self):
        # Distinct faults: a restart that forgets IC, or one that subtracts the
        # wrong prefix of a time-varying direct PWL input.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          V(y,r) <+ idt(1.0e6*V(u,r), 0.25, reset);
        """
        points = [[0, 0.5], [4 * US, 1.5]]
        result, _ = run(body, points=points, times=self.TIMES)
        expected = sawtooth(self.TIMES, [1 * US, 2 * US, 3 * US], points, ic=0.25)
        self.assertClose(values(result), expected, TIMER_TOL, self.TIMES)
        self.assertEqual(values(result)[4], 0.25)

    def test_cross_pulse_restarts_at_each_rising_crossing(self):
        # Rising crossings of 0.5 at the segment midpoints 1, 2 and 3 us.
        points = [[0, 0]]
        for k in (1, 2, 3):
            points += [[(k - .1) * US, 0], [(k + .1) * US, 1], [(k + .4) * US, 0]]
        points.append([4 * US, 0])
        body = """
          reset = 0;
          @(cross(V(u,r) - 0.5, +1)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        times = [t for t in self.TIMES if t not in (1 * US, 2 * US)]
        result, _ = run(body, points=points, times=times)
        expected = sawtooth(times, [1 * US, 2 * US, 3 * US], [[0, 1], [4 * US, 1]])
        self.assertClose(values(result), expected, CROSS_TOL, times)

    def test_or_trigger_pulses_from_each_leaf(self):
        # u rises through 2 at the segment midpoints 2 us (with the timer
        # leaf) and 2.5 us (cross leaf alone). The OR body runs once per
        # instant; two toggles in one evaluation would cancel the restart.
        points = [[0, 0], [1.9 * US, 0], [2.1 * US, 4], [2.3 * US, 0],
                  [2.4 * US, 0], [2.6 * US, 4], [2.8 * US, 0], [4 * US, 0]]
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6) or cross(V(u,r) - 2, +1)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        result, _ = run(body, points=points, times=self.TIMES)
        expected = sawtooth(self.TIMES, [1 * US, 2 * US, 2.5 * US, 3 * US], [[0, 1], [4 * US, 1]])
        self.assertClose(values(result), expected, CROSS_TOL, self.TIMES)

    def test_negative_assert_value_also_restarts(self):
        # Any nonzero assert restarts, not only a positive one.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = -1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        result, points = run(body, times=self.TIMES)
        expected = sawtooth(self.TIMES, [1 * US, 2 * US, 3 * US], points)
        self.assertClose(values(result), expected, TIMER_TOL, self.TIMES)

    def test_conditional_event_write_pulses_only_on_the_written_path(self):
        # The event writes reset only while u > 0.5 (first two periods). On the
        # unwritten path the evaluation still sees the ordinary value 0.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) if (V(u,r) > 0.5) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        points = [[0, 1], [2.5 * US, 1], [2.6 * US, 0], [4 * US, 0]]
        result, _ = run(body, points=points, times=self.TIMES)
        expected = sawtooth(self.TIMES, [1 * US, 2 * US], [[0, 1], [4 * US, 1]])
        self.assertClose(values(result), expected, TIMER_TOL, self.TIMES)

    def test_two_call_sites_share_the_pulse_but_not_their_histories(self):
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset) + idt(2.0e6, 0.5, reset);
        """
        result, points = run(body, times=self.TIMES)
        resets = [1 * US, 2 * US, 3 * US]
        expected = [a + b for a, b in zip(sawtooth(self.TIMES, resets, points),
                                          sawtooth(self.TIMES, resets, points, gain=2e6, ic=0.5))]
        self.assertClose(values(result), expected, 3 * TIMER_TOL, self.TIMES)

    def test_zero_input_keeps_ic_exactly_through_pulses(self):
        # Zero input gives exactly IC at every time, including extreme
        # magnitudes: combining the two restarted histories must count IC once.
        for ic in [1e300, -1e300, 0.1]:
            with self.subTest(ic=ic):
                body = f"""
                  reset = 0;
                  @(timer(1.0e-6, 1.0e-6)) reset = 1;
                  V(y,r) <+ idt(0, {ic}, reset);
                """
                result, _ = run(body, times=self.TIMES)
                self.assertEqual(values(result), [ic] * len(self.TIMES))

    def test_instances_keep_their_own_pulse_schedules(self):
        # Each bound instance owns its parity state and event toggles.
        source = model("""
          reset = 0;
          @(timer(period, period)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """, 'integer reset; parameter real period = 1.0e-6;')
        program = compile_sources({'pulse.va': source}, [
            instance('fast', connections=dict(u='u', y='y1', r='0'), parameters={'period': 0.5e-6}),
            instance('slow', connections=dict(u='u', y='y2', r='0'))])
        points = [[0, 1], [4 * US, 1]]
        # 1.5 us = 3 * 0.5 us is not an exact binary64 schedule instant.
        times = [t for t in self.TIMES if t != 1.5 * US]
        result = transient(program, {'u': points}, times, stop=4 * US, max_step=4 * US, kernel=KERNEL)
        fast = sawtooth(times, [k * .5 * US for k in range(1, 8)], points)
        slow = sawtooth(times, [1 * US, 2 * US, 3 * US], points)
        self.assertClose(values(result, 'y1'), fast, TIMER_TOL, times)
        self.assertClose(values(result, 'y2'), slow, TIMER_TOL, times)

    def test_feedback_integrand_restarts_from_ic(self):
        # y' = 1e6 (1 - y), restarted at 0 every microsecond:
        # y(t) = 1 - exp(-1e6 (t - r(t))). This integral is solved by the
        # continuous network path, not the direct PWL path.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          V(y,r) <+ idt(1.0e6*(1 - V(y,r)), 0.0, reset);
        """
        times = [t for t in self.TIMES if t]
        result, _ = run(body, times=times, vabstol=1e-6, reltol=1e-6)
        for t, actual in zip(times, values(result)):
            with self.subTest(t=t):
                expected = 1 - math.exp(-1e6 * float(F(t) - last_reset(t, [1 * US, 2 * US, 3 * US])))
                self.assertLessEqual(abs(actual - expected), 1e-6 + 1e-6 * abs(expected) + 1e-12)


class PulseAssertBoundaries(unittest.TestCase):
    """Neighbouring forms that main already answers correctly, plus refusals."""

    TIMES = PulseAssertResets.TIMES

    def assertMatches(self, body, resets, declarations='integer reset;', ic=0.0):
        result, points = run(body, declarations, times=self.TIMES)
        expected = sawtooth(self.TIMES, resets, points, ic=ic)
        for t, a, e in zip(self.TIMES, values(result), expected):
            with self.subTest(t=t):
                self.assertLessEqual(abs(F(a) - e), F(TIMER_TOL), (t, a, float(e)))

    def test_assert_held_over_an_interval_releases_at_its_clear(self):
        # Level reset from k us to k+0.25 us: IC while held, then integral
        # from the release instant.
        body = """
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          @(timer(1.25e-6, 1.0e-6)) reset = 0;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        result, points = run(body, times=self.TIMES)
        for t, actual in zip(self.TIMES, values(result)):
            k = math.floor(t / US + 1e-9)
            phase = F(t) - F(k * US)
            if k == 0:
                expected = F(1e6) * F(t)
            elif phase < F(.25 * US):
                expected = F(0)
            else:
                expected = F(1e6) * (F(t) - F(k * US + .25 * US))
            with self.subTest(t=t):
                self.assertLessEqual(abs(F(actual) - expected), F(1e-9), (t, actual, float(expected)))

    def test_abstime_offset_sawtooth(self):
        body = """
          @(timer(1.0e-6, 1.0e-6)) t0 = $abstime;
          V(y,r) <+ 1.0e6*($abstime - t0);
        """
        self.assertMatches(body, [1 * US, 2 * US, 3 * US], 'real t0;')

    def test_event_write_overwritten_before_the_call_is_not_a_reset(self):
        # Source order: the event's write is replaced by the ordinary write
        # before idt reads the assert, so idt never sees a nonzero value.
        body = """
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          reset = 0;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        self.assertMatches(body, [])

    def test_event_after_the_call_is_not_a_reset(self):
        body = """
          reset = 0;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
        """
        self.assertMatches(body, [])

    def test_nonzero_ordinary_assert_holds_ic(self):
        # A zero assert for one instant releases nothing: the last instant
        # where assert was nonzero is the same instant.
        body = """
          reset = 1;
          @(timer(1.0e-6, 1.0e-6)) reset = 0;
          V(y,r) <+ idt(1.0e6, 0.25, reset);
        """
        result, _ = run(body, times=self.TIMES)
        self.assertEqual(values(result), [0.25] * len(self.TIMES))

    def test_coincident_pulse_events_remain_an_event_conflict(self):
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
          @(timer(2.0e-6, 2.0e-6)) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
        """
        with self.assertRaisesRegex(KernelError, 'event_conflict'):
            run(body, times=self.TIMES)

    def test_conditional_pulse_beside_a_simultaneous_writer_is_refused(self):
        # Known conservative limit: a pulsing block that may leave the assert
        # unwritten first restores the ordinary value, so it always writes the
        # assert slot. A second block writing the same assert at the same
        # instant (here placed after the call, so main's ramp was right) then
        # becomes the existing same-time writer conflict, not a wrong value.
        body = """
          reset = 0;
          @(timer(1.0e-6, 1.0e-6)) if (V(u,r) > 5) reset = 1;
          V(y,r) <+ idt(1.0e6, 0.0, reset);
          @(timer(1.0e-6, 1.0e-6)) reset = 1;
        """
        with self.assertRaisesRegex(KernelError, 'event_conflict'):
            run(body, times=self.TIMES)

    def test_unsupported_pulse_forms_are_refused(self):
        # Each assert is nonzero at an event instant through a form outside
        # the lowered slice; main returned the never-reset waveform for all.
        cases = {
            'local copy': ('integer reset, a;', """
                reset = 0;
                @(timer(1.0e-6, 1.0e-6)) reset = 1;
                a = reset;
                V(y,r) <+ idt(1.0e6, 0.0, a);
            """),
            'scaled assert': ('integer reset;', """
                reset = 0;
                @(timer(1.0e-6, 1.0e-6)) reset = 1;
                V(y,r) <+ idt(1.0e6, 0.0, 2*reset);
            """),
            'final_step': ('integer reset;', """
                reset = 0;
                @(final_step) reset = 1;
                V(y,r) <+ idt(1.0e6, 0.0, reset);
            """),
        }
        for name, (declarations, body) in cases.items():
            with self.subTest(case=name):
                with self.assertRaises(CompileError) as caught:
                    run(body, declarations, times=self.TIMES)
                self.assertEqual(caught.exception.diagnostic['code'], 'unsupported_idt_pulse_reset')


if __name__ == '__main__':
    unittest.main()

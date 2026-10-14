"""History accuracy against exact binary64-input rational answers.

Accepted source event times are fixed; these tests do not charge the permitted
timer/cross timing window to the voltage budget. No simulator supplies goldens.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["TRANSITION", "TIMED-OPERATOR"]

from fractions import Fraction as F
import unittest

from evas import KernelError, transient
from test_transition import compile_transition, KERNEL


def execute(body, times, stop, *, atol, declarations='real a;', step=None, rtol=0):
    return transient(compile_transition(body, declarations),
                     {'u': [[0, 0], [stop, 0]]}, times, stop=stop,
                     max_step=stop if step is None else step, kernel=KERNEL,
                     vabstol=atol, reltol=rtol)


class TransitionAccuracy(unittest.TestCase):
    def assert_enclosed(self, result, node, expected, atol, rtol=0):
        index = result['nodes'].index(node)
        evidence = result['observation_evidence']
        bound_index = evidence['nodes'].index(node)
        for row, bounds, exact in zip(result['solutions'], evidence['voltage_bounds_V'], expected, strict=True):
            actual = F(row['voltages'][index])
            lo, hi = map(F, bounds[bound_index])
            budget = F(atol) + F(rtol)*abs(exact)
            self.assertLessEqual(lo, exact)
            self.assertLessEqual(exact, hi)
            self.assertLessEqual(abs(actual-exact), budget)
            self.assertLessEqual(max(abs(actual-lo), abs(actual-hi)), budget)

    def test_sample_inside_uncertain_delayed_start_is_rejected(self):
        start, delay = 1e12, .10005
        sample = start + delay
        self.assertGreater(F(sample), F(start) + F(delay))
        body = (f'@(initial_step) a=0; @(timer({start},0,1)) a=1; '
                f'V(y,r)<+transition(a,{delay},1,1);')
        # This sample precedes the representative upper deadline but follows
        # the exact real start. Returning the old zero level is not certifiable.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, [0,start,sample], sample, atol=1e-9)
        result = execute(body, [0,start,sample], sample, atol=1e-3)
        y = result['nodes'].index('y')
        actual = result['solutions'][-1]['voltages'][y]
        self.assertLessEqual(abs(F(actual)-(F(sample)-F(start)-F(delay))),F(1e-3))

    def test_delayed_start_roundoff_cannot_hide_behind_zero_residual(self):
        start, delay = 1e12, .10005
        body = (f'@(initial_step) a=0; @(timer({start},0,1)) a=1; '
                f'V(y,r)<+transition(a,{delay},1,1);')
        times = [0, start, start+.5, start+2]
        # The old code accepted a 169.7265625 uV error with zero residual.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, times, start+2, atol=1e-9)
        result = execute(body, times, start+2, atol=1e-3)
        y = result['solutions'][2]['voltages'][result['nodes'].index('y')]
        self.assertLessEqual(abs(F(y) - (F(1, 2)-F(delay))), F(1e-3))

    def test_timer_zero_final_seed_has_exact_network_gain(self):
        # The zero closure seeds transition at 1; no initial 1/3 ramp exists.
        body = ('@(initial_step) a=0; @(timer(0,0,0.001)) a=1; '
                'V(y,r)<+1073741824*transition(a,0,3,3);')
        result = execute(body, [0,1,3], 3, atol=1e-10)
        self.assert_enclosed(result, 'y', [F(1073741824)]*3, 1e-10)

    def test_network_gain_is_included_in_history_error_budget(self):
        # Shift the edge and old queries by 1/4 to preserve the inexact 1/3
        # history independently of zero-time initialization.
        body = ('@(initial_step) a=0; @(timer(0.25,0,0.001)) a=1; '
                'V(y,r)<+1073741824*transition(a,0,3,3);')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, [0,.25,1.25,3.25], 3.25, atol=1e-10)
        result = execute(body, [0,.25,1.25,3.25], 3.25, atol=1e-6)
        self.assert_enclosed(result, 'y',
                             [F(0),F(0),F(1073741824,3),F(1073741824)],1e-6)

    def test_timer_zero_final_seed_changes_interruption_origin(self):
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0,0,0.001)) a=1; @(timer(1,0,0.001)) b=-1; '
                '@(timer(2,0,0.001)) c=0.5; '
                'V(y,r)<+transition(a+b+c,0,3,6);')
        times = [0,.5,1,1.5,2,2.5,4,5]
        # Start at 1. First descent has slope -1/6; the same-direction
        # interruption retains origin 1 and changes its slope to -1/12.
        expected = [F(1),F(1),F(1),F(11,12),F(5,6),F(19,24),F(2,3),F(7,12)]
        for step in [5,.125]:
            result = execute(body,times,5,atol=1e-12,
                             declarations='real a,b,c;',step=step)
            self.assert_enclosed(result,'y',expected,1e-12)

    def test_multiple_interruptions_match_independent_rational_knots(self):
        # Original nonzero slopes 1/3, -1/6, +1/6, with all events and
        # queries shifted by 1/4 so initialization cannot erase the first edge.
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0.25,0,0.001)) a=1; @(timer(1.25,0,0.001)) b=-1; '
                '@(timer(2.25,0,0.001)) c=0.5; '
                'V(y,r)<+transition(a+b+c,0,3,6);')
        times = [0,.25,.75,1.25,1.75,2.25,2.75,4.25,5.25]
        expected = [F(0),F(0),F(1,6),F(1,3),F(1,4),F(1,6),F(1,4),F(1,2),F(1,2)]
        for step in [5.25,.125]:
            result = execute(body,times,5.25,atol=1e-12,
                             declarations='real a,b,c;',step=step)
            self.assert_enclosed(result,'y',expected,1e-12)

    def test_timer_zero_final_seed_is_sampled_as_one(self):
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0,0,0.001)) a=1; @(timer(1,0,0.001)) b=V(y,r); '
                '@(timer(2,0,0.001)) c=1073741824*V(z,r)-357913941.3333333+1; '
                'V(y,r)<+transition(a,0,3,3); V(z,r)<+b; V(w,r)<+c;')
        result = execute(body,[0,1,2,3],3,atol=1e-9,rtol=1e-9,
                         declarations='real a,b,c; electrical z,w;')
        exact = F(1073741824)-F(357913941.3333333)+1
        self.assert_enclosed(result,'y',[F(1)]*4,1e-9,1e-9)
        self.assert_enclosed(result,'dut:z',[F(0),F(1),F(1),F(1)],1e-9,1e-9)
        self.assert_enclosed(result,'dut:w',[F(0),F(0),exact,exact],1e-9,1e-9)

    def test_sampled_state_keeps_history_error_across_events(self):
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0.25,0,0.001)) a=1; @(timer(1.25,0,0.001)) b=V(y,r); '
                '@(timer(2.25,0,0.001)) c=1073741824*V(z,r)-357913941.3333333+1; '
                'V(y,r)<+transition(a,0,3,3); V(z,r)<+b; V(w,r)<+c;')
        declarations = 'real a,b,c; electrical z,w;'
        # Sample 1/3 at t=1.25; at t=2.25 its retained uncertainty is
        # amplified. Treating the sampled state as exact would accept it.
        times = [0,.25,1.25,2.25,3.25]
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body,times,3.25,atol=1e-9,rtol=1e-9,declarations=declarations)
        result = execute(body,times,3.25,atol=1e-6,rtol=1e-6,declarations=declarations)
        exact = F(1073741824,3)-F(357913941.3333333)+1
        self.assert_enclosed(result,'dut:w',[F(0),F(0),F(0),exact,exact],1e-6,1e-6)

    def test_initial_affine_input_roundoff_is_checked(self):
        # State coefficients remain in IR. Their exact sum is not the rounded
        # coefficient produced by nominal affine evaluation.
        body = '@(initial_step) a=1; V(y,r)<+transition(0.1*a+0.2*a,0,1,1);'
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body,[0,1],1,atol=1e-18)
        result = execute(body,[0,1],1,atol=1e-12)
        y = result['nodes'].index('y')
        self.assertLessEqual(abs(F(result['solutions'][0]['voltages'][y])-(F(.1)+F(.2))),F(1e-12))

"""History accuracy against exact binary64-input rational answers.

Accepted source event times are fixed; these tests do not charge the permitted
timer/cross timing window to the voltage budget. No simulator supplies goldens.
"""
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

    def test_network_gain_is_included_in_history_error_budget(self):
        # An inexact 1/3 ramp value is amplified; checking the operator alone
        # against a voltage tolerance would miss the output's tighter budget.
        body = ('@(initial_step) a=0; @(timer(0,0,.001)) a=1; '
                'V(y,r)<+1073741824*transition(a,0,3,3);')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, [0,1,3], 3, atol=1e-10)
        result = execute(body, [0,1,3], 3, atol=1e-6)
        y = result['solutions'][1]['voltages'][result['nodes'].index('y')]
        self.assertLessEqual(abs(F(y) - F(1073741824,3)), F(1e-6))

    def test_multiple_interruptions_match_independent_rational_knots(self):
        # m=1/3 to t=1, then -1/6 to t=2, then +1/6 to t=4.
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0,0,.001)) a=1; @(timer(1,0,.001)) b=-1; '
                '@(timer(2,0,.001)) c=.5; '
                'V(y,r)<+transition(a+b+c,0,3,6);')
        times = [0,.5,1,1.5,2,2.5,4,5]
        expected = [F(0),F(1,6),F(1,3),F(1,4),F(1,6),F(1,4),F(1,2),F(1,2)]
        for step in [5,.125]:
            result = execute(body,times,5,atol=1e-12,
                             declarations='real a,b,c;',step=step)
            y = result['nodes'].index('y')
            for row, exact in zip(result['solutions'],expected,strict=True):
                self.assertLessEqual(abs(F(row['voltages'][y])-exact),F(1e-12))

    def test_sampled_state_keeps_history_error_across_events(self):
        body = ('@(initial_step) begin a=0;b=0;c=0;end '
                '@(timer(0,0,.001)) a=1; @(timer(1,0,.001)) b=V(y,r); '
                '@(timer(2,0,.001)) c=1073741824*V(z,r)-357913941.3333333+1; '
                'V(y,r)<+transition(a,0,3,3); V(z,r)<+b; V(w,r)<+c;')
        declarations = 'real a,b,c; electrical z,w;'
        # At t=1, sampling 1/3 meets this budget. At t=2, amplifying the
        # retained uncertainty does not. Treating b as exact would accept it.
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body,[0,1,2,3],3,atol=1e-9,rtol=1e-9,declarations=declarations)
        result = execute(body,[0,1,2,3],3,atol=1e-6,rtol=1e-6,declarations=declarations)
        w = result['nodes'].index('dut:w')
        actual = result['solutions'][2]['voltages'][w]
        exact = F(1073741824,3)-F(357913941.3333333)+1
        self.assertLessEqual(abs(F(actual)-exact),F(1e-6))

    def test_initial_affine_input_roundoff_is_checked(self):
        # State coefficients remain in IR. Their exact sum is not the rounded
        # coefficient produced by nominal affine evaluation.
        body = '@(initial_step) a=1; V(y,r)<+transition(.1*a+.2*a,0,1,1);'
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body,[0,1],1,atol=1e-18)
        result = execute(body,[0,1],1,atol=1e-12)
        y = result['nodes'].index('y')
        self.assertLessEqual(abs(F(result['solutions'][0]['voltages'][y])-(F(.1)+F(.2))),F(1e-12))

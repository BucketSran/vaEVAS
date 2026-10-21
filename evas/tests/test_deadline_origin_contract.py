"""Shared held-time origins must survive fixed Transition shifts.

Expected waves come from Fraction recurrences and linear ramps, independently
of event discovery. A nonrepresentable reciprocal is deliberately retained.
No original benchmark model, settings or verdict are changed by these fixtures.
"""
import math
import os
from fractions import Fraction as Q
from pathlib import Path
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import instance, model

GUARDS = ['TIMER', 'TRANSITION', 'EVENT-ORDER', 'COMPOSE']
KERNEL = Path(os.environ.get('EVAS_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))
STOP = .55
COARSE = [0., STOP]
DENSE = [0., .05, .15, .265, .27, .275, .28, .30, .44, .45, .5, STOP]


def program(*, second_delay=0., second_rise=.01, reverse=False):
    outputs = [
        'V(y,r)<+transition(q,0,0.01,0.01);',
        f'V(a,r)<+transition(2*q,{second_delay!r},{second_rise!r},{second_rise!r});',
    ]
    if reverse:
        outputs.reverse()
    source = model('''@(initial_step) begin q=0; due=0.1; f=3; end
        @(timer(due)) begin q=1-q; due=$abstime+0.5/f; end
        ''' + ''.join(outputs), 'real q,due,f; electrical a;')
    return compile_sources({'deadline-origin.va': source}, [instance()])


def run(p, times):
    return transient(p, {'u': [[0., 0.], [STOP, 0.]]}, times,
                     stop=STOP, max_step=STOP,
                     vabstol=1e-8, reltol=0, kernel=KERNEL)


def expected(t, *, delay=0., rise=.01, gain=1):
    """Each target toggles at binary64(.1)+k*(exact 1/6).

    The longest delay+rise here is below 1/6, so ramps never overlap.
    This oracle uses no returned event time or simulator helper.
    """
    time, value = Q(t), Q(0)
    for k in range(3):
        arrival = Q(.1) + k * Q(1, 6) + Q(delay)
        if time < arrival:
            break
        old, target = Q(k % 2), Q((k + 1) % 2)
        fraction = min(Q(1), (time-arrival)/Q(rise))
        value = old + (target-old)*fraction
    return gain*value


class DeadlineOriginContract(unittest.TestCase):
    def assert_wave(self, result, times, *, delay=0., rise=.01):
        for time, row in zip(times, result['solutions']):
            for node, gain, shift, duration in [
                    ('y', 1, 0., .01), ('dut:a', 2, delay, rise)]:
                actual = Q(row['voltages'][result['nodes'].index(node)])
                self.assertLessEqual(abs(actual-expected(
                    time, delay=shift, rise=duration, gain=gain)), Q(1e-8))
        self.assertEqual(result['transient']['states'][-1][0], 1.)
        self.assertEqual(len(result['transient']['events']), 3)

    def test_shared_nonpoint_held_epoch_equal_shifts_match_independent_ramps(self):
        # RED target: second nonpoint timer creates two coincident end boxes
        # with no exact root. Equality must come from their shared origin,
        # never merely equal outward bounds.
        p = program()
        coarse = run(p, COARSE)
        dense = run(p, DENSE)
        self.assert_wave(coarse, COARSE)
        self.assert_wave(dense, DENSE)
        self.assertEqual(coarse['transient']['events'], dense['transient']['events'])
        self.assertEqual(coarse['solutions'][-1], dense['solutions'][-1])

    def test_shared_origin_different_fixed_shifts_preserve_physical_waveforms(self):
        # A representable shift changes the physical waveform. It cannot be
        # merged merely because the callback origin was shared.
        p = program(second_delay=.03125)
        result = run(p, DENSE)
        self.assert_wave(result, DENSE, delay=.03125)
        row = result['solutions'][DENSE.index(.28)]
        self.assertEqual(row['voltages'][result['nodes'].index('y')], 0.)
        self.assertEqual(row['voltages'][result['nodes'].index('dut:a')], 2.)

    def test_nextafter_duration_and_declaration_order_do_not_merge_histories(self):
        rise = math.nextafter(.01, math.inf)
        normal = run(program(second_rise=rise), DENSE)
        reverse = run(program(second_rise=rise, reverse=True), DENSE)
        self.assert_wave(normal, DENSE, rise=rise)
        self.assert_wave(reverse, DENSE, rise=rise)
        self.assertEqual(normal['transient']['events'], reverse['transient']['events'])
        for left, right in zip(normal['solutions'], reverse['solutions']):
            for node in ['y', 'dut:a']:
                self.assertEqual(left['voltages'][normal['nodes'].index(node)],
                                 right['voltages'][reverse['nodes'].index(node)])

    def test_unproved_irrational_interrupted_deadlines_remain_rejected(self):
        # Distinct obligation: equal interval boxes without a shared proven
        # deadline origin must retain the pre-existing rejection boundary.
        source = model('''@(initial_step) q=0;
            @(cross(pow(V(u,r),2)-2,1,1e-9,1e-9)) q=1;
            @(timer(0.6,0,1e-9)) q=2;
            V(y,r)<+transition(q,0,1);
            V(a,r)<+transition(2*q,0,1);''', 'real q; electrical a;')
        p = compile_sources({'unknown-origin.va': source}, [instance()])
        with self.assertRaises(KernelError) as caught:
            transient(p, {'u': [[0.,0.], [2.,6.]]}, [0.,.75,2.],
                      stop=2., max_step=.05, kernel=KERNEL)
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
        self.assertIn('ordering of operator deadlines', caught.exception.detail['message'])

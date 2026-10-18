"""Past one-shot held timers are empty until a later event changes their due time.

VAMS LRM2.4 timer rules make a nonpositive-period occurrence conditional on its
start being in the future. The independent ramp crosses0.5 at t=0.5, writes a
new due time0.625, then the timer samples the ramp as0.625 exactly once.
"""
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

GUARDS = ['TIMER', 'EVENT-ORDER']


class HeldTimerClosure(unittest.TestCase):
    def test_past_one_shot_is_empty_and_later_cross_rearms_it(self):
        for period in (0, -1):
            with self.subTest(period=period):
                source = model('''@(initial_step) begin due=-1; q=0; end
                    @(cross(V(u,r)-0.5,+1)) due=0.625;
                    @(timer(due,'''+str(period)+''')) q=V(u,r);
                    V(y,r)<+transition(q,0,0.01,0.01);''', 'real due,q;')
                program = compile_sources({'past-held-timer.va':source}, [instance()])
                result = transient(program, {'u':[[0,0],[1,1]]}, [0,0.25,0.6,0.75,1],
                                   stop=1,max_step=1,kernel=KERNEL)
                output = result['nodes'].index('y')
                self.assertEqual([row['voltages'][output] for row in result['solutions']],
                                 [0,0,0,0.625,0.625])
                self.assertEqual([event['time'] for event in result['transient']['events']],
                                 [0.5,0.625])

    def test_negative_start_with_positive_period_stays_rejected(self):
        # A positive period could create later occurrences. Empty-calendar
        # admission for a past one-shot must not silently suppress that regime.
        source = model('''@(initial_step) begin due=-1; q=0; end
            @(timer(due,0.25)) q=1; V(y,r)<+q;''', 'real due,q;')
        program = compile_sources({'negative-periodic-start.va':source}, [instance()])
        with self.assertRaisesRegex(KernelError, 'cannot certify dynamic timer start or period regime'):
            transient(program, {'u':[[0,0],[1,1]]}, [0,1], stop=1,max_step=1,kernel=KERNEL)

    def test_uncertain_source_cannot_turn_a_past_timer_into_a_certified_schedule(self):
        # Source uncertainty plus held timers remains outside the public
        # time-shape contract. Past one-shot admission must not bypass that
        # earlier gate. This does not exercise scheduler interval-sign checks.
        source = model('''@(initial_step) begin due=-1; q=0; end
            @(timer(0.25)) due=V(u,r);
            @(timer(due)) q=1; V(y,r)<+q;''', 'real due,q;')
        program = compile_sources({'uncertain-start-sign.va':source}, [instance()])
        with self.assertRaises(KernelError) as failure:
            transient(program, {'u':[[0,0],[1,0]]}, [0,1], stop=1,max_step=1,
                      source_errors={'u':0.01},kernel=KERNEL)
        self.assertEqual(failure.exception.detail['kind'], 'unsupported_source_uncertainty')

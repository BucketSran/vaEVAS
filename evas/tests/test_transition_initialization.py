"""Final zero-time seeds through the public compiler/kernel interface.

DC seeds, event counts and integral initial conditions are independent answers.
"""
GUARDS = ["TIMED-OPERATOR", "LAPLACE", "DYNAMICS", "COMPOSE"]

import unittest

from evas import CompileError, KernelError
from test_transition import run_transition


class FinalInitialHistory(unittest.TestCase):
    def values(self, result):
        index = result['nodes'].index('y')
        return [row['voltages'][index] for row in result['solutions']]

    def test_changed_fixed_zero_timer_seeds_final_point(self):
        for old, new in [(1, 0), (0, 1)]:
            result = run_transition(
                f'@(initial_step) a={old}; @(timer(0,0,0.001)) a={new}; '
                'V(y,r)<+transition(a,0.125,0.5,0.5);', [0, .25, 1], 1)
            self.assertEqual(self.values(result), [new] * 3)
            self.assertEqual(len(result['transient']['events']), 1)

    def test_filter_uses_the_same_final_dc_seed(self):
        result = run_transition(
            '@(initial_step) a=0; @(timer(0,0,0.001)) a=1; '
            "V(e,r)<+transition(a,0.125,0.5,0.5); "
            "V(y,r)<+laplace_nd(V(e,r),'{1},'{1,0.25});",
            [0, .25, 1], 1, declarations='real a; electrical e;')
        for value in self.values(result):
            self.assertAlmostEqual(value, 1, delta=2e-12)

    def test_integral_preserves_its_own_initial_condition(self):
        result = run_transition(
            '@(initial_step) a=0; @(timer(0,0,0.001)) a=1; '
            'V(e,r)<+transition(a,0.125,0.5,0.5); V(y,r)<+idt(V(e,r),0.75);',
            [0, .25, 1], 1, declarations='real a; electrical e;')
        self.assertEqual(self.values(result), [.75, 1, 1.75])

    def test_non_idempotent_or_body_runs_once_and_positive_neighbor_remains(self):
        result = run_transition(
            '@(initial_step) a=0; '
            '@(timer(0,0,0.001) or timer(0,0,0.002)) a=a+1; '
            '@(timer(0.25,0,0.001)) a=a+1; '
            'V(y,r)<+transition(a,0,0.5,0.5);', [0, .25, .5, .75, 1], 1)
        self.assertEqual(self.values(result), [1, 1, 1.5, 2, 2])
        events = result['transient']['events']
        self.assertEqual([e['time'] for e in events], [0, .25])
        self.assertEqual(events[0]['before'][0], 0)
        self.assertEqual(events[0]['after'][0], 1)
        self.assertEqual(len(events[0]['fired_triggers']), 2)

    def test_ordered_updates_and_independent_blocks_are_preserved(self):
        result = run_transition(
            '@(initial_step) begin a=0; b=2; end '
            '@(timer(0,0,0.001)) begin a=2; a=a+1; end '
            '@(timer(0,0,0.001)) b=1; '
            'V(y,r)<+transition(a+b,0.125,0.5,0.5);', [0, .5, 1], 1)
        self.assertEqual(self.values(result), [4] * 3)
        self.assertEqual(len(result['transient']['events']), 2)

    def test_unchanged_seed_retains_mixed_histories_and_unrelated_internal_read(self):
        for update in ['a=a;', 'a=a+1; a=a-1;', 'a=1;',
                       'if(V(u,r)>0.5) a=a; else begin a=a+1; a=a-1; end']:
            result = run_transition(
                '@(initial_step) begin a=1; b=0; end '
                f'@(timer(0,0,0.001)) begin {update} b=V(e,r); end '
                'V(e,r)<+2; V(y,r)<+transition(a,0.125,0.5,0.5)+idt(1,0.75);',
                [0, .25, 1], 1, declarations='real a,b; electrical e;')
            self.assertEqual(self.values(result), [1.75, 2, 2.75])
            self.assertEqual(result['transient']['events'][0]['after'][1], 2)

    def test_unchanged_seed_preserves_independent_filter_and_math_histories(self):
        for history in ["laplace_nd(V(u,r),'{1},'{1,0.25})", 'sin(V(u,r))']:
            result = run_transition(
                '@(initial_step) begin a=1; b=0; end '
                '@(timer(0,0,0.001)) begin a=a; b=V(e,r); end '
                f'V(e,r)<+2; V(y,r)<+transition(a,0.125,0.5,0.5)+{history};',
                [0, .25, 1], 1, declarations='real a,b; electrical e;')
            self.assertEqual(self.values(result), [1] * 3)
            self.assertEqual(result['transient']['events'][0]['after'][1], 2)

    def test_unchanged_seed_does_not_skip_writer_and_integer_validation(self):
        for declarations, body in [
            ('real a,b;', '@(timer(0,0,0.001)) a=a; @(timer(0,0,0.001)) a=a;'),
            ('real a; integer b;', '@(timer(0,0,0.001)) begin a=a; b=0.5; end'),
        ]:
            with self.assertRaises((CompileError, KernelError)):
                run_transition('@(initial_step) begin a=1; b=0; end ' + body +
                               'V(y,r)<+transition(a,0,0.5,0.5);', [0, 1], 1,
                               declarations=declarations)

    def test_changed_seed_rejects_unproved_other_histories_and_calendars(self):
        for suffix in [
            'V(y,r)<+transition(a,0,0.5,0.5)+idt(1,0.75);',
            '@(timer(b,0,0.001)) b=b+1; V(y,r)<+transition(a,0,0.5,0.5);',
            '@(cross(V(u,r)-V(e,r),1)) b=b+1; '
            'V(e,r)<+idt(1,0.75); V(y,r)<+transition(a,0,0.5,0.5);',
        ]:
            with self.assertRaises(KernelError) as caught:
                run_transition('@(initial_step) begin a=0; b=0.5; end '
                               '@(timer(0,0,0.001)) a=1; ' + suffix, [0, 1], 1,
                               declarations='real a,b; electrical e;')
            self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')
            self.assertEqual(caught.exception.diagnostic['category'], 'unsupported')
            self.assertEqual(caught.exception.diagnostic['capability'], 'COMPOSE')

    def test_changed_seed_rejects_nonpoint_state_certificate(self):
        with self.assertRaises(KernelError) as caught:
            run_transition('@(initial_step) a=0.1; @(timer(0,0,0.001)) a=a+0.2; '
                           'V(y,r)<+transition(a,0,0.5,0.5);', [0, 1], 1)
        self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')

    def test_changed_seed_rejects_hidden_internal_read_in_unselected_arm(self):
        with self.assertRaises(KernelError) as caught:
            run_transition('@(initial_step) a=0; '
                           '@(timer(0,0,0.001)) if(V(u,r)>0.5) a=V(e,r); else a=1; '
                           'V(e,r)<+2; V(y,r)<+transition(a,0,0.5,0.5);', [0, 1], 1,
                           declarations='real a; electrical e;')
        self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')

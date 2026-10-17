"""Held-state event decisions use accepted bounds and source statement order."""
GUARDS = ["EVENT-ORDER", "EVENT-CONDITIONS"]

import unittest
from fractions import Fraction as F

from evas import KernelError
from test_event_conditions import execute, source, states
from test_affine import model


class OrderedStateConditions(unittest.TestCase):
    def test_predicate_sees_prior_increment_and_accepted_next_event_state(self):
        text = source('q=q+1; if(q>=2) q=0;', kind='integer')
        self.assertEqual(states(execute(text)), [0, 1, 0])

    def test_following_predicate_sees_selected_nested_branch_assignment(self):
        text = source('if(q>0) q=3; else q=2; if(q>2) q=7; else q=9;', kind='integer')
        self.assertEqual(states(execute(text)), [0, 9, 7])

    def test_assignment_select_is_replayed_before_state_predicate(self):
        text = source('q=V(u,r)>=0.5 ? 2 : 3; if(q>2) q=q+10; else q=q+20;', kind='integer')
        self.assertEqual(states(execute(text)), [0, 22, 22])

    def test_state_decision_does_not_depend_on_observation_grid(self):
        text = source('q=q+1; if(q>=2) q=0;', kind='integer')
        result = execute(text, times=[0, .125, .5, .75, 1], step=.0625)
        self.assertEqual(states(result), [0, 0, 1, 1, 0])

    def test_exact_prior_sample_decides_sign_but_true_band_stays_unknown(self):
        # The original midpoint difference is exactly1/2^56, even though
        # floating subtraction rounds to zero. A source proof decides its sign.
        text = source('q=V(u,r)-0.5; if(q>0) q=1; else q=-1;')
        self.assertGreater((F(.1)+F(.9))/2-F(.5),0)
        self.assertEqual(states(execute(text,points=[[0,.1],[1,.9]])),[0,1,1])
        # Preserve a truly unknown sign, rather than only arithmetic width.
        with self.assertRaisesRegex(KernelError, 'event_condition'):
            execute(text,points=[[0,.1],[1,.9]],source_errors={'u':1e-12})

    def test_joint_voltage_feedback_is_rejected_when_used_by_later_state_predicate(self):
        text = source('q=0.5*V(y,r)+1; if(q>1) q=2; else q=3;')
        with self.assertRaisesRegex(KernelError, 'unsupported_condition'):
            execute(text)

    def test_condition_reads_other_block_state_from_an_earlier_event(self):
        text = model('''@(initial_step) begin q=0; p=0; end
            @(timer(0.25,0,0.001)) q=1;
            @(timer(0.5,0,0.001)) if(q>0) p=7; else p=9;
            V(y,r)<+p;''', 'integer q,p;')
        result = execute(text, times=[0, .25, .5, 1])
        self.assertEqual(result['transient']['states'], [[0, 0], [1, 0], [1, 7], [1, 7]])

    def test_simultaneous_condition_state_read_remains_structurally_rejected(self):
        for predicate in ('q', '0*q', 'q-q', '1e-200*(1e-200*q)'):
            text = model(f'''@(initial_step) begin q=0; p=0; end
                @(timer(0.5,0,0.001)) q=1;
                @(timer(0.5,0,0.001)) if({predicate}>0) p=7; else p=9;
                V(y,r)<+p;''', 'integer q,p;')
            with self.subTest(predicate=predicate), self.assertRaisesRegex(KernelError, 'unsupported_cross'):
                execute(text)

    def test_unselected_predicate_does_not_read_other_block_state(self):
        text = model('''@(initial_step) begin q=0; p=0; end
            @(timer(0.5,0,0.001)) q=1;
            @(timer(0.5,0,0.001)) if(1>0) p=7; else if(q>0) p=9;
            V(y,r)<+p;''', 'integer q,p;')
        self.assertEqual(execute(text)['transient']['states'], [[0, 0], [1, 7], [1, 7]])

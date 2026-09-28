"""Constructed method controls; these do not run or certify any simulator."""
from fractions import Fraction as Q
import unittest

from history import Event, check_history, value_at, value_bounds


class HistoryCalibration(unittest.TestCase):
    def setUp(self):
        self.ramp = [Event(0, 1, 1, 0, '0.1')]

    def check(self, rows, events=None, **kwargs):
        return check_history(rows, events or self.ramp, initial=0,
                             epsilon=kwargs.pop('epsilon', '0.01'), **kwargs)

    def test_legal_global_offset_and_nominal_trace(self):
        for rows in [[('0.25', '0.25'), ('0.75', '0.75')],
                     [('0.25', '0.20'), ('0.75', '0.70')]]:
            result = self.check(rows)
            self.assertEqual(result['status'], 'P')
            self.assertIsNotNone(result['witness_offsets'])
            self.assertEqual(result['formal_dvs_qualification'], 'I')
            self.assertFalse(result['continuous_time_qualified'])

    def test_pointwise_legal_but_no_shared_event(self):
        result = self.check([('0.25', '0.25'), ('0.75', '0.65')])
        self.assertEqual(result['status'], 'F')
        self.assertEqual(result['reason'], 'outer_domain_proved_empty')

    def test_uncertainty_three_way_decision(self):
        fixed = [Event(0, 0, 1, 0, 0)]
        for y, expected in [('0.0007', 'P'), ('0.0009', 'I'), ('0.0013', 'F')]:
            with self.subTest(y=y):
                result = self.check([(2, y)], fixed, epsilon='0.001', uncertainty='0.0002')
                self.assertEqual(result['status'], expected)

    def test_exact_closed_threshold(self):
        result = self.check([(2, '1.01')], epsilon='0.01')
        self.assertEqual(result['status'], 'P')

    def test_sample_value_and_edge_share_event(self):
        event = [Event(0, 1, 1, 0, '0.1', 1)]
        # At t=.5 y=.5 requires e=0; the held 1.1 requires e=.1.
        result = self.check([('0.5', '0.5'), (2, '1.1')], event, epsilon='0.001')
        self.assertEqual(result['status'], 'F')
        good = self.check([('0.5', '0.4725'), (2, '1.05')], event, epsilon='0.001')
        self.assertEqual(good['status'], 'P')

    def test_previous_sample_persists_into_next_edge(self):
        events = [Event(0, 1, 1, 0, '0.1', 1), Event(2, 0, 1, 0, 0)]
        self.assertEqual(self.check([('1.5', '1.05'), ('2.5', '0.525')], events)['status'], 'P')
        self.assertEqual(self.check([('1.5', '1.10'), ('2.5', '0.50')], events, epsilon='0.001')['status'], 'F')

    def test_wrong_shape_and_missing_edge(self):
        for rows in [[('0.25', '0.24'), ('0.75', '0.74'), (2, 0)],
                     [('0.25', '0.25'), ('0.5', '0.8'), ('0.75', '0.65')]]:
            self.assertEqual(self.check(rows)['status'], 'F')
        # A 2% stretched full edge cannot share the contract's single start.
        rows = [(Q(1, 4), Q(25, 102)), (Q(3, 4), Q(75, 102))]
        self.assertEqual(self.check(rows, epsilon='0.001')['status'], 'F')

    def test_budget_is_inconclusive_not_failure(self):
        self.assertEqual(self.check([('0.25', '0.2')], max_boxes=0)['status'], 'I')

    def test_interval_contains_exact_values(self):
        events = [Event(0, 1, 1, 0, '0.1', 1), Event(2, '-0.5', '0.5', 0, '0.1', '-0.5')]
        box = [(Q(0), Q(1, 10))] * 2
        for t in map(Q, ['0', '.05', '.5', '1.05', '1.5', '2.05', '2.3', '2.6', '3']):
            lo, hi = value_bounds(t, events, box, Q(0))
            for a in [Q(0), Q(1, 20), Q(1, 10)]:
                for b in [Q(0), Q(1, 20), Q(1, 10)]:
                    value = value_at(t, events, [a, b], Q(0))
                    self.assertLessEqual(lo, value)
                    self.assertGreaterEqual(hi, value)

    def test_empty_nan_duplicate_and_bad_budget_are_invalid(self):
        for rows in [[], [(0, 'NaN')], [(0, 0), (0, 1)], [(1, 0), (0, 0)]]:
            self.assertEqual(self.check(rows)['reason'], 'invalid_observation_or_contract')
        self.assertEqual(self.check([(0, 0)], uncertainty='-1')['status'], 'I')

    def test_overlapping_or_reversed_domains_not_silently_supported(self):
        for events in [[Event(0, 1, 2, 0, 1), Event(1, 0, 1, 0, 1)],
                       [Event(0, 1, 1, '0.2', '0.1')]]:
            self.assertEqual(self.check([(0, 0)], events)['status'], 'I')

    def test_same_wrong_data_twice_stays_wrong(self):
        rows = [('0.25', '0.25'), ('0.75', '0.65')]
        self.assertEqual([self.check(rows)['status'] for _ in range(2)], ['F', 'F'])


if __name__ == '__main__':
    unittest.main()

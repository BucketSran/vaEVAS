"""Known-good and known-bad controls for the F2 analytic measurement checker."""
import copy
import unittest

from history_windows import validate


class HistoryWindowCheckerCalibration(unittest.TestCase):
    def setUp(self):
        self.request = {'transient': {'output_times': [0., 1.]}}
        # Closed-form solution at t=1 is 1+exp(-1), independently tabulated.
        self.response = {'nodes': ['0', 'y', 'q'], 'solutions': [
            {'voltages': [0., 0., 0.]}, {'voltages': [0., 1.3678794411714423, 1.]}],
            'transient': {'times': [0., 1.], 'events': [{'time': .53}]}}

    def test_joint_analytic_reference_is_accepted(self):
        result = validate(self.request, self.response, 'joint-history-offset')
        self.assertEqual(result['outputs'], 2)
        self.assertEqual(result['events'], 1)

    def test_wrong_voltage_is_rejected(self):
        wrong = copy.deepcopy(self.response)
        wrong['solutions'][1]['voltages'][1] = 1.4
        with self.assertRaises(AssertionError):
            validate(self.request, wrong, 'joint-history-offset')

    def test_wrong_root_or_incomplete_observations_are_rejected(self):
        wrong = copy.deepcopy(self.response)
        wrong['transient']['events'][0]['time'] = .54
        with self.assertRaises(AssertionError):
            validate(self.request, wrong, 'joint-history-offset')
        wrong = copy.deepcopy(self.response)
        wrong['solutions'].pop()
        with self.assertRaises(AssertionError):
            validate(self.request, wrong, 'joint-history-offset')
        wrong = copy.deepcopy(self.response)
        wrong['transient']['times'] = [0., .5]
        with self.assertRaises(AssertionError):
            validate(self.request, wrong, 'joint-history-offset')


if __name__ == '__main__':
    unittest.main()

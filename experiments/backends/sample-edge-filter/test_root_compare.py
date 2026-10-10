import math
import unittest
from root_compare import TIMES, acceptance_observed, filter_error, oracle


class RootComparison(unittest.TestCase):
    def test_old_rejection_and_new_recovery_are_distinct_obligations(self):
        case = {'root_tolerance': 1e-3}
        rejected = {'status': 'REJECTED', 'reason': 'waveform_accuracy: budget exceeded'}
        self.assertTrue(acceptance_observed(rejected, case, 1e-10, 'retained-window'))
        self.assertFalse(acceptance_observed(rejected, case, 1e-10, 'adaptive-root'))
        accepted = {'status': 'ACCEPTED', 'within_requested_voltage_budget': True}
        self.assertTrue(acceptance_observed(accepted, case, 1e-10, 'adaptive-root'))
        accepted['within_requested_voltage_budget'] = False
        self.assertFalse(acceptance_observed(accepted, case, 1e-10, 'adaptive-root'))

    def test_same_fixed_observations_detect_corruption(self):
        rows = [{'time': t, 'y': oracle(t, .125)} for t in TIMES]
        self.assertEqual(filter_error(rows, .125), 0)
        rows[2]['y'] += 1e-4
        self.assertGreater(filter_error(rows, .125), 9e-5)
        rows[2]['y'] = math.nan
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            filter_error(rows, .125)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            filter_error(rows[:-1], .125)


if __name__ == '__main__':
    unittest.main()

"""Calibrate the triangle benchmark's independent accuracy checks."""
import copy
import math
import unittest

from profile_requests import validate


class TriangleAccuracy(unittest.TestCase):
    def setUp(self):
        # Integrate a unit-height triangle and its negative over [0, 1].
        times = [i / 8 for i in range(9)]
        expected = [0., 1/32, 1/8, 7/32, 1/4, 7/32, 1/8, 1/32, 0.]
        self.request = {
            'transient': {'pwl': [[[0., 0.], [.25, 1.], [.5, 0.],
                                   [.75, -1.], [1., 0.]]], 'output_times': times},
            'tolerances': {'absolute': 1e-12, 'relative': 1e-10},
        }
        self.response = {
            'transient': {'times': times, 'events': []},
            'solutions': [{'voltages': [0., 0., y]} for y in expected],
            'observation_evidence': {
                'effective_controls': {'absolute_V': 1e-12, 'relative': 1e-10},
                'voltage_bounds_V': [[[0., 0.], [0., 0.], [y, y]] for y in expected],
            },
        }

    def test_exact_answer_passes(self):
        validate('pwl_idt-9', self.request, self.response)

    def test_close_value_with_false_enclosure_fails(self):
        value = math.nextafter(1/8, math.inf)
        self.response['solutions'][2]['voltages'][2] = value
        self.response['observation_evidence']['voltage_bounds_V'][2][2] = [value, value]
        with self.assertRaisesRegex(AssertionError, 'missing exact integral'):
            validate('pwl_idt-9', self.request, self.response)

    def test_exact_value_with_wide_enclosure_fails(self):
        self.response['observation_evidence']['voltage_bounds_V'][2][2] = [0., 1.]
        with self.assertRaisesRegex(AssertionError, 'enclosure over budget'):
            validate('pwl_idt-9', self.request, self.response)

    def test_missing_observation_fails(self):
        self.response['solutions'].pop()
        with self.assertRaises(AssertionError):
            validate('pwl_idt-9', self.request, self.response)

    def test_wrong_stimulus_fails(self):
        changed = copy.deepcopy(self.request)
        changed['transient']['pwl'][0][1][1] = 2.
        with self.assertRaises(AssertionError):
            validate('pwl_idt-9', changed, self.response)


if __name__ == '__main__':
    unittest.main()

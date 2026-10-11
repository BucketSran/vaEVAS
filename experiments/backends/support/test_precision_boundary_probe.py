import copy
from fractions import Fraction
import unittest

from precision_boundary_probe import roots_and_times, assess_boundaries, load_contract, pwl_exact


class BoundaryProbeCalibration(unittest.TestCase):
    def setUp(self):
        self.card = next(c for c in load_contract()['cards'] if c['id'] == 'SH-X-RAMP')
        self.roots, times = roots_and_times(self.card)
        self.rows = []
        for t in times:
            n = sum(Fraction(t) >= r for r in self.roots)
            y = self.card['initial_V'] if not n else float(pwl_exact(self.card['inputs']['u'], self.roots[n-1]))
            self.rows.append(dict(time=t, count=n, y=y, u=float(pwl_exact(self.card['inputs']['u'],t)),
                                  clk=float(pwl_exact(self.card['inputs']['clk'],t))))

    def test_correct_sides_never_claim_callback_qualification(self):
        result = assess_boundaries(self.card, self.rows)
        self.assertEqual(result['matching_counts'], 56)
        self.assertEqual(result['callback_qualification'], 'not_established')

    def test_one_ulp_early_and_stale_sides_are_detected(self):
        for k in (3, 4):
            rows = copy.deepcopy(self.rows)
            rows[k]['count'] = 1-rows[k]['count']
            result = assess_boundaries(self.card, rows)
            self.assertEqual(result['matching_counts'], 55)

    def test_wrong_hold_is_measured_separately_from_event_count(self):
        rows = copy.deepcopy(self.rows); rows[4]['y'] += .1
        result = assess_boundaries(self.card, rows)
        self.assertEqual(result['matching_counts'], 56)
        self.assertGreater(result['held_error_upper_V'], .09)

    def test_missing_duplicate_invalid_or_changed_fixture_refused(self):
        for rows in (self.rows[:-1], self.rows + self.rows[-1:], list(reversed(self.rows))):
            with self.assertRaises(ValueError): assess_boundaries(self.card, rows)
        changed = copy.deepcopy(self.card); changed['event_early_s'] = 1.
        with self.assertRaises(ValueError): assess_boundaries(changed, self.rows)


if __name__ == '__main__':
    unittest.main()

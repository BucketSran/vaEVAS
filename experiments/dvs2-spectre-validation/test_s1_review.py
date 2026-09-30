"""Independent S1 checker calibration; no simulator or private archive needed."""
import copy
from fractions import Fraction as F
from pathlib import Path
import unittest
from unittest.mock import patch

import s1_review
from run_suite import conditions, netlist


ROOT = Path(__file__).resolve().parents[2]
# Hand-derived knot values from N-V1-02, in nominal volts and t / (1 us).
# Affine input and output segments make rational interpolation exact here.
# Do not use the production reference/PWL helper to generate calibration rows.
INPUT_KNOTS = {
    'u': [F(0), F(2, 5), F(2, 5), F(-1, 5), F(-1, 5)],
    'v': [F(-1, 5), F(-1, 5), F(3, 10), F(3, 10), F(-1, 10)],
}
OUTPUT_KNOTS = {
    's1-default': [F(9, 40), F(33, 40), F(23, 40), F(-13, 40), F(-1, 8)],
    's1-override': [F(-13, 20), F(-17, 20), F(3, 20), F(9, 20), F(-7, 20)],
}


def rational_rows(name):
    if name == s1_review.REORDERED_ID:
        name = 's1-default'
    knots = dict(INPUT_KNOTS, vout=OUTPUT_KNOTS[name])
    result = []
    for tick in range(4001):
        x = F(tick, 1000)
        segment = min(int(x), 3)
        row = {'time': float(x/F(1000000))}
        for signal, values in knots.items():
            value = values[segment]+(x-segment)*(values[segment+1]-values[segment])
            row[signal] = float(value)
        result.append(row)
    return result


class S1Review(unittest.TestCase):
    def test_rational_positive_controls(self):
        for case in s1_review.conditions():
            with self.subTest(condition=case['id']):
                result = s1_review.check(rational_rows(case['id']), case['id'])
                self.assertEqual(result['status'], 'observations_within_targets')
                self.assertLess(result['analytic_max_error']['vout'], 2e-15)

    def test_fixture_does_not_use_production_oracle(self):
        with patch('check_results.reference', side_effect=AssertionError('shared oracle')), \
                patch('check_results.v1.pwl', side_effect=AssertionError('shared PWL')):
            for name in OUTPUT_KNOTS:
                self.assertEqual(len(rational_rows(name)), 4001)

    def test_freezing_either_input_is_rejected(self):
        for name, gains in [('s1-default', (1.5, -.5)), ('s1-override', (-.5, 2))]:
            for signal, gain in zip(('u', 'v'), gains):
                with self.subTest(condition=name, frozen=signal):
                    data = rational_rows(name)
                    initial = data[0][signal]
                    # Preserve the observed input; only the DUT output is stale.
                    for row in data:
                        row['vout'] += gain*(initial-row[signal])
                    result = s1_review.check(data, name)
                    self.assertEqual(result['status'], 'observed_violation')

    def test_ignored_parameter_override_is_rejected(self):
        data = rational_rows('s1-default')
        result = s1_review.check(data, 's1-override')
        self.assertEqual(result['status'], 'observed_violation')

    def test_last_contribution_wins_is_rejected(self):
        for name, bias in [('s1-default', .125), ('s1-override', -.25)]:
            with self.subTest(condition=name):
                data = rational_rows(name)
                for row in data:
                    row['vout'] = bias
                self.assertEqual(s1_review.check(data, name)['status'], 'observed_violation')

    def test_signed_tolerance_margins(self):
        # Exact-export screening only. This does not certify a physical
        # observation uncertainty bound, or equality at a rounded 1 mV edge.
        for name in OUTPUT_KNOTS:
            for magnitude, expected in [(0.0009, 'observations_within_targets'),
                                        (0.0011, 'observed_violation')]:
                for sign in (-1, 1):
                    with self.subTest(condition=name, offset=sign*magnitude):
                        data = rational_rows(name)
                        for row in data:
                            row['vout'] += sign*magnitude
                        self.assertEqual(s1_review.check(data, name)['status'], expected)

    def test_reordered_condition_changes_only_source_identity(self):
        historical = conditions()
        before = copy.deepcopy(historical)
        original, override, reordered = s1_review.conditions()
        self.assertEqual(len(historical), 31)
        self.assertNotIn(reordered['id'], {c['id'] for c in historical})
        expected = copy.deepcopy(original)
        expected.update(id=s1_review.REORDERED_ID, card=s1_review.SOURCE_CARD,
                        source_cards=[s1_review.SOURCE_CARD],
                        comparison_condition=original['id'])
        self.assertEqual(reordered, expected)
        self.assertEqual(override, next(c for c in historical if c['id']=='s1-override'))
        for profile in ('base', 'fine'):
            self.assertEqual(netlist(original, profile), netlist(reordered, profile))
        reordered['inputs']['u'][0] = (0, 99)
        self.assertEqual(original, next(c for c in before if c['id']=='s1-default'))
        self.assertEqual(conditions(), before)

    def test_dut_reorders_only_the_three_contributions(self):
        cases = ROOT/'evas/validation/cases'
        original = (cases/'n_v1_02/dut.va').read_text()
        reordered = (cases/s1_review.SOURCE_CARD/'dut.va').read_text()
        lines = original.splitlines(keepends=True)
        positions = [i for i, line in enumerate(lines) if '<+' in line]
        self.assertEqual(len(positions), 3)
        contributions = [lines[i] for i in positions]
        for i, line in zip(positions, reversed(contributions)):
            lines[i] = line
        self.assertEqual(reordered, ''.join(lines))

    def test_reordered_oracle_cannot_pass_two_equal_wrong_outputs(self):
        for offset in (0, .002):
            data = rational_rows('s1-default')
            for row in data:
                row['vout'] += offset
            expected = 'observed_violation' if offset else 'observations_within_targets'
            for name in ('s1-default', s1_review.REORDERED_ID):
                self.assertEqual(s1_review.check(data, name)['status'], expected)
        with self.assertRaises(ValueError):
            s1_review.check([], 's1-unknown')


if __name__ == '__main__':
    unittest.main()

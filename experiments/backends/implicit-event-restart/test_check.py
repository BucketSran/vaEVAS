"""Accept/reject calibration of the public compact-data checker, no simulators."""
import copy
from fractions import Fraction as Q
import json
import hashlib
import tempfile
from pathlib import Path
import unittest

import check


def exact_samples():
    # Hand-worked selected-branch samples, independent of check.answer.
    ys = ['1/4', '3/8', '1/2', '5/8', '3/4', '1', '5/4', '3/2', '7/4']
    ws = ['3', '25/8', '13/4', '27/8', '7/2', '29/8', '15/4', '31/8', '4']
    return [(Q(i,8), {'u':Q(0), 'y':Q(y), 'w':Q(w)}) for i,(y,w) in enumerate(zip(ys,ws))]


class CheckerCalibration(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((Path(__file__).parent/'records.json').read_text())

    def rejected(self):
        with self.assertRaises((ValueError, KeyError, TypeError)):
            check.analyze(self.data)

    def test_actual_positive_and_two_negative_completions_are_distinct(self):
        result = check.analyze(self.data)
        self.assertEqual(result['positive_model_finite_passes'], 1)
        self.assertEqual(result['evas_expected_rejection_controls'], 2)
        self.assertEqual(result['spectre_negative_completions_not_passes'], 2)
        self.assertEqual(sum(x['classification']=='finite_numeric_pass' for x in result['backend_matrix']), 2)

    def test_independent_exact_synthetic_answers_are_accepted(self):
        exact = exact_samples()
        result = check.original_math(exact, exact)
        self.assertTrue(all(value == 0 for node in result.values() for value in node.values()))

    def test_evas_wrong_value_is_rejected(self):
        self.data['cases']['original']['evas']['rows'][5]['voltages']['y'] = (1.0001).hex()
        self.rejected()

    def test_reference_wrong_value_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'][5]['voltages']['y'] = '1.0001'
        self.rejected()

    def test_paired_failure_is_not_hidden_by_two_individual_passes(self):
        # Both are within B of the independent answer, but their separation
        # exceeds the same paired budget. This exercises a distinct consumer.
        rows = exact_samples()
        other = copy.deepcopy(rows)
        rows[5][1]['y'] += Q('7.5e-8')
        other[5][1]['y'] -= Q('7.5e-8')
        with self.assertRaisesRegex(ValueError, 'paired'):
            check.original_math(rows, other)

    def test_missing_initial_observation_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'].pop(0)
        self.rejected()

    def test_missing_event_observation_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'].pop(4)
        self.rejected()

    def test_missing_stop_observation_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'].pop()
        self.rejected()

    def test_missing_evas_observation_is_rejected(self):
        self.data['cases']['original']['evas']['rows'].pop(4)
        self.rejected()

    def test_repeated_native_point_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'][5] = self.data['cases']['original']['spectre']['rows'][4]
        self.rejected()

    def test_unordered_native_points_are_rejected(self):
        rows = self.data['cases']['original']['spectre']['rows']
        rows[1], rows[2] = rows[2], rows[1]
        self.rejected()

    def test_lost_backend_matrix_entry_is_rejected(self):
        del self.data['cases']['singular-initial']['evas']
        self.rejected()

    def test_negative_case_cannot_be_relabelled_as_a_positive(self):
        self.data['cases']['constraint-change']['role'] = 'positive'
        self.rejected()

    def test_positive_flags_cannot_be_added_to_negative_case(self):
        self.data['cases']['singular-initial']['passed'] = True
        self.rejected()

    def test_process_error_cannot_replace_the_required_mathematical_rejection(self):
        self.data['cases']['singular-initial']['evas']['error']['kind'] = 'kernel_process'
        self.rejected()

    def test_evas_acceptance_cannot_count_as_a_rejection_control(self):
        self.data['cases']['constraint-change']['evas']['status'] = 'completed'
        self.data['cases']['constraint-change']['evas']['returncode'] = 0
        self.rejected()

    def test_negative_timeout_is_not_an_expected_rejection(self):
        self.data['cases']['singular-initial']['evas']['timeout'] = True
        self.rejected()

    def test_retained_disaster_recovery_warning_is_required(self):
        self.data['cases']['constraint-change']['spectre']['log_observations'] = []
        self.rejected()

    def test_a_second_missing_negative_point_cannot_be_hidden(self):
        self.data['cases']['constraint-change']['spectre']['rows'][5]['time'] = '.626'
        self.rejected()

    def test_wrong_singular_equilibrium_classification_is_rejected(self):
        self.data['cases']['singular-initial']['spectre']['rows'][4]['voltages']['y'] = '7'
        self.rejected()

    def test_unrelated_history_corruption_is_rejected(self):
        self.data['cases']['constraint-change']['spectre']['rows'][4]['voltages']['w'] = '9'
        self.rejected()

    def test_effective_setting_change_is_rejected(self):
        self.data['cases']['original']['spectre']['effective_from_psf']['reltol'] = '1e-3'
        self.rejected()

    def test_nonfinite_token_is_rejected(self):
        self.data['cases']['original']['spectre']['rows'][0]['voltages']['y'] = 'NaN'
        self.rejected()

    def test_qualification_cannot_be_promoted(self):
        self.data['qualification'] = 'Q3'
        self.rejected()

    def test_changed_retained_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'dut.va').write_bytes(b'original bytes')
            (base/'records.json').write_text('{}')
            expected = hashlib.sha256((base/'dut.va').read_bytes()).hexdigest()
            (base/'receipt.json').write_text(json.dumps({'retained_files_sha256': {'dut.va': expected}}))
            self.assertEqual(check.load_package(base), {})
            (base/'dut.va').write_bytes(b'changed bytes')
            with self.assertRaisesRegex(ValueError, 'retained identity changed'):
                check.load_package(base)

    def test_case_dictionary_order_does_not_change_physical_result(self):
        reference = check.analyze(self.data)
        self.data['cases'] = dict(reversed(list(self.data['cases'].items())))
        self.assertEqual(check.analyze(self.data), reference)


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Planned denominator regressions; no archives, simulator, or model execution."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'calibration_report_under_test', Path(__file__).with_name('calibration_report.py'))
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class PlannedConditionCoverage(unittest.TestCase):
    def test_complete_names_are_order_independent(self):
        report.require_condition_coverage(['a', 'b'], ['b', 'a'])

    def test_missing_condition_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'missing'):
            report.require_condition_coverage(['a', 'b'], ['a'])

    def test_empty_actual_is_not_vacuous_success(self):
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            report.require_condition_coverage(['a', 'b'], [])

    def test_duplicate_actual_cannot_replace_missing_condition(self):
        with self.assertRaisesRegex(ValueError, 'unique'):
            report.require_condition_coverage(['a', 'b'], ['a', 'a'])

    def test_duplicate_plan_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unique'):
            report.require_condition_coverage(['a', 'a'], ['a'])

    def test_empty_plan_and_actual_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'nonempty'):
            report.require_condition_coverage([], [])

    def test_same_count_with_unexpected_name_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unexpected'):
            report.require_condition_coverage(['a', 'b'], ['a', 'c'])


if __name__ == '__main__':
    unittest.main()

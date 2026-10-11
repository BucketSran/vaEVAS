"""Binding policy calibration: no looser fallback and no stale reuse."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from precision_binding import load_registry, resolve, prepare


class BindingCalibration(unittest.TestCase):
    def setUp(self):
        self.registry = {'schema_version': 1, 'id': 'precision-bindings-v1',
            'dependencies': {}, 'configurations': {'base': {'settings': {}, 'actual': {},
             'tool_identity': {'kernel_sha256': 'a'}, 'recipe_hashes': {}, 'callback_trace': False, 'evidence': {}}},
            'bindings': {
             'LP-RAMP/evas/Q1': {'status': 'qualified', 'configuration': 'base', 'requirements': {'voltage_budget_V': 1e-5}},
             'LP-RAMP/evas/Q3': {'status': 'unavailable', 'reasons': ['missing proof'], 'requirements': {'voltage_budget_V': 1e-7}}}}

    def test_no_silent_looser_target_or_unknown_case(self):
        self.assertEqual(resolve(self.registry, 'Q1', 'evas', 'LP-RAMP')['status'], 'qualified')
        self.assertEqual(resolve(self.registry, 'Q3', 'evas', 'LP-RAMP')['status'], 'unavailable')
        with self.assertRaises(ValueError): resolve(self.registry, 'Q1', 'evas', 'another-model')
        with self.assertRaises(ValueError): resolve(self.registry, 'Q0', 'evas', 'LP-RAMP')

    def test_tool_mismatch_invalidates_reuse(self):
        with self.assertRaisesRegex(ValueError, 'tool identity'):
            resolve(self.registry, 'Q1', 'evas', 'LP-RAMP', tool_identity={'kernel_sha256': 'b'})

    def test_dependency_drift_invalidates_registry(self):
        self.registry['dependencies'] = {'evas/validation/paper/precision-v2.json': 'bad'}
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'registry.json'; p.write_text(json.dumps(self.registry))
            with self.assertRaisesRegex(ValueError, 'recalibration'): load_registry(p)

    def test_unqualified_prepare_does_not_write(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'case'
            with self.assertRaisesRegex(ValueError, 'no qualified'):
                prepare(self.registry, 'Q3', 'evas', 'LP-RAMP', p, {'kernel_sha256': 'a'})
            self.assertFalse(p.exists())

    def test_changed_recipe_rejected_before_write(self):
        # A forged settings/recipe pair cannot become a runnable directory.
        self.registry['configurations']['base']['settings'] = {
            'id': 'base', 'reltol': 1e-5, 'vabstol_V': 1e-9, 'iabstol_A': 1e-13, 'step_units': 1/32}
        self.registry['configurations']['base']['recipe_hashes'] = {'request.json': 'bad'}
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'case'
            with self.assertRaisesRegex(ValueError, 'recipe differs'):
                prepare(self.registry, 'Q1', 'evas', 'LP-RAMP', p, {'kernel_sha256': 'a'})
            self.assertFalse(p.exists())


if __name__ == '__main__': unittest.main()

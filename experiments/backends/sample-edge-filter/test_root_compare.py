import math
import json
from pathlib import Path
import tempfile
import unittest
from root_compare import (BUDGETS, CASES, TIMES, acceptance_observed, compare,
                          filter_error, oracle, sha, validate_reference)


class RootComparison(unittest.TestCase):
    def reference(self, root):
        for name, (delay, tolerance) in CASES.items():
            work = root / name
            work.mkdir()
            (work / 'case.json').write_text(json.dumps(dict(
                delay=delay, root_tolerance=tolerance, eva_voltage_budgets=BUDGETS,
                stop=3., inputs={'u': [[0., 0.], [3., 3.]]})))
            (work / 'dut.va').write_text('fixture, not executed')
            (work / 'rows.json').write_text('[]')
        self.manifest(root)

    def manifest(self, root):
        (root / 'MANIFEST.json').write_text(json.dumps({
            str(p.relative_to(root)): sha(p) for p in root.glob('*/*') if p.is_file()}))

    def test_reference_denominator_survives_rehashed_partial_archive(self):
        for mutation in ('missing-case', 'missing-budget', 'duplicate-budget',
                         'untracked-source', 'changed-case'):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.reference(root)
                self.assertEqual(len(validate_reference(root)), 4)
                name = next(iter(CASES))
                path = root / name / 'case.json'
                if mutation == 'missing-case':
                    path.unlink()
                elif mutation != 'untracked-source':
                    case = json.loads(path.read_text())
                    if mutation == 'missing-budget':
                        case['eva_voltage_budgets'].pop()
                    elif mutation == 'duplicate-budget':
                        case['eva_voltage_budgets'][1] = case['eva_voltage_budgets'][0]
                    else:
                        case['delay'] = 99.
                    path.write_text(json.dumps(case))
                self.manifest(root)
                if mutation == 'untracked-source':
                    manifest_path = root / 'MANIFEST.json'
                    manifest = json.loads(manifest_path.read_text())
                    del manifest[f'{name}/dut.va']
                    manifest_path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'reference'):
                    validate_reference(root)

    def test_empty_reference_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reference = root / 'reference'
            reference.mkdir()
            (reference / 'MANIFEST.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'reference'):
                compare(reference, root / 'output', root / 'unused-kernel', 'adaptive-root')
            self.assertFalse((root / 'output' / 'RESULTS.json').exists())

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

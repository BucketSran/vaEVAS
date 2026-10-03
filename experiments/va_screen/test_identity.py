"""Identity checks must reject changed/missing calibration consumers."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from experiments.va_screen.identity import ROOT, snapshot_files, verify_current_inputs


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ["benchmark/tasks", "benchmark/checkers", "experiments/va_screen"]:
            shutil.copytree(ROOT / name, self.root / name, ignore=shutil.ignore_patterns("__pycache__"))

    def test_complete_snapshot_includes_shared_source_and_evidence(self):
        tasks = verify_current_inputs(self.root)
        self.assertEqual(len(tasks), 6)
        snapshot = snapshot_files(self.root, tasks)
        for name in ["benchmark/checkers/spectre_waveform.py", "experiments/va_screen/remote.py",
                     "experiments/va_screen/CALIBRATION.json", "experiments/va_screen/FROZEN_INPUTS.json"]:
            self.assertIn(name, snapshot)

    def test_changed_scoring_file_and_missing_file_fail(self):
        file = self.root / "benchmark/tasks/va01-and2/tests/cases.json"
        original = file.read_bytes()
        file.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            verify_current_inputs(self.root)
        file.unlink()
        with self.assertRaisesRegex(ValueError, "changed or missing"):
            verify_current_inputs(self.root)

    def test_shared_checker_cannot_drift_while_copies_remain_old(self):
        file = self.root / "benchmark/checkers/spectre_waveform.py"
        file.write_text(file.read_text() + "\n# changed source\n")
        with self.assertRaisesRegex(ValueError, "shared checker changed"):
            verify_current_inputs(self.root)

    def test_execution_copy_and_adapter_changes_fail(self):
        for name in ["benchmark/tasks/va01-and2/tests/verify.py", "experiments/va_screen/remote.py"]:
            file = self.root / name
            original = file.read_bytes()
            file.write_bytes(original + b"\n")
            with self.assertRaisesRegex(ValueError, "changed or missing"):
                verify_current_inputs(self.root)
            file.write_bytes(original)

    def test_failed_mutation_and_frozen_manifest_changes_fail(self):
        file = self.root / "experiments/va_screen/CALIBRATION.json"
        data = json.loads(file.read_text())
        data["mutation_reports"][0]["reward"] = 1
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "mutation calibration failed"):
            verify_current_inputs(self.root)
        manifest = self.root / "experiments/va_screen/FROZEN_INPUTS.json"
        manifest.write_bytes(manifest.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "manifest identity changed"):
            verify_current_inputs(self.root)

    def test_incomplete_positive_calibration_cannot_pass(self):
        file = self.root / "experiments/va_screen/CALIBRATION.json"
        data = json.loads(file.read_text())
        data["calibration_reports"][0]["cases"].pop()
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "reference calibration failed"):
            verify_current_inputs(self.root)

    def test_final_result_must_keep_each_logical_submission(self):
        file = self.root / "experiments/va_screen/RESULTS.json"
        data = json.loads(file.read_text())
        data["records"][-1] = data["records"][0]
        file.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "submission inventory mismatch"):
            verify_current_inputs(self.root)

    def test_final_result_cannot_change_grade_or_input_identity(self):
        file = self.root / "experiments/va_screen/RESULTS.json"
        original = file.read_text()
        for field, value in [("passed_conditions", 999), ("cases_sha256", "0" * 64)]:
            data = json.loads(original)
            data["records"][0][field] = value
            file.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "identity/count mismatch"):
                verify_current_inputs(self.root)


if __name__ == "__main__":
    unittest.main()

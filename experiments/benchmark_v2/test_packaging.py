"""Task synchronization must preserve the v2 public contract."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.benchmark_first_batch import sync_runtime


class V2PackagingTest(unittest.TestCase):
    def test_v2_sync_copies_its_runtime_without_legacy_submission_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkers = root / "benchmark/checkers"
            tests = root / "benchmark/tasks/v2-fixture/tests"
            checkers.mkdir(parents=True)
            tests.mkdir(parents=True)
            for name in ("v2_runtime", "v2_fixture", "adc_linearity", "circuit_task"):
                (checkers / (name + ".py")).write_text("# maintained " + name + "\n")
            (tests / "verify.py").write_text("from v2_runtime import main\nfrom v2_fixture import evaluate\n")
            (tests / "contract.json").write_text(json.dumps({"candidate_files": ["dut.va"]}))
            instruction = tests.parent / "instruction.md"
            public_text = "Implement the public circuit contract.\n"
            instruction.write_text(public_text)
            with patch.object(sync_runtime, "ROOT", root):
                count, stale = sync_runtime.sync()
                self.assertEqual(instruction.read_text(), public_text)
                self.assertEqual(count, 1)
                self.assertEqual({Path(name).name for name in stale},
                                 {"v2_runtime.py", "v2_fixture.py", "adc_linearity.py"})
                self.assertFalse((tests / "circuit_task.py").exists())
                self.assertEqual(sync_runtime.sync(check=True), (1, []))


if __name__ == "__main__":
    unittest.main()

"""The CI timing wrapper must preserve unittest failures and interrupted evidence."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


RUNNER = Path(__file__).resolve().parents[1] / "run_regression.py"


class RegressionRunnerTests(unittest.TestCase):
    def run_fixture(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_fixture.py").write_text(body)
            report = root / "report.json"
            summary = root / "summary.md"
            result = subprocess.run(
                [sys.executable, "-B", str(RUNNER), "--start-directory", str(root),
                 "--report", str(report)], capture_output=True, text=True,
                env=dict(os.environ, GITHUB_STEP_SUMMARY=str(summary)), timeout=20)
            payload = json.loads(report.read_text()) if report.exists() else None
            events = [json.loads(line) for line in report.with_suffix(".jsonl").read_text().splitlines()] \
                if report.with_suffix(".jsonl").exists() else []
            return result, payload, events, summary.read_text() if summary.exists() else ""

    def test_success_is_timed_and_skips_remain_visible(self):
        result, report, events, summary = self.run_fixture('''import unittest
class Cases(unittest.TestCase):
    def test_ok(self): pass
    @unittest.skip("fixture skip")
    def test_skip(self): pass
''')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(report["successful"])
        self.assertTrue(report["complete"])
        self.assertEqual(report["tests_run"], 2)
        self.assertEqual([t["outcome"] for t in report["tests"]], ["passed", "skipped"])
        self.assertTrue(all(t["seconds"] >= 0 for t in report["tests"]))
        self.assertEqual([e["event"] for e in events], ["start", "stop", "start", "stop"])
        self.assertIn("test_ok", summary)

    def test_failure_error_and_subtest_failure_cannot_become_green(self):
        result, report, _, _ = self.run_fixture('''import unittest
class Cases(unittest.TestCase):
    def test_error(self): raise RuntimeError("fixture error")
    def test_failure(self): self.fail("fixture failure")
    def test_subtest(self):
        with self.subTest(part="a"): self.fail("subtest failure")
        with self.subTest(part="b"): self.skipTest("later skip")
''')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIsNotNone(report, result.stderr)
        self.assertFalse(report["successful"])
        self.assertEqual([t["outcome"] for t in report["tests"]], ["error", "failed", "failed"])

    def test_class_setup_error_cannot_be_hidden_by_a_passing_test(self):
        result, report, _, _ = self.run_fixture('''import unittest
class Broken(unittest.TestCase):
    @classmethod
    def setUpClass(cls): raise RuntimeError("setup failed")
    def test_never_runs(self): pass
class Passing(unittest.TestCase):
    def test_ok(self): pass
''')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["errors"], 1)
        self.assertFalse(report["successful"])

    def test_zero_tests_is_not_success(self):
        result, report, _, _ = self.run_fixture("# empty discovery\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNotNone(report, result.stderr)
        self.assertFalse(report["successful"])
        self.assertEqual(report["tests_run"], 0)

    def test_interrupt_keeps_current_test_and_incomplete_status(self):
        result, report, events, _ = self.run_fixture('''import unittest
class Cases(unittest.TestCase):
    def test_interrupt(self): raise KeyboardInterrupt()
''')
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNotNone(report, result.stderr)
        self.assertFalse(report["complete"])
        self.assertFalse(report["successful"])
        self.assertEqual(report["tests"][0]["outcome"], "interrupted")
        self.assertEqual(events[0]["event"], "start")

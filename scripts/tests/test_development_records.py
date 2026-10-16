"""Review limits and timing failures/overlap must remain observable."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "development_records.py"
spec = importlib.util.spec_from_file_location("records", SCRIPT)
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


class RecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_long_or_multiple_reports_fail_without_modifying_evidence(self):
        p = self.root / "review.md"
        raw = "已检查。" * 100
        p.write_text(raw)
        self.assertFalse(records.check_review([p], 0)["passed"])
        p.write_text("未发现可行动问题。范围与限制见[原记录](https://example.com/" + "a" * 500 + ").")
        self.assertTrue(records.check_review([p], 0)["passed"])
        self.assertFalse(records.check_review([p, p], 0)["passed"])
        self.assertIn("a" * 500, p.read_text())

    def test_findings_limit_and_blank_summary(self):
        p = self.root / "review.md"
        p.write_text("问" * 800)
        self.assertTrue(records.check_review([p], 2)["passed"])
        p.write_text("问" * 801)
        self.assertFalse(records.check_review([p], 2)["passed"])
        p.write_text(" \n")
        self.assertFalse(records.check_review([p], 0)["passed"])

    def test_cli_reports_failure(self):
        p = self.root / "review.md"
        p.write_text("长" * 301)
        run = subprocess.run([sys.executable, str(SCRIPT), "check-review", str(p), "--findings", "0", '--json'], capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertFalse(json.loads(run.stdout)["passed"])

    def test_timers_preserve_failure_and_reject_duplicate_or_missing_stop(self):
        p = self.root / "timing.jsonl"
        with patch.object(records, "stamp", side_effect=[
            {"at": "2026-10-17T00:00:00+00:00", "monotonic_s": 100},
            {"at": "2026-10-17T00:00:10+00:00", "monotonic_s": 110},
        ]):
            records.start(p, "one", "review", "coordinator")
            records.stop(p, "one", "failed", "review.json", "missing evidence")
        before = p.read_bytes()
        for action in [lambda: records.start(p, "one", "review", "coordinator"),
                       lambda: records.stop(p, "one", "complete", "x", ""),
                       lambda: records.stop(p, "absent", "complete", "x", "")]:
            with self.assertRaises(ValueError):
                action()
        self.assertEqual(p.read_bytes(), before)
        self.assertEqual(records.read_events(p)[-1]["status"], "failed")
        self.assertEqual(records.summarize(p)["observed_union_s"], 10)
        self.assertEqual(records.summarize(p)['failures'], [
            {'id': 'one', 'status': 'failed', 'evidence': 'review.json', 'reason': 'missing evidence'}])

    def test_compact_summary_surfaces_failed_and_cancelled_evidence_without_mutating_log(self):
        p = self.root / 'timing.jsonl'
        for status in ('failed', 'cancelled'):
            records.start(p, status, 'validation', 'coordinator')
            records.stop(p, status, status, status + '.log', 'preserve this failure')
        records.start(p, 'pending', 'review', 'coordinator')
        before = p.read_bytes()
        report = self.root / 'summary.json'
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), 'time-summary', str(p),
                              '--report', str(report)], capture_output=True, text=True, check=True)
        for status in ('failed', 'cancelled'):
            self.assertIn(status + '.log', run.stdout)
        self.assertIn('pending', run.stdout)
        self.assertIn(str(report), run.stdout)
        self.assertEqual(len(json.loads(report.read_text())['failures']), 2)
        self.assertEqual(p.read_bytes(), before)

    def test_parallel_time_is_not_double_counted_and_open_timer_is_visible(self):
        p = self.root / "timing.jsonl"
        times = [{"at": f"2026-10-17T00:00:{s:02d}+00:00", "monotonic_s": 100 + s}
                 for s in (0, 5, 10, 15, 20)]
        with patch.object(records, "stamp", side_effect=times):
            records.start(p, "a", "review", "one")
            records.start(p, "b", "review", "two")
            records.stop(p, "a", "complete", "a.json", "")
            records.stop(p, "b", "complete", "b.json", "")
            records.start(p, "pending", "publication", "coordinator")
        result = records.summarize(p)
        self.assertEqual(sum(result["actor_phase_seconds"].values()), 20)
        self.assertEqual(result["observed_union_s"], 15)
        self.assertEqual(result["unfinished"], ["pending"])

    def test_clock_discontinuity_does_not_invent_duration(self):
        p = self.root / "timing.jsonl"
        with patch.object(records, "stamp", side_effect=[
            {"at": "2026-10-17T00:00:00+00:00", "monotonic_s": 100},
            {"at": "2026-10-17T00:00:10+00:00", "monotonic_s": 3},
        ]):
            records.start(p, "one", "validation", "coordinator")
            records.stop(p, "one", "cancelled", "log", "host restarted")
        result = records.summarize(p)
        self.assertEqual(result["observed_union_s"], 0)
        self.assertEqual(result["unknown_duration"], ["one"])


if __name__ == "__main__":
    unittest.main()

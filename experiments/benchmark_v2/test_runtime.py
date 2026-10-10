"""Verifier protocol tests using a process fixture, never simulator evidence."""
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark/checkers"))
from v2_runtime import verify


class RuntimeProtocolTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.tests = self.root / "tests"
        self.tests.mkdir()
        self.candidate = self.root / "candidate/dut.va"
        self.candidate.parent.mkdir()
        self.source = b'`define LEVEL 1\nmodule dut; analog $strobe("completed"); endmodule\n'
        self.candidate.write_bytes(self.source)
        (self.tests / "contract.json").write_text(json.dumps({"candidate_files": ["dut.va"]}))
        (self.tests / "cases.json").write_text(json.dumps([
            {"name": "probe", "netlist": "trusted fixed netlist", "stop": 1e-9, "signals": ["out"]}
        ]))
        self.binary = self.root / "fixture-simulator"
        self.binary.write_text('''#!/usr/bin/env python3
import pathlib, sys
if "-W" in sys.argv:
    print("protocol fixture, not Spectre")
    raise SystemExit(0)
pathlib.Path("executed.va").write_bytes(pathlib.Path("dut.va").read_bytes())
pathlib.Path("psf").mkdir()
pathlib.Path("psf/tran.tran.tran").write_text('VALUE\\n"time" 0\\n"out" 0\\n"time" 1e-9\\n"out" 1\\nEND\\n')
''')
        self.binary.chmod(0o700)

    def run_verifier(self, evaluate=lambda rows, case, work: {"passed": True}):
        with patch.dict(os.environ, {"SPECTRE": str(self.binary)}):
            return verify(self.candidate, self.root / "result", self.tests, evaluate)

    def test_valid_source_is_executed_unchanged_without_language_filter(self):
        report = self.run_verifier()
        self.assertEqual(report["reward"], 1)
        self.assertEqual((self.root / "result/probe/executed.va").read_bytes(), self.source)
        self.assertEqual(report["cases"][0]["status"], "graded")
        self.assertEqual(report["candidate_sha256"], hashlib.sha256(self.source).hexdigest())

    def test_backend_failure_is_unscored_even_if_log_claims_a_verdict(self):
        self.binary.write_text(self.binary.read_text().split('pathlib.Path("executed.va")')[0]
                               + 'print("passed=1 infrastructure_error=false")\nraise SystemExit(2)\n')
        report = self.run_verifier()
        self.assertIsNone(report["reward"])
        self.assertEqual(report["cases"][0]["status"], "execution_error")
        self.assertFalse((self.root / "result/reward.txt").exists())

    def test_checker_evidence_error_is_not_a_graded_failure(self):
        report = self.run_verifier(lambda rows, case, work: {
            "passed": False, "status": "evidence_error", "reason": "missing measurement event"})
        self.assertIsNone(report["reward"])

    def test_real_checker_failure_has_zero_score(self):
        report = self.run_verifier(lambda rows, case, work: {"passed": False, "maximum_error": 0.3})
        self.assertEqual(report["reward"], 0)
        self.assertEqual(report["status"], "completed")

    def test_support_cannot_replace_candidate_before_execution(self):
        cases = json.loads((self.tests / "cases.json").read_text())
        cases[0]["support"] = {"dut.va": "replacement"}
        (self.tests / "cases.json").write_text(json.dumps(cases))
        report = self.run_verifier()
        self.assertEqual(report["status"], "checker_error")
        self.assertIsNone(report["reward"])
        self.assertFalse((self.root / "result/probe").exists())

    def test_missing_required_waveform_never_produces_a_score(self):
        self.binary.write_text(self.binary.read_text().replace('"out"', '"unrelated"'))
        report = self.run_verifier()
        self.assertIsNone(report["reward"])
        self.assertEqual(report["cases"][0]["status"], "evidence_error")

    def test_mutating_an_immutable_fixture_invalidates_evidence(self):
        text = self.binary.read_text()
        self.binary.write_text(text + '\npathlib.Path("tb.scs").write_text("changed")\n')
        report = self.run_verifier()
        self.assertIsNone(report["reward"])
        self.assertEqual(report["cases"][0]["status"], "evidence_error")


if __name__ == "__main__":
    unittest.main()

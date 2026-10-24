"""Frozen IR31 rational-transition snapshots stay byte-stable."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "evas/tests/helpers/check_rational_transition_fixture.py"
FIXTURES = ROOT / "evas/tests/fixtures/rational-transition-rollback"


class RationalTransitionFreshness(unittest.TestCase):
    def test_check_compiles_current_frontend_without_rewriting_ir31(self):
        paths = [FIXTURES / name for name in ("dut.va", "good.json", "bad.json")]
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in paths}
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        for path, (data, stamp) in before.items():
            self.assertEqual(path.read_bytes(), data)
            self.assertEqual(path.stat().st_mtime_ns, stamp)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["frozen_schema"], 31)
        self.assertFalse(receipt["frozen_rewritten"])
        self.assertNotEqual(receipt["current_schema"], 31)
        self.assertEqual(receipt["source_sha256"], hashlib.sha256((FIXTURES / "dut.va").read_bytes()).hexdigest())
        self.assertNotEqual(receipt["good_sha256"], receipt["bad_sha256"])

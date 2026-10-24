"""History-consumer public and private obligations stay distinct."""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "evas/tests/helpers/check_history_consumer_fixture.py"
BUILDER = ROOT / "evas/rust_core/src/history_consumer_fixture.rs"


class HistoryConsumerFreshness(unittest.TestCase):
    def test_shared_builder_declares_both_obligations(self):
        stamp = BUILDER.stat().st_mtime_ns
        before = BUILDER.read_bytes()
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(BUILDER.read_bytes(), before)
        self.assertEqual(BUILDER.stat().st_mtime_ns, stamp)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["builder_sha256"], hashlib.sha256(before).hexdigest())
        self.assertFalse(receipt["public_pass_is_private_rollback_pass"])
        self.assertEqual(
            [item["parameter"] for item in receipt["variants"]],
            ["late_failure=false", "late_failure=true"],
        )

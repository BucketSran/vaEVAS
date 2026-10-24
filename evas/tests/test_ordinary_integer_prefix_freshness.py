"""Ordinary integer-prefix fixture freshness.

The VA and the request recipe stay the working source. The program inside
the JSON is a derived frontend snapshot. The check compares them and does
not write.
"""
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "evas/tests/helpers/check_ordinary_integer_prefix_fixture.py"
FIXTURES = ROOT / "evas/rust_core/tests/fixtures"
SOURCE = FIXTURES / "ordinary_integer_prefix_joint.va"
REQUEST = FIXTURES / "ordinary_integer_prefix_joint.request.json"


class OrdinaryIntegerPrefixFreshness(unittest.TestCase):
    def test_check_compares_public_frontend_without_writing(self):
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (SOURCE, REQUEST)}
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
        self.assertTrue(receipt["program_matches_frontend"])
        self.assertEqual(receipt["source_sha256"], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        request = json.loads(REQUEST.read_text())
        recipe = {key: request[key] for key in ("driven", "samples", "tolerances", "transient")}
        encoded = json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
        self.assertEqual(receipt["recipe_sha256"], hashlib.sha256(encoded).hexdigest())
        self.assertEqual(len(receipt["compiler_sha256"]), 64)
        self.assertNotEqual(receipt["source_sha256"], receipt["recipe_sha256"])
        self.assertIn("schema_version", receipt)

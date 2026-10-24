"""Shaped-range oracle freshness: check is read-only; write is explicit.

The committed JSON is a derived snapshot. Knots and query windows are the
source. Expected range bits are not an answer source.
"""
GUARDS = ["TIMED-OPERATOR", "DEV:fixture-freshness"]
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "evas/tests/helpers/generate_shaped_range_oracle.py"
FIXTURE = ROOT / "evas/rust_core/tests/fixtures/shaped-range-oracle.json"
SEMANTICS = "fraction_value_slope_enclosure_binary64_bits"


def load():
    spec = importlib.util.spec_from_file_location("shaped_range_oracle_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ShapedRangeOracleFreshness(unittest.TestCase):
    def setUp(self):
        self.before = FIXTURE.read_bytes()
        self.stamp = FIXTURE.stat().st_mtime_ns

    def tearDown(self):
        if FIXTURE.read_bytes() != self.before:
            FIXTURE.write_bytes(self.before)

    def test_import_and_default_check_do_not_write_the_snapshot(self):
        load()
        self.assertEqual(FIXTURE.stat().st_mtime_ns, self.stamp)
        completed = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(FIXTURE.read_bytes(), self.before)
        self.assertEqual(FIXTURE.stat().st_mtime_ns, self.stamp)
        receipt = json.loads(completed.stdout)
        self.assertEqual(receipt["oracle_semantics"], SEMANTICS)
        self.assertGreater(receipt["case_count"], 0)
        self.assertGreater(receipt["query_count"], receipt["case_count"])
        self.assertEqual(len(receipt["generator_sha256"]), 64)
        self.assertEqual(len(receipt["source_sha256"]), 64)

    def test_source_hash_is_the_knot_query_spec_not_expected_range_bits(self):
        module = load()
        cases = module.build_cases()
        info = module.receipt(cases)
        spec = json.dumps(module.specification(cases), sort_keys=True, separators=(",", ":"))
        expected_bits = json.dumps(
            [query["expected"] for case in cases for query in case["queries"]],
            sort_keys=True,
        )
        self.assertEqual(info["source_sha256"], hashlib.sha256(spec.encode()).hexdigest())
        self.assertNotEqual(
            info["source_sha256"], hashlib.sha256(expected_bits.encode()).hexdigest()
        )
        self.assertEqual(info["case_count"], len(cases))
        self.assertEqual(info["query_count"], sum(len(case["queries"]) for case in cases))

    def test_write_is_explicit_and_check_rejects_drift_without_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "oracle.json"
            destination.write_text("[]\n")
            drifted = destination.stat().st_mtime_ns
            rejected = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--output", str(destination)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(destination.read_text(), "[]\n")
            self.assertEqual(destination.stat().st_mtime_ns, drifted)
            written = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "--write", "--output", str(destination)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(written.returncode, 0, written.stderr)
            self.assertEqual(destination.read_bytes(), self.before)
        self.assertEqual(FIXTURE.read_bytes(), self.before)
        self.assertEqual(FIXTURE.stat().st_mtime_ns, self.stamp)


if __name__ == "__main__":
    unittest.main()

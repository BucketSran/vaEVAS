"""Check the public generator CLI with synthetic contracts, never EVAS outputs."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "traceability.py"


class TraceabilityChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write("scripts/traceability.py", SCRIPT.read_text())
        self.write("evas/docs/development/capability-evidence.md", """# Capabilities
## 能力矩阵
| 能力 ID | 契约 | 证据 |
| --- | --- | --- |
| TIMER | [Math](../math/events.md) | [Run](../../../experiments/receipt.json) |
| NONLINEAR | [Math](../math/solving.md) | [Run](../../../experiments/receipt.json) |
| QUALIFICATION | [Contract](../../validation/README.md) | [Run](../../../experiments/receipt.json) |
""")
        for path in ("evas/README.md", "evas/docs/math/events.md",
                     "evas/docs/math/solving.md", "evas/docs/math/continuous.md"):
            self.write(path, "# 实现范围\n## 稀疏分支与性能边界\n")
        for name in ("ANALOG_CONDITIONS_CONTRACT", "NONLINEAR_TRANSIENT_CONTRACT",
                     "TIMED_OPERATOR_CONTRACTS", "EVENT_CONDITIONS_CONTRACT",
                     "DYNAMICS_CONTRACTS", "LAPLACE_CONTRACTS", "README"):
            self.write(f"evas/validation/{name}.md", "# Contract\n")
        self.write("experiments/receipt.json", "{}\n")
        self.write("evas/tests/test_timer.py", 'GUARDS = ["TIMER"]\nraise RuntimeError("do not import tests")\n')
        self.write("evas/validation/cases/unmapped/dut.va", "// independent model\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-B", str(self.root / "scripts/traceability.py"), *args],
                              capture_output=True, text=True)

    def test_round_trip_is_read_only_and_includes_capabilities_and_evidence(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.root / "evas/docs/development/TRACEABILITY.md"
        text = output.read_text()
        self.assertIn("| TIMER", text)
        self.assertIn("| NONLINEAR", text)
        self.assertIn("../../../experiments/receipt.json", text)
        self.assertIn("case:unmapped", text)
        before = output.read_bytes(), output.stat().st_mtime_ns
        self.assertEqual(self.run_cli("--check").returncode, 0)
        self.assertEqual((output.read_bytes(), output.stat().st_mtime_ns), before)

    def test_stale_or_missing_matrix_fails_without_rewriting(self):
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        self.assertFalse((self.root / "evas/docs/development/TRACEABILITY.md").exists())
        self.assertEqual(self.run_cli().returncode, 0)
        self.write("evas/tests/test_timer.py", 'GUARDS = ["NONLINEAR"]\n')
        path = self.root / "evas/docs/development/TRACEABILITY.md"
        before = path.read_bytes()
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        self.assertEqual(path.read_bytes(), before)

    def test_human_overview_can_change_without_invalidating_evidence(self):
        self.assertEqual(self.run_cli().returncode, 0)
        path = self.root / "evas/docs/development/TRACEABILITY.md"
        before = path.read_bytes(), path.stat().st_mtime_ns
        self.write("evas/docs/CAPABILITIES.md", "# 能力概览\n\n给使用者的自由格式简表。\n")
        result = self.run_cli("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((path.read_bytes(), path.stat().st_mtime_ns), before)

    def test_invalid_tags_fail_in_both_modes(self):
        for declaration in ('pass', 'GUARDS = []', 'GUARDS = "TIMER"',
                            'GUARDS = [123]', 'GUARDS = ["TIMRE"]',
                            'GUARDS = ["case:missing"]', 'GUARDS = ["DEV:"]',
                            'GUARDS = ["TIMER", "TIMER"]',
                            'GUARDS = ["TIMER"]\nGUARDS = ["NONLINEAR"]'):
            with self.subTest(declaration=declaration):
                self.write("evas/tests/test_timer.py", declaration + "\n")
                for flags in ((), ("--check",)):
                    self.assertNotEqual(self.run_cli(*flags).returncode, 0)
                self.assertFalse((self.root / "evas/docs/development/TRACEABILITY.md").exists())

    def test_missing_contract_or_evidence_target_fails(self):
        for name in ("evas/validation/DYNAMICS_CONTRACTS.md", "experiments/receipt.json"):
            path = self.root / name
            old = path.read_text()
            path.unlink()
            with self.subTest(name=name):
                self.assertNotEqual(self.run_cli().returncode, 0)
            path.write_text(old)

    def test_annotated_tags_and_development_topics(self):
        self.write("evas/tests/test_timer.py", 'GUARDS: list[str] = ["case:unmapped", "DEV:tool-contract"]\n')
        self.assertEqual(self.run_cli().returncode, 0)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_missing_anchor_is_an_error(self):
        self.write("evas/docs/math/solving.md", "# Renamed heading\n")
        result = self.run_cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing local anchor", result.stderr)

    def test_empty_test_inventory_is_an_error(self):
        shutil.rmtree(self.root / "evas/tests")
        self.assertNotEqual(self.run_cli("--check").returncode, 0)


if __name__ == "__main__":
    unittest.main()

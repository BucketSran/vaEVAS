"""Check the public generator CLI with synthetic contracts, never EVAS outputs."""
from pathlib import Path
import importlib.util
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

    def catalog_fixture(self, *, corrupt=False):
        self.write("evas/capabilities/data/registry.json", "{}\n")
        self.write("evas/capabilities/registry.py", '''
class Catalog:
    def namespace_counts(self):
        return {'maintenance': {'methods': 2, 'generated': 0, 'entrypoints': 1}}
    def current(self, kind):
        if kind == 'asset':
            return [{'role': {'status': 'pending'}, 'consumer_status': 'partial'}]
        if kind == 'historical-audit-record':
            return [{'id': 'old-audit'}]
        return []
    def read_history(self, obj):
        HISTORY_CHECK
class Registry:
    def catalog(self):
        return Catalog()
def load(data_dir, *, root, repositories):
    if not (data_dir / 'registry.json').is_file() or repositories != {'vaevas': root}:
        raise ValueError('missing or incorrect catalogue source')
    return Registry()
'''.replace('HISTORY_CHECK', "raise ValueError('historical row drift')" if corrupt else 'return {}'))

    def test_explicit_catalogue_cli_renders_same_registry_and_checks_freshness(self):
        self.catalog_fixture()
        flags = ('--catalog-data', str(self.root / 'evas/capabilities/data'))
        result = self.run_cli(*flags)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = self.root / 'evas/docs/development/TRACEABILITY.md'
        self.assertIn('maintenance: 2 registered methods', output.read_text())
        self.assertIn('1 historical records verified', output.read_text())
        self.assertEqual(self.run_cli('--check', *flags).returncode, 0)

    def test_corrupt_historical_source_or_missing_catalogue_cannot_rewrite_view(self):
        self.assertEqual(self.run_cli().returncode, 0)
        output = self.root / 'evas/docs/development/TRACEABILITY.md'
        before = output.read_bytes()
        self.catalog_fixture(corrupt=True)
        flags = ('--catalog-data', str(self.root / 'evas/capabilities/data'))
        result = self.run_cli(*flags)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('historical row drift', result.stderr)
        self.assertEqual(output.read_bytes(), before)
        shutil.rmtree(self.root / 'evas/capabilities/data')
        self.assertNotEqual(self.run_cli(*flags).returncode, 0)
        self.assertEqual(output.read_bytes(), before)

    def test_rust_navigation_uses_verified_native_listing_denominator(self):
        spec = importlib.util.spec_from_file_location('traceability_view_fixture', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        class FixtureCatalog:
            def current(self, kind):
                return [{'collector': 'binary-listing', 'listing_profile': 'fixture-profile',
                         'listing_source': {'id': 'source-fixture'}}] if kind == 'entrypoint' else []
            def namespace_counts(self):
                return {'rust-tests': {'methods': 0, 'generated': 0, 'entrypoints': 1}}
            def bound(self, ref, kind):
                return ref
            def reconcile_rust_listing(self, receipt, *, profile):
                if receipt != {'fixture': True} or profile != 'fixture-profile':
                    raise ValueError('fixture source/profile changed')
                return {'tests_discovered': 3, 'ignored_tests_discovered': 1, 'binaries': [{}]}
        class FixtureRegistry:
            def catalog(self):
                return FixtureCatalog()
            def read_source(self, source):
                return b'{"fixture": true}'
        view = module.render_catalog_navigation(FixtureRegistry())
        self.assertIn('3 IDs in the archived native listing; 1 ignored; 1 binary entrypoints', view)
        self.assertNotIn('0 registered methods', view)

    def test_fast_metadata_consumer_accepts_the_complete_generated_view(self):
        self.catalog_fixture()
        data = self.root / 'evas/capabilities/data'
        result = self.run_cli('--catalog-data', str(data))
        self.assertEqual(result.returncode, 0, result.stderr)
        spec = importlib.util.spec_from_file_location('fast_metadata_consumer', SCRIPT.parent / 'ci_lint.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        command = next(cmd for cmd in module.commands([], maintenance=True)
                       if 'scripts/traceability.py' in cmd)
        checked = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertEqual(checked.returncode, 0, checked.stderr)


if __name__ == "__main__":
    unittest.main()

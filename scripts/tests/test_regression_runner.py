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
    def run_fixture(self, body, extra_env=None, execution_identity=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "test_fixture.py").write_text(body)
            report = root / "report.json"
            summary = root / "summary.md"
            identity_args = []
            if execution_identity is not None:
                identity_path = root / 'identity.json'
                identity_path.write_text(json.dumps(execution_identity))
                identity_args = ['--input-identity', str(identity_path)]
            result = subprocess.run(
                [sys.executable, "-B", str(RUNNER), "--start-directory", str(root),
                 "--report", str(report), *identity_args], capture_output=True, text=True,
                env=dict(os.environ, GITHUB_STEP_SUMMARY=str(summary), **(extra_env or {})), timeout=20)
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
        self.assertEqual([e["event"] for e in events if e["event"] in ("start", "stop")],
                         ["start", "stop", "start", "stop"])
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

    def test_subcondition_replacement_preserves_successes_and_distinguishes_new_failure(self):
        body = """import os, unittest
class Cases(unittest.TestCase):
    def test_conditions(self):
        for condition in ('A', 'B'):
            with self.subTest(condition=condition):
                self.assertNotEqual(condition, os.environ['FAILING_CONDITION'])
"""
        observations = []
        for bad in ('A', 'B'):
            result, report, _, _ = self.run_fixture(body, {'FAILING_CONDITION': bad})
            self.assertEqual(result.returncode, 1)
            self.assertFalse(report['successful'])
            conditions = report['tests'][0]['conditions']
            self.assertEqual(len(conditions), 2)
            self.assertEqual({c['params']['condition']: c['outcome'] for c in conditions},
                             {c: 'failed' if c == bad else 'passed' for c in ('A', 'B')})
            observations.append({c['params']['condition']: c['id'] for c in conditions})
        self.assertEqual(observations[0], observations[1])
        self.assertNotEqual(observations[0]['A'], observations[0]['B'])

    def test_body_and_teardown_failures_retain_both_phases_and_reasons(self):
        result, report, _, _ = self.run_fixture("""import unittest
class Cases(unittest.TestCase):
    def tearDown(self): raise RuntimeError('teardown failed')
    def test_body(self): self.fail('body failed')
""")
        self.assertEqual(result.returncode, 1)
        method = report['tests'][0]
        self.assertEqual(method['outcome'], 'error')
        self.assertEqual([c['phase'] for c in method['conditions']], ['test', 'teardown'])
        self.assertEqual([c['reason']['message'] for c in method['conditions']],
                         ['body failed', 'teardown failed'])
        self.assertTrue(all(c['reason']['site']['source_sha256'] for c in method['conditions']))

    def test_plain_loop_replacement_retains_iteration_identity_without_subtest(self):
        body = """import os, unittest
class Cases(unittest.TestCase):
    def test_loop(self):
        for condition in ('A', 'B'):
            if condition == os.environ['FAILING_CONDITION']:
                self.fail('same diagnostic for either condition')
"""
        identities = []
        for bad in ('A', 'B'):
            result, report, _, _ = self.run_fixture(body, {'FAILING_CONDITION': bad})
            self.assertEqual(result.returncode, 1)
            condition = report['tests'][0]['conditions'][0]
            self.assertEqual(condition['context'][0]['values']['condition'], bad)
            self.assertTrue(condition['identity_complete'])
            identities.append(condition['id'])
        self.assertNotEqual(*identities)

    def test_parameter_identity_retains_sequence_types_mapping_order_and_float_bits(self):
        result, report, _, _ = self.run_fixture("""import unittest
class Cases(unittest.TestCase):
    def test_values(self):
        for value in ((1,), [1], {'a': 1, 'b': 2}, {'b': 2, 'a': 1}, 0.0, -0.0):
            with self.subTest(value=value): pass
""")
        self.assertEqual(result.returncode, 0)
        conditions = report['tests'][0]['conditions']
        self.assertEqual(len({c['id'] for c in conditions}), 6)
        self.assertTrue(all(c['identity_complete'] for c in conditions))

    def test_expected_failure_and_subtest_skip_remain_raw_success_with_visible_conditions(self):
        result, report, _, _ = self.run_fixture("""import unittest
class Cases(unittest.TestCase):
    @unittest.expectedFailure
    def test_expected(self): self.fail('documented expected failure')
    def test_subskip(self):
        with self.subTest(part='control'): self.assertTrue(True)
        with self.subTest(part='skipped'): self.skipTest('documented skip')
""")
        self.assertEqual(result.returncode, 0)
        self.assertTrue(report['successful'])
        expected, subskip = report['tests']
        self.assertEqual(expected['conditions'][0]['outcome'], 'expected_failure')
        self.assertEqual([c['outcome'] for c in subskip['conditions']], ['passed', 'skipped'])
        self.assertEqual(subskip['conditions'][1]['reason']['message'], 'documented skip')

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

    def test_dataclass_parameters_retain_values_and_opaque_repetitions_remain_raw_data(self):
        result, report, _, _ = self.run_fixture("""import unittest
from dataclasses import dataclass
@dataclass
class Input:
    value: int
class Cases(unittest.TestCase):
    def test_inputs(self):
        for value in (Input(1), Input(2)):
            with self.subTest(value=value): pass
    def test_opaque(self):
        for value in (object(), object()):
            with self.subTest(value=value): pass
""")
        self.assertEqual(result.returncode, 0)
        typed, opaque = [r['conditions'] for r in report['tests']]
        self.assertEqual(len({c['id'] for c in typed}), 2)
        self.assertTrue(all(c['identity_complete'] for c in typed))
        self.assertEqual(len({c['id'] for c in opaque}), 2)
        self.assertFalse(any(c['identity_complete'] for c in opaque))

    def test_unknown_while_state_cannot_be_a_matchable_failure(self):
        result, report, _, _ = self.run_fixture("""import unittest
def hidden_state(): return True
class Cases(unittest.TestCase):
    def test_body(self):
        while hidden_state(): self.fail('same failure')
    def test_subtest(self):
        while True:
            with self.subTest(label='same'):
                self.fail('same failure')
            break
""")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(any(c['identity_complete'] for row in report['tests'] for c in row['conditions']))

    def test_dataclass_extra_stored_state_changes_condition_identity(self):
        body = """import os, unittest
from dataclasses import dataclass
@dataclass
class Input:
    value: int
class Cases(unittest.TestCase):
    def test_input(self):
        value=Input(1)
        value.extra=os.environ['EXTRA_STATE']
        with self.subTest(value=value): self.fail('same failure')
"""
        conditions=[]
        for value in ('A','B'):
            result, report, _, _ = self.run_fixture(body, {'EXTRA_STATE':value})
            self.assertEqual(result.returncode, 1)
            conditions.append(report['tests'][0]['conditions'][0])
        self.assertNotEqual(conditions[0]['id'], conditions[1]['id'])

    def test_actual_encoded_compiler_configuration_changes_runtime_profile(self):
        body="import unittest\nclass Cases(unittest.TestCase):\n def test_ok(self): pass\n"
        profiles=[]
        for value in ('-Copt-level=1','-Copt-level=2'):
            result, report, _, _ = self.run_fixture(body, {'CARGO_ENCODED_RUSTFLAGS':value})
            self.assertEqual(result.returncode, 0)
            profiles.append(report['metadata']['runtime_profile'])
        self.assertNotEqual(*profiles)

    def test_execution_toolchain_changes_context_but_dut_kernel_content_does_not(self):
        body="import unittest\nclass Cases(unittest.TestCase):\n def test_ok(self): pass\n"
        profiles=[]
        for rustc,kernel in (('compiler-A','kernel-A'),('compiler-A','kernel-B'),('compiler-B','kernel-B')):
            identity={'environment':{'rustc':rustc,'cargo':'cargo-fixture','kernel_sha256':kernel,
                                     'kernel_overrides':{'EVAS_KERNEL':{'path':'selected','sha256':kernel}},
                                     'shard':'0-of-1','variables':{'RUSTFLAGS':''}}}
            result, report, _, _ = self.run_fixture(body, execution_identity=identity)
            self.assertEqual(result.returncode, 0)
            profiles.append(report['metadata']['runtime_profile'])
        self.assertEqual(profiles[0],profiles[1])
        self.assertNotEqual(profiles[1],profiles[2])

    def test_report_binds_actual_criteria_and_marks_import_failure_incomplete(self):
        result, report, _, _ = self.run_fixture('raise ImportError("missing fixture dependency")\n')
        self.assertEqual(result.returncode, 1)
        self.assertFalse(report['collection_complete'])
        self.assertEqual(len(report['metadata']['criteria_id']), 64)
        self.assertTrue(report['collection_errors'])

    def test_complete_failing_shards_merge_without_changing_raw_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'test_fixture.py').write_text("import unittest\nclass Cases(unittest.TestCase):\n    def test_bad(self): self.fail('known failure')\n")
            reports = [root / ('part%d.json' % index) for index in range(2)]
            for index, report in enumerate(reports):
                subprocess.run([sys.executable, '-B', str(RUNNER), '--start-directory', str(root),
                                '--report', str(report), '--shard-count', '2', '--shard-index', str(index)],
                               capture_output=True, timeout=20)
            merged = root / 'merged.json'
            result = subprocess.run([sys.executable, '-B', str(RUNNER), '--report', str(merged),
                                     '--merge', *map(str, reports)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertTrue(merged.exists(), result.stderr)
            payload = json.loads(merged.read_text())
            self.assertTrue(payload['complete'])
            self.assertFalse(payload['successful'])
            self.assertTrue(payload['merged'])
            self.assertEqual(payload['failures'], 1)
            self.assertEqual(len(payload['parts']), 2)

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

"""scripts/run_explicit_checks.py runs named check_ methods exactly once and fails closed.

Fixture repositories only: a small test module with check_ methods, a registry
whose current case registers them, and a copy of the runner. No simulator runs here.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNNER = 'scripts/run_explicit_checks.py'
CHECK = 'test_fixture.Fixture.check_named'
MODULE = '''import os
import unittest


class Fixture(unittest.TestCase):
    def check_named(self):
        self.assertTrue(os.environ.get('FIXTURE_KERNEL'), 'FIXTURE_KERNEL must name a kernel')
        print('fixture check body ran')
        self.assertEqual(os.environ.get('FIXTURE_OUTCOME', 'pass'), 'pass')

    def check_other(self):
        pass

    def test_collected(self):
        pass
'''


class ExplicitCheckRunner(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        (self.root / 'scripts').mkdir()
        shutil.copy(ROOT / RUNNER, self.root / RUNNER)
        self.write('tests/test_fixture.py', MODULE)
        self.register(CHECK, 'test_fixture.Fixture.check_other', 'test_fixture.Fixture.test_collected')

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def register(self, *runtime_ids, current=True):
        case = {'id': 'case:fixture', 'version': '1', 'kind': 'case',
                'checks': [{'module': 'tests/test_fixture.py', 'runtime_id': r} for r in runtime_ids]}
        self.write('evas/capabilities/data/registry.json', json.dumps(
            {'objects': [case], 'current': {'case:fixture': '1'} if current else {}}))

    def run_checks(self, *checks, env=None, require=('FIXTURE_KERNEL',)):
        environment = {k: v for k, v in os.environ.items() if not k.startswith('FIXTURE_')}
        environment.update({'FIXTURE_KERNEL': 'kernel'} if env is None else env)
        report = self.root / 'runs/explicit-checks.json'
        argv = [sys.executable, '-B', RUNNER, '--start', 'tests', '--report', 'runs/explicit-checks.json']
        for name in require:
            argv += ['--require-env', name]
        for check in checks or (CHECK,):
            argv += ['--check', check]
        proc = subprocess.run(argv, cwd=self.root, env=environment, capture_output=True, text=True, timeout=60)
        return proc, json.loads(report.read_text()) if report.is_file() else None

    def single(self, receipt):
        self.assertIsNotNone(receipt)
        self.assertEqual(len(receipt['checks']), 1)
        return receipt['checks'][0]

    def test_a_passing_check_runs_exactly_once_and_is_named_in_the_log_and_receipt(self):
        proc, receipt = self.run_checks()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        row = self.single(receipt)
        self.assertEqual((row['id'], row['executed'], row['outcome']), (CHECK, 1, 'ok'))
        self.assertEqual(row['module'], 'tests/test_fixture.py')
        self.assertEqual(row['registered_by'], ['case:fixture@1'])
        self.assertTrue(receipt['success'])
        self.assertEqual(receipt['required_environment'], {'FIXTURE_KERNEL': 'kernel'})
        self.assertIn(f'explicit check {CHECK}: executed 1 time, outcome ok', proc.stdout)
        self.assertIn('fixture check body ran', proc.stdout + proc.stderr)

    def test_a_failing_check_fails_the_run(self):
        proc, receipt = self.run_checks(env={'FIXTURE_KERNEL': 'kernel', 'FIXTURE_OUTCOME': 'fail'})
        self.assertNotEqual(proc.returncode, 0)
        row = self.single(receipt)
        self.assertEqual((row['executed'], row['outcome']), (1, 'FAIL'))
        self.assertFalse(receipt['success'])

    def test_a_missing_prerequisite_fails_before_anything_runs(self):
        for env in ({}, {'FIXTURE_KERNEL': ''}):
            with self.subTest(env=env):
                proc, receipt = self.run_checks(env=env)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(receipt['success'])
                self.assertEqual(self.single(receipt)['executed'], 0)
                self.assertIn('prerequisite FIXTURE_KERNEL is not set', ' '.join(receipt['refused']))
                self.assertNotIn('fixture check body ran', proc.stdout + proc.stderr)
        # Without the runner-level declaration the check's own precondition still fails it.
        proc, receipt = self.run_checks(env={}, require=())
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual((self.single(receipt)['executed'], self.single(receipt)['outcome']), (1, 'FAIL'))

    def test_a_renamed_or_deleted_check_fails_instead_of_running_nothing(self):
        cases = {
            'method renamed': lambda: self.write('tests/test_fixture.py', MODULE.replace('check_named', 'check_renamed')),
            'method deleted': lambda: self.write('tests/test_fixture.py', MODULE.replace('    def check_named(self):', '    def helper(self):')),
            'class renamed': lambda: self.write('tests/test_fixture.py', MODULE.replace('class Fixture', 'class Other')),
            'module deleted': lambda: (self.root / 'tests/test_fixture.py').unlink(),
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.write('tests/test_fixture.py', MODULE)
                change()
                proc, receipt = self.run_checks()
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(receipt['success'])
                self.assertEqual(self.single(receipt)['executed'], 0)
                self.assertRegex(' '.join(receipt['refused']), r'not found')

    def test_skip_expected_failure_and_unexpected_success_are_failures(self):
        decorated = {
            'skip decorator': MODULE.replace('    def check_named', '    @unittest.skip("fixture")\n    def check_named'),
            'skip in the body': MODULE.replace("        print('fixture", "        self.skipTest('fixture')\n        print('fixture"),
            'class setup skip': MODULE.replace('    def check_named', '    @classmethod\n    def setUpClass(cls):\n'
                                               '        raise unittest.SkipTest("fixture")\n\n    def check_named'),
            'expected failure': MODULE.replace('    def check_named', '    @unittest.expectedFailure\n    def check_named'),
        }
        for name, text in decorated.items():
            with self.subTest(name):
                self.write('tests/test_fixture.py', text)
                proc, receipt = self.run_checks(env={'FIXTURE_KERNEL': 'kernel', 'FIXTURE_OUTCOME': 'pass'})
                self.assertNotEqual(proc.returncode, 0, name)
                self.assertFalse(receipt['success'])
                self.assertNotEqual(self.single(receipt)['outcome'], 'ok')

    def test_a_class_setup_error_is_a_failure_with_nothing_executed(self):
        self.write('tests/test_fixture.py', MODULE.replace(
            '    def check_named', '    @classmethod\n    def setUpClass(cls):\n        raise RuntimeError("fixture")\n\n    def check_named'))
        proc, receipt = self.run_checks()
        self.assertNotEqual(proc.returncode, 0)
        row = self.single(receipt)
        self.assertEqual(row['executed'], 0)
        self.assertNotEqual(row['outcome'], 'ok')

    def test_an_import_error_is_a_failure_with_nothing_executed(self):
        self.write('tests/test_fixture.py', 'import missing_fixture_dependency\n' + MODULE)
        proc, receipt = self.run_checks()
        self.assertNotEqual(proc.returncode, 0)
        row = self.single(receipt)
        self.assertEqual(row['executed'], 0)
        self.assertEqual(row['outcome'], 'ERROR')

    def test_an_unregistered_check_is_refused(self):
        for registered, current in ((('test_fixture.Fixture.check_other',), True), ((CHECK,), False)):
            with self.subTest(registered=registered, current=current):
                self.register(*registered, current=current)
                proc, receipt = self.run_checks()
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(self.single(receipt)['executed'], 0)
                self.assertIn('not registered in the checks of a current case', ' '.join(receipt['refused']))

    def test_only_full_check_method_names_are_accepted(self):
        for name in ('test_fixture.Fixture.test_collected', 'test_fixture.Fixture', 'test_fixture',
                     'test_fixture.Fixture.check_named.extra', 'tests/test_fixture.py'):
            with self.subTest(name=name):
                proc, receipt = self.run_checks(name)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(receipt['success'])
                self.assertEqual(self.single(receipt)['executed'], 0)
        proc, receipt = self.run_checks(CHECK, CHECK)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn('named more than once', ' '.join(receipt['refused']))

    def test_every_named_check_runs_once_and_one_failure_fails_the_run(self):
        proc, receipt = self.run_checks(CHECK, 'test_fixture.Fixture.check_other')
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual([(r['id'], r['executed'], r['outcome']) for r in receipt['checks']],
                         [(CHECK, 1, 'ok'), ('test_fixture.Fixture.check_other', 1, 'ok')])
        proc, receipt = self.run_checks(CHECK, 'test_fixture.Fixture.check_other',
                                        env={'FIXTURE_KERNEL': 'kernel', 'FIXTURE_OUTCOME': 'fail'})
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual([r['outcome'] for r in receipt['checks']], ['FAIL', 'ok'])

    def test_a_check_without_any_check_name_or_start_is_a_usage_error(self):
        for argv in (['--start', 'tests', '--report', 'runs/r.json'],
                     ['--check', CHECK, '--report', 'runs/r.json'],
                     ['--start', '../tests', '--check', CHECK, '--report', 'runs/r.json'],
                     ['--start', 'tests', '--check', CHECK, '--report', '/abs/r.json']):
            with self.subTest(argv=argv):
                proc = subprocess.run([sys.executable, '-B', RUNNER, *argv], cwd=self.root,
                                      capture_output=True, text=True, timeout=60)
                self.assertNotEqual(proc.returncode, 0)


if __name__ == '__main__':
    unittest.main()

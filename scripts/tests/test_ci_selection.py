"""Exercise CI routing against real Git changes and failed job dependencies."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_selection.py'
spec = importlib.util.spec_from_file_location('ci_selection', SCRIPT)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class RoutingTests(unittest.TestCase):
    def test_five_layer_documentation_change_does_not_build_or_simulate(self):
        paths = [
            'evas/docs/COMPARISON.md', 'evas/docs/COMPARISON-METHODOLOGY.md',
            'evas/docs/README.md', 'evas/docs/development/capability-evidence.md',
            'evas/validation/paper/COVERAGE.md', 'evas/validation/paper/README.md',
            'experiments/backends/support/README.md',
        ]
        self.assertEqual(ci.classify(paths), ci.flags())

    def test_production_change_keeps_full_regression_and_both_install_platforms(self):
        for path in ('evas/src/evas/compiler.py', 'evas/rust_core/src/main.rs',
                     'evas/rust_core/ir/src/lib.rs', 'evas/rust_core/Cargo.lock',
                     'evas/rust_core/build.rs', 'evas/rust_core/.cargo/config.toml',
                     'evas/pyproject.toml', 'evas/MANIFEST.in', 'evas/setup.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(full=True, package=True))

    def test_checker_or_fixture_change_cannot_be_mistaken_for_documentation(self):
        for path in ('evas/tests/test_events.py', 'evas/validation/strobe/cases.json',
                     'evas/validation/paper/dut/hold.va',
                     'experiments/backends/support/checker.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(full=True))

    def test_task_instructions_are_a_benchmark_input_even_when_markdown(self):
        for path in ('benchmark/tasks/adc/instruction.md',
                     'experiments/benchmark_next/adc/source/instruction.md',
                     'benchmark/checkers/adc.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(benchmark=True))

    def test_mixed_change_runs_the_union_of_checks(self):
        self.assertEqual(ci.classify(['evas/docs/COMPARISON.md',
                                      'evas/src/evas/compiler.py',
                                      'benchmark/checkers/adc.py']), ci.flags(True, True, True))

    def test_workflow_selector_or_unrecognized_code_runs_every_lane(self):
        for path in ('.github/workflows/package-install.yml',
                     'scripts/ci_selection.py', 'scripts/tests/test_ci_selection.py',
                     'new_runtime/solver.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(True, True, True))


class GitChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.git('init', '-q')
        self.git('config', 'user.email', 'ci-test@example.invalid')
        self.git('config', 'user.name', 'CI Test')
        self.write('evas/docs/old.md', 'original\n')
        self.base = self.commit()

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True).strip()

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def test_pr_uses_merge_base_and_excludes_base_branch_only_changes(self):
        self.git('checkout', '-qb', 'feature')
        self.write('evas/docs/with space.md', 'documentation\n')
        head = self.commit()
        self.git('checkout', '--detach', self.base)
        self.write('evas/src/evas/base_only.py', 'raise RuntimeError\n')
        base_tip = self.commit()
        plan = ci.select(self.repo, 'pull_request', {'pull_request': {
            'base': {'sha': base_tip}, 'head': {'sha': head}}})
        self.assertEqual(plan['paths'], ['evas/docs/with space.md'])
        self.assertFalse(plan['full'])
        self.assertEqual(plan['base'], self.base)

    def test_push_includes_deletion_and_rename_destination(self):
        self.git('mv', 'evas/docs/old.md', 'evas/docs/old.py')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': self.base, 'after': head})
        self.assertEqual(set(plan['paths']), {'evas/docs/old.md', 'evas/docs/old.py'})
        self.assertTrue(plan['full'])

    def test_deleted_source_still_runs_regression_and_install(self):
        self.write('evas/src/evas/deleted.py', 'old\n')
        base = self.commit()
        self.git('rm', 'evas/src/evas/deleted.py')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': base, 'after': head})
        self.assertTrue(plan['full'])
        self.assertTrue(plan['package'])

    def test_missing_history_initial_push_and_manual_run_cannot_skip_checks(self):
        events = [('push', {'before': '0' * 40, 'after': self.base}),
                  ('push', {'before': 'f' * 40, 'after': self.base}),
                  ('pull_request', {}), ('workflow_dispatch', {})]
        for name, event in events:
            with self.subTest(name=name, event=event):
                plan = ci.select(self.repo, name, event)
                self.assertEqual({key: plan[key] for key in ci.flags()}, ci.flags(True, True, True))

    def test_cli_emits_github_boolean_outputs(self):
        self.write('evas/docs/with space.md', 'documentation\n')
        head = self.commit()
        event_file = self.repo / 'event.json'
        event_file.write_text(json.dumps({'before': self.base, 'after': head}))
        output_file = self.repo / 'outputs'
        completed = subprocess.run([
            'python3', '-B', str(SCRIPT), 'select', '--repo', str(self.repo),
            '--event-name', 'push', '--event-path', str(event_file),
            '--output', str(output_file),
        ], text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(completed.stdout)['full'])
        self.assertIn('full=false\n', output_file.read_text())
        self.assertIn('package=false\n', output_file.read_text())


class GateTests(unittest.TestCase):
    def results(self, lane, selected=False):
        output = {'full': 'true' if selected else 'false',
                  'package': 'true' if selected else 'false',
                  'benchmark': 'true' if selected else 'false'}
        needs = {'selection': {'result': 'success', 'outputs': output}}
        if lane == 'numerical':
            needs['static-checks'] = {'result': 'success'}
        jobs = {'numerical': ('regression', 'properties-and-ngspice', 'fuzz-smoke'),
                'package': ('install',), 'benchmark': ('identity', 'first-batch')}[lane]
        needs.update({job: {'result': 'success' if selected else 'skipped'} for job in jobs})
        return needs

    def test_intentional_skips_are_allowed_but_selected_skips_are_not(self):
        for lane in ('numerical', 'package', 'benchmark'):
            self.assertEqual(ci.gate_errors(lane, self.results(lane)), [])
            needs = self.results(lane, True)
            job = next(job for job in needs if job not in ('selection', 'static-checks'))
            needs[job]['result'] = 'skipped'
            self.assertTrue(ci.gate_errors(lane, needs))

    def test_failed_selector_static_checks_and_cancelled_jobs_cannot_turn_green(self):
        for job, result in (('selection', 'failure'), ('static-checks', 'failure'),
                            ('regression', 'cancelled'), ('fuzz-smoke', 'failure')):
            with self.subTest(job=job):
                needs = self.results('numerical', True)
                needs[job]['result'] = result
                self.assertTrue(ci.gate_errors('numerical', needs))

    def test_missing_or_invalid_selector_output_is_rejected(self):
        for value in (None, '', 'unknown'):
            needs = self.results('numerical')
            needs['selection']['outputs']['full'] = value
            self.assertTrue(ci.gate_errors('numerical', needs))


if __name__ == '__main__':
    unittest.main()

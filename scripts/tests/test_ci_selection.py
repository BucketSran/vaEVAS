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
    def test_plain_prose_only_needs_selection_and_whitespace(self):
        self.assertEqual(ci.classify(['README.md', 'evas/README.md',
                                      'docs/contributing/workspaces.md']), ci.flags())

    def test_five_layer_documentation_change_keeps_only_related_static_checks(self):
        paths = [
            'evas/docs/COMPARISON.md', 'evas/docs/COMPARISON-METHODOLOGY.md',
            'evas/docs/README.md', 'evas/docs/development/capability-evidence.md',
            'evas/validation/paper/COVERAGE.md', 'evas/validation/paper/README.md',
            'experiments/backends/support/README.md',
        ]
        self.assertEqual(ci.classify(paths), ci.flags('maintenance', 'calibration', 'provenance'))

    def test_documentation_uses_its_own_contract(self):
        for path, expected in (
            ('evas/docs/COMPARISON.md', ('provenance',)),
            ('evas/docs/COMPARISON-METHODOLOGY.md', ('calibration', 'provenance')),
            ('evas/docs/math/continuous.md', ('calibration',)),
            ('evas/validation/NEXT_CASE_CARDS.md', ('calibration',)),
            ('evas/docs/development/TRACEABILITY.md', ('maintenance',)),
        ):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(*expected))

    def test_production_and_build_changes_keep_all_evas_checks(self):
        for path in ('evas/src/evas/compiler.py', 'evas/rust_core/src/main.rs',
                     'evas/rust_core/ir/src/lib.rs', 'evas/rust_core/Cargo.lock',
                     'evas/rust_core/build.rs', 'evas/rust_core/.cargo/config.toml',
                     'evas/pyproject.toml', 'evas/MANIFEST.in', 'evas/setup.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(*ci.CHECKS[:-1]))

    def test_fixtures_keep_regression_without_unrelated_fuzz_or_install(self):
        for path in ('evas/tests/test_events.py', 'evas/validation/strobe/cases.json',
                     'evas/validation/paper/dut/hold.va',
                     'experiments/backends/event-alignment/vco-controls/original--tight/dut.va',
                     'evas/validation/paper/core-v1.json', 'experiments/backends/paper/inputs.py',
                     'experiments/backends/dvs2-spectre-validation/check_results.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]),
                                 ci.flags('maintenance', 'calibration', 'provenance', 'regression'))

    def test_backend_checkers_keep_calibration_without_kernel_regression(self):
        for path in ('experiments/backends/support/checker.py',
                     'experiments/backends/evidence/archive.py',
                     'evas/validation/paper/criteria.py', 'experiments/performance/test_profile.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags('calibration', 'provenance'))

    def test_maintenance_and_install_checks_are_separate(self):
        self.assertEqual(ci.classify(['scripts/check_workspaces.py']), ci.flags('maintenance'))
        self.assertEqual(ci.classify(['scripts/check_installed_evas.py']),
                         ci.flags('maintenance', 'package'))
        self.assertEqual(ci.classify(['evas/validation/differential/ngspice_compare.py']),
                         ci.flags('maintenance', 'calibration', 'differential'))
        plan = ci.classify(['evas/rust_core/fuzz/fuzz_targets/run.rs'])
        self.assertTrue(plan['fuzz'])
        self.assertFalse(plan['differential'])
        self.assertFalse(plan['package'])

    def test_shared_smoke_inputs_and_required_sdist_seed_keep_their_consumers(self):
        for path in ('evas/validation/smoke/idt.json', 'evas/validation/cases/n_v1_02/dut.va'):
            with self.subTest(path=path):
                plan = ci.classify([path])
                self.assertTrue(plan['regression'])
                self.assertTrue(plan['differential'])
        plan = ci.classify(['evas/rust_core/fuzz/seeds/static.json'])
        self.assertTrue(plan['fuzz'])
        self.assertTrue(plan['package'])

    def test_task_instructions_are_a_benchmark_input_even_when_markdown(self):
        for path in ('benchmark/tasks/adc/instruction.md',
                     'benchmark/material/draftbench/batches/test-01/tasks/adc/instruction.md',
                     'benchmark/material/historyref/tasks/va07-triangle-repair/instruction.md',
                     'experiments/benchmark_paths.py',
                     'experiments/test_benchmark_paths.py',
                     'experiments/benchmark_next/adc/source/instruction.md',
                     'benchmark/material/historyref/legacy-authoring/checkers/adc.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags('benchmark'))

    def test_mixed_change_runs_the_union_of_checks(self):
        self.assertEqual(ci.classify(['evas/docs/COMPARISON.md',
                                      'scripts/check_workspaces.py',
                                      'benchmark/material/historyref/legacy-authoring/checkers/adc.py']),
                         ci.flags('maintenance', 'provenance', 'benchmark'))

    def test_workflow_selector_or_unrecognized_code_runs_every_check(self):
        for path in ('.github/workflows/package-install.yml', '.github/actions/rust-cache/action.yml',
                     'scripts/ci_selection.py', 'scripts/tests/test_ci_selection.py',
                     'scripts/new_tool.py', 'experiments/new_backend/test.py', 'new_runtime/solver.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(*ci.CHECKS))


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
        self.assertFalse(plan['regression'])
        self.assertEqual(plan['base'], self.base)

    def test_push_includes_deletion_and_rename_destination(self):
        (self.repo / 'evas/tests').mkdir()
        self.git('mv', 'evas/docs/old.md', 'evas/tests/old.py')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': self.base, 'after': head})
        self.assertEqual(set(plan['paths']), {'evas/docs/old.md', 'evas/tests/old.py'})
        self.assertTrue(plan['regression'])

    def test_deleted_source_still_runs_regression_and_install(self):
        self.write('evas/src/evas/deleted.py', 'old\n')
        base = self.commit()
        self.git('rm', 'evas/src/evas/deleted.py')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': base, 'after': head})
        self.assertTrue(plan['regression'])
        self.assertTrue(plan['package'])

    def test_missing_history_initial_push_and_manual_run_cannot_skip_checks(self):
        events = [('push', {'before': '0' * 40, 'after': self.base}),
                  ('push', {'before': 'f' * 40, 'after': self.base}),
                  ('pull_request', {}), ('workflow_dispatch', {})]
        for name, event in events:
            with self.subTest(name=name, event=event):
                plan = ci.select(self.repo, name, event)
                self.assertEqual({key: plan[key] for key in ci.flags()}, ci.flags(*ci.CHECKS))

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
        self.assertFalse(json.loads(completed.stdout)['regression'])
        self.assertIn('regression=false\n', output_file.read_text())
        self.assertIn('package=false\n', output_file.read_text())


class GateTests(unittest.TestCase):
    def results(self, *selected):
        output = {key: str(value).lower() for key, value in ci.flags(*selected).items()}
        needs = {'selection': {'result': 'success', 'outputs': output}}
        for job, flags in ci.JOB_FLAGS.items():
            result = 'success' if any(flag in selected for flag in flags) else 'skipped'
            needs[job] = {'result': result, 'outputs': {
                child: result for child in ci.CHILD_RESULTS.get(job, ())}}
        return needs

    def test_intentional_skips_are_allowed_but_selected_skips_are_not(self):
        self.assertEqual(ci.gate_errors(self.results()), [])
        for flag in ci.CHECKS:
            needs = self.results(flag)
            self.assertEqual(ci.gate_errors(needs), [])
            for job, flags in ci.JOB_FLAGS.items():
                if flag in flags:
                    needs[job]['result'] = 'skipped'
                    self.assertTrue(ci.gate_errors(needs), (flag, job))

    def test_failure_cancellation_missing_jobs_or_unexpected_execution_failures_are_rejected(self):
        for job in ('selection', *ci.JOB_FLAGS):
            for result in ('failure', 'cancelled', None):
                with self.subTest(job=job, result=result):
                    needs = self.results(*ci.CHECKS)
                    needs[job]['result'] = result
                    self.assertTrue(ci.gate_errors(needs))
                    needs = self.results()
                    needs[job]['result'] = result
                    self.assertTrue(ci.gate_errors(needs))

    def test_missing_or_invalid_selector_output_is_rejected(self):
        for flag in ci.CHECKS:
            for value in (None, '', 'unknown'):
                needs = self.results()
                needs['selection']['outputs'][flag] = value
                self.assertTrue(ci.gate_errors(needs))

    def test_reusable_workflow_success_cannot_hide_skipped_or_failed_child_jobs(self):
        for job, children in ci.CHILD_RESULTS.items():
            for child in children:
                for result in (None, 'skipped', 'failure', 'cancelled'):
                    with self.subTest(job=job, child=child, result=result):
                        needs = self.results(*ci.CHECKS)
                        needs[job]['outputs'][child] = result
                        self.assertTrue(ci.gate_errors(needs))

    def test_cli_gate_returns_nonzero_for_failed_selected_check(self):
        import os
        for failed in (False, True):
            needs = self.results('regression')
            if failed:
                needs['regression']['result'] = 'failure'
            result = subprocess.run(['python3', '-B', str(SCRIPT), 'gate'],
                                    env={**os.environ, 'CI_NEEDS': json.dumps(needs)},
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, int(failed), result.stderr)


if __name__ == '__main__':
    unittest.main()

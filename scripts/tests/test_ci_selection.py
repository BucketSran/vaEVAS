"""Exercise CI routing against real Git changes and failed job dependencies."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import git_fixture


SCRIPT = Path(__file__).resolve().parents[1] / 'ci_selection.py'
spec = importlib.util.spec_from_file_location('ci_selection', SCRIPT)
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class RoutingTests(unittest.TestCase):
    def test_continuation_controls_only_select_maintenance(self):
        paths = ('scripts/check_task_continuation.py',
                 'scripts/task_continuation_policy.py',
                 'scripts/task_continuation_execution.py',
                 'scripts/tests/test_task_continuation.py',
                 'scripts/tests/test_task_continuation_policy.py',
                 'scripts/tests/test_task_continuation_execution.py',
                 'scripts/tests/fixtures/continuation-wave21-313.json',
                 'scripts/tests/test_task_continuation_checkpoints.py',
                 'scripts/tests/test_task_continuation_review_execution.py',
                 'scripts/tests/fixtures/continuation-wave26-zero-gain.json')
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags('maintenance'))
        self.assertTrue(ci.classify([*paths, 'evas/src/evas/compiler.py'])['regression'])

    def test_development_records_only_select_maintenance(self):
        for path in ('scripts/development_records.py', 'scripts/tests/test_development_records.py',
                     'scripts/tests/test_ci_selection.py'):
            self.assertEqual(ci.classify([path]), ci.flags('maintenance'))
        self.assertTrue(ci.classify(['scripts/development_records.py',
                                     'evas/rust_core/src/events.rs'])['regression'])

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

    def test_capability_catalog_stays_on_maintenance(self):
        maintenance = ci.flags("maintenance")
        for path in (
            "evas/capabilities/catalog.py",
            "evas/capabilities/render.py",
            "evas/capabilities/registry.json",
            "evas/capabilities/generated/paper.md",
            "evas/capabilities/timer/README.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), maintenance)
        mixed = ci.classify([
            "evas/capabilities/catalog.py",
            "evas/rust_core/compiler/src/lib.rs",
        ])
        self.assertEqual(mixed, ci.flags(*ci.CHECKS[:-1]))

    def test_production_and_build_changes_keep_all_evas_checks(self):
        for path in ('evas/src/evas/compiler.py', 'evas/rust_core/Cargo.lock',
                     'evas/rust_core/build.rs', 'evas/rust_core/.cargo/config.toml',
                     'evas/pyproject.toml', 'evas/MANIFEST.in', 'evas/setup.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(*ci.CHECKS[:-1]))

    def test_rust_implementation_keeps_producer_identity_but_not_checker_calibration(self):
        for path in ('evas/rust_core/src/main.rs', 'evas/rust_core/ir/src/lib.rs'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(
                    'maintenance', 'provenance', 'regression', 'differential', 'fuzz', 'package'))

    def test_development_tests_keep_regression_and_source_identity(self):
        self.assertEqual(ci.classify(['evas/tests/test_events.py']),
                         ci.flags('maintenance', 'provenance', 'regression'))
        self.assertEqual(ci.classify(['evas/rust_core/tests/properties.rs']),
                         ci.flags('maintenance', 'provenance', 'regression'))
        self.assertEqual(ci.classify(['evas/tests/test_events.py',
                                     'experiments/backends/support/checker.py']),
                         ci.flags('maintenance', 'regression', 'calibration', 'provenance'))
        self.assertEqual(ci.classify(['evas/tests/test_events.py', 'evas/src/evas/compiler.py']),
                         ci.flags(*ci.CHECKS[:-1]))

    def test_narrow_routes_do_not_apply_to_other_fixture_or_build_inputs(self):
        self.assertEqual(ci.classify(['evas/tests/shared.json']),
                         ci.flags('maintenance', 'calibration', 'provenance', 'regression'))
        self.assertEqual(ci.classify(['evas/rust_core/src/generated.json']),
                         ci.flags(*ci.CHECKS[:-1]))

    def test_fixtures_keep_regression_without_unrelated_fuzz_or_install(self):
        for path in ('evas/validation/strobe/cases.json',
                     'evas/validation/paper/dut/hold.va',
                     'experiments/backends/event-alignment/vco-controls/original--tight/dut.va',
                     'evas/validation/paper/core-v1.json', 'evas/validation/paper/case_inputs.py',
                     'experiments/backends/paper/inputs.py',
                     'experiments/backends/dvs2-spectre-validation/check_results.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]),
                                 ci.flags('maintenance', 'calibration', 'provenance', 'regression'))

    def test_backend_checkers_keep_calibration_without_kernel_regression(self):
        for path in ('experiments/backends/support/checker.py',
                     'experiments/backends/implicit-event-restart/check.py',
                     'experiments/backends/evidence/archive.py',
                     'evas/validation/paper/criteria.py', 'experiments/performance/test_profile.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags('calibration', 'provenance'))

    def test_registered_historical_receipt_keeps_static_checks(self):
        receipt = 'experiments/backends/sample-edge-filter/rea-boundary-receipt.json'
        self.assertEqual(ci.classify([receipt]), ci.flags('calibration', 'provenance'))
        self.assertEqual(ci.classify([
            receipt, 'evas/docs/development/capability-evidence.md',
            'evas/validation/sample_edge_filter/README.md',
            'experiments/backends/sample-edge-filter/BOUNDARY.md',
            'benchmark/material/draftbench/CANDIDATES.md',
            'benchmark/material/draftbench/sources/README.md',
            'benchmark/material/draftbench/sources/cvdp-heavy-multifile.md',
        ]), ci.flags('maintenance', 'calibration', 'provenance', 'benchmark'))
        for other in ('experiments/backends/sample-edge-filter/unknown-receipt.json',
                      'experiments/backends/sample-edge-filter/fixture.json',
                      'evas/tests/shared.json'):
            with self.subTest(path=other):
                self.assertTrue(ci.classify([receipt, other])['regression'])

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

    def test_benchmark_sources_and_format_checks_keep_their_ci_consumer(self):
        for path in ('benchmark/material/draftbench/sources/cvdp-heavy-multifile.md',
                     'benchmark/material/draftbench/sources/README.md',
                     'benchmark/material/draftbench/docs/task-package.md',
                     'benchmark/material/draftbench/templates/INSTRUCTION.md',
                     'benchmark/README.md', 'scripts/benchmark_workbench.py',
                     'scripts/benchmark_package.py',
                     'scripts/tests/test_benchmark_workbench.py',
                     'scripts/tests/test_benchmark_package.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags('benchmark'))

    def test_mixed_change_runs_the_union_of_checks(self):
        self.assertEqual(ci.classify(['evas/docs/COMPARISON.md',
                                      'scripts/check_workspaces.py',
                                      'benchmark/material/historyref/legacy-authoring/checkers/adc.py']),
                         ci.flags('maintenance', 'provenance', 'benchmark'))

    def test_workflow_selector_or_unrecognized_code_runs_every_check(self):
        for path in ('.github/workflows/package-install.yml', '.github/actions/rust-cache/action.yml',
                     'scripts/ci_selection.py',
                     'scripts/new_tool.py', 'experiments/new_backend/test.py', 'new_runtime/solver.py'):
            with self.subTest(path=path):
                self.assertEqual(ci.classify([path]), ci.flags(*ci.CHECKS))


    def test_shared_dvs2_scientific_sources_keep_their_public_regression(self):
        root = SCRIPT.parents[1]
        sources = sorted((root/'evas/validation/dvs2').glob('*.py'))
        self.assertTrue(sources)
        for source in sources:
            with self.subTest(source=source.name):
                self.assertEqual(ci.classify([str(source.relative_to(root))]),
                                 ci.flags('maintenance', 'calibration', 'provenance', 'regression'))


class GitChangeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        git_fixture.bind(self, self.repo)
        self.git('init', '-q')
        self.git('config', 'user.email', 'ci-test@example.invalid')
        self.git('config', 'user.name', 'CI Test')
        # Fixture commits must not invoke a developer's signing keys or hooks.
        self.git('config', 'commit.gpgsign', 'false')
        hooks = self.repo / '.git/fixture-hooks'
        hooks.mkdir()
        self.git('config', 'core.hooksPath', str(hooks))
        self.write('evas/docs/old.md', 'original\n')
        self.base = self.commit()

    def git(self, *args):
        completed = git_fixture.run(args, cwd=self.repo, scratch=self.repo, check=True,
                                    capture_output=True, text=True)
        return completed.stdout.strip()

    def write(self, path, data):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def test_fixture_ignores_host_signing_and_hooks(self):
        hooks = self.repo / 'host-hooks'
        hooks.mkdir()
        reject = hooks / 'pre-commit'
        reject.write_text('#!/bin/sh\necho host-policy-rejected >&2\nexit 1\n')
        reject.chmod(0o755)
        config = self.repo / 'host.gitconfig'
        policies = {
            'signing': '[commit]\n gpgsign = true\n[gpg]\n program = '
                       + json.dumps(str(reject)) + '\n',
            'hooks': '[core]\n hooksPath = ' + json.dumps(str(hooks)) + '\n',
        }
        for policy, settings in policies.items():
            with self.subTest(policy=policy):
                config.write_text(settings)
                fixture = GitChangeTests()
                with git_fixture.explicit(GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_NOSYSTEM='1'):
                    try:
                        fixture.setUp()
                        if policy == 'signing':
                            self.assertEqual(fixture.git('config', '--global', '--get', 'commit.gpgsign'), 'true')
                        else:
                            self.assertEqual(fixture.git('config', '--global', '--get', 'core.hooksPath'), str(hooks))
                        self.assertEqual(fixture.git('config', '--local', '--get', 'commit.gpgsign'), 'false')
                        fixture.write('evas/docs/new.md', 'maintenance fixture\n')
                        self.assertNotEqual(fixture.commit(), fixture.base)
                        self.assertEqual(fixture.git('status', '--porcelain'), '')
                    finally:
                        fixture.doCleanups()

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

    def test_receipt_rename_to_unknown_input_keeps_regression(self):
        receipt = 'experiments/backends/sample-edge-filter/rea-boundary-receipt.json'
        self.write(receipt, '{}\n')
        base = self.commit()
        self.git('mv', receipt, 'experiments/backends/sample-edge-filter/fixture.json')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': base, 'after': head})
        self.assertTrue(plan['regression'])
        self.git('rm', 'experiments/backends/sample-edge-filter/fixture.json')
        deleted = self.commit()
        self.assertTrue(ci.select(self.repo, 'push', {'before': head, 'after': deleted})['regression'])

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
            '--output', str(output_file), '--json',
        ], env=git_fixture.child_env(), text=True, capture_output=True, check=True)
        self.assertFalse(json.loads(completed.stdout)['regression'])
        self.assertIn('regression=false\n', output_file.read_text())
        self.assertIn('package=false\n', output_file.read_text())

    def test_compact_cli_saves_complete_evidence_and_preserves_job_outputs(self):
        self.write('scripts/check_workspaces.py', 'maintenance\n')
        head = self.commit()
        event = self.repo / 'event.json'
        event.write_text(json.dumps({'before': self.base, 'after': head}))
        report, output = self.repo / 'plan.json', self.repo / 'outputs'
        run = subprocess.run(['python3', '-B', str(SCRIPT), 'select', '--repo', str(self.repo),
                              '--event-name', 'push', '--event-path', str(event),
                              '--output', str(output), '--report', str(report)],
                             env=git_fixture.child_env(), capture_output=True, text=True, check=True)
        self.assertIn('Selected: maintenance', run.stdout)
        self.assertIn(str(report), run.stdout)
        self.assertEqual(json.loads(report.read_text())['paths'], ['scripts/check_workspaces.py'])
        self.assertIn('maintenance=true\n', output.read_text())

    def test_registration_exemption_preserves_semantics_and_unknown_inputs(self):
        original = SCRIPT.read_text()
        earlier = original.replace("    'scripts/development_records.py', 'scripts/tests/test_development_records.py',\n", '')
        self.write('scripts/ci_selection.py', earlier)
        base = self.commit()
        self.write('scripts/ci_selection.py', original)
        self.write('scripts/development_records.py', 'maintenance\n')
        self.write('scripts/tests/test_ci_selection.py', 'test fixture changes\n')
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': base, 'after': head})
        self.assertEqual({key: plan[key] for key in ci.CHECKS}, ci.flags('maintenance'))
        self.assertIn('registration only', plan['reasons'][0]['reason'])
        for source in (original.replace("'scripts/check_workspaces.py'", "'scripts/unreviewed.py'"),
                       original.replace("selected.add('provenance')", "selected.add('maintenance')"),
                       'invalid python !'):
            with self.subTest(source=source[:20]):
                self.write('scripts/ci_selection.py', source)
                changed = self.commit()
                plan = ci.select(self.repo, 'push', {'before': base, 'after': changed})
                self.assertTrue(all(plan[key] for key in ci.CHECKS))
        self.write('scripts/ci_selection.py', original)
        self.write('scripts/unrecognized.py', 'shared dependency\n')
        mixed = self.commit()
        self.assertTrue(all(ci.select(self.repo, 'push', {'before': base, 'after': mixed})[key]
                            for key in ci.CHECKS))

    def test_progress_block_exemption_does_not_cover_table_contract_or_file_removal(self):
        path = 'evas/docs/COMPARISON.md'
        source = '| ability | Q3 |\ncriterion unchanged\n' + ci.PROGRESS_START + '\nqueued work\n' + ci.PROGRESS_END + '\n'
        self.write(path, source)
        base = self.commit()
        self.write(path, source.replace('queued work', 'new progress'))
        head = self.commit()
        plan = ci.select(self.repo, 'push', {'before': base, 'after': head})
        self.assertEqual({key: plan[key] for key in ci.CHECKS}, ci.flags())
        for altered in (source.replace('Q3', 'Q2'), source.replace('criterion unchanged', 'new criterion'),
                        source.replace('queued work', '| hidden table | Q3 |'),
                        source.replace(ci.PROGRESS_START, ''), source.replace('queued work', '')):
            self.write(path, altered)
            changed = self.commit()
            self.assertTrue(ci.select(self.repo, 'push', {'before': base, 'after': changed})['provenance'])
        self.write(path, source)
        self.write('evas/src/evas/events.py', 'shared\n')
        mixed = self.commit()
        self.assertTrue(ci.select(self.repo, 'push', {'before': base, 'after': mixed})['regression'])
        self.git('mv', path, 'evas/docs/renamed.md')
        renamed = self.commit()
        self.assertTrue(ci.select(self.repo, 'push', {'before': mixed, 'after': renamed})['provenance'])
        self.git('rm', 'evas/docs/renamed.md')
        self.git('rm', 'evas/src/evas/events.py')
        deleted = self.commit()
        self.assertTrue(ci.select(self.repo, 'push', {'before': renamed, 'after': deleted})['regression'])


class GateTests(unittest.TestCase):
    def results(self, *selected):
        output = {key: str(value).lower() for key, value in ci.flags(*selected).items()}
        output.update(plan_version='2', mode='delivery')
        needs = {'selection': {'result': 'success', 'outputs': output}}
        needs['fast-checks'] = {'result': 'success'}
        for job in ci.ALWAYS_REQUIRED_JOBS:
            needs[job] = {'result': 'success'}
        needs['regression-coverage'] = {'result': 'success' if 'regression' in selected else 'skipped'}
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
        for failed in (False, True):
            needs = self.results('regression')
            if failed:
                needs['regression']['result'] = 'failure'
            result = subprocess.run(['python3', '-B', str(SCRIPT), 'gate'],
                                    env=git_fixture.child_env(CI_NEEDS=json.dumps(needs)),
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, int(failed), result.stderr)


if __name__ == '__main__':
    unittest.main()

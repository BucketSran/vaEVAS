"""Coordinator construction fixtures; no scientific tests or Git writes."""
import copy
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts/capabilities/collect_ci_inventory.py'
spec = importlib.util.spec_from_file_location('inventory', SCRIPT)
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Literal discover entries in .github/workflows/numerical-assurance.yml at the
# fixed candidate, in source order. Primary regression discovery is separate.
WORKFLOW_LITERALS = (
    ('maintenance', 'selection', 'Check CI routing and changed-line whitespace', 'scripts/tests', 'test_ci_selection.py'),
    ('maintenance', 'selection', 'Check CI routing and changed-line whitespace', 'scripts/tests', 'test_evas_check_policy.py'),
    ('maintenance', 'selection', 'Check CI routing and changed-line whitespace', 'scripts/tests', 'test_fast_feedback.py'),
    ('maintenance', 'selection', 'Check CI routing and changed-line whitespace', 'scripts/tests', 'test_independent_ci.py'),
    ('maintenance', 'selection', 'Check CI routing and changed-line whitespace', 'scripts/tests', 'test_regression_runner.py'),
    ('maintenance', 'static-checks', 'Traceability and frozen validation identities', 'scripts/tests', 'test*.py'),
    ('maintenance', 'static-checks', 'Traceability and frozen validation identities', 'evas/capabilities', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/evidence', 'test*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/dvs2-spectre-validation', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/spectre-alignment', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'evas/validation/event_alignment', 'test_checker.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'evas/validation/strobe', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/event-alignment', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'evas/validation/sample_edge_filter', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/sample-edge-filter', 'test_*.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/backends/implicit-event-restart', 'test_check.py'),
    ('validation', 'static-checks', 'Independent mathematics and checker calibration (no simulator)', 'experiments/performance', 'test_*.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_criteria.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_*root*.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/checker_calibration', 'test*.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_coefficient_first_order.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_precision.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_precision_binding.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_precision_v2.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/paper', 'test_primitives.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'experiments/backends/paper', 'test_*.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'experiments/backends/comparison', 'test_*.py'),
    ('validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance', 'evas/validation/support', 'test_*.py'),
    ('validation', 'provenance-support', 'Backend support checker tests', 'experiments/backends/support', 'test_*.py'),
    ('validation', 'properties-and-ngspice', None, 'evas/validation/differential', 'test*.py'),
)
PAPER_TEST_MODULES = (
    'test_coefficient_first_order.py',
    'test_criteria.py',
    'test_precision.py',
    'test_precision_binding.py',
    'test_precision_composition_root_v3.py',
    'test_precision_root_v3.py',
    'test_precision_v2.py',
    'test_primitives.py',
    'test_root_windows.py',
)
DIRECT_MATH_SCRIPTS = (
    'evas/validation/check_design_math.py',
    'evas/validation/check_timed_operator_math.py',
    'evas/validation/check_dynamics_math.py',
    'evas/validation/check_event_conditions_math.py',
)
RC_CHECK = 'test_output_point_limit.LargeGridEndToEnd.check_rc_step_response_over_a_hundred_thousand_rows'
EXPLICIT = 'python3 -B scripts/run_explicit_checks.py'
NAMED_STEP = b'''jobs:
  checks:
    steps:
      - name: Named check
        env:
          PYTHONPATH: evas/src
          KERNEL_PATH: evas/rust_core/target/release/evas-kernel
        run: |
          cargo build --locked --release --manifest-path evas/rust_core/Cargo.toml
          python3 -B scripts/run_explicit_checks.py --start evas/tests --require-env KERNEL_PATH --check test_a.A.check_one --check test_a.A.check_two --report runs/explicit-checks.json
'''


def literal_identity(entry):
    return (entry['namespace'], entry['job'], entry['step'], entry['start'], entry['pattern'])


class ParserTests(unittest.TestCase):
    def test_current_workflow_literals_and_separate_primary(self):
        value = inventory.parse_workflow((ROOT / inventory.WORKFLOW).read_bytes())
        self.assertEqual(len(WORKFLOW_LITERALS), 30)
        self.assertEqual([literal_identity(entry) for entry in value['entries']], list(WORKFLOW_LITERALS))
        self.assertEqual([inventory.namespace(entry['start']) for entry in value['entries']],
                         [entry[0] for entry in WORKFLOW_LITERALS])
        self.assertEqual(sum(entry[0] == 'maintenance' for entry in WORKFLOW_LITERALS), 7)
        self.assertEqual(sum(entry[0] == 'validation' for entry in WORKFLOW_LITERALS), 23)
        self.assertFalse(any(entry[0] in ('calibration', 'python-regression') for entry in WORKFLOW_LITERALS))
        paper = [entry for entry in value['entries'] if entry['start'] == 'evas/validation/paper']
        self.assertEqual([entry['pattern'] for entry in paper], [
            'test_criteria.py', 'test_*root*.py', 'test_coefficient_first_order.py', 'test_precision.py',
            'test_precision_binding.py', 'test_precision_v2.py', 'test_primitives.py'])
        self.assertTrue(all(entry['namespace'] == 'validation' and entry['job'] == 'provenance-paper' for entry in paper))
        observed_paper = sorted(path.name for path in (ROOT / 'evas/validation/paper').glob('test_*.py'))
        self.assertEqual(observed_paper, list(PAPER_TEST_MODULES))
        for name in PAPER_TEST_MODULES:
            matches = [entry for entry in paper if fnmatch.fnmatchcase(name, entry['pattern'])]
            self.assertEqual(len(matches), 1, name)
        calibration = [entry for entry in value['entries'] if entry['start'] == 'evas/validation/checker_calibration']
        self.assertEqual([literal_identity(entry) for entry in calibration], [(
            'validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance',
            'evas/validation/checker_calibration', 'test*.py')])
        differential = [entry for entry in value['entries'] if entry['start'] == 'evas/validation/differential']
        self.assertEqual([literal_identity(entry) for entry in differential], [(
            'validation', 'properties-and-ngspice', None, 'evas/validation/differential', 'test*.py')])
        primary = inventory.primary_entry(ROOT, value)
        self.assertEqual(primary['namespace'], 'python-regression')
        self.assertEqual(primary['start'], 'evas/tests')
        self.assertEqual(primary['pattern'], 'test*.py')
        self.assertNotIn(('python-regression', 'evas/tests'), {(entry['namespace'], entry['start']) for entry in value['entries']})
        scripts = [entry for entry in value['script_entries'] if entry['kind'] == 'direct-math-script']
        self.assertEqual([entry['source'] for entry in scripts], list(DIRECT_MATH_SCRIPTS))
        self.assertTrue(all(entry['method_denominator'] is None and not entry['executed'] for entry in scripts))

    def test_missing_or_duplicate_comparison_literal_is_rejected(self):
        raw = (ROOT / inventory.WORKFLOW).read_bytes()
        needle = b"          python3 -B -m unittest discover -s experiments/backends/comparison -p 'test_*.py' -v\n"
        self.assertEqual(raw.count(needle), 1)
        expected = list(WORKFLOW_LITERALS)
        comparison = (
            'validation', 'provenance-paper', 'Paper contracts, observable criteria and table provenance',
            'experiments/backends/comparison', 'test_*.py')
        self.assertEqual(expected[25][3:], ('experiments/backends/paper', 'test_*.py'))
        self.assertEqual(expected[26], comparison)
        self.assertEqual(expected[27][3:], ('evas/validation/support', 'test_*.py'))
        self.assertEqual(sum(row == comparison for row in expected), 1)
        missing_ids = [literal_identity(entry) for entry in inventory.parse_workflow(raw.replace(needle, b'', 1))['entries']]
        duplicate_ids = [literal_identity(entry) for entry in inventory.parse_workflow(raw.replace(needle, needle + needle, 1))['entries']]
        self.assertEqual(missing_ids, expected[:26] + expected[27:])
        self.assertNotEqual(missing_ids, expected)
        self.assertEqual(duplicate_ids, expected[:27] + [comparison] + expected[27:])
        self.assertNotEqual(duplicate_ids, expected)
        self.assertNotIn('evas/tests', [row[3] for row in expected])

    def test_inline_pipe_and_folded_origins_retained(self):
        raw = b'''jobs:
  examples:
    steps:
      - name: A
        run: |
          python3 -B -m unittest discover -s evas/validation/a -p 'test_*.py' -v
      - run: python3 -B -m unittest discover -s evas/validation/b -v
      - run: >-
          python3 -B evas/validation/check_design_math.py
          --a literal
'''
        result = inventory.parse_workflow(raw)
        self.assertEqual([e['start'] for e in result['entries']], ['evas/validation/a', 'evas/validation/b'])
        self.assertEqual(result['entries'][0]['step'], 'A')
        self.assertIsNone(result['entries'][1]['step'])
        self.assertEqual(result['script_entries'][0]['command'], 'python3 -B evas/validation/check_design_math.py --a literal')

    def test_dynamic_or_unknown_unittest_syntax_fails_instead_of_guessing(self):
        for command in (
                'python3 -B -m unittest discover -s "$ROOT"',
                'python3 -B -m unittest discover -s tests -p "$PATTERN"',
                'python3 -B -m unittest discover -s tests && true',
                'python3 -B -m unittest discover -s tests --top-level-directory elsewhere',
                'python3 -m unittest discover -s tests',
                'python3 -B -m unittest discover -s tests -s elsewhere'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                inventory.parse_workflow(('jobs:\n  a:\n    steps:\n      - run: ' + command + '\n').encode())

    def test_unknown_dynamic_phase_env_fails_but_known_outputs_are_declared(self):
        raw = b'''jobs:
  a:
    steps:
      - name: discovery
        env:
          DATA: ${{ secrets.UNKNOWN }}
        run: python3 -B -m unittest discover -s scripts/tests
'''
        with self.assertRaisesRegex(ValueError, 'dynamic environment'):
            inventory.parse_workflow(raw)
        parsed = inventory.parse_workflow(raw.replace(b'${{ secrets.UNKNOWN }}', b'${{ steps.changes.outputs.base }}'))
        self.assertIn('${{ steps.changes.outputs.base }}', parsed['entries'][0]['environment_overrides'].values())

    def test_named_explicit_checks_are_recorded_as_ci_by_name_entries(self):
        parsed = inventory.parse_workflow(NAMED_STEP)
        self.assertEqual(parsed['entries'], [])
        self.assertEqual(parsed['script_entries'], [])
        self.assertEqual(parsed['explicit_check_count'], 1)
        entry, = parsed['explicit_check_entries']
        self.assertEqual((entry['job'], entry['step'], entry['step_if'], entry['line']), ('checks', 'Named check', None, 10))
        self.assertEqual((entry['kind'], entry['collector'], entry['namespace']),
                         ('ci-named-explicit-check', 'explicit-check', 'python-regression'))
        self.assertEqual(entry['checks'], ['test_a.A.check_one', 'test_a.A.check_two'])
        self.assertEqual(entry['required_environment'], ['KERNEL_PATH'])
        self.assertEqual((entry['start'], entry['report']), ('evas/tests', 'runs/explicit-checks.json'))
        self.assertEqual(entry['environment_overrides'],
                         {'PYTHONPATH': 'evas/src', 'KERNEL_PATH': 'evas/rust_core/target/release/evas-kernel'})
        self.assertEqual(entry['entry_id'], inventory.canonical({k: v for k, v in entry.items() if k != 'entry_id'}))

    def test_unknown_or_dynamic_explicit_check_forms_fail_instead_of_guessing(self):
        good = EXPLICIT + ' --start evas/tests --check test_a.A.check_one --report runs/r.json'
        self.assertEqual(len(inventory.parse_workflow(('jobs:\n  a:\n    steps:\n      - run: ' + good + '\n').encode())
                             ['explicit_check_entries']), 1)
        for command in (
                EXPLICIT + ' --start evas/tests --report runs/r.json',
                EXPLICIT + ' --check test_a.A.check_one --report runs/r.json',
                EXPLICIT + ' --start evas/tests --check test_a.A.check_one',
                EXPLICIT + ' --start evas/tests --check "$CHECK" --report runs/r.json',
                good + ' && true',
                good + ' > runs/out.txt',
                good + ' --unknown value',
                good + ' --start other',
                good + ' --check test_a.A.check_one',
                good + ' --require-env',
                good + ' --require-env BAD-NAME',
                EXPLICIT + ' --start evas/tests --check test_a.A.test_one --report runs/r.json',
                EXPLICIT + ' --start evas/tests --check test_a.A --report runs/r.json',
                EXPLICIT + ' --start ../tests --check test_a.A.check_one --report runs/r.json',
                'python3 scripts/run_explicit_checks.py --start evas/tests --check test_a.A.check_one --report runs/r.json',
                'python3 -B ./scripts/run_explicit_checks.py --start evas/tests --check test_a.A.check_one --report runs/r.json',
                'python -B scripts/run_explicit_checks.py --start evas/tests --check test_a.A.check_one --report runs/r.json'):
            with self.subTest(command=command), self.assertRaises(ValueError):
                inventory.parse_workflow(('jobs:\n  a:\n    steps:\n      - run: ' + command + '\n').encode())

    def test_dynamic_environment_on_an_explicit_check_entry_fails(self):
        raw = NAMED_STEP.replace(b'KERNEL_PATH: evas/rust_core', b'KERNEL_PATH: ${{ secrets.X }}/evas/rust_core')
        with self.assertRaisesRegex(ValueError, 'dynamic environment'):
            inventory.parse_workflow(raw)

    def test_rust_regression_runs_the_rc_check_by_name_in_both_package_selections(self):
        raw = (ROOT / inventory.WORKFLOW).read_bytes()
        parsed = inventory.parse_workflow(raw)
        entry, = parsed['explicit_check_entries']
        self.assertEqual((entry['job'], entry['job_if']), ('rust-regression', "needs.selection.outputs.regression == 'true'"))
        # No step condition: the check runs whether or not the package job is selected.
        self.assertIsNone(entry['step_if'])
        self.assertEqual(entry['checks'], [RC_CHECK])
        self.assertEqual((entry['start'], entry['required_environment']), ('evas/tests', ['EVAS_TEST_KERNEL']))
        self.assertEqual(entry['environment_overrides']['EVAS_TEST_KERNEL'], 'evas/rust_core/target/release/evas-kernel')
        self.assertEqual(entry['environment_overrides']['PYTHONPATH'], 'evas/src')
        job = raw.decode().split('\n  rust-regression:\n')[1].split('\n  regression:\n')[0]
        self.assertNotIn('continue-on-error', job)
        step = job.split('      - name: ' + entry['step'] + '\n')[1].split('\n      - ')[0]
        self.assertNotIn('if:', step)
        # The step builds its own release kernel under the job's Rust cache, so it does
        # not depend on the source-delivery build that is skipped when package is selected.
        build = '          cargo build --locked --release --manifest-path evas/rust_core/Cargo.toml\n'
        self.assertIn(build, step)
        self.assertLess(step.index(build), step.index(EXPLICIT))
        self.assertLess(job.index('uses: ./.github/actions/rust-cache'), job.index(entry['step']))
        self.assertNotIn('outputs.package', step)
        self.assertEqual(sum(e['job'] == 'rust-regression' for e in parsed['entries']), 0)
        registry = json.loads((ROOT / 'evas/capabilities/data/registry.json').read_text())
        checks = [c for o in registry['objects'] if o.get('kind') == 'case' for c in o.get('checks', [])]
        self.assertIn({'module': 'evas/tests/test_output_point_limit.py', 'runtime_id': RC_CHECK}, checks)

    def test_a_missing_or_incomplete_rc_receipt_fails_the_rust_regression_job(self):
        # The runner records every early end, but a separate step reads only its receipt, so a
        # runner that ends with status 0 and no complete receipt still fails the job.
        raw = (ROOT / inventory.WORKFLOW).read_bytes()
        parsed = inventory.parse_workflow(raw)
        entry, = parsed['explicit_check_entries']
        job = raw.decode().split('\n  rust-regression:\n')[1].split('\n  regression:\n')[0]
        steps = job.split('\n      - ')
        index = next(i for i, step in enumerate(steps) if step.startswith('name: ' + entry['step'] + '\n'))
        verify = steps[index + 1]
        self.assertTrue(verify.startswith('name: Require a complete receipt for the dynamic RC check\n'), verify)
        self.assertNotIn('if:', verify)
        command = ('python3 -B scripts/verify_explicit_checks.py --report ' + entry['report'] + ' --check ' + RC_CHECK
                   + ' --require-file-env EVAS_TEST_KERNEL')
        self.assertEqual(verify.split('\n')[1], '        run: ' + command)
        script, = [e for e in parsed['script_entries'] if e['source'] == 'scripts/verify_explicit_checks.py']
        self.assertEqual((script['job'], script['step_if'], script['command']), ('rust-regression', None, command))
        upload = steps[index + 2]
        self.assertIn('name: explicit-checks\n', upload)
        self.assertIn('if: always()\n', upload)
        self.assertIn('path: ' + entry['report'] + '\n', upload)
        self.assertIn('if-no-files-found: error\n', upload)
        self.assertNotIn('if-no-files-found: warn', job)

    def test_capability_discovery_and_namespace_patch_are_present(self):
        value = inventory.parse_workflow((ROOT / inventory.WORKFLOW).read_bytes())
        entry = next(e for e in value['entries'] if e['start'] == 'evas/capabilities')
        self.assertEqual(entry['pattern'], 'test_*.py')
        self.assertEqual(entry['namespace'], 'maintenance')
        catalog = load(ROOT / 'evas/capabilities/asset_catalog.py', 'catalog_namespace_fixture')
        self.assertIn('validation', catalog.NAMESPACES)


class ConstructionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=os.environ.get('CI_INVENTORY_FIXTURE_TMP'))
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'root'
        self.root.mkdir()
        self.root = self.root.resolve()
        for path in ('scripts/capabilities/discover_methods.py', 'scripts/capabilities/observe_assets.py',
                     'scripts/capabilities/collect_ci_inventory.py'):
            self.write(path, (ROOT / path).read_text())
        self.write('scripts/run_regression.py', '''import argparse
p=argparse.ArgumentParser()
p.add_argument('--pattern',default='test*.py')
p.add_argument('--start-directory',default='evas/tests')
''')
        self.write('scripts/helper.py', 'VALUE=1\n')
        self.write('scripts/tests/test_one.py', '''import unittest
from scripts.helper import VALUE
class A(unittest.TestCase):
    def test_one(self):
        raise AssertionError('scientific/test body must never run')
''')
        self.write('evas/capabilities/test_meta.py', '''import unittest
class Meta(unittest.TestCase):
    def test_one(self): raise AssertionError('body not allowed')
''')
        self.write('evas/validation/demo/test_one.py', '''import unittest
class Validation(unittest.TestCase):
    def test_one(self): raise AssertionError('body not allowed')
''')
        self.write('evas/tests/testfactory.py', '''import unittest
def factory():
    def implementation(self): raise AssertionError('factory body not allowed')
    return implementation
class Main(unittest.TestCase): pass
setattr(Main,'test_generated',factory())
''')
        self.write('evas/validation/paper/test_unrouted.py', "raise AssertionError('unrouted file must never import')\n")
        self.write(inventory.WORKFLOW, '''jobs:
  selection:
    steps:
      - run: python3 -B -m unittest discover -s scripts/tests -p test_one.py
  static-checks:
    steps:
      - name: actual construction
        run: |
          python3 -B -m unittest discover -s scripts/tests
          python3 -B -m unittest discover -s evas/capabilities -p 'test_*.py'
          python3 -B -m unittest discover -s evas/validation/demo
  regression:
    steps:
      - run: python3 -B scripts/run_regression.py --shard-count 1
''')

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def observed(self, root, **kwargs):
        # Explicit fixture-only source observation, not an actual Git receipt.
        return {'schema_version': 1, 'producer': 'fixture-not-a-real-Git-observer',
                'source_kind': 'synthetic-fixture', 'source_profile': 'fixture-files-only',
                'assets': [{'path': p.relative_to(root).as_posix(),
                            'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                            'git_mode': '100644', 'actual_mode': p.stat().st_mode & 0o777}
                           for p in sorted(Path(root).rglob('*')) if p.is_file()]}

    def collect(self, **kwargs):
        return inventory.collect(self.root, self.base / 'receipts', observer=self.observed, **kwargs)

    def named_check_fixture(self, registered=True):
        self.write('scripts/run_explicit_checks.py', (ROOT / 'scripts/run_explicit_checks.py').read_text())
        self.write('evas/tests/test_named.py', 'import unittest\nclass Named(unittest.TestCase):\n'
                   '    def check_one(self): raise AssertionError("check body must never run here")\n')
        checks = [{'module': 'evas/tests/test_named.py', 'runtime_id': 'test_named.Named.check_one'}] if registered else []
        self.write('evas/capabilities/data/registry.json', json.dumps(
            {'objects': [{'id': 'case:named', 'version': '1', 'kind': 'case', 'checks': checks}],
             'current': {'case:named': '1'}}))
        workflow = (self.root / inventory.WORKFLOW).read_text().replace('  regression:\n', '''  named:
    steps:
      - name: Named check
        env:
          FIXTURE_KERNEL: kernel
        run: python3 -B scripts/run_explicit_checks.py --start evas/tests --require-env FIXTURE_KERNEL --check test_named.Named.check_one --report runs/explicit-checks.json
  regression:
''')
        self.write(inventory.WORKFLOW, workflow)

    def test_named_check_entries_are_validated_statically_and_written(self):
        self.named_check_fixture()
        result = self.collect(mode='observe-only')
        self.assertTrue(result['success'], result)
        self.assertEqual(result['explicit_checks'], ['test_named.Named.check_one'])
        written = json.loads((self.base / 'receipts/explicit-check-entrypoints.json').read_text())
        entry, = written['entries']
        self.assertEqual((entry['job'], entry['kind'], entry['checks']),
                         ('named', 'ci-named-explicit-check', ['test_named.Named.check_one']))
        check, = entry['resolved']
        self.assertEqual((check['module'], check['line'], check['registered_by']),
                         ('evas/tests/test_named.py', 3, ['case:named@1']))
        self.assertEqual(check['module_sha256'], hashlib.sha256((self.root / 'evas/tests/test_named.py').read_bytes()).hexdigest())
        self.assertIsNone(written['method_denominator'])
        self.assertFalse(result['scientific_execution'])

    def test_a_renamed_or_unregistered_named_check_fails_construction(self):
        for name, change in (('renamed', lambda: self.write('evas/tests/test_named.py', 'import unittest\n'
                              'class Named(unittest.TestCase):\n    def check_two(self): pass\n')),
                             ('deleted', lambda: (self.root / 'evas/tests/test_named.py').unlink()),
                             ('unregistered', lambda: self.named_check_fixture(registered=False))):
            with self.subTest(name):
                self.named_check_fixture()
                change()
                result = inventory.collect(self.root, self.base / ('receipts-' + name), observer=self.observed,
                                           mode='observe-only')
                self.assertFalse(result['success'])
                self.assertRegex(result['errors'][0]['message'], 'CI named explicit check')

    def test_independent_children_construct_only_and_keep_unique_vs_instance_counts(self):
        result = self.collect(mode='observe-only')
        self.assertTrue(result['success'], result)
        self.assertTrue(result['construction_complete'])
        self.assertFalse(result['reconciled'])
        self.assertFalse(result['scientific_execution'])
        self.assertEqual(result['denominators']['maintenance']['instance_count'], 3)
        self.assertEqual(result['denominators']['maintenance']['unique_method_count'], 2)
        self.assertEqual(result['denominators']['python-regression']['generated_count'], 1)
        entry = json.loads((self.base / 'receipts/entry-000.json').read_text())
        transport = entry['receipt']['transport']
        self.assertEqual(transport['cwd'], str(self.root))
        self.assertIn('stdout', transport)
        self.assertIn('stderr', transport)
        self.assertTrue(entry['receipt']['environment']['bytecode_disabled'])
        self.assertEqual(entry['receipt']['collector']['source_relationship'], 'owned-source-root')
        unrouted = json.loads((self.base / 'receipts/unrouted-paper.json').read_text())
        self.assertEqual(len(unrouted['files']), 1)
        self.assertIsNone(unrouted['methods'])

    def test_import_error_is_retained_and_construction_fails(self):
        self.write('evas/validation/demo/test_broken.py', 'raise ImportError("fixture import failure")\n')
        result = self.collect(mode='observe-only')
        self.assertFalse(result['success'])
        receipt = json.loads((self.base / 'receipts/entry-003.json').read_text())['receipt']
        self.assertIn('fixture import failure', receipt['transport']['stdout'])
        self.assertFalse(receipt['complete'])

    def test_import_side_effect_failure_is_not_reported_as_a_test_body_result(self):
        self.write('evas/validation/demo/test_process.py', 'import subprocess\nsubprocess.run(["never-launch"])\n')
        result = self.collect(mode='observe-only')
        self.assertFalse(result['success'])
        receipt = json.loads((self.base / 'receipts/entry-003.json').read_text())['receipt']
        self.assertIn('discovery side effect blocked', receipt['transport']['stdout'])

    def test_require_catalog_failure_never_falls_back_to_observe(self):
        def reject(*args):
            raise ValueError('full data/history/bridges missing')
        result = self.collect(mode='require-catalog', reconciler=reject)
        self.assertTrue(result['construction_complete'])
        self.assertFalse(result['success'])
        self.assertFalse(result['reconciled'])
        self.assertEqual(result['mode'], 'require-catalog')

    def test_observe_only_never_calls_catalog_reconciliation(self):
        def forbidden(*args):
            raise AssertionError('observe-only is construction-only')
        result = self.collect(mode='observe-only', reconciler=forbidden)
        self.assertTrue(result['success'], result)

    def test_namespace_source_identity_conflict_is_rejected(self):
        calls = 0
        def changed(root, entry, timeout):
            nonlocal calls
            receipt = inventory.child(root, entry, timeout)
            calls += 1
            if calls == 2:
                receipt['methods'][0]['definition']['sha256'] = 'f' * 64
            return receipt
        result = self.collect(mode='observe-only', collector=changed)
        self.assertFalse(result['success'])
        self.assertIn('identity/source conflict', result['errors'][0]['message'])

    def test_same_source_skip_and_native_runtime_observations_can_differ(self):
        first = {'schema_version': 1, 'namespace': 'validation', 'complete': True, 'errors': [],
                 'discovered_instances': 1, 'methods': [{'module_path': 'module.py', 'runtime_id': 'A.test_x',
                 'module_sha256': 'a' * 64, 'definition': {'path': 'module.py', 'sha256': 'b' * 64, 'line': 1, 'name': 'test_x'},
                 'generated': False, 'skip_declaration': {'declared': True},
                 'native_skip_wrapper': {'authority_sha256': 'c' * 64}}]}
        second = copy.deepcopy(first)
        second['methods'][0]['skip_declaration']['declared'] = False
        second['methods'][0]['native_skip_wrapper']['authority_sha256'] = 'd' * 64
        entries = [{'namespace': 'validation', 'entry_id': 'one'}, {'namespace': 'validation', 'entry_id': 'two'}]
        merged = inventory.merge_entries(entries, [first, second])['validation']
        self.assertEqual(merged['instance_count'], 2)
        self.assertEqual(merged['unique_method_count'], 1)
        self.assertEqual(len(merged['methods'][0]['discovery_observations']), 2)

    def test_runtimeID_collision_in_distinct_owner_modules_is_not_swallowed(self):
        workflow = (self.root / inventory.WORKFLOW).read_text()
        workflow = workflow.replace('  regression:\n', '''  extra:
    steps:
      - run: python3 -B -m unittest discover -s evas/validation/one
      - run: python3 -B -m unittest discover -s evas/validation/two
  regression:
''')
        self.write(inventory.WORKFLOW, workflow)
        body = 'import unittest\nclass Same(unittest.TestCase):\n def test_same(self): raise AssertionError("no body")\n'
        self.write('evas/validation/one/test_collision.py', body)
        self.write('evas/validation/two/test_collision.py', body)
        result = self.collect(mode='observe-only')
        self.assertTrue(result['success'], result)
        self.assertEqual(result['denominators']['validation']['unique_method_count'], 3)

    def test_changed_source_or_workflow_during_construction_fails(self):
        calls = 0
        def observe(root, **kwargs):
            nonlocal calls
            calls += 1
            value = self.observed(root)
            if calls == 2:
                value['assets'][0]['actual_mode'] ^= 1
            return value
        result = inventory.collect(self.root, self.base / 'receipts', mode='observe-only', observer=observe)
        self.assertFalse(result['success'])
        self.assertIn('changed during discovery', result['errors'][0]['message'])

    def test_require_catalog_reads_each_history_with_explicit_local_repository_map(self):
        entry = {'namespace': 'validation', 'start': 'evas/validation/demo', 'pattern': 'test*.py', 'entry_id': 'one'}
        calls = []
        registered = dict(entry, collector='unittest', ci_entrypoint_ids=['one'],
                          workflow_sha256=inventory.sha((self.root / inventory.WORKFLOW).read_bytes()))
        catalog = types.SimpleNamespace(
            validate=lambda: calls.append('validate'),
            current=lambda kind: [registered] if kind == 'entrypoint' else [{'namespace': 'validation'}] if kind == 'method' else [{'fixture': kind}],
            read_history=lambda obj: calls.append(obj['id']),
            reconcile_assets=lambda rows, **kw: {'ok': True},
            reconcile_methods=lambda ns, receipt: calls.append(ns),
            namespace_counts=lambda: {'validation': {'methods': 1}})
        registry = types.SimpleNamespace(data={'asset_scope': {'id': 'EVAS-scope-v1'}},
            objects={('history1', '1'): {'id': 'history1', 'kind': 'historical-audit-record'},
                     ('history2', '1'): {'id': 'history2', 'kind': 'historical-finding'}},
            catalog=lambda: catalog)
        def bound_load(data, **kwargs):
            self.assertEqual(kwargs['repositories'], {'vaevas': self.root})
            return registry
        with patch.object(inventory, 'load', return_value=types.SimpleNamespace(load=bound_load)):
            result = inventory.require_catalog(self.root, self.root / 'data', self.observed(self.root),
                                               {'validation': {'fixture': 'method receipt'}}, [entry])
        self.assertEqual(calls, ['validate', 'history1', 'history2', 'validation'])
        self.assertEqual(result['historical_rows_read'], 2)
        self.assertIn('pending', result['rust_status'])

    def test_registered_namespace_without_actual_discovery_is_not_reconciled(self):
        catalog = types.SimpleNamespace(
            validate=lambda: None,
            current=lambda kind: [{'namespace': 'calibration'}] if kind == 'method' else [{}] if kind == 'asset' else [],
            read_history=lambda obj: {},
            reconcile_assets=lambda rows, **kw: {'ok': True},
            reconcile_methods=lambda ns, receipt: None,
            namespace_counts=lambda: {'calibration': {'methods': 1}})
        registry = types.SimpleNamespace(data={'asset_scope': {'id': 'EVAS-scope-v1'}},
            objects={('h', '1'): {'kind': 'historical-audit-record'}}, catalog=lambda: catalog)
        with patch.object(inventory, 'load', return_value=types.SimpleNamespace(load=lambda *a, **kw: registry)):
            with self.assertRaisesRegex(ValueError, 'namespace has no actual discovery'):
                inventory.require_catalog(self.root, self.root / 'data', self.observed(self.root), {}, [])

    def test_require_catalog_history_retrieval_failure_is_not_structure_success(self):
        def unavailable(obj):
            raise ValueError('exact archived history bytes unavailable')
        catalog = types.SimpleNamespace(validate=lambda: None, current=lambda kind: [{}], read_history=unavailable)
        registry = types.SimpleNamespace(data={'asset_scope': {'id': 'EVAS-scope-v1'}},
            objects={('h', '1'): {'kind': 'historical-audit-record'}}, catalog=lambda: catalog)
        with patch.object(inventory, 'load', return_value=types.SimpleNamespace(load=lambda *a, **kw: registry)):
            with self.assertRaisesRegex(ValueError, 'history bytes unavailable'):
                inventory.require_catalog(self.root, self.root / 'data', {}, {}, [])

    def test_invalid_child_JSON_preserves_actual_stdout_and_stderr(self):
        entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',
                     environment_overrides={}, declared_python_versions=[])
        proc = types.SimpleNamespace(returncode=2, stdout='fixture non-JSON stream\n', stderr='fixture complete error stream\n')
        with patch.object(inventory.subprocess, 'run', return_value=proc):
            receipt = inventory.child(self.root, entry, 1)
        self.assertFalse(receipt['complete'])
        self.assertEqual(receipt['transport']['stdout'], proc.stdout)
        self.assertEqual(receipt['transport']['stderr'], proc.stderr)

    def test_patch_pinned_workflow_python_matches_by_major_minor(self):
        current = '%d.%d' % sys.version_info[:2]
        proc = types.SimpleNamespace(returncode=2, stdout='fixture non-JSON stream\n', stderr='')
        for declared in ([current], [current + '.99']):
            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',
                         environment_overrides={}, declared_python_versions=declared)
            with patch.object(inventory.subprocess, 'run', return_value=proc):
                self.assertFalse(inventory.child(self.root, entry, 1)['complete'])
        other_minor = '%d.%d.1' % (sys.version_info[0], sys.version_info[1] + 1)
        for declared in ([other_minor], [current, current], [current + '.not-a-version'], [current + '.'],
                         [current + '.15.extra'], [str(sys.version_info[0])], [current + 'x']):
            entry = dict(start='scripts/tests', pattern='test*.py', namespace='maintenance',
                         environment_overrides={}, declared_python_versions=declared)
            with patch.object(inventory.subprocess, 'run') as run, self.assertRaisesRegex(ValueError, 'major/minor'):
                inventory.child(self.root, entry, 1)
            run.assert_not_called()


class RequiredGateTests(unittest.TestCase):
    def setUp(self):
        self.ci = load(ROOT / 'scripts/ci_selection.py', 'inventory_ci_fixture')

    def needs(self, mode='iteration'):
        outputs = dict(plan_version='2', mode=mode, **{key: 'false' for key in self.ci.CHECKS})
        needs = {'selection': {'result': 'success', 'outputs': outputs},
                 'fast-checks': {'result': 'success'}, 'regression-coverage': {'result': 'skipped'},
                 'catalog-inventory': {'result': 'success'}}
        needs.update({job: {'result': 'skipped'} for job in self.ci.JOB_FLAGS})
        return needs

    def test_gate_always_requires_inventory_without_changing_scientific_JOB_FLAGS(self):
        for mode in ('iteration', 'delivery'):
            needs = self.needs(mode)
            self.assertEqual(self.ci.gate_errors(needs), [])
            for value in ('failure', 'cancelled', 'skipped', None):
                bad = copy.deepcopy(needs)
                if value is None:
                    bad.pop('catalog-inventory')
                else:
                    bad['catalog-inventory']['result'] = value
                self.assertTrue(any('catalog-inventory' in x for x in self.ci.gate_errors(bad)), (mode, value))
        self.assertNotIn('catalog-inventory', self.ci.JOB_FLAGS)

    def test_workflow_has_dedicated_unconditional_phase_and_always_artifact(self):
        workflow = (ROOT / inventory.WORKFLOW).read_text()
        block = workflow.split('  catalog-inventory:\n')[1].split('  static-checks:\n')[0]
        self.assertIn('needs: [selection, fast-checks]', block)
        self.assertNotIn('outputs.maintenance', block)
        self.assertIn('--require-catalog --registry-data evas/capabilities/data', block)
        self.assertNotIn('--observe-only', block)
        self.assertIn('scripts/traceability.py --check --catalog-data evas/capabilities/data', workflow)
        self.assertIn('if: always()', block)
        result = workflow.split('  ci-result:\n')[1]
        self.assertIn('catalog-inventory', result.split('    if: always()')[0])


if __name__ == '__main__':
    unittest.main(verbosity=2)

"""Exercise cache and raw-result collection through the public evidence CLI."""
import ast
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import git_fixture

EVIDENCE = Path(__file__).resolve().parents[1] / 'ci_evidence.py'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observation(identity, outcome='passed'):
    site = dict(module='test_fixture', line=10, source_sha256='a' * 64)
    condition = dict(id='condition', phase='test', site=site, identity_complete=True, outcome=outcome)
    if outcome != 'passed':
        condition['reason'] = dict(kind='assertion', message='fixture failure', site=site,
                                   exception_type='builtins.AssertionError', attribution='unreviewed-observation')
    report = dict(schema_version=3, complete=True, collection_complete=True,
                  successful=outcome not in ('failed', 'error', 'unexpected_success'),
                  tests_run=1, failures=int(outcome == 'failed'), errors=int(outcome == 'error'),
                  skipped=int(outcome == 'skipped'), expected_failures=int(outcome == 'expected_failure'),
                  unexpected_successes=int(outcome == 'unexpected_success'),
                  tests=[dict(id='demo.Case.test_one', outcome=outcome, seconds=.1, conditions=[condition])],
                  fixtures=[], setup_skipped_test_ids=[], discovered_test_ids=['demo.Case.test_one'],
                  selected_test_ids=['demo.Case.test_one'], assignment=[['demo.Case.test_one'], []],
                  shard_count=2, shard_index=0,
                  metadata=dict(criteria_id='1'*64, language_profile='2'*64, collector_sha256='3'*64,
                                runtime_profile={'backend': 'debug'}, invocation={'pattern': 'test_*.py'}),
                  source_identity={'execution_identity': identity})
    report['input_identity'] = digest({key: report[key] for key in ('metadata', 'source_identity', 'selected_test_ids')})
    return report


class EvidenceV3Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        git_fixture.bind(self, self.root)
        git_fixture.run(['init', str(self.root)], scratch=self.root, check=True, capture_output=True)
        (self.root / 'input.txt').write_text('actual fixture input\n')
        git_fixture.run(['-C', str(self.root), 'add', 'input.txt'], scratch=self.root, check=True, capture_output=True)
        kernel = self.root / 'evas/rust_core/target/debug/evas-kernel'
        kernel.parent.mkdir(parents=True)
        kernel.write_bytes(b'fixture kernel identity')
        toolbin = self.root / 'tools'
        toolbin.mkdir()
        for name in ('rustc', 'cargo'):
            tool = toolbin / name
            tool.write_text('#!/bin/sh\necho "fixture-tool-version-1"\n')
            tool.chmod(0o755)
        self.env = git_fixture.child_env(PATH=str(toolbin) + os.pathsep + os.environ['PATH'])
        self.identity_path = self.root / 'identity.json'
        self.report_path = self.root / 'report.json'
        self.receipt_path = self.root / 'receipt.json'
        result = self.run_cli('identity')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.identity = json.loads(self.identity_path.read_text())
        self.write_report(observation(self.identity))

    def run_cli(self, operation, *args):
        command = [sys.executable, '-B', str(EVIDENCE), operation, '--repo', str(self.root),
                   '--identity', str(self.identity_path), '--shard', '0-of-2']
        if operation != 'identity':
            command += ['--report', str(self.report_path), '--receipt', str(self.receipt_path)]
        return subprocess.run(command + list(args), env=self.env, capture_output=True, text=True)

    def write_report(self, report):
        self.report_path.write_text(json.dumps(report))

    def test_format_version_binds_fingerprint_and_receipt(self):
        self.assertEqual(self.identity['report_schema_version'], 3)
        self.assertEqual(self.identity['evidence_schema_version'], 3)
        self.assertEqual(self.run_cli('record').returncode, 0)
        receipt = json.loads(self.receipt_path.read_text())
        self.assertEqual(receipt['report_schema_version'], 3)
        self.assertEqual(receipt['evidence_schema_version'], 3)
        self.assertEqual(self.run_cli('verify').returncode, 0)
        receipt.pop('report_schema_version')
        self.receipt_path.write_text(json.dumps(receipt))
        self.assertNotEqual(self.run_cli('verify').returncode, 0)

    def test_selected_kernel_override_and_actual_bytes_invalidate_cached_pass(self):
        for selector in ('EVAS_KERNEL', 'EVAS_TEST_KERNEL', 'EVAS_CAUSAL_KERNEL', 'FORCING_SHAPE_KERNEL'):
            selected = self.root / 'selected-kernel'
            other = self.root / 'other-kernel'
            selected.write_bytes(b'kernel-A')
            other.write_bytes(b'kernel-B')
            self.env[selector] = str(selected)
            self.assertEqual(self.run_cli('identity').returncode, 0)
            identity = json.loads(self.identity_path.read_text())
            self.write_report(observation(identity))
            self.assertEqual(self.run_cli('record').returncode, 0)
            self.assertEqual(self.run_cli('verify').returncode, 0)
            self.env[selector] = str(other)
            self.assertNotEqual(self.run_cli('verify').returncode, 0)
            self.assertEqual(self.run_cli('identity').returncode, 0)
            self.assertNotEqual(json.loads(self.identity_path.read_text())['key'], identity['key'])
            self.env[selector] = str(selected)
            self.identity_path.write_text(json.dumps(identity))
            selected.write_bytes(b'replaced-at-same-path')
            self.assertNotEqual(self.run_cli('verify').returncode, 0)
            self.assertNotEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)
            del self.env[selector]

    def test_missing_selected_kernel_cannot_generate_cache_identity(self):
        for selector in ('EVAS_KERNEL', 'EVAS_TEST_KERNEL', 'EVAS_CAUSAL_KERNEL', 'FORCING_SHAPE_KERNEL'):
            self.env[selector] = str(self.root / 'missing-kernel')
            self.assertNotEqual(self.run_cli('identity').returncode, 0)
            self.assertNotEqual(self.run_cli('verify').returncode, 0)
            del self.env[selector]

    def test_default_kernel_permissions_are_part_of_execution_identity(self):
        self.assertEqual(self.run_cli('record').returncode, 0)
        kernel = self.root / 'evas/rust_core/target/debug/evas-kernel'
        kernel.chmod(kernel.stat().st_mode ^ 0o100)
        self.assertNotEqual(self.run_cli('verify').returncode, 0)

    def test_every_literal_python_environment_consumer_is_registered(self):
        spec = importlib.util.spec_from_file_location('evidence_environment_policy', EVIDENCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        consumers=set()
        unresolved=[]
        root=EVIDENCE.parents[1]
        for directory in ('evas/tests','evas/src'):
            for path in (root/directory).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text())):
                    if isinstance(node,ast.Call) and node.args:
                        func=node.func
                        if isinstance(func,ast.Attribute) and (func.attr=='getenv' or
                                (func.attr=='get' and isinstance(func.value,ast.Attribute)
                                 and func.value.attr=='environ')):
                            if isinstance(node.args[0],ast.Constant) and isinstance(node.args[0].value,str):
                                consumers.add(node.args[0].value)
                            else:
                                unresolved.append((str(path),node.lineno))
                    if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Attribute) and node.value.attr=='environ':
                        if isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):
                            consumers.add(node.slice.value)
                        else:
                            unresolved.append((str(path),node.lineno))
        self.assertFalse(unresolved, 'Unresolved configuration consumers require review: '+str(unresolved))
        self.assertFalse(consumers-set(module.ENVIRONMENT), sorted(consumers-set(module.ENVIRONMENT)))
        self.assertTrue({key for key in consumers if key.endswith('_KERNEL')} <= set(module.KERNEL_SELECTORS))

    def test_rust_runtime_environment_reads_are_registered_or_explicitly_reviewed(self):
        spec=importlib.util.spec_from_file_location('rust_environment_policy',EVIDENCE)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        unresolved=[]
        consumers=set()
        for path in (EVIDENCE.parents[1]/'evas/rust_core/src').rglob('*.rs'):
            source=path.read_text()
            for match in re.finditer(r'env::var(?:_os)?\(([^)]+)\)',source):
                argument=match.group(1).strip()
                if argument.startswith('"') and argument.endswith('"'):
                    consumers.add(argument[1:-1])
                else:
                    # The one reviewed dynamic reader accepts only the two
                    # literal diagnostic_budget call sites in main.rs.
                    start=source.find('fn diagnostic_budget(')
                    end=source.find('\nfn main()',start)
                    if not (path.name=='main.rs' and argument=='name' and start<=match.start()<end):
                        unresolved.append((str(path),argument))
            consumers.update(re.findall(r'diagnostic_budget\("([^"\n]+)"',source))
        self.assertFalse(unresolved, 'Unresolved Rust runtime config: '+str(unresolved))
        self.assertFalse(consumers-set(module.ENVIRONMENT),sorted(consumers-set(module.ENVIRONMENT)))

    def test_requested_external_evidence_is_reexecuted_instead_of_cached(self):
        self.env['EVAS_RAMP_EVIDENCE_DIR']=str(self.root/'evidence-output')
        self.assertEqual(self.run_cli('identity').returncode,0)
        identity=json.loads(self.identity_path.read_text())
        self.write_report(observation(identity))
        result=self.run_cli('collect','--raw-exit','0')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(json.loads(result.stdout)['cacheable'])
        self.assertNotEqual(self.run_cli('record').returncode,0)

    def test_environment_presence_distinguishes_empty_from_default_configuration(self):
        self.assertEqual(self.run_cli('record').returncode,0)
        self.env['EVAS_STATIC_THREADS']=''
        self.assertNotEqual(self.run_cli('verify').returncode,0)
        self.assertEqual(self.run_cli('identity').returncode,0)
        self.assertNotEqual(json.loads(self.identity_path.read_text())['key'],self.identity['key'])

    def test_performance_profile_manifest_is_outside_portable_cache_scope(self):
        self.env['EVAS_PROFILE_INPUTS']=str(self.root/'profile-inputs.json')
        self.assertNotEqual(self.run_cli('identity').returncode,0)
        self.assertNotEqual(self.run_cli('verify').returncode,0)

    def test_collect_preserves_complete_raw_failure_without_claiming_merge(self):
        self.write_report(observation(self.identity, 'failed'))
        collected = self.run_cli('collect', '--raw-exit', '1')
        self.assertEqual(collected.returncode, 0, collected.stderr)
        facts = json.loads(collected.stdout)
        self.assertFalse(facts['raw_successful'])
        self.assertFalse(facts['cacheable'])
        self.assertNotIn('merge_allowed', facts)
        self.assertFalse(json.loads(self.report_path.read_text())['successful'])
        self.assertNotEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)
        self.assertNotEqual(self.run_cli('record').returncode, 0)
        self.assertFalse(self.receipt_path.exists())

    def test_successful_shard_caches_but_skips_xfails_and_errors_do_not(self):
        self.assertEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)
        self.assertEqual(self.run_cli('record').returncode, 0)
        for outcome in ('skipped', 'expected_failure', 'error', 'failed', 'unexpected_success'):
            self.write_report(observation(self.identity, outcome))
            self.assertNotEqual(self.run_cli('record').returncode, 0, outcome)
            self.assertNotEqual(self.run_cli('verify').returncode, 0, outcome)

    def test_fixture_skip_and_error_remain_collectable_but_never_cache(self):
        for outcome in ('skipped', 'error'):
            report = observation(self.identity)
            fixture = dict(report['tests'][0]['conditions'][0])
            fixture.update(scope='tearDownModule (fixture)', phase='teardown_module',
                           outcome=outcome, reason=dict(kind='exception', message='fixture outcome',
                           exception_type='builtins.RuntimeError', site=fixture['site'],
                           attribution='unreviewed-observation'))
            report['fixtures'] = [fixture]
            report['skipped' if outcome == 'skipped' else 'errors'] = 1
            report['successful'] = outcome == 'skipped'
            self.write_report(report)
            raw_exit = '0' if report['successful'] else '1'
            result = self.run_cli('collect', '--raw-exit', raw_exit)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['cacheable'])
            self.assertNotEqual(self.run_cli('record').returncode, 0)

    def test_empty_shard_is_not_success_cache_and_scope_tampering_rejected(self):
        report = observation(self.identity)
        report.update(selected_test_ids=[], assignment=[[], ['demo.Case.test_one']],
                      tests=[], tests_run=0)
        report['input_identity'] = digest({key: report[key] for key in
                                         ('metadata', 'source_identity', 'selected_test_ids')})
        self.write_report(report)
        result = self.run_cli('collect', '--raw-exit', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['cacheable'])
        self.assertNotEqual(self.run_cli('record').returncode, 0)
        changed = observation(self.identity)
        changed.update(shard_count=1, assignment=[['demo.Case.test_one']])
        self.write_report(changed)
        self.assertNotEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)

    def test_report_digest_and_execution_identity_are_required(self):
        for mutate in [lambda r: r.update(input_identity='0'*64),
                       lambda r: r['source_identity'].update(execution_identity={}),
                       lambda r: r.update(source_identity={})]:
            changed = observation(self.identity)
            mutate(changed)
            self.write_report(changed)
            self.assertNotEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)
            self.assertNotEqual(self.run_cli('record').returncode, 0)

    def test_changes_during_execution_and_old_schema_fail_closed(self):
        self.assertEqual(self.run_cli('record').returncode, 0)
        (self.root / 'input.txt').write_text('changed actual input\n')
        self.assertNotEqual(self.run_cli('collect', '--raw-exit', '0').returncode, 0)
        self.assertNotEqual(self.run_cli('record').returncode, 0)
        self.assertNotEqual(self.run_cli('verify').returncode, 0)
        (self.root / 'input.txt').write_text('actual fixture input\n')
        old = observation(self.identity)
        old['schema_version'] = 2
        self.write_report(old)
        self.assertNotEqual(self.run_cli('record').returncode, 0)
        self.assertNotEqual(self.run_cli('verify').returncode, 0)

    def test_collect_rejects_missing_raw_exit_and_incomplete_report(self):
        self.assertNotEqual(self.run_cli('collect').returncode, 0)
        for field in ('complete', 'collection_complete'):
            bad = observation(self.identity)
            bad[field] = False
            self.write_report(bad)
            self.assertNotEqual(self.run_cli('collect', '--raw-exit', '1').returncode, 0)

    def test_real_collector_binds_pre_execution_identity_to_cache_receipt(self):
        fixture = self.root / 'test_real.py'
        fixture.write_text('import unittest\nclass Real(unittest.TestCase):\n def test_pass(self): pass\n')
        git_fixture.run(['-C', str(self.root), 'add', 'test_real.py'], scratch=self.root,
                        check=True, capture_output=True)
        result = self.run_cli('identity')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.identity = json.loads(self.identity_path.read_text())
        result = subprocess.run([sys.executable, '-B', str(EVIDENCE.with_name('run_regression.py')),
                                 '--start-directory', str(self.root), '--report', str(self.report_path),
                                 '--input-identity', str(self.identity_path)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        # The actual unsharded report must agree with the shard identity too.
        rejected = self.run_cli('collect', '--raw-exit', '0')
        self.assertNotEqual(rejected.returncode, 0)
        def single(operation, *extra):
            return subprocess.run([sys.executable, '-B', str(EVIDENCE), operation,
                                   '--repo', str(self.root), '--identity', str(self.identity_path),
                                   '--report', str(self.report_path), '--receipt', str(self.receipt_path),
                                   '--shard', '0-of-1', *extra], env=self.env,
                                  capture_output=True, text=True)
        self.assertEqual(single('identity').returncode, 0)
        result = subprocess.run([sys.executable, '-B', str(EVIDENCE.with_name('run_regression.py')),
                                 '--start-directory', str(self.root), '--report', str(self.report_path),
                                 '--input-identity', str(self.identity_path)],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = single('collect', '--raw-exit', '0')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['cacheable'])
        self.assertEqual(single('record').returncode, 0)
        self.assertEqual(single('verify').returncode, 0)

    def test_module_supports_import_without_scripts_on_sys_path(self):
        spec = importlib.util.spec_from_file_location('isolated_evidence', EVIDENCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        identity = module.fingerprint(self.root, {'tools': 'fixture'})
        self.assertEqual(identity['report_schema_version'], 3)


if __name__ == '__main__':
    unittest.main()

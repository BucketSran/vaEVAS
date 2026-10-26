"""Report integrity and trusted-baseline behavior, without simulator execution."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import git_fixture

GATE = Path(__file__).resolve().parents[1] / 'regression_gate.py'


def load_gate():
    spec = importlib.util.spec_from_file_location('regression_gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report(outcome='failed'):
    def condition(identity, status):
        row = dict(id=identity, phase='test', site={'module': 'test_demo', 'line': 10,
                   'source_sha256': 'a' * 64}, identity_complete=True, outcome=status)
        if status != 'passed':
            row['reason'] = dict(kind='assertion', exception_type='builtins.AssertionError',
                                 message='A differs', site=row['site'],
                                 attribution='unreviewed-observation')
        return row
    return dict(schema_version=3, complete=True, collection_complete=True,
                successful=outcome not in ('failed', 'error', 'unexpected_success'),
                tests_run=1, failures=int(outcome == 'failed'), errors=int(outcome == 'error'),
                skipped=int(outcome == 'skipped'), expected_failures=int(outcome == 'expected_failure'),
                unexpected_successes=int(outcome == 'unexpected_success'),
                tests=[dict(id='demo.Case.test_one', outcome=outcome, seconds=0.1,
                            conditions=[condition('A', outcome), condition('P', 'passed')])],
                fixtures=[], setup_skipped_test_ids=[], discovered_test_ids=['demo.Case.test_one'],
                selected_test_ids=['demo.Case.test_one'], assignment=[['demo.Case.test_one']],
                shard_count=1, shard_index=0,
                metadata=dict(criteria_id='1' * 64, language_profile='2' * 64,
                              collector_sha256='3' * 64, runtime_profile={'backend': 'debug'},
                              invocation={'pattern': 'test_*.py'}))


REVIEW = dict(status='approved', reviewer='independent-reviewer', reference='review:123',
              semantic_status='pending')


class GateTests(unittest.TestCase):
    def setUp(self):
        self.gate = load_gate()
        self.old = report()
        self.baseline = self.gate.propose_baseline(self.old, {'commit': 'a' * 40}, REVIEW)

    def test_complete_known_failure_retains_raw_result(self):
        self.assertTrue(self.gate.validate_report(self.old)['valid'])
        result = self.gate.compare_report(self.old, self.baseline)
        self.assertFalse(result['raw_successful'])
        self.assertTrue(result['merge_allowed'], result)
        self.assertFalse(self.gate.cacheable_report(self.old))

    def test_baseline_keeps_complete_signatures_without_bulk_raw_payload(self):
        observed=copy.deepcopy(self.old)
        observed['tests'][0]['conditions'][0]['reason']['traceback']='large raw traceback'*1000
        observed['source_identity']={'criteria_files':[['fixture.py','a'*64]]*1000}
        before=copy.deepcopy(observed)
        baseline=self.gate.propose_baseline(observed, {'commit':'b'*40,'raw_report':'retained-fixture'}, REVIEW)
        entry=baseline['contexts'][0]
        self.assertEqual(entry['observation_format'],'regression-observations-v1')
        self.assertEqual(observed,before)
        self.assertNotIn('source_identity',entry['observations'])
        self.assertNotIn('traceback',entry['observations']['tests'][0]['conditions'][0]['reason'])
        self.assertEqual(entry['observations']['tests'][0]['conditions'][0]['reason']['message'],
                         observed['tests'][0]['conditions'][0]['reason']['message'])
        encoded=json.dumps(observed,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        self.assertEqual(entry['canonical_report_sha256'],hashlib.sha256(encoded).hexdigest())
        self.assertTrue(self.gate.compare_report(observed,baseline)['merge_allowed'])
        self.assertLess(len(json.dumps(baseline)),len(json.dumps(observed))//4)
        changed=copy.deepcopy(observed)
        changed['tests'][0]['conditions'][0]['reason']['message']='changed failure condition'
        self.assertFalse(self.gate.compare_report(changed,baseline)['merge_allowed'])

    def test_structured_assertion_identity_preserves_operands_and_raw_diagnostic(self):
        observed = copy.deepcopy(self.old)
        reason = observed['tests'][0]['conditions'][0]['reason']
        reason['comparison_identity'] = dict(
            schema_version=1, kind='unittest-assertion', operation='assertGreaterEqual',
            operation_source_sha256='4' * 64,
            operands={'a': {'type': 'int', 'hex': '0x1'},
                      'b': {'type': 'int', 'hex': '0x2'}},
            message={'type': 'none'}, policies=[
                {'id': 'native-site', 'version': 1, 'source_sha256': 'a' * 64}])
        reason['message'] = '1 not greater than or equal to <Fraction at 0x111>'
        baseline = self.gate.propose_baseline(observed, {'commit': 'a' * 40}, REVIEW)
        changed = copy.deepcopy(observed)
        changed['tests'][0]['conditions'][0]['reason']['message'] = (
            '1 not greater than or equal to <Fraction at 0x222>')
        result = self.gate.compare_report(changed, baseline)
        self.assertTrue(result['merge_allowed'], result)
        self.assertEqual(baseline['contexts'][0]['observations']['tests'][0]
                         ['conditions'][0]['reason']['message'], reason['message'])
        for field, value in [('operands', {'a': {'type': 'int', 'hex': '0x1'},
                                          'b': {'type': 'int', 'hex': '0x3'}}),
                             ('operation', 'assertEqual'),
                             ('message', {'type': 'str', 'value': 'semantic diagnostic'})]:
            variant = copy.deepcopy(changed)
            variant['tests'][0]['conditions'][0]['reason']['comparison_identity'][field] = value
            self.assertFalse(self.gate.compare_report(variant, baseline)['merge_allowed'])
        for field, value in [('schema_version', 99), ('operation_source_sha256', 'missing')]:
            variant = copy.deepcopy(changed)
            variant['tests'][0]['conditions'][0]['reason']['comparison_identity'][field] = value
            self.assertFalse(self.gate.validate_report(variant)['valid'])
        for operand in ({'type': 'opaque', 'name': 'unknown'},
                        {'type': 'int', 'hex': '0x2', 'complete': False},
                        {'type': 'future-encoding', 'value': 2}):
            variant = copy.deepcopy(changed)
            variant['tests'][0]['conditions'][0]['reason']['comparison_identity']['operands']['b'] = operand
            self.assertFalse(self.gate.validate_report(variant)['valid'])
        incomplete = copy.deepcopy(changed)
        incomplete['tests'][0]['conditions'][0]['reason']['comparison_complete'] = False
        self.assertFalse(self.gate.compare_report(incomplete, baseline)['merge_allowed'])

    def test_repeated_large_context_is_losslessly_pooled_and_tampering_blocks(self):
        observed=copy.deepcopy(self.old)
        context=[dict(function='case',line=12,values={'grid':list(range(1000)),'case':'A'})]
        for condition in observed['tests'][0]['conditions']:
            condition['context']=copy.deepcopy(context)
            if 'reason' in condition: condition['reason']['context']=copy.deepcopy(context)
        baseline=self.gate.propose_baseline(observed,{'commit':'b'*40},REVIEW)
        entry=baseline['contexts'][0]
        self.assertEqual(len(entry['value_pool']),1)
        self.assertTrue(self.gate.compare_report(observed,baseline)['merge_allowed'])
        self.assertLess(len(json.dumps(baseline)),len(json.dumps(observed)))
        changed=copy.deepcopy(observed)
        changed['tests'][0]['conditions'][0]['context'][0]['values']['grid'][0]=999
        self.assertFalse(self.gate.compare_report(changed,baseline)['merge_allowed'])
        broken=copy.deepcopy(baseline)
        next(iter(broken['contexts'][0]['value_pool'].values())).append(1001)
        self.assertFalse(self.gate.compare_report(observed,broken)['merge_allowed'])
        missing=copy.deepcopy(baseline)
        missing['contexts'][0]['value_pool'].clear()
        self.assertFalse(self.gate.compare_report(observed,missing)['merge_allowed'])

    def test_unknown_reason_structure_is_invalid_instead_of_crashing_comparison(self):
        broken=report('passed')
        broken['tests'][0]['conditions'][0]['reason']=None
        self.assertFalse(self.gate.validate_report(broken)['valid'])
        self.assertFalse(self.gate.compare_report(broken,self.baseline)['merge_allowed'])

    def test_compact_merged_observations_keep_complete_part_coverage(self):
        merged=copy.deepcopy(self.old)
        merged.update(merged=True,shard_index=None,shard_count=2,
                      assignment=[merged['discovered_test_ids'],[]],
                      parts=[dict(shard_index=0,complete=True,collection_complete=True,
                                  selected_test_ids=merged['discovered_test_ids'],
                                  source_identity={'bulk':'retained outside baseline'}),
                             dict(shard_index=1,complete=True,collection_complete=True,selected_test_ids=[])])
        baseline=self.gate.propose_baseline(merged,{'commit':'b'*40},REVIEW)
        self.assertTrue(self.gate.compare_report(merged,baseline)['merge_allowed'])
        projected=baseline['contexts'][0]['observations']
        self.assertTrue(self.gate.validate_report(projected)['valid'])
        self.assertEqual(projected['assignment'],merged['assignment'])
        self.assertEqual(projected['parts'][0]['selected_test_ids'],merged['selected_test_ids'])
        broken=copy.deepcopy(baseline)
        broken['contexts'][0]['observations']['parts'].pop()
        self.assertFalse(self.gate.compare_report(merged,broken)['merge_allowed'])

    def test_unknown_or_missing_observation_projection_format_is_not_trusted(self):
        for value in (None,'future-unreviewed-format'):
            baseline=copy.deepcopy(self.baseline)
            baseline['contexts'][0]['observation_format']=value
            self.assertFalse(self.gate.compare_report(self.old,baseline)['merge_allowed'])

    def test_replaced_condition_reason_and_phase_are_new_failures(self):
        for field, value in [('id', 'B'), ('phase', 'teardown')]:
            changed = copy.deepcopy(self.old)
            changed['tests'][0]['conditions'][0][field] = value
            self.assertFalse(self.gate.compare_report(changed, self.baseline)['merge_allowed'])
        for field, value in [('message', 'B differs'), ('exception_type', 'builtins.ValueError'),
                             ('site', {'module': 'other', 'line': 20})]:
            changed = copy.deepcopy(self.old)
            changed['tests'][0]['conditions'][0]['reason'][field] = value
            self.assertFalse(self.gate.compare_report(changed, self.baseline)['merge_allowed'])

    def test_missing_passed_condition_is_unknown(self):
        changed = copy.deepcopy(self.old)
        changed['tests'][0]['conditions'].pop()
        self.assertFalse(self.gate.compare_report(changed, self.baseline)['merge_allowed'])

    def test_missing_context_review_or_identity_fails_closed(self):
        for baseline in [None, {'schema_version': 1, 'contexts': []}]:
            self.assertFalse(self.gate.compare_report(self.old, baseline)['merge_allowed'])
        unreviewed = copy.deepcopy(self.baseline)
        unreviewed['contexts'][0]['review']['status'] = 'pending'
        self.assertFalse(self.gate.compare_report(self.old, unreviewed)['merge_allowed'])
        unknown = copy.deepcopy(self.old)
        unknown['tests'][0]['conditions'][0]['identity_complete'] = False
        baseline = self.gate.propose_baseline(unknown, {'commit': 'b' * 40}, REVIEW)
        self.assertFalse(self.gate.compare_report(unknown, baseline)['merge_allowed'])

    def test_incomplete_reason_context_cannot_be_waived_by_complete_outer_label(self):
        observed = copy.deepcopy(self.old)
        observed['tests'][0]['conditions'][0]['reason']['context_complete'] = False
        baseline = self.gate.propose_baseline(observed, {'commit': 'b' * 40}, REVIEW)
        self.assertTrue(self.gate.validate_report(observed)['valid'])
        self.assertFalse(self.gate.compare_report(observed, baseline)['merge_allowed'])

    def test_cache_accepts_only_complete_actual_passes(self):
        self.assertTrue(self.gate.cacheable_report(report('passed')))
        for status in ['failed', 'error', 'skipped', 'expected_failure', 'unexpected_success']:
            self.assertFalse(self.gate.cacheable_report(report(status)))
        for status in ['skipped', 'expected_failure']:
            self.assertFalse(self.gate.compare_report(report(status), self.baseline)['merge_allowed'])

    def test_integrity_rejects_incomplete_empty_duplicate_collection_and_unknown(self):
        mutations = [lambda r: r.update(complete=False),
                     lambda r: r.update(collection_complete=False),
                     lambda r: r.update(schema_version=99),
                     lambda r: r.update(tests_run=0, tests=[]),
                     lambda r: r['tests'].append(copy.deepcopy(r['tests'][0])),
                     lambda r: r['tests'][0].update(outcome='interrupted'),
                     lambda r: r.update(shard_count=2),
                     lambda r: r.update(successful=True),
                     lambda r: r['tests'][0].update(conditions=[])]
        for mutate in mutations:
            changed = copy.deepcopy(self.old)
            mutate(changed)
            self.assertFalse(self.gate.validate_report(changed)['valid'], changed)
            self.assertFalse(self.gate.compare_report(changed, self.baseline)['merge_allowed'])

    def test_profiles_match_criteria_not_dut_identity(self):
        changed = copy.deepcopy(self.old)
        changed['input_identity'] = {'dut_sha256': 'f' * 64}
        self.assertTrue(self.gate.compare_report(changed, self.baseline)['merge_allowed'])
        for key in ['criteria_id', 'language_profile', 'collector_sha256']:
            changed = copy.deepcopy(self.old)
            changed['metadata'][key] = 'f' * 64
            self.assertFalse(self.gate.compare_report(changed, self.baseline)['merge_allowed'])
        multiple = copy.deepcopy(self.baseline)
        second = report('passed')
        second['metadata']['runtime_profile'] = {'backend': 'release'}
        multiple['contexts'].extend(self.gate.propose_baseline(second, {'commit': 'b' * 40}, REVIEW)['contexts'])
        self.assertTrue(self.gate.compare_report(second, multiple)['merge_allowed'])
        multiple['contexts'].append(copy.deepcopy(multiple['contexts'][0]))
        self.assertFalse(self.gate.compare_report(self.old, multiple)['merge_allowed'])

    def test_pending_proposal_does_not_grant_merge(self):
        proposal = self.gate.propose_baseline(self.old, {'commit': 'a' * 40})
        self.assertEqual(proposal['contexts'][0]['review']['status'], 'pending')
        self.assertFalse(self.gate.compare_report(self.old, proposal)['merge_allowed'])

    def test_nonempty_passed_shard_can_cache_without_granting_full_merge(self):
        shard = report('passed')
        shard.update(discovered_test_ids=['demo.Case.test_one', 'demo.Other.test_two'],
                     assignment=[['demo.Case.test_one'], ['demo.Other.test_two']],
                     shard_count=2)
        self.assertTrue(self.gate.validate_report(shard)['valid'])
        self.assertTrue(self.gate.cacheable_report(shard))
        self.assertFalse(self.gate.compare_report(shard, self.baseline)['merge_allowed'])
        with self.assertRaises(ValueError):
            self.gate.propose_baseline(shard, {'commit': 'a' * 40}, REVIEW)
        shard.update(shard_index=1, selected_test_ids=[], tests=[], tests_run=0,
                     assignment=[['demo.Case.test_one', 'demo.Other.test_two'], []])
        self.assertTrue(self.gate.validate_report(shard)['valid'])
        self.assertFalse(self.gate.cacheable_report(shard))

    def test_merged_parts_missing_or_duplicated_block(self):
        merged = report('passed')
        merged.update(merged=True, shard_index=None, shard_count=2,
                      assignment=[['demo.Case.test_one'], []],
                      parts=[dict(shard_index=0, complete=True, collection_complete=True,
                                  selected_test_ids=['demo.Case.test_one']),
                             dict(shard_index=1, complete=True, collection_complete=True,
                                  selected_test_ids=[])])
        self.assertTrue(self.gate.validate_report(merged)['valid'])
        for mutation in [lambda r: r['parts'].pop(),
                         lambda r: r['parts'][1].update(shard_index=0),
                         lambda r: r['parts'][1].update(complete=False),
                         lambda r: r['parts'][1].update(selected_test_ids=['demo.Case.test_one'])]:
            changed = copy.deepcopy(merged)
            mutation(changed)
            self.assertFalse(self.gate.validate_report(changed)['valid'])

    def test_malformed_structures_return_invalid_without_crashing(self):
        for field, value in [('tests', [None]), ('metadata', []), ('fixtures', [None]),
                             ('assignment', {}), ('tests', {}), ('successful', 1)]:
            malformed = copy.deepcopy(self.old)
            malformed[field] = value
            self.assertFalse(self.gate.validate_report(malformed)['valid'])

    def test_incomplete_source_identity_cannot_exempt_failure(self):
        unknown = copy.deepcopy(self.old)
        for c in unknown['tests'][0]['conditions']:
            c.pop('site', None)
            if 'reason' in c:
                c['reason'].pop('site', None)
        proposed = self.gate.propose_baseline(unknown, {'commit': 'a' * 40}, REVIEW)
        self.assertFalse(self.gate.compare_report(unknown, proposed)['merge_allowed'])

    def test_cli_validate_and_pending_proposal_are_reviewable_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'report.json'
            source = root / 'source.json'
            path.write_text(json.dumps(self.old))
            source.write_text(json.dumps({'commit': 'b' * 40}))
            validation = subprocess.run([sys.executable, '-B', str(GATE), 'validate', str(path)],
                                        capture_output=True, text=True)
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertTrue(json.loads(validation.stdout)['valid'])
            proposal = subprocess.run([sys.executable, '-B', str(GATE), 'propose', str(path),
                                       '--source-identity', str(source)], capture_output=True, text=True)
            self.assertEqual(proposal.returncode, 0, proposal.stderr)
            baseline = json.loads(proposal.stdout)
            self.assertFalse(self.gate.compare_report(self.old, baseline)['merge_allowed'])

    def test_fixture_errors_block_even_reviewed_observations(self):
        bad = copy.deepcopy(self.old)
        fixture = copy.deepcopy(bad['tests'][0]['conditions'][0])
        fixture.update(scope='tearDownModule (demo)', phase='teardown_module', outcome='error')
        bad['fixtures'] = [fixture]
        bad['errors'] = 1
        baseline = self.gate.propose_baseline(bad, {'commit': 'a' * 40}, REVIEW)
        self.assertFalse(self.gate.compare_report(bad, baseline)['merge_allowed'])

    def test_cli_reads_trusted_commit_and_inactive_cannot_allow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                return git_fixture.run(['-C', str(root), *args], scratch=root, check=True,
                                       capture_output=True, text=True).stdout.strip()
            with git_fixture.isolate():
                git('init')
                path = root / 'evas/validation/baselines/regression-v1.json'
                path.parent.mkdir(parents=True)
                path.write_text(json.dumps(self.baseline))
                git('add', '.')
                git('-c', 'user.name=Gate Test', '-c', 'user.email=gate@example.invalid', 'commit', '-m', 'trusted')
                trusted = git('rev-parse', 'HEAD')
                path.write_text(json.dumps({'schema_version': 1, 'contexts': []}))
                self.assertEqual(self.gate.load_trusted_baseline(root, trusted), self.baseline)
                candidate = root / 'report.json'
                candidate.write_text(json.dumps(self.old))
                command = [sys.executable, '-B', str(GATE), 'compare', str(candidate),
                           '--repo', str(root), '--trusted-base', trusted]
                result = subprocess.run(command, env=git_fixture.child_env(), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)['merge_allowed'])
                inactive = subprocess.run(command + ['--inactive'], env=git_fixture.child_env(),
                                          capture_output=True, text=True)
                self.assertIsNone(json.loads(inactive.stdout)['merge_allowed'])
                for ref in ['HEAD', trusted[:12], '0' * 40]:
                    denied = subprocess.run(command[:-1] + [ref], env=git_fixture.child_env(),
                                            capture_output=True, text=True)
                    self.assertNotEqual(denied.returncode, 0)
                denied = subprocess.run(command + ['--baseline', str(path)], env=git_fixture.child_env(),
                                        capture_output=True, text=True)
                self.assertNotEqual(denied.returncode, 0)


if __name__ == '__main__':
    unittest.main()

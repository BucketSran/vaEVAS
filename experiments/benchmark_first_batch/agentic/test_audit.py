"""Local sealed-schema fixtures and optional actual Trial archive regression."""
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
import audit


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def info(data):
    return {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def fixture(directory, kind='pass', corrupt=None):
    """Construct sealed evidence schemas; never run a checker or simulator."""
    source = b'module dut; integer f; analog f=$fopen("/work/output/result.csv","w"); endmodule\n'
    source_info = info(source)
    candidate_core = {'task_id': 'fixture', 'task_version': 'v1', 'files': {'dut.va': source_info}}
    candidate = {**candidate_core, 'schema_version': 1,
                 'candidate_sha256': info(encoded(candidate_core))['sha256']}
    cases = [{'name': name, 'netlist': name + ' netlist', 'signals':['out'], 'stop':1.0} for name in ['one', 'two']]
    tests = {'tests/cases.json': encoded(cases),
             'tests/contract.json': encoded({'candidate_files': ['dut.va'], 'output_files': ['result.csv']}),
             'tests/verify.py': b'# fixture checker', 'tests/circuit_task.py': b'# fixture runtime',
             'tests/adc_linearity.py': b'# fixture parser'}
    manifest = {'schema_version': 1, 'task_id': 'fixture', 'task_version': 'v1',
                'condition_id': 'all', 'criteria_sha256': 'fixture-criteria',
                'candidate_file': 'dut.va', 'files': {k: info(v) for k, v in tests.items()}}
    package_files = {**tests, 'manifest.json': encoded(manifest)}
    package_inventory = {k: info(v) for k, v in package_files.items()}
    package_sha = info(encoded(package_inventory))['sha256']
    members = {**{'task-package/' + k: v for k, v in package_files.items()},
               **{'run/work/' + k: v for k, v in package_files.items()},
               'candidate/manifest.json': encoded(candidate), 'candidate/files/dut.va': source,
               'run/work/candidate/dut.va': source}
    report = {'candidate_sha256': source_info['sha256'], 'cases': [], 'status': 'completed', 'reward': 1}
    for key, filename in {'cases_sha256': 'cases.json', 'contract_sha256': 'contract.json',
                          'checker_sha256': 'verify.py', 'runtime_sha256': 'circuit_task.py',
                          'parser_sha256': 'adc_linearity.py'}.items():
        report[key] = info(tests['tests/' + filename])['sha256']
    if kind == 'source_rejection':
        report.update(status='submission_contract_violation', reward=0, reason='macro prohibited')
    else:
        report['candidate_files'] = {'dut.va': source_info['sha256']}
        for case in cases:
            prefix = 'run/work/verifier/' + case['name'] + '/'
            literal = b'"/work/output/result.csv"'
            start = source.index(literal)
            replacement = encoded('/remote/verifier/' + case['name'] + '/output/result.csv')
            executed = source[:start] + replacement + source[start + len(literal):]
            members.update({prefix + 'original/dut.va': source, prefix + 'dut.va': executed,
                            prefix + 'tb.scs': case['netlist'].encode()})
            record = {'name': case['name'], 'status': 'graded', 'passed': True, 'returncode':0,
                      'netlist_sha256': info(members[prefix + 'tb.scs'])['sha256'],
                      'candidate_files': {'dut.va': {'original_sha256': source_info['sha256'],
                          'executed_sha256': info(executed)['sha256'], 'output_translation': {
                              'version': 'circuit-output-paths-v1', 'inverse_verified': True,
                              'edits': [{'start': start, 'end': start + len(literal),
                                         'original_literal': literal.decode(),
                                         'executed_literal': replacement.decode()}]}}}}
            if kind != 'compile_failure':
                raw=b'VALUE\n"time" 0\n"out" 0\n"time" 1\n"out" 1\nEND\n'
                if kind == 'truncated_waveform':raw=raw.removesuffix(b'END\n')
                members[prefix+'psf/tran.tran.tran']=raw
                record.update(waveform_sha256=info(raw)['sha256'],waveform_rows=2)
            if kind == 'compile_failure':
                record.update(status='submission_failure', passed=False,
                              failure_kind='compile_or_simulation_failure')
            report['cases'].append(record)
        if kind == 'compile_failure':
            report.update(status='submission_contract_violation', reward=0, reason='candidate not executable')
        if kind == 'missing_waveform':
            report['cases'][0].pop('waveform_sha256')
            report['cases'][0].pop('waveform_rows')
            members.pop('run/work/verifier/one/psf/tran.tran.tran')
        if kind == 'bad_row_count':report['cases'][0]['waveform_rows']=3
        if kind == 'nonzero_returncode':report['cases'][0]['returncode']=1
        if kind == 'partial_pass':
            report['cases'].pop()
    members['run/work/verifier/report.json'] = encoded(report)
    identity = {'backend': 'benchmark_spectre', 'purpose': 'final', 'candidate_manifest': candidate,
                'candidate': {k[len('candidate/'):]: info(v) for k, v in members.items() if k.startswith('candidate/')},
                'package': {'manifest': manifest, 'files': package_inventory, 'sha256': package_sha}}
    members['run/identity.json'] = encoded(identity)
    result = {'execution': 'ok', 'verdict': 'pass' if report['reward'] else 'fail',
              'score': report['reward'], 'benchmark_status': report['status'],
              'task_id': 'fixture', 'task_version': 'v1', 'condition_id': 'all',
              'criteria_sha256': 'fixture-criteria', 'candidate_sha256': candidate['candidate_sha256'],
              'task_package_sha256': package_sha,
              'artifacts': {k[len('run/'):]: info(v) for k, v in members.items() if k.startswith('run/')}}
    # Corruption is resealed at the transport layer; semantic identities must still catch it.
    if corrupt == 'executed':
        members['run/work/verifier/one/dut.va'] += b'// changed'
        result['artifacts']['work/verifier/one/dut.va'] = info(members['run/work/verifier/one/dut.va'])
    elif corrupt == 'working':
        members['run/work/candidate/dut.va'] += b'// changed'
        result['artifacts']['work/candidate/dut.va'] = info(members['run/work/candidate/dut.va'])
    elif corrupt == 'result_artifact':
        result['artifacts']['work/verifier/report.json']['sha256'] = '0' * 64
    elif corrupt == 'inverse':
        report['cases'][0]['candidate_files']['dut.va']['output_translation']['edits'][0]['original_literal'] = '"different"'
        members['run/work/verifier/report.json'] = encoded(report)
        result['artifacts']['work/verifier/report.json'] = info(members['run/work/verifier/report.json'])
    members['run/result.json'] = encoded(result)
    request = {'job_id': 'fixture-job', 'identity': identity}
    members['request.json'] = encoded(request)
    completion = {'result': result, 'artifacts': {}}
    members['completion.json'] = encoded(completion)
    archive = directory / 'job.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for name, data in members.items():
            entry = tarfile.TarInfo(name); entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
    receipt = {'package': info(archive.read_bytes()), 'members': {k: info(v) for k, v in members.items()},
               'completion': completion, 'request': request}
    receipt_path = directory / 'receipt.json'
    receipt_path.write_bytes(encoded(receipt))
    return receipt_path, [{'state': 'completed', **result}], {'final_task_package_sha256': package_sha}


class AuditTests(unittest.TestCase):
    def run_fixture(self, kind='pass', corrupt=None):
        with tempfile.TemporaryDirectory() as temp:
            return audit.audit_archive(*fixture(Path(temp), kind, corrupt))

    def test_complete_pass_and_output_relocation(self):
        result = self.run_fixture()
        self.assertTrue(result['complete_pass'])
        self.assertTrue(result['actual_candidate_and_case_bytes_verified'])

    def test_source_rejection_without_cases_or_candidate_files(self):
        result = self.run_fixture('source_rejection')
        self.assertEqual(result['score'], 0)
        self.assertFalse(result['complete_pass'])
        self.assertFalse(result['all_cases_present'])

    def test_compile_failure_is_valid_zero(self):
        result = self.run_fixture('compile_failure')
        self.assertEqual(result['score'], 0)
        self.assertTrue(result['all_cases_present'])
        self.assertFalse(result['complete_pass'])

    def test_partial_success_cannot_be_complete_pass(self):
        with self.assertRaisesRegex(ValueError, 'missing cases'):
            self.run_fixture('partial_pass')

    def test_complete_pass_requires_actual_complete_waveform(self):
        for kind in ['missing_waveform','bad_row_count','nonzero_returncode','truncated_waveform']:
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.run_fixture(kind)

    def test_unbound_verifier_result_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'attempt';trial=root/'jobs/attempt/trial';trial.mkdir(parents=True)
            (trial/'result.json').write_bytes(encoded({'id':'fixture','verifier_result':{'rewards':{'reward':1}}}))
            (root/'identity.json').write_bytes(encoded({'final_task_package_sha256':'unused'}))
            with self.assertRaisesRegex(ValueError,'sealed final evaluation'):
                audit.summarize(root)

    def test_configured_pi_model_and_response_model_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'attempt'
            trial = root / 'jobs/attempt/trial'
            sessions = trial / 'agent/pi/sessions'
            sessions.mkdir(parents=True)
            (trial / 'result.json').write_bytes(encoded({'id': 'fixture'}))
            (root / 'identity.json').write_bytes(encoded({'final_task_package_sha256': 'unused'}))
            messages = [
                {'role': 'assistant', 'provider': 'endpoint', 'model': 'requested',
                 'responseId': 'response-1'},
                {'role': 'assistant', 'provider': 'endpoint', 'model': 'requested',
                 'responseId': 'response-2', 'responseModel': 'server-other'}]
            (sessions / 'fixture.jsonl').write_text(''.join(
                json.dumps({'message': message}) + '\n' for message in messages))
            result = audit.summarize(root)
            self.assertEqual(result['pi_recorded_models'], [
                {'provider': 'endpoint', 'model': 'requested', 'assistant_messages': 2}])
            self.assertEqual(result['pi_response_models'], [
                {'model': 'server-other', 'assistant_messages': 1}])
            self.assertEqual(result['pi_response_id_message_count'], 2)
            self.assertIn('equal and omitted', result['model_identity_limit'])

    def test_resealed_hash_and_identity_corruption(self):
        for corruption in ['executed', 'working', 'result_artifact', 'inverse']:
            with self.subTest(corruption=corruption), self.assertRaises(ValueError):
                self.run_fixture(corrupt=corruption)

    def test_actual_pass_and_missing_candidate(self):
        value = os.environ.get('AGENTIC_ACTUAL_EVIDENCE')
        if not value:
            self.skipTest('set AGENTIC_ACTUAL_EVIDENCE to retained actual Trial root')
        root = Path(value)
        passed = audit.summarize(root / 'comparator-trial-v4')
        self.assertTrue(passed['archives'][0]['complete_pass'])
        self.assertEqual(len(passed['archives'][0]['cases']), 2)
        self.assertEqual(passed['pi_response_models'], [])
        self.assertGreater(passed['pi_response_id_message_count'], 0)
        failed = audit.summarize(root / 'comparator-flash-v1')
        self.assertIsNotNone(failed['exception'])
        self.assertIsNone(failed['verifier_result'])
        self.assertEqual(failed['archives'], [])
        infrastructure = root / 'comparator-flash-budget-v3'
        if infrastructure.exists():
            unavailable = audit.summarize(infrastructure)
            self.assertIsNone(unavailable['verifier_result'])
            self.assertFalse(unavailable['archives'][0]['complete_pass'])
            self.assertEqual(unavailable['archives'][0]['execution'], 'dependency_unavailable')
            self.assertTrue(unavailable['archives'][0]['seal_and_result_artifacts_verified'])


if __name__ == '__main__':
    unittest.main()

"""Local optimization-audit checks; optional actual sealed reference replay."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import audit_optimization as audit


class OptimizationAuditTests(unittest.TestCase):
    def test_main_compile_failure_has_no_invented_performance_work(self):
        canonical = {name: audit.REPO / 'benchmark/checkers' / name for name in
                     ('adc_linearity.py', 'circuit_task.py', 'first_batch_optimization.py')}
        canonical.update({name: audit.REPO / 'benchmark/tasks/optimize-vco-step/tests' / name
                          for name in ('evaluate.py', 'performance.json', 'baseline.va')})
        contents = {'run/work/tests/' + name: path.read_bytes()
                    for name, path in canonical.items()}
        contents['candidate/files/dut.va'] = b'invalid candidate fixture'
        result = {'condition_id': 'main', 'task_package_sha256': 'package', 'execution': 'ok'}

        class Archive:
            members = set(contents)
            receipt = {'package': {'sha256': 'archive'}}
            def read(self, name):
                return contents[name]
            def json(self, name):
                return {'run/result.json': result,
                        'run/work/tests/cases.json': [{'name': 'main', 'performance': True}],
                        'run/work/verifier/report.json': {'cases': [
                            {'name': 'main', 'status': 'submission_failure', 'returncode': 2}]}}[name]
            def close(self):
                pass

        with tempfile.TemporaryDirectory() as directory:
            receipt = Path(directory) / 'receipt.json'
            receipt.write_text(json.dumps({'request': {'job_id': 'unit-fixture'}}))
            with patch.object(audit, 'SealedArchive', return_value=Archive()), \
                 patch.object(audit, 'verify_seal', return_value=(result,
                     {'task_id': 'optimize-vco-step'}, {'candidate_sha256': 'candidate'})), \
                 patch.object(audit, 'audit_paired') as paired:
                report = audit.audit_bound_archive(receipt, {
                    'task_id': 'optimize-vco-step', 'final_task_package_sha256': 'package'})
            self.assertEqual(report['paired_cases'], [{'condition': 'main',
                'stage': 'not_run_main_submission_or_compile_failure', 'attempts': []}])
            paired.assert_not_called()

    def test_missing_candidate_has_no_invented_paired_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'identity.json').write_text(json.dumps({'task_id': 'optimize-vco-step'}))
            with patch.object(audit, 'summarize', return_value={
                    'archives': [], 'exception': {'exception_type': 'AgentTimeoutError'}}):
                report = audit.audit_trial(folder)
            self.assertIsNone(report['candidate_final_score'])
            self.assertEqual(report['phase_exception_type'], 'AgentTimeoutError')
            self.assertEqual(report['performance_stage'], 'not_run_no_completed_final_archive')
            self.assertEqual(report['paired_cases'], [])
            self.assertEqual(report['new_model_or_solver_requests'], 0)

    @unittest.skipUnless(os.environ.get('AGENTIC_OPTIMIZATION_REFERENCE_RECEIPT'),
                         'requires explicit retained actual sealed reference receipt')
    def test_actual_reference_and_wrong_final_package_binding(self):
        path = Path(os.environ['AGENTIC_OPTIMIZATION_REFERENCE_RECEIPT'])
        receipt = json.loads(path.read_text())
        archive = audit.SealedArchive(path.with_name('job.tar.gz'), receipt)
        try:
            package_sha = archive.json('run/result.json')['task_package_sha256']
        finally:
            archive.close()
        identity = {'task_id': 'optimize-vco-step', 'final_task_package_sha256': package_sha}
        report = audit.audit_bound_archive(path, identity)
        self.assertEqual(report['performance_stage'], 'audited')
        self.assertEqual(report['final_package_sha256'], package_sha)
        self.assertEqual(len(report['paired_cases']), 1)
        paired = report['paired_cases'][0]
        self.assertEqual(paired['stage'], 'completed')
        self.assertEqual(len(paired['attempts']), 12)
        self.assertTrue(paired['lossless_waveform_and_statistics_replayed'])
        with self.assertRaisesRegex(ValueError, 'paired final package differs'):
            audit.audit_bound_archive(path, {**identity, 'final_task_package_sha256': '0' * 64})


if __name__ == '__main__':
    unittest.main()

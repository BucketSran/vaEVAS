"""Source publication fixtures; no credentials, model calls or backend calls."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import export_candidates as export


class ExportTests(unittest.TestCase):
    def fixture(self, root, files):
        folder = root / 'attempt'
        bundle = folder / 'jobs/attempt/trial/public-session/candidate'
        bundle.mkdir(parents=True)
        (bundle / 'manifest.json').write_text('{}')
        records = {}
        for name, data in files.items():
            path = bundle / 'files' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            records[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        identity = {'task_id': 'task', 'task_version': '1', 'model_requested': 'model',
                    'final_task_package_sha256': 'package'}
        (folder / 'identity.json').write_text(json.dumps(identity))
        (folder / 'final-evaluation.json').write_text(json.dumps({'task_package': str(root / 'package')}))
        manifest = {'task_id': 'task', 'task_version': '1', 'files': records,
                    'candidate_sha256': 'bundle', 'reason': 'cancelled'}
        audited = {'pi_recorded_models': [{'model': 'model'}], 'model_identity_limit': 'endpoint only',
                   'archives': [{'job_id': 'job', 'archive_sha256': 'archive',
                                 'candidate_bundle_sha256': 'bundle', 'candidate_files': records,
                                 'score': 0}], 'exception': {'exception_type': 'AgentTimeoutError'},
                   'episode_end': {'candidate_sha256': 'bundle'}}
        package = {'sha256': 'package', 'manifest': {'task_id': 'task', 'criteria_sha256': 'criteria'}}
        return folder, manifest, audited, package

    def test_complete_multifile_copy_preserves_bytes_and_original_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {'dut.va': b'original\r\n', 'blocks/tdc.va': b'child\x00\n'}
            folder, manifest, audited, package = self.fixture(root, files)
            with patch.object(export, 'summarize', return_value=audited), \
                 patch.object(export, 'harness_verifiers', return_value=(lambda path: manifest,
                     lambda path, purpose: package)):
                result = export.export(folder, root / 'published', b'known-test-credential')
            self.assertEqual(result['availability'], 'repository-contained')
            self.assertEqual(result['candidate_final_score'], 0)
            self.assertEqual(result['phase_exception_type'], 'AgentTimeoutError')
            for name, data in files.items():
                self.assertEqual((root / 'published/task/model' / name).read_bytes(), data)

    def test_sensitive_source_is_not_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {'dut.va': b'// known-test-credential'}
            folder, manifest, audited, package = self.fixture(root, files)
            with patch.object(export, 'summarize', return_value=audited), \
                 patch.object(export, 'harness_verifiers', return_value=(lambda path: manifest,
                     lambda path, purpose: package)):
                result = export.export(folder, root / 'published', b'known-test-credential')
            self.assertEqual(result['availability'], 'not_exported_credential_scan')
            self.assertFalse((root / 'published/task/model/dut.va').exists())
            self.assertTrue((root / 'published/task/model/manifest.json').exists())

    def test_generic_patterns_reject_without_exposing_match(self):
        scan = export.credential_scan(b'Authorization: Bearer abcdefghijklmnopqrstuvwxyz', b'unrelated-test-token')
        self.assertFalse(export.clean(scan))
        self.assertNotIn('abcdefghijklmnopqrstuvwxyz', json.dumps(scan))

    def test_missing_candidate_is_explicit_none(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, manifest, audited, package = self.fixture(root, {'dut.va': b'partial file'})
            (folder / 'jobs/attempt/trial/public-session/candidate/manifest.json').unlink()
            audited.update(archives=[], episode_end={'candidate_sha256': None})
            with patch.object(export, 'summarize', return_value=audited), \
                 patch.object(export, 'harness_verifiers', return_value=(lambda path: manifest,
                     lambda path, purpose: package)):
                result = export.export(folder, root / 'published', b'known-test-credential')
            self.assertEqual(result['availability'], 'none_no_frozen_candidate')
            self.assertEqual(result['candidate_files'], {})
            self.assertFalse((root / 'published/task/model/dut.va').exists())

    def test_changed_source_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, manifest, audited, package = self.fixture(root, {'dut.va': b'original'})
            (folder / 'jobs/attempt/trial/public-session/candidate/files/dut.va').write_bytes(b'changed')
            with patch.object(export, 'summarize', return_value=audited), \
                 patch.object(export, 'harness_verifiers', return_value=(lambda path: manifest,
                     lambda path, purpose: package)), \
                 self.assertRaisesRegex(ValueError, 'source changed after bundle verification'):
                export.export(folder, root / 'published', b'known-test-credential')
            self.assertFalse((root / 'published/task/model').exists())

    def test_no_model_response_and_no_candidate_has_unknown_actual_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, manifest, audited, package = self.fixture(root, {})
            (folder / 'jobs/attempt/trial/public-session/candidate/manifest.json').unlink()
            audited.update(pi_recorded_models=[], archives=[], episode_end=None)
            with patch.object(export, 'summarize', return_value=audited), \
                 patch.object(export, 'harness_verifiers', return_value=(lambda path: manifest,
                     lambda path, purpose: package)):
                result = export.export(folder, root / 'published', b'known-test-credential')
            self.assertEqual(result['availability'], 'none_no_frozen_candidate')
            self.assertEqual(result['requested_model'], 'model')
            self.assertIsNone(result['served_model'])
            self.assertFalse(result['actual_model_observed'])

    def test_conflicting_observed_model_is_strictly_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            folder, manifest, audited, package = self.fixture(root, {})
            audited['pi_recorded_models'] = [{'model': 'different'}]
            with patch.object(export, 'summarize', return_value=audited), \
                 self.assertRaisesRegex(ValueError, 'actual served model identity'):
                export.export(folder, root / 'published', b'known-test-credential')
            self.assertFalse((root / 'published/task/model').exists())


if __name__ == '__main__':
    unittest.main()

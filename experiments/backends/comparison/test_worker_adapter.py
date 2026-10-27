"""Comparison worker dependency and legacy entry controls; no numerical backend."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import freeze
import ingest
import runner


class WorkerAdapterControls(unittest.TestCase):
    def test_legacy_worker_dispatches_original_root(self):
        with patch.object(runner.importlib.util, 'spec_from_file_location') as spec, patch.object(runner.importlib.util, 'module_from_spec') as module:
            runner.worker(Path('work'), Path('kernel'))
            module.return_value.worker.assert_called_once_with(Path('work'), Path('kernel'), runner.ROOT)
            self.assertEqual(spec.call_args.args[1], runner.ROOT / freeze.WORKER_ADAPTER)

    def test_contract_uses_audited_source_not_file_presence(self):
        self.assertEqual(freeze.worker_dependencies('def worker(): pass'), ())
        source = "_EVAS_WORKER_PATH = ROOT / " + repr(freeze.WORKER_ADAPTER)
        self.assertEqual(freeze.worker_dependencies(source), (freeze.WORKER_ADAPTER,))
        for invalid in [source.replace('ROOT /', 'OTHER /'), source+'\n'+source,
                        "path = " + repr(freeze.WORKER_ADAPTER)]:
            with self.subTest(source=invalid), self.assertRaises(ValueError):
                freeze.worker_dependencies(invalid)

    def test_runtime_identity_binds_adapter_and_rejects_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            runner_path = root / 'experiments/backends/comparison/runner.py'
            runner_path.parent.mkdir(parents=True)
            runner_path.write_text('def worker(): pass')
            with patch.object(freeze, 'ROOT', root):
                old = freeze.runtime_identity()
                adapter = root / freeze.WORKER_ADAPTER
                adapter.parent.mkdir(parents=True);adapter.write_text('# control')
                self.assertEqual(old, freeze.runtime_identity())
                runner_path.write_text("_EVAS_WORKER_PATH = ROOT / " + repr(freeze.WORKER_ADAPTER))
                current = freeze.runtime_identity()
                self.assertNotEqual(old, current)
                adapter.write_text('# changed control')
                self.assertNotEqual(current, freeze.runtime_identity())
                adapter.unlink()
                with self.assertRaises(FileNotFoundError):freeze.runtime_identity()

    def test_archive_closure_old_new_and_missing_or_changed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'experiments/backends/comparison/evidence/sources'
            archive.mkdir(parents=True)
            def frozen(text):
                digest = hashlib.sha256(text.encode()).hexdigest()
                path = archive / ('control-' + digest + '.py.txt');path.write_text(text)
                return digest, path
            old, _ = frozen('def worker(): pass')
            new, _ = frozen("_EVAS_WORKER_PATH = ROOT / " + repr(freeze.WORKER_ADAPTER))
            adapter, path = frozen('# controlled adapter')
            with patch.object(ingest, 'ROOT', root):
                self.assertEqual(len(ingest.runner_sources([old])), 1)
                self.assertEqual(len(ingest.runner_sources([new], {freeze.WORKER_ADAPTER:adapter})), 2)
                with self.assertRaisesRegex(ValueError, 'closure mismatch'):ingest.runner_sources([new])
                with self.assertRaisesRegex(ValueError, 'closure mismatch'):ingest.runner_sources([old], {freeze.WORKER_ADAPTER:adapter})
                path.write_text('# changed')
                with self.assertRaisesRegex(ValueError, 'not retrievable'):ingest.runner_sources([new], {freeze.WORKER_ADAPTER:adapter})

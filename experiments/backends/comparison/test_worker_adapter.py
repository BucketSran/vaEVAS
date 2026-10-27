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


class ContinuationIngestControls(unittest.TestCase):
    """Synthetic execution artifacts exercise run -> results -> real ingest wiring.

    External execution and scientific analysis are forbidden/mocked. The oracle is
    source identity, immutable STARTED bytes and rejection of unbound provenance.
    """
    def exercise(self, mode='resume', fault=None):
        import json
        from argparse import Namespace
        from contextlib import ExitStack
        import derive
        from records import sha, load
        with tempfile.TemporaryDirectory() as temp, ExitStack() as stack:
            root = Path(temp)
            stack.enter_context(patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('external process forbidden')))
            stack.enter_context(patch.object(runner.subprocess, 'run', side_effect=AssertionError('external process forbidden')))
            stack.enter_context(patch.object(runner.subprocess, 'check_output', side_effect=AssertionError('external process forbidden')))
            inputs = root / 'inputs';inputs.mkdir()
            output = root / 'output'
            archive = root / 'experiments/backends/comparison/evidence/sources'
            archive.mkdir(parents=True)
            def write(path, value):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            def frozen(text):
                digest = hashlib.sha256(text.encode()).hexdigest()
                (archive / ('control-' + digest + '.py.txt')).write_text(text)
                return digest
            current_text = Path(runner.__file__).read_text()
            current = frozen(current_text)
            legacy = frozen('def worker(): pass')
            adapter = frozen('# synthetic bound adapter')
            workers = {freeze.WORKER_ADAPTER: adapter}
            binary = root / 'synthetic-binary';binary.write_text('# never executed')
            profile = root / 'profile.json'
            write(profile, {'spectre': str(binary), 'setup_scripts': []})
            tool = {'revision': 'synthetic', 'runtime_identity': 'synthetic',
                    'binary_sha256': sha(binary), 'setup_sha256': []}
            plan = [{'backend': b, 'condition': c, 'profile': 'base',
                     'input_identity': c, 'source_sha256': 'synthetic', 'work': c}
                    for b in runner.BACKENDS for c in freeze.SELECTED]
            write(inputs / 'RUN_PLAN.json', plan)
            write(inputs / 'INPUT_MANIFEST.json', {})
            write(inputs / 'provenance.json', {'checker_identity': 'synthetic'})
            for c in freeze.SELECTED:
                write(inputs / c / 'requested_settings.json', {})
            started = {'backend': 'spectre', 'input_manifest_sha256': sha(inputs / 'INPUT_MANIFEST.json'),
                       'runner_sha256': legacy, 'tool': tool, 'allocation': 'synthetic'}
            if mode != 'new':
                write(output / 'STARTED.json', started)
                # Original formatting is intentionally retained byte for byte.
                with (output / 'STARTED.json').open('a') as stream:stream.write(' \n')
                for c in freeze.SELECTED:
                    work = output / 'runs' / c / 'base'
                    write(work / 'requested_settings.json', {})
                    (work / 'simulate.log').write_text('synthetic completed log')
                    write(work / 'simulate.json', {'stage': 'simulate', 'exit_code': 0,
                          'timed_out': False, 'log_sha256': sha(work / 'simulate.log')})
                original = (output / 'STARTED.json').read_bytes()
            def execute(argv, work, stage, *args, **kwargs):
                if mode != 'new':raise AssertionError('resume must never launch a process')
                (work / (stage + '.log')).write_text('synthetic tool log')
                return {'stage': stage, 'exit_code': 0, 'timed_out': False}
            stack.enter_context(patch.object(runner, 'checker_identity', return_value='synthetic'))
            stack.enter_context(patch.object(runner, 'worker_sources', return_value=workers))
            stack.enter_context(patch.object(runner.os, 'sched_getaffinity', return_value={0}, create=True))
            stack.enter_context(patch.object(runner, 'execute', side_effect=execute))
            stack.enter_context(patch.object(runner, 'analyze', return_value={'status': 'unresolved'}))
            args = Namespace(inputs=inputs, output=output, backend='spectre', kernel=None,
                             spectre_profile=profile, allocation='synthetic', resume_finished_spectre=mode!='new')
            runner.run(args)
            if mode != 'new':self.assertEqual((output / 'STARTED.json').read_bytes(), original)
            if mode in ('legacy', 'legacy-continuation'):
                if mode == 'legacy':
                    (output / 'CONTINUATION.json').unlink()
                else:
                    (output / 'CONTINUATION.json').write_text(json.dumps({
                        'old_started_sha256': sha(output / 'STARTED.json'), 'runner_sha256': legacy}))
                results = load(output / 'EXECUTION.json')
                for result in results:result['runner_sha256'] = legacy
                (output / 'EXECUTION.json').write_text(json.dumps(results))
            if fault:
                continuation = load(output / 'CONTINUATION.json')
                if fault == 'missing-workers':continuation.pop('worker_sources', None)
                elif fault == 'wrong-adapter':continuation['worker_sources'] = {freeze.WORKER_ADAPTER: '0'*64}
                elif fault == 'extra-worker':continuation['worker_sources'] = {**workers, 'unknown.py': adapter}
                elif fault == 'wrong-started':continuation['old_started_sha256'] = '0'*64
                elif fault == 'wrong-runner':continuation['runner_sha256'] = legacy
                elif fault == 'unknown-contract':
                    digest = frozen("_EVAS_WORKER_PATH = OTHER / " + repr(freeze.WORKER_ADAPTER))
                    continuation['runner_sha256'] = digest
                    results = load(output / 'EXECUTION.json')
                    for result in results:result['runner_sha256'] = digest
                    (output / 'EXECUTION.json').write_text(json.dumps(results))
                if fault == 'missing-continuation':(output / 'CONTINUATION.json').unlink()
                else:(output / 'CONTINUATION.json').write_text(json.dumps(continuation))
            # Rebuild the synthetic raw manifest after the intentional fault.
            manifest = {str(p.relative_to(output)): {'sha256': sha(p), 'bytes': p.stat().st_size}
                        for p in output.rglob('*') if p.is_file() and p.name != 'FILE_MANIFEST.json'}
            (output / 'FILE_MANIFEST.json').write_text(json.dumps(manifest))
            snapshot = root / 'snapshot.json'
            write(snapshot, {'schema_version': 2, 'datasets': [
                {'id': 'cmp8-base', 'cases': [{'id': c, 'input_identity': c} for c in freeze.SELECTED]},
                {'id': 'application-reference'}], 'records': [
                {'dataset': 'cmp8-base', 'backend': 'spectre', 'case': c, 'accounting': 'unrun'}
                for c in freeze.SELECTED]})
            task = root / 'benchmark/material/historyref/tasks/va07-triangle-repair'
            write(task / 'tests/cases.json', [{'name': 'constant-tighter'}])
            for rel in ['solution/dut.va']:(task / rel).parent.mkdir(parents=True, exist_ok=True);(task / rel).write_text('synthetic')
            for name in ['triangle_oscillator.py', 'triangle_evas.py']:
                p = root / 'benchmark/material/historyref/legacy-authoring/checkers' / name
                p.parent.mkdir(parents=True, exist_ok=True);p.write_text('# synthetic')
            stack.enter_context(patch.object(ingest, 'ROOT', root))
            stack.enter_context(patch.object(ingest.subprocess, 'check_output', return_value='synthetic-revision'))
            stack.enter_context(patch.object(derive, 'freeze_candidates'))
            stack.enter_context(patch.object(ingest, 'validate'))
            data = ingest.ingest(snapshot, inputs, [output], root / 'compact')
            self.assertEqual(len([r for r in data['records'] if r['accounting']=='executed']), 8)
            receipt = load(root / 'compact/spectre' / freeze.SELECTED[0] / 'receipt.json')
            expected = {legacy} if mode in ('legacy', 'legacy-continuation') else {current, adapter} if mode == 'new' else {legacy, current, adapter}
            self.assertEqual({ref['sha256'] for ref in receipt['runner_sources']}, expected)
            self.assertEqual((root / 'compact/spectre/STARTED.json').read_bytes(), (output / 'STARTED.json').read_bytes())
            if mode == 'resume':self.assertEqual(receipt['continuation']['worker_sources'], workers)

    def test_resume_to_actual_ingest_preserves_started_and_binds_analysis(self):
        self.exercise()

    def test_new_execution_to_actual_ingest(self):
        self.exercise('new')

    def test_legacy_execution_to_actual_ingest(self):
        self.exercise('legacy')

    def test_legacy_continuation_without_worker_contract_to_actual_ingest(self):
        self.exercise('legacy-continuation')

    def test_resume_rejects_missing_analysis_workers(self):
        with self.assertRaisesRegex(ValueError, 'closure mismatch'):self.exercise(fault='missing-workers')

    def test_resume_rejects_wrong_analysis_worker_digest(self):
        with self.assertRaisesRegex(ValueError, 'not retrievable'):self.exercise(fault='wrong-adapter')

    def test_resume_rejects_unknown_extra_dependency(self):
        with self.assertRaisesRegex(ValueError, 'closure mismatch'):self.exercise(fault='extra-worker')

    def test_resume_rejects_wrong_started_digest(self):
        with self.assertRaisesRegex(ValueError, 'continuation.*identity'):self.exercise(fault='wrong-started')

    def test_resume_rejects_wrong_analysis_runner_digest(self):
        with self.assertRaisesRegex(ValueError, 'continuation.*identity'):self.exercise(fault='wrong-runner')

    def test_resume_rejects_missing_continuation(self):
        with self.assertRaisesRegex(ValueError, 'continuation.*identity'):self.exercise(fault='missing-continuation')

    def test_resume_rejects_unknown_analysis_contract(self):
        with self.assertRaisesRegex(ValueError, 'unknown comparison worker dependency'):self.exercise(fault='unknown-contract')

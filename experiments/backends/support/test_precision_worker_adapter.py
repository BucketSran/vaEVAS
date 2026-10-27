"""Synthetic precision transport controls; never compile or run a real DUT."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import precision_run as runner


def synthetic_evas(mode='success'):
    """Replace the entire public EVAS boundary, with an auditable call record."""
    module = types.ModuleType('evas')
    module.calls = []

    class CompileError(Exception):
        pass

    class KernelError(Exception):
        def __init__(self, message, detail):
            super().__init__(message)
            self.detail = detail

    module.CompileError = CompileError
    module.KernelError = KernelError
    module.Instance = lambda *args: list(args)

    def compile_sources(sources, instances):
        module.calls.append({'sources': sources, 'instances': instances})
        if mode == 'compile':
            raise CompileError('synthetic compile rejection')
        return types.SimpleNamespace(to_dict=lambda: {'synthetic_program': True})

    def transient(program, inputs, times, **kwargs):
        module.calls.append({'inputs': inputs, 'times': times, 'kwargs': kwargs})
        if mode == 'kernel':
            raise KernelError('synthetic kernel rejection', {'tag': 'synthetic'})
        if mode == 'generic':
            raise RuntimeError('synthetic worker rejection')
        response = {
            'engine': 'synthetic boundary only', 'nodes': ['y'],
            'transient': {'accepted_steps': 0},
            # Ordinary solutions deliberately disagree with the strobe response.
            'solutions': [{'voltages': [99.]} for t in times],
            'strobe_evidence': {
                'times': list(times), 'voltages_V': [[-0.0], [5e-324], [1.0000000000000002]][:len(times)],
                'sample_origins': ['implicit_history_evaluation', 'stateless_working_point',
                                   'implicit_history_evaluation'][:len(times)]},
            'observation_evidence': {'effective_controls': {'reltol': kwargs['reltol']},
                                     'sample_origins': ['accepted_controller_frame'] * len(times)}}
        if mode == 'mismatch':
            response['strobe_evidence']['times'] = [42.]
        if mode == 'short':
            response['strobe_evidence']['voltages_V'] = []
        if mode == 'nonfinite':
            response['strobe_evidence']['voltages_V'][0] = [float('nan')]
        return response

    module.compile_sources = compile_sources
    module.transient = transient
    return module


def fixture(work):
    request = {'instances': [{'name': 'x', 'module': 'synthetic', 'ports': {}, 'parameters': {}}],
               'inputs': {'u': [[0., -0.0], [1., 1.]]}, 'stop': 1., 'max_step': .125,
               'vabstol': 1e-9, 'reltol': 1e-6}
    (work/'request.json').write_text(json.dumps(request))
    # Duplicate and adjacent binary64 observations must reach transient unchanged.
    (work/'requested_times.json').write_text('[0.0, 0.0, 1.0000000000000002e-6]')
    (work/'dut.va').write_text('// synthetic boundary token; never compiled\n')
    return request


class PrecisionWorkerAdapter(unittest.TestCase):
    def run_worker(self, work, mode='success'):
        fake = synthetic_evas(mode)
        with patch.dict(sys.modules, {'evas': fake}):
            runner.worker(work, 'synthetic-kernel-must-not-execute')
        return fake

    def test_strobe_bytes_origins_and_public_arguments_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            request = fixture(work)
            fake = self.run_worker(work)
            call = fake.calls[-1]
            times = json.loads((work/'requested_times.json').read_text())
            self.assertEqual(call['times'], times)
            self.assertEqual(call['kwargs'], dict(stop=request['stop'], max_step=request['max_step'],
                strobetimes=times, kernel='synthetic-kernel-must-not-execute', vabstol=1e-9,
                reltol=1e-6, timeout=None))
            self.assertEqual((work/'waveform.csv').read_bytes(),
                b'time,y\r\n0.0,-0.0\r\n0.0,5e-324\r\n1.0000000000000002e-06,1.0000000000000002\r\n')
            raw = (work/'raw-response.json').read_bytes()
            self.assertIn(b'"voltages_V":[[-0.0],[5e-324],[1.0000000000000002]]', raw)
            self.assertEqual(json.loads((work/'worker-result.json').read_text()),
                {'status': 'waveform_available', 'origins': ['implicit_history_evaluation', 'stateless_working_point']})

    def test_failure_classes_and_partial_artifacts_remain_distinct(self):
        expected = {'compile': 'compile_failed', 'kernel': 'execution_failed',
                    'generic': 'execution_failed', 'mismatch': 'execution_failed',
                    'short': 'execution_failed', 'nonfinite': 'execution_failed'}
        for mode, status in expected.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                fixture(work)
                self.run_worker(work, mode)
                result = json.loads((work/'worker-result.json').read_text())
                self.assertEqual(result['status'], status)
                if mode == 'kernel':
                    self.assertEqual(result['detail'], {'tag': 'synthetic'})
                if mode in ('mismatch', 'short'):
                    self.assertTrue((work/'raw-response.json').is_file())
                self.assertNotIn('failure_stage', result)

    def test_missing_request_or_times_escapes_before_result(self):
        for missing in ('request.json', 'requested_times.json'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                fixture(work)
                (work/missing).unlink()
                with self.assertRaises(FileNotFoundError):
                    self.run_worker(work)
                self.assertFalse((work/'worker-result.json').exists())

    def test_existing_waveform_and_bad_request_keep_worker_rejection(self):
        for mode in ('existing-waveform', 'bad-request'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                work = Path(temporary)
                fixture(work)
                if mode == 'existing-waveform':
                    (work/'waveform.csv').write_bytes(b'original waveform\n')
                else:
                    (work/'request.json').write_text('{}')
                self.run_worker(work)
                self.assertEqual(json.loads((work/'worker-result.json').read_text())['status'], 'execution_failed')
                if mode == 'existing-waveform':
                    self.assertEqual((work/'waveform.csv').read_bytes(), b'original waveform\n')

    def test_current_freeze_binds_both_adapters_and_verify_rejects_drift(self):
        files = runner.source_files()
        self.assertEqual(len(files), len(set(files)))
        self.assertTrue(set(runner.worker_source_files()).issubset(files))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inputs = root/'inputs'
            inputs.mkdir()
            relative = 'evas/validation/adapters/precision_evas_worker.py'
            source = root/relative
            source.parent.mkdir(parents=True)
            source.write_bytes((ROOT/relative).read_bytes())
            (inputs/'SOURCE_IDENTITY.json').write_text(json.dumps({relative: runner.sha(source)}))
            (inputs/'MANIFEST.json').write_text(json.dumps({'SOURCE_IDENTITY.json': runner.sha(inputs/'SOURCE_IDENTITY.json')}))
            with patch.object(runner, 'ROOT', root):
                runner.verify(inputs)
                source.write_bytes(source.read_bytes() + b'\n# drift\n')
                with self.assertRaisesRegex(ValueError, 'source drift: .*precision_evas_worker'):
                    runner.verify(inputs)

"""Call the paper EVAS response adapter without a kernel or DUT simulation."""
import json
import tempfile
import unittest
from pathlib import Path

import runner
from actual_observation import EVAS_WORKER_ADAPTER, production_dependencies


REQUEST = {'reltol': 1e-5, 'vabstol': 1e-6, 'stop': 1e-6, 'max_step': 1e-9}
LEGACY = {'engine': 'synthetic-engine', 'transient': {'accepted_steps': 0, 'times': [0, 0.30000000000000004]}}
EVIDENCE = {'effective_controls': {'relative': 1e-5, 'absolute_V': 1e-6, 'stop_s': 1e-6,
                                   'max_step_s': 1e-9, 'max_step_applied': True},
            'sample_origins': ['accepted_controller_frame', 'certified_causal_frame', 'accepted_controller_frame']}


class PaperEvasWorkerAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = runner.evas_worker_adapter()

    def test_public_entry_and_adapter_write_the_same_response_bytes(self):
        response = {**LEGACY, 'observation_evidence': EVIDENCE, 'nodes': ['a'], 'extra': {'kept': True}}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            left = root / 'runner.json'
            right = root / 'adapter.json'
            runner.save_raw_response(left, response)
            self.adapter.save_raw_response(right, response)
            self.assertEqual(left.read_bytes(), right.read_bytes())
            self.assertEqual(runner.evas_effective_record(REQUEST, LEGACY),
                             self.adapter.evas_effective_record(REQUEST, LEGACY))
            self.assertEqual(runner.evas_effective_record(REQUEST, response),
                             self.adapter.evas_effective_record(REQUEST, response))

    def test_missing_request_stops_before_a_worker_result(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            with self.assertRaises(FileNotFoundError):
                runner.worker(work, Path('unused-kernel'))
            self.assertFalse((work / 'worker-result.json').exists())
            with self.assertRaises(FileNotFoundError):
                self.adapter.worker(work, Path('unused-kernel'))
            self.assertFalse((work / 'worker-result.json').exists())

    def test_incomplete_request_keeps_the_worker_failure_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            (work / 'request.json').write_text('{}\n')
            runner.worker(work, Path('unused-kernel'))
            record = json.loads((work / 'worker-result.json').read_text())
            self.assertEqual(record['status'], 'execution_failed')
            self.assertEqual(record['failure_stage'], 'worker')
            self.assertEqual(record['exception_type'], 'KeyError')
            self.assertFalse((work / 'waveform.csv').exists())
            self.assertFalse((work / 'raw-response.json').exists())

    def test_compact_response_rejects_nan_and_an_existing_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'raw.json'
            runner.save_raw_response(path, LEGACY)
            with self.assertRaises(FileExistsError):
                self.adapter.save_raw_response(path, LEGACY)
            with self.assertRaises(ValueError):
                runner.save_raw_response(Path(temporary) / 'nan.json', {'v': float('nan')})

    def test_production_closure_includes_the_adapter_file(self):
        sources = production_dependencies(Path(__file__).resolve().parents[3])
        self.assertIn(EVAS_WORKER_ADAPTER, sources)
        self.assertIn('experiments/backends/paper/runner.py', sources)


if __name__ == '__main__':
    unittest.main()

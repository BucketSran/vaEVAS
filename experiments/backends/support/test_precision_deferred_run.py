"""The v2 execution-only path exports all slots without running a checker."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import precision_v2_run as runner
from precision_breadth_reanalysis import verify_lane


class DeferredV2Tests(unittest.TestCase):
    def test_next_simulation_does_not_wait_for_analysis_and_raw_is_sealed(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            inputs = base / 'inputs'
            inputs.mkdir()
            profile = base / 'host.json'
            profile.write_text('{}')
            (inputs / 'cards.json').write_text('{}')
            (inputs / 'MANIFEST.json').write_text('{}')
            plan = []
            for name in ('a', 'b'):
                work = inputs / name
                work.mkdir()
                (work / 'condition.json').write_text('{}')
                plan.append({'label': name, 'condition': name, 'backend': 'evas',
                             'family': 'sample_hold', 'profile': 'base', 'work': name})
            (inputs / 'PLAN.json').write_text(json.dumps(plan))
            order = []
            def export(backend, tool, env, work):
                order.append(work.name)
                (work / 'waveform.csv').write_text('time,y\n0,1\n1,1\n')
                return {'status': 'waveform_available', 'waveform': 'waveform.csv',
                        'stages': [], 'abort_batch': False}
            out = base / 'out'
            with patch.object(runner, 'verify'), patch.object(runner, 'verify_tool'), \
                 patch.object(runner, 'preflight', return_value=({}, {})), \
                 patch.object(runner, 'execute_one', side_effect=export), \
                 patch.object(runner, 'read_native', side_effect=AssertionError('analysis called')) as reader, \
                 patch.object(runner, 'assess') as checker, patch.object(runner, 'effective_settings') as settings:
                runner.run(inputs, out, 'evas', profile, 'sample_hold', defer_analysis=True)
            reader.assert_not_called()
            checker.assert_not_called()
            settings.assert_not_called()
            self.assertEqual(order, ['a', 'b'])
            records = runner.load(out / 'EXECUTION.json')
            self.assertTrue(all(r['analysis_status'] == 'pending' for r in records))
            self.assertTrue(all('assessment' not in r and 'effective_settings' not in r for r in records))
            self.assertEqual(verify_lane(out)['status'], 'verified')

    def test_deferred_failure_keeps_unrun_slots(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            inputs = base / 'inputs'
            inputs.mkdir()
            profile = base / 'host.json'
            profile.write_text('{}')
            for name in ('cards.json', 'MANIFEST.json'):
                (inputs / name).write_text('{}')
            plan = []
            for name in ('a', 'b'):
                (inputs / name).mkdir()
                plan.append({'label': name, 'backend': 'evas', 'family': 'sample_hold', 'work': name})
            (inputs / 'PLAN.json').write_text(json.dumps(plan))
            out = base / 'out'
            with patch.object(runner, 'verify'), patch.object(runner, 'verify_tool'), \
                 patch.object(runner, 'preflight', return_value=({}, {})), \
                 patch.object(runner, 'execute_one', return_value={'status': 'compile_failed', 'abort_batch': True}), \
                 patch.object(runner, 'assess') as checker:
                runner.run(inputs, out, 'evas', profile, 'sample_hold', defer_analysis=True)
            checker.assert_not_called()
            rows = runner.load(out / 'EXECUTION.json')
            self.assertEqual([r['status'] for r in rows], ['compile_failed', 'not_run'])
            self.assertEqual(rows[0]['analysis_status'], 'not_available')
            self.assertEqual(verify_lane(out)['status'], 'verified')

    def test_adapter_exception_is_not_relabelled_as_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            inputs = base / 'inputs'
            inputs.mkdir()
            profile = base / 'host.json'
            profile.write_text('{}')
            for name in ('cards.json', 'MANIFEST.json'):
                (inputs / name).write_text('{}')
            plan = []
            for name in ('a', 'b'):
                (inputs / name).mkdir()
                plan.append({'label': name, 'backend': 'evas', 'family': 'sample_hold', 'work': name})
            (inputs / 'PLAN.json').write_text(json.dumps(plan))
            out = base / 'out'
            with patch.object(runner, 'verify'), patch.object(runner, 'verify_tool'), \
                 patch.object(runner, 'preflight', return_value=({}, {})), \
                 patch.object(runner, 'execute_one', side_effect=RuntimeError('failed after invocation')):
                with self.assertRaisesRegex(RuntimeError, 'failed after invocation'):
                    runner.run(inputs, out, 'evas', profile, 'sample_hold', defer_analysis=True)
            rows = runner.load(out / 'EXECUTION.json')
            self.assertEqual([r['status'] for r in rows], ['execution_failed', 'not_run'])
            self.assertEqual(rows[0]['analysis_status'], 'not_available')
            self.assertEqual(verify_lane(out)['status'], 'verified')


if __name__ == '__main__':
    unittest.main()

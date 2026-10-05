"""Runner controls detect wrong matrix and changed artifacts before launch."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from freeze import freeze
from runner import execute, effective_settings, verify


class RunnerControls(unittest.TestCase):
    def test_input_drift_prevents_any_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'frozen'
            freeze(root)
            self.assertEqual(len(verify(root)), 32)
            dut = next(root.rglob('dut.va'))
            dut.write_text(dut.read_text() + '\n// changed\n')
            with patch('runner.subprocess.Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'input drift'):
                    verify(root)
                launch.assert_not_called()

    def test_checker_drift_prevents_any_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'frozen'
            freeze(root)
            with patch('runner.checker_identity', return_value='different-checker'), patch('runner.subprocess.Popen') as launch:
                with self.assertRaisesRegex(ValueError, 'checker changed'):
                    verify(root)
                launch.assert_not_called()

    def test_spectre_settings_uses_exact_module_despite_name_collision(self):
        import json
        import types
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requested = {'vabstol': 1e-8, 'iabstol': 1e-12, 'reltol': 1e-5, 'stop': 4e-6,
                         'step': 1e-9, 'maxstep': 1e-9, 'method': 'traponly'}
            (root / 'requested_settings.json').write_text(json.dumps(requested))
            (root / 'spectre.log').write_text('\n'.join(f'{k} = {v}' for k, v in requested.items()) + '\n')
            with patch.dict('sys.modules', {'report': types.ModuleType('wrong_historical_report')}):
                actual = effective_settings(root, 'spectre')
            self.assertTrue(actual['requested_values_match'])
            self.assertEqual(actual['actual']['stop'], 4e-6)

    def test_timeout_records_failure_and_never_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            process = __import__('subprocess')
            with patch('runner.subprocess.Popen') as launch:
                launched = launch.return_value
                launched.pid = 100
                launched.returncode = -9
                launched.wait.side_effect = [process.TimeoutExpired('synthetic', .01), -9]
                with patch('runner.os.killpg') as kill:
                    result = execute(['synthetic'], root, 'simulate', timeout=.01)
                launch.assert_called_once()
                kill.assert_called_once()
                self.assertTrue(result['timed_out'])
                self.assertEqual(result['exit_code'], -9)
                self.assertTrue((root / 'simulate.json').is_file())


if __name__ == '__main__':
    unittest.main()

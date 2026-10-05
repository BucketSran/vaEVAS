"""Runner controls detect wrong matrix and changed artifacts before launch."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from freeze import freeze
from runner import execute, verify


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

"""Runner controls detect wrong matrix and changed artifacts before launch."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from freeze import freeze
from runner import execute, effective_settings, verify, run


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

    def test_selected_kernel_identity_is_recorded_before_simulation(self):
        import json
        import sys
        from argparse import Namespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'inputs'
            freeze(inputs)
            kernel = root / 'kernel'
            reported = {'identity_version': 1, 'name': 'evas-kernel', 'version': '0.13.0',
                        'ir_schema_version': 17, 'build_revision': 'frozen-build',
                        'request_protocol_version': None, 'platform': {'os': 'test', 'arch': 'test'}}
            kernel.write_text('#!' + sys.executable + '\nimport json\nprint(' + repr(json.dumps(reported)) + ')\n')
            kernel.chmod(0o755)
            output = root / 'output'
            args = Namespace(inputs=inputs, output=output, backend='evas', kernel=kernel,
                             allocation='local-test-only', resume_finished_spectre=False)
            with patch('runner.execute', side_effect=RuntimeError('simulation seam')) as launch:
                with self.assertRaisesRegex(RuntimeError, 'simulation seam'):
                    run(args)
            launch.assert_called_once()
            started = json.loads((output / 'STARTED.json').read_text())
            self.assertEqual(started['tool']['kernel_version'], '0.13.0')
            self.assertEqual(started['tool']['identity']['kernel']['reported'], reported)
            self.assertEqual(started['tool']['kernel_sha256'], started['tool']['identity']['kernel']['sha256'])
            self.assertEqual(json.loads((output / 'KERNEL_IDENTITY.json').read_text()), started['tool']['identity'])

    def test_invalid_selected_kernel_identity_prevents_simulation(self):
        import json
        import sys
        from argparse import Namespace
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'evas/src'))
        from evas import KernelError
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'inputs'
            freeze(inputs)
            kernel = root / 'kernel'
            kernel.write_text('#!' + sys.executable + '\nprint("not identity JSON")\n')
            kernel.chmod(0o755)
            output = root / 'output'
            args = Namespace(inputs=inputs, output=output, backend='evas', kernel=kernel,
                             allocation='local-test-only', resume_finished_spectre=False)
            with patch('runner.execute', side_effect=AssertionError('invalid identity launched simulation')) as launch:
                with self.assertRaises(KernelError):
                    run(args)
            launch.assert_not_called()
            self.assertFalse((output / 'STARTED.json').exists())
            facts = json.loads((output / 'KERNEL_IDENTITY.json').read_text())
            self.assertEqual(facts['kernel']['status'], 'error')
            self.assertIsNotNone(facts['kernel']['sha256'])

    def test_environment_image_inspection_has_bounded_timeout(self):
        import json
        from argparse import Namespace
        from records import ROOT, load
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = root / 'inputs'
            freeze(inputs)
            environment = root / 'environment'
            environment.mkdir()
            images = load(ROOT / 'experiments/archive/dvs2-starter-pilot/results/TOOL_IDENTITIES.json')['images']
            (environment / 'INPUT_MANIFEST.json').write_text('{}')
            compiler = environment / 'backend-semantics-v1/tools/reloaded/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r'
            compiler.parent.mkdir(parents=True)
            compiler.write_text('synthetic compiler; never launched')
            (environment / 'environment.py').write_text(
                'from pathlib import Path\nimport subprocess\nPACKAGE=Path(__file__).parent\n'
                + 'def check_inputs():\n subprocess.check_output(["synthetic-image-inspect"])\n return ' + repr(images) + '\n'
                + 'def container(*args): return ["synthetic-container"], "owned-test"\n')
            args = Namespace(inputs=inputs, output=root/'output', backend='openvaf_ngspice',
                             environment=environment, allocation='synthetic-only', resume_finished_spectre=False)
            with patch('runner.subprocess.check_output', return_value=b'{}') as inspect, patch('runner.execute', side_effect=RuntimeError('version boundary')):
                with self.assertRaisesRegex(RuntimeError, 'version boundary'):
                    run(args)
            self.assertEqual(inspect.call_args.kwargs.get('timeout'), 30)

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

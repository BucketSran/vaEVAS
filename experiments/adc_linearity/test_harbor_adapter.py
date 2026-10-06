"""Optional installed-Harbor integration; no Docker or remote simulation."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
try:
    from experiments.adc_linearity.harbor_adapter import ADCHarnessVerifier
except ModuleNotFoundError as error:
    if error.name!='harbor' and not error.name.startswith('harbor.'):
        raise
    ADCHarnessVerifier=None


@unittest.skipUnless(ADCHarnessVerifier,'optional Harbor dependency absent')
class HarborBoundary(unittest.TestCase):
    def test_transport_exception_is_private_and_log_projection_is_scalar(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);trial=root/'trial';trial.mkdir()
            private=root/'private';private.mkdir(mode=0o700)
            task=root/'va08-adc-linearity';task.mkdir()
            verifier=ADCHarnessVerifier.__new__(ADCHarnessVerifier)
            verifier.task=SimpleNamespace(paths=SimpleNamespace(task_dir=task))
            verifier.trial_paths=SimpleNamespace(trial_dir=trial,verifier_dir=trial/'verifier')
            verifier.environment=SimpleNamespace(_mounts=[dict(type='bind',source=str(trial))])
            verifier.config={'private_root':str(private)}
            verifier._evaluate=AsyncMock(side_effect=RuntimeError('SECRET hidden thresholds'))
            with self.assertRaisesRegex(RuntimeError,'private operator evidence retained') as caught:
                asyncio.run(verifier.verify())
            self.assertNotIn('SECRET',str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(json.loads((trial/'verifier/report.json').read_text()),{'status':'infrastructure_error','reward':None})
            self.assertIn('SECRET',next(private.glob('*/failure.txt')).read_text())

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
    from experiments.adc_linearity.harness_adapter import visible_mount_roots
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths
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
            envdir=task/'environment';envdir.mkdir();(envdir/'Dockerfile').write_text('FROM python:3.12-slim\n')
            verifier.environment=SimpleNamespace(_mounts=[dict(type='bind',source=str(trial))],extra_docker_compose_paths=[],environment_dir=envdir,task_env_config=SimpleNamespace(docker_image=None))
            verifier.config={'private_root':str(private)}
            verifier._evaluate=AsyncMock(side_effect=RuntimeError('SECRET hidden thresholds'))
            with self.assertRaisesRegex(RuntimeError,'private operator evidence retained') as caught:
                asyncio.run(verifier.verify())
            self.assertNotIn('SECRET',str(caught.exception))
            self.assertIsNone(caught.exception.__cause__)
            self.assertEqual(json.loads((trial/'verifier/report.json').read_text()),{'status':'infrastructure_error','reward':None})
            self.assertIn('SECRET',next(private.glob('*/failure.txt')).read_text())

    def test_real_harbor_docker_constructor_rejects_compose_and_prebuilt_entrypoints(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);task=root/'task';envdir=task/'environment';envdir.mkdir(parents=True)
            (envdir/'Dockerfile').write_text('FROM python:3.12-slim\n')
            trial=root/'trial';trial.mkdir()
            overlay=root/'overlay.yaml';overlay.write_text('services:\n  main:\n    volumes: ["/operator/private:/exposed"]\n')
            def environment(**kwargs):
                return DockerEnvironment(environment_dir=envdir,environment_name='adc-probe',session_id='adc-probe',
                    trial_paths=TrialPaths(trial_dir=trial),task_env_config=kwargs.pop('task_env_config',EnvironmentConfig()),**kwargs)
            clean=environment()
            self.assertEqual(clean.extra_docker_compose_paths,[])
            visible_mount_roots(clean,task,trial)
            custom=environment(extra_docker_compose=[str(overlay)])
            self.assertEqual(custom.extra_docker_compose_paths,[overlay.resolve()])
            self.assertEqual(custom._mounts,[])
            with self.assertRaises(ValueError): visible_mount_roots(custom,task,trial)
            compose=envdir/'docker-compose.yaml';compose.write_text(overlay.read_text())
            composed=environment()
            self.assertEqual(composed._environment_docker_compose_path,compose)
            with self.assertRaises(ValueError): visible_mount_roots(composed,task,trial)
            compose.unlink()
            prebuilt=environment(task_env_config=EnvironmentConfig(docker_image='python:3.12-slim'))
            with self.assertRaises(ValueError): visible_mount_roots(prebuilt,task,trial)

"""Identity queries cross the public Python and executable CLI boundaries."""
GUARDS = ["DEV:package-identity"]

import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = ROOT / 'rust_core/target/debug/evas-kernel'


class IdentityCLI(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'evas', 'version', '--json', *map(str, args)],
                              capture_output=True, text=True, timeout=8,
                              env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))

    def test_package_without_manifest_or_kernel(self):
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity['identity_version'], 1)
        self.assertEqual(identity['package']['name'], 'evas-rebuild')
        self.assertEqual(identity['package']['version'], '0.13.0')
        self.assertIsNone(identity['package']['build_revision'])
        self.assertEqual(identity['kernel']['status'], 'not_requested')
        self.assertEqual(identity['compatibility']['ir_schema_version'], 17)
        self.assertIsNone(identity['compatibility']['request_protocol_version'])

    def test_real_kernel_query_does_not_wait_for_stdin(self):
        # Keep stdin open: reading to EOF would hang, unlike an identity query.
        with subprocess.Popen([str(KERNEL), '--version', '--json'], stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                self.fail("kernel identity query waited for stdin")
            identity = json.loads(process.stdout.read())
            self.assertEqual(process.returncode, 0, process.stderr.read())
        self.assertEqual(identity['identity_version'], 1)
        self.assertEqual(identity['name'], 'evas-kernel')
        self.assertEqual(identity['version'], '0.13.0')
        self.assertIsNone(identity['build_revision'])
        self.assertEqual(identity['ir_schema_version'], 17)
        self.assertIsNone(identity['request_protocol_version'])
        result = self.cli('--kernel', KERNEL)
        self.assertEqual(result.returncode, 0, result.stderr)
        identity = json.loads(result.stdout)
        self.assertEqual(identity['kernel']['sha256'], hashlib.sha256(KERNEL.read_bytes()).hexdigest())
        self.assertEqual(identity['kernel']['path'], str(KERNEL.resolve()))
        self.assertEqual(identity['compatibility']['status'], 'ir_matched')

    def test_explicit_kernel_failures_keep_identity_and_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'selected'
            cases = [('missing', None, 'kernel_process'),
                     ('nonexecutable', '{}', 'kernel_process'),
                     ('wrong', '#!/bin/sh\necho not-json\n', 'invalid_response'),
                     ('query_exit', '#!/bin/sh\necho failed >&2\nexit 7\n', 'kernel_process'),
                     ('timeout', '#!/bin/sh\nexec sleep 30\n', 'kernel_timeout'),
                     ('malformed', '#!/bin/sh\necho \'{"identity_version":1,"name":"evas-kernel"}\'\n', 'invalid_response'),
                     ('protocol', '#!/bin/sh\necho \'{"identity_version":99}\'\n', 'invalid_response'),
                     ('mismatch', '#!/bin/sh\necho \'{"identity_version":1,"name":"evas-kernel","version":"0.13.0","build_revision":null,"ir_schema_version":16,"request_protocol_version":null,"platform":{"os":"test","arch":"test"}}\'\n', 'unsupported_ir_version')]
            for label, content, kind in cases:
                with self.subTest(label=label):
                    if path.exists():
                        path.unlink()
                    if content is not None:
                        path.write_text(content)
                        path.chmod(0o644 if label == 'nonexecutable' else 0o755)
                    result = self.cli('--kernel', path)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    identity = json.loads(result.stdout)
                    diagnostic = json.loads(result.stderr)
                    self.assertEqual(identity['kernel']['status'], 'error')
                    self.assertEqual(diagnostic['kind'], kind)
                    self.assertEqual(diagnostic['diagnostic_version'], 1)
                    self.assertEqual(identity['kernel']['path'], str(path.resolve()))
                    self.assertEqual(identity['kernel']['sha256'] is not None, content is not None)
                    if label == 'mismatch':
                        self.assertEqual(identity['kernel']['reported']['ir_schema_version'], 16)

    def test_nonregular_kernel_is_rejected_before_opening_or_hashing(self):
        with tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / 'kernel-fifo'
            os.mkfifo(fifo)
            for path in (Path('/dev/zero'), fifo, Path(directory)):
                with self.subTest(path=path):
                    result = subprocess.run(
                        [sys.executable, '-B', '-m', 'evas', 'version', '--json', '--kernel', str(path)],
                        capture_output=True, text=True, timeout=2,
                        env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))
                    self.assertEqual(result.returncode, 2, result.stderr)
                    identity = json.loads(result.stdout)
                    self.assertIsNone(identity['kernel']['sha256'])
                    self.assertEqual(identity['kernel']['status'], 'error')
                    self.assertEqual(json.loads(result.stderr)['kind'], 'kernel_process')

    def test_matching_pair_compiles_and_runs_independent_integral_smoke(self):
        def invoke(*args):
            return subprocess.run([sys.executable, '-m', 'evas', *map(str, args)],
                                  capture_output=True, text=True, timeout=10,
                                  env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))
        manifest = ROOT / 'validation/smoke/idt.json'
        compiled = invoke('compile', manifest)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        self.assertEqual(json.loads(compiled.stdout)['schema_version'], 17)
        solved = invoke('transient', manifest, '--kernel', KERNEL)
        self.assertEqual(solved.returncode, 0, solved.stderr)
        response = json.loads(solved.stdout)
        index = response['nodes'].index('output')
        self.assertEqual(response['transient']['times'], [0, 1e-6, 2e-6, 3e-6, 4e-6])
        # Integral of the documented linear input, with initial value 0.25 V.
        for row, expected in zip(response['solutions'], [0.25, 0.4, 0.45, 0.4, 0.25]):
            self.assertAlmostEqual(row['voltages'][index], expected, delta=1e-9)

    def test_missing_installed_metadata_returns_structured_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            site = Path(directory) / 'site'
            shutil.copytree(ROOT / 'src/evas', site / 'evas', ignore=shutil.ignore_patterns('__pycache__'))
            result = subprocess.run([sys.executable, '-S', '-B', '-m', 'evas', 'version', '--json'],
                                    cwd=directory, capture_output=True, text=True, timeout=3,
                                    env=dict(os.environ, PYTHONPATH=str(site)))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stderr)['code'], 'input_error')
            self.assertNotIn('Traceback', result.stderr)

    def test_source_identity_does_not_borrow_another_installed_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            dist = Path(directory) / 'evas_rebuild-99.0.dist-info'
            dist.mkdir()
            (dist / 'METADATA').write_text('Metadata-Version: 2.1\nName: evas-rebuild\nVersion: 99.0\n')
            result = subprocess.run([sys.executable, '-m', 'evas', 'version', '--json'],
                                    capture_output=True, text=True, timeout=8,
                                    env=dict(os.environ, PYTHONPATH=str(ROOT / 'src') + os.pathsep + directory))
            self.assertEqual(result.returncode, 0, result.stderr)
            package = json.loads(result.stdout)['package']
            self.assertEqual(package['version'], '0.13.0')
            self.assertEqual(package['metadata_source'], 'source_pyproject')

    def test_identity_bypasses_simulation_configuration_and_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / 'diagnostics.json'
            result = subprocess.run([str(KERNEL), '--version', '--json'],
                                    capture_output=True, text=True, timeout=8,
                                    env=dict(os.environ, EVAS_STATIC_THREADS='invalid',
                                             EVAS_DIAGNOSTICS_RECORDS='invalid',
                                             EVAS_DIAGNOSTICS_PATH=str(artifact)))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['name'], 'evas-kernel')
            self.assertFalse(artifact.exists())

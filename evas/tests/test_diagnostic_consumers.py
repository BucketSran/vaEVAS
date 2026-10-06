"""Real public inputs retain failure identity across repository consumers."""
GUARDS = ['LANG']

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from evas import CompileError
from evas.lint import compile_manifest
from evas.results import run

ROOT = Path(__file__).resolve().parents[1]


class ConsumerContracts(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.path = self.root / 'sim.json'
        self.path.write_text(json.dumps(dict(models=['bad.va'], instances=[dict(
            name='dut', module='m', connections=dict(y='y'))], driven=[], samples=[[]])))
        self.source = self.root / 'bad.va'
        self.source.write_bytes(b'\xff')

    def cli(self, module, *args):
        return subprocess.run([sys.executable, '-B', '-m', module, *map(str, args)],
                              capture_output=True, text=True, timeout=10,
                              env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')))

    def test_compile_and_lint_share_source_identity(self):
        with self.assertRaises(CompileError) as caught:
            compile_manifest(self.path)
        for action in ('lint', 'compile', 'solve', 'transient'):
            result = self.cli('evas', action, self.path)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stderr), caught.exception.diagnostic)
            self.assertEqual(result.stdout, '')

    def test_results_api_and_failed_bundle_share_input_identity(self):
        self.path.unlink()
        with self.assertRaises(CompileError) as caught:
            run(self.path, kernel=self.root / 'missing', out=self.root / 'out')
        bundle = json.loads((self.root / 'out/manifest.json').read_text())
        self.assertEqual(bundle['error'], caught.exception.diagnostic)
        self.assertEqual(bundle['status'], 'failed')
        self.assertEqual(caught.exception.diagnostic['category'], 'infrastructure')

    def test_capture_cli_keeps_compile_location_and_instance(self):
        self.source.write_text('module m(y); output y; electrical y; analog begin V(y)<+V(missing); end endmodule')
        # capture records the kernel identity before compiling; existing file is sufficient here.
        result = self.cli('evas.diagnostics', 'capture', self.path, '--kernel', sys.executable,
                          '--out', self.root / 'session.json')
        self.assertEqual(result.returncode, 2)
        with self.assertRaises(CompileError) as caught:
            compile_manifest(self.path)
        self.assertEqual(caught.exception.diagnostic['code'], 'undeclared_node')
        self.assertEqual(caught.exception.diagnostic['instance'], 'dut')
        self.assertEqual(caught.exception.diagnostic['location']['source'], str(self.source.resolve()))
        self.assertEqual(json.loads(result.stderr), caught.exception.diagnostic)
        self.assertFalse((self.root / 'session.json').exists())

    def test_command_argument_errors_are_diagnostics(self):
        for module, args in [('evas', []), ('evas.results', []),
                             ('evas.diagnostics', []), ('evas', ['version']), ('evas.mcp', [])]:
            with self.subTest(module=module):
                result = self.cli(module, *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)['code'], 'input_error')
                self.assertEqual(result.stdout, '')

    def test_source_encoding_identity_in_capture_and_results_apis(self):
        from evas.diagnostics import capture
        with self.assertRaises(CompileError) as expected:
            compile_manifest(self.path)
        for operation in (lambda: capture(self.path, sys.executable),
                          lambda: run(self.path, kernel=sys.executable, out=self.root / 'bundle')):
            with self.assertRaises(CompileError) as caught:
                operation()
            self.assertEqual(caught.exception.diagnostic, expected.exception.diagnostic)

    def test_migration_retains_legacy_text_and_structured_source_reason(self):
        from evas.migrate import recompile_manifest
        with self.assertRaises(CompileError) as expected:
            compile_manifest(self.path)
        result = recompile_manifest(self.path, self.root / 'ir.json')
        self.assertEqual(result.status, 'failure')
        self.assertEqual(result.diagnostic, str(expected.exception))
        self.assertEqual(result.error, expected.exception.diagnostic)

    def test_future_kernel_diagnostic_version_keeps_raw_reason_unknown(self):
        from evas import KernelError, Instance, compile_sources, solve
        executable = self.root / 'future-kernel'
        detail = dict(kind='unsupported_timer', message='future contract', diagnostic_version=2,
                      sample=3, future_field=42)
        executable.write_text('#!' + sys.executable + '\nimport sys\nsys.stderr.write(' +
                              repr(json.dumps(detail)) + ')\nraise SystemExit(2)\n')
        executable.chmod(0o755)
        with self.assertRaises(KernelError) as caught:
            program = compile_sources({'m.va': 'module m(y); output y; electrical y; analog begin V(y)<+1; end endmodule'},
                                      [Instance('dut', 'm', dict(y='y'))])
            solve(program, [], [[]], kernel=executable)
        self.assertEqual(caught.exception.detail, detail)
        report = caught.exception.diagnostic
        self.assertEqual(report['diagnostic_version'], 2)
        self.assertEqual(report['category'], 'unknown')
        self.assertIsNone(report['capability'])
        self.assertEqual(report['sample'], 3)
        self.assertEqual(report['future_field'], 42)

    def test_failed_session_status_exposes_category_and_retains_raw_kernel_error(self):
        from evas.diagnostics import capture, Session
        kernel = ROOT / 'rust_core/target/debug/evas-kernel'
        self.source.write_text('module m(y); output y; electrical y; analog begin V(y)<+1; end endmodule')
        data = json.loads(self.path.read_text())
        data.update(driven=['missing'], samples=[[0]])
        self.path.write_text(json.dumps(data))
        artifact = capture(self.path, kernel)
        raw = artifact['payload']['error']
        self.assertEqual(artifact['payload']['status'], 'failed')
        report = artifact['payload']['error_diagnostic']
        self.assertEqual(report['kind'], raw['kind'])
        self.assertEqual(report['message'], raw['message'])
        self.assertEqual(report['category'], 'invalid_input')
        saved = self.root / 'session.json'
        saved.write_text(json.dumps(artifact))
        status = Session(saved).query('status')
        self.assertEqual(status['error'], raw)
        self.assertEqual(status['error_diagnostic'], report)

        # Legacy sessions remain readable; absent metadata stays absent.
        from evas.diagnostics import canonical, digest
        artifact['payload'].pop('error_diagnostic')
        artifact['payload_sha256'] = digest(canonical(artifact['payload']))
        saved.write_text(json.dumps(artifact))
        legacy = Session(saved).query('status')
        self.assertEqual(legacy['status'], 'failed')
        self.assertEqual(legacy['error'], raw)
        self.assertIsNone(legacy['error_diagnostic'])

    def test_public_sha256_file_retains_valid_file_call(self):
        from evas.migrate import sha256_file
        # Independently known SHA-256 for UTF-8 'abc'.
        self.source.write_bytes(b'abc')
        self.assertEqual(sha256_file(self.source),
                         'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

"""Public execution boundaries reject missing or incompatible selected kernels."""
from pathlib import Path
GUARDS = ['DEV:installed-kernel-selection']

import json
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest

from evas import Instance, KernelError, compile_sources, solve


class KernelSelection(unittest.TestCase):
    def program(self):
        return compile_sources({'m.va': '`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u); end endmodule'},
                               [Instance(name='dut', module='m', connections={'u':'u', 'y':'y'})])

    def test_source_install_without_bundle_has_actionable_default_error(self):
        with self.assertRaises(KernelError) as failure:
            solve(self.program(), ['u'], [[0.25]])
        self.assertIn('kernel', failure.exception.diagnostic['message'])
        self.assertIn('--kernel', failure.exception.diagnostic['message'])

    def test_explicit_missing_kernel_reports_selected_path_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            selected = Path(directory)/'missing-explicit-kernel'
            with self.assertRaises(KernelError) as failure:
                solve(self.program(), ['u'], [[0.25]], kernel=selected)
            self.assertIn(str(selected), failure.exception.diagnostic['message'])
            self.assertIn('matching platform', failure.exception.diagnostic['message'])


    def test_api_explicit_bare_command_keeps_path_lookup(self):
        kernel = Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel'
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory)/'evas-test-path-command'
            executable.symlink_to(kernel)
            with patch.dict(os.environ, PATH=str(directory)+os.pathsep+os.environ['PATH']):
                response = solve(self.program(), ['u'], [[0.25]], kernel=executable.name)
            self.assertAlmostEqual(response['solutions'][0]['voltages'][response['nodes'].index('y')], 0.5, delta=1e-9)

    def test_cli_explicit_bare_name_keeps_current_directory_path_semantics(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            command_folder = directory/'commands'
            command_folder.mkdir()
            executable = command_folder/'evas-test-path-command'
            executable.symlink_to(root/'rust_core/target/debug/evas-kernel')
            source = directory/'m.va'
            source.write_text('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u); end endmodule')
            manifest = directory/'sim.json'
            manifest.write_text(json.dumps(dict(models=['m.va'], instances=[dict(name='dut',module='m',connections=dict(u='u',y='y'))],driven=['u'],samples=[[.25]])))
            result = subprocess.run([sys.executable,'-m','evas','solve',str(manifest),'--kernel',executable.name],cwd=directory,
                                    env=dict(os.environ, PYTHONPATH=str(root/'src'),PATH=str(command_folder)+os.pathsep+os.environ['PATH']),
                                    capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,2,result.stdout)
            self.assertIn(str(directory/executable.name),json.loads(result.stderr)['message'])


if __name__ == '__main__':
    unittest.main()

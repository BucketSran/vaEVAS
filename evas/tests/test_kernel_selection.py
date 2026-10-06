"""Public execution boundaries reject missing or incompatible selected kernels."""
from pathlib import Path
GUARDS = ['DEV:installed-kernel-selection']

import tempfile
import unittest

from evas import Instance, KernelError, compile_sources, solve


class KernelSelection(unittest.TestCase):
    def program(self):
        return compile_sources({'m.va': 'module m(u,y); input u; output y; electrical u,y; analog begin V(y)<+2*V(u); end endmodule'},
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


if __name__ == '__main__':
    unittest.main()

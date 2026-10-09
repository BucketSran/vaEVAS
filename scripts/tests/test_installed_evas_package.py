"""Distribution tags must describe the actual shipped executable."""
import ast
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'evas/src'))
from check_installed_evas import CHECK, check_wheel_payload


class InstalledSourceAdmission(unittest.TestCase):
    def test_actual_installed_check_sources_compile_before_kernel_checks(self):
        # Read the actual authored CHECK fixtures; do not execute its installed
        # metadata assertions or normalize source on the way to compilation.
        from evas import Instance, KernelError, compile_sources, solve
        sources = [node.value.value for node in ast.parse(CHECK).body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'source' for t in node.targets)]
        self.assertEqual(len(sources), 2)
        static = compile_sources({'m.va': sources[0]}, [Instance('dut','m',{'u':'u','y':'y'})])
        integral = compile_sources({'integral.va': sources[1]}, [Instance('dut','m',{'y':'y'})])
        self.assertEqual(len(integral.operators), 1)
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory)/'absent-kernel'
            with self.assertRaisesRegex(KernelError, 'absent-kernel'):
                solve(static, ['u'], [[0]], kernel=missing)


class InstalledWheelTags(unittest.TestCase):
    def wheel(self, folder, tag, *, metadata_tag=None, reported_arch='aarch64'):
        # Mach-O constants/fields from Apple's loader.h/machine.h. This minimal
        # thin arm64 header carries a real LC_BUILD_VERSION with minimum 14.0.
        binary = struct.pack('<8I', 0xfeedfacf, 0x0100000c, 0, 2, 1, 24, 0, 0)
        binary += struct.pack('<6I', 0x32, 24, 1, 0x000e0000, 0x000e0500, 0)
        receipt = dict(sha256=hashlib.sha256(binary).hexdigest(),
                       platform=dict(os='macos',arch='aarch64'),
                       reported=dict(platform=dict(os='macos',arch=reported_arch)),
                       wheel_platform=tag, rust_target='aarch64-apple-darwin',
                       macos_deployment_target='14.0')
        path = folder/f'evas_rebuild-0.13.0-py3-none-{tag}.whl'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('evas_rebuild-0.13.0.dist-info/WHEEL',
                             'Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: py3-none-'+(metadata_tag or tag)+'\n')
            archive.writestr('evas/_bin/evas-kernel', binary)
            archive.writestr('evas/_bin/kernel.json', json.dumps(receipt))
        return path

    def test_thin_arm64_with_matching_minimum_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            facts = check_wheel_payload(self.wheel(Path(directory), 'macosx_14_0_arm64'))
            self.assertEqual(facts['executable'], dict(architecture='arm64',minimum_macos=[14,0,0]))

    def test_thin_arm64_cannot_be_distributed_as_universal2(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, 'architecture'):
                check_wheel_payload(self.wheel(Path(directory), 'macosx_14_0_universal2'))

    def test_tag_cannot_claim_an_os_older_than_linked_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, 'older than linked'):
                check_wheel_payload(self.wheel(Path(directory), 'macosx_10_13_arm64'))

    def test_filename_and_wheel_metadata_tags_must_agree(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, 'filename'):
                check_wheel_payload(self.wheel(Path(directory), 'macosx_14_0_arm64', metadata_tag='macosx_14_0_universal2'))

    def test_reported_architecture_must_agree_with_executable_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(AssertionError, 'reported kernel platform'):
                check_wheel_payload(self.wheel(Path(directory), 'macosx_14_0_arm64', reported_arch='x86_64'))


if __name__ == '__main__':
    unittest.main()

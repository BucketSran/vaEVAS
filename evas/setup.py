"""Build the standalone Rust executable into a native-platform Python wheel."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import struct
import sys
import shutil
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.errors import CompileError


def native_policy():
    """Build only the native targets tested by the package-install workflow."""
    machine = platform.machine().lower()
    if sys.platform == 'darwin' and machine in ('arm64', 'aarch64'):
        # Deliberately target the host's major OS release. This is a build policy,
        # not a guess at the earliest OS on which an older binary might run.
        major = int(platform.mac_ver()[0].split('.')[0])
        if major < 11:
            raise CompileError('native arm64 macOS wheels require macOS 11 or newer')
        return dict(host='aarch64-apple-darwin', platform=dict(os='macos', arch='aarch64'),
                    wheel_platform=f'macosx_{major}_0_arm64', deployment=f'{major}.0')
    if sys.platform == 'linux' and machine == 'x86_64':
        return dict(host='x86_64-unknown-linux-gnu', platform=dict(os='linux', arch='x86_64'),
                    wheel_platform='linux_x86_64', deployment=None)
    raise CompileError('native wheels are supported only on Linux x86_64 and macOS arm64; use cargo and an explicit kernel for other targets')


class BuildKernel(build_py):
    def run(self):
        super().run()
        # Editable development keeps the established cargo + explicit-path flow.
        if self.editable_mode:
            return
        root = Path(__file__).resolve().parent
        policy = native_policy()
        target = (root / self.get_finalized_command('build').build_base / ('cargo-native-'+policy['wheel_platform'])).resolve()
        try:
            facts = subprocess.check_output(['rustc', '-vV'], text=True)
            host = next(line.split(': ', 1)[1] for line in facts.splitlines() if line.startswith('host: '))
            if host != policy['host'] or os.environ.get('CARGO_BUILD_TARGET', host) != host:
                raise ValueError('Rust host and requested target must match the native wheel platform; cross builds are unsupported')
            environment = dict(os.environ)
            if policy['deployment'] is not None:
                environment['MACOSX_DEPLOYMENT_TARGET'] = policy['deployment']
            subprocess.run(['cargo', 'build', '--locked', '--release', '--target', host,
                            '--target-dir', str(target), '--manifest-path', str(root/'rust_core/Cargo.toml')], check=True, env=environment)
            executable = target/host/'release'/('evas-kernel.exe' if os.name=='nt' else 'evas-kernel')
            report = json.loads(subprocess.check_output([str(executable),'--version','--json'], text=True))
            if report['platform'] != policy['platform']:
                raise ValueError('reported kernel platform does not match native Rust target')
            if policy['deployment'] is not None:
                architectures = subprocess.check_output(['lipo', '-archs', str(executable)], text=True).split()
                if architectures != ['arm64']:
                    raise ValueError('kernel must be a thin native arm64 executable')
                commands = subprocess.check_output(['otool', '-l', str(executable)], text=True)
                minimums = re.findall(r'\bminos\s+(\d+\.\d+(?:\.\d+)?)', commands)
                if minimums != [policy['deployment']]:
                    raise ValueError(f'linked minimum OS {minimums} differs from requested deployment {policy["deployment"]}')
            else:
                with executable.open('rb') as stream:
                    header = stream.read(64)
                if (len(header) < 64 or header[:6] != b'\x7fELF\x02\x01'
                        or struct.unpack_from('<H', header, 18)[0] != 62):
                    raise ValueError('kernel must be a native ELF64 x86_64 executable')
        except (OSError, subprocess.CalledProcessError, ValueError, StopIteration) as exc:
            raise CompileError(f'Cannot build/run evas-kernel. Install native Rust/Cargo and retry: {exc}') from exc
        if report['version'] != self.distribution.get_version():
            raise CompileError('Rust and Python package versions must match')
        folder = Path(self.build_lib)/'evas/_bin'
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder/executable.name
        shutil.copy2(executable, destination)
        destination.chmod(0o755)
        (folder/'kernel.json').write_text(json.dumps(dict(
            platform=report['platform'], reported=report, wheel_platform=policy['wheel_platform'],
            rust_target=host, macos_deployment_target=policy['deployment'],
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest()), sort_keys=True)+'\n')


class PlatformWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        if (self.plat_name_supplied or self.skip_build
                or 'plat_name' in self.distribution.get_option_dict('bdist')
                or os.environ.get('_PYTHON_HOST_PLATFORM')):
            raise CompileError('manual platform overrides and skip-build are unsupported for native kernel wheels')
        self.root_is_pure = False

    def get_tag(self):
        # Python may itself be universal2; this kernel is a native thin binary.
        return 'py3', 'none', native_policy()['wheel_platform']


setup(cmdclass={'build_py': BuildKernel, 'bdist_wheel': PlatformWheel})

"""Build the standalone Rust executable into a native-platform Python wheel."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.bdist_wheel import bdist_wheel
from setuptools.errors import CompileError


class BuildKernel(build_py):
    def run(self):
        super().run()
        # Editable development keeps the established cargo + explicit-path flow.
        if self.editable_mode:
            return
        root = Path(__file__).resolve().parent
        target = (root / self.get_finalized_command('build').build_base / 'cargo').resolve()
        try:
            facts = subprocess.check_output(['rustc', '-vV'], text=True)
            host = next(line.split(': ', 1)[1] for line in facts.splitlines() if line.startswith('host: '))
            subprocess.run(['cargo', 'build', '--locked', '--release', '--target', host,
                            '--target-dir', str(target), '--manifest-path', str(root/'rust_core/Cargo.toml')], check=True)
            executable = target/host/'release'/('evas-kernel.exe' if os.name=='nt' else 'evas-kernel')
            report = json.loads(subprocess.check_output([str(executable),'--version','--json'], text=True))
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
            platform=report['platform'], reported=report,
            sha256=hashlib.sha256(destination.read_bytes()).hexdigest()), sort_keys=True)+'\n')


class PlatformWheel(bdist_wheel):
    def finalize_options(self):
        super().finalize_options()
        self.root_is_pure = False

    def get_tag(self):
        # The executable has no Python ABI. Preserve the native platform tag.
        _, _, platform = super().get_tag()
        return 'py3', 'none', platform


setup(cmdclass={'build_py': BuildKernel, 'bdist_wheel': PlatformWheel})

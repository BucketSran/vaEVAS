"""Select an explicit executable or verify this distribution's bundled kernel."""
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import sys

from .errors import KernelError
from .identity import inspect_identity, package_identity


def _platform():
    system = {'darwin': 'macos', 'win32': 'windows'}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    arch = {'arm64': 'aarch64', 'amd64': 'x86_64'}.get(machine, machine)
    return dict(os=system, arch=arch)


def select_kernel(kernel=None):
    """An explicit selection never falls back to another executable.

    Explicit paths retain the existing runtime protocol validation. A default
    bundle additionally verifies the build receipt, file and reported identity.
    """
    if kernel is not None:
        return Path(kernel).resolve()
    directory = Path(__file__).resolve().parent / '_bin'
    selected = directory / ('evas-kernel.exe' if os.name == 'nt' else 'evas-kernel')
    remedy = 'Install a wheel for your OS/architecture, or build evas/rust_core with cargo and pass --kernel PATH (API: kernel=PATH).'
    try:
        if not selected.is_file():
            raise ValueError('bundled kernel is missing')
        receipt = json.loads((directory / 'kernel.json').read_text())
        if not isinstance(receipt, dict) or receipt.get('platform') != _platform():
            raise ValueError('bundled kernel platform does not match this OS/architecture')
        if receipt.get('sha256') != hashlib.sha256(selected.read_bytes()).hexdigest():
            raise ValueError('bundled kernel file does not match its build receipt')
        identity, error = inspect_identity(selected)
        if error is not None:
            raise error
        reported = identity['kernel']['reported']
        if (reported != receipt.get('reported')
                or reported['platform'] != _platform()
                or reported['version'] != package_identity()['version']):
            raise ValueError('bundled kernel identity does not match this distribution/platform')
    except (OSError, ValueError, KeyError, KernelError, metadata.PackageNotFoundError) as exc:
        detail = exc.diagnostic if isinstance(exc, KernelError) else dict(kind='kernel_process', message=str(exc))
        raise KernelError(dict(detail, message=f"{detail['message']}; selected {selected}. {remedy}")) from exc
    return selected

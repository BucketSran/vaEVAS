"""Inspect package metadata and an explicitly selected executable, without solving."""
import ast
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import subprocess
import sys

from .errors import KernelError
from .ir import SCHEMA_VERSION
from .manifest import finite_float, reject_constant, unique_object

IDENTITY_VERSION = 1
QUERY_TIMEOUT = 5.0


def package_identity():
    """Use the owning source pyproject, or installed distribution metadata."""
    path = Path(__file__).resolve().parents[2] / 'pyproject.toml'
    if path.is_file():
        # Python 3.10 has no stdlib TOML reader. Read only the string-valued
        # version in this project's metadata section, never a nearby checkout.
        text = path.read_text()
        section = re.search(r'^\[project\]\s*$(.*?)(?=^\[|\Z)', text, re.M | re.S)
        value = re.search(r'^version\s*=\s*("[^"\n]*"|\x27[^\x27\n]*\x27)\s*$', section[1], re.M) if section else None
        if value is None:
            raise ValueError('source project metadata has no string version')
        version = ast.literal_eval(value[1])
        source = 'source_pyproject'
    else:
        version = metadata.version('evas-rebuild')
        source = 'distribution'
    return dict(name='evas-rebuild', version=version, metadata_source=source,
                build_revision=None)


def inspect_identity(kernel=None):
    """Return available facts and a KernelError on failed explicit selection."""
    result = dict(identity_version=IDENTITY_VERSION, package=package_identity(),
                  platform=dict(os=sys.platform, arch=platform.machine()),
                  compatibility=dict(ir_schema_version=SCHEMA_VERSION,
                                     request_protocol_version=None, status='not_checked'),
                  kernel=dict(status='not_requested'))
    if kernel is None:
        return result, None
    selected = Path(kernel).resolve()
    facts = dict(status='error', path=str(selected), sha256=None, reported=None)
    result['kernel'] = facts
    try:
        digest = hashlib.sha256()
        with selected.open('rb') as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b''):
                digest.update(chunk)
        facts['sha256'] = digest.hexdigest()
        process = subprocess.run([str(selected), '--version', '--json'], stdin=subprocess.DEVNULL,
                                 capture_output=True, text=True, timeout=QUERY_TIMEOUT, check=False)
        if process.returncode:
            raise KernelError(dict(kind='kernel_process', message=f'identity query exited {process.returncode}: {process.stderr}'))
        try:
            reported = json.loads(process.stdout, object_pairs_hook=unique_object,
                                  parse_constant=reject_constant, parse_float=finite_float)
            if isinstance(reported, dict):
                facts['reported'] = reported
            if not isinstance(reported, dict) or type(reported.get('identity_version')) is not int or reported['identity_version'] != IDENTITY_VERSION:
                raise ValueError('unsupported or missing identity_version')
            if (reported.get('name') != 'evas-kernel' or not isinstance(reported.get('version'), str)
                    or type(reported.get('ir_schema_version')) is not int
                    or 'build_revision' not in reported
                    or reported['build_revision'] is not None and not isinstance(reported['build_revision'], str)
                    or 'request_protocol_version' not in reported
                    or reported['request_protocol_version'] is not None and type(reported['request_protocol_version']) is not int
                    or not isinstance(reported.get('platform'), dict)
                    or not all(isinstance(reported['platform'].get(key), str) for key in ('os', 'arch'))):
                raise ValueError('malformed kernel identity')
        except (ValueError, RecursionError) as exc:
            raise KernelError(dict(kind='invalid_response', message=f'invalid kernel identity: {exc}')) from exc
        facts['reported'] = reported
        if reported['ir_schema_version'] != SCHEMA_VERSION:
            result['compatibility']['status'] = 'ir_mismatch'
            raise KernelError(dict(kind='unsupported_ir_version', message=f"expected IR version {SCHEMA_VERSION}, kernel reports {reported['ir_schema_version']}"))
        facts['status'] = 'queried'
        result['compatibility']['status'] = 'ir_matched'
        return result, None
    except subprocess.TimeoutExpired:
        error = KernelError(dict(kind='kernel_timeout', message=f'identity query exceeded {QUERY_TIMEOUT} s', timeout_seconds=QUERY_TIMEOUT))
    except (OSError, UnicodeError) as exc:
        error = KernelError(dict(kind='kernel_process', message=str(exc)))
    except KernelError as exc:
        error = exc
    return result, error


def main(argv):
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--json', action='store_true', required=True)
    parser.add_argument('--kernel', type=Path)
    args = parser.parse_args(argv)
    try:
        result, error = inspect_identity(args.kernel)
    except (OSError, ValueError) as exc:
        from .errors import diagnostic
        print(json.dumps(diagnostic('input_io' if isinstance(exc, OSError) else 'input_error', str(exc))), file=sys.stderr)
        return 2
    print(json.dumps(result, allow_nan=False))
    if error is not None:
        print(json.dumps(error.diagnostic, allow_nan=False), file=sys.stderr)
        return 2
    return 0

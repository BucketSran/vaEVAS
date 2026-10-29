"""Discover actual unittest instances, without running test bodies or generic unwrap.
Trusted source imports execute. Archived/untrusted code is not a discovery input.
"""
import argparse
import functools
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import types
import unittest

# Freeze runtime-native authority before any selected source tree is imported.
_NATIVE_SKIP = unittest.skip
_NATIVE_SKIP_FACTORY_CODE = _NATIVE_SKIP.__code__
_NATIVE_FUNCTION = types.FunctionType
_NATIVE_METHOD = types.MethodType

def _probe():
    raise RuntimeError('authority probe body must never execute')

_NATIVE_WRAPPER_CODE = _NATIVE_SKIP('authority probe')(_probe).__code__
_TOOL_PATH = Path(__file__).resolve()
_TOOL_SHA = hashlib.sha256(_TOOL_PATH.read_bytes()).hexdigest()

def _span(code):
    # inspect.getsourcelines(function) silently calls generic inspect.unwrap.
    # A code object has no __wrapped__ and identifies the actual callable body.
    file = Path(inspect.getsourcefile(code)).resolve()
    lines, line = inspect.getsourcelines(code)
    return file, line, hashlib.sha256(''.join(lines).encode()).hexdigest()

_NATIVE_SOURCE_PATH, _, _NATIVE_WRAPPER_SHA = _span(_NATIVE_WRAPPER_CODE)
_AUTHORITY = {'profile': 'registered-native-unittest-skip-v1',
    'runtime_source': 'unittest/case.py',
    'runtime_file_sha256': hashlib.sha256(_NATIVE_SOURCE_PATH.read_bytes()).hexdigest(),
    'factory_span_sha256': _span(_NATIVE_SKIP_FACTORY_CODE)[2],
    'wrapper_span_sha256': _NATIVE_WRAPPER_SHA}
_AUTHORITY_SHA = hashlib.sha256(json.dumps(_AUTHORITY, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
_ENVIRONMENT = {'python_version': sys.version, 'implementation': sys.implementation.name,
    'cache_tag': sys.implementation.cache_tag, 'executable': sys.executable, 'platform': sys.platform,
    'environment_scope': 'python-runtime-and-import-path-only',
    'PYTHONPATH': os.environ.get('PYTHONPATH'),
    'PYTHONDONTWRITEBYTECODE': os.environ.get('PYTHONDONTWRITEBYTECODE'),
    'sys_path_before_selected_imports': list(sys.path), 'bytecode_disabled': sys.dont_write_bytecode}


def worker(root, start, pattern, namespace):
    root = Path(root).resolve()
    sys.dont_write_bytecode = True
    errors, methods, unresolved = [], [], []
    instances = []
    loader_error_count = 0
    registered = {}

    def register(wrapper, original):
        if wrapper is not original and not isinstance(original, type):
            if not isinstance(wrapper, _NATIVE_FUNCTION) or wrapper.__code__ is not _NATIVE_WRAPPER_CODE:
                raise ValueError('native skip factory returned an unexpected callable')
            registered[wrapper] = original
        return wrapper

    @functools.wraps(_NATIVE_SKIP)
    def tracked_skip(reason):
        if _NATIVE_SKIP.__code__ is not _NATIVE_SKIP_FACTORY_CODE:
            raise ValueError('native skip factory authority changed')
        if isinstance(reason, _NATIVE_FUNCTION):
            return register(_NATIVE_SKIP(reason), reason)
        decorator = _NATIVE_SKIP(reason)
        def tracked_decorator(item):
            return register(decorator(item), item)
        return tracked_decorator

    def owned_callable(bound):
        actual = bound.__func__ if isinstance(bound, _NATIVE_METHOD) else bound
        layers, seen = 0, set()
        while actual in registered:
            if id(actual) in seen:
                raise ValueError('native skip wrapper cycle')
            seen.add(id(actual))
            original = registered[actual]
            if actual.__code__ is not _NATIVE_WRAPPER_CODE or actual.__dict__.get('__wrapped__') is not original or actual.__dict__.get('__unittest_skip__') is not True:
                raise ValueError('registered native skip wrapper authority/pointer changed')
            actual = original
            layers += 1
        if not isinstance(actual, _NATIVE_FUNCTION):
            raise TypeError('test callable has no supported actual Python code object')
        if actual.__code__ is _NATIVE_WRAPPER_CODE:
            raise ValueError('unregistered native skip wrapper cannot establish original source')
        return actual, layers

    # Trusted imports may read; common process/network/filesystem writes are blocked.
    # This audit policy is not a malicious-code sandbox.
    def audit(event, args):
        if event.startswith(('subprocess.', 'socket.', 'os.exec', 'os.spawn')) or event in ('os.system', 'os.remove', 'os.rename', 'os.mkdir', 'os.rmdir'):
            raise PermissionError('discovery side effect blocked: ' + event)
        if event == 'open':
            mode, flags = args[1:3]
            if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & 3):
                raise PermissionError('discovery write blocked')
    sys.addaudithook(audit)
    loader = unittest.TestLoader()
    original_public, original_case = unittest.skip, unittest.case.skip
    unittest.skip = unittest.case.skip = tracked_skip
    try:
        suite = loader.discover(str(root/start), pattern=pattern, top_level_dir=str(root/start))
        errors.extend(loader.errors)
        loader_error_count = len(loader.errors)
        def walk(value):
            if isinstance(value, unittest.TestSuite):
                for item in value:
                    yield from walk(item)
            else:
                yield value
        instances = list(walk(suite))
        for case in instances:
            runtime_id = case.id()
            if isinstance(case, unittest.loader._FailedTest):
                message = 'failed import: ' + runtime_id
                errors.append(message)
                unresolved.append({'runtime_id': runtime_id, 'kind': 'failed-import', 'error': message})
                continue
            try:
                bound = getattr(case, case._testMethodName)
                actual, layers = owned_callable(bound)
                file, line, definition_sha = _span(actual.__code__)
                owner = Path(inspect.getfile(type(case))).resolve()
                method_skip = getattr(bound, '__unittest_skip__', False) is True
                class_skip = getattr(type(case), '__unittest_skip__', False) is True
                reason = getattr(bound, '__unittest_skip_why__', None) if method_skip else getattr(type(case), '__unittest_skip_why__', None) if class_skip else None
                if not isinstance(reason, (str, int, float, bool, type(None))):
                    reason = '<non-scalar skip reason not evaluated>'
                row = {'runtime_id': runtime_id, 'module_path': owner.relative_to(root).as_posix(),
                    'module_sha256': hashlib.sha256(owner.read_bytes()).hexdigest(),
                    'definition': {'path': file.relative_to(root).as_posix(),
                        'sha256': definition_sha, 'line': line, 'name': case._testMethodName},
                    'generated': case._testMethodName != actual.__name__,
                    'skip_declaration': {'declared': method_skip or class_skip,
                        'method': method_skip, 'class': class_skip, 'reason': reason}}
                if layers:
                    row['native_skip_wrapper'] = {'profile': _AUTHORITY['profile'],
                        'authority_sha256': _AUTHORITY_SHA, 'layers': layers}
                methods.append(row)
            except (ValueError, TypeError, OSError, AttributeError) as error:
                message = runtime_id + ': ' + str(error)
                errors.append(message)
                unresolved.append({'runtime_id': runtime_id, 'kind': 'definition-unresolved', 'error': message})
    except Exception as error:
        errors.append(type(error).__name__ + ': ' + str(error))
    finally:
        unittest.skip, unittest.case.skip = original_public, original_case
    try:
        collector_path = _TOOL_PATH.relative_to(root).as_posix()
        relationship = 'owned-source-root'
    except ValueError:
        collector_path = str(_TOOL_PATH)
        relationship = 'external-tool-override'
    return {'schema_version': 1, 'namespace': namespace, 'complete': not errors,
            'errors': errors, 'error_count': len(errors), 'loader_error_count': loader_error_count,
            'discovered_instances': len(instances), 'unresolved_instances': unresolved,
            'skipped_declarations': sum(row['skip_declaration']['declared'] for row in methods),
            'methods': methods, 'collector': {'path': collector_path, 'sha256': _TOOL_SHA,
                'source_relationship': relationship, 'definition_profile': 'actual-code-or-registered-native-skip-v1',
                'native_skip_authority': _AUTHORITY}, 'environment': _ENVIRONMENT}


def discover(root, start, *, pattern='test*.py', namespace='python-regression', timeout=30):
    proc = subprocess.run([sys.executable, '-B', str(_TOOL_PATH), '--worker',
        '--root', str(root), '--start', start, '--pattern', pattern, '--namespace', namespace],
        capture_output=True, text=True, timeout=timeout)
    if proc.returncode and not proc.stdout:
        raise ValueError('discovery worker failed: ' + proc.stderr)
    result = json.loads(proc.stdout.splitlines()[-1])
    # These are actual child-process streams, including the child's final JSON.
    result['transport'] = {'returncode': proc.returncode, 'stdout': proc.stdout, 'stderr': proc.stderr}
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True); parser.add_argument('--start', required=True)
    parser.add_argument('--pattern', default='test*.py'); parser.add_argument('--namespace', required=True,
        choices=['python-regression', 'calibration', 'maintenance', 'validation'])
    parser.add_argument('--worker', action='store_true'); args = parser.parse_args()
    result = worker(args.root, args.start, args.pattern, args.namespace) if args.worker else discover(args.root, args.start, pattern=args.pattern, namespace=args.namespace)
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result['complete'] else 1)

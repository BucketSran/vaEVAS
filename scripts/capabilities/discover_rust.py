"""Observe owned Rust test binaries through Cargo artifacts and native --list.

Listing is not test-body execution or function/AST source attribution. Cargo's
actual metadata supplies expected targets; no executable glob or prior count is
accepted. This observer is not a sandbox for malicious owned native binaries.
"""
import argparse
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from urllib.parse import unquote, urlsplit

OWNED = {'evas/rust_core/Cargo.toml': 'evas-kernel', 'evas/rust_core/ir/Cargo.toml': 'evas-ir'}
KINDS = {'bin', 'lib', 'test'}
PROFILE_ENV = ('CARGO_PROFILE_DEV_OPT_LEVEL', 'CARGO_PROFILE_DEV_DEBUG_ASSERTIONS',
               'CARGO_PROFILE_DEV_OVERFLOW_CHECKS', 'CARGO_BUILD_TARGET', 'CARGO_TARGET_DIR',
               'CARGO_ENCODED_RUSTFLAGS', 'RUSTFLAGS', 'RUSTC', 'RUSTC_WRAPPER',
               'RUSTC_WORKSPACE_WRAPPER', 'RUSTC_BOOTSTRAP', 'RUST_TEST_THREADS', 'RUST_TEST_NOCAPTURE')
METADATA_ARGV = ['cargo', '+stable', 'metadata', '--locked', '--offline', '--no-deps',
                 '--format-version=1', '--manifest-path', 'evas/rust_core/Cargo.toml']
BUILD_ARGV = ['cargo', '+stable', 'test', '--locked', '--workspace', '--no-run',
              '--message-format=json', '--manifest-path', 'evas/rust_core/Cargo.toml']


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _git(repo, *args):
    env = os.environ.copy()
    for name in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(name, None)
    run = subprocess.run(['git', '--no-optional-locks', '-C', str(repo), *args],
                         capture_output=True, env=env)
    if run.returncode:
        raise ValueError('source Git query failed: ' + run.stderr.decode(errors='replace').strip())
    return run.stdout


def _owned_path(repo, value, logical_repo):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('owned path must be absolute without parent traversal')
    # Preserve components below the selected checkout while accepting an alias
    # of the checkout root (for example macOS /var versus /private/var).
    for root in (repo, logical_repo):
        try:
            return repo / path.relative_to(root)
        except ValueError:
            pass
    # Cargo may retain a physical-root alias even when --repo is '.'. Take
    # the first checkout-root ancestor, never an inner symlink shortcut.
    for root in reversed(path.parents):
        if root.resolve() == repo:
            return repo / path.relative_to(root)
    raise ValueError('path is outside the selected checkout')


def _file(repo, path, *, executable=False):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('file path must be an absolute owned path')
    relative = path.relative_to(repo)
    current = repo
    for index, part in enumerate(relative.parts):
        current = current / part
        mode = current.lstat().st_mode
        if stat.S_ISLNK(mode) or (not stat.S_ISREG(mode) if index == len(relative.parts)-1 else not stat.S_ISDIR(mode)):
            raise ValueError('nonregular owned file path: ' + str(relative))
    before = path.stat()
    if executable and not before.st_mode & 0o111:
        raise ValueError('test artifact is not executable: ' + str(relative))
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode):
        raise ValueError('file changed during observation: ' + str(relative))
    return dict(path=relative.as_posix(), sha256=digest.hexdigest(), size=after.st_size,
                mode=stat.S_IMODE(after.st_mode))


def _source(repo):
    commit = _git(repo, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    entries = {}
    for row in _git(repo, 'ls-tree', '-r', '-z', 'HEAD', '--', 'evas/rust_core').split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, kind, oid = metadata.decode().split()
        path = os.fsdecode(name)
        if mode not in ('100644', '100755') or kind != 'blob':
            raise ValueError('unsupported owned Rust source object: ' + path)
        entries[path] = (mode, oid)
    index = {}
    for row in _git(repo, 'ls-files', '--stage', '-z', '--', 'evas/rust_core').split(b'\0'):
        if not row:
            continue
        metadata, name = row.split(b'\t', 1)
        mode, oid, stage = metadata.decode().split()
        if stage != '0':
            raise ValueError('unmerged owned source index')
        index[os.fsdecode(name)] = (mode, oid)
    if not entries or entries != index:
        raise ValueError('owned Rust source index differs from HEAD')
    files = []
    for path, (mode, oid) in sorted(entries.items()):
        value = _file(repo, repo / path)
        actual = _git(repo, 'hash-object', '--no-filters', '--', path).decode().strip()
        if actual != oid or bool(value['mode'] & 0o111) != (mode == '100755'):
            raise ValueError('owned Rust source bytes/mode differ from HEAD: ' + path)
        files.append(value)
    return dict(commit=commit, tree=_git(repo, 'rev-parse', 'HEAD^{tree}').decode().strip(),
                scope='all tracked owned Rust tree files; conservative identity, not per-test AST source',
                files=files, sha256=hashlib.sha256(_json(files).encode()).hexdigest())


def _command(argv, repo, raw, stem):
    try:
        run = subprocess.run(argv, cwd=repo, capture_output=True, timeout=60)
        code, stdout, stderr = run.returncode, run.stdout, run.stderr
    except subprocess.TimeoutExpired as error:
        code, stdout, stderr = None, error.stdout or b'', error.stderr or b''
    except OSError as error:
        code, stdout, stderr = None, b'', str(error).encode()
    out, err = raw / (stem + '.stdout.txt'), raw / (stem + '.stderr.txt')
    out.write_bytes(stdout)
    err.write_bytes(stderr)
    return dict(argv=list(map(str, argv)), cwd=str(repo), returncode=code,
                stdout=stdout.decode(errors='replace'), stderr=stderr.decode(errors='replace'),
                stdout_file=str(out), stderr_file=str(err),
                stdout_sha256=hashlib.sha256(stdout).hexdigest(), stderr_sha256=hashlib.sha256(stderr).hexdigest())


def _compact(command):
    return {key: value for key, value in command.items() if key not in ('stdout', 'stderr')}


def _ok(command, label):
    if command['returncode'] != 0:
        raise ValueError(label + ' failed; see ' + command['stderr_file'])


def parse_listing(text):
    """Parse complete native libtest list output; accept no unknown stdout rows."""
    if not isinstance(text, str) or not text.endswith('\n'):
        raise ValueError('incomplete harness listing text')
    rows, seen, summary = [], set(), None
    for line in text.splitlines():
        if not line:
            continue
        count = re.fullmatch(r'(\d+) tests?, (\d+) benchmarks?', line)
        if count:
            if summary is not None:
                raise ValueError('duplicate harness summary')
            summary = (int(count[1]), int(count[2]))
            continue
        match = re.fullmatch(r'(.+): (test|benchmark)', line)
        if summary is not None or match is None:
            raise ValueError('unknown or trailing harness output: ' + line)
        identity, kind = match.groups()
        if identity in seen or identity != identity.strip() or any(ord(c) < 32 for c in identity):
            raise ValueError('duplicate or malformed local test ID')
        seen.add(identity)
        rows.append(dict(local_id=identity, kind=kind))
    actual = (sum(row['kind'] == 'test' for row in rows), sum(row['kind'] == 'benchmark' for row in rows))
    if summary is None or summary != actual:
        raise ValueError('harness summary disagrees with actual listed IDs')
    return rows


def _targets(repo, metadata, source, logical_repo):
    if not isinstance(metadata, dict) or type(metadata.get('version')) is not int or metadata['version'] != 1:
        raise ValueError('unsupported Cargo metadata schema')
    packages = metadata.get('packages')
    members = metadata.get('workspace_members')
    if (not isinstance(packages, list) or not isinstance(members, list)
            or any(not isinstance(member, str) for member in members)
            or len(members) != len(set(members))):
        raise ValueError('incomplete Cargo workspace metadata')
    source_files = {row['path']: row for row in source['files']}
    if 'evas/rust_core/Cargo.lock' not in source_files:
        raise ValueError('owned locked workspace is missing Cargo.lock identity')
    target_dir = _owned_path(repo, metadata['target_directory'], logical_repo)
    if target_dir.resolve() != (repo / 'evas/rust_core/target').resolve():
        raise ValueError('unknown Cargo target directory outside owned build root')
    expected, owned, seen_members = {}, set(), set()
    for package in packages:
        if not isinstance(package, dict):
            raise ValueError('unknown Cargo package structure')
        if package.get('id') not in members:
            raise ValueError('unexpected package in no-dependencies workspace metadata')
        seen_members.add(package['id'])
        manifest_path = _owned_path(repo, package['manifest_path'], logical_repo)
        manifest = manifest_path.relative_to(repo).as_posix()
        if manifest not in OWNED or manifest not in source_files:
            raise ValueError('unknown workspace package/manifest')
        cargo_manifest = tomllib.loads(manifest_path.read_text())
        declared = cargo_manifest['package']
        if package['name'] != OWNED[manifest] or package['name'] != declared['name'] or package['version'] != declared['version']:
            raise ValueError('Cargo package metadata disagrees with owned manifest')
        package_id = package['id']
        uri = urlsplit(package_id)
        if (uri.scheme != 'path+file' or uri.netloc not in ('', 'localhost')
                or Path(unquote(uri.path)).resolve() != manifest_path.parent.resolve()
                or uri.fragment not in (package['version'], package['name'] + '@' + package['version'])):
            raise ValueError('unknown owned Cargo package ID')
        if manifest in owned:
            raise ValueError('duplicate owned workspace package')
        owned.add(manifest)
        if not isinstance(package.get('targets'), list):
            raise ValueError('Cargo package has no target manifest')
        for target in package['targets']:
            if not isinstance(target, dict):
                raise ValueError('unknown Cargo target structure')
            if type(target.get('test')) is not bool:
                raise ValueError('unknown target test selection')
            if not target['test']:
                continue
            kinds = target['kind']
            src = _owned_path(repo, target['src_path'], logical_repo).relative_to(repo).as_posix()
            if (not isinstance(kinds, list) or len(kinds) != 1 or kinds[0] not in KINDS
                    or src not in source_files or not src.endswith('.rs')
                    or not isinstance(target.get('name'), str) or not target['name']
                    or not src.startswith(manifest_path.parent.relative_to(repo).as_posix() + '/')
                    or target.get('required-features')):
                raise ValueError('unknown or unsupported owned test target')
            declarations = cargo_manifest.get(kinds[0], []) if kinds[0] != 'lib' else []
            if not isinstance(declarations, list) or any(not isinstance(item, dict) for item in declarations):
                raise ValueError('unknown explicit Cargo target declarations')
            explicit = cargo_manifest.get('lib', {}) if kinds[0] == 'lib' else next(
                (item for item in declarations if item.get('name') == target['name']), {})
            if not isinstance(explicit, dict) or explicit.get('harness') is False:
                raise ValueError('custom Cargo harness is outside native listing scope')
            key = (package_id, tuple(kinds), target['name'], src)
            if key in expected:
                raise ValueError('duplicate Cargo metadata target')
            expected[key] = dict(package=package['name'], version=package['version'], cargo_package_id=package_id,
                name=target['name'], target_kind=kinds, src_path=src, cargo_src_path=target['src_path'], src_sha256=source_files[src]['sha256'],
                manifest=dict(path=manifest, sha256=source_files[manifest]['sha256']),
                source_tree_sha256=source['sha256'], source_commit=source['commit'],
                lockfile_sha256=source_files['evas/rust_core/Cargo.lock']['sha256'])
    if owned != set(OWNED) or seen_members != set(members) or not expected:
        raise ValueError('missing owned packages or test targets')
    return expected, target_dir


def _artifacts(raw, build_exit, expected, repo, target_dir, logical_repo):
    if build_exit != 0:
        raise ValueError('Cargo no-run build failed with exit ' + str(build_exit))
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('incomplete Cargo JSONL stream')
    messages = [json.loads(line) for line in raw.decode().splitlines()]
    finished = [i for i, row in enumerate(messages) if isinstance(row, dict) and row.get('reason') == 'build-finished']
    if finished != [len(messages)-1] or messages[-1].get('success') is not True:
        raise ValueError('missing, duplicate or unsuccessful terminal build-finished')
    artifacts, paths = {}, set()
    for row in messages[:-1]:
        reason = row.get('reason') if isinstance(row, dict) else None
        if reason == 'compiler-message':
            diagnostic = row.get('message')
            if not isinstance(diagnostic, dict):
                raise ValueError('unknown Cargo compiler diagnostic structure')
            level = diagnostic.get('level')
            if level not in ('warning', 'note', 'help'):
                raise ValueError('compiler error or unknown diagnostic structure')
            continue
        if reason == 'build-script-executed':
            continue
        if reason != 'compiler-artifact':
            raise ValueError('unknown Cargo JSON message')
        profile = row.get('profile')
        if not isinstance(profile, dict) or type(profile.get('test')) is not bool:
            raise ValueError('unknown Cargo artifact profile')
        if not profile['test']:
            continue
        if (not isinstance(profile.get('opt_level'), str)
                or type(profile.get('debug_assertions')) is not bool
                or type(profile.get('overflow_checks')) is not bool):
            raise ValueError('incomplete effective Cargo test profile')
        for field, variable in [('opt_level', 'CARGO_PROFILE_DEV_OPT_LEVEL'),
                                ('debug_assertions', 'CARGO_PROFILE_DEV_DEBUG_ASSERTIONS'),
                                ('overflow_checks', 'CARGO_PROFILE_DEV_OVERFLOW_CHECKS')]:
            requested = os.environ.get(variable)
            actual = str(profile[field]).lower()
            if requested is not None and requested != actual:
                raise ValueError('effective Cargo profile differs from requested ' + variable)
        target = row['target']
        src = _owned_path(repo, target['src_path'], logical_repo).relative_to(repo).as_posix()
        key = (row['package_id'], tuple(target['kind']), target['name'], src)
        if key not in expected or key in artifacts:
            raise ValueError('unknown or duplicate owned test artifact')
        path = _owned_path(repo, row['executable'], logical_repo)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('unknown executable path')
        path.relative_to(target_dir)
        if str(path) in paths:
            raise ValueError('duplicate test executable')
        binary = _file(repo, path, executable=True)
        paths.add(str(path))
        artifacts[key] = dict(row=row, path=path, binary=binary)
    if set(artifacts) != set(expected):
        raise ValueError('missing owned test compiler artifacts')
    return artifacts


def discover(repo, build_messages, build_exit, raw_directory):
    """Return a complete listing or a retained failure report, never execution credit."""
    logical_repo = Path(repo).absolute()
    repo = logical_repo.resolve()
    raw = Path(raw_directory).resolve()
    raw.mkdir(parents=True, exist_ok=True)
    observer = Path(__file__).resolve()
    result = dict(schema_version=1, observation_kind='rust-test-binary-listing', complete=False,
                  listing_only=True, test_body_execution='not_observed_by_this_helper', errors=[],
                  observer=dict(path=str(observer), sha256=hashlib.sha256(observer.read_bytes()).hexdigest()),
                  environment=dict(platform=platform.platform(), machine=platform.machine(), python=sys.version,
                                   variables={name: os.environ.get(name) for name in PROFILE_ENV}),
                  ci_environment={name: os.environ.get(name) for name in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT',
                      'GITHUB_JOB', 'GITHUB_SHA', 'GITHUB_REPOSITORY', 'RUNNER_OS', 'RUNNER_ARCH')},
                  build=dict(declared_workflow_argv=BUILD_ARGV, raw_file=str(build_messages), exit=build_exit),
                  discovery_scope='owned Cargo native test executables only; no rustdoc doctest or per-function AST enumeration',
                  tests_discovered=None, ignored_tests_discovered=None, benchmarks_discovered=None,
                  toolchain={}, binaries=[], tests=[])
    try:
        result['source'] = source = _source(repo)
        build_raw = Path(build_messages).read_bytes()
        result['build']['sha256'] = hashlib.sha256(build_raw).hexdigest()
        if build_exit != 0:
            raise ValueError('Cargo no-run build failed with exit ' + str(build_exit))
        for name, argv in [('rustc', ['rustc', '+stable', '-vV']), ('cargo', ['cargo', '+stable', '--version'])]:
            info = _command(argv, repo, raw, 'tool-' + name)
            result['toolchain'][name] = info
            _ok(info, name + ' identity')
            launcher = shutil.which(name)
            if launcher is None or not info['stdout'].strip():
                raise ValueError('tool identity is missing')
            tool_path = Path(launcher).resolve()
            info['resolved_launcher'] = str(tool_path)
            info['launcher_sha256'] = hashlib.sha256(tool_path.read_bytes()).hexdigest()
            info['identity_scope'] = 'actual invoked launcher and tool version output; rustup proxy is not relabeled as compiler binary'
        command = _command(METADATA_ARGV, repo, raw, 'cargo-metadata')
        result['metadata_invocation'] = _compact(command)
        _ok(command, 'Cargo metadata')
        metadata = json.loads(Path(command['stdout_file']).read_bytes())
        expected, target_dir = _targets(repo, metadata, source, logical_repo)
        artifacts = _artifacts(build_raw, build_exit, expected, repo, target_dir, logical_repo)
        global_ids = set()
        for index, key in enumerate(sorted(expected)):
            target = expected[key]
            artifact = artifacts[key]
            binary = artifact['binary']
            stem = f'{index:02}'
            commands, listings = {}, {}
            entry = dict(target, binary_path=str(artifact['path']), binary_sha256=binary['sha256'],
                         binary_size=binary['size'], binary_availability='execution-host-only; not copied or uploaded by observer',
                         cargo_profile=artifact['row']['profile'],
                         cargo_fresh=artifact['row'].get('fresh'), listing_complete=False, listing=commands,
                         observer_sha256=result['observer']['sha256'],
                         toolchain_ref='/toolchain', environment_ref='/environment')
            result['binaries'].append(entry)
            for label, flags in [('all', ['--list']), ('ignored', ['--list', '--ignored'])]:
                info = _command([str(artifact['path']), *flags], repo, raw, stem + '-' + label)
                commands[label] = _compact(info)
                _ok(info, 'test harness ' + label + ' listing')
                listings[label] = parse_listing(Path(info['stdout_file']).read_bytes().decode())
            all_rows = {(row['local_id'], row['kind']) for row in listings['all']}
            ignored = {(row['local_id'], row['kind']) for row in listings['ignored']}
            if not ignored <= all_rows:
                raise ValueError('ignored listing is not a subset of full listing')
            if _file(repo, artifact['path'], executable=True) != binary:
                raise ValueError('test executable changed during listing')
            logical = target['package'] + '@' + target['version'] + '/' + target['target_kind'][0] + '/' + target['name']
            entry.update(listing_complete=True, tests_discovered=sum(row['kind'] == 'test' for row in listings['all']),
                         ignored_tests_discovered=sum(row['kind'] == 'test' for row in listings['ignored']))
            for row in listings['all']:
                identity = 'rust:' + logical + '::' + row['local_id']
                if identity in global_ids:
                    raise ValueError('duplicate qualified Rust listing ID')
                global_ids.add(identity)
                result['tests'].append(dict(row, id=identity, binary_index=index,
                                            ignored=(row['local_id'], row['kind']) in ignored))
        result['tests_discovered'] = sum(row['kind'] == 'test' for row in result['tests'])
        result['ignored_tests_discovered'] = sum(row['kind'] == 'test' and row['ignored'] for row in result['tests'])
        result['benchmarks_discovered'] = sum(row['kind'] == 'benchmark' for row in result['tests'])
        if not result['tests_discovered']:
            raise ValueError('zero tests across complete owned binary listing')
        if _source(repo) != source:
            raise ValueError('owned Rust inputs changed during discovery')
        result['complete'] = True
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, subprocess.SubprocessError) as error:
        result['errors'].append(str(error))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--build-messages', type=Path, required=True)
    parser.add_argument('--build-exit', type=int, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--raw-directory', type=Path, required=True)
    parser.add_argument('--require-catalog', type=Path)
    parser.add_argument('--listing-profile')
    parser.add_argument('--source-repository', action='append', default=[], metavar='NAME=PATH')
    args = parser.parse_args(argv)
    if bool(args.require_catalog) != bool(args.listing_profile):
        parser.error('--require-catalog and --listing-profile must be used together')
    if args.source_repository and not args.require_catalog:
        parser.error('--source-repository requires --require-catalog')
    repositories = {}
    for binding in args.source_repository:
        name, separator, path = binding.partition('=')
        if not separator or not name or not path or name in repositories:
            parser.error('invalid or duplicate --source-repository NAME=PATH')
        repositories[name] = Path(path)
    result = discover(args.repo, args.build_messages, args.build_exit, args.raw_directory)
    if args.require_catalog:
        result['catalog_reconciliation'] = dict(reconciled=False, errors=[])
        try:
            if not result['complete']:
                raise ValueError('cannot require an incomplete Rust listing')
            path = Path(__file__).resolve().parents[2] / 'evas/capabilities/registry.py'
            spec = importlib.util.spec_from_file_location('_rust_listing_registry', path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            catalog = module.load(args.require_catalog, root=args.repo, repositories=repositories).catalog()
            result['catalog_reconciliation'] = catalog.reconcile_rust_listing(result, profile=args.listing_profile)
        except (OSError, ValueError, TypeError, KeyError) as error:
            result['catalog_reconciliation']['errors'].append(str(error))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    summary = {key: result[key] for key in ('complete', 'listing_only', 'errors')}
    if args.require_catalog:
        summary['catalog_reconciliation'] = result['catalog_reconciliation']
    print(json.dumps(summary))
    return 0 if result['complete'] and result.get('catalog_reconciliation', {'reconciled': True})['reconciled'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

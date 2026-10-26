"""Materialize ten fixed registration-bundle blobs from one local Git commit.

This helper only copies untrusted data. The manifest selects a
commit and a repo-relative directory; it does not grant review authority,
semantic qualification, or permission to execute bundle bytes. Callers must
already have the commit locally. This tool does not fetch, and it does not
update refs or the index.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

FIXED_FILES = (
    'report.json',
    'composition_recipe',
    'snapshot_manifest',
    'dut_build',
    'kernel_binary',
    'collector_manifest',
    'artifact_manifest',
    'stdout',
    'stderr',
    'shard_reports',
)
_ALLOWED_GIT = {'rev-parse', 'ls-tree', 'cat-file'}
_COMMIT = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})')
_BLOB = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})')


def _git(repo, *args):
    if not args or args[0] not in _ALLOWED_GIT:
        raise ValueError('refusing Git command')
    env = dict(os.environ)
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['GIT_PAGER'] = 'cat'
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, env=env)
    if result.returncode:
        detail = result.stderr.decode(errors='replace').strip()
        raise ValueError(detail or 'Git read failed')
    return result.stdout


def _manifest(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict) or set(value) != {'schema_version', 'commit', 'prefix'}:
        raise ValueError('unknown or incomplete manifest schema')
    if type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('unknown manifest schema version')
    commit = value['commit']
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit) or set(commit) == {'0'}:
        raise ValueError('manifest commit must be a nonzero exact full Git commit')
    return commit, _prefix(value['prefix'])


def _prefix(prefix):
    if not isinstance(prefix, str) or not prefix or prefix.startswith(('/', '\\')):
        raise ValueError('prefix is not a canonical repo-relative directory')
    if re.search(r'[\0\n\r*?\[\]:\\]', prefix):
        raise ValueError('prefix is not a canonical repo-relative directory')
    parts = prefix.split('/')
    if any(part in ('', '.', '..') for part in parts):
        raise ValueError('prefix escapes the repository')
    return prefix


def _exact_commit(repo, commit):
    try:
        actual = _git(repo, 'rev-parse', '--verify', commit + '^{commit}').decode().strip()
        tree = _git(repo, 'rev-parse', '--verify', commit + '^{tree}').decode().strip()
    except ValueError:
        raise ValueError('manifest commit is not an available exact local commit')
    if actual != commit or not _BLOB.fullmatch(tree):
        raise ValueError('manifest commit is not an available exact local commit')
    return tree


def _regular_blob(repo, commit, path):
    entries = [item for item in _git(repo, 'ls-tree', '-z', commit, '--', path).split(b'\0') if item]
    if not entries:
        raise ValueError('missing blob: ' + path)
    if len(entries) != 1:
        raise ValueError('ambiguous blob: ' + path)
    metadata, name = entries[0].split(b'\t', 1)
    if name.decode() != path:
        raise ValueError('path escapes the repository: ' + path)
    mode, kind, blob = metadata.decode().split()
    if kind == 'tree':
        raise ValueError('path is a tree: ' + path)
    if mode == '120000':
        raise ValueError('path is a symlink: ' + path)
    if kind != 'blob' or mode not in ('100644', '100755') or not _BLOB.fullmatch(blob):
        raise ValueError('path is not a regular blob: ' + path)
    return mode, blob


def materialize(repo, manifest, output):
    """Copy the fixed ten blobs into a new directory and return their inventory."""
    repo = Path(repo)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('output path already exists')
    if not output.parent.is_dir():
        raise ValueError('output parent directory is missing')
    inventory_path = Path(str(output) + '.inventory.json')
    if inventory_path.exists() or inventory_path.is_symlink():
        raise ValueError('inventory path already exists')
    commit, prefix = _manifest(manifest)
    tree = _exact_commit(repo, commit)
    selected = []
    for name in FIXED_FILES:
        path = prefix + '/' + name
        if path != '/'.join((prefix, name)) or '..' in path.split('/'):
            raise ValueError('path escapes the repository: ' + path)
        mode, blob = _regular_blob(repo, commit, path)
        payload = _git(repo, 'cat-file', 'blob', blob)
        selected.append(dict(name=name, path=path, mode=mode, blob=blob,
                             sha256=hashlib.sha256(payload).hexdigest(),
                             byte_count=len(payload), data=payload))
    temporary = output.with_name('.materialize-' + output.name + '-' + os.urandom(4).hex())
    published = False
    try:
        temporary.mkdir()
        for item in selected:
            target = temporary / item['name']
            if target.parent != temporary:
                raise ValueError('path escapes the output directory')
            target.write_bytes(item['data'])
            os.chmod(target, 0o755 if item['mode'] == '100755' else 0o644)
        temporary.rename(output)
        published = True
    except Exception:
        if temporary.exists():
            for child in temporary.iterdir():
                child.unlink()
            temporary.rmdir()
        if published and output.exists() and not output.is_symlink():
            for child in output.iterdir():
                child.unlink()
            output.rmdir()
        raise
    inventory = dict(schema_version=1, kind='registration-bundle-materialization',
                     materialized=True, commit=commit, tree=tree, prefix=prefix,
                     output=str(output),
                     files=[dict(name=item['name'], path=item['path'], mode=item['mode'],
                                 blob=item['blob'], sha256=item['sha256'],
                                 byte_count=item['byte_count']) for item in selected])
    try:
        inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + '\n')
    except Exception:
        for child in output.iterdir():
            child.unlink()
        output.rmdir()
        raise
    return inventory


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inventory = materialize(args.repo, args.manifest, args.output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
        json.dump(dict(materialized=False, error=str(error)), sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
        return 2
    json.dump(inventory, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

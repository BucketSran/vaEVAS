"""Materialize ten fixed registration-bundle blobs from one local Git commit.

This helper only copies untrusted data. The manifest selects a
commit and a repo-relative directory; it does not grant review authority,
semantic qualification, or permission to execute bundle bytes. Callers must
already have the commit locally. This tool does not fetch, and it does not
update refs or the index.

Schema 1 copies every selected blob unchanged. Schema 2 stores only the
kernel_binary blob as one gzip member and writes that member's original
bytes; the other nine blobs stay unchanged. Byte contents are never inspected
to discover compression.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zlib

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
_SHA256 = re.compile(r'[0-9a-f]{64}')
# Read window for zlib. It is not a limit on the kernel or on declared_bytes.
_GZIP_WINDOW = 65536
_KERNEL = 'kernel_binary'


def _git(repo, *args):
    if not args or args[0] not in _ALLOWED_GIT:
        raise ValueError('refusing Git command')
    env = dict(os.environ)
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_OPTIONAL_LOCKS'] = '0'
    env['GIT_PAGER'] = 'cat'
    # Object reads in a partial clone can otherwise fetch from a promisor remote.
    # A command-line option overrides a caller's GIT_NO_LAZY_FETCH=0 preference.
    result = subprocess.run(['git', '--no-lazy-fetch', '-C', str(repo), *args],
                            capture_output=True, env=env)
    if result.returncode:
        detail = result.stderr.decode(errors='replace').strip()
        raise ValueError(detail or 'Git read failed')
    return result.stdout


def _commit(commit):
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit) or set(commit) == {'0'}:
        raise ValueError('manifest commit must be a nonzero exact full Git commit')
    return commit


def _kernel_descriptor(value):
    if not isinstance(value, dict) or set(value) != {'encoding', 'decoded_bytes', 'decoded_sha256'}:
        raise ValueError('unknown or incomplete kernel_binary descriptor')
    if value['encoding'] != 'gzip':
        raise ValueError('unknown kernel_binary encoding')
    size = value['decoded_bytes']
    if type(size) is not int or size < 1:
        raise ValueError('kernel decoded_bytes must be a positive integer')
    digest = value['decoded_sha256']
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError('kernel decoded_sha256 must be a lowercase SHA-256')
    return size, digest


def _manifest(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError('unknown or incomplete manifest schema')
    version = value.get('schema_version')
    if type(version) is not int:
        raise ValueError('unknown manifest schema version')
    if version == 1:
        if set(value) != {'schema_version', 'commit', 'prefix'}:
            raise ValueError('unknown or incomplete manifest schema')
        kernel = None
    elif version == 2:
        if set(value) != {'schema_version', 'commit', 'prefix', 'kernel_binary'}:
            raise ValueError('unknown or incomplete manifest schema')
        kernel = _kernel_descriptor(value['kernel_binary'])
    else:
        raise ValueError('unknown manifest schema version')
    return version, _commit(value['commit']), _prefix(value['prefix']), kernel


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


def _gzip_failure(error):
    detail = str(error).lower()
    if 'data check' in detail or 'length check' in detail:
        return ValueError('kernel gzip checksum does not match')
    return ValueError('kernel gzip is truncated')


def _gunzip_member(payload, declared):
    """Return one gzip member, reading at most declared + 1 decoded bytes."""
    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = bytearray()
    view = payload
    try:
        while view:
            room = declared + 1 - len(out)
            if room <= 0:
                raise ValueError('kernel gzip exceeds declared decoded_bytes')
            step = _GZIP_WINDOW if room > _GZIP_WINDOW else room
            produced = decoder.decompress(view, step)
            nxt = decoder.unconsumed_tail
            if not produced and nxt == view:
                raise ValueError('kernel gzip is truncated')
            view = nxt
            out += produced
            if decoder.unused_data:
                raise ValueError('kernel gzip has trailing data')
            if len(out) > declared:
                raise ValueError('kernel gzip exceeds declared decoded_bytes')
            if decoder.eof:
                break
    except zlib.error as error:
        raise _gzip_failure(error) from None
    if decoder.unused_data:
        raise ValueError('kernel gzip has trailing data')
    if not decoder.eof:
        raise ValueError('kernel gzip is truncated')
    if len(out) != declared:
        if len(out) > declared:
            raise ValueError('kernel gzip exceeds declared decoded_bytes')
        raise ValueError('kernel decoded length does not match the manifest')
    return bytes(out)


def _inventory_file(version, item):
    if version == 1:
        return dict(name=item['name'], path=item['path'], mode=item['mode'], blob=item['blob'],
                    sha256=item['sha256'], byte_count=item['byte_count'])
    row = dict(name=item['name'], path=item['path'], mode=item['mode'], blob=item['blob'],
               stored_sha256=item['stored_sha256'], stored_byte_count=item['stored_byte_count'],
               materialized_sha256=item['sha256'], materialized_byte_count=item['byte_count'])
    if item['name'] == _KERNEL:
        row['encoding'] = 'gzip'
    return row


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
    version, commit, prefix, kernel = _manifest(manifest)
    tree = _exact_commit(repo, commit)
    selected = []
    for name in FIXED_FILES:
        path = prefix + '/' + name
        if path != '/'.join((prefix, name)) or '..' in path.split('/'):
            raise ValueError('path escapes the repository: ' + path)
        mode, blob = _regular_blob(repo, commit, path)
        stored = _git(repo, 'cat-file', 'blob', blob)
        stored_sha = hashlib.sha256(stored).hexdigest()
        if version == 2 and name == _KERNEL:
            data = _gunzip_member(stored, kernel[0])
            file_sha = hashlib.sha256(data).hexdigest()
            if file_sha != kernel[1]:
                raise ValueError('kernel decoded sha256 does not match the manifest')
        else:
            data = stored
            file_sha = stored_sha
        selected.append(dict(name=name, path=path, mode=mode, blob=blob,
                             stored_sha256=stored_sha, stored_byte_count=len(stored),
                             sha256=file_sha, byte_count=len(data), data=data))
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
    inventory = dict(schema_version=version, kind='registration-bundle-materialization',
                     materialized=True, commit=commit, tree=tree, prefix=prefix,
                     output=str(output),
                     files=[_inventory_file(version, item) for item in selected])
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

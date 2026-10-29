"""Observe complete tracked-file facts from a worktree or a verified immutable export."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess


def _git(repository, *args):
    # Read-only commands must not refresh a real worktree's index as a side effect.
    env = os.environ.copy()
    for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE'):
        env.pop(key, None)
    try:
        return subprocess.check_output(['git', '--no-optional-locks', '-C', str(repository), *args],
                                       stderr=subprocess.PIPE, env=env)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('source Git object query failed: ' + ' '.join(args)) from error


def _regular_bytes(root, path):
    logical = PurePosixPath(path)
    if logical.is_absolute() or '..' in logical.parts or str(logical) != path:
        raise ValueError('invalid tracked relative path: ' + path)
    target = root
    try:
        for index, part in enumerate(logical.parts):
            target = target / part
            mode = target.lstat().st_mode
            if stat.S_ISLNK(mode) or (not stat.S_ISREG(mode) if index == len(logical.parts)-1 else not stat.S_ISDIR(mode)):
                raise ValueError('nonregular tracked export/checkout path: ' + path)
        before = target.stat()
        raw = target.read_bytes()
        after = target.stat()
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_mode) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_mode):
            raise ValueError('tracked file changed during observation: ' + path)
        return raw, stat.S_IMODE(after.st_mode)
    except OSError as error:
        raise ValueError('missing/unreadable tracked export/checkout path: ' + path) from error


def _blob_oid(raw, object_format):
    return hashlib.new(object_format, b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()


def _dirty_paths(raw):
    entries = raw.split(b'\0')
    paths = set()
    index = 0
    while index < len(entries):
        entry = entries[index]; index += 1
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b' ':
            raise ValueError('unknown Git status record')
        status = entry[:2]
        paths.add(os.fsdecode(entry[3:]))
        if b'R' in status or b'C' in status:
            if index >= len(entries) or not entries[index]:
                raise ValueError('incomplete Git rename/copy status')
            paths.add(os.fsdecode(entries[index])); index += 1
    return sorted(paths)


def observe(root, *, source_repository=None, source_revision=None, source_availability='local-only'):
    """Do not fetch, checkout, import code, modify a catalog, or guess a revision."""
    root = Path(root).resolve()
    if (source_repository is None) != (source_revision is None):
        raise ValueError('source_repository and source_revision must be supplied together')
    if source_availability not in ('local-only', 'published'):
        raise ValueError('unknown declared source availability')
    immutable = source_repository is not None
    repository = Path(source_repository).resolve() if immutable else root
    def git(*args):
        return _git(repository, *args)
    object_format = git('rev-parse', '--show-object-format').decode().strip()
    if object_format not in ('sha1', 'sha256'):
        raise ValueError('unsupported Git object format')
    if immutable:
        length = 40 if object_format == 'sha1' else 64
        if not isinstance(source_revision, str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}', source_revision) or set(source_revision) == {'0'}:
            raise ValueError('source_revision must be a nonzero full immutable commit OID')
        commit = git('rev-parse', '--verify', source_revision+'^{commit}').decode().strip()
        if commit != source_revision:
            raise ValueError('source_revision is not the exact declared commit')
        tree = git('rev-parse', '--verify', commit+'^{tree}').decode().strip()
        entries = git('ls-tree', '-r', '-z', '--full-tree', commit)
    else:
        if Path(os.fsdecode(git('rev-parse', '--show-toplevel')).strip()).resolve() != root:
            raise ValueError('worktree root must be the Git toplevel')
        commit = git('rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
        tree = git('rev-parse', '--verify', 'HEAD^{tree}').decode().strip()
        entries = git('ls-files', '--stage', '-z')
    rows = []
    seen = set()
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        meta, raw_path = entry.split(b'\t', 1)
        mode, middle, last = meta.decode().split()
        path = os.fsdecode(raw_path)
        if path in seen or mode not in ('100644', '100755'):
            raise ValueError('duplicate or nonregular tracked path: ' + path)
        if (immutable and middle != 'blob') or (not immutable and last != '0'):
            raise ValueError('unmerged or nonregular tracked Git entry: ' + path)
        seen.add(path)
        raw, actual_mode = _regular_bytes(root, path)
        observed_oid = _blob_oid(raw, object_format)
        row = {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(),
               'git_mode': mode, 'actual_mode': actual_mode}
        if immutable:
            if observed_oid != last:
                raise ValueError('actual export bytes differ from immutable Git blob: ' + path)
            row['git_blob_oid'] = last
        else:
            row['index_blob_oid'] = middle
            row['observed_blob_oid'] = observed_oid
        rows.append(row)
    result = {'schema_version': 1, 'producer': 'capabilities.observe-assets-v1',
        'observer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'source_commit': commit, 'source_tree': tree, 'source_object_format': object_format,
        'source_kind': 'immutable-export' if immutable else 'worktree',
        'source_profile': 'git-tree-regular-blobs-v1' if immutable else 'git-index-regular-files-v1',
        'source_availability': source_availability,
        'scope': {'kind': 'all-tracked-regular-checkout-files', 'untracked': 'excluded-explicitly'},
        'relation_to_ci_input_key': 'unproven-independent-observation', 'assets': rows}
    if immutable:
        result['content_binding'] = 'verified-git-blob-oids'
        result['source_commit_relationship'] = 'all-declared-tree-regular-blob-bytes-verified'
    else:
        result['content_binding'] = 'actual-checkout-bytes-not-commit-identity'
        result['source_commit_relationship'] = 'head-context-only'
        result['dirty_paths'] = _dirty_paths(git('status', '--porcelain=v1', '-z', '--untracked-files=no'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--source-repository', type=Path)
    parser.add_argument('--source-revision')
    parser.add_argument('--source-availability', choices=['local-only', 'published'], default='local-only',
                        help='declared availability; does not publish or fetch the commit')
    args = parser.parse_args()
    if (args.source_repository is None) != (args.source_revision is None):
        parser.error('--source-repository and --source-revision must be supplied together')
    print(json.dumps(observe(args.root, source_repository=args.source_repository,
        source_revision=args.source_revision, source_availability=args.source_availability), sort_keys=True))

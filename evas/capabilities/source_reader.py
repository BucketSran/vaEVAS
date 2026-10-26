"""Retrieve immutable source bytes; Git archives are data and are never imported."""
import hashlib
import copy
import json
from pathlib import Path, PurePosixPath
import re
import subprocess

def read_source(source, *, root=None, repositories=None):
    locator = source.get('locator')
    if locator is None:
        locator = {'kind': 'embedded', 'value': source['embedded']} if 'embedded' in source else {'kind': 'repository-relative', 'path': source.get('path')}
    kind = locator.get('kind')
    if source.get('availability') in ('pending', 'local-only', 'reference-only'):
        raise ValueError('source unavailable for portable retrieval')
    if kind == 'embedded':
        raw = json.dumps(locator['value'], ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    else:
        path = locator.get('path')
        if not isinstance(path, str) or not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or ':' in path or '\\' in path:
            raise ValueError('invalid source-relative path')
        if kind == 'repository-relative' and root is not None:
            target = (Path(root)/path).resolve()
            target.relative_to(Path(root).resolve())
            raw = target.read_bytes()
        elif kind == 'git-object':
            revision = locator.get('revision', '')
            if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', revision):
                raise ValueError('source revision must be an immutable full commit')
            repo = (repositories or {}).get(locator.get('repository'))
            if repo is None:
                raise ValueError('source repository unavailable; no fetch attempted')
            def git(*args):
                try:
                    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)
                except subprocess.SubprocessError as error:
                    raise ValueError('declared Git archive is unavailable') from error
            if git('rev-parse', '--verify', revision+'^{commit}').decode().strip() != revision:
                raise ValueError('source revision is not the declared commit')
            entry = git('ls-tree', revision, '--', path).decode().split()
            if len(entry) < 4 or entry[0] not in ('100644', '100755') or entry[1] != 'blob':
                raise ValueError('source is not a regular immutable blob')
            raw = git('show', revision+':'+path)
        else:
            raise ValueError('source unavailable or unsupported locator')
    if hashlib.sha256(raw).hexdigest() != source.get('sha256'):
        raise ValueError('source evidence bytes changed')
    return raw

def json_pointer(value, pointer):
    """RFC 6901 string form; array indices have one canonical decimal spelling."""
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('invalid JSON pointer')
    if not pointer:
        return value
    for token in pointer[1:].split('/'):
        if re.search(r'~(?:[^01]|$)', token):
            raise ValueError('invalid JSON pointer escape')
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, list):
            if not re.fullmatch(r'0|[1-9][0-9]*', token):
                raise ValueError('invalid JSON array index')
            index = int(token)
            if index >= len(value):
                raise ValueError('JSON array index out of bounds')
            value = value[index]
        elif isinstance(value, dict) and token in value:
            value = value[token]
        else:
            raise ValueError('JSON pointer does not resolve')
    return value


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


class DocumentReader:
    """Cache only immutable authenticated Git/embedded JSON, never mutable paths."""
    def __init__(self, *, root=None, repositories=None):
        self.root, self.repositories = root, repositories
        self._cache = {}

    def _document(self, source):
        kind = source.get('locator', {}).get('kind')
        immutable = kind in ('git-object', 'embedded') or ('locator' not in source and 'embedded' in source)
        key = canonical_sha(source)
        if immutable and key in self._cache:
            return self._cache[key]
        document = json.loads(read_source(source, root=self.root, repositories=self.repositories))
        if immutable:
            self._cache[key] = document
        return document

    def _bound_value(self, document, pointer, expected_sha):
        value = json_pointer(document, pointer)
        if canonical_sha(value) != expected_sha:
            raise ValueError('historical row/scope changed')
        return value

    def row(self, source, pointer, row_sha256):
        return copy.deepcopy(self._bound_value(self._document(source), pointer, row_sha256))


def historical_row(source, pointer, row_sha256, **kwargs):
    return DocumentReader(**kwargs).row(source, pointer, row_sha256)

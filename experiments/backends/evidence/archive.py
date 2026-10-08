"""Bind an already unpacked collection to a reviewed archive, without extracting."""
import hashlib
from pathlib import Path
import re
import stat
import tarfile
from typing import Iterable


def _digest(stream):
    digest = hashlib.sha256()
    size = 0
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
        size += len(chunk)
    return {'sha256': digest.hexdigest(), 'bytes': size}


def _member_path(name, *, directory=False):
    if not isinstance(name, str) or not name or '\\' in name or '\x00' in name:
        raise ValueError('invalid archive member path')
    if directory:
        name = name.rstrip('/')
    parts = name.split('/')
    if any(part in ('', '.', '..') for part in parts) or ':' in parts[0]:
        raise ValueError('unsafe archive member path: ' + name)
    return name


def _without_symlinks(path):
    for component in (*reversed(path.parents), path):
        if stat.S_ISLNK(component.lstat().st_mode):
            raise ValueError('symlink in collection path: ' + str(component))


def verify_archive_members(collection: Path, expected_sha256: str,
                           required_members: Iterable[str]) -> dict:
    """Return identities of every regular member after archive and file binding.

    expected_sha256 must come from a fixed reviewed identity, never COLLECTION.
    Directory entries carry no payload; all other nonregular types are rejected.
    required_members must be nonempty and name regular archived files.
    The collection must remain stable while this read-only check runs.
    """
    if not isinstance(expected_sha256, str) or not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise ValueError('expected archive SHA256 must be a reviewed lowercase hex digest')
    if isinstance(required_members, (str, bytes)):
        raise ValueError('required members must be a nonempty collection of paths')
    try:
        required = {_member_path(name) for name in required_members}
    except TypeError as error:
        raise ValueError('required members must be a nonempty collection of paths') from error
    if not required:
        raise ValueError('required archive members cannot be empty')
    collection = Path(collection).absolute()
    archive_path = collection / 'raw.tar.gz'
    result, seen = {}, set()
    try:
        _without_symlinks(archive_path)
        if not stat.S_ISREG(archive_path.stat().st_mode):
            raise ValueError('archive must be a regular file')
        with archive_path.open('rb') as archive_stream:
            if _digest(archive_stream)['sha256'] != expected_sha256:
                raise ValueError('archive SHA256 differs from reviewed identity')
            archive_stream.seek(0)
            with tarfile.open(fileobj=archive_stream, mode='r:*') as archive:
                for member in archive:
                    name = _member_path(member.name, directory=member.isdir())
                    if name in seen:
                        raise ValueError('duplicate archive member: ' + name)
                    seen.add(name)
                    if member.type not in (tarfile.REGTYPE, tarfile.AREGTYPE, tarfile.DIRTYPE):
                        raise ValueError('nonregular archive payload: ' + name)
                    path = collection / name
                    _without_symlinks(path)
                    mode = path.stat().st_mode
                    if member.isdir():
                        if member.size != 0 or not stat.S_ISDIR(mode):
                            raise ValueError('invalid archived directory: ' + name)
                        continue
                    if not stat.S_ISREG(mode):
                        raise ValueError('unpacked member is not a regular file: ' + name)
                    with archive.extractfile(member) as stream:
                        identity = _digest(stream)
                    if identity['bytes'] != member.size:
                        raise ValueError('truncated archive payload: ' + name)
                    with path.open('rb') as stream:
                        if _digest(stream) != identity:
                            raise ValueError('unpacked member differs from archive: ' + name)
                    result[name] = identity
        if not result:
            raise ValueError('archive has no regular payload')
        if not required <= result.keys():
            raise ValueError('required regular archive members missing: ' + ', '.join(sorted(required - result.keys())))
        return result
    except (OSError, EOFError, tarfile.TarError) as error:
        raise ValueError('invalid or incomplete archived collection: ' + str(error)) from error

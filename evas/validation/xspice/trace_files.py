"""Lossless retention and transparent reads for the optional large CSV traces."""

import gzip
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
import shutil


@contextmanager
def retained_traces(directory):
    """Retain traces after success, rejected runs, timeouts or grading errors."""
    try:
        yield
    finally:
        compress_traces(directory)


def open_trace(path):
    path = Path(path)
    if path.exists():
        return path.open()
    # Trace aliases may point at an already compressed original.
    compressed = Path(str(path.resolve()) + ".gz")
    return gzip.open(compressed, "rt")


def digest(stream):
    result = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
        result.update(chunk)
    return result.hexdigest()


def compress_traces(directory):
    directory = Path(directory)
    rows = []
    for path in sorted(directory.glob("trace*.csv")):
        if path.is_symlink():
            continue
        with path.open("rb") as stream:
            identity = digest(stream)
        temporary = Path(str(path) + ".gz.part")
        compressed = Path(str(path) + ".gz")
        if compressed.exists():
            raise FileExistsError(compressed)
        with path.open("rb") as source, gzip.open(temporary, "xb", compresslevel=6) as target:
            shutil.copyfileobj(source, target)
        with gzip.open(temporary, "rb") as stream:
            if digest(stream) != identity:
                raise RuntimeError("compressed trace identity differs: " + str(path))
        size = path.stat().st_size
        temporary.rename(compressed)
        path.unlink()
        rows.append({"original": path.name, "compressed": compressed.name,
                     "uncompressed_sha256": identity, "uncompressed_bytes": size,
                     "compressed_bytes": compressed.stat().st_size})
    if rows:
        (directory / "trace-retention.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows

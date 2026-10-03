"""Semantics-blind normalization for one unambiguous submission prefix."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
from typing import Any


def _safe_relative(raw: str) -> Path:
    path = Path(raw.replace("\\", "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path: {raw!r}")
    return path


def _prefix_for(relative: Path, expected: Path) -> Path | None:
    if len(relative.parts) <= len(expected.parts):
        return None
    if relative.parts[-len(expected.parts):] != expected.parts:
        return None
    return Path(*relative.parts[:-len(expected.parts)])


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_submission_layout(
    submission: Path, expected_raw: list[str]
) -> dict[str, Any] | None:
    """Copy one complete common-prefix bundle to its declared relative paths.

    Selection uses paths only. It rejects partial bundles, symlinks, duplicate
    target copies, and more than one viable prefix; file contents are never
    inspected beyond hashing the selected bytes for the audit record.
    """
    expected = [_safe_relative(item) for item in expected_raw]
    if not expected or len({item.as_posix() for item in expected}) != len(expected):
        return None
    if all((submission / item).is_file() for item in expected):
        return None

    files = [path for path in sorted(submission.rglob("*")) if path.is_file()]
    if any(path.is_symlink() for path in files):
        return None
    groups: dict[str, dict[str, list[Path]]] = {}
    competing: set[Path] = set()
    for path in files:
        relative = path.relative_to(submission)
        for target in expected:
            prefix = _prefix_for(relative, target)
            if prefix is None:
                continue
            competing.add(path)
            groups.setdefault(prefix.as_posix(), {}).setdefault(target.as_posix(), []).append(path)

    viable: list[tuple[str, dict[str, Path]]] = []
    expected_names = {item.as_posix() for item in expected}
    for prefix, by_target in groups.items():
        if set(by_target) != expected_names or any(len(paths) != 1 for paths in by_target.values()):
            continue
        viable.append((prefix, {target: paths[0] for target, paths in by_target.items()}))
    if len(viable) != 1:
        return None
    prefix, selected = viable[0]
    if competing != set(selected.values()):
        return None

    artifacts = []
    for target_name in sorted(selected):
        source = selected[target_name]
        target = submission / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        artifacts.append({
            "source": source.relative_to(submission).as_posix(),
            "target": target_name,
            "sha256": _sha256(target),
        })
    return {
        "schema_version": "v4-submission-layout-normalization-v1",
        "normalization": "unique_common_prefix",
        "stripped_prefix": prefix,
        "artifacts": artifacts,
    }

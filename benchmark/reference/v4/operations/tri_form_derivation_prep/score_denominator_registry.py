#!/usr/bin/env python3
"""Validate and read the family-sharded V4 score denominator registry."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REGISTRY_DIRNAME = "score_denominator_registry"
META_FILENAME = "_meta.json"
FAMILY_SCHEMA = "v4-score-denominator-family-registry-v1"


class RegistryError(ValueError):
    """Raised when the registry is incomplete or internally inconsistent."""


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def registry_dir(source: Path) -> Path:
    return source / REGISTRY_DIRNAME


def family_path(source: Path, family: str) -> Path:
    return registry_dir(source) / f"{int(family):03d}.json"


def expected_family_ids(meta: dict[str, Any]) -> list[str]:
    canonical_range = meta.get("canonical_range") or []
    if len(canonical_range) != 2:
        raise RegistryError("registry metadata must declare a two-value canonical_range")
    start, end = (int(value) for value in canonical_range)
    if start > end:
        raise RegistryError("registry metadata canonical_range is descending")
    return [f"{value:03d}" for value in range(start, end + 1)]


def load_family_row(source: Path, family: str) -> dict[str, Any]:
    family = f"{int(family):03d}"
    path = family_path(source, family)
    if not path.is_file():
        raise RegistryError(f"missing family registry: {path}")
    shard = read_json(path)
    if shard.get("schema_version") != FAMILY_SCHEMA:
        raise RegistryError(f"{path}: unsupported schema_version")
    if str(shard.get("family_id") or "") != family:
        raise RegistryError(f"{path}: family_id does not match filename")
    row = shard.get("task")
    if not isinstance(row, dict):
        raise RegistryError(f"{path}: task must be an object")
    if str(row.get("canonical_dut_id") or "") != family:
        raise RegistryError(f"{path}: task canonical_dut_id does not match shard")
    return row


def write_family_row(source: Path, family: str, row: dict[str, Any]) -> None:
    family = f"{int(family):03d}"
    if str(row.get("canonical_dut_id") or "") != family:
        raise RegistryError(f"family {family}: task canonical_dut_id mismatch")
    write_json(
        family_path(source, family),
        {"schema_version": FAMILY_SCHEMA, "family_id": family, "task": row},
    )


def load_registry_metadata(source: Path) -> dict[str, Any]:
    directory = registry_dir(source)
    meta_path = directory / META_FILENAME
    if not meta_path.is_file():
        raise RegistryError(f"missing registry metadata: {meta_path}")
    meta = read_json(meta_path)
    if "tasks" in meta or "content_sha256" in meta:
        raise RegistryError("registry metadata must not contain generated manifest fields")
    expected = expected_family_ids(meta)
    actual = sorted(path.stem for path in directory.glob("[0-9][0-9][0-9].json"))
    if actual != expected:
        missing = sorted(set(expected) - set(actual))
        extra = sorted(set(actual) - set(expected))
        raise RegistryError(f"registry family coverage mismatch: missing={missing} extra={extra}")
    if int(meta.get("counted_task_count") or -1) != len(expected):
        raise RegistryError("registry counted_task_count does not match family coverage")
    return meta


def load_family_rows(source: Path) -> list[dict[str, Any]]:
    meta = load_registry_metadata(source)
    return [load_family_row(source, family) for family in expected_family_ids(meta)]


def score_denominator_registry_sha256(source: Path) -> str:
    """Hash metadata and shard bytes without constructing an aggregate table."""
    meta = load_registry_metadata(source)
    paths = [registry_dir(source) / META_FILENAME]
    paths.extend(family_path(source, family) for family in expected_family_ids(meta))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.expanduser().resolve()
    rows = load_family_rows(source)
    print(json.dumps({
        "status": "PASS",
        "family_count": len(rows),
        "registry_sha256": score_denominator_registry_sha256(source),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

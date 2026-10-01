"""Recompile manifest-owned Verilog-A sources into the current EVAS IR.

Old IR JSON is intentionally not rewritten in place.  Migration starts from the
original circuit manifest and source text, then records enough provenance to make
the new IR identity reviewable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Mapping, Sequence

from .frontend import CompileError, Instance, compile_sources


MANIFEST_FIELDS = {"models", "instances", "driven", "samples", "tolerances", "transient"}


class _TextDecodeError(ValueError):
    def __init__(self, digest: str, message: str):
        super().__init__(message)
        self.digest = digest


@dataclass(frozen=True)
class RecompileResult:
    manifest: str
    manifest_sha256: str
    source_sha256: Mapping[str, str]
    status: str
    output: str | None = None
    schema_version: int | None = None
    diagnostic: str | None = None


@dataclass(frozen=True)
class RecompileBatch:
    ok: bool
    output_dir: str
    results: tuple[RecompileResult, ...]

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "output_dir": self.output_dir,
            "results": [asdict(result) for result in self.results],
        }


def sha256_file(path: Path) -> str:
    return _read_text_with_hash(path)[0]


def discover_manifests(inputs: Sequence[Path] | None = None, *, repo_root: Path | None = None) -> tuple[Path, ...]:
    root = (repo_root or Path.cwd()).resolve()
    selected = inputs or (root / "evas/examples",)
    manifests: list[Path] = []
    for item in selected:
        path = item if item.is_absolute() else root / item
        path = path.resolve()
        if path.is_dir():
            manifests.extend(sorted(path.rglob("*.json")))
        elif path.is_file():
            manifests.append(path)
        else:
            raise FileNotFoundError(str(item))
    return tuple(dict.fromkeys(manifests))


def recompile_manifest(manifest_path: Path, output_path: Path, *, repo_root: Path | None = None) -> RecompileResult:
    root = (repo_root or Path.cwd()).resolve()
    manifest_path = manifest_path.resolve()
    manifest_label = _display_path(manifest_path, root)
    manifest_hash = ""
    source_hashes: dict[str, str] = {}
    try:
        try:
            manifest_hash, manifest_text = _read_text_with_hash(manifest_path)
        except _TextDecodeError as exc:
            manifest_hash = exc.digest
            raise ValueError(str(exc)) from exc
        manifest = json.loads(manifest_text)
        if not isinstance(manifest, dict):
            raise ValueError("manifest root must be a JSON object")
        unknown = set(manifest) - MANIFEST_FIELDS
        if unknown:
            raise ValueError(f"unknown manifest fields: {sorted(unknown)}")
        if "models" not in manifest or "instances" not in manifest:
            raise KeyError("models and instances are required")
        model_paths = []
        for declared in manifest["models"]:
            if not isinstance(declared, str):
                raise TypeError("model paths must be strings")
            model_paths.append((declared, (manifest_path.parent / declared).resolve()))
        sources = {}
        for declared, source_path in model_paths:
            try:
                source_hashes[declared], sources[str(source_path)] = _read_text_with_hash(source_path)
            except _TextDecodeError as exc:
                source_hashes[declared] = exc.digest
                raise ValueError(str(exc)) from exc
        program = compile_sources(sources, [Instance(**instance) for instance in manifest["instances"]])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = program.to_dict()
        with output_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")
        return RecompileResult(
            manifest=manifest_label,
            manifest_sha256=manifest_hash,
            source_sha256=source_hashes,
            status="success",
            output=_display_path(output_path.resolve(), root),
            schema_version=payload["schema_version"],
        )
    except (CompileError, OSError, ValueError, KeyError, TypeError) as exc:
        return RecompileResult(
            manifest=manifest_label,
            manifest_sha256=manifest_hash,
            source_sha256=source_hashes,
            status="failure",
            diagnostic=str(exc),
        )


def recompile_manifests(
    inputs: Sequence[Path] | None,
    output_dir: Path,
    *,
    repo_root: Path | None = None,
) -> RecompileBatch:
    root = (repo_root or Path.cwd()).resolve()
    output_dir = output_dir if output_dir.is_absolute() else root / output_dir
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing output directory: {output_dir}")
    manifests = discover_manifests(inputs, repo_root=root)
    output_dir.mkdir(parents=True)
    if not manifests:
        batch = RecompileBatch(
            ok=False,
            output_dir=_display_path(output_dir, root),
            results=(RecompileResult("<batch>", "", {}, "failure", diagnostic="no manifests selected"),),
        )
        (output_dir / "summary.json").write_text(json.dumps(batch.to_dict(), indent=2, sort_keys=True) + "\n")
        return batch
    results = []
    for manifest in manifests:
        rel = _output_relative_path(manifest, root).with_suffix(".ir.json")
        results.append(recompile_manifest(manifest, output_dir / rel, repo_root=root))
    batch = RecompileBatch(
        ok=all(result.status == "success" for result in results),
        output_dir=_display_path(output_dir, root),
        results=tuple(results),
    )
    (output_dir / "summary.json").write_text(json.dumps(batch.to_dict(), indent=2, sort_keys=True) + "\n")
    return batch


def _display_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _relative_or_name(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(_path_digest(path)) / path.name


def _output_relative_path(path: Path, root: Path) -> Path:
    return _relative_or_name(path, root)


def _path_digest(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:16]


def _read_text_with_hash(path: Path) -> tuple[str, str]:
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    try:
        return digest, data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _TextDecodeError(digest, str(exc)) from exc

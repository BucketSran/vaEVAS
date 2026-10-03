#!/usr/bin/env python3
"""Audit assigned v4 profile parity under the EVAS2 evidence environment.

This is a static smoke (no simulator invocation).  It still requires the same
explicit EVAS2 environment as executable evidence so a combined batch report
cannot accidentally mix Python-engine and Rust-engine runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
DEFAULT_RELEASE = ROOT / "release" / "benchmarkv4-r53"
DEFAULT_RELEASE_REVISION = "r53"
FORMS = ("dut", "testbench", "bugfix")
REQUIRED_EVAS_ENGINE = "evas2"
REQUIRED_EVAS_VERSION = "0.8.7"
LEGACY_EVAS_VERSION = "0.8.3"
RUST_EVAS_LOG_ENGINE = "evas-rust"
SUPPORTED_RELEASE_REVISIONS = ("r44", "r45", "r47", "r48", "r49", "r50", "r51", "r52", "r53")
EVAS_VERSION_BY_RELEASE = {
    "r52": "0.8.5",
    "r53": REQUIRED_EVAS_VERSION,
}

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "operations" / "tri_form_derivation_prep"))

from run_v4_reference_evas_smoke import (  # noqa: E402
    probe_evas2_runtime,
    require_evas2_environment,
)
from score_denominator_registry import score_denominator_registry_sha256  # noqa: E402
import render_v4_harness  # noqa: E402


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_provenance(release: Path, release_revision: str) -> dict[str, str]:
    manifest_path = release / "MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit(f"release manifest is missing: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("release_revision") != release_revision:
        raise SystemExit(
            "release manifest revision does not match --release-revision: "
            f"declared={manifest.get('release_revision')!r} selected={release_revision!r}"
        )
    source_registry_sha = str(
        manifest.get("source_score_denominator_registry_sha256") or ""
    )
    if re.fullmatch(r"[0-9a-f]{64}", source_registry_sha) is None:
        raise SystemExit("release manifest lacks a valid source denominator binding")
    if int(release_revision.removeprefix("r")) >= 47:
        current_source_sha = score_denominator_registry_sha256(SOURCE_ROOT)
        if source_registry_sha != current_source_sha:
            raise SystemExit("release manifest is not bound to the current source denominator")
    return {
        "source_score_denominator_registry_sha256": source_registry_sha,
        "release_manifest_sha256": file_sha(manifest_path),
    }


def canonical_payload(spec: dict[str, Any]) -> dict[str, Any]:
    deck = spec.get("deck") or {}
    defaults = spec.get("profile_defaults") or {}
    return {
        "deck": {
            key: deck.get(key)
            for key in ("header", "include_templates", "body_lines", "analyses", "save_signals")
        },
        "profile_parameters": {
            profile: {
                "parameters": (defaults.get(profile) or {}).get("parameters"),
                "corners": (defaults.get(profile) or {}).get("corners", []),
            }
            for profile in ("feedback", "score")
        },
        "property_ids": spec.get("property_ids") or [],
    }


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def release_label(revision: str) -> str:
    if revision == "r44":
        return "release/benchmarkv4"
    return f"release/benchmarkv4-{revision}"

def required_evas_version(revision: str) -> str:
    return EVAS_VERSION_BY_RELEASE.get(revision, LEGACY_EVAS_VERSION)


def source_family(family_id: str) -> Path:
    matches = sorted(SOURCE_ROOT.glob(f"{family_id}-*/evaluator/harness_spec.json"))
    if len(matches) != 1:
        raise SystemExit(f"expected one source harness for family {family_id}, found {len(matches)}")
    return matches[0].parent.parent


def parse_range(value: str) -> tuple[int, int]:
    left, separator, right = value.partition("-")
    if not separator:
        right = left
    start, stop = int(left), int(right)
    if start < 1 or stop < start or stop > 400:
        raise argparse.ArgumentTypeError(f"invalid family range: {value}")
    return start, stop


def release_rows(
    release: Path,
    task_ids: list[str] | None,
    family_range: tuple[int, int],
) -> list[dict[str, Any]]:
    index = read_json(release / "TASK_INDEX.json")
    wanted = set(task_ids or [])
    start, stop = family_range
    families = {f"{value:03d}" for value in range(start, stop + 1)}
    rows = [
        row
        for row in index.get("tasks") or []
        if str(row.get("family_id")) in families
        and str(row.get("form")) in FORMS
        and (not wanted or str(row.get("task_id")) in wanted)
    ]
    rows.sort(key=lambda row: (int(str(row["family_id"])), FORMS.index(str(row["form"]))))
    expected = (stop - start + 1) * len(FORMS)
    if len(rows) != expected:
        raise SystemExit(f"expected {expected} assigned release tasks, found {len(rows)}")
    return rows


def audit_row(
    release: Path, row: dict[str, Any], *, evas_version: str = REQUIRED_EVAS_VERSION
) -> dict[str, Any]:
    family_id = str(row["family_id"])
    task_id = str(row["task_id"])
    task_dir = release / str(row["task_dir"])
    source = source_family(family_id)
    source_spec = read_json(source / "evaluator" / "harness_spec.json")
    release_spec = read_json(task_dir / "evaluator" / "harness_spec.json")
    expected = canonical_payload(source_spec)
    observed = canonical_payload(release_spec)
    errors: list[str] = []
    try:
        render_v4_harness.validate_profile_semantics(release_spec)
        render_v4_harness.validate_profile_semantic_parity(release_spec)
    except ValueError as exc:
        errors.append(str(exc))
    if expected != observed:
        errors.append("canonical_semantics_mismatch")
    for profile in ("feedback", "score"):
        profile_path = task_dir / "evaluator" / "profiles" / f"{profile}.json"
        profile_data = read_json(profile_path)
        source_profile = (source_spec.get("profile_defaults") or {}).get(profile) or {}
        if profile_data.get("deck_overrides"):
            errors.append(f"{profile}:semantic_deck_overrides_present")
        if (profile_data.get("parameters") or {}) != (source_profile.get("parameters") or {}):
            errors.append(f"{profile}:parameters_mismatch")
        if (profile_data.get("corners") or []) != (source_profile.get("corners") or []):
            errors.append(f"{profile}:corners_mismatch")
        if profile_data.get("property_ids") != source_spec.get("property_ids"):
            errors.append(f"{profile}:property_ids_mismatch")
    return {
        "task_id": task_id,
        "family_id": family_id,
        "form": row["form"],
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "source_semantic_sha256": digest(expected),
        "release_semantic_sha256": digest(observed),
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": evas_version,
        "evas_backend_required": RUST_EVAS_LOG_ENGINE,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument(
        "--release-revision",
        choices=SUPPORTED_RELEASE_REVISIONS,
        default=DEFAULT_RELEASE_REVISION,
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--task-id", action="append")
    parser.add_argument("--family-range", type=parse_range, default=(1, 400))
    args = parser.parse_args()
    require_evas2_environment()
    evas_version = required_evas_version(args.release_revision)
    runtime = probe_evas2_runtime(required_evas_version=evas_version)
    release = args.release.expanduser().resolve()
    provenance = release_provenance(release, args.release_revision)
    rows = [
        audit_row(release, row, evas_version=evas_version)
        for row in release_rows(release, args.task_id, args.family_range)
    ]
    report = {
        "schema_version": "v4-profile-parity-evas2-smoke-v1",
        "release": release_label(args.release_revision),
        "release_revision": args.release_revision,
        **provenance,
        "family_range": f"{args.family_range[0]:03d}-{args.family_range[1]:03d}",
        "simulation_performed": False,
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": evas_version,
        "evas_backend_required": RUST_EVAS_LOG_ENGINE,
        "runtime": runtime,
        "task_count": len(rows),
        "pass_count": sum(row["status"] == "pass" for row in rows),
        "fail_count": sum(row["status"] != "pass" for row in rows),
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "results": rows,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("schema_version", "status", "task_count", "pass_count", "fail_count")}, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

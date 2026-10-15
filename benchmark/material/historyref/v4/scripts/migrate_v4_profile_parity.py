#!/usr/bin/env python3
"""Canonicalize feedback/score harnesses for a selected V4 family batch.

The public feedback deck is the source of stimulus semantics.  This script
updates only the canonical provenance package and regenerates profiles/decks
through ``render_v4_harness.py``; it never edits ``release/benchmarkv4``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from render_v4_harness import build_profile, render_scs  # noqa: E402


ROOT = SCRIPT_DIR.parent
PREP_DIR = ROOT / "operations" / "tri_form_derivation_prep"
if str(PREP_DIR) not in sys.path:
    sys.path.insert(0, str(PREP_DIR))

from score_denominator_registry import load_family_row, write_family_row  # noqa: E402

DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def family_dir(source: Path, family: str) -> Path:
    matches = sorted(source.glob(f"{family}-*"))
    if len(matches) != 1:
        raise ValueError(f"family {family}: expected one source directory, found {len(matches)}")
    return matches[0]


def parse_family_ids(values: list[str], ranges: list[str]) -> list[str]:
    ids = {f"{int(value):03d}" for value in values}
    for item in ranges:
        try:
            start, end = (int(part) for part in item.split("-", 1))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid family range: {item}") from exc
        if start > end:
            raise ValueError(f"invalid descending family range: {item}")
        ids.update(f"{value:03d}" for value in range(start, end + 1))
    return sorted(ids, key=int)


def parse_feedback_deck(path: Path) -> tuple[list[str], list[str], list[str]]:
    """Extract body, analyses, and saved traces from the public deck."""
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines()]
    include_indices = [index for index, line in enumerate(lines) if line.strip().startswith("ahdl_include ")]
    if not include_indices:
        raise ValueError(f"{path}: no ahdl_include line")
    body_start = include_indices[-1] + 1
    control_starts = ("simulatorOptions ", "tran ", "save ")
    body_end = len(lines)
    for index in range(body_start, len(lines)):
        if lines[index].strip().startswith(control_starts):
            body_end = index
            break
    body = [line.strip() for line in lines[body_start:body_end] if line.strip()]
    analyses = [line.strip() for line in lines if line.strip().startswith("tran ")]
    save_signals: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("save "):
            save_signals.extend(stripped.split()[1:])
    if not body or not analyses or not save_signals:
        raise ValueError(f"{path}: feedback deck lacks body, analyses, or save signals")
    return body, analyses, save_signals


def update_task_record(task: Path) -> None:
    evaluator = task / "evaluator"
    public = task / "public" / "task"
    record_path = evaluator / "task_record.json"
    record = read_json(record_path)
    evaluator_hashes = record.setdefault("evaluator_hashes", {})
    for relative in tuple(evaluator_hashes):
        path = evaluator / relative
        if path.is_file():
            evaluator_hashes[relative] = file_sha(path)
    for relative in ("harness_spec.json", "profiles/feedback.json", "profiles/score.json", "score_tb.scs"):
        evaluator_hashes[relative] = file_sha(evaluator / relative)
    readiness = record.get("readiness_evidence")
    if isinstance(readiness, dict):
        relative = readiness.get("path")
        if isinstance(relative, str) and (task / relative).is_file():
            readiness["sha256"] = file_sha(task / relative)
    public_hashes = record.setdefault("public_hashes", {})
    for relative in tuple(public_hashes):
        path = public / relative
        if path.is_file():
            public_hashes[relative] = file_sha(path)
    public_hashes["feedback_tb.scs"] = file_sha(public / "feedback_tb.scs")
    write_json(record_path, record)


def update_denominator(source: Path, families: set[str]) -> None:
    for family in sorted(families):
        row = load_family_row(source, family)
        task = source / str(row["release_dir"])
        evaluator = task / "evaluator"
        row.setdefault("hashes", {})["task_record_sha256"] = file_sha(evaluator / "task_record.json")
        row["hashes"]["score_deck_sha256"] = file_sha(evaluator / "score_tb.scs")
        row["hashes"]["mutation_catalog_sha256"] = file_sha(evaluator / "mutation_catalog.json")
        write_family_row(source, family, row)


def migrate_family(source: Path, family: str) -> dict[str, Any]:
    task = family_dir(source, family)
    evaluator = task / "evaluator"
    public = task / "public" / "task"
    spec_path = evaluator / "harness_spec.json"
    spec = read_json(spec_path)
    old_spec_sha = file_sha(spec_path)
    body, analyses, save_signals = parse_feedback_deck(public / "feedback_tb.scs")
    spec["deck"]["body_lines"] = body
    spec["deck"]["analyses"] = analyses
    spec["deck"]["save_signals"] = save_signals
    spec["profile_defaults"] = {
        "feedback": {"simulatorOptions": {"evas_profile": "balanced"}},
        "score": {},
    }
    note = "feedback deck is the canonical stimulus; score is generated with identical semantics"
    notes = spec.setdefault("migration", {}).setdefault("notes", [])
    if note not in notes:
        notes.append(note)
    write_json(spec_path, spec)
    spec_sha = file_sha(spec_path)
    rendered: dict[str, str] = {}
    for profile_name in ("feedback", "score"):
        profile = build_profile(spec, profile_name, spec_sha)
        profile_path = evaluator / "profiles" / f"{profile_name}.json"
        write_json(profile_path, profile)
        deck = render_scs(spec, profile)
        output = public / "feedback_tb.scs" if profile_name == "feedback" else evaluator / "score_tb.scs"
        output.write_text(deck, encoding="utf-8")
        rendered[profile_name] = file_sha(output)
    reference = evaluator / "reference_tb.scs"
    if reference.is_file():
        reference.write_text((public / "feedback_tb.scs").read_text(encoding="utf-8"), encoding="utf-8")
    update_task_record(task)
    return {
        "family_id": family,
        "task": task.name,
        "old_harness_spec_sha256": old_spec_sha,
        "new_harness_spec_sha256": spec_sha,
        "feedback_deck_sha256": rendered["feedback"],
        "score_deck_sha256": rendered["score"],
        "reference_regenerated": reference.is_file(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--family-range", action="append", default=[])
    args = parser.parse_args()
    families = parse_family_ids(args.family, args.family_range)
    if not families:
        raise SystemExit("select at least one family with --family or --family-range")
    source = args.source_root.expanduser().resolve()
    changes = [migrate_family(source, family) for family in families]
    update_denominator(source, set(families))
    print(json.dumps({"status": "MIGRATED", "families": changes}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

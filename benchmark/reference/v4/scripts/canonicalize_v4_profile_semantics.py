#!/usr/bin/env python3
"""Migrate selected V4 harnesses to one feedback/score semantic source.

The score profile is used as the canonical stimulus for this migration. EVAS
feedback retains only backend options such as ``evas_profile=balanced``; it no
longer carries a second waveform, stop time, or parameter set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from render_v4_harness import (
    effective_profile_semantics,
    validate_profile_semantic_parity,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def score_deck_semantics(source_task: Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Use the checked-in score deck as the canonical rendered stimulus.

    A few legacy specs had incomplete profile body lines even though their
    score deck contained the complete reference stimulus. Keeping the score
    deck as the source of truth avoids dropping input clocks during migration.
    """
    score_tb = source_task / "evaluator" / "score_tb.scs"
    lines = score_tb.read_text(encoding="utf-8").splitlines()
    include_indexes = [
        index for index, line in enumerate(lines) if line.strip().startswith("ahdl_include ")
    ]
    analysis_indexes = [
        index for index, line in enumerate(lines) if line.strip().startswith("tran ")
    ]
    if not include_indexes or not analysis_indexes:
        raise ValueError(f"{score_tb}: cannot locate includes and transient analysis")
    first_analysis = min(analysis_indexes)
    body = lines[max(include_indexes) + 1 : first_analysis]
    while body and not body[0].strip():
        body.pop(0)
    while body and not body[-1].strip():
        body.pop()
    analyses = [lines[index].strip() for index in analysis_indexes]
    save_signals: list[str] = []
    for line in lines[first_analysis + 1 :]:
        stripped = line.strip()
        if not stripped.startswith("save "):
            continue
        save_signals.extend(stripped.split()[1:])
    if not save_signals:
        save_signals = list(spec["deck"].get("save_signals") or [])
    return {"body_lines": body, "analyses": analyses, "save_signals": save_signals}


def canonicalize(path: Path) -> bool:
    spec = read_json(path)
    source_task = path.parent.parent
    score = effective_profile_semantics(spec, "score")
    score.update(score_deck_semantics(source_task, spec))
    deck = spec["deck"]
    changed = False

    for key in ("body_lines", "analyses", "save_signals"):
        if deck.get(key) != score[key]:
            deck[key] = score[key]
            changed = True

    defaults = spec["profile_defaults"]
    for profile_name in ("feedback", "score"):
        original = defaults[profile_name]
        migrated: dict[str, Any] = {
            "parameters": score["parameters"],
            "corners": score["corners"],
            "deterministic_seed": score["deterministic_seed"],
        }
        simulator_options = dict(original.get("simulatorOptions") or {})
        if simulator_options:
            migrated["simulatorOptions"] = simulator_options
        if original != migrated:
            defaults[profile_name] = migrated
            changed = True

    migration = dict(spec.get("migration") or {})
    notes = list(migration.get("notes") or [])
    note = (
        "feedback and score now derive identical stimulus, analysis, trace, "
        "parameter, corner, and deterministic-seed semantics from the canonical deck"
    )
    if note not in notes:
        notes.append(note)
        migration["notes"] = notes
        spec["migration"] = migration
        changed = True

    # The provenance tree uses ``public/task/feedback_tb.scs`` as its public
    # feedback deck.  Keep the checker contract's shared-deck declaration
    # aligned with that generated layout instead of the retired legacy path.
    checker_path = source_task / "evaluator" / "checker_profile.json"
    if checker_path.is_file():
        checker = read_json(checker_path)
        shared_by = ["public/task/feedback_tb.scs", "evaluator/score_tb.scs"]
        if checker.get("shared_by") != shared_by:
            checker["shared_by"] = shared_by
            write_json(checker_path, checker)

    validate_profile_semantic_parity(spec)
    if changed:
        write_json(path, spec)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family", type=int, action="append", required=True)
    args = parser.parse_args()

    for family in sorted(set(args.family)):
        if family < 1 or family > 400:
            raise SystemExit(f"family must be in 1..400: {family}")
        matches = list(args.source.glob(f"{family:03d}-*/evaluator/harness_spec.json"))
        if len(matches) != 1:
            raise SystemExit(f"expected one harness spec for family {family:03d}, found {matches}")
        path = matches[0]
        changed = canonicalize(path)
        print(f"{family:03d}\t{'updated' if changed else 'already canonical'}\t{path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

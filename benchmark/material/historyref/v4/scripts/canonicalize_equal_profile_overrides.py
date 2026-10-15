#!/usr/bin/env python3
"""Move equal feedback/score semantic overrides into the canonical V4 deck."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark-vabench-release-v4" / "scripts"))
import render_v4_harness  # noqa: E402


SEMANTIC_FIELDS = ("body_lines", "analyses", "save_signals")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def family_dir(source: Path, family: str) -> Path:
    matches = sorted(source.glob(f"{family}-*"))
    if len(matches) != 1:
        raise SystemExit(f"{family}: expected one source family, found {len(matches)}")
    return matches[0]


def canonicalize(task: Path) -> bool:
    evaluator = task / "evaluator"
    spec_path = evaluator / "harness_spec.json"
    spec = read_json(spec_path)
    defaults = spec.get("profile_defaults") or {}
    feedback = defaults.get("feedback") or {}
    score = defaults.get("score") or {}
    feedback_overrides = dict(feedback.get("deck_overrides") or {})
    score_overrides = dict(score.get("deck_overrides") or {})
    fields = [
        field
        for field in SEMANTIC_FIELDS
        if field in feedback_overrides or field in score_overrides
    ]
    changed = False
    deck = spec.get("deck") or {}
    for field in fields:
        feedback_value = feedback_overrides.get(field)
        score_value = score_overrides.get(field)
        if feedback_value != score_value:
            raise SystemExit(f"{task.name}: {field} overrides differ across profiles")
        # Equal overrides are the currently effective semantics for both
        # profiles, so they replace any dormant canonical placeholder.
        deck[field] = feedback_value
        feedback_overrides.pop(field, None)
        score_overrides.pop(field, None)
        changed = True
    feedback_seed = int(feedback.get("deterministic_seed") or 0)
    score_seed = int(score.get("deterministic_seed") or 0)
    if feedback_seed != score_seed:
        if feedback_seed != 0:
            raise SystemExit(
                f"{task.name}: non-default feedback seed differs from score seed"
            )
        feedback["deterministic_seed"] = score_seed
        changed = True
    if not changed:
        return False
    spec["deck"] = deck
    spec["canonical_semantics"] = {"mode": "single_deck_v1"}
    for profile, overrides in ((feedback, feedback_overrides), (score, score_overrides)):
        if overrides:
            profile["deck_overrides"] = overrides
        else:
            profile.pop("deck_overrides", None)
    defaults["feedback"] = feedback
    defaults["score"] = score
    spec["profile_defaults"] = defaults
    render_v4_harness.validate_canonical_semantics(spec)
    render_v4_harness.validate_profile_semantics(spec)
    render_v4_harness.validate_profile_semantic_parity(spec)
    write_json(spec_path, spec)

    spec_hash = render_v4_harness.file_sha256(spec_path)
    for profile_name in ("feedback", "score"):
        profile = render_v4_harness.build_profile(spec, profile_name, spec_hash)
        profile_path = evaluator / "profiles" / f"{profile_name}.json"
        write_json(profile_path, profile)
        deck_text = render_v4_harness.render_scs(spec, profile)
        deck_path = (
            task / "public" / "task" / "feedback_tb.scs"
            if profile_name == "feedback"
            else evaluator / "score_tb.scs"
        )
        deck_path.write_text(deck_text, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--family-range", default="001-400")
    args = parser.parse_args()
    left, separator, right = args.family_range.partition("-")
    if not separator:
        right = left
    start, stop = int(left), int(right)
    source = args.source.expanduser().resolve()
    changed = [
        f"{value:03d}"
        for value in range(start, stop + 1)
        if canonicalize(family_dir(source, f"{value:03d}"))
    ]
    print(json.dumps({"status": "pass", "changed_families": changed}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

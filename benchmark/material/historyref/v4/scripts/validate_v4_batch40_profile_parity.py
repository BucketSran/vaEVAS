#!/usr/bin/env python3
"""Validate that V4 feedback and score profiles share semantic stimuli.

Backend-specific simulator options and visibility are intentionally excluded
from the comparison. Stimulus, analysis, parameters, thresholds, properties,
and deck overrides must be identical because both profiles are derived from a
single canonical harness specification.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
SEMANTIC_PROFILE_FIELDS = (
    "property_ids",
    "parameters",
    "corners",
    "deterministic_seed",
    "deck_overrides",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def projection(profile: dict[str, Any]) -> dict[str, Any]:
    return {key: profile.get(key) for key in SEMANTIC_PROFILE_FIELDS}


def semantic_deck(deck: str) -> str:
    lines = []
    for line in deck.splitlines():
        if re.match(r"^simulatorOptions\s+options\s+", line):
            continue
        if line.strip():
            lines.append(line.rstrip())
    return "\n".join(lines).rstrip() + "\n"


def check_task(task: Path) -> list[str]:
    evaluator = task / "evaluator"
    spec_path = evaluator / "harness_spec.json"
    feedback_path = evaluator / "profiles" / "feedback.json"
    score_path = evaluator / "profiles" / "score.json"
    problems: list[str] = []
    try:
        spec = read_json(spec_path)
        feedback = read_json(feedback_path)
        score = read_json(score_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{task.name}: cannot read harness/profile: {exc}"]
    if feedback.get("profile_name") != "feedback":
        problems.append(f"{task.name}: feedback profile identity is invalid")
    if score.get("profile_name") != "score":
        problems.append(f"{task.name}: score profile identity is invalid")
    if projection(feedback) != projection(score):
        problems.append(f"{task.name}: feedback/score semantic profile fields differ")
    if feedback.get("property_ids") != spec.get("property_ids") or score.get("property_ids") != spec.get("property_ids"):
        problems.append(f"{task.name}: profile property IDs do not match canonical spec")
    try:
        feedback_deck = semantic_deck((task / "public" / "task" / "feedback_tb.scs").read_text(encoding="utf-8"))
        score_deck = semantic_deck((evaluator / "score_tb.scs").read_text(encoding="utf-8"))
    except OSError as exc:
        return problems + [f"{task.name}: cannot read rendered deck: {exc}"]
    if feedback_deck != score_deck:
        problems.append(f"{task.name}: feedback/score rendered semantic decks differ")
    if spec.get("deck", {}).get("body_lines") is None or spec.get("deck", {}).get("analyses") is None:
        problems.append(f"{task.name}: canonical spec lacks body_lines or analyses")
    if any(profile.get("deck_overrides") for profile in (feedback, score)):
        problems.append(f"{task.name}: semantic deck overrides remain profile-specific")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family", action="append", type=int)
    args = parser.parse_args()
    wanted = {f"{value:03d}" for value in args.family} if args.family else None
    tasks = sorted(args.source.glob("[0-9][0-9][0-9]-*"))
    if wanted is not None:
        tasks = [task for task in tasks if task.name[:3] in wanted]
    problems = [problem for task in tasks for problem in check_task(task)]
    summary = {
        "status": "PASS" if not problems else "FAIL",
        "task_count": len(tasks),
        "problem_count": len(problems),
        "problems": problems,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

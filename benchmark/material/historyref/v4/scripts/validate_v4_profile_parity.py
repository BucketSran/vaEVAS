#!/usr/bin/env python3
"""Validate feedback/score semantic parity for canonical V4 harness sources.

Simulator adapters (for example ``evas_profile``) are deliberately excluded
from the comparison.  Stimulus, analyses, saved traces, parameters, and
property IDs are semantic inputs and must be identical.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_lines(lines: Any) -> list[str]:
    return [str(line).strip() for line in (lines or []) if str(line).strip()]


def normalized_semantics(spec: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Return only fields that can change the exercised behavior."""
    deck = spec.get("deck") or {}
    overrides = profile.get("deck_overrides") or {}
    body = _clean_lines(list(deck.get("body_lines") or []) + list(overrides.get("body_lines") or []))
    analyses = _clean_lines(overrides.get("analyses") or deck.get("analyses") or [])
    save_signals = _clean_lines(overrides.get("save_signals") or deck.get("save_signals") or [])
    return {
        "body_lines": body,
        "analyses": analyses,
        "save_signals": save_signals,
        "parameters": profile.get("parameters") or {},
        "corners": list(profile.get("corners") or []),
        "deterministic_seed": int(profile.get("deterministic_seed") or 0),
        "property_ids": list(spec.get("property_ids") or []),
        "profile_property_ids": list(profile.get("property_ids") or []),
    }


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


def audit(source: Path, family_ids: list[str]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    checked: list[str] = []
    for family in family_ids:
        task = family_dir(source, family)
        evaluator = task / "evaluator"
        spec = read_json(evaluator / "harness_spec.json")
        feedback = read_json(evaluator / "profiles" / "feedback.json")
        score = read_json(evaluator / "profiles" / "score.json")
        f_semantics = normalized_semantics(spec, feedback)
        s_semantics = normalized_semantics(spec, score)
        checked.append(family)
        if f_semantics != s_semantics:
            differences = {
                key: {"feedback": f_semantics[key], "score": s_semantics[key]}
                for key in sorted(f_semantics)
                if f_semantics[key] != s_semantics[key]
            }
            failures.append({"family_id": family, "differences": differences})
    return {
        "status": "PASS" if not failures else "FAIL",
        "evidence_kind": "static_profile_parity",
        "checked_families": checked,
        "failure_count": len(failures),
        "failures": failures,
        "allowed_profile_differences": ["simulatorOptions"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--family-range", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    family_ids = parse_family_ids(args.family, args.family_range)
    if not family_ids:
        family_ids = [f"{value:03d}" for value in range(1, 401)]
    report = audit(args.source_root.expanduser().resolve(), family_ids)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Validate issue-scoped V4 repair gate invariants for selected families."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / "operations" / "tri_form_derivation_prep"
if str(PREP) not in sys.path:
    sys.path.insert(0, str(PREP))

from score_denominator_registry import load_family_rows  # noqa: E402

DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
FORBIDDEN_DIAGNOSTIC_MARKERS = (
    "/private/",
    "mutation_bundles",
    "checker_implementation",
    "oracle_runner",
    "spectre-mutation",
    "standalone-rust/",
    "neg_",
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.parent.resolve()))
    except ValueError:
        return str(path)


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


def clean_lines(lines: Any) -> list[str]:
    return [str(line).strip() for line in (lines or []) if str(line).strip()]


def normalize_signal(signal: Any) -> str:
    return str(signal).strip().lower()


def normalized_semantics(spec: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    deck = spec.get("deck") or {}
    overrides = profile.get("deck_overrides") or {}
    body = clean_lines(list(deck.get("body_lines") or []) + list(overrides.get("body_lines") or []))
    analyses = clean_lines(overrides.get("analyses") or deck.get("analyses") or [])
    save_signals = clean_lines(overrides.get("save_signals") or deck.get("save_signals") or [])
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


def add_failure(
    failures: list[dict[str, Any]], family: str, check: str, message: str, details: Any = None
) -> None:
    failure: dict[str, Any] = {"family_id": family, "check": check, "message": message}
    if details is not None:
        failure["details"] = details
    failures.append(failure)


def expected_trace_signals(family_spec: dict[str, Any]) -> set[str]:
    signals = {
        normalize_signal(signal)
        for signal in ((family_spec.get("trace_contract") or {}).get("required_signals") or [])
    }
    for prop in family_spec.get("properties") or []:
        signals.update(normalize_signal(signal) for signal in prop.get("required_signals") or [])
    signals.discard("time")
    return signals


def validate_trace_contract(
    failures: list[dict[str, Any]],
    family: str,
    spec: dict[str, Any],
    family_spec: dict[str, Any],
    checker: dict[str, Any],
    public_contract: dict[str, Any],
) -> None:
    public_observables = {normalize_signal(signal) for signal in public_contract.get("public_observables") or []}
    checker_trace = checker.get("trace_contract") or {}
    checker_observables = {normalize_signal(signal) for signal in checker_trace.get("public_observables") or []}
    checker_extra = {normalize_signal(signal) for signal in checker_trace.get("extra_trace_signals") or []}
    checker_extra.discard("time")
    saved = {normalize_signal(signal) for signal in (spec.get("deck") or {}).get("save_signals") or []}
    required = expected_trace_signals(family_spec)

    if checker_observables != public_observables:
        add_failure(
            failures,
            family,
            "observable_alignment",
            "checker trace public observables differ from public contract",
            {
                "missing_in_checker": sorted(public_observables - checker_observables),
                "extra_in_checker": sorted(checker_observables - public_observables),
            },
        )
    trace_signals = public_observables | checker_observables | checker_extra | required
    trace_signals.discard("time")
    missing_saved = sorted(trace_signals - saved)
    if missing_saved:
        add_failure(
            failures,
            family,
            "trace_coverage",
            "deck save signals do not cover declared observables",
            {"missing_saved_signals": missing_saved},
        )


def validate_profiles(
    failures: list[dict[str, Any]],
    family: str,
    spec: dict[str, Any],
    spec_sha256: str,
    feedback: dict[str, Any],
    score: dict[str, Any],
) -> None:
    property_ids = list(spec.get("property_ids") or [])
    for profile_name, profile in (("feedback", feedback), ("score", score)):
        if profile.get("harness_spec_sha256") != spec_sha256:
            add_failure(
                failures,
                family,
                "profile_harness_binding",
                f"{profile_name} profile is not bound to the current harness spec",
                {
                    "recorded": profile.get("harness_spec_sha256"),
                    "actual": spec_sha256,
                },
            )
        if list(profile.get("property_ids") or []) != property_ids:
            add_failure(
                failures,
                family,
                "property_ids",
                f"{profile_name} profile property_ids differ from harness spec",
            )
    feedback_semantics = normalized_semantics(spec, feedback)
    score_semantics = normalized_semantics(spec, score)
    if feedback_semantics != score_semantics:
        differences = {
            key: {"feedback": feedback_semantics[key], "score": score_semantics[key]}
            for key in sorted(feedback_semantics)
            if feedback_semantics[key] != score_semantics[key]
        }
        add_failure(
            failures,
            family,
            "profile_semantic_parity",
            "feedback and score profiles exercise different semantics",
            differences,
        )
    if score.get("deck_overrides"):
        add_failure(
            failures,
            family,
            "score_overrides",
            "score profile still carries private stimulus overrides",
            score.get("deck_overrides"),
        )


def diagnostic_strings(diagnostics: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("expected", "observed"):
        value = diagnostics.get(key)
        if isinstance(value, str):
            values.append(value)
    return values


def validate_diagnostics(
    failures: list[dict[str, Any]], family: str, task: Path, property_ids: set[str]
) -> None:
    certifications = sorted((task / "evaluator" / "mutation_bundles").glob("*/certification.json"))
    if len(certifications) < 5:
        add_failure(
            failures,
            family,
            "certified_mutations",
            "fewer than five certified mutation diagnostics are present",
            {"count": len(certifications)},
        )
    for certification in certifications:
        payload = read_json(certification)
        diagnostics = payload.get("diagnostics")
        if not isinstance(diagnostics, dict):
            add_failure(
                failures,
                family,
                "diagnostic_shape",
                "mutation certification lacks a structured diagnostics object",
                str(certification.relative_to(task)),
            )
            continue
        missing_keys = sorted({"expected", "observed", "violated_property_ids"} - diagnostics.keys())
        if missing_keys:
            add_failure(
                failures,
                family,
                "diagnostic_shape",
                "diagnostics object is missing required public fields",
                {"path": str(certification.relative_to(task)), "missing_keys": missing_keys},
            )
        violated = diagnostics.get("violated_property_ids")
        if not isinstance(violated, list) or not violated:
            add_failure(
                failures,
                family,
                "diagnostic_shape",
                "violated_property_ids must be a nonempty list",
                str(certification.relative_to(task)),
            )
            continue
        unknown = sorted(str(item) for item in violated if str(item) not in property_ids)
        if unknown:
            add_failure(
                failures,
                family,
                "diagnostic_properties",
                "diagnostics cite properties outside the public property set",
                {"path": str(certification.relative_to(task)), "unknown_property_ids": unknown},
            )
        strings = diagnostic_strings(diagnostics)
        if not strings or any(not item.strip() for item in strings):
            add_failure(
                failures,
                family,
                "diagnostic_shape",
                "expected and observed diagnostics must be nonempty strings",
                str(certification.relative_to(task)),
            )
        observed = str(diagnostics.get("observed") or "")
        if "EVAS:" not in observed:
            add_failure(
                failures,
                family,
                "diagnostic_parity",
                "observed diagnostics must report an EVAS summary",
                str(certification.relative_to(task)),
            )
        combined = "\n".join(strings).lower()
        leaked = sorted(marker for marker in FORBIDDEN_DIAGNOSTIC_MARKERS if marker in combined)
        if leaked:
            add_failure(
                failures,
                family,
                "diagnostic_redaction",
                "diagnostics expose private implementation or provenance markers",
                {"path": str(certification.relative_to(task)), "markers": leaked},
            )


def validate_hashes(
    failures: list[dict[str, Any]], family: str, source: Path, task: Path, manifest: dict[str, Any]
) -> None:
    record_path = task / "evaluator" / "task_record.json"
    record = read_json(record_path)
    for relative, expected in (record.get("evaluator_hashes") or {}).items():
        path = task / "evaluator" / relative
        if path.is_file() and file_sha(path) != expected:
            add_failure(
                failures,
                family,
                "task_record_hash",
                "evaluator hash is stale",
                {"path": str(path.relative_to(source)), "recorded": expected, "actual": file_sha(path)},
            )
    for relative, expected in (record.get("public_hashes") or {}).items():
        path = task / "public" / "task" / relative
        if path.is_file() and file_sha(path) != expected:
            add_failure(
                failures,
                family,
                "task_record_hash",
                "public hash is stale",
                {"path": str(path.relative_to(source)), "recorded": expected, "actual": file_sha(path)},
            )
    rows = [manifest[family]] if family in manifest else []
    if len(rows) != 1:
        add_failure(
            failures,
            family,
            "score_denominator_registry",
            "expected one registry row for family",
            {"row_count": len(rows)},
        )
        return
    row = rows[0]
    hashes = row.get("hashes") or {}
    expected_hashes = {
        "task_record_sha256": file_sha(record_path),
        "score_deck_sha256": file_sha(task / "evaluator" / "score_tb.scs"),
    }
    stale = {
        key: {"recorded": hashes.get(key), "actual": value}
        for key, value in expected_hashes.items()
        if hashes.get(key) != value
    }
    if stale:
        add_failure(
            failures,
            family,
            "score_denominator_registry",
            "registry row hashes are stale",
            stale,
        )


def validate_family(
    failures: list[dict[str, Any]], source: Path, family: str, manifest: dict[str, Any]
) -> None:
    task = family_dir(source, family)
    evaluator = task / "evaluator"
    public = task / "public" / "task"
    spec = read_json(evaluator / "harness_spec.json")
    feedback = read_json(evaluator / "profiles" / "feedback.json")
    score = read_json(evaluator / "profiles" / "score.json")
    family_spec = read_json(evaluator / "family_spec.json")
    checker = read_json(evaluator / "checker_profile.json")
    public_contract = read_json(public / "public_contract.json")

    validate_trace_contract(failures, family, spec, family_spec, checker, public_contract)
    validate_profiles(
        failures,
        family,
        spec,
        file_sha(evaluator / "harness_spec.json"),
        feedback,
        score,
    )
    validate_diagnostics(failures, family, task, set(spec.get("property_ids") or []))
    validate_hashes(failures, family, source, task, manifest)


def audit(source: Path, families: list[str]) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    manifest = {
        str(row["canonical_dut_id"]): row
        for row in load_family_rows(source)
    }
    for family in families:
        validate_family(failures, source, family, manifest)
    return {
        "schema_version": "v4-repair-gate-validation-v1",
        "source": display_path(source),
        "evidence_kind": "static_repair_gate",
        "runtime_evidence_claimed": False,
        "checked_families": families,
        "status": "PASS" if not failures else "FAIL",
        "failure_count": len(failures),
        "failures": failures,
        "checks": [
            "profile_semantic_parity",
            "profile_harness_binding",
            "observable_alignment",
            "trace_coverage",
            "structured_redacted_diagnostics",
            "task_record_hashes",
            "score_denominator_registry_hashes",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--family-range", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    families = parse_family_ids(args.family, args.family_range)
    if not families:
        raise SystemExit("select at least one family with --family or --family-range")
    report = audit(args.source_root.expanduser().resolve(), families)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

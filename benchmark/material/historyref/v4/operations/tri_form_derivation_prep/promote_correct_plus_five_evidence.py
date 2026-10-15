#!/usr/bin/env python3
"""Promote raw correct+5 reports into compact, repository-safe evidence.

The raw EVAS and Spectre reports contain machine-local paths, simulator work
directories, and log tails.  This tool deliberately does not copy those
fields.  It binds the retained outcomes to the current source task inputs and
emits only repository-relative paths plus SHA-256 fingerprints.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from score_denominator_registry import load_family_rows


SCHEMA_VERSION = "v4-compact-correct-plus-five-evidence-v1"
DECK_PATHS = {
    "feedback": Path("public/task/feedback_tb.scs"),
    "reference": Path("evaluator/reference_tb.scs"),
    "score": Path("evaluator/score_tb.scs"),
}
_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9_.-])/(?:[^\s\"'<>]+)")


class PromotionError(ValueError):
    """Raised when a raw report cannot be bound to source inputs exactly."""


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PromotionError(f"expected a JSON object: {path}")
    return value


def _clean_text(value: Any) -> str:
    return _ABSOLUTE_PATH.sub("<path>", str(value))


def _clean_lines(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return sorted({_clean_text(item) for item in values if str(item).strip()})


def _relative(source_root: Path, path: Path) -> str:
    try:
        return path.relative_to(source_root).as_posix()
    except ValueError as exc:
        raise PromotionError(f"source artifact escapes source root: {path}") from exc


def _source_files(root: Path) -> list[Path]:
    if not root.is_dir():
        raise PromotionError(f"candidate source directory is missing: {root}")
    files = [
        path
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "certification.json"
    ]
    if not files:
        raise PromotionError(f"candidate source directory is empty: {root}")
    return files


def _file_records(source_root: Path, files: Iterable[Path]) -> list[dict[str, str]]:
    return [
        {"path": _relative(source_root, path), "sha256": file_sha(path)}
        for path in files
    ]


def _tree_fingerprint(records: list[dict[str, str]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        digest.update(record["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(record["sha256"].encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def _detect_evaluator(report: dict[str, Any]) -> str:
    schema = str(report.get("schema_version") or "")
    engine = report.get("engine") or {}
    if "rust-evas" in schema or engine.get("name") == "evas-rust":
        return "rust-evas"
    if "spectre" in schema or report.get("spectre_backend"):
        return "spectre"
    raise PromotionError("unsupported raw report schema")


def _load_rows(source_root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in load_family_rows(source_root):
        family = str(row.get("canonical_dut_id") or "")
        if family:
            rows[family] = row
    if not rows:
        raise PromotionError("source denominator has no task rows")
    return rows


def _reported_cases(
    evaluator: str,
    result: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    for raw_case in result.get("cases") or []:
        raw_id = str(raw_case.get("case_id") or "")
        if evaluator == "rust-evas":
            role = str(raw_case.get("role") or "")
            case_id = "correct" if role == "reference" else raw_id
        else:
            kind = str(raw_case.get("case_kind") or "")
            case_id = "correct" if kind == "correct" else raw_id
        if not case_id or case_id in cases:
            raise PromotionError(f"duplicate or empty case id: {case_id!r}")
        cases[case_id] = raw_case
    return cases


def _require_passed_case(evaluator: str, case_id: str, case: dict[str, Any]) -> None:
    expected_outcome = "reference_pass" if case_id == "correct" else "killed_behaviorally"
    if case.get("outcome") != expected_outcome:
        raise PromotionError(f"{case_id}: expected outcome {expected_outcome}")
    if evaluator == "rust-evas":
        simulation = case.get("simulation") or {}
        behavior = case.get("behavior") or {}
        expected_behavior = case_id == "correct"
        if simulation.get("ok") is not True or behavior.get("ok") is not expected_behavior:
            raise PromotionError(f"{case_id}: Rust EVAS did not prove the expected behavior")
    else:
        simulation = case.get("spectre") or {}
        expected_observed = "behavior_pass" if case_id == "correct" else "behavior_fail"
        if simulation.get("ok") is not True or case.get("observed") != expected_observed:
            raise PromotionError(f"{case_id}: Spectre did not prove the expected behavior")
        if case.get("untriaged_warning_lines"):
            raise PromotionError(f"{case_id}: untriaged Spectre warnings remain")


def _bind_runtime_candidate_files(
    *,
    evaluator: str,
    case_id: str,
    case: dict[str, Any],
    source_files: list[Path],
    runtime_root: Path,
) -> None:
    source_by_name = {path.name: file_sha(path) for path in source_files}
    if len(source_by_name) != len(source_files):
        raise PromotionError(f"{case_id}: candidate files have ambiguous basenames")

    if evaluator == "rust-evas":
        if case_id == "correct":
            runtime_files = _source_files(runtime_root / "evaluator" / "trusted_solution")
        else:
            runtime_files = _source_files(
                runtime_root / "evaluator" / "mutation_bundles" / case_id
            )
    else:
        include_paths = [Path(item) for item in case.get("include_paths") or []]
        if not include_paths or any(not path.is_file() for path in include_paths):
            raise PromotionError(f"{case_id}: raw Spectre include paths are unavailable")
        runtime_files = include_paths

    runtime_by_name = {path.name: file_sha(path) for path in runtime_files}
    if runtime_by_name != source_by_name:
        raise PromotionError(f"{case_id}: runtime candidate files do not match source")


def _checker_binding(
    *,
    repo_root: Path,
    source_root: Path,
    task_root: Path,
    family: str,
    checker_task_id: str,
) -> dict[str, Any]:
    profile = task_root / "evaluator" / "checker_profile.json"
    if not profile.is_file():
        raise PromotionError(f"{family}: checker profile is missing")
    candidates = [repo_root / "runners" / "simulate_evas.py"]
    for relative in (
        Path("runners/checkers/api.py"),
        Path("runners/checkers/v4/registry.py"),
        Path(f"runners/checkers/v4/task_{family}.py"),
    ):
        path = repo_root / relative
        if path.is_file():
            candidates.append(path)
    implementation_files = [
        {"path": path.relative_to(repo_root).as_posix(), "sha256": file_sha(path)}
        for path in candidates
        if path.is_file()
    ]
    if not implementation_files:
        raise PromotionError("checker implementation files are missing")
    return {
        "task_id": checker_task_id,
        "profile_path": _relative(source_root, profile),
        "profile_sha256": file_sha(profile),
        "implementation_bundle_sha256": _tree_fingerprint(implementation_files),
        "implementation_files": implementation_files,
    }


def _tool_fingerprints(
    evaluator: str,
    report: dict[str, Any],
    runner_file: Path | None,
) -> dict[str, Any]:
    promoted: dict[str, Any] = {
        "promotion_tool_sha256": file_sha(Path(__file__)),
    }
    if runner_file is not None:
        if not runner_file.is_file():
            raise PromotionError(f"runner file is missing: {runner_file}")
        promoted["runner_sha256"] = file_sha(runner_file)
    if evaluator == "rust-evas":
        engine = report.get("engine") or {}
        promoted["reported_engine"] = {
            key: engine[key]
            for key in (
                "name",
                "git_commit",
                "git_describe",
                "rust_library_sha256",
                "spectre_strict",
            )
            if key in engine
        }
        for key in ("checker_module_sha256", "checker_aliases_sha256"):
            if report.get(key):
                promoted[key] = report[key]
    else:
        promoted["reported_engine"] = {
            "name": "spectre",
            "backend": report.get("spectre_backend"),
            "mode": report.get("spectre_mode"),
        }
    return promoted


def _case_record(
    *,
    evaluator: str,
    case_id: str,
    case: dict[str, Any],
    candidate_files: list[dict[str, str]],
) -> dict[str, Any]:
    if evaluator == "rust-evas":
        behavior = case.get("behavior") or {}
        score = behavior.get("score")
        notes = _clean_lines(behavior.get("notes"))
        benign_warnings: list[str] = []
        untriaged_warnings: list[str] = []
    else:
        score = case.get("behavior_score")
        notes = _clean_lines(case.get("behavior_notes"))
        benign_warnings = _clean_lines(case.get("benign_warning_lines"))
        untriaged_warnings = _clean_lines(case.get("untriaged_warning_lines"))
    return {
        "case_id": case_id,
        "role": "correct" if case_id == "correct" else "negative",
        "expected": "behavior_pass" if case_id == "correct" else "behavior_fail",
        "observed": "behavior_pass" if case_id == "correct" else "behavior_fail",
        "outcome": "reference_pass" if case_id == "correct" else "killed_behaviorally",
        "behavior_score": score,
        "behavior_notes": notes,
        "candidate_bundle_sha256": _tree_fingerprint(candidate_files),
        "candidate_files": candidate_files,
        # Warning text is deduplicated once at task scope.  Per-case counts
        # retain the important distinction without repeating long simulator
        # messages six times.
        "warnings": {
            "benign_count": len(benign_warnings),
            "untriaged_count": len(untriaged_warnings),
        },
        "_benign_warnings": benign_warnings,
        "_untriaged_warnings": untriaged_warnings,
    }


def promote_report(
    *,
    source_root: Path,
    report_path: Path,
    deck_kind: str,
    task_ids: set[str] | None = None,
    runner_file: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Return compact evidence after verifying every retained source binding."""
    source_root = source_root.resolve()
    report_path = report_path.resolve()
    if deck_kind not in DECK_PATHS:
        raise PromotionError(f"unsupported deck kind: {deck_kind}")
    report = read_json(report_path)
    evaluator = _detect_evaluator(report)
    rows = _load_rows(source_root)
    repo_root = (repo_root or Path(__file__).resolve().parents[3]).resolve()

    raw_results = [
        result
        for result in report.get("results") or []
        if not task_ids or str(result.get("task_id") or "") in task_ids
    ]
    if not raw_results:
        raise PromotionError("no report tasks matched the requested task ids")
    if task_ids and {str(item.get("task_id") or "") for item in raw_results} != task_ids:
        raise PromotionError("one or more requested task ids are missing from the report")

    tasks: list[dict[str, Any]] = []
    for result in raw_results:
        task_id = str(result.get("task_id") or "")
        family = str(result.get("family_id") or "")
        row = rows.get(family)
        if row is None:
            raise PromotionError(f"{task_id}: family {family} is not in the source denominator")
        if str(result.get("status") or "").lower() != "pass":
            raise PromotionError(f"{task_id}: report result is not PASS")
        if result.get("reference_gate") not in (True, "reference_pass"):
            raise PromotionError(f"{task_id}: reference gate did not pass")

        mutation_ids = [
            str(item.get("mutation_id") or "") for item in row.get("active_mutations") or []
        ]
        if len(mutation_ids) != 5 or len(set(mutation_ids)) != 5:
            raise PromotionError(f"{task_id}: source denominator is not exact-five")
        cases = _reported_cases(evaluator, result)
        expected_case_ids = {"correct", *mutation_ids}
        if set(cases) != expected_case_ids:
            raise PromotionError(f"{task_id}: report does not contain the exact active negative set")
        if result.get("kill_denominator") != 5 or result.get("killed_count") != 5:
            raise PromotionError(f"{task_id}: report does not prove five behavioral kills")

        task_root = source_root / str(row.get("release_dir") or "")
        deck = task_root / DECK_PATHS[deck_kind]
        if not deck.is_file():
            raise PromotionError(f"{task_id}: selected candidate testbench is missing")
        deck_sha = file_sha(deck)
        if evaluator == "rust-evas":
            reported_sha = (result.get("candidate_sha256") or {}).get("testbench.scs")
            if reported_sha != deck_sha:
                raise PromotionError(f"{task_id}: candidate testbench hash does not match source")
            runtime_root = Path(str(result.get("run_dir") or ""))
            runtime_deck = runtime_root / "public" / "submission" / "testbench.scs"
        else:
            runtime_root = Path(".")
            runtime_deck = Path(str(result.get("reference_tb") or ""))
        if not runtime_deck.is_file() or file_sha(runtime_deck) != deck_sha:
            raise PromotionError(f"{task_id}: raw report deck is unavailable or hash-mismatched")

        checker_task_id = str(result.get("checker_task_id") or "")
        case_records: list[dict[str, Any]] = []
        for case_id in ["correct", *mutation_ids]:
            case = cases[case_id]
            _require_passed_case(evaluator, case_id, case)
            candidate_root = (
                task_root / "evaluator" / "solution"
                if case_id == "correct"
                else task_root / "evaluator" / "mutation_bundles" / case_id
            )
            source_files = _source_files(candidate_root)
            _bind_runtime_candidate_files(
                evaluator=evaluator,
                case_id=case_id,
                case=case,
                source_files=source_files,
                runtime_root=runtime_root,
            )
            candidate_files = _file_records(source_root, source_files)
            case_records.append(
                _case_record(
                    evaluator=evaluator,
                    case_id=case_id,
                    case=case,
                    candidate_files=candidate_files,
                )
            )

        benign_warnings = sorted(
            {
                warning
                for item in case_records
                for warning in item.pop("_benign_warnings")
            }
        )
        untriaged_warnings = sorted(
            {
                warning
                for item in case_records
                for warning in item.pop("_untriaged_warnings")
            }
        )

        tasks.append(
            {
                "task_id": task_id,
                "family_id": family,
                "form": str(result.get("form") or "testbench"),
                "candidate_testbench": {
                    "path": _relative(source_root, deck),
                    "sha256": deck_sha,
                },
                "checker": _checker_binding(
                    repo_root=repo_root,
                    source_root=source_root,
                    task_root=task_root,
                    family=family,
                    checker_task_id=checker_task_id,
                ),
                "reference_gate": "pass",
                "kill_denominator": 5,
                "killed_count": 5,
                "warnings": {
                    "benign": benign_warnings,
                    "untriaged": untriaged_warnings,
                },
                "untriaged_warning_count": sum(
                    item["warnings"]["untriaged_count"] for item in case_records
                ),
                "status": "pass",
                "cases": case_records,
            }
        )

    tasks.sort(key=lambda item: item["task_id"])
    return {
        "schema_version": SCHEMA_VERSION,
        "claim_scope": "fresh_correct_plus_five_behavioral_validation",
        "evaluator": evaluator,
        "deck_kind": deck_kind,
        "source_report_schema_version": report.get("schema_version"),
        "source_report_sha256": file_sha(report_path),
        "tool_fingerprints": _tool_fingerprints(evaluator, report, runner_file),
        "summary": {
            "task_count": len(tasks),
            "reference_pass_count": len(tasks),
            "negative_case_count": 5 * len(tasks),
            "behavioral_kill_count": 5 * len(tasks),
            "untriaged_warning_count": sum(
                task["untriaged_warning_count"] for task in tasks
            ),
            "status": "pass",
        },
        "tasks": tasks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--deck-kind", choices=sorted(DECK_PATHS), required=True)
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--runner-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        promoted = promote_report(
            source_root=args.source_root,
            report_path=args.report,
            deck_kind=args.deck_kind,
            task_ids=set(args.task_id) or None,
            runner_file=args.runner_file,
        )
    except (OSError, json.JSONDecodeError, PromotionError) as exc:
        raise SystemExit(f"promotion failed: {exc}") from exc
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(promoted, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Replay tri-form reference testbenches through Spectre and private checkers.

This is intentionally narrower than the model/API runner: it validates sealed
benchmark reference assets by running each selected testbench-form task's local
``evaluator/reference_tb.scs`` against its public ``public/supplied_dut``
artifacts, then scores the resulting Spectre CSV with the canonical private
checker.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
REPO = PACKAGE.parent
RUNNERS = REPO / "runners"
DEFAULT_RELEASE = PACKAGE / "release" / "benchmarkv4-r52"

for import_dir in (RUNNERS,):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

from run_gold_dual_suite import (  # noqa: E402
    ahdl_includes,
    default_bridge_repo,
    default_remote_cadence_cshrc,
    default_remote_host,
    default_remote_work_root,
    discover_spectre_support_files,
    normalize_spectre_backend,
    normalize_spectre_mode,
    rewrite_ahdl_includes_for_staging,
    run_spectre_case,
    safe_path_component,
    staged_input_rel,
)
from simulate_evas import (  # noqa: E402
    behavior_side_output_names,
    behavior_checker_policy,
    evaluate_behavior_with_timeout,
    has_behavior_check,
    resolve_row_behavior_checker,
    validate_behavior_side_outputs,
)


WARNING_RE = re.compile(r"(?m)^\s*(?:WARNING(?:\s|\()|AHDL\w* warning)[^\n]*$")
BENIGN_WARNING_PATTERNS = (
    re.compile(r"^remote_ahdlcmi_cache_prepare_failed rc=75$"),
    re.compile(r"^WARNING \(VACOMP-2435\):"),
    re.compile(r"^WARNING \(SPECTRE-592\):"),
    re.compile(
        r"^WARNING \(SFE-105\): .*`evas_profile' has been ignored because it is not an option\."
    ),
    re.compile(r"^spectre completes with 0 errors, [0-9]+ warnings?, and [0-9]+ notices?\.$"),
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_fingerprint(path: Path, root: Path) -> dict[str, Any]:
    data = path.read_bytes()
    try:
        rel_path = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel_path = path.resolve().as_posix()
    return {"path": rel_path, "bytes": len(data), "sha256": sha256_bytes(data)}


def missing_file_fingerprint(path: Path, root: Path) -> dict[str, Any]:
    try:
        rel_path = path.resolve().relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        rel_path = path.as_posix()
    return {"path": rel_path, "exists": False}


def tree_fingerprint(root: Path, rel_root: Path) -> dict[str, Any]:
    try:
        root_name = root.resolve().relative_to(rel_root.resolve()).as_posix()
    except ValueError:
        root_name = root.name
    if not root.exists():
        return {"root": root_name, "exists": False, "files": []}
    if root.is_file():
        return {"root": root_name, "exists": True, "files": [file_fingerprint(root, rel_root)]}
    files = [
        file_fingerprint(path, rel_root)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return {"root": root_name, "exists": True, "files": files}


def unique_existing_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def fingerprint_if_file(path: Path, root: Path) -> dict[str, Any]:
    return file_fingerprint(path, root) if path.is_file() else missing_file_fingerprint(path, root)


def checker_implementation_bundle(checker_id: str) -> dict[str, Any]:
    checker = resolve_row_behavior_checker(checker_id)
    files: list[Path] = []
    source_sha256 = ""
    source_error = ""
    if checker is None:
        source_error = "checker_not_registered"
    else:
        unwrapped = inspect.unwrap(checker)
        try:
            source_sha256 = sha256_bytes(inspect.getsource(unwrapped).encode("utf-8"))
        except (OSError, TypeError) as exc:
            source_error = f"{type(exc).__name__}: {exc}"
        for candidate in (checker, unwrapped):
            try:
                source_file = inspect.getsourcefile(candidate)
            except TypeError:
                source_file = None
            if source_file:
                files.append(Path(source_file))
    for func in (run_spectre_case, evaluate_behavior_with_timeout, validate_behavior_side_outputs):
        source_file = inspect.getsourcefile(func)
        if source_file:
            files.append(Path(source_file))
    existing_files = sorted(
        unique_existing_paths(files),
        key=lambda item: item.resolve().as_posix(),
    )
    return {
        "checker_id": checker_id,
        "policy": behavior_checker_policy(checker_id),
        "source_sha256": source_sha256,
        "source_error": source_error,
        "files": [file_fingerprint(path, REPO) for path in existing_files],
    }


def function_source_fingerprint(func: Any) -> dict[str, Any]:
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError) as exc:
        return {
            "function": getattr(func, "__name__", repr(func)),
            "source_sha256": "",
            "source_error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "function": getattr(func, "__name__", repr(func)),
        "source_sha256": sha256_bytes(source.encode("utf-8")),
        "source_error": "",
    }


def bridge_implementation_bundle() -> dict[str, Any]:
    funcs = [
        run_spectre_case,
        discover_spectre_support_files,
        rewrite_ahdl_includes_for_staging,
        staged_input_rel,
        safe_path_component,
    ]
    files = []
    for func in funcs:
        source_file = inspect.getsourcefile(func)
        if source_file:
            files.append(Path(source_file))
    return {
        "implementation_id": "run_gold_dual_suite.spectre_staging_v1",
        "functions": [function_source_fingerprint(func) for func in funcs],
        "files": [file_fingerprint(path, REPO) for path in unique_existing_paths(files)],
    }


def effective_staged_deck_bundle(
    *,
    task_id: str,
    case_id: str,
    tb_path: Path,
    include_paths: list[Path],
    release: Path,
) -> dict[str, Any]:
    support_paths = discover_spectre_support_files(tb_path, include_paths)
    staged_deck = rewrite_ahdl_includes_for_staging(tb_path, include_paths)
    staged_task_id = safe_path_component(f"{task_id}:{case_id}")
    staged_tb_name = f"{staged_task_id}__{tb_path.name}"
    input_paths = [*include_paths, *support_paths]
    return {
        "staged_tb_name": staged_tb_name,
        "staged_deck_bytes": len(staged_deck.encode("utf-8")),
        "staged_deck_sha256": sha256_bytes(staged_deck.encode("utf-8")),
        "staged_inputs": [
            {
                "source": file_fingerprint(path, release),
                "staged_rel": staged_input_rel(tb_path, path).as_posix(),
            }
            for path in unique_existing_paths(input_paths)
        ],
        "support_files": [file_fingerprint(path, release) for path in unique_existing_paths(support_paths)],
    }


def build_case_signature(
    *,
    release: Path,
    row: dict[str, Any],
    task_dir: Path,
    task_record: dict[str, Any],
    case_id: str,
    case_kind: str,
    mutation_id: str,
    checker_id: str,
    tb_path: Path,
    include_paths: list[Path],
    missing_includes: list[str],
    score_policy: dict[str, Any],
    dut_root: Path,
    spectre_backend: str,
    spectre_mode: str,
    timeout_s: int,
    spectre_runtime_id: str,
    sui_host: str | None,
    sui_work_root: str | None,
    cadence_cshrc: str | None,
) -> tuple[dict[str, Any], str]:
    task_eval = task_dir / "evaluator"
    signature = {
        "schema_version": "v4-reference-spectre-case-signature-v1",
        "identity": {
            "task_id": str(row.get("task_id") or ""),
            "family_id": str(task_record.get("family_id") or row.get("family_id") or ""),
            "task_dir": str(row.get("task_dir") or ""),
            "case_id": case_id,
            "case_kind": case_kind,
            "mutation_id": mutation_id,
        },
        "reference_deck": fingerprint_if_file(tb_path, release),
        "dut_tree": tree_fingerprint(dut_root, release),
        "mutation_bundle_tree": (
            tree_fingerprint(dut_root, release)
            if case_kind == "negative"
            else {"root": "", "exists": False, "files": []}
        ),
        "include_files": [
            file_fingerprint(path, release) for path in unique_existing_paths(include_paths)
        ],
        "missing_includes": list(missing_includes),
        "effective_staged_deck": effective_staged_deck_bundle(
            task_id=str(row.get("task_id") or ""),
            case_id=case_id,
            tb_path=tb_path,
            include_paths=include_paths,
            release=release,
        ),
        "checker_profile": fingerprint_if_file(task_eval / "checker_profile.json", release),
        "checker_implementation_bundle": checker_implementation_bundle(checker_id),
        "score_mutation_policy": {
            "score_policy": fingerprint_if_file(task_eval / "score_policy.json", release),
            "score_policy_payload": score_policy,
            "mutation_catalog": fingerprint_if_file(task_eval / "mutation_catalog.json", release),
            "mutation_bundle_manifest": fingerprint_if_file(
                task_eval / "mutation_bundles" / "manifest.json", release
            ),
        },
        "harness_profile": {
            "task_record": fingerprint_if_file(task_dir / "task_record.json", release),
            "public_contract": fingerprint_if_file(
                release / str(row.get("public_contract") or ""), release
            ),
            "harness_spec": fingerprint_if_file(task_eval / "harness_spec.json", release),
            "family_spec": fingerprint_if_file(task_eval / "family_spec.json", release),
            "testbench_security_policy": fingerprint_if_file(
                task_eval / "testbench_security_policy.json", release
            ),
        },
        "spectre_run_config": {
            "spectre_backend": spectre_backend,
            "spectre_mode": spectre_mode,
            "timeout_s": timeout_s,
            "spectre_runtime_id": spectre_runtime_id,
            "side_output_files": list(behavior_side_output_names(checker_id)),
            "bridge_implementation_bundle": bridge_implementation_bundle(),
        },
    }
    digest = sha256_bytes(canonical_json_bytes(signature))
    return signature, digest


def attach_case_signature(case: dict[str, Any], signature: dict[str, Any], digest: str) -> dict[str, Any]:
    case["case_signature"] = signature
    case["case_signature_sha256"] = digest
    return case


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def extract_warning_lines(case_dir: Path, spectre_result: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for item in spectre_result.get("warnings") or []:
        text = str(item).strip()
        if text:
            warnings.append(text)
    log_path = case_dir / "spectre.out"
    if log_path.exists():
        text = log_path.read_text(encoding="utf-8", errors="replace")
        for match in WARNING_RE.finditer(text):
            line = re.sub(r"\s+", " ", match.group(0).strip())
            if line and line not in warnings:
                warnings.append(line)
    return warnings[:50]


def is_benign_warning(line: str) -> bool:
    return any(pattern.search(line) for pattern in BENIGN_WARNING_PATTERNS)


def resolve_task_rows(release: Path, requested: list[str]) -> list[dict[str, Any]]:
    rows = list(read_json(release / "TASK_INDEX.json").get("tasks") or [])
    tb_rows = [row for row in rows if row.get("form") == "testbench"]
    if not requested:
        return tb_rows
    by_id = {str(row.get("task_id")): row for row in tb_rows}
    missing = [task_id for task_id in requested if task_id not in by_id]
    if missing:
        raise SystemExit(f"unknown testbench task id(s): {', '.join(missing)}")
    return [by_id[task_id] for task_id in requested]


def checker_task_id(task_dir: Path, task_record: dict[str, Any]) -> str:
    task_eval = task_dir / "evaluator"
    checker_profile = read_json(task_eval / "checker_profile.json")
    source_slug = str(task_record.get("canonical_dut_source_slug") or "")
    source_name = source_slug.partition("-")[2].replace("-", "_")
    candidates = [
        str(task_record.get("checker_task_id") or ""),
        str(checker_profile.get("checker_task_id") or ""),
        str((checker_profile.get("contract") or {}).get("source_task_id") or ""),
        f"v3_{source_slug.replace('-', '_')}" if source_slug else "",
        source_slug,
        source_name,
    ]
    for checker_id in candidates:
        if has_behavior_check(checker_id):
            return checker_id
    attempted = ", ".join(repr(item) for item in candidates if item)
    raise RuntimeError(f"{task_dir.name}: checker not registered; tried {attempted}")


def include_paths_for_reference_tb(
    task_dir: Path,
    tb_path: Path,
    *,
    dut_root: Path | None = None,
) -> tuple[list[Path], list[str]]:
    public_dut = task_dir / "public" / "supplied_dut"
    supplied_dut = dut_root or public_dut
    public_support = task_dir / "public" / "public_support"
    search_dirs = [supplied_dut, public_support, tb_path.parent]
    public_dut_names = (
        {path.name for path in public_dut.rglob("*") if path.is_file()}
        if dut_root is not None and public_dut.is_dir()
        else set()
    )
    found: list[Path] = []
    missing: list[str] = []
    for include in ahdl_includes(tb_path):
        include_path = Path(include.replace("\\", "/"))
        candidates: list[Path] = []
        is_staged_dut_include = bool(include_path.parts) and include_path.parts[0] == "dut"
        is_dut_artifact = dut_root is not None and include_path.name in public_dut_names
        if dut_root is None and is_staged_dut_include:
            relative_to_dut = Path(*include_path.parts[1:])
            candidates.append(public_dut / relative_to_dut)
            candidates.append(supplied_dut / relative_to_dut)
        if is_dut_artifact:
            relative_to_dut = (
                Path(*include_path.parts[1:]) if is_staged_dut_include else Path(include_path.name)
            )
            candidates.append(dut_root / relative_to_dut)
            candidates.extend(
                path for path in dut_root.rglob(include_path.name) if path.is_file()
            )
            if is_staged_dut_include:
                candidates.append(public_dut / relative_to_dut)
                candidates.extend(
                    path for path in public_dut.rglob(include_path.name) if path.is_file()
                )
        else:
            if not include_path.is_absolute() and ".." not in include_path.parts:
                candidates.append(task_dir / include_path)
                candidates.extend(root / include_path.name for root in search_dirs)
            candidates.append((tb_path.parent / include_path).resolve())
        match = next((path for path in candidates if path.exists() and path.is_file()), None)
        if match is None:
            missing.append(include)
            continue
        if match not in found:
            found.append(match)
    return found, missing


def compact_spectre_result(spectre: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": bool(spectre.get("ok")),
        "status": spectre.get("status"),
        "spectre_backend": spectre.get("spectre_backend"),
        "spectre_mode": spectre.get("spectre_mode"),
        "errors": list(spectre.get("errors") or []),
        "warnings": list(spectre.get("warnings") or []),
        "rows": int(spectre.get("rows") or 0),
        "signals_count": len(spectre.get("signals") or []),
        "timing": spectre.get("timing") or {},
        "remote_run_dir": spectre.get("remote_run_dir") or "",
        "csv_path": spectre.get("csv_path") or "",
    }


def _invalid_case(
    *,
    case_id: str,
    case_kind: str,
    mutation_id: str,
    expected: str,
    observed: str,
    notes: list[str],
    include_paths: list[Path] | None = None,
    missing_includes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "case_kind": case_kind,
        "mutation_id": mutation_id,
        "expected": expected,
        "observed": observed,
        "outcome": "invalid_run",
        "include_paths": [str(path) for path in include_paths or []],
        "missing_includes": list(missing_includes or []),
        "spectre": {},
        "behavior_score": 0.0,
        "behavior_notes": notes,
        "side_output_ok": None,
        "side_output_note": "",
        "warning_lines": [],
        "benign_warning_lines": [],
        "untriaged_warning_lines": [],
        "wall_time_s": 0.0,
        "case_dir": "",
    }


def _behavior_evaluation_is_valid(notes: list[str]) -> bool:
    invalid_prefixes = (
        "behavior_eval_timeout>",
        "behavior_eval_no_result",
        "behavior_eval_error=",
        "missing_columns=",
        "empty_trace",
        "empty trace",
    )
    for note in notes:
        normalized = str(note).strip().lower()
        if normalized.startswith(invalid_prefixes):
            return False
        if re.match(r"^insufficient(?:_|\s).*coverage(?:$|[ =])", normalized):
            return False
    return True


def _run_correct_plus_five_case(
    *,
    task_id: str,
    case_id: str,
    case_kind: str,
    mutation_id: str,
    expected: str,
    checker_id: str,
    tb_path: Path,
    include_paths: list[Path],
    case_dir: Path,
    spectre_backend: str,
    spectre_mode: str,
    timeout_s: int,
    sui_host: str | None,
    sui_work_root: str | None,
    cadence_cshrc: str | None,
    keep_case_dirs: bool,
) -> dict[str, Any]:
    if case_dir.exists():
        shutil.rmtree(case_dir)
    started = time.perf_counter()
    spectre = run_spectre_case(
        task_id=f"{task_id}:{case_id}",
        tb_path=tb_path,
        include_paths=include_paths,
        output_dir=case_dir,
        bridge_repo=default_bridge_repo(),
        cadence_cshrc=cadence_cshrc,
        timeout_s=timeout_s,
        side_output_files=behavior_side_output_names(checker_id),
        spectre_backend=spectre_backend,
        sui_host=sui_host,
        sui_work_root=sui_work_root,
        spectre_mode=spectre_mode,
    )
    wall_time_s = round(time.perf_counter() - started, 3)
    csv_path = case_dir / "tran_spectre.csv"
    behavior_score = 0.0
    behavior_notes: list[str] = []
    side_output_ok: bool | None = None
    side_output_note = ""
    if not spectre.get("ok"):
        observed = "spectre_failed"
        behavior_notes = ["spectre did not complete successfully"]
    elif not csv_path.exists():
        observed = "trace_missing"
        behavior_notes = ["tran_spectre.csv missing after Spectre run"]
    else:
        behavior_score, behavior_notes = evaluate_behavior_with_timeout(
            checker_id,
            csv_path,
            timeout_s=timeout_s,
        )
        if not _behavior_evaluation_is_valid(behavior_notes):
            observed = "checker_invalid"
        else:
            side_validation = validate_behavior_side_outputs(checker_id, case_dir, csv_path)
            if side_validation is not None:
                side_output_ok, side_output_note = side_validation
            if side_output_ok is False:
                observed = "side_output_failed"
            elif behavior_score >= 1.0:
                observed = "behavior_pass"
            else:
                observed = "behavior_fail"

    if case_kind == "correct":
        if observed == "behavior_pass":
            outcome = "reference_pass"
        elif observed in {"behavior_fail", "side_output_failed"}:
            outcome = "reference_fail"
        else:
            outcome = "invalid_run"
    elif observed == "behavior_fail":
        outcome = "killed_behaviorally"
    elif observed == "behavior_pass":
        outcome = "survived"
    else:
        outcome = "invalid_run"

    warning_lines = extract_warning_lines(case_dir, spectre)
    benign_warnings = [line for line in warning_lines if is_benign_warning(line)]
    untriaged_warnings = [line for line in warning_lines if not is_benign_warning(line)]
    result = {
        "case_id": case_id,
        "case_kind": case_kind,
        "mutation_id": mutation_id,
        "expected": expected,
        "observed": observed,
        "outcome": outcome,
        "include_paths": [str(path) for path in include_paths],
        "missing_includes": [],
        "spectre": compact_spectre_result(spectre),
        "behavior_score": behavior_score,
        "behavior_notes": behavior_notes,
        "side_output_ok": side_output_ok,
        "side_output_note": side_output_note,
        "warning_lines": warning_lines,
        "benign_warning_lines": benign_warnings,
        "untriaged_warning_lines": untriaged_warnings,
        "wall_time_s": wall_time_s,
        "case_dir": str(case_dir) if keep_case_dirs else "",
    }
    return result


def run_correct_plus_mutations(
    *,
    release: Path,
    row: dict[str, Any],
    output_root: Path,
    spectre_backend: str,
    spectre_mode: str,
    timeout_s: int,
    spectre_runtime_id: str,
    sui_host: str | None,
    sui_work_root: str | None,
    cadence_cshrc: str | None,
    keep_case_dirs: bool,
) -> dict[str, Any]:
    task_id = str(row["task_id"])
    task_dir = release / str(row["task_dir"])
    task_eval = task_dir / "evaluator"
    task_record = read_json(task_dir / "task_record.json")
    tb_path = task_eval / "reference_tb.scs"
    base: dict[str, Any] = {
        "task_id": task_id,
        "task_dir": str(row["task_dir"]),
        "family_id": task_record.get("family_id"),
        "reference_tb": str(tb_path),
        "reference_gate": False,
        "killed_count": 0,
        "kill_denominator": 5,
        "survived_count": 0,
        "invalid_count": 0,
        "skipped_count": 0,
        "cases": [],
        "warning_lines": [],
        "benign_warning_lines": [],
        "untriaged_warning_lines": [],
    }
    try:
        checker_id = checker_task_id(task_dir, task_record)
    except RuntimeError as exc:
        return {**base, "status": "FAIL_CHECKER", "notes": [str(exc)]}
    base["checker_task_id"] = checker_id

    if not tb_path.is_file():
        return {
            **base,
            "status": "FAIL_MUTATION_SETUP",
            "notes": [f"reference testbench missing: {tb_path}"],
        }

    try:
        score_policy = read_json(task_eval / "score_policy.json")
    except (OSError, ValueError) as exc:
        return {
            **base,
            "status": "FAIL_MUTATION_SETUP",
            "notes": [f"score policy unavailable: {exc}"],
        }
    negative_ids = list(score_policy.get("negative_suite_mutation_ids") or [])
    valid_ids = all(isinstance(item, str) and item for item in negative_ids)
    if (
        len(negative_ids) != 5
        or not valid_ids
        or len(set(negative_ids)) != 5
        or score_policy.get("kill_ratio_denominator") != 5
    ):
        return {
            **base,
            "status": "FAIL_MUTATION_SETUP",
            "notes": [
                "score policy must declare exactly five unique negative IDs and a kill denominator of five"
            ],
        }

    task_output_dir = output_root / task_id
    if task_output_dir.exists():
        shutil.rmtree(task_output_dir)
    cases: list[dict[str, Any]] = []

    correct_paths, correct_missing = include_paths_for_reference_tb(task_dir, tb_path)
    correct_signature, correct_signature_sha256 = build_case_signature(
        release=release,
        row=row,
        task_dir=task_dir,
        task_record=task_record,
        case_id="correct",
        case_kind="correct",
        mutation_id="",
        checker_id=checker_id,
        tb_path=tb_path,
        include_paths=correct_paths,
        missing_includes=correct_missing,
        score_policy=score_policy,
        dut_root=task_dir / "public" / "supplied_dut",
        spectre_backend=spectre_backend,
        spectre_mode=spectre_mode,
        timeout_s=timeout_s,
        spectre_runtime_id=spectre_runtime_id,
        sui_host=sui_host,
        sui_work_root=sui_work_root,
        cadence_cshrc=cadence_cshrc,
    )
    if correct_missing:
        correct_case = _invalid_case(
            case_id="correct",
            case_kind="correct",
            mutation_id="",
            expected="behavior_pass",
            observed="setup_invalid",
            notes=[f"missing include: {item}" for item in correct_missing],
            include_paths=correct_paths,
            missing_includes=correct_missing,
        )
    else:
        correct_case = _run_correct_plus_five_case(
            task_id=task_id,
            case_id="correct",
            case_kind="correct",
            mutation_id="",
            expected="behavior_pass",
            checker_id=checker_id,
            tb_path=tb_path,
            include_paths=correct_paths,
            case_dir=task_output_dir / "correct",
            spectre_backend=spectre_backend,
            spectre_mode=spectre_mode,
            timeout_s=timeout_s,
            sui_host=sui_host,
            sui_work_root=sui_work_root,
            cadence_cshrc=cadence_cshrc,
            keep_case_dirs=keep_case_dirs,
        )
    attach_case_signature(correct_case, correct_signature, correct_signature_sha256)
    cases.append(correct_case)
    if correct_case["outcome"] != "reference_pass":
        warning_lines = list(correct_case["warning_lines"])
        return {
            **base,
            "status": "FAIL_REFERENCE",
            "reference_gate": False,
            "skipped_count": len(negative_ids),
            "cases": cases,
            "warning_lines": warning_lines,
            "benign_warning_lines": [line for line in warning_lines if is_benign_warning(line)],
            "untriaged_warning_lines": [
                line for line in warning_lines if not is_benign_warning(line)
            ],
            "wall_time_s": round(float(correct_case["wall_time_s"]), 3),
            "notes": ["negative cases skipped because the reference gate did not pass"],
        }

    mutation_root = task_eval / "mutation_bundles"
    for mutation_id in negative_ids:
        bundle_dir = mutation_root / mutation_id
        include_paths: list[Path] = []
        missing: list[str] = []
        if not bundle_dir.is_dir():
            case = _invalid_case(
                case_id=mutation_id,
                case_kind="negative",
                mutation_id=mutation_id,
                expected="behavior_fail",
                observed="setup_invalid",
                notes=[f"mutation bundle missing: {bundle_dir}"],
            )
        else:
            include_paths, missing = include_paths_for_reference_tb(
                task_dir,
                tb_path,
                dut_root=bundle_dir,
            )
        negative_signature, negative_signature_sha256 = build_case_signature(
            release=release,
            row=row,
            task_dir=task_dir,
            task_record=task_record,
            case_id=mutation_id,
            case_kind="negative",
            mutation_id=mutation_id,
            checker_id=checker_id,
            tb_path=tb_path,
            include_paths=include_paths,
            missing_includes=missing,
            score_policy=score_policy,
            dut_root=bundle_dir,
            spectre_backend=spectre_backend,
            spectre_mode=spectre_mode,
            timeout_s=timeout_s,
            spectre_runtime_id=spectre_runtime_id,
            sui_host=sui_host,
            sui_work_root=sui_work_root,
            cadence_cshrc=cadence_cshrc,
        )
        if not bundle_dir.is_dir():
            attach_case_signature(case, negative_signature, negative_signature_sha256)
            cases.append(case)
            continue
        if missing:
            case = _invalid_case(
                case_id=mutation_id,
                case_kind="negative",
                mutation_id=mutation_id,
                expected="behavior_fail",
                observed="setup_invalid",
                notes=[f"missing include: {item}" for item in missing],
                include_paths=include_paths,
                missing_includes=missing,
            )
        else:
            case = _run_correct_plus_five_case(
                task_id=task_id,
                case_id=mutation_id,
                case_kind="negative",
                mutation_id=mutation_id,
                expected="behavior_fail",
                checker_id=checker_id,
                tb_path=tb_path,
                include_paths=include_paths,
                case_dir=task_output_dir / mutation_id,
                spectre_backend=spectre_backend,
                spectre_mode=spectre_mode,
                timeout_s=timeout_s,
                sui_host=sui_host,
                sui_work_root=sui_work_root,
                cadence_cshrc=cadence_cshrc,
                keep_case_dirs=keep_case_dirs,
            )
        attach_case_signature(case, negative_signature, negative_signature_sha256)
        cases.append(case)

    reference_gate = correct_case["outcome"] == "reference_pass"
    negative_cases = cases[1:]
    killed_count = sum(case["outcome"] == "killed_behaviorally" for case in negative_cases)
    survived_count = sum(case["outcome"] == "survived" for case in negative_cases)
    invalid_count = sum(case["outcome"] == "invalid_run" for case in negative_cases)
    warning_lines = list(dict.fromkeys(line for case in cases for line in case["warning_lines"]))
    benign_warnings = [line for line in warning_lines if is_benign_warning(line)]
    untriaged_warnings = [line for line in warning_lines if not is_benign_warning(line)]
    if not reference_gate:
        status = "FAIL_REFERENCE"
    elif killed_count != 5:
        status = "FAIL_MUTATIONS"
    elif untriaged_warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"
    result = {
        **base,
        "status": status,
        "reference_gate": reference_gate,
        "killed_count": killed_count,
        "survived_count": survived_count,
        "invalid_count": invalid_count,
        "skipped_count": 0,
        "cases": cases,
        "warning_lines": warning_lines,
        "benign_warning_lines": benign_warnings,
        "untriaged_warning_lines": untriaged_warnings,
        "wall_time_s": round(sum(float(case["wall_time_s"]) for case in cases), 3),
        "notes": [],
    }
    if not keep_case_dirs and status == "PASS" and task_output_dir.exists():
        shutil.rmtree(task_output_dir)
    return result


def run_one(
    *,
    release: Path,
    row: dict[str, Any],
    output_root: Path,
    spectre_backend: str,
    spectre_mode: str,
    timeout_s: int,
    spectre_runtime_id: str,
    sui_host: str | None,
    sui_work_root: str | None,
    cadence_cshrc: str | None,
    keep_case_dirs: bool,
) -> dict[str, Any]:
    task_id = str(row["task_id"])
    task_dir = release / str(row["task_dir"])
    task_record = read_json(task_dir / "task_record.json")
    tb_path = task_dir / "evaluator" / "reference_tb.scs"
    try:
        checker_id = checker_task_id(task_dir, task_record)
    except RuntimeError as exc:
        return {
            "task_id": task_id,
            "task_dir": str(row["task_dir"]),
            "family_id": task_record.get("family_id"),
            "status": "FAIL_CHECKER",
            "notes": [str(exc)],
        }
    include_paths, missing_includes = include_paths_for_reference_tb(task_dir, tb_path)
    case_dir = output_root / task_id
    if case_dir.exists():
        shutil.rmtree(case_dir)

    base: dict[str, Any] = {
        "task_id": task_id,
        "task_dir": str(row["task_dir"]),
        "family_id": task_record.get("family_id"),
        "checker_task_id": checker_id,
        "reference_tb": str(tb_path),
        "include_paths": [str(path) for path in include_paths],
        "missing_includes": missing_includes,
    }
    if missing_includes:
        return {**base, "status": "FAIL_MISSING_INCLUDE", "notes": missing_includes}

    started = time.perf_counter()
    spectre = run_spectre_case(
        task_id=f"{task_id}:reference_tb",
        tb_path=tb_path,
        include_paths=include_paths,
        output_dir=case_dir,
        bridge_repo=default_bridge_repo(),
        cadence_cshrc=cadence_cshrc,
        timeout_s=timeout_s,
        side_output_files=behavior_side_output_names(checker_id),
        spectre_backend=spectre_backend,
        sui_host=sui_host,
        sui_work_root=sui_work_root,
        spectre_mode=spectre_mode,
    )
    wall_time_s = round(time.perf_counter() - started, 3)
    csv_path = case_dir / "tran_spectre.csv"
    behavior_score = 0.0
    behavior_notes: list[str] = []
    side_output_ok: bool | None = None
    side_output_note = ""
    if spectre.get("ok") and csv_path.exists():
        behavior_score, behavior_notes = evaluate_behavior_with_timeout(
            checker_id,
            csv_path,
            timeout_s=timeout_s,
        )
        side_validation = validate_behavior_side_outputs(checker_id, case_dir, csv_path)
        if side_validation is not None:
            side_output_ok, side_output_note = side_validation
    elif not spectre.get("ok"):
        behavior_notes = ["spectre did not complete successfully"]
    else:
        behavior_notes = ["tran_spectre.csv missing after Spectre run"]

    warning_lines = extract_warning_lines(case_dir, spectre)
    benign_warnings = [line for line in warning_lines if is_benign_warning(line)]
    untriaged_warnings = [line for line in warning_lines if not is_benign_warning(line)]
    if not spectre.get("ok"):
        status = "FAIL_SPECTRE"
    elif behavior_score < 1.0:
        status = "FAIL_BEHAVIOR"
    elif side_output_ok is False:
        status = "FAIL_SIDE_OUTPUT"
    elif untriaged_warnings:
        status = "PASS_WITH_WARNINGS"
    else:
        status = "PASS"

    result = {
        **base,
        "status": status,
        "wall_time_s": wall_time_s,
        "spectre": compact_spectre_result(spectre),
        "behavior_score": behavior_score,
        "behavior_notes": behavior_notes,
        "side_output_ok": side_output_ok,
        "side_output_note": side_output_note,
        "warning_lines": warning_lines,
        "benign_warning_lines": benign_warnings,
        "untriaged_warning_lines": untriaged_warnings,
        "case_dir": str(case_dir) if keep_case_dirs else "",
    }
    if not keep_case_dirs and status == "PASS" and case_dir.exists():
        shutil.rmtree(case_dir)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument("--spectre-backend", default="sui-direct")
    parser.add_argument("--spectre-mode", default="ax")
    parser.add_argument(
        "--spectre-runtime-id",
        default="spectre-21.1.0-64bit-2022-09-24-csvcm36c-4",
        help="Stable Spectre runtime identity to bind into reusable case signatures.",
    )
    parser.add_argument("--sui-host", default=default_remote_host("sui-direct"))
    parser.add_argument("--sui-work-root", default=default_remote_work_root("sui-direct"))
    parser.add_argument("--cadence-cshrc", default=default_remote_cadence_cshrc("sui-direct"))
    parser.add_argument("--keep-case-dirs", action="store_true")
    parser.add_argument(
        "--include-mutations",
        action="store_true",
        help="run the supplied correct DUT plus the five score-policy negative mutation bundles",
    )
    args = parser.parse_args(argv)

    release = args.release.expanduser().resolve()
    output_root = args.work_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    backend = normalize_spectre_backend(args.spectre_backend)
    mode = normalize_spectre_mode(args.spectre_mode)
    rows = resolve_task_rows(release, args.task_id)

    results: list[dict[str, Any]] = []
    started_at = now_utc()
    for row in rows:
        runner = run_correct_plus_mutations if args.include_mutations else run_one
        result = runner(
            release=release,
            row=row,
            output_root=output_root,
            spectre_backend=backend,
            spectre_mode=mode,
            timeout_s=args.timeout_s,
            spectre_runtime_id=args.spectre_runtime_id,
            sui_host=args.sui_host,
            sui_work_root=args.sui_work_root,
            cadence_cshrc=args.cadence_cshrc,
            keep_case_dirs=args.keep_case_dirs,
        )
        results.append(result)
        progress = [
            result["task_id"],
            result["status"],
            f"{result.get('wall_time_s', 0.0):.2f}s",
        ]
        if args.include_mutations:
            progress.extend(
                [
                    f"reference_gate={result.get('reference_gate', False)}",
                    f"killed={result.get('killed_count', 0)}/5",
                ]
            )
        else:
            progress.append(f"score={result.get('behavior_score', 0.0)}")
        progress.append(
            f"untriaged_warnings={len(result.get('untriaged_warning_lines') or [])}"
        )
        print(*progress, flush=True)

    pass_statuses = {"PASS", "PASS_WITH_WARNINGS"}
    summary = {
        "schema_version": (
            "v4-benchmarkv4-reference-spectre-correct-plus-five-audit-v1"
            if args.include_mutations
            else "v4-benchmarkv4-reference-spectre-audit-v1"
        ),
        "release": str(release),
        "started_at": started_at,
        "finished_at": now_utc(),
        "spectre_backend": backend,
        "spectre_mode": mode,
        "spectre_runtime_id": args.spectre_runtime_id,
        "timeout_s": args.timeout_s,
        "sui_host": args.sui_host or "",
        "sui_work_root": args.sui_work_root or "",
        "task_count": len(results),
        "pass_count": sum(1 for result in results if result.get("status") in pass_statuses),
        "fail_count": sum(1 for result in results if result.get("status") not in pass_statuses),
        "pass_with_warnings_count": sum(1 for result in results if result.get("status") == "PASS_WITH_WARNINGS"),
        "untriaged_warning_count": sum(len(result.get("untriaged_warning_lines") or []) for result in results),
        "results": results,
    }
    if args.include_mutations:
        summary["include_mutations"] = True
        summary["reference_gate_pass_count"] = sum(
            bool(result.get("reference_gate")) for result in results
        )
        summary["killed_count"] = sum(int(result.get("killed_count") or 0) for result in results)
        summary["kill_denominator"] = 5 * len(results)
    write_json(args.output.expanduser().resolve(), summary)
    print(
        json.dumps(
            {
                "task_count": summary["task_count"],
                "pass_count": summary["pass_count"],
                "fail_count": summary["fail_count"],
                "untriaged_warning_count": summary["untriaged_warning_count"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0 if summary["fail_count"] == 0 and summary["untriaged_warning_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

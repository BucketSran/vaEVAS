#!/usr/bin/env python3
"""Audit frozen calibration submissions with Spectre without rewriting campaign evidence."""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import re
import shutil
import sys
import tempfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
REPO = PACKAGE.parent
PACKAGE_RUNNERS = PACKAGE / "runners"
PACKAGE_SCRIPTS = PACKAGE / "scripts"
REPO_RUNNERS = REPO / "runners"

for import_dir in (HERE, PACKAGE_RUNNERS, PACKAGE_SCRIPTS, REPO_RUNNERS):
    if str(import_dir) not in sys.path:
        sys.path.insert(0, str(import_dir))

from derived_testbench_oracle import (  # noqa: E402
    CaseOutcome,
    CaseResult,
    _prepare_dut_sources,
    _trace_is_valid,
)
from feedback_oracle import (  # noqa: E402
    _copy_candidate_sources,
    _copy_public_support,
    _load_checker_profile,
    _load_tb_text,
    _validate_side_effect_contract,
)
from run_gold_dual_suite import (  # noqa: E402
    default_bridge_repo,
    default_remote_cadence_cshrc,
    default_remote_host,
    default_remote_work_root,
    normalize_spectre_backend,
    normalize_spectre_mode,
    run_spectre_case,
)
from simulate_evas import (  # noqa: E402
    behavior_side_output_names,
    evaluate_behavior_with_timeout,
)
from testbench_security import validate_testbench  # noqa: E402
from trusted_replay_adapter import (  # noqa: E402
    classify_testbench_result,
    mutation_bundle,
    resolve_release_task,
    staged_score_task,
    taxonomy,
    testbench_negative_suite,
)


SCHEMA_VERSION = "vabench-spectre-campaign-audit-v1"
DEFAULT_SPECTRE_RUNTIME_ID = "spectre-21.1.0.509.isr12"
MAX_SPECTRE_WORKERS = 48
SPECTRE_TRACE_CACHE_SCHEMA_VERSION = "vabench-spectre-trace-input-signature-v1"


@dataclass(frozen=True)
class SpectreConfig:
    backend: str = "bridge"
    mode: str = "ax"
    timeout_s: int = 600
    checker_timeout_s: int = 300
    runtime_id: str = DEFAULT_SPECTRE_RUNTIME_ID
    sui_host: str | None = None
    sui_work_root: str | None = None
    cadence_cshrc: str | None = None


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_relative_path(raw: str, *, label: str) -> PurePosixPath:
    relative = PurePosixPath(raw)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe {label} path: {raw!r}")
    return relative


def _verify_frozen_submission(
    runtime: Path,
    score_row: dict[str, Any],
) -> str:
    campaign_result = read_json(runtime / "evidence" / "campaign_result.json")
    cell = campaign_result.get("cell") or {}
    if cell.get("cell_id") != score_row.get("cell_id"):
        raise ValueError(
            f"campaign cell mismatch for {runtime.name}: "
            f"{cell.get('cell_id')!r} != {score_row.get('cell_id')!r}"
        )
    experiment = campaign_result.get("experiment_result") or {}
    submission = experiment.get("final_submission") or {}
    if submission.get("status") != "available":
        raise ValueError(f"frozen submission is unavailable for {runtime.name}")

    manifest: list[dict[str, str]] = []
    submission_root = runtime / "evidence" / "final_submission"
    for artifact in submission.get("artifacts") or []:
        relative = _safe_relative_path(str(artifact.get("path") or ""), label="artifact")
        path = submission_root.joinpath(*relative.parts)
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing frozen artifact for {runtime.name}: {relative}")
        observed_sha = sha256_file(path)
        expected_sha = str(artifact.get("sha256") or "")
        if observed_sha != expected_sha:
            raise ValueError(
                f"frozen artifact hash mismatch for {runtime.name}/{relative}: "
                f"{observed_sha} != {expected_sha}"
            )
        expected_bytes = artifact.get("bytes")
        if expected_bytes is not None and path.stat().st_size != int(expected_bytes):
            raise ValueError(f"frozen artifact size mismatch for {runtime.name}/{relative}")
        manifest.append({"path": relative.as_posix(), "sha256": observed_sha})

    observed_tree = canonical_sha256(manifest)
    expected_trees = {
        str(value)
        for value in (
            submission.get("tree_sha256"),
            (score_row.get("trusted_replay") or {}).get("submission_tree_sha256"),
        )
        if value
    }
    if expected_trees != {observed_tree}:
        raise ValueError(
            f"frozen submission tree mismatch for {runtime.name}: "
            f"observed={observed_tree} expected={sorted(expected_trees)}"
        )
    return observed_tree


def build_audit_plan(
    *,
    score_path: Path,
    campaign_run: Path,
    freeze_manifest: Path,
    source_outcomes: set[str],
    cell_ids: set[str],
) -> list[dict[str, Any]]:
    """Load and verify immutable inputs, returning selected Spectre audit cells."""
    score_path = score_path.expanduser().resolve()
    campaign_run = campaign_run.expanduser().resolve()
    freeze_manifest = freeze_manifest.expanduser().resolve()
    freeze = read_json(freeze_manifest)
    if freeze.get("schema_version") != "vabench-spectre-audit-freeze-v1":
        raise ValueError("unsupported or missing Spectre audit freeze schema")
    policy = freeze.get("audit_policy") or {}
    if policy.get("do_not_overwrite_frozen_score") is not True:
        raise ValueError("freeze manifest does not protect the source score")

    experiment_root = Path(str(freeze["experiment_root"])).expanduser().resolve()
    expected_score = (experiment_root / str(freeze["score_report"]["path"])).resolve()
    if score_path != expected_score:
        raise ValueError(f"score path is not the frozen report: {score_path} != {expected_score}")
    observed_score_sha = sha256_file(score_path)
    expected_score_sha = str(freeze["score_report"].get("sha256") or "")
    if observed_score_sha != expected_score_sha:
        raise ValueError(
            f"frozen score hash mismatch: {observed_score_sha} != {expected_score_sha}"
        )
    expected_campaign_run = (
        experiment_root / str(freeze["master_output"]) / "run"
    ).resolve()
    if campaign_run != expected_campaign_run:
        raise ValueError(
            f"campaign run is not the frozen master output: "
            f"{campaign_run} != {expected_campaign_run}"
        )

    score = read_json(score_path)
    rows = score.get("rows") or []
    if not isinstance(rows, list):
        raise ValueError("frozen score rows must be a list")
    expected_rows = int(freeze["score_report"].get("rows") or 0)
    if len(rows) != expected_rows:
        raise ValueError(f"frozen score row count mismatch: {len(rows)} != {expected_rows}")

    selected: list[dict[str, Any]] = []
    known_ids = {str(row.get("cell_id") or "") for row in rows}
    unknown_ids = sorted(cell_ids - known_ids)
    if unknown_ids:
        raise ValueError(f"unknown requested cell IDs: {', '.join(unknown_ids)}")
    for row in rows:
        cell_id = str(row.get("cell_id") or "")
        if cell_ids and cell_id not in cell_ids:
            continue
        if source_outcomes and str(row.get("outcome") or "") not in source_outcomes:
            continue
        runtime = campaign_run / cell_id
        submission_tree = _verify_frozen_submission(runtime, row)
        selected.append(
            {
                "cell_id": cell_id,
                "runtime": runtime,
                "submission_tree_sha256": submission_tree,
                "score_row": row,
            }
        )
    return selected


def _compact_spectre_result(
    result: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, Any]:
    observed_version = ""
    if output_dir is not None:
        spectre_log = output_dir / "spectre.out"
        if spectre_log.is_file():
            head = spectre_log.read_text(
                encoding="utf-8",
                errors="replace",
            )[:2000]
            match = re.search(r"(?m)^Version\s+([^\n]+)$", head)
            if match:
                observed_version = match.group(1).strip()
    return {
        "ok": bool(result.get("ok")),
        "status": str(result.get("status") or ""),
        "errors": [str(item) for item in result.get("errors") or []],
        "warnings": [str(item) for item in result.get("warnings") or []],
        "rows": int(result.get("rows") or 0),
        "signals": [str(item) for item in result.get("signals") or []],
        "spectre_backend": str(result.get("spectre_backend") or ""),
        "spectre_mode": str(result.get("spectre_mode") or ""),
        "observed_version": observed_version,
        "timing": result.get("timing") or {},
        "stdout_tail": str(result.get("stdout_tail") or "")[-4000:],
    }


def _spectre_failure_kind(result: dict[str, Any]) -> str:
    text = "\n".join(
        [
            *(str(item) for item in result.get("errors") or []),
            str(result.get("stdout_tail") or ""),
        ]
    ).lower()
    infrastructure_markers = (
        "remote_workdir_",
        "remote_upload_",
        "remote_download_",
        "spectre_license_checkout_failed",
        "required license could not be checked out",
        "psf_parse_failed",
        "spectre_raw_missing",
        "ssh:",
        "connection refused",
        "connection timed out",
        "no route to host",
        "could not resolve hostname",
        "connection closed by unknown port",
        "labctl_exception",
        "sui_direct_exception",
    )
    if any(marker in text for marker in infrastructure_markers):
        return "infrastructure"
    compile_markers = (
        "during circuit read-in",
        "during ahdl read-in",
        "syntax error",
        "sfe-",
        "vacomp-",
        "failed to compile",
        "undefined model",
        "undefined subcircuit",
        "file not found",
        "cannot open include",
    )
    if any(marker in text for marker in compile_markers):
        return "compile"
    return "runtime"


def _candidate_has_ungrounded_voltage_source_component(tb_path: Path) -> bool:
    """Return whether a candidate vsource graph has no path to ground."""

    try:
        lines = tb_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False

    ground_nodes = {"0"}
    edges: list[tuple[str, str]] = []
    for raw_line in lines:
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        global_match = re.match(
            r"(?i)^global\s+(?:\(\s*)?([^()\s]+)",
            line,
        )
        if global_match is not None:
            ground_nodes.add(global_match.group(1))
        if re.search(r"(?i)\bvsource\b", line) is None:
            continue
        terminals = re.search(r"\(([^()]*)\)", line)
        if terminals is not None:
            nodes = terminals.group(1).split()
            if len(nodes) >= 2:
                edges.append((nodes[0], nodes[1]))
            continue
        tokens = line.split()
        primitive_indexes = [
            index
            for index, token in enumerate(tokens)
            if token.lower() == "vsource"
        ]
        if primitive_indexes and primitive_indexes[-1] >= 3:
            index = primitive_indexes[-1]
            edges.append((tokens[index - 2], tokens[index - 1]))

    if not edges:
        return False

    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for left, right in edges:
        union(left, right)
    grounded_roots = {
        find(node)
        for node in ground_nodes
        if node in parent
    }
    return any(find(left) not in grounded_roots for left, _right in edges)


def _spectre_added_ground_gmin(
    result: dict[str, Any],
    tb_path: Path,
    output_dir: Path | None = None,
) -> bool:
    """Detect Spectre's fallback on an actually ungrounded source graph."""

    sources = [
        *(str(item) for item in result.get("errors") or []),
        *(str(item) for item in result.get("warnings") or []),
        str(result.get("stdout_tail") or ""),
    ]
    if output_dir is not None:
        spectre_log = output_dir / "spectre.out"
        if spectre_log.is_file():
            sources.append(
                spectre_log.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )
    text = "\n".join(sources).lower()
    warning_present = (
        "spectre-470" in text
        and "no ground node was found in the netlist" in text
    )
    return (
        warning_present
        and _candidate_has_ungrounded_voltage_source_component(tb_path)
    )


_TIME_UNIT_SECONDS = {
    "": 1.0,
    "s": 1.0,
    "f": 1e-15,
    "fs": 1e-15,
    "p": 1e-12,
    "ps": 1e-12,
    "n": 1e-9,
    "ns": 1e-9,
    "u": 1e-6,
    "us": 1e-6,
    "m": 1e-3,
    "ms": 1e-3,
}


def _time_literal_seconds(value: str, unit: str | None) -> float | None:
    try:
        numeric = float(value)
    except ValueError:
        return None
    scale = _TIME_UNIT_SECONDS.get((unit or "").strip().lower())
    if scale is None:
        return None
    return numeric * scale


def _requested_tran_maxstep_s(tb_path: Path) -> float | None:
    try:
        text = tb_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    values: list[float] = []
    for match in re.finditer(
        r"(?i)\btran\b[^\n]*\bmaxstep\s*=\s*"
        r"([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)\s*"
        r"(fs|ps|ns|us|ms|s|f|p|n|u|m)?\b",
        text,
    ):
        seconds = _time_literal_seconds(match.group(1), match.group(2))
        if seconds is not None:
            values.append(seconds)
    return min(values) if values else None


def _spectre_output_text(
    result: dict[str, Any],
    output_dir: Path | None = None,
) -> str:
    sources = [
        *(str(item) for item in result.get("errors") or []),
        *(str(item) for item in result.get("warnings") or []),
        str(result.get("stdout_tail") or ""),
    ]
    if output_dir is not None:
        spectre_log = output_dir / "spectre.out"
        if spectre_log.is_file():
            sources.append(
                spectre_log.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            )
    return "\n".join(sources)


def _effective_spectre_maxstep_s(text: str) -> float | None:
    values: list[float] = []
    for match in re.finditer(
        r"(?i)\bmaxstep\b\s*=?\s*"
        r"([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)\s*"
        r"(fs|ps|ns|us|ms|s|f|p|n|u|m)?\b",
        text,
    ):
        seconds = _time_literal_seconds(match.group(1), match.group(2))
        if seconds is not None:
            values.append(seconds)
    return max(values) if values else None


def _spectre_oracle_config_issue(
    tb_path: Path,
    result: dict[str, Any],
    output_dir: Path | None = None,
) -> list[str]:
    text = _spectre_output_text(result, output_dir)
    if "SPECTRE-592" not in text:
        return []
    requested_s = _requested_tran_maxstep_s(tb_path)
    effective_s = _effective_spectre_maxstep_s(text)
    if requested_s is None or effective_s is None:
        return []
    if effective_s <= requested_s * (1.0 + 1e-9):
        return []
    return [
        (
            "Spectre sidecar is not a semantic oracle: SPECTRE-592 changed "
            f"the effective maxstep from requested <= {requested_s:.6g}s "
            f"to {effective_s:.6g}s"
        ),
        "rerun required under Classic Spectre or an honored maxstep backend",
    ]


def _invalid_oracle_config_case(
    case_id: str,
    role: str,
    spectre: dict[str, Any],
    notes: list[str],
) -> tuple[dict[str, Any], CaseResult]:
    prefixed = [f"{case_id}: {note}" for note in notes]
    case = {
        "case_id": case_id,
        "role": role,
        "outcome": "invalid_run",
        "responsibility": "system",
        "failure_kind": "invalid_oracle_config",
        "behavior_score": None,
        "behavior_notes": prefixed,
        "spectre": spectre,
    }
    return case, CaseResult(
        case_id,
        role,
        CaseOutcome.INVALID_RUN,
        tuple(prefixed),
    )


def _no_ground_case(
    case_id: str,
    role: str,
    spectre: dict[str, Any],
) -> tuple[dict[str, Any], CaseResult]:
    notes = [
        (
            f"{case_id}: invalid candidate testbench source topology; "
            "Spectre added gmin because the netlist has no ground node"
        ),
        "WARNING (SPECTRE-470): No ground node was found in the netlist",
    ]
    case = {
        "case_id": case_id,
        "role": role,
        "outcome": "invalid_run",
        "responsibility": "candidate",
        "failure_kind": "floating_source_reference",
        "behavior_score": None,
        "behavior_notes": notes,
        "spectre": spectre,
    }
    return case, CaseResult(
        case_id,
        role,
        CaseOutcome.INVALID_RUN,
        tuple(notes),
    )


def _spectre_failure_notes(
    case_id: str,
    result: dict[str, Any],
    kind: str,
    output_dir: Path | None = None,
) -> list[str]:
    details = [str(item) for item in result.get("errors") or []]
    diagnostic = re.compile(
        r"\b(error|fatal|failed|failure|syntax|undefined|cannot|invalid|"
        r"not found|convergence|singular|timestep|time step)\b|"
        r"\b(?:SFE|VACOMP|SPECTRE)-\d+",
        flags=re.IGNORECASE,
    )
    sources: list[str] = []
    if output_dir is not None:
        spectre_log = output_dir / "spectre.out"
        if spectre_log.is_file():
            sources.extend(
                spectre_log.read_text(
                    encoding="utf-8",
                    errors="replace",
                ).splitlines()
            )
    sources.extend(str(result.get("stdout_tail") or "").splitlines())
    selected: list[str] = []
    for index, line in enumerate(sources):
        if diagnostic.search(line) is None:
            continue
        for nearby in sources[max(0, index - 1) : min(len(sources), index + 2)]:
            value = nearby.strip()
            if value and value not in selected:
                selected.append(value)
    details.extend(selected)
    compact = list(dict.fromkeys(details))[:24]
    headline = (
        f"{case_id}: Failed to compile Verilog-A/Spectre case"
        if kind == "compile"
        else f"{case_id}: Spectre {kind} failure"
    )
    return [headline, *compact]


def _behavior_evaluation_is_valid(notes: list[str]) -> bool:
    invalid_prefixes = (
        "behavior_eval_timeout>",
        "behavior_eval_no_result",
        "behavior_eval_error=",
        "missing_columns=",
        "empty_trace",
        "empty trace",
    )
    return not any(
        str(note).strip().lower().startswith(invalid_prefixes) for note in notes
    )


def _behavior_evaluation_failure_kind(notes: list[str]) -> str:
    if any(
        str(note).strip().lower().startswith("behavior_eval_timeout>")
        for note in notes
    ):
        return "checker_timeout"
    return "infrastructure"


def _semantic_eligibility(
    outcome: str,
    failure_taxonomy: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Return whether a sidecar result belongs in a semantic denominator."""
    if outcome == "infrastructure_failure":
        return False, "retryable_infrastructure"
    if outcome == "runtime_failure":
        stage = str((failure_taxonomy or {}).get("stage") or "")
        if stage == "simulation":
            return False, "unresolved_simulation_runtime"
    return True, "semantic_result"


def _source_outcome_is_semantic(outcome: str) -> bool:
    return outcome in {"passed", "compile_failure", "behavior_failure"}


def _pass_impact(row: dict[str, Any]) -> tuple[int, str]:
    """Separate Pass changes from provenance/attribution-only transitions."""
    source = str(row.get("source_outcome") or "")
    observed = str(row.get("outcome") or "")
    eligible, _reason = _semantic_eligibility(
        observed,
        row.get("failure_taxonomy")
        if isinstance(row.get("failure_taxonomy"), dict)
        else None,
    )
    if source == observed:
        return 0, "unchanged"
    if source == "passed" and eligible:
        return -1, "confirmed_pass_loss"
    if observed == "passed" and _source_outcome_is_semantic(source):
        return 1, "confirmed_pass_gain"
    if observed == "passed":
        return 0, "provenance_resolution_to_pass"
    if source != "passed" and observed != "passed":
        return 0, "attribution_only_nonpass_reclassification"
    return 0, "unresolved_nonsemantic_transition"


def _default_simulate_case(
    *,
    cell_id: str,
    case_id: str,
    tb_path: Path,
    include_paths: list[Path],
    output_dir: Path,
    required_signals: set[str],
    side_output_files: tuple[str, ...] = (),
    config: SpectreConfig,
) -> dict[str, Any]:
    del required_signals
    backend = normalize_spectre_backend(config.backend)
    if backend == "bridge":
        bridge_repo = default_bridge_repo()
        bridge_python = bridge_repo / ".venv" / "bin" / "python"
        if not bridge_repo.is_dir() or not bridge_python.is_file():
            raise FileNotFoundError(
                f"bridge-lite preflight failed: missing {bridge_python}"
            )
    return run_spectre_case(
        task_id=f"{cell_id}:{case_id}",
        tb_path=tb_path,
        include_paths=include_paths,
        output_dir=output_dir,
        bridge_repo=default_bridge_repo(),
        cadence_cshrc=(
            config.cadence_cshrc
            if config.cadence_cshrc is not None
            else default_remote_cadence_cshrc(backend)
        ),
        timeout_s=config.timeout_s,
        side_output_files=side_output_files,
        spectre_backend=backend,
        sui_host=(
            config.sui_host
            if config.sui_host is not None
            else default_remote_host(backend)
        ),
        sui_work_root=(
            config.sui_work_root
            if config.sui_work_root is not None
            else default_remote_work_root(backend)
        ),
        spectre_mode=normalize_spectre_mode(config.mode),
    )


def _spectre_trace_implementation_sha256() -> dict[str, str]:
    """Bind cached traces to trace generation, excluding checker-only code."""
    return {
        "default_simulate_case": canonical_sha256(
            {
                "trace_cache_schema_version": SPECTRE_TRACE_CACHE_SCHEMA_VERSION,
                "source": inspect.getsource(_default_simulate_case),
            }
        ),
        "run_gold_dual_suite.py": sha256_file(
            REPO_RUNNERS / "run_gold_dual_suite.py"
        ),
    }


def _run_or_reuse_spectre_trace(
    *,
    cell_id: str,
    case_id: str,
    tb_path: Path,
    include_paths: list[Path],
    requested_output_dir: Path,
    trace_cache_root: Path | None,
    required_signals: set[str],
    side_output_files: tuple[str, ...],
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any], Path, bool]:
    """Cache successful simulator evidence independently of checker outcomes."""
    output_dir = requested_output_dir
    cache_result_path: Path | None = None
    if trace_cache_root is not None:
        backend = normalize_spectre_backend(config.backend)
        signature = {
            "schema_version": SPECTRE_TRACE_CACHE_SCHEMA_VERSION,
            "cell_id": cell_id,
            "case_id": case_id,
            "trace_implementation_sha256": (
                _spectre_trace_implementation_sha256()
            ),
            "tb_sha256": sha256_file(tb_path),
            "include_manifest": [
                {
                    "path": path.relative_to(tb_path.parent).as_posix(),
                    "sha256": sha256_file(path),
                }
                for path in sorted(include_paths)
            ],
            "required_signals": sorted(required_signals),
            "side_output_files": list(side_output_files),
            "spectre_run_config": {
                "backend": backend,
                "mode": normalize_spectre_mode(config.mode),
                "timeout_s": config.timeout_s,
                "runtime_id": config.runtime_id,
                "host": config.sui_host or default_remote_host(backend),
                "work_root": config.sui_work_root or default_remote_work_root(backend),
                "cadence_cshrc": config.cadence_cshrc
                or default_remote_cadence_cshrc(backend),
            },
        }
        signature_sha = canonical_sha256(signature)
        output_dir = trace_cache_root / signature_sha
        cache_result_path = output_dir / "spectre_trace_result.json"
        trace_path = output_dir / "tran_spectre.csv"
        if cache_result_path.is_file() and trace_path.is_file():
            cached = read_json(cache_result_path)
            if (
                cached.get("input_signature") == signature
                and cached.get("input_signature_sha256") == signature_sha
                and (cached.get("spectre") or {}).get("ok") is True
            ):
                return dict(cached["spectre"]), output_dir, True

    spectre = simulate_case(
        cell_id=cell_id,
        case_id=case_id,
        tb_path=tb_path,
        include_paths=include_paths,
        output_dir=output_dir,
        required_signals=required_signals,
        side_output_files=side_output_files,
        config=config,
    )
    if (
        cache_result_path is not None
        and spectre.get("ok") is True
        and (output_dir / "tran_spectre.csv").is_file()
    ):
        write_json_atomic(
            cache_result_path,
            {
                "input_signature": signature,
                "input_signature_sha256": signature_sha,
                "spectre": spectre,
            },
        )
    return spectre, output_dir, False


def _testbench_case(
    *,
    runtime: Path,
    cell_id: str,
    tb_source: Path,
    source_eval: Path,
    public_contract: dict[str, Any],
    target_artifacts: list[str],
    negative_bundle: Path | None,
    checker_task_id: str,
    required_signals: set[str],
    case_id: str,
    output_dir: Path,
    trace_cache_root: Path | None,
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]],
    behavior_evaluator: Callable[..., tuple[float, list[str]]],
) -> tuple[dict[str, Any], CaseResult]:
    role = "reference" if negative_bundle is None else "negative"
    case_result_path = output_dir / "case_audit_result.json"
    if case_result_path.is_file():
        try:
            cached = read_json(case_result_path)
            if (
                cached.get("case_cache_schema_version")
                == "vabench-spectre-case-cache-v1"
                and cached.get("case_id") == case_id
                and cached.get("role") == role
                and cached.get("responsibility") != "system"
            ):
                if _spectre_added_ground_gmin(
                    cached.get("spectre") or {},
                    tb_source,
                    output_dir,
                ):
                    normalized, oracle = _no_ground_case(
                        case_id,
                        role,
                        cached.get("spectre") or {},
                    )
                    cached.update(normalized)
                    cached["case_cache_schema_version"] = (
                        "vabench-spectre-case-cache-v1"
                    )
                    cached["resumed_case"] = True
                    return cached, oracle
                cached_outcome = CaseOutcome(str(cached["outcome"]))
                cached["resumed_case"] = True
                notes = tuple(
                    str(note) for note in cached.get("behavior_notes") or []
                )
                return cached, CaseResult(
                    case_id,
                    role,
                    cached_outcome,
                    notes,
                )
        except (KeyError, OSError, ValueError, json.JSONDecodeError):
            pass

    def finish(
        case: dict[str, Any],
        oracle: CaseResult,
    ) -> tuple[dict[str, Any], CaseResult]:
        case["case_cache_schema_version"] = "vabench-spectre-case-cache-v1"
        case["resumed_case"] = False
        write_json_atomic(case_result_path, case)
        return case, oracle

    with tempfile.TemporaryDirectory(prefix=f"v4_spectre_{cell_id}_{case_id}_") as td:
        run_dir = Path(td)
        tb_dst = run_dir / "tb_candidate.scs"
        shutil.copy2(tb_source, tb_dst)
        try:
            _prepare_dut_sources(
                package_root=PACKAGE,
                source_formal=source_eval,
                run_dir=run_dir,
                target_artifacts=target_artifacts,
                negative_bundle=negative_bundle,
                dut_subdir="dut",
                public_contract=public_contract,
            )
        except (OSError, SystemExit, ValueError) as exc:
            notes = [f"{case_id}: frozen DUT staging failed: {type(exc).__name__}: {exc}"]
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "system",
                "failure_kind": "infrastructure",
                "behavior_score": None,
                "behavior_notes": notes,
                "spectre": {},
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )

        include_paths = sorted(path for path in run_dir.rglob("*.va") if path.is_file())
        try:
            spectre, output_dir, trace_reused = _run_or_reuse_spectre_trace(
                cell_id=cell_id,
                case_id=case_id,
                tb_path=tb_dst,
                include_paths=include_paths,
                requested_output_dir=output_dir,
                trace_cache_root=trace_cache_root,
                required_signals=required_signals,
                side_output_files=(),
                config=config,
                simulate_case=simulate_case,
            )
        except Exception as exc:
            notes = [
                f"{case_id}: Spectre infrastructure failure",
                f"{type(exc).__name__}: {str(exc)[:500]}",
            ]
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "system",
                "failure_kind": "infrastructure",
                "behavior_score": None,
                "behavior_notes": notes,
                "spectre": {},
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )

        compact = _compact_spectre_result(spectre, output_dir)
        if _spectre_added_ground_gmin(compact, tb_dst, output_dir):
            case, oracle = _no_ground_case(case_id, role, compact)
            return finish(case, oracle)
        oracle_config_notes = _spectre_oracle_config_issue(
            tb_dst,
            compact,
            output_dir,
        )
        if oracle_config_notes:
            case, oracle = _invalid_oracle_config_case(
                case_id,
                role,
                compact,
                oracle_config_notes,
            )
            return finish(case, oracle)
        if not spectre.get("ok"):
            kind = _spectre_failure_kind(spectre)
            notes = _spectre_failure_notes(
                case_id,
                spectre,
                kind,
                output_dir,
            )
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "system" if kind == "infrastructure" else "candidate",
                "failure_kind": kind,
                "behavior_score": None,
                "behavior_notes": notes,
                "spectre": compact,
                "spectre_trace_reused": trace_reused,
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )

        csv_path = output_dir / "tran_spectre.csv"
        if not csv_path.is_file():
            notes = [f"{case_id}: Spectre completed without a transient trace"]
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "system",
                "failure_kind": "infrastructure",
                "behavior_score": None,
                "behavior_notes": notes,
                "spectre": compact,
                "spectre_trace_reused": trace_reused,
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )
        trace_valid, trace_notes = _trace_is_valid(csv_path, required_signals)
        if not trace_valid:
            notes = [f"{case_id}: {note}" for note in trace_notes]
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "candidate",
                "failure_kind": "runtime",
                "behavior_score": None,
                "behavior_notes": notes,
                "spectre": compact,
                "spectre_trace_reused": trace_reused,
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )
        try:
            score, behavior_notes = behavior_evaluator(
                checker_task_id,
                csv_path,
                timeout_s=config.checker_timeout_s,
            )
        except Exception as exc:
            score = 0.0
            behavior_notes = [
                f"behavior_eval_error={type(exc).__name__}: {str(exc)[:500]}"
            ]
        behavior_notes = [str(note) for note in behavior_notes]
        if not _behavior_evaluation_is_valid(behavior_notes):
            notes = [f"{case_id}: {note}" for note in behavior_notes]
            failure_kind = _behavior_evaluation_failure_kind(behavior_notes)
            case = {
                "case_id": case_id,
                "role": role,
                "outcome": "invalid_run",
                "responsibility": "system",
                "failure_kind": failure_kind,
                "behavior_score": score,
                "behavior_notes": notes,
                "spectre": compact,
                "spectre_trace_reused": trace_reused,
            }
            return finish(
                case,
                CaseResult(case_id, role, CaseOutcome.INVALID_RUN, tuple(notes)),
            )

        behavior_pass = score >= 1.0
        if role == "reference":
            outcome = (
                CaseOutcome.REFERENCE_PASS
                if behavior_pass
                else CaseOutcome.REFERENCE_FAIL
            )
        else:
            outcome = (
                CaseOutcome.SURVIVED
                if behavior_pass
                else CaseOutcome.KILLED_BEHAVIORALLY
            )
        notes = [f"{case_id}: {note}" for note in behavior_notes]
        case = {
            "case_id": case_id,
            "role": role,
            "outcome": outcome.value,
            "responsibility": "candidate",
            "failure_kind": None,
            "behavior_score": score,
            "behavior_notes": notes,
            "spectre": compact,
            "spectre_trace_reused": trace_reused,
        }
        return finish(case, CaseResult(case_id, role, outcome, tuple(notes)))


def _audit_testbench_cell(
    *,
    runtime: Path,
    score_row: dict[str, Any],
    submission_tree_sha256: str,
    cell_output: Path,
    trace_cache_root: Path | None,
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]],
    behavior_evaluator: Callable[..., tuple[float, list[str]]],
) -> dict[str, Any]:
    cell_id = str(score_row["cell_id"])
    source_eval = runtime / "evaluator"
    record = read_json(source_eval / "task_record.json")
    release_task = resolve_release_task(runtime, record)
    public_contract_path = release_task / "public_contract.json"
    public_contract = read_json(public_contract_path)
    family_spec = read_json(source_eval / "family_spec.json")
    checker = read_json(source_eval / "checker_profile.json")
    mutation_ids = testbench_negative_suite(source_eval)
    target_artifacts = [
        str(item["path"])
        for item in (family_spec.get("artifact_contract") or {}).get("files") or []
    ]
    if not target_artifacts:
        raise ValueError("family_spec declares no DUT target artifacts")
    checker_task_id = str(checker["checker_task_id"])
    required_signals = {
        str(item)
        for item in (checker.get("trace_contract") or {}).get("required_signals") or []
    }
    return _finish_testbench_audit(
        runtime=runtime,
        score_row=score_row,
        submission_tree_sha256=submission_tree_sha256,
        cell_output=cell_output,
        trace_cache_root=trace_cache_root,
        config=config,
        simulate_case=simulate_case,
        behavior_evaluator=behavior_evaluator,
        cell_id=cell_id,
        source_eval=source_eval,
        public_contract_path=public_contract_path,
        public_contract=public_contract,
        target_artifacts=target_artifacts,
        checker_task_id=checker_task_id,
        required_signals=required_signals,
        mutation_ids=mutation_ids,
    )


def _evaluator_tree_sha256(source_eval: Path) -> str:
    return canonical_sha256(
        [
            {
                "path": path.relative_to(source_eval).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in sorted(source_eval.rglob("*"))
            if path.is_file() and not path.is_symlink()
        ]
    )


def _audit_dut_cell(
    *,
    runtime: Path,
    score_row: dict[str, Any],
    submission_tree_sha256: str,
    cell_output: Path,
    trace_cache_root: Path | None,
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]],
    behavior_evaluator: Callable[..., tuple[float, list[str]]],
) -> dict[str, Any]:
    cell_id = str(score_row["cell_id"])
    form = str(score_row["form"])
    source_eval = runtime / "evaluator"
    record = read_json(source_eval / "task_record.json")
    release_task = resolve_release_task(runtime, record)
    public_contract_path = release_task / "public_contract.json"
    submission = runtime / "evidence" / "final_submission"
    base = {
        "schema_version": SCHEMA_VERSION,
        "completed_at": now_utc(),
        "cell_id": cell_id,
        "family_id": score_row.get("family_id"),
        "form": form,
        "mode": score_row.get("mode"),
        "experimental_arm": score_row.get("experimental_arm"),
        "source_outcome": score_row.get("outcome"),
        "submission_tree_sha256": submission_tree_sha256,
        "frozen_evaluator_tree_sha256": _evaluator_tree_sha256(source_eval),
        "public_contract_sha256": sha256_file(public_contract_path),
        "spectre_identity": {
            "runtime_id": config.runtime_id,
            "backend": normalize_spectre_backend(config.backend),
            "mode": normalize_spectre_mode(config.mode),
            "host": config.sui_host or default_remote_host(config.backend),
        },
    }

    with tempfile.TemporaryDirectory(prefix=f"v4_spectre_{cell_id}_") as td:
        try:
            task = staged_score_task(runtime, release_task, Path(td))
            contract = read_json(task / "public_contract.json")
            checker_profile = _load_checker_profile(task)
            checker_task_id = str(checker_profile.get("checker_task_id") or "")
            expected_files = [
                str(item) for item in contract.get("target_artifacts") or []
            ]
            run_dir = Path(td) / "spectre_input"
            run_dir.mkdir()
            tb_text, generated_harness = _load_tb_text(task, "score")
            _copy_candidate_sources(
                submission,
                run_dir,
                expected_files,
                generated_harness=generated_harness,
            )
            _copy_public_support(task, submission, run_dir, expected_files)
            tb_dst = run_dir / "tb_score.scs"
            tb_dst.write_text(tb_text, encoding="utf-8")
        except (OSError, SystemExit, ValueError) as exc:
            diagnostics = [f"frozen score staging failed: {type(exc).__name__}: {exc}"]
            return {
                **base,
                "outcome": "compile_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy("compile", "compilation"),
                "checker_task_id": str(record.get("checker_task_id") or ""),
                "cases": [],
            }

        required_signals: set[str] = set()
        for line in tb_text.splitlines():
            if line.strip().startswith("save "):
                required_signals.update(line.split()[1:])
        trace_contract = checker_profile.get("trace_contract") or {}
        required_signals.update(
            str(signal) for signal in trace_contract.get("required_signals") or []
        )
        required_signals.update(
            str(signal) for signal in trace_contract.get("extra_trace_signals") or []
        )
        include_paths = sorted(
            path for path in run_dir.rglob("*.va") if path.is_file()
        )
        output_dir = cell_output / "cases" / "score"
        try:
            spectre, output_dir, trace_reused = _run_or_reuse_spectre_trace(
                cell_id=cell_id,
                case_id="score",
                tb_path=tb_dst,
                include_paths=include_paths,
                requested_output_dir=output_dir,
                trace_cache_root=trace_cache_root,
                required_signals=required_signals,
                side_output_files=behavior_side_output_names(checker_task_id),
                config=config,
                simulate_case=simulate_case,
            )
        except Exception as exc:
            diagnostics = [
                "score: Spectre infrastructure failure",
                f"{type(exc).__name__}: {str(exc)[:500]}",
            ]
            return {
                **base,
                "outcome": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "infrastructure",
                    case_ids=["score"],
                    retryable=True,
                    responsibility="system",
                ),
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": "system",
                        "failure_kind": "infrastructure",
                        "spectre": {},
                        "behavior_score": None,
                        "behavior_notes": diagnostics,
                    }
                ],
            }

        compact = _compact_spectre_result(spectre, output_dir)
        oracle_config_notes = _spectre_oracle_config_issue(
            tb_dst,
            compact,
            output_dir,
        )
        if oracle_config_notes:
            diagnostics = [f"score: {note}" for note in oracle_config_notes]
            return {
                **base,
                "outcome": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "invalid_oracle_config",
                    case_ids=["score"],
                    retryable=True,
                    responsibility="system",
                ),
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": "system",
                        "failure_kind": "invalid_oracle_config",
                        "spectre": compact,
                        "spectre_trace_reused": trace_reused,
                        "behavior_score": None,
                        "behavior_notes": diagnostics,
                    }
                ],
            }
        if not spectre.get("ok"):
            kind = _spectre_failure_kind(spectre)
            diagnostics = _spectre_failure_notes(
                "score",
                spectre,
                kind,
                output_dir,
            )
            status = (
                "infrastructure_failure"
                if kind == "infrastructure"
                else "compile_failure"
                if kind == "compile"
                else "runtime_failure"
            )
            taxonomy_value = taxonomy(
                "infrastructure" if kind == "infrastructure" else kind,
                "infrastructure"
                if kind == "infrastructure"
                else "compilation"
                if kind == "compile"
                else "simulation",
                case_ids=["score"],
                retryable=kind == "infrastructure",
                responsibility="system" if kind == "infrastructure" else "candidate",
            )
            return {
                **base,
                "outcome": status,
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy_value,
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": taxonomy_value["responsibility"],
                        "failure_kind": kind,
                        "spectre": compact,
                        "spectre_trace_reused": trace_reused,
                        "behavior_score": None,
                        "behavior_notes": diagnostics,
                    }
                ],
            }

        csv_path = output_dir / "tran_spectre.csv"
        if not csv_path.is_file():
            diagnostics = ["score: Spectre completed without a transient trace"]
            return {
                **base,
                "outcome": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "infrastructure",
                    case_ids=["score"],
                    retryable=True,
                    responsibility="system",
                ),
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": "system",
                        "failure_kind": "infrastructure",
                        "spectre": compact,
                        "spectre_trace_reused": trace_reused,
                        "behavior_score": None,
                        "behavior_notes": diagnostics,
                    }
                ],
            }

        trace_valid, trace_notes = _trace_is_valid(csv_path, required_signals)
        if not trace_valid:
            diagnostics = [f"score: {note}" for note in trace_notes]
            return {
                **base,
                "outcome": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "trace_contract",
                    case_ids=["score"],
                    retryable=True,
                    responsibility="system",
                ),
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": "system",
                        "failure_kind": "required_signal",
                        "spectre": compact,
                        "spectre_trace_reused": trace_reused,
                        "behavior_score": None,
                        "behavior_notes": diagnostics,
                    }
                ],
            }

        try:
            score, behavior_notes = behavior_evaluator(
                checker_task_id,
                csv_path,
                timeout_s=config.checker_timeout_s,
            )
        except Exception as exc:
            score = 0.0
            behavior_notes = [
                f"behavior_eval_error={type(exc).__name__}: {str(exc)[:500]}"
            ]
        behavior_notes = [str(note) for note in behavior_notes]
        if not _behavior_evaluation_is_valid(behavior_notes):
            diagnostics = [f"score: {note}" for note in behavior_notes]
            failure_kind = _behavior_evaluation_failure_kind(behavior_notes)
            return {
                **base,
                "outcome": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure", failure_kind,
                    case_ids=["score"],
                    retryable=True,
                    responsibility="system",
                ),
                "checker_task_id": checker_task_id,
                "cases": [
                    {
                        "case_id": "score",
                        "responsibility": "system",
                        "failure_kind": failure_kind,
                        "spectre": compact,
                        "spectre_trace_reused": trace_reused,
                        "behavior_score": score,
                        "behavior_notes": diagnostics,
                    }
                ],
            }

        side_effect_ok, side_effect_notes = _validate_side_effect_contract(
            checker_profile,
            csv_path,
            output_dir,
        )
        diagnostics = [
            *(f"score: {note}" for note in behavior_notes),
            *(f"score: {note}" for note in side_effect_notes),
        ]
        passed = score >= 1.0 and side_effect_ok
        if passed:
            status = "passed"
            taxonomy_value = None
        else:
            status = "behavior_failure"
            taxonomy_value = taxonomy(
                "property",
                "property_check",
                case_ids=["score"],
            )
        return {
            **base,
            "outcome": status,
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy_value,
            "checker_task_id": checker_task_id,
            "cases": [
                {
                    "case_id": "score",
                    "responsibility": "candidate",
                    "failure_kind": None if passed else "behavior",
                    "spectre": compact,
                    "spectre_trace_reused": trace_reused,
                    "behavior_score": score,
                    "behavior_notes": diagnostics,
                    "side_effect_ok": side_effect_ok,
                }
            ],
        }
def _finish_testbench_audit(
    *,
    runtime: Path,
    score_row: dict[str, Any],
    submission_tree_sha256: str,
    cell_output: Path,
    trace_cache_root: Path | None,
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]],
    behavior_evaluator: Callable[..., tuple[float, list[str]]],
    cell_id: str,
    source_eval: Path,
    public_contract_path: Path,
    public_contract: dict[str, Any],
    target_artifacts: list[str],
    checker_task_id: str,
    required_signals: set[str],
    mutation_ids: list[str],
) -> dict[str, Any]:
    required_signals.update(
        str(item)
        for item in (public_contract.get("trace_contract") or {}).get(
            "required_signals"
        )
        or []
    )
    tb = runtime / "evidence" / "final_submission" / "testbench.scs"
    if not tb.is_file():
        return {
            "schema_version": SCHEMA_VERSION,
            "cell_id": cell_id,
            "family_id": score_row.get("family_id"),
            "form": "testbench",
            "mode": score_row.get("mode"),
            "experimental_arm": score_row.get("experimental_arm"),
            "source_outcome": score_row.get("outcome"),
            "outcome": "compile_failure",
            "diagnostics": ["missing frozen final submission artifact: testbench.scs"],
            "failure_taxonomy": taxonomy("compile", "compilation"),
            "submission_tree_sha256": submission_tree_sha256,
            "cases": [],
        }
    security_policy = read_json(source_eval / "testbench_security_policy.json")
    security = validate_testbench(tb, public_contract, security_policy)
    if not security.valid:
        diagnostics = [f"security: {note}" for note in security.diagnostics]
        return {
            "schema_version": SCHEMA_VERSION,
            "cell_id": cell_id,
            "family_id": score_row.get("family_id"),
            "form": "testbench",
            "mode": score_row.get("mode"),
            "experimental_arm": score_row.get("experimental_arm"),
            "source_outcome": score_row.get("outcome"),
            "outcome": "compile_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy("compile", "compilation"),
            "submission_tree_sha256": submission_tree_sha256,
            "cases": [],
        }

    cases: list[dict[str, Any]] = []
    oracle_results: list[CaseResult] = []
    case_specs: list[tuple[str, Path | None]] = [("reference", None)]
    case_specs.extend(
        (
            mutation_id,
            mutation_bundle(source_eval, mutation_id, target_artifacts),
        )
        for mutation_id in mutation_ids
    )
    for case_id, negative in case_specs:
        case, oracle = _testbench_case(
            runtime=runtime,
            cell_id=cell_id,
            tb_source=tb,
            source_eval=source_eval,
            public_contract=public_contract,
            target_artifacts=target_artifacts,
            negative_bundle=negative,
            checker_task_id=checker_task_id,
            required_signals=required_signals,
            case_id=case_id,
            output_dir=cell_output / "cases" / case_id,
            trace_cache_root=trace_cache_root,
            config=config,
            simulate_case=simulate_case,
            behavior_evaluator=behavior_evaluator,
        )
        cases.append(case)
        oracle_results.append(oracle)

    infrastructure_cases = [
        case["case_id"]
        for case in cases
        if case.get("responsibility") == "system"
    ]
    if infrastructure_cases:
        infrastructure_failure_kinds = {
            str(case.get("failure_kind") or "infrastructure")
            for case in cases
            if case["case_id"] in infrastructure_cases
        }
        infrastructure_stage = (
            "checker_timeout"
            if infrastructure_failure_kinds == {"checker_timeout"}
            else "invalid_oracle_config"
            if infrastructure_failure_kinds == {"invalid_oracle_config"}
            else "infrastructure"
        )
        classification = {
            "status": "infrastructure_failure",
            "diagnostics": [
                note
                for case in cases
                if case["case_id"] in infrastructure_cases
                for note in case.get("behavior_notes") or []
            ],
            "failure_taxonomy": taxonomy(
                "infrastructure",
                infrastructure_stage,
                case_ids=infrastructure_cases,
                retryable=True,
                responsibility="system",
            ),
        }
    else:
        classification = classify_testbench_result(
            oracle_results[0],
            oracle_results[1:],
            mutation_ids,
        )

    negative_cases = cases[1:]
    return {
        "schema_version": SCHEMA_VERSION,
        "completed_at": now_utc(),
        "cell_id": cell_id,
        "family_id": score_row.get("family_id"),
        "form": "testbench",
        "mode": score_row.get("mode"),
        "experimental_arm": score_row.get("experimental_arm"),
        "source_outcome": score_row.get("outcome"),
        "outcome": classification["status"],
        "diagnostics": classification.get("diagnostics") or [],
        "failure_taxonomy": classification.get("failure_taxonomy"),
        "submission_tree_sha256": submission_tree_sha256,
        "frozen_evaluator_tree_sha256": _evaluator_tree_sha256(source_eval),
        "public_contract_sha256": sha256_file(public_contract_path),
        "spectre_identity": {
            "runtime_id": config.runtime_id,
            "backend": normalize_spectre_backend(config.backend),
            "mode": normalize_spectre_mode(config.mode),
            "host": config.sui_host or default_remote_host(config.backend),
        },
        "checker_task_id": checker_task_id,
        "reference_gate": cases[0]["outcome"] == "reference_pass",
        "killed_count": sum(
            case["outcome"] == "killed_behaviorally" for case in negative_cases
        ),
        "survived_count": sum(
            case["outcome"] == "survived" for case in negative_cases
        ),
        "invalid_count": sum(
            case["outcome"] == "invalid_run" for case in negative_cases
        ),
        "kill_denominator": 5,
        "cases": cases,
    }


def audit_cell(
    *,
    runtime: Path,
    score_row: dict[str, Any],
    submission_tree_sha256: str,
    cell_output: Path,
    trace_cache_root: Path | None = None,
    config: SpectreConfig,
    simulate_case: Callable[..., dict[str, Any]] = _default_simulate_case,
    behavior_evaluator: Callable[
        ..., tuple[float, list[str]]
    ] = evaluate_behavior_with_timeout,
) -> dict[str, Any]:
    """Replay one frozen cell through Spectre and the canonical private checker."""
    form = str(score_row.get("form") or "")
    if form == "testbench":
        return _audit_testbench_cell(
            runtime=runtime,
            score_row=score_row,
            submission_tree_sha256=submission_tree_sha256,
            cell_output=cell_output,
            trace_cache_root=trace_cache_root,
            config=config,
            simulate_case=simulate_case,
            behavior_evaluator=behavior_evaluator,
        )
    if form in {"dut", "bugfix"}:
        return _audit_dut_cell(
            runtime=runtime,
            score_row=score_row,
            submission_tree_sha256=submission_tree_sha256,
            cell_output=cell_output,
            trace_cache_root=trace_cache_root,
            config=config,
            simulate_case=simulate_case,
            behavior_evaluator=behavior_evaluator,
        )
    raise NotImplementedError(f"Spectre campaign audit is not implemented for form={form}")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(encoded)
        temporary = Path(handle.name)
    temporary.replace(path)


def _cell_input_signature(
    item: dict[str, Any],
    config: SpectreConfig,
) -> tuple[dict[str, Any], str]:
    runtime = Path(item["runtime"])
    record = read_json(runtime / "evaluator" / "task_record.json")
    release_task = resolve_release_task(runtime, record)
    row = item["score_row"]
    backend = normalize_spectre_backend(config.backend)
    execution_environment = {
        "host": (
            config.sui_host
            if config.sui_host is not None
            else default_remote_host(backend)
        ),
        "work_root": (
            config.sui_work_root
            if config.sui_work_root is not None
            else default_remote_work_root(backend)
        ),
        "cadence_cshrc": (
            config.cadence_cshrc
            if config.cadence_cshrc is not None
            else default_remote_cadence_cshrc(backend)
        ),
    }
    implementation_files = {
        "score_spectre_campaign.py": Path(__file__),
        "simulate_evas.py": REPO_RUNNERS / "simulate_evas.py",
        "derived_testbench_oracle.py": PACKAGE_RUNNERS / "derived_testbench_oracle.py",
        "trusted_replay_adapter.py": HERE / "trusted_replay_adapter.py",
        "run_gold_dual_suite.py": REPO_RUNNERS / "run_gold_dual_suite.py",
    }
    signature = {
        "schema_version": "vabench-spectre-cell-input-signature-v2",
        "audit_schema_version": SCHEMA_VERSION,
        "implementation_sha256": {
            name: sha256_file(path) for name, path in implementation_files.items()
        },
        "frozen_source_row_sha256": canonical_sha256(row),
        "cell": {
            key: row.get(key)
            for key in (
                "cell_id",
                "family_id",
                "form",
                "mode",
                "experimental_arm",
                "outcome",
            )
        },
        "submission_tree_sha256": item["submission_tree_sha256"],
        "frozen_evaluator_tree_sha256": _evaluator_tree_sha256(
            runtime / "evaluator"
        ),
        "public_contract_sha256": sha256_file(
            release_task / "public_contract.json"
        ),
        "spectre_run_config": {
            "backend": backend,
            "mode": normalize_spectre_mode(config.mode),
            "timeout_s": config.timeout_s,
            "checker_timeout_s": config.checker_timeout_s,
            "runtime_id": config.runtime_id,
            "execution_environment_sha256": canonical_sha256(
                execution_environment
            ),
        },
    }
    return signature, canonical_sha256(signature)


def _run_or_resume_cell(
    *,
    item: dict[str, Any],
    work_root: Path,
    config: SpectreConfig,
    cell_auditor: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    signature, signature_sha = _cell_input_signature(item, config)
    cell_id = str(item["cell_id"])
    if re.fullmatch(r"[A-Za-z0-9._-]+", cell_id) is None:
        raise ValueError(f"unsafe cell ID: {cell_id!r}")
    cell_output = work_root / "cells" / cell_id / signature_sha
    trace_cache_root = work_root / "cells" / cell_id / "trace_cache"
    result_path = cell_output / "result.json"
    if result_path.is_file():
        existing = read_json(result_path)
        existing_taxonomy = existing.get("failure_taxonomy")
        retryable = bool(
            isinstance(existing_taxonomy, dict)
            and existing_taxonomy.get("retryable") is True
        )
        if (
            existing.get("input_signature_sha256") == signature_sha
            and existing.get("input_signature") == signature
            and not retryable
        ):
            return existing, True

    try:
        result = cell_auditor(
            runtime=Path(item["runtime"]),
            score_row=item["score_row"],
            submission_tree_sha256=str(item["submission_tree_sha256"]),
            cell_output=cell_output,
            trace_cache_root=trace_cache_root,
            config=config,
        )
    except Exception as exc:
        row = item["score_row"]
        diagnostics = [
            "Spectre sidecar cell audit raised an exception",
            f"{type(exc).__name__}: {str(exc)[:1000]}",
        ]
        result = {
            "schema_version": SCHEMA_VERSION,
            "completed_at": now_utc(),
            "cell_id": cell_id,
            "family_id": row.get("family_id"),
            "form": row.get("form"),
            "mode": row.get("mode"),
            "experimental_arm": row.get("experimental_arm"),
            "source_outcome": row.get("outcome"),
            "outcome": "infrastructure_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy(
                "infrastructure",
                "infrastructure",
                retryable=True,
                responsibility="system",
            ),
            "cases": [],
        }
    result["input_signature"] = signature
    result["input_signature_sha256"] = signature_sha
    source_row_sha = str(signature["frozen_source_row_sha256"])
    result["source_provenance"] = {
        "authority": "frozen_plan_score_row",
        "source_outcome": item["score_row"].get("outcome"),
        "source_row_sha256": source_row_sha,
    }
    semantic_eligible, semantic_reason = _semantic_eligibility(
        str(result.get("outcome") or ""),
        result.get("failure_taxonomy")
        if isinstance(result.get("failure_taxonomy"), dict)
        else None,
    )
    pass_delta, pass_reason = _pass_impact(result)
    result["semantic_eligible"] = semantic_eligible
    result["semantic_eligibility_reason"] = semantic_reason
    result["confirmed_pass_delta"] = pass_delta
    result["pass_impact_reason"] = pass_reason
    result["sidecar_result_path"] = str(result_path)
    write_json_atomic(result_path, result)
    return result, False


def _summarize_audit(
    rows: list[dict[str, Any]],
    *,
    resumed_cell_count: int,
    config: SpectreConfig,
) -> dict[str, Any]:
    outcomes = Counter(str(row.get("outcome") or "unknown") for row in rows)
    breakdown = Counter(
        (
            str(row.get("form") or ""),
            str(row.get("experimental_arm") or ""),
            str(row.get("outcome") or "unknown"),
        )
        for row in rows
    )
    transitions = Counter(
        (
            str(row.get("source_outcome") or ""),
            str(row.get("outcome") or "unknown"),
        )
        for row in rows
    )
    semantic_eligibility = [
        _semantic_eligibility(
            str(row.get("outcome") or ""),
            row.get("failure_taxonomy")
            if isinstance(row.get("failure_taxonomy"), dict)
            else None,
        )
        for row in rows
    ]
    pass_impacts = [_pass_impact(row) for row in rows]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_utc(),
        "score_authority": "spectre_sidecar_audit_not_final_benchmark_score",
        "cell_count": len(rows),
        "resumed_cell_count": resumed_cell_count,
        "spectre_identity": {
            "runtime_id": config.runtime_id,
            "backend": normalize_spectre_backend(config.backend),
            "mode": normalize_spectre_mode(config.mode),
            "host": config.sui_host or default_remote_host(config.backend),
        },
        "outcomes": dict(sorted(outcomes.items())),
        "breakdown": [
            {
                "form": form,
                "experimental_arm": arm,
                "outcome": outcome,
                "count": count,
            }
            for (form, arm, outcome), count in sorted(breakdown.items())
        ],
        "source_outcome_transitions": [
            {
                "source_outcome": source,
                "spectre_outcome": observed,
                "count": count,
            }
            for (source, observed), count in sorted(transitions.items())
        ],
        "semantic_denominator": {
            "eligible_cells": sum(eligible for eligible, _reason in semantic_eligibility),
            "excluded_cells": sum(not eligible for eligible, _reason in semantic_eligibility),
            "excluded_by_reason": dict(
                sorted(
                    Counter(
                        reason
                        for eligible, reason in semantic_eligibility
                        if not eligible
                    ).items()
                )
            ),
        },
        "pass_impact": {
            "net_confirmed_pass_delta": sum(delta for delta, _reason in pass_impacts),
            "by_reason": dict(sorted(Counter(reason for _delta, reason in pass_impacts).items())),
        },
        "mutation_summary": {
            "killed": sum(int(row.get("killed_count") or 0) for row in rows),
            "survived": sum(int(row.get("survived_count") or 0) for row in rows),
            "invalid": sum(int(row.get("invalid_count") or 0) for row in rows),
        },
        "infrastructure_cells": [
            str(row["cell_id"])
            for row in rows
            if row.get("outcome") == "infrastructure_failure"
        ],
        "rows": rows,
    }


def run_audit(
    *,
    plan: list[dict[str, Any]],
    work_root: Path,
    output: Path,
    config: SpectreConfig,
    workers: int,
    cell_auditor: Callable[..., dict[str, Any]] = audit_cell,
) -> dict[str, Any]:
    """Run or resume a verified plan and write only independent sidecar evidence."""
    if not 1 <= workers <= MAX_SPECTRE_WORKERS:
        raise ValueError(
            f"Spectre workers must be between 1 and {MAX_SPECTRE_WORKERS}"
        )
    work_root = work_root.expanduser().resolve()
    output = output.expanduser().resolve()
    work_root.mkdir(parents=True, exist_ok=True)

    def run_one(item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        return _run_or_resume_cell(
            item=item,
            work_root=work_root,
            config=config,
            cell_auditor=cell_auditor,
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        completed = list(executor.map(run_one, plan))
    rows = [result for result, _resumed in completed]
    resumed_count = sum(resumed for _result, resumed in completed)
    aggregate = _summarize_audit(
        rows,
        resumed_cell_count=resumed_count,
        config=config,
    )
    write_json_atomic(output, aggregate)
    return aggregate


def _path_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--score", type=Path, required=True)
    parser.add_argument("--campaign-run", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--source-outcome",
        action="append",
        default=[],
        help="select a frozen score outcome; defaults to runtime_failure",
    )
    parser.add_argument(
        "--all-outcomes",
        action="store_true",
        help="audit every frozen cell instead of filtering by source outcome",
    )
    parser.add_argument("--cell-id", action="append", default=[])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout-s", type=int, default=600)
    parser.add_argument(
        "--checker-timeout-s",
        type=int,
        default=300,
        help="per-checker watchdog, separate from each Spectre simulation timeout",
    )
    parser.add_argument(
        "--spectre-backend",
        required=True,
        help="explicit Spectre transport backend (bridge, labctl, or sui-direct)",
    )
    parser.add_argument("--spectre-mode", default="ax")
    parser.add_argument(
        "--spectre-runtime-id",
        default=DEFAULT_SPECTRE_RUNTIME_ID,
    )
    parser.add_argument("--sui-host")
    parser.add_argument("--sui-work-root")
    parser.add_argument("--cadence-cshrc")
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="verify immutable inputs and write a selection manifest without simulation",
    )
    args = parser.parse_args(argv)

    score = args.score.expanduser().resolve()
    campaign_run = args.campaign_run.expanduser().resolve()
    freeze = args.freeze_manifest.expanduser().resolve()
    work_root = args.work_root.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if work_root == campaign_run or _path_within(work_root, campaign_run):
        raise SystemExit("--work-root must be outside the frozen campaign run")
    if output in {score, freeze} or _path_within(output, campaign_run):
        raise SystemExit("--output must be an independent sidecar path")
    if args.workers < 1 or args.workers > MAX_SPECTRE_WORKERS:
        raise SystemExit(
            f"--workers must be between 1 and {MAX_SPECTRE_WORKERS}"
        )
    if args.timeout_s <= 0 or args.checker_timeout_s <= 0:
        raise SystemExit("simulation and checker timeouts must be positive")

    source_outcomes = (
        set()
        if args.all_outcomes
        else set(args.source_outcome or ["runtime_failure"])
    )
    plan = build_audit_plan(
        score_path=score,
        campaign_run=campaign_run,
        freeze_manifest=freeze,
        source_outcomes=source_outcomes,
        cell_ids=set(args.cell_id),
    )
    config = SpectreConfig(
        backend=normalize_spectre_backend(args.spectre_backend),
        mode=normalize_spectre_mode(args.spectre_mode),
        timeout_s=args.timeout_s,
        checker_timeout_s=args.checker_timeout_s,
        runtime_id=args.spectre_runtime_id,
        sui_host=args.sui_host,
        sui_work_root=args.sui_work_root,
        cadence_cshrc=args.cadence_cshrc,
    )
    if args.plan_only:
        plan_report = {
            "schema_version": "vabench-spectre-audit-plan-v1",
            "generated_at": now_utc(),
            "source_score": str(score),
            "freeze_manifest": str(freeze),
            "campaign_run": str(campaign_run),
            "cell_count": len(plan),
            "source_outcomes": sorted(source_outcomes),
            "spectre_identity": {
                "runtime_id": config.runtime_id,
                "backend": config.backend,
                "mode": config.mode,
                "host": config.sui_host or default_remote_host(config.backend),
            },
            "cells": [
                {
                    "cell_id": item["cell_id"],
                    "family_id": item["score_row"].get("family_id"),
                    "form": item["score_row"].get("form"),
                    "experimental_arm": item["score_row"].get(
                        "experimental_arm"
                    ),
                    "source_outcome": item["score_row"].get("outcome"),
                    "submission_tree_sha256": item[
                        "submission_tree_sha256"
                    ],
                }
                for item in plan
            ],
        }
        write_json_atomic(output, plan_report)
        print(
            json.dumps(
                {"plan_only": True, "cell_count": len(plan), "output": str(output)}
            )
        )
        return 0

    aggregate = run_audit(
        plan=plan,
        work_root=work_root,
        output=output,
        config=config,
        workers=args.workers,
    )
    print(
        json.dumps(
            {
                "cell_count": aggregate["cell_count"],
                "resumed_cell_count": aggregate["resumed_cell_count"],
                "outcomes": aggregate["outcomes"],
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

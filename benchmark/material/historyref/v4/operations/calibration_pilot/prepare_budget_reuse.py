#!/usr/bin/env python3
"""Reuse completed calibration episodes under compatible execution settings."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
from typing import Any


HERE = Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_campaign.py"
SPEC = importlib.util.spec_from_file_location("v4_calibration_runner", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)

SUBMITTED = {"submitted", "submitted_at_budget"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_files(runtime: Path) -> list[Path]:
    policy_path = runtime / "evaluator" / "score_policy.json"
    if not policy_path.is_file():
        return []
    policy = read_json(policy_path)
    files = []
    for raw in policy.get("candidate_artifacts") or []:
        relative = RUNNER.safe_relative(str(raw))
        files.append(runtime / "public" / "submission" / relative)
    return files


def model_turn_hit_limit(result: dict[str, Any]) -> bool:
    per_turn_cap = RUNNER.cell_per_turn_max_tokens(result["cell"])
    legacy_used = 0
    for event in result.get("events") or []:
        if event.get("type") == "model":
            requested = event.get("requested_max_tokens")
            if not isinstance(requested, int):
                requested = per_turn_cap
            generated = event.get("provider_output_tokens")
            if not isinstance(generated, int):
                generated = (event.get("provider_usage") or {}).get("completion_tokens")
            probe = dict(event)
            probe["requested_max_tokens"] = requested
            probe["provider_output_tokens"] = generated
            if RUNNER.model_event_hit_limit(probe):
                return True
        legacy_used += int(event.get("reference_tokens") or 0)
    return False


def assess_reuse(
    result: dict[str, Any], source_runtime: Path, target_cell: dict[str, Any]
) -> dict[str, Any]:
    reasons: list[str] = []
    source_cell = result.get("cell") or {}
    if result.get("status") not in SUBMITTED:
        reasons.append("source_not_submitted")
    if result.get("submission_protocol_compliant") is False:
        reasons.append("source_submission_protocol_noncompliant")
    if source_cell.get("cell_id") != target_cell.get("cell_id"):
        reasons.append("cell_id_mismatch")
    if source_cell.get("prompt_record_sha256") != target_cell.get("prompt_record_sha256"):
        reasons.append("prompt_record_mismatch")
    files = candidate_files(source_runtime)
    artifact_gate = RUNNER.submission_artifact_gate(source_runtime)
    if not files or not artifact_gate["passed"]:
        reasons.append("incomplete_candidate_artifacts")
    if model_turn_hit_limit(result):
        reasons.append("model_turn_hit_output_limit")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "candidate_artifacts": [
            {
                "path": relative,
                "sha256": digest,
            }
            for relative, digest in artifact_gate["artifact_sha256"].items()
        ],
    }


def check_campaign_compatibility(source: dict[str, Any], target: dict[str, Any]) -> None:
    for key in (
        "model_provider",
        "model",
        "release_manifest_sha256",
        "selection_manifest_sha256",
    ):
        if source.get(key) != target.get(key):
            raise ValueError(f"campaign mismatch for {key}: {source.get(key)!r} != {target.get(key)!r}")
    if source.get("selection") != target.get("selection"):
        raise ValueError("campaign selection mismatch")
    if not source.get("execution_config") or not target.get("execution_config"):
        raise ValueError("budget reuse requires execution_config in both campaigns")
    if source["execution_config"] != target["execution_config"]:
        raise ValueError("campaign execution_config mismatch")
    if RUNNER.cell_per_turn_max_tokens(target) != RUNNER.cell_per_turn_max_tokens(source):
        raise ValueError("campaign per-turn token cap mismatch")


def prepare_reuse(
    source_output: Path,
    source_campaign: dict[str, Any],
    target_campaign: dict[str, Any],
    output: Path,
) -> dict[str, Any]:
    check_campaign_compatibility(source_campaign, target_campaign)
    target_cells = {str(row["cell_id"]): row for row in target_campaign["cells"]}
    rows = []
    output.mkdir(parents=True, exist_ok=True)
    for cell_id, target_cell in sorted(target_cells.items()):
        source_runtime = source_output / cell_id
        result_path = source_runtime / "evidence" / "campaign_result.json"
        if not result_path.is_file():
            rows.append({"cell_id": cell_id, "eligible": False, "reasons": ["missing_source_result"]})
            continue
        result = read_json(result_path)
        assessment = assess_reuse(result, source_runtime, target_cell)
        row = {
            "cell_id": cell_id,
            "source_result_sha256": sha256(result_path),
            **assessment,
        }
        rows.append(row)
        if not assessment["eligible"]:
            continue
        target_runtime = output / cell_id
        if target_runtime.exists():
            raise FileExistsError(f"reuse target already exists: {target_runtime}")
        shutil.copytree(source_runtime, target_runtime)
        copied_result_path = target_runtime / "evidence" / "campaign_result.json"
        snapshot_path = target_runtime / "evidence" / "source_campaign_result.json"
        shutil.copy2(copied_result_path, snapshot_path)
        copied = read_json(copied_result_path)
        copied["source_cell"] = copied["cell"]
        copied["cell"] = target_cell
        copied["runtime"] = str(target_runtime)
        copied["output_token_budget"] = None
        copied["per_turn_max_tokens"] = RUNNER.cell_per_turn_max_tokens(target_cell)
        provider_output_tokens = sum(
            int((event.get("provider_usage") or {}).get("completion_tokens") or 0)
            for event in copied.get("events") or []
            if event.get("type") == "model"
        )
        if provider_output_tokens > 0:
            copied["output_tokens"] = provider_output_tokens
            copied["working_tokens"] = provider_output_tokens
        copied["reuse"] = {
            "kind": "uncensored_completed_episode",
            "prepared_at": now(),
            "source_result_sha256": row["source_result_sha256"],
            "source_per_turn_max_tokens": RUNNER.cell_per_turn_max_tokens(result["cell"]),
            "target_per_turn_max_tokens": RUNNER.cell_per_turn_max_tokens(target_cell),
            "source_output_token_budget": RUNNER.cell_per_turn_max_tokens(result["cell"]),
            "target_output_token_budget": RUNNER.cell_per_turn_max_tokens(target_cell),
        }
        write_json(copied_result_path, copied)
        write_json(target_runtime / "evidence" / "reuse_record.json", row)

    reusable = sum(bool(row["eligible"]) for row in rows)
    manifest = {
        "schema_version": "v4-calibration-budget-reuse-v1",
        "generated_at": now(),
        "source_output": str(source_output),
        "source_per_turn_max_tokens": RUNNER.cell_per_turn_max_tokens(source_campaign),
        "target_per_turn_max_tokens": RUNNER.cell_per_turn_max_tokens(target_campaign),
        "source_budget": RUNNER.cell_per_turn_max_tokens(source_campaign),
        "target_budget": RUNNER.cell_per_turn_max_tokens(target_campaign),
        "cell_count": len(rows),
        "reused_count": reusable,
        "rerun_count": len(rows) - reusable,
        "rows": rows,
    }
    write_json(output / "REUSE_MANIFEST.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-output", type=Path, required=True)
    parser.add_argument("--source-campaign", type=Path, required=True)
    parser.add_argument("--target-campaign", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = prepare_reuse(
        args.source_output.resolve(),
        read_json(args.source_campaign.resolve()),
        read_json(args.target_campaign.resolve()),
        args.output.resolve(),
    )
    print(json.dumps({key: manifest[key] for key in (
        "cell_count", "reused_count", "rerun_count", "source_budget", "target_budget"
    )}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

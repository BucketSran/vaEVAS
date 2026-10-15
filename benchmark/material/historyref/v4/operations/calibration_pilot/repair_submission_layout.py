#!/usr/bin/env python3
"""Repair the historical public/submission alias nesting with an audit record."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
from collections import Counter


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from submission_normalization import normalize_submission_layout  # noqa: E402


SUBMITTED = {"submitted", "submitted_at_budget"}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repair_runtime(runtime: Path) -> dict[str, Any] | None:
    result_path = runtime / "evidence" / "campaign_result.json"
    policy_path = runtime / "evaluator" / "score_policy.json"
    if not result_path.is_file() or not policy_path.is_file():
        return None
    result = read_json(result_path)
    if result.get("status") in SUBMITTED:
        return None
    expected = [str(item) for item in read_json(policy_path).get("candidate_artifacts") or []]
    submission = runtime / "public" / "submission"
    normalization = normalize_submission_layout(submission, expected)
    if normalization is None or not all((submission / item).is_file() for item in expected):
        return None
    result["status"] = "submitted"
    result["submission_layout_repair"] = {
        **normalization,
        "schema_version": "v4-submission-layout-repair-v2",
        "reason": "runner_normalized_unique_common_submission_prefix",
        "repaired_at": datetime.now(timezone.utc).isoformat(),
    }
    result["submission_protocol_compliant"] = False
    write_json(result_path, result)
    return {
        "cell_id": result["cell"]["cell_id"],
        "stripped_prefix": normalization["stripped_prefix"],
        "artifacts": normalization["artifacts"],
    }


def refresh_summary(root: Path, report_path: Path) -> None:
    results = [
        read_json(path)
        for path in sorted(root.glob("v4-*/evidence/campaign_result.json"))
    ]
    summary_path = root / "SUMMARY.json"
    summary = read_json(summary_path) if summary_path.is_file() else {
        "schema_version": "v4-calibration-run-summary-v1"
    }
    summary["result_count"] = len(results)
    summary["statuses"] = dict(sorted(Counter(row["status"] for row in results).items()))
    summary["submission_layout_repair_report"] = {
        "path": report_path.name,
        "sha256": sha256(report_path),
    }
    write_json(summary_path, summary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    root = args.campaign_output.resolve()
    new_rows = [row for runtime in sorted(root.glob("v4-*")) if (row := repair_runtime(runtime))]
    output = (args.report or root / "SUBMISSION_LAYOUT_REPAIR.json").resolve()
    existing_rows = []
    if output.is_file():
        existing = read_json(output)
        if existing.get("schema_version") == "v4-submission-layout-repair-report-v1":
            existing_rows = list(existing.get("rows") or [])
    by_cell = {str(row["cell_id"]): row for row in existing_rows}
    by_cell.update({str(row["cell_id"]): row for row in new_rows})
    rows = [by_cell[key] for key in sorted(by_cell)]
    report = {
        "schema_version": "v4-submission-layout-repair-report-v1",
        "campaign_output": str(root),
        "repair_count": len(rows),
        "new_repair_count": len(new_rows),
        "rows": rows,
    }
    write_json(output, report)
    refresh_summary(root, output)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

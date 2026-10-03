#!/usr/bin/env python3
"""Audit raw direct responses separately from candidate functionality."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("v4_calibration_runner", HERE / "run_campaign.py")
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-output", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.campaign_output.expanduser().resolve()
    rows = []
    for result_path in sorted(root.glob("v4-*/evidence/campaign_result.json")):
        result = read_json(result_path)
        cell = result.get("cell") or {}
        if cell.get("process") != "direct_one_shot":
            continue
        runtime = result_path.parents[1]
        checkpoint = read_json(runtime / "evidence" / "conversation_checkpoint.json")
        content = str(checkpoint["messages"][-1].get("content") or "")
        strict_mapping, strict_protocol = RUNNER.parse_direct_artifacts(content, runtime)
        mapping, protocol = RUNNER.parse_recoverable_direct_artifacts(content, runtime)
        rows.append({
            "cell_id": cell["cell_id"],
            "task_id": cell["task_id"],
            "form": cell["form"],
            "mode": cell["mode"],
            "response_sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "raw_protocol_compliant": (
                strict_mapping is not None
                and RUNNER.direct_protocol_compliant(strict_protocol)
            ),
            "deterministically_extractable": mapping is not None,
            "extraction_protocol": protocol,
            "declared_artifacts": RUNNER.expected_candidate_artifacts(runtime),
            "mapped_artifacts": sorted(mapping or {}),
            "functional_submission_status": result.get("status"),
        })
    protocols = Counter(row["extraction_protocol"] for row in rows)
    report = {
        "schema_version": "v4-direct-response-protocol-audit-v2",
        "campaign_output": str(root),
        "cell_count": len(rows),
        "raw_protocol_compliant_count": sum(row["raw_protocol_compliant"] for row in rows),
        "deterministically_extractable_count": sum(row["deterministically_extractable"] for row in rows),
        "artifact_delivery_failure_count": sum(not row["deterministically_extractable"] for row in rows),
        "ambiguous_count": sum(row["extraction_protocol"] == "ambiguous_labeled_artifacts" for row in rows),
        "protocol_counts": dict(sorted(protocols.items())),
        "score_boundary": "Protocol compliance is diagnostic and is not the Verilog-A functional score.",
        "rows": rows,
    }
    output = (args.output or root / "DIRECT_RESPONSE_PROTOCOL_AUDIT.json").resolve()
    write_json(output, report)
    summary_path = root / "SUMMARY.json"
    if summary_path.is_file():
        summary = read_json(summary_path)
        summary["direct_response_protocol_audit"] = {
            "path": output.name,
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            "raw_protocol_compliant_count": report["raw_protocol_compliant_count"],
            "deterministically_extractable_count": report["deterministically_extractable_count"],
            "ambiguous_count": report["ambiguous_count"],
        }
        write_json(summary_path, summary)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Audit canonical feedback/score stimulus parity for selected v4 families."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_v4_harness import load_spec, validate_profile_semantic_parity  # noqa: E402


DEFAULT_SOURCE = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--family-id", action="append", dest="family_ids")
    args = parser.parse_args()
    selected = {str(value).zfill(3) for value in (args.family_ids or [])}
    rows = []
    problems = []
    for task_dir in sorted(args.source.glob("[0-9][0-9][0-9]-*")):
        family = task_dir.name.split("-", 1)[0]
        if selected and family not in selected:
            continue
        spec_path = task_dir / "evaluator" / "harness_spec.json"
        if not spec_path.is_file():
            continue
        try:
            spec, sha = load_spec(spec_path)
            validate_profile_semantic_parity(spec)
        except Exception as exc:  # schema and parity errors are audit evidence
            problems.append(f"{family}: {exc}")
            rows.append({"family_id": family, "status": "fail", "error": str(exc)})
        else:
            rows.append({"family_id": family, "status": "pass", "harness_spec_sha256": sha})
    report = {
        "schema_version": "v4-profile-parity-audit-v1",
        "status": "pass" if rows and not problems else "fail",
        "family_count": len(rows),
        "families": rows,
        "problems": problems,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

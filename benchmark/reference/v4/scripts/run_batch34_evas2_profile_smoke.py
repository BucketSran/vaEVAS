#!/usr/bin/env python3
"""Run the batch-34 canonical profile parity smoke with an EVAS2 lock."""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_ROOT = SCRIPT_DIR.parent / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"


def load_renderer() -> Any:
    path = SCRIPT_DIR / "render_v4_harness.py"
    spec = importlib.util.spec_from_file_location("render_v4_harness", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load renderer: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_evas2() -> dict[str, Any]:
    sys.path.insert(0, str(SCRIPT_DIR))
    from run_batch34_metamorphic import require_evas2_installation

    return require_evas2_installation()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    engine = require_evas2()
    renderer = load_renderer()
    rows: list[dict[str, Any]] = []
    for family in sorted(SOURCE_ROOT.glob("3??-*")):
        family_id = int(family.name[:3])
        if not 331 <= family_id <= 340:
            continue
        evaluator = family / "evaluator"
        spec, spec_hash = renderer.load_spec(evaluator / "harness_spec.json")
        renderer.validate_profile_semantic_parity(spec)
        profile_checks: dict[str, bool] = {}
        for profile_name in ("feedback", "score"):
            generated = renderer.build_profile(spec, profile_name, spec_hash)
            recorded = json.loads(
                (evaluator / "profiles" / f"{profile_name}.json").read_text(
                    encoding="utf-8"
                )
            )
            profile_checks[profile_name] = generated == recorded
        rendered_score = renderer.render_scs(spec, renderer.build_profile(spec, "score", spec_hash))
        recorded_score = (evaluator / "score_tb.scs").read_text(encoding="utf-8")
        profile_checks["score_deck"] = rendered_score == recorded_score
        rows.append(
            {
                "family": family_id,
                "semantic_parity": True,
                "profiles": profile_checks,
                "status": "pass" if all(profile_checks.values()) else "fail",
                "evas_engine": "evas2",
                "evas_engine_used": "evas2",
            }
        )
    report = {
        "schema_version": "v4-batch34-evas2-profile-smoke-v1",
        **engine,
        "execution": "static_profile_parity_no_simulator",
        "family_count": len(rows),
        "pass_count": sum(row["status"] == "pass" for row in rows),
        "fail_count": sum(row["status"] != "pass" for row in rows),
        "status": "pass" if len(rows) == 10 and all(row["status"] == "pass" for row in rows) else "fail",
        "families": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("status", "family_count", "pass_count", "fail_count", "evas_engine_used")}, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

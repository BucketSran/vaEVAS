from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
RELEASE_ROOT = ROOT / "release" / "benchmarkv4"
RENDERER = ROOT / "scripts" / "render_v4_harness.py"
sys.path.insert(0, str(ROOT / "runners"))
from testbench_security import validate_testbench  # noqa: E402


def _source_task(family_id: int) -> Path:
    return next(SOURCE_ROOT.glob(f"{family_id:03d}-*"))


def _release_testbench_task(family_id: int) -> Path:
    return next((RELEASE_ROOT / "tasks").glob(f"{family_id + 500:03d}-*"))


def _semantic_projection(spec: dict, profile_name: str) -> dict:
    defaults = copy.deepcopy(spec["profile_defaults"][profile_name])
    return {
        "body_lines": list(spec["deck"].get("body_lines", []))
        + list((defaults.get("deck_overrides") or {}).get("body_lines", [])),
        "analyses": list(
            (defaults.get("deck_overrides") or {}).get(
                "analyses", spec["deck"].get("analyses", [])
            )
        ),
        "save_signals": list(
            (defaults.get("deck_overrides") or {}).get(
                "save_signals", spec["deck"].get("save_signals", [])
            )
        ),
        "parameters": defaults.get("parameters", {}),
        "corners": defaults.get("corners", []),
        "deterministic_seed": defaults.get("deterministic_seed", 0),
        "property_ids": list(spec["property_ids"]),
    }


def _without_backend_options(deck: str) -> str:
    return "\n".join(
        line.rstrip()
        for line in deck.splitlines()
        if line.strip() and not line.startswith("simulatorOptions options ")
    ) + "\n"


def test_batch40_canonical_specs_have_feedback_score_semantic_parity() -> None:
    for family_id in range(391, 401):
        source = _source_task(family_id) / "evaluator"
        spec = json.loads((source / "harness_spec.json").read_text(encoding="utf-8"))
        assert _semantic_projection(spec, "feedback") == _semantic_projection(
            spec, "score"
        ), f"family {family_id:03d} profile semantic drift"


def test_batch40_regeneration_is_deterministic_and_matches_tracked_artifacts(
    tmp_path: Path,
) -> None:
    for family_id in range(391, 401):
        source = _source_task(family_id) / "evaluator"
        spec_path = source / "harness_spec.json"
        output = tmp_path / f"{family_id:03d}"
        output.mkdir()
        generated: dict[str, tuple[dict, str]] = {}
        for profile_name in ("feedback", "score"):
            profile_path = output / f"{profile_name}.json"
            deck_path = output / f"{profile_name}.scs"
            subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "--spec",
                    str(spec_path),
                    "--profile",
                    profile_name,
                    "--profile-output",
                    str(profile_path),
                    "--deck-output",
                    str(deck_path),
                ],
                check=True,
                cwd=ROOT,
            )
            generated[profile_name] = (
                json.loads(profile_path.read_text(encoding="utf-8")),
                deck_path.read_text(encoding="utf-8"),
            )
        feedback, score = generated["feedback"], generated["score"]
        assert feedback[0]["property_ids"] == score[0]["property_ids"]
        assert feedback[0]["parameters"] == score[0]["parameters"]
        assert feedback[0]["corners"] == score[0]["corners"]
        assert feedback[0]["deterministic_seed"] == score[0]["deterministic_seed"]
        assert feedback[0]["deck_overrides"] == score[0]["deck_overrides"]
        assert feedback[0]["simulatorOptions"] == {"evas_profile": "balanced"}
        assert score[0]["simulatorOptions"] == {}
        assert _without_backend_options(feedback[1]) == _without_backend_options(score[1])
        assert feedback[1] == (source.parent / "public" / "task" / "feedback_tb.scs").read_text(
            encoding="utf-8"
        )
        assert score[1] == (source / "score_tb.scs").read_text(encoding="utf-8")


def test_batch40_active_mutation_contract_has_five_testbench_kills() -> None:
    for family_id in range(391, 401):
        source = _source_task(family_id) / "evaluator"
        catalog = {
            item["id"]: item
            for item in json.loads(
                (source / "mutation_bundles" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )["mutations"]
        }
        policy = json.loads(
            (_release_testbench_task(family_id) / "evaluator" / "score_policy.json").read_text(
                encoding="utf-8"
            )
        )
        active_ids = policy["negative_suite_mutation_ids"]
        assert len(active_ids) == 5
        assert len(set(active_ids)) == 5
        assert policy["kill_ratio_denominator"] == 5
        for mutation_id in active_ids:
            certification = catalog[mutation_id]["certification"]
            assert certification["compile_status"] == "pass"
            assert certification["simulation_status"] == "pass"
            assert certification["status"] == "pass"
            assert catalog[mutation_id]["violated_property_ids"]


def test_batch40_reference_testbenches_match_public_security_contract() -> None:
    for family_id in range(391, 401):
        task = _release_testbench_task(family_id)
        contract = json.loads((task / "public_contract.json").read_text(encoding="utf-8"))
        policy = json.loads(
            (task / "evaluator" / "testbench_security_policy.json").read_text(
                encoding="utf-8"
            )
        )
        result = validate_testbench(
            task / "evaluator" / "reference_tb.scs", contract, policy
        )
        assert result.valid, f"family {family_id:03d}: {result.diagnostics}"

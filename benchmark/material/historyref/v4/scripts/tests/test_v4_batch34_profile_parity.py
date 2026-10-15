from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "render_v4_harness.py"
SPEC_ROOT = (
    Path(__file__).resolve().parents[2]
    / "provenance"
    / "dut-base-v3-exact-five-hash-bound-v2"
)


def load_renderer():
    spec = importlib.util.spec_from_file_location("render_v4_harness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_spec() -> dict:
    return {
        "schema_version": "v4-harness-spec-v1",
        "family_id": "999",
        "task_id": "v4-999",
        "generator": {"name": "render_v4_harness.py", "version": "test"},
        "candidate": {"source_root": "./dut", "artifact_paths": ["dut.va"]},
        "deck": {
            "header": ["simulator lang=spectre"],
            "include_templates": ['ahdl_include "{candidate_source_root}/{artifact_path}"'],
            "body_lines": ["Vclk (clk 0) vsource type=pulse period=10n"],
            "analyses": ["tran tran stop=20n maxstep=100p"],
            "save_signals": ["clk"],
        },
        "property_ids": ["P_CLOCK"],
        "profile_defaults": {
            "feedback": {
                "parameters": {"maxstep": "100p", "stop_time": "20n"},
                "simulatorOptions": {"evas_profile": "balanced"},
            },
            "score": {
                "parameters": {"maxstep": "100p", "stop_time": "20n"},
                "simulatorOptions": {},
            },
        },
    }


def test_backend_only_difference_is_allowed() -> None:
    renderer = load_renderer()
    renderer.validate_profile_semantic_parity(minimal_spec())


def test_stimulus_drift_is_rejected() -> None:
    renderer = load_renderer()
    spec = minimal_spec()
    spec["profile_defaults"]["score"]["deck_overrides"] = {
        "body_lines": ["Vclk (clk 0) vsource type=pulse period=7n"]
    }
    with pytest.raises(ValueError, match="feedback/score semantic parity violation"):
        renderer.validate_profile_semantic_parity(spec)


def test_parameter_drift_is_rejected() -> None:
    renderer = load_renderer()
    spec = minimal_spec()
    spec["profile_defaults"]["score"]["parameters"]["maxstep"] = "50p"
    assert "parameters" in renderer.profile_semantic_diffs(spec)
    with pytest.raises(ValueError, match="parameters"):
        renderer.validate_profile_semantic_parity(spec)


def test_batch_34_specs_and_generated_score_decks_are_parity_clean() -> None:
    renderer = load_renderer()
    families = [
        path
        for path in sorted(SPEC_ROOT.iterdir())
        if path.is_dir() and path.name[:3].isdigit() and 331 <= int(path.name[:3]) <= 340
    ]
    assert len(families) == 10
    for family in families:
        evaluator = family / "evaluator"
        spec = json.loads((evaluator / "harness_spec.json").read_text(encoding="utf-8"))
        renderer.validate_profile_semantic_parity(spec)
        spec_hash = renderer.file_sha256(evaluator / "harness_spec.json")
        for profile_name in ("feedback", "score"):
            generated = renderer.build_profile(spec, profile_name, spec_hash)
            recorded = json.loads(
                (evaluator / "profiles" / f"{profile_name}.json").read_text(encoding="utf-8")
            )
            assert generated == recorded, family.name
        score = renderer.build_profile(spec, "score", spec_hash)
        assert renderer.render_scs(spec, score) == (
            evaluator / "score_tb.scs"
        ).read_text(encoding="utf-8")

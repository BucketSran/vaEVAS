from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "render_r45_canonical_test.py"
spec = importlib.util.spec_from_file_location("render_r45_canonical_test", SCRIPT)
assert spec and spec.loader
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def _spec() -> dict:
    return {
        "schema_version": "v4-harness-spec-v1",
        "family_id": "999",
        "task_id": "v4-999",
        "generator": {"name": "render_v4_harness.py", "version": "test"},
        "candidate": {"source_root": "./dut", "artifact_paths": ["dut.va"]},
        "deck": {
            "header": ["simulator lang=spectre", "global 0"],
            "include_templates": ["ahdl_include \"{candidate_source_root}/{artifact_path}\""],
            "body_lines": ["Vstim (in 0) vsource dc=0.45", "XDUT (in out) dut"],
            "analyses": ["tran tran stop=10n maxstep=100p"],
            "save_signals": ["in", "out"],
        },
        "property_ids": ["P_TEST"],
        "profile_defaults": {
            "feedback": {
                "parameters": {"maxstep": "100p"},
                "corners": ["nominal"],
                "deterministic_seed": 7,
                "simulatorOptions": {"evas_profile": "balanced", "strict": True},
                "deck_overrides": {},
            },
            "score": {
                "parameters": {"maxstep": "100p"},
                "corners": ["nominal"],
                "deterministic_seed": 7,
                "simulatorOptions": {"strict": True},
                "deck_overrides": {},
            },
        },
    }


def test_builds_one_profile_for_public_and_trusted_replay() -> None:
    profile, deck = renderer.build_canonical_test(_spec(), "a" * 64)

    assert profile["profile_name"] == "canonical_test"
    assert profile["reuse_policy"] == renderer.REUSE_POLICY
    assert (
        profile["source"]["feedback_semantics_sha256"]
        == profile["source"]["score_semantics_sha256"]
    )
    assert (
        profile["canonical_semantics_sha256"]
        == profile["source"]["score_semantics_sha256"]
    )
    assert profile["test_deck_sha256"] == hashlib.sha256(deck.encode()).hexdigest()
    assert profile["simulator_options"] == {"strict": True}
    assert "evas_profile" not in deck
    assert "feedback" not in profile
    assert "score" not in profile


def test_rejects_feedback_score_semantic_drift() -> None:
    payload = _spec()
    payload["profile_defaults"]["score"]["parameters"]["maxstep"] = "50p"

    with pytest.raises(ValueError, match="semantic parity violation"):
        renderer.build_canonical_test(payload, "b" * 64)


def test_deck_is_deterministic() -> None:
    first_profile, first_deck = renderer.build_canonical_test(_spec(), "c" * 64)
    second_profile, second_deck = renderer.build_canonical_test(_spec(), "c" * 64)

    assert first_profile == second_profile
    assert first_deck == second_deck


def test_deployment_binding_updates_only_the_deck_hash() -> None:
    profile, _ = renderer.build_canonical_test(_spec(), "e" * 64)
    deployed = 'ahdl_include "../submission/dut.va"\n'

    bound = renderer.bind_deployed_test_deck(profile, deployed)

    assert bound["test_deck_sha256"] == hashlib.sha256(deployed.encode()).hexdigest()
    assert bound["canonical_semantics_sha256"] == profile["canonical_semantics_sha256"]
    assert profile["test_deck_sha256"] != bound["test_deck_sha256"]


def test_schema_validation_has_no_jsonschema_runtime_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(renderer.v4, "Draft202012Validator", None)

    profile, _ = renderer.build_canonical_test(_spec(), "d" * 64)

    assert profile["schema_version"] == "r45-canonical-test-profile-v1"

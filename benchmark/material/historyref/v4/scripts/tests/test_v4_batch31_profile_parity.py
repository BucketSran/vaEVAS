from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "render_v4_harness.py"
spec = importlib.util.spec_from_file_location("render_v4_harness", SCRIPT)
assert spec and spec.loader
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)


def _spec(*, drift: bool = False) -> dict:
    body = ["Vstim (in 0) vsource dc=0.45"]
    return {
        "schema_version": "v4-harness-spec-v1",
        "family_id": "999",
        "task_id": "v4-999",
        "generator": {"name": "render_v4_harness.py", "version": "test"},
        "candidate": {"source_root": "./dut", "artifact_paths": ["dut.va"]},
        "deck": {
            "header": ["simulator lang=spectre", "global 0"],
            "body_lines": body,
            "analyses": ["tran tran stop=10n maxstep=100p"],
            "save_signals": ["in", "out"],
        },
        "property_ids": ["P_TEST"],
        "profile_defaults": {
            "feedback": {
                "parameters": {"maxstep": "100p"},
                "corners": [],
                "deterministic_seed": 7,
                "simulatorOptions": {"evas_profile": "balanced"},
                "deck_overrides": {},
            },
            "score": {
                "parameters": {"maxstep": "100p"},
                "corners": [],
                "deterministic_seed": 7,
                "simulatorOptions": {},
                "deck_overrides": {},
            },
        },
    }


def test_profile_semantics_match_when_only_backend_options_differ() -> None:
    payload = _spec()
    renderer.validate_profile_semantic_parity(payload)
    assert renderer.effective_profile_semantics(payload, "feedback") == renderer.effective_profile_semantics(payload, "score")


def test_profile_semantics_reject_stimulus_drift() -> None:
    payload = _spec(drift=True)
    payload["profile_defaults"]["score"]["deck_overrides"] = {
        "body_lines": ["Vstim (in 0) vsource dc=0.55"]
    }
    with pytest.raises(ValueError, match="semantic parity violation"):
        renderer.validate_profile_semantic_parity(payload)


def test_profile_semantics_reject_parameter_drift() -> None:
    payload = _spec()
    payload["profile_defaults"]["feedback"]["parameters"]["maxstep"] = "50p"
    with pytest.raises(ValueError, match="parameters"):
        renderer.validate_profile_semantic_parity(payload)

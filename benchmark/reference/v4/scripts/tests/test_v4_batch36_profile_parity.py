import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "render_v4_harness.py"
SPEC = importlib.util.spec_from_file_location("render_v4_harness", MODULE_PATH)
assert SPEC and SPEC.loader
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def make_spec(feedback_body=None, score_body=None):
    feedback_body = feedback_body if feedback_body is not None else ["Vx x 0 vsource dc=0"]
    score_body = score_body if score_body is not None else list(feedback_body)
    defaults = {
        "parameters": {"stop_time": "10n"},
        "corners": [],
        "deterministic_seed": 7,
        "deck_overrides": {"body_lines": feedback_body},
    }
    score = {
        "parameters": {"stop_time": "10n"},
        "corners": [],
        "deterministic_seed": 7,
        "deck_overrides": {"body_lines": score_body},
    }
    return {
        "family_id": "999",
        "property_ids": ["P_X"],
        "deck": {
            "body_lines": [],
            "analyses": ["tran tran stop=10n"],
            "save_signals": ["x"],
        },
        "profile_defaults": {"feedback": defaults, "score": score},
    }


def test_equal_profiles_pass_parity():
    renderer.validate_profile_semantic_parity(make_spec())


def test_different_stimulus_fails_parity():
    spec = make_spec(score_body=["Vx x 0 vsource dc=0.9"])
    try:
        renderer.validate_profile_semantic_parity(spec)
    except ValueError as exc:
        assert "body_lines" in str(exc)
    else:
        raise AssertionError("semantic profile drift was not rejected")


def test_backend_options_are_not_semantic_drift():
    spec = make_spec()
    spec["profile_defaults"]["feedback"]["simulatorOptions"] = {
        "evas_profile": "balanced"
    }
    spec["profile_defaults"]["score"]["simulatorOptions"] = {}
    renderer.validate_profile_semantic_parity(spec)

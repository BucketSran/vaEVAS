from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_v4_repair_gate.py"
SPEC = importlib.util.spec_from_file_location("validate_v4_repair_gate", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_trace_contract_does_not_require_implicit_time_save() -> None:
    failures: list[dict[str, object]] = []

    MODULE.validate_trace_contract(
        failures,
        "071",
        {"deck": {"save_signals": ["vin", "vout"]}},
        {"trace_contract": {"required_signals": ["time", "vin", "vout"]}},
        {
            "trace_contract": {
                "public_observables": ["time", "vin", "vout"],
                "extra_trace_signals": ["time"],
            }
        },
        {"public_observables": ["time", "vin", "vout"]},
    )

    assert failures == []


def test_profile_binding_rejects_stale_harness_spec_hash() -> None:
    failures: list[dict[str, object]] = []
    spec = {
        "property_ids": ["P_GAIN"],
        "deck": {
            "body_lines": ["VIN (vin 0) vsource dc=0"],
            "analyses": ["tran tran stop=1n"],
            "save_signals": ["vin", "vout"],
        },
    }
    profile = {
        "harness_spec_sha256": "stale",
        "property_ids": ["P_GAIN"],
        "parameters": {},
        "corners": [],
        "deterministic_seed": 0,
    }

    MODULE.validate_profiles(
        failures,
        "068",
        spec,
        "a" * 64,
        profile,
        profile,
    )

    assert [failure["check"] for failure in failures] == [
        "profile_harness_binding",
        "profile_harness_binding",
    ]

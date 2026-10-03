#!/usr/bin/env python3
"""Collapse one parity-checked v4 harness into an r45 canonical test profile."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import render_v4_harness as v4


ROOT = Path(__file__).resolve().parents[1]
PROFILE_SCHEMA = ROOT / "schemas" / "r45_canonical_test_profile.schema.json"
GENERATOR_VERSION = "r45-canonical-test-renderer-v1"
PROFILE_NAME = "canonical_test"
REUSE_POLICY = "public_visible_and_final_trusted_replay_same_bytes"


def canonical_json_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_profile(profile: dict[str, Any]) -> None:
    """Validate r45 output without making jsonschema a runtime dependency."""
    schema = v4.read_json(PROFILE_SCHEMA)
    if v4.Draft202012Validator is not None:
        v4.Draft202012Validator(schema).validate(profile)
        return

    required = set(schema["required"])
    if set(profile) != required:
        raise ValueError("r45 canonical profile fields do not match the schema")
    if profile["schema_version"] != "r45-canonical-test-profile-v1":
        raise ValueError("unsupported r45 canonical profile schema_version")
    if profile["profile_name"] != PROFILE_NAME:
        raise ValueError("r45 profile_name must be canonical_test")
    if profile["reuse_policy"] != REUSE_POLICY:
        raise ValueError("unsupported r45 canonical test reuse policy")
    hashes = [
        profile["canonical_semantics_sha256"],
        profile["test_deck_sha256"],
        profile["source"]["harness_spec_sha256"],
        profile["source"]["feedback_semantics_sha256"],
        profile["source"]["score_semantics_sha256"],
    ]
    invalid_hash = any(
        len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
        for value in hashes
    )
    if invalid_hash:
        raise ValueError("r45 canonical profile contains an invalid sha256")


def _canonical_semantics(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    v4.validate_profile_semantic_parity(spec)
    feedback = v4.effective_profile_semantics(spec, "feedback")
    score = v4.effective_profile_semantics(spec, "score")
    if feedback != score:
        raise ValueError("v4 feedback and score semantics differ after parity validation")
    return feedback, score


def _render_profile_deck(spec: dict[str, Any], semantics: dict[str, Any]) -> str:
    profile = {
        "profile_name": PROFILE_NAME,
        "parameters": dict(semantics["parameters"]),
        "corners": list(semantics["corners"]),
        "deterministic_seed": int(semantics["deterministic_seed"]),
        "simulatorOptions": dict(semantics["simulator_options"]),
        "deck_overrides": {},
    }
    return v4.render_scs(spec, profile)


def build_canonical_test(
    spec: dict[str, Any], harness_spec_sha256: str
) -> tuple[dict[str, Any], str]:
    """Return the single r45 profile and its exact reusable test deck."""
    v4.validate_schema(spec, v4.SPEC_SCHEMA)
    v4.validate_canonical_semantics(spec)
    feedback, score = _canonical_semantics(spec)
    feedback_sha256 = canonical_json_sha256(feedback)
    score_sha256 = canonical_json_sha256(score)
    if feedback_sha256 != score_sha256:
        raise ValueError("feedback and score semantic hashes differ")

    deck = _render_profile_deck(spec, feedback)
    profile = {
        "schema_version": "r45-canonical-test-profile-v1",
        "profile_name": PROFILE_NAME,
        "generated_from": {
            "script": "render_r45_canonical_test.py",
            "version": GENERATOR_VERSION,
        },
        "source": {
            "schema_version": str(spec["schema_version"]),
            "family_id": str(spec["family_id"]),
            "task_id": str(spec["task_id"]),
            "harness_spec_sha256": harness_spec_sha256,
            "feedback_semantics_sha256": feedback_sha256,
            "score_semantics_sha256": score_sha256,
        },
        "property_ids": list(feedback["property_ids"]),
        "parameters": dict(feedback["parameters"]),
        "corners": list(feedback["corners"]),
        "deterministic_seed": int(feedback["deterministic_seed"]),
        "simulator_options": dict(feedback["simulator_options"]),
        "canonical_semantics_sha256": feedback_sha256,
        "test_deck_sha256": hashlib.sha256(deck.encode("utf-8")).hexdigest(),
        "reuse_policy": REUSE_POLICY,
    }
    validate_profile(profile)
    return profile, deck


def bind_deployed_test_deck(
    profile: dict[str, Any], deck: str
) -> dict[str, Any]:
    """Bind canonical semantics to the exact deck bytes used at runtime.

    Materializers may rewrite only deployment paths (for example ``./dut`` to
    the writable submission mount).  The semantic profile stays unchanged,
    while its deck hash must describe the bytes copied to both public and
    trusted replay surfaces.
    """
    bound = copy.deepcopy(profile)
    bound["test_deck_sha256"] = hashlib.sha256(deck.encode("utf-8")).hexdigest()
    validate_profile(bound)
    return bound


def load_and_build(spec_path: Path) -> tuple[dict[str, Any], str]:
    spec, spec_sha256 = v4.load_spec(spec_path)
    return build_canonical_test(spec, spec_sha256)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--profile-output", type=Path)
    parser.add_argument("--deck-output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    profile, deck = load_and_build(args.spec)
    if args.profile_output:
        v4.write_json(args.profile_output, profile)
    if args.deck_output:
        args.deck_output.parent.mkdir(parents=True, exist_ok=True)
        args.deck_output.write_bytes(deck.encode("utf-8"))
    if not args.profile_output and not args.deck_output:
        print(deck, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

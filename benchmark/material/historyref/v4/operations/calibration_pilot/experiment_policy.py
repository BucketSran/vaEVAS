"""Load the single canonical v4 experiment policy."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parents[2]
POLICY_PATH = PACKAGE / "EXPERIMENT_POLICY.json"


def load_experiment_policy() -> dict[str, Any]:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    if policy.get("schema_version") != "v4-experiment-policy-v1":
        raise ValueError("unsupported v4 experiment policy schema")
    wall_seconds = policy.get("agent_wall_time_seconds")
    if not isinstance(wall_seconds, int) or isinstance(wall_seconds, bool) or wall_seconds <= 0:
        raise ValueError("agent_wall_time_seconds must be a positive integer")
    finalization = policy.get("timeout_finalization")
    if not isinstance(finalization, dict):
        raise ValueError("timeout_finalization must be an object")
    if finalization.get("artifact_source") != "latest_complete_declared_submission":
        raise ValueError("timeout_finalization must use the latest complete submission")
    if finalization.get("score_complete_artifact") is not True:
        raise ValueError("timeout_finalization must score a complete artifact")
    if finalization.get("termination_reason") != "agent_timeout":
        raise ValueError("timeout_finalization must retain agent_timeout")
    return policy


def experiment_policy_sha256() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()

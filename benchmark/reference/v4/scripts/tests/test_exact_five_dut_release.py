from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "release" / "dut-base-v3-exact-five-hash-bound-v2"
AUDITOR = ROOT / "scripts" / "audit_exact_five_dut_release.py"
DECISIONS = ROOT / "operations" / "dut_base_exact_five" / "SEMANTIC_SELECTION_DECISIONS.json"
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from audit_exact_five_dut_release import is_rust_evas2_behavioral_kill  # noqa: E402


def test_exact_five_release_passes_strict_audit() -> None:
    if not (RELEASE / "score_denominator_registry" / "_meta.json").is_file():
        pytest.skip("exact-five integration release is supplied by the asset PRs")
    completed = subprocess.run(
        [sys.executable, str(AUDITOR), "--release", str(RELEASE)],
        check=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    summary = json.loads(completed.stdout)
    assert summary == {
        "status": "PASS",
        "task_count": 400,
        "active_mutation_count": 2000,
        "archived_mutation_count": 51,
        "problem_count": 0,
        "problems": [],
    }


def test_semantic_decisions_cover_overfive_and_duplicate_proxy_reviews() -> None:
    decisions = json.loads(DECISIONS.read_text())
    assert decisions["family_count"] == 36
    assert decisions["changed_family_count"] == 15
    assert len(decisions["families"]) == 36
    assert all(len(row["active_mutation_ids"]) == 5 for row in decisions["families"])
    assert {row["family_id"] for row in decisions["supplemental_exact_five_reviews"]} == {"092", "098"}


def test_behavioral_kill_requires_rust_evas2_policy() -> None:
    certification = {
        "outcome": "killed_behaviorally",
        "certification_policy": "rust_evas2_only",
        "evaluators": {
            "evas2": "compile_pass_behavior_fail",
        },
    }
    assert is_rust_evas2_behavioral_kill(certification)
    certification["evaluators"]["evas2"] = "pass"
    assert not is_rust_evas2_behavioral_kill(certification)

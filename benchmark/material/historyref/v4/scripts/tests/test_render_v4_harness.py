#!/usr/bin/env python3
"""Regression tests for v4 canonical feedback/score harness parity."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS = Path(__file__).resolve().parents[1]
RELEASE_ROOT = SCRIPTS.parent
SOURCE_ROOT = RELEASE_ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(RELEASE_ROOT / "operations" / "tri_form_derivation_prep"))

import render_v4_harness  # noqa: E402
import run_v4_metamorphic_smoke as metamorphic_smoke  # noqa: E402
from run_v4_metamorphic_smoke import transform_deck  # noqa: E402
from run_v4_reference_evas_smoke import (  # noqa: E402
    engine_evidence_from_log,
    require_evas2_environment,
)


FAMILIES = range(361, 371)
BATCH_32_FAMILIES = range(311, 321)


def load_family_spec(family: int) -> dict:
    path = next(SOURCE_ROOT.glob(f"{family:03d}-*/evaluator/harness_spec.json"))
    return json.loads(path.read_text(encoding="utf-8"))


def family_dir(family: int) -> Path:
    return next(SOURCE_ROOT.glob(f"{family:03d}-*"))


def spec_hash(spec: dict) -> str:
    payload = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _without_simulator_options(deck: str) -> str:
    return "\n".join(
        line
        for line in deck.splitlines()
        if line.strip() and not line.startswith("simulatorOptions options ")
    )


@pytest.mark.parametrize(
    ("release_revision", "expected_evas_version"),
    [("r51", "0.8.3"), ("r52", "0.8.5"), ("r53", "0.8.7")],
)
def test_metamorphic_smoke_uses_release_pinned_evas_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    release_revision: str,
    expected_evas_version: str,
) -> None:
    release = tmp_path / f"benchmarkv4-{release_revision}"
    release.mkdir()
    (release / "MANIFEST.json").write_text(
        json.dumps({"release_revision": release_revision}) + "\n",
        encoding="utf-8",
    )
    observed: dict[str, str] = {}

    def fake_run_task(*_args, **kwargs) -> dict[str, object]:
        observed["task"] = kwargs["required_evas_version"]
        return {"status": "pass", "case_count": 0}

    monkeypatch.setattr(metamorphic_smoke, "require_evas2_environment", lambda: None)
    monkeypatch.setattr(metamorphic_smoke, "run_task", fake_run_task)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_v4_metamorphic_smoke.py",
            "--release",
            str(release),
            "--task-id",
            "v4-501",
            "--output",
            str(tmp_path / "report.json"),
            "--work-root",
            str(tmp_path / "work"),
        ],
    )

    assert metamorphic_smoke.main() == 0
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert observed["task"] == expected_evas_version
    assert report["evas_version"] == expected_evas_version


def test_assigned_specs_have_profile_parity() -> None:
    for family in FAMILIES:
        render_v4_harness.validate_profile_semantics(load_family_spec(family))


def test_batch_32_specs_have_profile_parity() -> None:
    for family in BATCH_32_FAMILIES:
        render_v4_harness.validate_profile_semantic_parity(load_family_spec(family))


def test_cli_check_parity_accepts_batch_32_spec() -> None:
    spec = next(SOURCE_ROOT.glob("311-*/evaluator/harness_spec.json"))
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "render_v4_harness.py"),
            "--spec",
            str(spec),
            "--profile",
            "feedback",
            "--check-parity",
        ],
        cwd=RELEASE_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert "simulatorOptions" in completed.stdout


def test_assigned_checker_contracts_preserve_diagnostics_and_mutation_scope() -> None:
    for family in FAMILIES:
        root = family_dir(family)
        checker = json.loads((root / "evaluator" / "checker_profile.json").read_text())
        harness = load_family_spec(family)
        catalog = json.loads((root / "evaluator" / "mutation_catalog.json").read_text())
        trace_contract = checker.get("trace_contract") or {}
        assert checker["score_and_feedback_share_checker"] is True
        assert "evaluator/score_tb.scs" in checker["shared_by"]
        assert trace_contract.get("public_observables")
        family_spec = json.loads((root / "evaluator" / "family_spec.json").read_text())
        assert set(harness["property_ids"]) == {
            property_spec["id"] for property_spec in family_spec["properties"]
        }
        assert len(catalog.get("mutations") or []) == 5
        assert all(
            mutation.get("certification", {}).get("status") == "pass"
            for mutation in catalog["mutations"]
        )


def test_semantic_profile_override_is_rejected() -> None:
    spec = copy.deepcopy(load_family_spec(361))
    spec["profile_defaults"]["score"]["deck_overrides"] = {"body_lines": ["bad"]}
    with pytest.raises(ValueError, match="semantic fields"):
        render_v4_harness.validate_profile_semantics(spec)


def test_metamorphic_transform_affinely_moves_events_and_scales_durations() -> None:
    deck = (
        "Vx (x 0) vsource type=pwl wave=[0 0.4 10n 0.4]\n"
        "Vclk (clk 0) vsource type=pulse delay=2n period=4n width=1n rise=10p fall=10p\n"
        "tran tran stop=20n maxstep=100p\n"
    )
    transformed = transform_deck(deck, scale=1.05, shift_s=1e-9)
    assert "wave=[0 0.4 11.5n 0.4]" in transformed
    assert "delay=3.1n period=4.2n width=1.05n" in transformed
    assert "stop=22n maxstep=105p" in transformed


def test_feedback_and_score_render_the_same_canonical_deck() -> None:
    spec = load_family_spec(362)
    render_v4_harness.validate_profile_semantics(spec)
    digest = spec_hash(spec)
    feedback = render_v4_harness.render_scs(
        spec, render_v4_harness.build_profile(spec, "feedback", digest)
    )
    score = render_v4_harness.render_scs(
        spec, render_v4_harness.build_profile(spec, "score", digest)
    )
    assert _without_simulator_options(feedback) == _without_simulator_options(score)
    assert "tran tran stop=190n maxstep=50p" in feedback
    assert "tran tran stop=190n maxstep=50p" in score


def test_evas2_evidence_requires_explicit_engine_and_rust_log(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("EVAS_ENGINE", "evas2")
    monkeypatch.setenv("VAEVAS_DEFAULT_EVAS_ENGINE", "evas2")
    require_evas2_environment()
    log = tmp_path / "evas.log"
    log.write_text(
        "Version 0.8.7 -- Jul 2026\n    evas_engine = evas-rust\n",
        encoding="utf-8",
    )
    evidence = engine_evidence_from_log(log, "")
    assert evidence["evas_engine"] == "evas2"
    assert evidence["evas_engine_used"] == "evas2"
    assert evidence["valid"] is True


def test_evas2_evidence_rejects_python_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("EVAS_ENGINE", "python")
    monkeypatch.setenv("VAEVAS_DEFAULT_EVAS_ENGINE", "python")
    with pytest.raises(SystemExit, match="EVAS_ENGINE=evas2"):
        require_evas2_environment()
    log = tmp_path / "evas.log"
    log.write_text(
        "Version 0.8.3 -- Jul 2026\n    evas_engine = python\n",
        encoding="utf-8",
    )
    evidence = engine_evidence_from_log(log, "")
    assert evidence["evas_engine"] == "python"
    assert evidence["evas_engine_used"] == "python"
    assert evidence["valid"] is False

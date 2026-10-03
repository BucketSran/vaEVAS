import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).parents[1] / "run_v4_stimulus_metamorphic.py"
SPEC = importlib.util.spec_from_file_location("run_v4_stimulus_metamorphic", MODULE_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_affine_transform_scales_pwl_and_shifts_absolute_times() -> None:
    deck = (
        "Vx (x 0) vsource type=pwl wave=[0 0 10n 0.9]\n"
        "Vclk (clk 0) vsource type=pulse period=5n width=2n delay=1n rise=10p fall=20p\n"
        "XDUT (x) dut unit_phase_delay=40p tr=20p\n"
        "tran tran stop=20n maxstep=100p\n"
    )
    transformed = runner.transform_stimulus(deck, scale=2.0, shift=1e-9)
    assert "wave=[1n 0 21n 0.9]" in transformed
    assert "period=10n" in transformed
    assert "width=4n" in transformed
    assert "delay=3n" in transformed
    assert "rise=20p" in transformed
    assert "fall=40p" in transformed
    assert "unit_phase_delay=80p" in transformed
    assert "tr=40p" in transformed
    assert "stop=41n" in transformed
    assert "maxstep=200p" in transformed


def test_affine_transform_scales_explicit_dut_timing_parameters() -> None:
    deck = (
        "XDUT (clk data up dn) bbpd clk_period=20n clk_delay=10n "
        "deadzone=800p pulse_w=1n poll_dt=50p lock_window=180p\n"
    )
    transformed = runner.transform_stimulus(deck, scale=2.0, shift=1e-9)
    assert "clk_period=40n" in transformed
    assert "clk_delay=21n" in transformed
    assert "deadzone=1.6n" in transformed
    assert "pulse_w=2n" in transformed
    assert "poll_dt=100p" in transformed
    assert "lock_window=360p" in transformed


def test_affine_transform_accepts_multiline_pwl_continuations() -> None:
    deck = (
        "Vx (x 0) vsource type=pwl wave=[ \\\n"
        "0 0 \\\n"
        "10n 0.9 \\\n"
        "]\ntran tran stop=10n\n"
    )
    transformed = runner.transform_stimulus(deck, scale=2.0, shift=1e-9)
    assert "wave=[1n 0 21n 0.9]" in transformed
    assert "\\" not in transformed


def test_insufficient_stimulus_keeps_legal_source_declarations() -> None:
    deck = "Vx (x 0) vsource type=pwl wave=[0 0 5n 0.9]\nVclk (c 0) vsource type=pulse period=5n width=2n\n"
    suppressed = runner.suppress_stimulus(deck)
    assert "type=pwl" not in suppressed
    assert "type=pulse" not in suppressed
    assert suppressed.count("vsource dc=0") == 2


def test_insufficient_stimulus_leaves_autonomous_dc_only_deck_unchanged() -> None:
    deck = "Vdd (vdd 0) vsource dc=0.9\ntran tran stop=10n\n"
    assert runner.suppress_stimulus(deck) == deck


def test_insufficient_stimulus_leaves_constant_configuration_pwl_unchanged() -> None:
    deck = "Vseed (seed 0) vsource type=pwl wave=[0 0.9 10n 0.9]\n"
    assert runner.suppress_stimulus(deck) == deck


def test_absolute_timing_contracts_use_translation_only() -> None:
    assert runner.effective_affine_scale("077", 1.37) == 1.0
    assert runner.effective_affine_scale("358", 1.37) == 1.0
    assert runner.effective_affine_scale("361", 1.37) == 1.0
    assert runner.effective_affine_scale("362", 1.37) == 1.0
    assert runner.effective_affine_scale("081", 1.37) == 1.0
    assert runner.effective_affine_scale("082", 1.37) == 1.37


@pytest.mark.parametrize(
    ("family_id", "reason"),
    [
        ("077", "autonomous_dither_remains_exercised_at_zero_input"),
        ("299", "free_running_vco_remains_exercised_at_zero_input"),
    ],
)
def test_zero_input_is_not_insufficient_for_autonomous_sources(
    family_id: str, reason: str,
) -> None:
    assert runner.insufficient_excitation_not_applicable_reason(family_id) == reason
    assert runner.insufficient_excitation_not_applicable_reason("001") is None


def test_evas2_evidence_requires_version_and_rust_backend_markers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAS_ENGINE", "evas2")
    monkeypatch.setenv("VAEVAS_DEFAULT_EVAS_ENGINE", "evas2")
    evidence = runner.require_rust_evas2(
        "Version 0.8.7\n    evas_engine = evas-rust\n"
    )
    assert evidence["evas_engine"] == "evas2"
    assert evidence["evas_engine_used"] == "evas2"
    assert evidence["evas_version"] == "0.8.7"


def test_evas2_evidence_rejects_python_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EVAS_ENGINE", "evas2")
    monkeypatch.setenv("VAEVAS_DEFAULT_EVAS_ENGINE", "evas2")
    try:
        runner.require_rust_evas2("Version 0.8.7\n    evas_engine = python\n")
    except RuntimeError as exc:
        assert "Rust backend marker" in str(exc)
    else:
        raise AssertionError("Python EVAS evidence was accepted")


def test_compact_evidence_identity_separates_release_revisions() -> None:
    assert runner.compact_evidence_identity("r44") == (
        "release/benchmarkv4",
        "v4-r44-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r45") == (
        "release/benchmarkv4-r45",
        "v4-r45-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r47") == (
        "release/benchmarkv4-r47",
        "v4-r47-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r50") == (
        "release/benchmarkv4-r50",
        "v4-r50-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r51") == (
        "release/benchmarkv4-r51",
        "v4-r51-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r52") == (
        "release/benchmarkv4-r52",
        "v4-r52-stimulus-metamorphic-compact-v1",
    )
    assert runner.compact_evidence_identity("r53") == (
        "release/benchmarkv4-r53",
        "v4-r53-stimulus-metamorphic-compact-v1",
    )
    assert runner.required_evas_version("r51") == "0.8.3"
    assert runner.required_evas_version("r52") == "0.8.5"
    assert runner.required_evas_version("r53") == "0.8.7"


def test_release_provenance_binds_manifest_and_source_registry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(
        json.dumps({
            "release_revision": "r47",
            "source_score_denominator_registry_sha256": "a" * 64,
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "score_denominator_registry_sha256",
        lambda source: "a" * 64,
    )

    assert runner.release_provenance(tmp_path, "r47") == {
        "source_score_denominator_registry_sha256": "a" * 64,
        "release_manifest_sha256": runner.file_sha(manifest),
    }

    with pytest.raises(SystemExit, match="revision does not match"):
        runner.release_provenance(tmp_path, "r45")


def test_release_provenance_preserves_frozen_r45_source_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = tmp_path / "MANIFEST.json"
    manifest.write_text(
        json.dumps({
            "release_revision": "r45",
            "source_score_denominator_registry_sha256": "b" * 64,
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        runner,
        "score_denominator_registry_sha256",
        lambda source: "a" * 64,
    )

    assert runner.release_provenance(tmp_path, "r45") == {
        "source_score_denominator_registry_sha256": "b" * 64,
        "release_manifest_sha256": runner.file_sha(manifest),
    }

    manifest.write_text(
        json.dumps({
            "release_revision": "r47",
            "source_score_denominator_registry_sha256": "b" * 64,
        }) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="current source denominator"):
        runner.release_provenance(tmp_path, "r47")


def test_run_case_rejects_missing_per_case_runtime_log(tmp_path, monkeypatch) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    tb_path = task_dir / "reference_tb.scs"
    tb_path.write_text("tran tran stop=1n\n", encoding="utf-8")

    monkeypatch.setattr(runner, "stage_case", lambda **kwargs: (tb_path, []))
    monkeypatch.setattr(runner, "required_trace_signals_for_checker", lambda task_id: {"time"})
    monkeypatch.setattr(
        runner,
        "run_evas",
        lambda *args, **kwargs: type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})(),
    )

    result = runner.run_case(
        task_dir=task_dir,
        checker_task_id="v4-001",
        deck_text="tran tran stop=1n\n",
        case_id="correct",
        mutation_id=None,
        output_root=tmp_path / "runs",
        timeout_s=1,
    )

    assert result["status"] == "infrastructure_error"
    assert result["evas_runtime_valid"] is False
    assert result["evas_runtime_notes"] == ["missing evas.log"]

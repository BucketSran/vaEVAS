from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "operations"
    / "tri_form_derivation_prep"
    / "run_v4_profile_parity_smoke.py"
)
SPEC = importlib.util.spec_from_file_location("run_v4_profile_parity_smoke", MODULE_PATH)
assert SPEC and SPEC.loader
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


def test_profile_evidence_defaults_to_r53_evas_087_rust_runtime() -> None:
    assert runner.REQUIRED_EVAS_VERSION == "0.8.7"
    assert runner.REQUIRED_EVAS_ENGINE == "evas2"
    assert runner.RUST_EVAS_LOG_ENGINE == "evas-rust"
    assert runner.DEFAULT_RELEASE.name == "benchmarkv4-r53"
    assert runner.DEFAULT_RELEASE_REVISION == "r53"


def test_profile_evidence_labels_are_revision_scoped() -> None:
    assert runner.release_label("r44") == "release/benchmarkv4"
    assert runner.release_label("r45") == "release/benchmarkv4-r45"
    assert runner.release_label("r47") == "release/benchmarkv4-r47"
    assert runner.release_label("r52") == "release/benchmarkv4-r52"
    assert runner.release_label("r53") == "release/benchmarkv4-r53"
    assert runner.required_evas_version("r51") == "0.8.3"
    assert runner.required_evas_version("r52") == "0.8.5"
    assert runner.required_evas_version("r53") == "0.8.7"


def test_profile_provenance_rejects_revision_mismatch(
    tmp_path: Path, monkeypatch,
) -> None:
    (tmp_path / "MANIFEST.json").write_text(
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

    with pytest.raises(SystemExit, match="revision does not match"):
        runner.release_provenance(tmp_path, "r45")


def test_profile_provenance_preserves_frozen_r45_source_binding(
    tmp_path: Path, monkeypatch,
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


def test_profile_cli_writes_selected_release_revision(tmp_path: Path, monkeypatch) -> None:
    output = tmp_path / "PROFILE_PARITY.json"
    release = tmp_path / "staged-release"
    release.mkdir()
    (release / "MANIFEST.json").write_text(
        json.dumps({
            "release_revision": "r47",
            "source_score_denominator_registry_sha256": "a" * 64,
        }) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "require_evas2_environment", lambda: None)
    monkeypatch.setattr(
        runner,
        "score_denominator_registry_sha256",
        lambda source: "a" * 64,
    )
    monkeypatch.setattr(
        runner,
        "probe_evas2_runtime",
        lambda **kwargs: {
            "evas_engine": "evas2",
            "evas_engine_used": "evas2",
            "evas_version": "0.8.3",
            "evas_backend": "evas-rust",
        },
    )
    monkeypatch.setattr(runner, "release_rows", lambda release, task_ids, family_range: [])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_v4_profile_parity_smoke.py",
            "--release",
            str(release),
            "--release-revision",
            "r47",
            "--output",
            str(output),
        ],
    )

    assert runner.main() == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["release"] == "release/benchmarkv4-r47"
    assert payload["release_revision"] == "r47"
    assert payload["evas_version"] == "0.8.3"
    assert payload["source_score_denominator_registry_sha256"] == "a" * 64
    assert payload["release_manifest_sha256"] == runner.file_sha(
        release / "MANIFEST.json"
    )

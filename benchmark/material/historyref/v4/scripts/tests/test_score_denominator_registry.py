from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


PREP = Path(__file__).resolve().parents[2] / "operations" / "tri_form_derivation_prep"
SOURCE = Path(__file__).resolve().parents[2] / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
if str(PREP) not in sys.path:
    sys.path.insert(0, str(PREP))

from score_denominator_registry import (  # noqa: E402
    RegistryError,
    load_family_rows,
    load_registry_metadata,
    score_denominator_registry_sha256,
    write_family_row,
)


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def row(family: str) -> dict[str, object]:
    return {
        "canonical_dut_id": family,
        "release_dir": f"{family}-sample",
        "active_mutation_count": 5,
        "active_mutations": [],
        "hashes": {},
    }


def test_canonical_source_has_only_family_shards() -> None:
    assert not (SOURCE / "score_denominator_manifest.json").exists()
    assert not (SOURCE / "selection_inputs" / "ACTIVE_MUTATION_SUITE_INDEX.json").exists()
    assert len(load_family_rows(SOURCE)) == 400
    metadata = load_registry_metadata(SOURCE)
    assert "tasks" not in metadata
    assert "content_sha256" not in metadata


def test_registry_rejects_missing_family_shard(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_json(
        source / "score_denominator_registry" / "_meta.json",
        {"canonical_range": ["001", "002"], "counted_task_count": 2},
    )
    write_family_row(source, "001", row("001"))

    with pytest.raises(RegistryError, match="coverage mismatch"):
        load_family_rows(source)


def test_updating_one_family_does_not_touch_other_shards(tmp_path: Path) -> None:
    source = tmp_path / "source"
    write_json(
        source / "score_denominator_registry" / "_meta.json",
        {"canonical_range": ["001", "002"], "counted_task_count": 2},
    )
    write_family_row(source, "001", row("001"))
    write_family_row(source, "002", row("002"))
    untouched = (source / "score_denominator_registry" / "002.json").read_bytes()
    original_hash = score_denominator_registry_sha256(source)

    changed = row("001")
    changed["bugfix_seed"] = "neg_001"
    write_family_row(source, "001", changed)

    assert (source / "score_denominator_registry" / "002.json").read_bytes() == untouched
    assert load_family_rows(source)[0]["bugfix_seed"] == "neg_001"
    assert score_denominator_registry_sha256(source) != original_hash

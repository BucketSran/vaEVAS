from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PACKAGE_ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
RELEASE_ROOT = PACKAGE_ROOT / "release" / "benchmarkv4"
SCRIPTS_ROOT = PACKAGE_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from render_v4_harness import (  # noqa: E402
    CANONICAL_SEMANTICS_MODE,
    build_profile,
    load_spec,
    render_scs,
    validate_canonical_semantics,
)


def _task_path(root: Path, task_id: int) -> Path:
    matches = sorted((root / "tasks").glob(f"{task_id}-*"))
    assert len(matches) == 1
    return matches[0]


def _semantic_deck(text: str) -> str:
    return re.sub(r"\n{2,}", "\n", "\n".join(
        line for line in text.splitlines() if not line.startswith("simulatorOptions options ")
    )).strip()


def test_batch38_specs_use_one_canonical_deck_and_reproduce_profiles() -> None:
    for family in range(371, 381):
        source_spec_path = next(
            SOURCE_ROOT.glob(f"{family:03d}-*/evaluator/harness_spec.json")
        )
        source_spec, source_hash = load_spec(source_spec_path)
        assert source_spec["canonical_semantics"]["mode"] == CANONICAL_SEMANTICS_MODE
        assert all(
            not (source_spec["profile_defaults"][name].get("deck_overrides") or {})
            for name in ("feedback", "score")
        )

        score_profile = build_profile(source_spec, "score", source_hash)
        feedback_profile = build_profile(source_spec, "feedback", source_hash)
        assert _semantic_deck(render_scs(source_spec, score_profile)) == _semantic_deck(
            render_scs(source_spec, feedback_profile)
        )
        assert _semantic_deck(render_scs(source_spec, score_profile)) == _semantic_deck(
            (source_spec_path.parent / "score_tb.scs").read_text(encoding="utf-8")
        )

        for task_id in (family, family + 500, family + 1000):
            task = _task_path(RELEASE_ROOT, task_id)
            release_spec, release_hash = load_spec(
                task / "evaluator" / "harness_spec.json"
            )
            assert release_spec == source_spec
            for profile_name in ("feedback", "score"):
                expected = json.loads(
                    (task / "evaluator" / "profiles" / f"{profile_name}.json").read_text(
                        encoding="utf-8"
                    )
                )
                assert build_profile(release_spec, profile_name, release_hash) == expected


def test_opted_in_spec_rejects_semantic_profile_overrides() -> None:
    source_spec_path = next(
        SOURCE_ROOT.glob("371-*/evaluator/harness_spec.json")
    )
    spec, _ = load_spec(source_spec_path)
    broken = copy.deepcopy(spec)
    broken["profile_defaults"]["feedback"]["deck_overrides"] = {
        "body_lines": ["Vbad (bad 0) vsource dc=0"]
    }
    with pytest.raises(ValueError, match="forbids semantic profile deck overrides"):
        validate_canonical_semantics(broken)

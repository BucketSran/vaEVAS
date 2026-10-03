#!/usr/bin/env python3
"""Audit the standalone 1,200-task benchmarkv4 release package."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from materialize_tri_form_release import materialized_testbench_reference, resolve_testbench_reference
from source_certification_binding import (
    inspect_source_certification_reuse,
    source_certification_definition_sha256,
)
from score_denominator_registry import (
    load_family_rows,
    score_denominator_registry_sha256,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASES = {
    "r44": PACKAGE_ROOT / "release" / "benchmarkv4",
    "r45": PACKAGE_ROOT / "release" / "benchmarkv4-r45",
    "r47": PACKAGE_ROOT / "release" / "benchmarkv4-r47",
    "r48": PACKAGE_ROOT / "release" / "benchmarkv4-r48",
    "r49": PACKAGE_ROOT / "release" / "benchmarkv4-r49",
    "r50": PACKAGE_ROOT / "release" / "benchmarkv4-r50",
    "r51": PACKAGE_ROOT / "release" / "benchmarkv4-r51",
    "r52": PACKAGE_ROOT / "release" / "benchmarkv4-r52",
    "r53": PACKAGE_ROOT / "release" / "benchmarkv4-r53",
}
DEFAULT_SOURCE = PACKAGE_ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
FORMS = ("dut", "testbench", "bugfix")
MODES = ("G0", "G1", "G2", "G3", "G4", "G5")
DIRECT_MODES = {"G0", "G1"}
AGENTIC_MODES = {"G2", "G3", "G4", "G5"}
WRAPPERS_BY_MODE = {
    "G0": "direct_wrapper.md",
    "G1": "direct_wrapper.md",
    "G2": "agentic_wrapper.md",
    "G3": "agentic_wrapper.md",
    "G4": "agentic_wrapper.md",
    "G5": "agentic_wrapper.md",
}
FORM_SKILLS = {
    "dut": "dut_modeling.md",
    "testbench": "testbench_verification.md",
    "bugfix": "bugfix_diagnosis.md",
}
EVAS_GUIDES = {
    "dut": "evas_dut.md",
    "testbench": "evas_testbench.md",
    "bugfix": "evas_bugfix.md",
}
EVAS_CORE = "evas_core.md"
FEEDBACK_GUIDES = {
    "dut": "feedback_dut.md",
    "testbench": "feedback_testbench.md",
    "bugfix": "feedback_bugfix.md",
}
FEEDBACK_CORE = "feedback_core.md"
MATERIALIZED_ARTIFACTS = (
    "TASK_INDEX.json",
    "prompt_modes/modes.json",
    "prompt_modes/manifest.json",
)
RELEASE_SEAL_ARTIFACTS = (
    "MANIFEST.json",
    *MATERIALIZED_ARTIFACTS,
    "AUDIT_REPORT.json",
    "RUNTIME_INGESTION_EVIDENCE.json",
)
EVIDENCE_FILENAMES = (
    "RUST_EVAS2_CERTIFICATION.json",
    "STIMULUS_METAMORPHIC.json",
    "PROFILE_PARITY.json",
)
STANDALONE_EVALUATOR_COMMON = (
    "family_spec.json",
    "checker_profile.json",
    "harness_spec.json",
    "score_tb.scs",
)
# The name records the revision that introduced this stable profile format;
# release identity is carried by the task record and public runtime schemas.
CANONICAL_TEST_PROFILE_SCHEMA = "r45-canonical-test-profile-v1"
REFERENCE_ONLY_TESTBENCH_REVISIONS = frozenset({"r52", "r53"})
EVAS_VERSION_BY_REVISION = {
    "r52": "0.8.5",
    "r53": "0.8.7",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def valid_sha256(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def valid_git_oid(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is not None


def rust_evas2_runtime(
    payload: object,
    *,
    backend_key: str = "evas_backend",
    require_source_revision: bool = False,
    expected_version: str = "0.8.3",
) -> bool:
    markers_valid = isinstance(payload, dict) and (
        payload.get("evas_engine") == "evas2"
        and payload.get("evas_engine_used") == "evas2"
        and payload.get("evas_version") == expected_version
        and payload.get(backend_key) == "evas-rust"
    )
    if not markers_valid or not require_source_revision:
        return markers_valid
    repository = payload.get("evas_source_repository")
    return (
        isinstance(repository, str)
        and bool(repository.strip())
        and valid_git_oid(payload.get("evas_source_revision"))
        and payload.get("evas_source_tree") == "clean"
    )


def allowed_runtime_schemas(release_revision: str, form: str) -> set[str]:
    if (
        release_revision in REFERENCE_ONLY_TESTBENCH_REVISIONS
        and form == "testbench"
    ):
        return {f"{release_revision}-direct-evas-testbench-reference-v1"}
    kind = "direct-evas-testbench-suite" if form == "testbench" else "direct-evas-runtime"
    versions = (
        (1, 2)
        if release_revision == "r45"
        else ((2, 3) if release_revision in {"r51", "r52", "r53"} else (2,))
    )
    return {
        f"{release_revision}-{kind}-v{version}"
        for version in versions
    }


def audit_testbench_reference(
    evaluator: Path,
    source_task: Path,
    score: dict[str, Any],
    prefix: str,
    problems: list[str],
) -> str | None:
    """Validate the TB-form gold and preserve independent-vs-legacy provenance."""
    try:
        canonical, source_kind = resolve_testbench_reference(source_task)
    except SystemExit as exc:
        problems.append(f"{prefix} {exc}")
        return None
    expected = materialized_testbench_reference(source_task, canonical)
    canonical_sha = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    local = evaluator / "reference_tb.scs"
    if not local.is_file():
        problems.append(f"{prefix} evaluator missing reference_tb.scs")
    elif local.read_text(encoding="utf-8") != expected:
        problems.append(f"{prefix} reference testbench differs from canonical {source_kind}")
    if score.get("reference_tb_sha256") != canonical_sha:
        problems.append(f"{prefix} reference testbench score policy hash mismatch")
    declared_source_kind = score.get("reference_tb_source_kind")
    if declared_source_kind is not None and declared_source_kind != source_kind:
        problems.append(
            f"{prefix} reference testbench source kind mismatch: "
            f"declared={declared_source_kind!r} expected={source_kind!r}"
        )
    if source_kind == "independent_reference_tb" and declared_source_kind is None:
        problems.append(f"{prefix} independent reference testbench source kind is not declared")
    return source_kind


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def tree_sha(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def tree_file_hashes(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): file_sha(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def expected_solution_file_hashes(source_task: Path) -> dict[str, str]:
    """Return the standalone solution tree expected after public support is added.

    The editable/canonical gold artifacts live in evaluator/solution. Some
    composite testbenches also require read-only helper modules that are public
    solver inputs under public/task/public_support. In the standalone package
    those helpers are copied under solution/support/ and supplied_dut/support/
    so that every include path can use the stable ./dut/... contract.
    """

    solution = source_task / "evaluator" / "solution"
    expected = tree_file_hashes(solution)
    public_support = source_task / "public" / "task" / "public_support"
    if public_support.is_dir():
        for item in sorted(public_support.rglob("*")):
            if item.is_file():
                relative = item.relative_to(public_support).as_posix()
                expected[f"support/{relative}"] = file_sha(item)
    return expected


def tree_sha_skipping(path: Path, *, excluded_names: set[str]) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file() and item.name not in excluded_names:
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def public_bundle_hash(task_dir: Path) -> str:
    public = task_dir / "public"
    digest = hashlib.sha256()
    for path in sorted(public.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(public).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def prompt_component_path(release: Path, component_id: str) -> Path:
    if component_id.endswith("_wrapper.md"):
        subdir = "wrappers"
    elif component_id in set(FORM_SKILLS.values()):
        subdir = "form_skills"
    elif component_id == EVAS_CORE or component_id in set(EVAS_GUIDES.values()):
        subdir = "evas_guides"
    elif component_id == FEEDBACK_CORE or component_id in set(FEEDBACK_GUIDES.values()):
        subdir = "feedback_guides"
    else:
        raise SystemExit(f"unknown prompt component: {component_id}")
    return release / "prompt_modes" / subdir / component_id


def release_uses_real_skills(release_revision: str) -> bool:
    return int(release_revision.removeprefix("r")) >= 50


def materialized_artifacts_for_revision(release_revision: str) -> tuple[str, ...]:
    if release_uses_real_skills(release_revision):
        return (*MATERIALIZED_ARTIFACTS, "skills/SNAPSHOT_MANIFEST.json")
    return MATERIALIZED_ARTIFACTS


def build_release_seal(
    release: Path,
    source_registry_sha256: str,
    certification_reuse: dict[str, Any],
    certification_problems: list[str] | None = None,
    evidence_hashes: dict[str, str] | None = None,
    *,
    release_revision: str = "r44",
) -> dict[str, Any]:
    artifact_hashes = {}
    release_seal_artifacts = (
        ("MANIFEST.json", *materialized_artifacts_for_revision(release_revision), "AUDIT_REPORT.json", "RUNTIME_INGESTION_EVIDENCE.json")
    )
    for relative in release_seal_artifacts:
        path = release / relative
        if not path.is_file():
            raise SystemExit(f"cannot seal release; missing artifact: {relative}")
        artifact_hashes[relative] = file_sha(path)
    certification_problems = certification_problems or []
    refresh_required = bool(
        certification_reuse.get("simulation_rerun_required_for_materialization")
    )
    manifest = read_json(release / "MANIFEST.json")
    declared_revision = manifest.get("release_revision")
    if declared_revision is not None and str(declared_revision) != release_revision:
        raise SystemExit(
            "cannot seal release; manifest revision does not match selected revision: "
            f"{declared_revision!r} != {release_revision!r}"
        )
    release_status = (
        "materialized_certification_refresh_required"
        if refresh_required
        else (
            "r53_immutable_source_certification_reused"
            if release_revision == "r53"
            else f"{release_revision}_immutable_rust_evas2_certified"
        )
    )
    simulation_claim = (
        "none; one or more source certifications require Rust EVAS2 refresh"
        if refresh_required
        else (
            "canonical source certification reused by hash; the EVAS 0.8.7 "
            "deployment is qualified by pushed-image and Vela smoke"
            if release_revision == "r53"
            else (
                "fresh full400 Rust EVAS2 evidence with hash-bound source inputs"
                if release_revision != "r44"
                else "canonical DUT gold and exact-five negative Rust EVAS2 certifications reused by hash"
            )
        )
    )
    seal = {
        "schema_version": "v4-benchmarkv4-release-seal-v1",
        "release_revision": release_revision,
        "immutable": not refresh_required,
        "release_status": release_status,
        "source_score_denominator_registry_sha256": source_registry_sha256,
        "artifact_sha256": artifact_hashes,
        "evidence_sha256": evidence_hashes or {},
        "certification_reuse": certification_reuse,
        "simulation_claim": simulation_claim,
    }
    if refresh_required:
        seal["certification_problem_count"] = len(certification_problems)
        seal["certification_problems"] = certification_problems
    if release_revision == "r53":
        seal["runtime_requirements"] = manifest["runtime_requirements"]
    return seal


def evidence_artifacts(release_revision: str) -> tuple[str, ...]:
    if release_revision == "r53":
        return ()
    return tuple(
        f"evidence/{release_revision}/{filename}" for filename in EVIDENCE_FILENAMES
    )


def audit_release_evidence(
    release_revision: str,
    problems: list[str],
    *,
    package_root: Path = PACKAGE_ROOT,
    release: Path | None = None,
    source_registry_sha256: str | None = None,
    source_definition_sha256: str | None = None,
) -> dict[str, str]:
    artifacts = evidence_artifacts(release_revision)
    if release_revision == "r53":
        return {}
    expected_release_label = (
        "release/benchmarkv4"
        if release_revision == "r44"
        else f"release/benchmarkv4-{release_revision}"
    )
    payloads: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for relative in artifacts:
        path = package_root / relative
        if not path.is_file():
            problems.append(f"missing {release_revision} evidence artifact: {relative}")
            continue
        payloads[relative] = read_json(path)
        hashes[relative] = file_sha(path)

    if release_revision != "r44":
        for relative, digest in hashes.items():
            filename = Path(relative).name
            current_number = int(release_revision.removeprefix("r"))
            for prior_revision in DEFAULT_RELEASES:
                prior_number = int(prior_revision.removeprefix("r"))
                if prior_number >= current_number:
                    continue
                prior = package_root / "evidence" / prior_revision / filename
                if prior.is_file() and file_sha(prior) == digest:
                    problems.append(
                        f"{relative} is byte-identical to {prior_revision} evidence; "
                        f"{release_revision} requires a fresh certification artifact"
                    )

    rust = payloads.get(artifacts[0]) or {}
    rust_summary = rust.get("summary") or {}
    if not (
        rust.get("status") == "pass"
        and rust.get("release_candidate") == release_revision
        and rust.get("certification_policy") == "rust_evas2_only"
        and rust_summary.get("family_count") == 400
        and rust_summary.get("gold_pass_count") == 400
        and rust_summary.get("negative_case_count") == 2000
        and rust_summary.get("mutation_kill_count") == 2000
        and (
            int(rust_summary.get("insufficient_excitation_rejection_count") or 0)
            + int(rust_summary.get("insufficient_excitation_not_applicable_count") or 0)
            == 400
        )
    ):
        problems.append(f"{release_revision} Rust EVAS2 certification summary is incomplete")

    metamorphic = payloads.get(artifacts[1]) or {}
    metamorphic_summary = metamorphic.get("summary") or {}
    if not (
        metamorphic.get("status") == "pass"
        and metamorphic.get("release") == expected_release_label
        and metamorphic.get("certification_policy") == "rust_evas2_only"
        and metamorphic_summary.get("task_count") == 400
        and metamorphic_summary.get("affine_gold_pass_count") == 400
        and metamorphic_summary.get("affine_mutation_kill_count") == 2000
        and metamorphic_summary.get("affine_infrastructure_error_count") == 0
        and (
            int(metamorphic_summary.get("insufficient_excitation_rejection_count") or 0)
            + int(metamorphic_summary.get("insufficient_excitation_not_applicable_count") or 0)
            == 400
        )
    ):
        problems.append(f"{release_revision} stimulus metamorphic summary is incomplete")

    parity = payloads.get(artifacts[2]) or {}
    if not (
        parity.get("status") == "pass"
        and parity.get("release") == expected_release_label
        and parity.get("evas_engine") == "evas2"
        and parity.get("task_count") == 1200
        and parity.get("pass_count") == 1200
        and parity.get("fail_count") == 0
    ):
        problems.append(f"{release_revision} profile parity summary is incomplete")

    if int(release_revision.removeprefix("r")) >= 46:
        manifest_sha256 = None
        if release is None or not (release / "MANIFEST.json").is_file():
            problems.append(f"{release_revision} evidence audit lacks a release manifest binding target")
        else:
            manifest_sha256 = file_sha(release / "MANIFEST.json")
        if not valid_sha256(source_registry_sha256):
            problems.append(f"{release_revision} evidence audit lacks a source registry binding target")

        expected_schemas = {
            artifacts[0]: f"v4-{release_revision}-rust-evas2-certification-report-v2",
            artifacts[1]: f"v4-{release_revision}-stimulus-metamorphic-compact-v1",
            artifacts[2]: "v4-profile-parity-evas2-smoke-v1",
        }
        for relative, expected_schema in expected_schemas.items():
            payload = payloads.get(relative)
            if payload is not None and payload.get("schema_version") != expected_schema:
                problems.append(
                    f"{relative} schema mismatch: "
                    f"declared={payload.get('schema_version')!r} expected={expected_schema!r}"
                )

        require_source_revision = release_revision in {"r51", "r52", "r53"}
        expected_evas_version = EVAS_VERSION_BY_REVISION.get(
            release_revision, "0.8.3"
        )
        if rust and not rust_evas2_runtime(
            rust.get("runtime"),
            require_source_revision=require_source_revision,
            expected_version=expected_evas_version,
        ):
            problems.append(
                f"{release_revision} Rust certification lacks EVAS "
                f"{expected_evas_version} Rust runtime markers"
            )
        if metamorphic and not (
            rust_evas2_runtime(
                metamorphic,
                expected_version=expected_evas_version,
            )
            and (
                not require_source_revision
                or rust_evas2_runtime(
                    metamorphic.get("runtime"),
                    require_source_revision=True,
                    expected_version=expected_evas_version,
                )
            )
        ):
            problems.append(
                f"{release_revision} metamorphic evidence lacks EVAS "
                f"{expected_evas_version} Rust runtime markers"
            )
        if parity and not (
            rust_evas2_runtime(
                parity,
                backend_key="evas_backend_required",
                expected_version=expected_evas_version,
            )
            and rust_evas2_runtime(
                parity.get("runtime"),
                require_source_revision=require_source_revision,
                expected_version=expected_evas_version,
            )
        ):
            problems.append(
                f"{release_revision} profile evidence lacks EVAS "
                f"{expected_evas_version} Rust runtime markers"
            )

        if rust and rust.get("source_certification_definition_sha256") != source_definition_sha256:
            problems.append(f"{release_revision} Rust certification source definition binding mismatch")
        for label, payload in (
            ("metamorphic evidence", metamorphic),
            ("profile evidence", parity),
        ):
            if payload and payload.get("source_score_denominator_registry_sha256") != source_registry_sha256:
                problems.append(f"{release_revision} {label} source registry binding mismatch")
        for label, payload in (
            ("metamorphic evidence", metamorphic),
            ("profile evidence", parity),
        ):
            if payload and payload.get("release_manifest_sha256") != manifest_sha256:
                problems.append(f"{release_revision} {label} release manifest binding mismatch")

        rust_inputs = rust.get("input_report_sha256") if rust else None
        if rust and not (
            isinstance(rust_inputs, list)
            and bool(rust_inputs)
            and all(
                isinstance(item, dict)
                and isinstance(item.get("name"), str)
                and bool(item.get("name"))
                and valid_sha256(item.get("sha256"))
                for item in rust_inputs
            )
        ):
            problems.append(f"{release_revision} Rust certification input report binding is invalid")
        if metamorphic and not valid_sha256(metamorphic.get("input_report_sha256")):
            problems.append(f"{release_revision} metamorphic input report binding is invalid")
        if metamorphic and metamorphic.get("release_revision") != release_revision:
            problems.append(f"{release_revision} metamorphic release revision mismatch")
        if parity and parity.get("release_revision") != release_revision:
            problems.append(f"{release_revision} profile release revision mismatch")
    return hashes


def expected_task_id(form: str, family: str) -> str:
    offsets = {"dut": 0, "testbench": 500, "bugfix": 1000}
    value = offsets[form] + int(family)
    width = 3 if value < 1000 else 4
    return f"v4-{value:0{width}d}"


def expected_buggy_artifact_hashes(
    artifact_paths: list[str],
    changed_hashes: dict[str, str],
    solution: Path,
) -> dict[str, str]:
    return {
        artifact: changed_hashes.get(artifact, file_sha(solution / artifact))
        for artifact in artifact_paths
    }


def audit_source_certifications(
    source: Path,
    source_rows: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    return inspect_source_certification_reuse(source, source_rows)


def audit_standalone_evaluator(
    task_dir: Path,
    source_task: Path,
    form: str,
    prefix: str,
    problems: list[str],
) -> Path | None:
    evaluator = task_dir / "evaluator"
    source_eval = source_task / "evaluator"
    if not evaluator.is_dir():
        problems.append(f"{prefix} evaluator directory missing")
        return None
    for name in STANDALONE_EVALUATOR_COMMON:
        local = evaluator / name
        source = source_eval / name
        if not local.is_file():
            problems.append(f"{prefix} standalone evaluator missing {name}")
        elif not source.is_file() or file_sha(local) != file_sha(source):
            problems.append(f"{prefix} standalone evaluator {name} differs from canonical source")
    for directory in ("profiles",):
        local = evaluator / directory
        source = source_eval / directory
        if not local.is_dir():
            problems.append(f"{prefix} standalone evaluator missing {directory}/")
        elif tree_sha(local) != tree_sha(source):
            problems.append(f"{prefix} standalone evaluator {directory}/ differs from canonical source")
    local_solution = evaluator / "solution"
    if not local_solution.is_dir():
        problems.append(f"{prefix} standalone evaluator missing solution/")
    elif tree_file_hashes(local_solution) != expected_solution_file_hashes(source_task):
        problems.append(f"{prefix} standalone evaluator solution/ differs from canonical source/support")
    if form == "testbench":
        local_catalog = evaluator / "mutation_catalog.json"
        source_catalog = source_eval / "mutation_catalog.json"
        if not local_catalog.is_file():
            problems.append(f"{prefix} standalone testbench evaluator missing mutation_catalog.json")
        elif file_sha(local_catalog) != file_sha(source_catalog):
            problems.append(f"{prefix} standalone testbench evaluator mutation_catalog.json differs from canonical source")
        local_mutations = evaluator / "mutation_bundles"
        source_mutations = source_eval / "mutation_bundles"
        if not local_mutations.is_dir():
            problems.append(f"{prefix} standalone testbench evaluator missing mutation_bundles/")
        elif tree_sha(local_mutations) != tree_sha_skipping(source_mutations, excluded_names={"certification.json"}):
            problems.append(f"{prefix} standalone testbench evaluator mutation_bundles/ scoring files differ from canonical source")
        if list(local_mutations.rglob("certification.json")):
            problems.append(f"{prefix} standalone testbench evaluator should not copy negative certification files")
    score_policy = evaluator / "score_policy.json"
    if not score_policy.is_file():
        problems.append(f"{prefix} evaluator missing score_policy.json")
    else:
        score = read_json(score_policy)
        if "source_checker_profile" in score:
            problems.append(f"{prefix} score policy keeps external source_checker_profile reference")
        if score.get("materialized_checker_profile") != "evaluator/checker_profile.json":
            problems.append(f"{prefix} score policy does not point at materialized checker_profile.json")
        if score.get("checker_profile_sha256") != file_sha(evaluator / "checker_profile.json"):
            problems.append(f"{prefix} score policy checker_profile hash mismatch")
    return evaluator


def source_task_for_family(source: Path, source_rows: dict[str, dict[str, Any]], family: str) -> Path | None:
    row = source_rows.get(family)
    if row is None:
        return None
    return source / str(row.get("release_dir") or "")


def audit_task(
    release: Path,
    source: Path,
    source_rows: dict[str, dict[str, Any]],
    row: dict[str, Any],
    problems: list[str],
    release_revision: str = "r45",
) -> str | None:
    task_dir = release / str(row.get("task_dir") or "")
    task_dir_parts = Path(str(row.get("task_dir") or "")).parts
    task_id = str(row.get("task_id") or "")
    form = str(row.get("form") or "")
    family = str(row.get("family_id") or "")
    prefix = f"{task_id or task_dir.name}:"
    if not task_dir.is_dir():
        problems.append(f"{prefix} task directory missing")
        return
    if len(task_dir_parts) != 2 or task_dir_parts[0] != "tasks":
        problems.append(f"{prefix} task directory is not flat under tasks/")
    required_paths = [
        "task_record.json", "public/instruction.md", "public_contract.json", "evaluator",
    ]
    if release_revision != "r44":
        required_paths.append("public/evas_runtime.json")
        if form in {"dut", "bugfix"}:
            required_paths.append("public/visible_test.scs")
    for required in required_paths:
        if not (task_dir / required).exists():
            problems.append(f"{prefix} missing {required}")
    if (task_dir / "provenance").exists():
        problems.append(f"{prefix} formal task package should not contain provenance/")
    if problems and not (task_dir / "task_record.json").is_file():
        return
    record = read_json(task_dir / "task_record.json")
    contract = read_json(task_dir / "public_contract.json")
    if release_revision != "r44":
        if record.get("release_revision") != release_revision:
            problems.append(
                f"{prefix} task record release revision mismatch: "
                f"declared={record.get('release_revision')!r} selected={release_revision!r}"
            )
        expected_record_schema = f"{release_revision}-benchmarkv4-task-record-v1"
        if record.get("schema_version") != expected_record_schema:
            problems.append(
                f"{prefix} task record schema mismatch: "
                f"declared={record.get('schema_version')!r} expected={expected_record_schema!r}"
            )
        runtime_path = task_dir / "public" / "evas_runtime.json"
        if runtime_path.is_file():
            runtime = read_json(runtime_path)
            allowed_schemas = allowed_runtime_schemas(release_revision, form)
            if runtime.get("schema_version") not in allowed_schemas:
                problems.append(
                    f"{prefix} public EVAS runtime schema mismatch: "
                    f"declared={runtime.get('schema_version')!r} "
                    f"allowed={sorted(allowed_schemas)!r}"
                )
        if "feedback" in contract:
            problems.append(f"{prefix} public contract retains feedback broker entry")
        if not isinstance(contract.get("evas"), dict):
            problems.append(f"{prefix} public contract lacks direct EVAS entry")
    expected_contract = rel(task_dir / "public_contract.json", release)
    if row.get("public_contract") != expected_contract or record.get("public_contract") != expected_contract:
        problems.append(f"{prefix} public contract path is not task-local")
    expected_contract_sha = file_sha(task_dir / "public_contract.json")
    if row.get("public_contract_sha256") != expected_contract_sha:
        problems.append(f"{prefix} task index public contract hash mismatch")
    if record.get("public_contract_sha256") != expected_contract_sha:
        problems.append(f"{prefix} task record public contract hash mismatch")
    if record.get("canonical_dut_source"):
        problems.append(f"{prefix} task record keeps external canonical_dut_source path")
    if task_id != expected_task_id(form, family):
        problems.append(f"{prefix} ID does not match form/family numbering")
    if record.get("task_id") != task_id or record.get("form") != form or record.get("family_id") != family:
        problems.append(f"{prefix} task record identity mismatch")
    if contract.get("task_id") != task_id or contract.get("form") != form or str(contract.get("family_id")) != family:
        problems.append(f"{prefix} public contract identity mismatch")
    if record.get("public_bundle_sha256") != public_bundle_hash(task_dir):
        problems.append(f"{prefix} public bundle hash mismatch")
    source_row = source_rows.get(family)
    source_task = source_task_for_family(source, source_rows, family)
    if source_row is None or source_task is None or not source_task.is_dir():
        problems.append(f"{prefix} canonical denominator row missing")
        return
    if record.get("canonical_dut_source_slug") != source_task.name:
        problems.append(f"{prefix} source slug does not match denominator row")
    spec_path = source_task / "evaluator" / "family_spec.json"
    if not spec_path.is_file() or record.get("family_spec_sha256") != file_sha(spec_path):
        problems.append(f"{prefix} family spec hash mismatch")
        return
    spec = read_json(spec_path)
    artifact_paths = [str(item["path"]) for item in spec["artifact_contract"]["files"]]
    instruction_text = (task_dir / "public" / "instruction.md").read_text(encoding="utf-8")
    for marker in ("test_visible", "Public visible tests", "hidden evaluator", "Vela"):
        if marker in instruction_text:
            problems.append(f"{prefix} instruction leaks run/evaluator marker {marker!r}")
    if form != "testbench" and "visible testbench" in instruction_text.lower():
        problems.append(f"{prefix} non-testbench instruction leaks visible testbench wording")
    evaluator = audit_standalone_evaluator(task_dir, source_task, form, prefix, problems)
    if evaluator is None:
        return
    if release_revision != "r44":
        binding = record.get("evaluation_binding") or {}
        if form in {"dut", "bugfix"}:
            visible = task_dir / "public" / "visible_test.scs"
            runtime_contract = task_dir / "public" / "evas_runtime.json"
            trusted = evaluator / "trusted_replay_test.scs"
            profile_path = evaluator / "canonical_test_profile.json"
            if binding.get("kind") != "canonical_test_deck":
                problems.append(f"{prefix} task record lacks canonical test binding")
            if not trusted.is_file():
                problems.append(f"{prefix} evaluator missing trusted_replay_test.scs")
            elif visible.is_file() and visible.read_bytes() != trusted.read_bytes():
                problems.append(f"{prefix} visible test and trusted replay deck differ")
            if not profile_path.is_file():
                problems.append(f"{prefix} evaluator missing canonical_test_profile.json")
            elif visible.is_file():
                profile = read_json(profile_path)
                if profile.get("schema_version") != CANONICAL_TEST_PROFILE_SCHEMA:
                    problems.append(f"{prefix} canonical profile schema mismatch")
                if profile.get("test_deck_sha256") != file_sha(visible):
                    problems.append(f"{prefix} canonical profile deck hash mismatch")
                if binding.get("profile_sha256") != file_sha(profile_path):
                    problems.append(f"{prefix} canonical profile binding hash mismatch")
                if binding.get("test_deck_sha256") != file_sha(visible):
                    problems.append(f"{prefix} canonical deck binding hash mismatch")
            if not runtime_contract.is_file():
                problems.append(f"{prefix} public EVAS runtime contract is missing")
            else:
                runtime_data = read_json(runtime_contract)
                schema_version = runtime_data.get("schema_version")
                if schema_version not in allowed_runtime_schemas(release_revision, form):
                    problems.append(f"{prefix} public EVAS runtime schema is unsupported")
                if schema_version in {
                    f"{release_revision}-direct-evas-runtime-v2",
                    f"{release_revision}-direct-evas-runtime-v3",
                }:
                    command = str(runtime_data.get("command") or "")
                    if "/tmp/vabench-visible/evas-output" not in command or "public/submission/evas-output" in command:
                        problems.append(f"{prefix} public EVAS output is not isolated from submission")
                if schema_version == f"{release_revision}-direct-evas-runtime-v3":
                    if runtime_data.get("compatibility_mode") != "portable":
                        problems.append(f"{prefix} portable EVAS runtime mode is missing")
                    if "--spectre-strict" in str(runtime_data.get("command") or ""):
                        problems.append(f"{prefix} portable EVAS runtime still requests strict mode")
        elif release_revision not in REFERENCE_ONLY_TESTBENCH_REVISIONS:
            public_suite = task_dir / "public" / "evas_runtime.json"
            trusted_suite = evaluator / "trusted_replay_suite.json"
            public_fixtures = task_dir / "public" / "visible_fixtures"
            trusted_fixtures = evaluator / "trusted_replay_fixtures"
            if binding.get("kind") != "public_testbench_suite":
                problems.append(f"{prefix} task record lacks public testbench suite binding")
            if (task_dir / "public" / "visible_test.scs").exists():
                problems.append(f"{prefix} testbench view exposes gold-derived visible_test.scs")
            if (
                not public_suite.is_file()
                or not trusted_suite.is_file()
                or public_suite.read_bytes() != trusted_suite.read_bytes()
            ):
                problems.append(f"{prefix} public and trusted suite manifests differ")
            if (
                not public_fixtures.is_dir()
                or not trusted_fixtures.is_dir()
                or tree_sha(public_fixtures) != tree_sha(trusted_fixtures)
            ):
                problems.append(f"{prefix} public and trusted fixture trees differ")
            if public_suite.is_file() and binding.get("public_suite_sha256") != file_sha(public_suite):
                problems.append(f"{prefix} public suite binding hash mismatch")
            if public_suite.is_file():
                suite_data = read_json(public_suite)
                schema_version = suite_data.get("schema_version")
                if schema_version not in allowed_runtime_schemas(release_revision, form):
                    problems.append(f"{prefix} public testbench suite schema is unsupported")
                if schema_version in {
                    f"{release_revision}-direct-evas-testbench-suite-v2",
                    f"{release_revision}-direct-evas-testbench-suite-v3",
                }:
                    command = str(suite_data.get("candidate_command_template") or "")
                    if "/tmp/vabench-visible/runs/{case}" not in command:
                        problems.append(f"{prefix} public testbench runs are not scratch-isolated")
                    if "public/submission/runs" in command or "public/submission/evas-output" in command:
                        problems.append(f"{prefix} public testbench scratch pollutes submission")
                if schema_version == f"{release_revision}-direct-evas-testbench-suite-v3":
                    if suite_data.get("compatibility_mode") != "portable":
                        problems.append(f"{prefix} portable EVAS testbench mode is missing")
                    if "--spectre-strict" in str(suite_data.get("candidate_command_template") or ""):
                        problems.append(f"{prefix} portable EVAS testbench still requests strict mode")
            if public_fixtures.is_dir() and binding.get("public_fixture_tree_sha256") != tree_sha(public_fixtures):
                problems.append(f"{prefix} public fixture binding hash mismatch")
        else:
            public_runtime = task_dir / "public" / "evas_runtime.json"
            public_reference = task_dir / "public" / "supplied_dut"
            trusted_suite = evaluator / "trusted_replay_suite.json"
            trusted_fixtures = evaluator / "trusted_replay_fixtures"
            trusted_reference = trusted_fixtures / "reference" / "dut"
            if binding.get("kind") != "reference_only_public_testbench":
                problems.append(
                    f"{prefix} task record lacks reference-only public testbench binding"
                )
            if (task_dir / "public" / "visible_fixtures").exists():
                problems.append(f"{prefix} public testbench view exposes private fixtures")
            if not public_runtime.is_file():
                problems.append(f"{prefix} reference-only public runtime is missing")
            else:
                runtime_data = read_json(public_runtime)
                if (
                    runtime_data.get("schema_version")
                    != f"{release_revision}-direct-evas-testbench-reference-v1"
                ):
                    problems.append(f"{prefix} reference-only public runtime schema mismatch")
                if runtime_data.get("feedback_scope") != "reference_dut_only":
                    problems.append(f"{prefix} public feedback is not reference-only")
                if re.search(
                    r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                    json.dumps(runtime_data, sort_keys=True),
                ):
                    problems.append(f"{prefix} public runtime leaks private mutation identity")
                if binding.get("public_runtime_sha256") != file_sha(public_runtime):
                    problems.append(f"{prefix} reference-only public runtime hash mismatch")
            if not trusted_suite.is_file() or not trusted_fixtures.is_dir():
                problems.append(f"{prefix} private trusted replay suite is incomplete")
            else:
                trusted_data = read_json(trusted_suite)
                expected_cases = [
                    "reference",
                    "mutation_01",
                    "mutation_02",
                    "mutation_03",
                    "mutation_04",
                    "mutation_05",
                ]
                if [item.get("case") for item in trusted_data.get("cases") or []] != expected_cases:
                    problems.append(f"{prefix} private trusted replay is not reference plus five")
                if binding.get("trusted_replay_suite_sha256") != file_sha(trusted_suite):
                    problems.append(f"{prefix} private trusted replay suite hash mismatch")
                if binding.get("trusted_replay_fixture_tree_sha256") != tree_sha(trusted_fixtures):
                    problems.append(f"{prefix} private trusted replay fixture hash mismatch")
            if public_reference.is_dir() and trusted_reference.is_dir():
                public_reference_sha = tree_sha(public_reference)
                trusted_reference_sha = tree_sha(trusted_reference)
                if (
                    public_reference_sha != trusted_reference_sha
                    or binding.get("public_reference_dut_tree_sha256")
                    != public_reference_sha
                    or binding.get("trusted_reference_dut_tree_sha256")
                    != trusted_reference_sha
                ):
                    problems.append(f"{prefix} public/trusted reference DUT binding mismatch")
            else:
                problems.append(f"{prefix} public or trusted reference DUT is missing")
    checker_profile = read_json(evaluator / "checker_profile.json")
    if record.get("checker_task_id") != checker_profile.get("checker_task_id"):
        problems.append(f"{prefix} task record checker_task_id does not match checker_profile.json")
    if form == "dut":
        if record.get("candidate_artifacts") != artifact_paths:
            problems.append(f"{prefix} DUT candidate artifacts differ from family spec")
        score = read_json(evaluator / "score_policy.json")
        if score.get("gold_solution_tree_sha256") != tree_sha(evaluator / "solution"):
            problems.append(f"{prefix} DUT gold solution hash mismatch")
        if score.get("gold_dut_certification_sha256") != (
            source_row.get("hashes") or {}
        ).get("task_certification_sha256"):
            problems.append(f"{prefix} gold DUT certification hash mismatch")
        return
    score = read_json(evaluator / "score_policy.json")
    active_mutations = source_row.get("active_mutations") or []
    expected_suite = [str(item.get("mutation_id") or "") for item in active_mutations]
    if form == "testbench":
        suite = score.get("negative_suite_mutation_ids") or []
        if len(suite) != 5 or len(set(suite)) != 5:
            problems.append(f"{prefix} testbench suite is not exactly five unique mutations")
        if suite != expected_suite:
            problems.append(f"{prefix} testbench suite differs from the exact-five denominator")
        if score.get("bugfix_seed_mutation_id") not in suite:
            problems.append(f"{prefix} bugfix seed is not a member of the testbench suite")
        if score.get("mutation_catalog_sha256") != file_sha(source_task / "evaluator" / "mutation_catalog.json"):
            problems.append(f"{prefix} mutation catalog hash mismatch")
    if form == "testbench":
        if record.get("candidate_artifacts") != ["testbench.scs"] or contract.get("target_artifacts") != ["testbench.scs"]:
            problems.append(f"{prefix} testbench output is not exactly testbench.scs")
        if score.get("candidate_artifacts") != ["testbench.scs"] or score.get("kill_ratio_denominator") != 5:
            problems.append(f"{prefix} testbench score policy mismatch")
        supplied = task_dir / "public" / "supplied_dut"
        if tree_file_hashes(supplied) != expected_solution_file_hashes(source_task):
            problems.append(f"{prefix} supplied DUT differs from canonical gold")
        if release_revision not in {"r44", *REFERENCE_ONLY_TESTBENCH_REVISIONS}:
            fixture_names = sorted(
                path.name for path in (task_dir / "public" / "visible_fixtures").iterdir()
                if path.is_dir()
            ) if (task_dir / "public" / "visible_fixtures").is_dir() else []
            if fixture_names != [
                "mutation_01", "mutation_02", "mutation_03", "mutation_04", "mutation_05", "reference",
            ]:
                problems.append(f"{prefix} visible suite is not one reference plus five mutations")
        if release_revision in REFERENCE_ONLY_TESTBENCH_REVISIONS:
            public_root = task_dir / "public"
            leaked_paths = [
                path.relative_to(public_root).as_posix()
                for path in public_root.rglob("*")
                if re.search(
                    r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                    path.name,
                    flags=re.IGNORECASE,
                )
            ]
            leaked_content = [
                path.relative_to(public_root).as_posix()
                for path in public_root.rglob("*")
                if path.is_file()
                and re.search(
                    r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                    path.read_text(encoding="utf-8", errors="ignore"),
                    flags=re.IGNORECASE,
                )
            ]
            if leaked_paths or leaked_content:
                problems.append(
                    f"{prefix} public testbench bundle leaks private mutation surface"
                )
        reference_tb_source_kind = audit_testbench_reference(
            evaluator, source_task, score, prefix, problems
        )
        public_text = instruction_text + json.dumps(contract)
        if "neg_" in public_text or "mutation_id" in public_text:
            problems.append(f"{prefix} public testbench view leaks negative identity")
        return reference_tb_source_kind
    elif form == "bugfix":
        if record.get("candidate_artifacts") != artifact_paths or contract.get("target_artifacts") != artifact_paths:
            problems.append(f"{prefix} bugfix artifact contract mismatch")
        buggy = task_dir / "public" / "buggy_bundle"
        buggy_paths = sorted(path.relative_to(buggy).as_posix() for path in buggy.rglob("*.va"))
        if buggy_paths != sorted(artifact_paths):
            problems.append(f"{prefix} buggy bundle file set mismatch")
        seed_id = str(score.get("bugfix_seed_mutation_id") or "")
        if seed_id not in expected_suite:
            problems.append(f"{prefix} bugfix seed is not a member of the exact-five denominator")
        if score.get("mutation_catalog_sha256") != file_sha(source_task / "evaluator" / "mutation_catalog.json"):
            problems.append(f"{prefix} mutation catalog hash mismatch")
        mutation_catalog = read_json(source_task / "evaluator" / "mutation_catalog.json")
        mutation_rows = {str(item.get("id") or ""): item for item in mutation_catalog.get("mutations") or []}
        seed_catalog = mutation_rows.get(seed_id)
        if seed_catalog is None:
            problems.append(f"{prefix} bugfix seed is missing from the canonical mutation catalog")
        else:
            expected_hashes = expected_buggy_artifact_hashes(
                artifact_paths,
                seed_catalog.get("artifact_hashes") or {},
                source_task / "evaluator" / "solution",
            )
            actual_hashes = {
                path.relative_to(buggy).as_posix(): file_sha(path)
                for path in buggy.rglob("*.va")
            }
            if actual_hashes != expected_hashes:
                problems.append(f"{prefix} buggy bundle differs from the selected canonical mutation")
        if tree_sha(buggy) == tree_sha(source_task / "evaluator" / "solution"):
            problems.append(f"{prefix} buggy bundle is byte-identical to gold")
        if score.get("buggy_bundle_sha256") != tree_sha(buggy):
            problems.append(f"{prefix} buggy bundle hash mismatch")
        if score.get("gold_solution_tree_sha256") != tree_sha(evaluator / "solution"):
            problems.append(f"{prefix} gold repair solution hash mismatch")
        if score.get("gold_dut_certification_sha256") != (
            source_row.get("hashes") or {}
        ).get("task_certification_sha256"):
            problems.append(f"{prefix} gold DUT certification hash mismatch")
        public_text = instruction_text + json.dumps(contract)
        forbidden = ("neg_", "faulty file", "root cause", "changed line", "public summary")
        for marker in forbidden:
            if marker.lower() in public_text.lower():
                problems.append(f"{prefix} public bugfix view leaks forbidden marker {marker!r}")
        if re.search(r"\bmutation\b", public_text, re.IGNORECASE):
            problems.append(f"{prefix} public bugfix view leaks forbidden marker 'mutation'")
        if score.get("bugfix_seed_selection_status") != "policy_reviewed" or score.get("bugfix_seed_triviality_markers"):
            problems.append(f"{prefix} bugfix seed lacks nontrivial semantic review")


def iter_prompt_public_inputs(task_dir: Path, form: str) -> list[Path]:
    public = task_dir / "public"
    inputs = [public / "instruction.md"]
    if form == "testbench":
        inputs.extend(sorted((public / "supplied_dut").rglob("*.va")))
    elif form == "bugfix":
        inputs.extend(sorted((public / "buggy_bundle").rglob("*.va")))
    return inputs


def audit_prompt_components(
    release: Path,
    tasks: list[dict[str, Any]],
    problems: list[str],
    release_revision: str = "r45",
) -> int:
    if (release / "prompt_modes" / "PROMPT_RECORDS.jsonl").exists():
        problems.append("release should not include prompt_modes/PROMPT_RECORDS.jsonl")
    component_manifest = read_json(release / "prompt_modes" / "manifest.json")
    mode_manifest = read_json(release / "prompt_modes" / "modes.json")
    wrapper_records = component_manifest.get("wrappers") or {}
    component_records = component_manifest.get("components") or dict(wrapper_records)
    tokenizer = component_manifest.get("reference_tokenizer") or {}
    tokenizer_key = f"{tokenizer.get('id')}@{tokenizer.get('version')}"
    required_wrappers = set(WRAPPERS_BY_MODE.values())
    if set(wrapper_records) != required_wrappers:
        problems.append("component manifest wrapper set mismatch")
    if release_uses_real_skills(release_revision):
        if component_manifest.get("form_skills") or component_manifest.get("evas_guides"):
            problems.append("real-skill release still declares legacy inline guide sets")
        skill_manifest_path = release / "skills" / "SNAPSHOT_MANIFEST.json"
        if not skill_manifest_path.is_file():
            problems.append("real-skill release is missing skills/SNAPSHOT_MANIFEST.json")
            skill_manifest = {}
        else:
            skill_manifest = read_json(skill_manifest_path)
            if skill_manifest.get("schema_version") != "v4-real-skill-snapshot-manifest-v1":
                problems.append("skill snapshot manifest schema mismatch")
        skills = skill_manifest.get("skills") or {}
        if not isinstance(skills, dict):
            problems.append("skill snapshot manifest skills must be an object")
            skills = {}
        if set(skills) != {"veriloga", "vabench-feedback"}:
            problems.append("skill snapshot set mismatch")
        expected_matrix = {
            "G0": [],
            "G1": ["veriloga"],
            "G2": [],
            "G3": ["veriloga"],
            "G4": ["vabench-feedback"],
            "G5": ["veriloga", "vabench-feedback"],
        }
        if skill_manifest.get("mode_skill_matrix") != expected_matrix:
            problems.append("skill mode matrix mismatch")
        for skill_id, record in skills.items():
            if not isinstance(record, dict):
                problems.append(f"skill snapshot {skill_id}: invalid record")
                continue
            skill_root = release / "skills" / skill_id
            if record.get("path") != f"skills/{skill_id}":
                problems.append(f"skill snapshot {skill_id}: unexpected package path")
            if record.get("skill_file") != f"skills/{skill_id}/SKILL.md":
                problems.append(f"skill snapshot {skill_id}: unexpected SKILL.md path")
            if skill_root.is_symlink() or any(
                item.is_symlink() for item in skill_root.rglob("*")
            ):
                problems.append(f"skill snapshot {skill_id}: symlink is not allowed")
            if not (skill_root / "SKILL.md").is_file():
                problems.append(f"skill snapshot {skill_id}: missing SKILL.md")
            elif record.get("tree_sha256") != tree_sha_skipping(skill_root, excluded_names=set()):
                problems.append(f"skill snapshot {skill_id}: tree hash mismatch")
            actual_files = {
                item.relative_to(skill_root).as_posix(): {
                    "sha256": file_sha(item),
                    "bytes": item.stat().st_size,
                }
                for item in sorted(skill_root.rglob("*"))
                if item.is_file() and not item.is_symlink()
            } if skill_root.is_dir() and not skill_root.is_symlink() else {}
            declared_files: dict[str, dict[str, Any]] = {}
            for item in record.get("files") or []:
                if not isinstance(item, dict):
                    problems.append(f"skill snapshot {skill_id}: invalid file record")
                    continue
                relative = Path(str(item.get("path") or ""))
                relative_key = relative.as_posix()
                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or relative_key in {"", "."}
                    or relative_key in declared_files
                ):
                    problems.append(f"skill snapshot {skill_id}: invalid file path")
                    continue
                declared_files[relative_key] = {
                    "sha256": item.get("sha256"),
                    "bytes": item.get("bytes"),
                }
            if declared_files != actual_files:
                problems.append(f"skill snapshot {skill_id}: file index mismatch")
            for item in record.get("files") or []:
                source_path = Path(str(item.get("source_path") or ""))
                if source_path.is_absolute() or source_path.parts[:2] != ("skills", skill_id):
                    problems.append(f"skill snapshot {skill_id}: invalid source path")
                    break
            source = record.get("source") or {}
            if skill_id == "veriloga":
                if (
                    source.get("type") != "vendored_runtime_subset"
                    or source.get("upstream_repository")
                    != "https://github.com/Arcadia-1/veriloga-skills"
                    or source.get("upstream_pull_request")
                    != "https://github.com/Arcadia-1/veriloga-skills/pull/17"
                    or not valid_git_oid(source.get("upstream_commit"))
                ):
                    problems.append("veriloga skill snapshot provenance mismatch")
            elif source != {"type": "in_repository", "path": "skills/vabench-feedback"}:
                problems.append("feedback skill snapshot provenance mismatch")
    else:
        form_skill_records = component_manifest.get("form_skills") or {}
        guide_manifest_key = "feedback_guides" if release_revision == "r44" else "evas_guides"
        guide_records = component_manifest.get(guide_manifest_key) or {}
        component_records = component_manifest.get("components") or {
            **wrapper_records,
            **form_skill_records,
            **guide_records,
        }
        required_form_skills = set(FORM_SKILLS.values())
        core_guide = FEEDBACK_CORE if release_revision == "r44" else EVAS_CORE
        form_guides = FEEDBACK_GUIDES if release_revision == "r44" else EVAS_GUIDES
        required_guides = {core_guide, *form_guides.values()}
        if set(form_skill_records) != required_form_skills:
            problems.append("component manifest form-skill set mismatch")
        if set(guide_records) != required_guides:
            problems.append(f"component manifest {guide_manifest_key.replace('_', '-')} set mismatch")
        if set(component_records) != required_wrappers | required_form_skills | required_guides:
            problems.append("component manifest component set mismatch")
    if release_uses_real_skills(release_revision) and set(component_records) != required_wrappers:
        problems.append("component manifest component set mismatch")
    if (release / "prompt_modes" / "skills").exists():
        problems.append("legacy prompt_modes/skills/ directory should not be present")
    for name, component in component_records.items():
        for field in ("stable_id", "semantic_version", "applicable_forms", "sha256", "bytes", "license", "provenance", "token_counts"):
            if field not in component:
                problems.append(f"component manifest {name}: missing {field}")
        if tokenizer_key not in (component.get("token_counts") or {}):
            problems.append(f"component manifest {name}: missing reference-tokenizer count")
        expected_path = prompt_component_path(release, name)
        if component.get("path") != expected_path.relative_to(release).as_posix():
            problems.append(f"component manifest {name}: path does not match component kind")
        if expected_path.is_file() and component.get("sha256") != file_sha(expected_path):
            problems.append(f"component manifest {name}: sha256 mismatch")
    mode_records = mode_manifest.get("modes") or {}
    if set(mode_records) != set(MODES):
        problems.append("prompt mode registry does not define exactly G0-G5")
    count = 0
    for task in tasks:
        task_id = str(task.get("task_id") or "")
        form = str(task.get("form") or "")
        task_dir = release / str(task.get("task_dir") or "")
        for mode in MODES:
            count += 1
            policy = mode_records.get(mode) or {}
            expected_cli = mode in AGENTIC_MODES
            cli_field = "feedback_cli" if release_revision == "r44" else "evas_cli"
            if bool(policy.get(cli_field)) is not expected_cli:
                problems.append(f"{task_id}/{mode}: {cli_field} availability mismatch")
            public_inputs = iter_prompt_public_inputs(task_dir, form)
            for item in public_inputs:
                if not item.is_file():
                    problems.append(f"{task_id}/{mode}: prompt public input missing: {item.relative_to(task_dir)}")
            expected_components: list[str] = []
            if not release_uses_real_skills(release_revision) and mode in {"G1", "G3", "G5"}:
                expected_components.append(FORM_SKILLS.get(form, ""))
            if not release_uses_real_skills(release_revision) and mode in {"G4", "G5"}:
                expected_components.extend([core_guide, form_guides.get(form, "")])
            expected_components.append(WRAPPERS_BY_MODE.get(mode, ""))
            for name in expected_components:
                component = component_records.get(name) or {}
                if component.get("sha256") != file_sha(prompt_component_path(release, name)):
                    problems.append(f"{task_id}/{mode}: prompt component hash mismatch for {name}")
            if mode in DIRECT_MODES:
                direct_text_parts = [item.read_text(encoding="utf-8", errors="replace") for item in public_inputs if item.is_file()]
                direct_text_parts.extend(
                    prompt_component_path(release, name).read_text(encoding="utf-8", errors="replace")
                    for name in expected_components
                    if name in component_records
                )
                direct_text = "\n".join(direct_text_parts)
                for marker in (
                    "Feedback tools",
                    "feedback CLI",
                    "public/submission",
                    "agentic mode",
                    "mounted public task inputs",
                ):
                    if marker.lower() in direct_text.lower():
                        problems.append(f"{task_id}/{mode}: direct prompt leaks {marker!r}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-revision",
        choices=tuple(DEFAULT_RELEASES),
        required=True,
        help="selects the task contract, evidence namespace, and seal identity",
    )
    parser.add_argument("--release", type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seal-output", type=Path)
    args = parser.parse_args()
    release_revision = str(args.release_revision)
    release = (args.release or DEFAULT_RELEASES[release_revision]).expanduser().resolve()
    source = args.source.expanduser().resolve()
    manifest = read_json(release / "MANIFEST.json")
    task_index = read_json(release / "TASK_INDEX.json")
    tasks = task_index.get("tasks") or []
    problems: list[str] = []
    if manifest.get("release_revision") != release_revision:
        problems.append(
            "manifest release revision mismatch: "
            f"declared={manifest.get('release_revision')!r} selected={release_revision!r}"
        )
    if release_revision == "r53":
        runtime_requirements = manifest.get("runtime_requirements") or {}
        if (
            runtime_requirements.get("evas_package") != "evas-sim"
            or runtime_requirements.get("evas_version") != "0.8.7"
            or runtime_requirements.get("experiment_policy")
            != "EXPERIMENT_POLICY.json"
            or runtime_requirements.get("experiment_policy_sha256")
            != file_sha(PACKAGE_ROOT / "EXPERIMENT_POLICY.json")
        ):
            problems.append(
                "r53 manifest does not bind EVAS 0.8.7 and the canonical "
                "experiment policy"
            )
    if release_revision != "r44":
        expected_manifest_schema = f"{release_revision}-benchmarkv4-release-manifest-v1"
        if manifest.get("schema_version") != expected_manifest_schema:
            problems.append(
                "manifest schema mismatch: "
                f"declared={manifest.get('schema_version')!r} expected={expected_manifest_schema!r}"
            )
        expected_index_schema = f"{release_revision}-benchmarkv4-task-index-v1"
        if task_index.get("schema_version") != expected_index_schema:
            problems.append(
                "task index schema mismatch: "
                f"declared={task_index.get('schema_version')!r} expected={expected_index_schema!r}"
            )
    if (release / "private_evaluator").exists():
        problems.append("top-level private_evaluator/ should not exist in standalone benchmarkv4")
    if (release / "public_contracts").exists():
        problems.append("top-level public_contracts/ should not exist in standalone benchmarkv4")
    for legacy_form_dir in FORMS:
        if (release / "tasks" / legacy_form_dir).exists():
            problems.append(f"legacy form directory should not exist under tasks/: {legacy_form_dir}")
    source_rows_list = load_family_rows(source)
    source_registry_sha = score_denominator_registry_sha256(source)
    source_rows = {
        str(item.get("canonical_dut_id") or ""): item
        for item in source_rows_list
    }
    source_definition_sha = source_certification_definition_sha256(source, source_rows)
    expected_artifacts = materialized_artifacts_for_revision(release_revision)
    expected_materialized_hashes = {
        relative: file_sha(release / relative)
        for relative in expected_artifacts
        if (release / relative).is_file()
    }
    if set(expected_materialized_hashes) != set(expected_artifacts):
        problems.append("one or more materialized release artifacts are missing")
    if manifest.get("materialized_artifact_sha256") != expected_materialized_hashes:
        problems.append("materialized artifact hash binding mismatch")
    if manifest.get("source_release") or manifest.get("private_evaluator"):
        problems.append("manifest keeps legacy external source/private evaluator path")
    if manifest.get("source_release_label") != source.name:
        problems.append("manifest source release label mismatch")
    if manifest.get("source_score_denominator_registry_sha256") != source_registry_sha:
        problems.append("manifest source denominator hash mismatch")
    certification_reuse, certification_problems = audit_source_certifications(
        source, source_rows
    )
    if manifest.get("certification_reuse") != certification_reuse:
        problems.append("manifest certification reuse summary does not match source inputs")
    if manifest.get("simulation_rerun_required_for_materialization") != certification_reuse.get(
        "simulation_rerun_required_for_materialization"
    ):
        problems.append("manifest simulation rerun requirement does not match source inputs")
    counts = Counter(str(row.get("form") or "") for row in tasks)
    if len(tasks) != 1200 or counts != Counter({form: 400 for form in FORMS}):
        problems.append(f"task counts mismatch: total={len(tasks)} forms={dict(counts)}")
    family_forms: dict[str, set[str]] = defaultdict(set)
    reference_tb_source_counts: Counter[str] = Counter()
    for row in tasks:
        family_forms[str(row.get("family_id") or "")].add(str(row.get("form") or ""))
        source_kind = audit_task(
            release,
            source,
            source_rows,
            row,
            problems,
            release_revision,
        )
        if source_kind:
            reference_tb_source_counts[source_kind] += 1
    expected_families = {f"{value:03d}" for value in range(1, 401)}
    if set(family_forms) != expected_families:
        problems.append("family coverage is not exactly 001-400")
    for family in expected_families:
        if family_forms[family] != set(FORMS):
            problems.append(f"{family}: missing one or more task forms")
    task_by_family_form = {
        (str(row.get("family_id") or ""), str(row.get("form") or "")): release / str(row.get("task_dir") or "")
        for row in tasks
    }
    for family in sorted(expected_families):
        testbench_dir = task_by_family_form.get((family, "testbench"))
        bugfix_dir = task_by_family_form.get((family, "bugfix"))
        if testbench_dir is None or bugfix_dir is None:
            continue
        testbench_seed = read_json(testbench_dir / "evaluator" / "score_policy.json").get("bugfix_seed_mutation_id")
        bugfix_seed = read_json(bugfix_dir / "evaluator" / "score_policy.json").get("bugfix_seed_mutation_id")
        if testbench_seed != bugfix_seed:
            problems.append(f"{family}: cross-form bugfix seed mismatch: testbench={testbench_seed} bugfix={bugfix_seed}")
    prompt_count = audit_prompt_components(release, tasks, problems, release_revision)
    if prompt_count != 7200:
        problems.append(f"prompt record count is {prompt_count}, expected 7200")
    evidence_hashes = audit_release_evidence(
        release_revision,
        problems,
        release=release,
        source_registry_sha256=source_registry_sha,
        source_definition_sha256=source_definition_sha,
    )
    report = {
        "schema_version": "v4-benchmarkv4-release-audit-v1",
        "release_revision": release_revision,
        "status": "pass" if not problems else "fail",
        "family_count": len(family_forms),
        "task_count": len(tasks),
        "task_counts": dict(sorted(counts.items())),
        "prompt_record_count": prompt_count,
        "testbench_reference_source_counts": dict(sorted(reference_tb_source_counts.items())),
        "certification_reuse": certification_reuse,
        "certification_status": (
            "refresh_required"
            if certification_reuse.get("simulation_rerun_required_for_materialization")
            else (
                "source_certification_reused"
                if release_revision == "r53"
                else "rust_evas2_certified"
            )
        ),
        "certification_problems": certification_problems,
        "input_hashes": {
            "source_score_denominator_registry_sha256": source_registry_sha,
            "manifest_sha256": file_sha(release / "MANIFEST.json"),
            **expected_materialized_hashes,
            f"{release_revision}_evidence_sha256": evidence_hashes,
        },
        "problems": problems,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.seal_output:
        if problems:
            raise SystemExit("cannot seal release while audit problems remain")
        if not args.output:
            raise SystemExit("--seal-output requires --output so the audit report can be hash-bound")
        seal = build_release_seal(
            release,
            source_registry_sha,
            certification_reuse,
            certification_problems,
            evidence_hashes,
            release_revision=release_revision,
        )
        args.seal_output.parent.mkdir(parents=True, exist_ok=True)
        args.seal_output.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

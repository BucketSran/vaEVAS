#!/usr/bin/env python3
"""Validate source certification inputs before tri-form evidence reuse."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha_by_file_hash(path: Path, *, excluded_names: set[str] | None = None) -> str:
    """Match the canonical DUT evidence tree hash used by v4 certificates."""
    excluded_names = excluded_names or set()
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file() or item.name in excluded_names:
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def source_certification_definition_sha256(
    source: Path,
    source_rows: dict[str, dict[str, Any]],
) -> str:
    """Hash executable benchmark semantics without certification outputs.

    The denominator registry contains hashes of certificates and task records,
    so binding a report to that registry before rewriting certificates creates
    a circular dependency.  This definition deliberately binds only inputs to
    certification: static registry identity, task/checker/profile/deck inputs,
    gold sources, public task inputs, catalog semantics, and mutation sources.
    """
    repository_root = source.parents[2]
    families: list[dict[str, Any]] = []
    for family, original_row in sorted(source_rows.items()):
        row = deepcopy(original_row)
        row.pop("hashes", None)
        for mutation in row.get("active_mutations") or []:
            mutation.pop("certification_sha256", None)
            mutation.pop("mutation_bundle_sha256", None)

        task = source / str(row.get("release_dir") or "")
        evaluator = task / "evaluator"
        public = task / "public" / "task"
        checker_source = repository_root / "runners" / "checkers" / "v4" / f"task_{family}.py"
        if not checker_source.is_file():
            raise FileNotFoundError(f"missing checker source for family {family}: {checker_source}")
        catalog = read_json(evaluator / "mutation_catalog.json")
        catalog_semantics = deepcopy(catalog)
        for mutation in catalog_semantics.get("mutations") or []:
            certification = mutation.get("certification") or {}
            mutation["certification"] = {
                key: certification[key]
                for key in ("activated_property_ids", "profile")
                if key in certification
            }

        active_sources: dict[str, str] = {}
        for mutation in original_row.get("active_mutations") or []:
            mutation_id = str(mutation.get("mutation_id") or "")
            bundle = evaluator / "mutation_bundles" / mutation_id
            active_sources[mutation_id] = tree_sha_by_file_hash(
                bundle, excluded_names={"certification.json"}
            )

        families.append(
            {
                "family_id": family,
                "registry_row": row,
                "task_inputs": {
                    "checker_profile": file_sha(evaluator / "checker_profile.json"),
                    "checker_source": file_sha(checker_source),
                    "family_spec": file_sha(evaluator / "family_spec.json"),
                    "feedback_profile": file_sha(evaluator / "profiles" / "feedback.json"),
                    "gold_bundle": tree_sha_by_file_hash(evaluator / "solution"),
                    "harness_spec": file_sha(evaluator / "harness_spec.json"),
                    "score_deck": file_sha(evaluator / "score_tb.scs"),
                    "score_profile": file_sha(evaluator / "profiles" / "score.json"),
                    "public_task": tree_sha_by_file_hash(public),
                },
                "catalog_semantics": catalog_semantics,
                "active_mutation_sources": active_sources,
            }
        )
    canonical = json.dumps(
        {"schema_version": "v4-source-certification-definition-v1", "families": families},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _check_hash(
    *,
    family: str,
    label: str,
    path: Path,
    expected: Any,
    problems: list[str],
) -> bool:
    if not path.is_file():
        problems.append(f"{family}: source {label} is missing")
        return False
    actual = file_sha(path)
    if expected != actual:
        problems.append(f"{family}: source {label} mismatch")
        return False
    return True


def _check_mapping(
    *,
    family: str,
    label: str,
    actual: dict[str, Any],
    expected: dict[str, str],
    problems: list[str],
) -> bool:
    valid = True
    for name, sha in expected.items():
        if actual.get(name) != sha:
            problems.append(f"{family}: source {label} mismatch: {name}")
            valid = False
    return valid


def _task_input_hashes(source_task: Path) -> tuple[dict[str, str], dict[str, str]]:
    evaluator = source_task / "evaluator"
    public = source_task / "public" / "task"
    certificate_inputs = {
        "checker_profile": file_sha(evaluator / "checker_profile.json"),
        "family_spec": file_sha(evaluator / "family_spec.json"),
        "feedback_profile": file_sha(evaluator / "profiles" / "feedback.json"),
        "gold_bundle": tree_sha_by_file_hash(evaluator / "solution"),
        "harness_spec": file_sha(evaluator / "harness_spec.json"),
        "score_profile": file_sha(evaluator / "profiles" / "score.json"),
    }
    component_inputs = {
        "checker_profile_sha256": certificate_inputs["checker_profile"],
        "family_spec_sha256": certificate_inputs["family_spec"],
        "feedback_deck_sha256": file_sha(public / "feedback_tb.scs"),
        "feedback_profile_sha256": certificate_inputs["feedback_profile"],
        "gold_bundle_sha256": certificate_inputs["gold_bundle"],
        "harness_spec_sha256": certificate_inputs["harness_spec"],
        "score_deck_sha256": file_sha(evaluator / "score_tb.scs"),
        "score_profile_sha256": certificate_inputs["score_profile"],
    }
    return certificate_inputs, component_inputs


def _check_evidence_report(
    *, source: Path, family: str, certification: dict[str, Any], problems: list[str]
) -> bool:
    evidence = certification.get("evidence") or {}
    relative = Path(str(evidence.get("report_path") or ""))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        problems.append(f"{family}: source certification evidence path is unsafe")
        return False
    report = source.parents[1] / relative
    return _check_hash(
        family=family,
        label="certification evidence report hash",
        path=report,
        expected=evidence.get("report_sha256"),
        problems=problems,
    )


def inspect_source_certification_reuse(
    source: Path,
    source_rows: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    """Return exact reusable counts and every broken source hash binding.

    Outer denominator hashes are insufficient: a task record and certificate
    can remain byte-identical after one of their declared inputs changes.  This
    routine therefore validates the transitive task-record and certificate
    inputs before any tri-form release claims evidence reuse.
    """
    problems: list[str] = []
    reusable_gold = 0
    reusable_negatives = 0
    invalid_gold: list[str] = []
    invalid_negatives: list[str] = []
    stale_families: set[str] = set()
    negative_total = 0

    for family, row in sorted(source_rows.items()):
        source_task = source / str(row.get("release_dir") or "")
        evaluator = source_task / "evaluator"
        public = source_task / "public" / "task"
        row_hashes = row.get("hashes") or {}
        gold_valid = True
        if not source_task.is_dir():
            problems.append(f"{family}: source task directory is missing")
            invalid_gold.append(family)
            stale_families.add(family)
            negative_total += len(row.get("active_mutations") or [])
            invalid_negatives.extend(
                f"{family}/{item.get('mutation_id')}" for item in row.get("active_mutations") or []
            )
            continue

        record_path = evaluator / "task_record.json"
        certification_path = evaluator / "certification.json"
        for label, path, expected in (
            ("task record hash", record_path, row_hashes.get("task_record_sha256")),
            ("gold certification hash", certification_path, row_hashes.get("task_certification_sha256")),
            ("mutation catalog hash", evaluator / "mutation_catalog.json", row_hashes.get("mutation_catalog_sha256")),
            ("score deck hash", evaluator / "score_tb.scs", row_hashes.get("score_deck_sha256")),
        ):
            if not _check_hash(
                family=family, label=label, path=path, expected=expected, problems=problems
            ):
                gold_valid = False

        if record_path.is_file():
            record = read_json(record_path)
            evaluator_hashes = record.get("evaluator_hashes") or {}
            for relative, expected in sorted(evaluator_hashes.items()):
                # ``solution_tree`` is a historical opaque aggregate.  The
                # certificate's gold_bundle hash below binds the actual tree.
                if relative == "solution_tree":
                    continue
                path = evaluator / relative
                if not _check_hash(
                    family=family,
                    label=f"task record evaluator hash mismatch: {relative}",
                    path=path,
                    expected=expected,
                    problems=problems,
                ):
                    gold_valid = False
            public_hashes = record.get("public_hashes") or {}
            for relative, expected in sorted(public_hashes.items()):
                if not _check_hash(
                    family=family,
                    label=f"task record public hash mismatch: {relative}",
                    path=public / relative,
                    expected=expected,
                    problems=problems,
                ):
                    gold_valid = False
            readiness = record.get("readiness_evidence") or {}
            readiness_path = source_task / str(readiness.get("path") or "")
            if not _check_hash(
                family=family,
                label="task record readiness evidence hash",
                path=readiness_path,
                expected=readiness.get("sha256"),
                problems=problems,
            ):
                gold_valid = False

        if certification_path.is_file():
            certification = read_json(certification_path)
            evaluators = certification.get("evaluators") or {}
            if certification.get("status") != "gate2_pass":
                problems.append(f"{family}: source gold certification is not gate2_pass")
                gold_valid = False
            if certification.get("certification_policy") != "rust_evas2_only":
                problems.append(f"{family}: source gold does not use Rust EVAS2-only policy")
                gold_valid = False
            if (evaluators.get("evas2") or {}).get("status") != "pass":
                problems.append(f"{family}: source gold lacks Rust EVAS2 PASS")
                gold_valid = False
            if not _check_evidence_report(
                source=source,
                family=family,
                certification=certification,
                problems=problems,
            ):
                gold_valid = False
            try:
                certificate_inputs, component_inputs = _task_input_hashes(source_task)
            except FileNotFoundError as exc:
                problems.append(f"{family}: source gold certification input is missing: {exc.filename}")
                gold_valid = False
            else:
                for profile_name in ("feedback", "score"):
                    profile_path = evaluator / "profiles" / f"{profile_name}.json"
                    profile = read_json(profile_path)
                    if profile.get("harness_spec_sha256") != certificate_inputs["harness_spec"]:
                        problems.append(
                            f"{family}: source gold {profile_name} profile "
                            "harness_spec_sha256 mismatch"
                        )
                        gold_valid = False
                if not _check_mapping(
                    family=family,
                    label="gold certification input hash",
                    actual=certification.get("input_hashes") or {},
                    expected=certificate_inputs,
                    problems=problems,
                ):
                    gold_valid = False
                task_inputs = ((certification.get("component_fingerprints") or {}).get("task_inputs") or {})
                if not _check_mapping(
                    family=family,
                    label="gold certification component hash",
                    actual=task_inputs,
                    expected=component_inputs,
                    problems=problems,
                ):
                    gold_valid = False

        if gold_valid:
            reusable_gold += 1
        else:
            invalid_gold.append(family)
            stale_families.add(family)

        for mutation in row.get("active_mutations") or []:
            negative_total += 1
            mutation_id = str(mutation.get("mutation_id") or "")
            pair = f"{family}/{mutation_id}"
            cert_path = source_task / str(mutation.get("certification_path") or "")
            bundle = cert_path.parent
            negative_valid = _check_hash(
                family=family,
                label=f"negative {mutation_id} certification hash",
                path=cert_path,
                expected=mutation.get("certification_sha256"),
                problems=problems,
            )
            if bundle.is_dir():
                actual_bundle_sha = tree_sha_by_file_hash(bundle)
                if mutation.get("mutation_bundle_sha256") != actual_bundle_sha:
                    problems.append(f"{family}: source negative {mutation_id} bundle hash mismatch")
                    negative_valid = False
            else:
                problems.append(f"{family}: source negative {mutation_id} bundle is missing")
                negative_valid = False
            if cert_path.is_file():
                negative_certification = read_json(cert_path)
                negative_evaluators = negative_certification.get("evaluators") or {}
                if negative_certification.get("outcome") != "killed_behaviorally":
                    problems.append(f"{family}: source negative {mutation_id} was not killed behaviorally")
                    negative_valid = False
                if negative_certification.get("certification_policy") != "rust_evas2_only":
                    problems.append(
                        f"{family}: source negative {mutation_id} does not use Rust EVAS2-only policy"
                    )
                    negative_valid = False
                if negative_evaluators.get("evas2") != "compile_pass_behavior_fail":
                    problems.append(
                        f"{family}: source negative {mutation_id} lacks Rust EVAS2 behavioral kill"
                    )
                    negative_valid = False
                if not _check_evidence_report(
                    source=source,
                    family=f"{family}/{mutation_id}",
                    certification=negative_certification,
                    problems=problems,
                ):
                    negative_valid = False
                try:
                    negative_inputs = {
                        "checker_profile_sha256": file_sha(evaluator / "checker_profile.json"),
                        "harness_spec_sha256": file_sha(evaluator / "harness_spec.json"),
                    }
                    accepted_profile_hashes = {
                        file_sha(evaluator / "profiles" / "feedback.json"),
                        file_sha(evaluator / "profiles" / "score.json"),
                    }
                except FileNotFoundError as exc:
                    problems.append(
                        f"{family}: source negative {mutation_id} input is missing: {exc.filename}"
                    )
                    negative_valid = False
                else:
                    if not _check_mapping(
                        family=family,
                        label=f"negative {mutation_id} input hash",
                        actual=negative_certification.get("inputs") or {},
                        expected=negative_inputs,
                        problems=problems,
                    ):
                        negative_valid = False
                    declared_bundle = (negative_certification.get("inputs") or {}).get(
                        "mutation_bundle_sha256"
                    )
                    requires_bundle_binding = (
                        negative_certification.get("schema_version")
                        == "v4-negative-certification-rust-evas2-v2"
                    )
                    if requires_bundle_binding and not declared_bundle:
                        problems.append(
                            f"{family}: source negative {mutation_id} lacks mutation bundle binding"
                        )
                        negative_valid = False
                    elif declared_bundle and declared_bundle != tree_sha_by_file_hash(
                        bundle, excluded_names={"certification.json"}
                    ):
                        problems.append(
                            f"{family}: source negative {mutation_id} input hash mismatch: "
                            "mutation_bundle_sha256"
                        )
                        negative_valid = False
                    declared_profile = (negative_certification.get("inputs") or {}).get(
                        "profile_sha256"
                    )
                    if declared_profile not in accepted_profile_hashes:
                        problems.append(
                            f"{family}: source negative {mutation_id} input hash mismatch: "
                            "profile_sha256"
                        )
                        negative_valid = False
            if negative_valid:
                reusable_negatives += 1
            else:
                invalid_negatives.append(pair)
                stale_families.add(family)

    rerun_required = bool(invalid_gold or invalid_negatives)
    return {
        "policy": "source_transitive_input_hash_bound",
        "source_dut_gold_certification_total": len(source_rows),
        "source_dut_gold_certification_count": reusable_gold,
        "source_negative_certification_total": negative_total,
        "source_negative_certification_count": reusable_negatives,
        "evaluators": ["rust_evas2"],
        "simulation_rerun_required_for_materialization": rerun_required,
        "stale_certification_family_ids": sorted(stale_families),
        "stale_gold_family_ids": invalid_gold,
        "stale_negative_case_ids": invalid_negatives,
    }, problems

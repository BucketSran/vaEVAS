#!/usr/bin/env python3
"""Audit V4 family contract bindings and emit independent family shards."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[2]
V4_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = V4_ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
FAMILY_DIR_RE = re.compile(r"(?P<family>\d{3})-.+")
TRACE_SIGNAL_RE = re.compile(r"(?:time|[A-Za-z_][A-Za-z0-9_$]*(?:\[\d+\])?)\Z")
SCHEMA_VERSION = "v4-contract-semantic-audit-shard-v1"
AGGREGATE_SCHEMA_VERSION = "v4-contract-semantic-audit-aggregate-v1"


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha_by_file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha(item).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def family_directories(source: Path) -> list[Path]:
    directories = [
        item
        for item in source.iterdir()
        if item.is_dir() and FAMILY_DIR_RE.fullmatch(item.name)
    ]
    return sorted(directories, key=lambda item: int(item.name[:3]))


def select_families(
    source: Path, family_ids: Iterable[str], family_ranges: Iterable[str]
) -> list[Path]:
    selected = {f"{int(value):03d}" for value in family_ids}
    for value in family_ranges:
        try:
            start, end = (int(part) for part in value.split("-", 1))
        except ValueError as exc:
            raise ValueError(f"invalid family range: {value}") from exc
        if start > end:
            raise ValueError(f"invalid descending family range: {value}")
        selected.update(f"{number:03d}" for number in range(start, end + 1))
    directories = family_directories(source)
    if not selected:
        return directories
    found = {item.name[:3]: item for item in directories}
    missing = sorted(selected - found.keys())
    if missing:
        raise ValueError(f"families not found: {', '.join(missing)}")
    return [found[family_id] for family_id in sorted(selected, key=int)]


def normalized_signals(values: Iterable[Any]) -> set[str]:
    return {str(value).strip().lower() for value in values if str(value).strip()}


def invalid_trace_signal_names(values: Iterable[Any]) -> list[str]:
    """Return entries that cannot name a physical scalar or indexed trace.

    Required-trace metadata is a simulator interface, not a container for
    checker-derived values, scenario labels, thresholds, or diagnostics.
    Cross-file trace binding below proves that otherwise-valid identifiers are
    also public and saved; this lexical gate catches literals before case
    normalization can make an invalid contract look internally consistent.
    """
    invalid: set[str] = set()
    for value in values:
        signal = str(value).strip()
        if not signal or TRACE_SIGNAL_RE.fullmatch(signal) is None:
            invalid.add(signal or "<empty>")
    return sorted(invalid)


def identifier_visible(text: str, identifier: str) -> bool:
    """Find scalar identifiers and common prose representations of buses."""
    base = identifier.split("[", 1)[0]
    if re.search(rf"(?<![A-Za-z0-9_]){re.escape(base)}(?![A-Za-z0-9_])", text, re.I):
        return True
    if "[" in identifier and re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(base)}(?=[0-9\[])", text, re.I
    ):
        return True
    numbered = re.fullmatch(r"(.+?)(\d+)", base)
    return bool(
        numbered
        and re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(numbered.group(1))}(?=[0-9\[]|[^A-Za-z0-9_]|$)",
            text,
            re.I,
        )
    )


def normalized_semantics(harness: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    deck = harness.get("deck") or {}
    overrides = profile.get("deck_overrides") or {}

    def clean(values: Iterable[Any]) -> list[str]:
        return [str(value).strip() for value in values if str(value).strip()]

    return {
        "body_lines": clean(list(deck.get("body_lines") or []) + list(overrides.get("body_lines") or [])),
        "analyses": clean(overrides.get("analyses") or deck.get("analyses") or []),
        "save_signals": clean(overrides.get("save_signals") or deck.get("save_signals") or []),
        "parameters": profile.get("parameters") or {},
        "corners": list(profile.get("corners") or []),
        "deterministic_seed": int(profile.get("deterministic_seed") or 0),
        "property_ids": list(harness.get("property_ids") or []),
        "profile_property_ids": list(profile.get("property_ids") or []),
    }


class FamilyAudit:
    def __init__(self, family_id: str, slug: str) -> None:
        self.family_id = family_id
        self.slug = slug
        self.findings: list[dict[str, Any]] = []
        self.checks: list[str] = []

    def checked(self, check: str) -> None:
        if check not in self.checks:
            self.checks.append(check)

    def finding(
        self, severity: str, check: str, message: str, details: Any | None = None
    ) -> None:
        self.checked(check)
        finding: dict[str, Any] = {
            "severity": severity,
            "check": check,
            "message": message,
        }
        if details is not None:
            finding["details"] = details
        self.findings.append(finding)

    def shard(self, evidence: dict[str, Any]) -> dict[str, Any]:
        counts = Counter(item["severity"] for item in self.findings)
        status = "error" if counts["error"] else "review" if counts["review"] else "pass"
        return {
            "schema_version": SCHEMA_VERSION,
            "family_id": self.family_id,
            "family_slug": self.slug,
            "status": status,
            "finding_counts": {
                "error": counts["error"],
                "review": counts["review"],
            },
            "checks_completed": sorted(self.checks),
            "findings": self.findings,
            "evidence": evidence,
        }


def check_equal(
    audit: FamilyAudit,
    check: str,
    expected: Any,
    actual: Any,
    message: str,
) -> None:
    audit.checked(check)
    if actual != expected:
        audit.finding("error", check, message, {"expected": expected, "actual": actual})


def audit_family(task: Path) -> dict[str, Any]:
    family_id = task.name[:3]
    audit = FamilyAudit(family_id, task.name)
    evaluator = task / "evaluator"
    public = task / "public" / "task"
    required = {
        "family_spec": evaluator / "family_spec.json",
        "harness_spec": evaluator / "harness_spec.json",
        "checker_profile": evaluator / "checker_profile.json",
        "feedback_profile": evaluator / "profiles" / "feedback.json",
        "score_profile": evaluator / "profiles" / "score.json",
        "certification": evaluator / "certification.json",
        "task_record": evaluator / "task_record.json",
        "instruction": public / "instruction.md",
        "public_contract": public / "public_contract.json",
    }
    missing = sorted(name for name, path in required.items() if not path.is_file())
    audit.checked("required_files")
    if missing:
        audit.finding("error", "required_files", "required contract files are missing", missing)
        return audit.shard({"task_path": task.name})

    family_spec = read_json(required["family_spec"])
    harness = read_json(required["harness_spec"])
    checker_profile = read_json(required["checker_profile"])
    feedback = read_json(required["feedback_profile"])
    score = read_json(required["score_profile"])
    certification = read_json(required["certification"])
    task_record = read_json(required["task_record"])
    public_contract = read_json(required["public_contract"])
    instruction = required["instruction"].read_text(encoding="utf-8")

    expected_task_id = f"v4-{family_id}"
    identity_values = {
        "family_spec": family_spec.get("family_id"),
        "harness_spec": harness.get("family_id"),
        "certification": certification.get("family_id"),
        "public_contract": public_contract.get("canonical_dut_id"),
        "task_record": task_record.get("canonical_dut_id"),
    }
    audit.checked("identity_binding")
    bad_identity = {
        name: value
        for name, value in identity_values.items()
        if str(value).zfill(3) != family_id
    }
    if bad_identity:
        audit.finding("error", "identity_binding", "family identifiers disagree", bad_identity)
    check_equal(
        audit,
        "identity_binding",
        expected_task_id,
        (family_spec.get("task_ids") or {}).get("dut"),
        "family DUT task ID disagrees with directory identity",
    )
    check_equal(
        audit,
        "identity_binding",
        expected_task_id,
        harness.get("task_id"),
        "harness task ID disagrees with directory identity",
    )

    artifact_files = (family_spec.get("artifact_contract") or {}).get("files") or []
    artifact_paths = [str(item.get("path")) for item in artifact_files]
    check_equal(
        audit,
        "artifact_binding",
        artifact_paths,
        public_contract.get("target_artifacts"),
        "public target artifacts differ from family artifact contract",
    )
    check_equal(
        audit,
        "artifact_binding",
        artifact_paths,
        (harness.get("candidate") or {}).get("artifact_paths"),
        "harness candidate artifacts differ from family artifact contract",
    )
    check_equal(
        audit,
        "artifact_binding",
        artifact_paths,
        task_record.get("target_artifacts"),
        "task record artifacts differ from family artifact contract",
    )
    for artifact in artifact_paths:
        if artifact not in instruction:
            audit.finding(
                "error",
                "instruction_interface_traceability",
                "target artifact is absent from the public instruction",
                {"artifact": artifact},
            )
    for artifact in artifact_files:
        for module in artifact.get("modules") or []:
            if module.get("role") != "entry":
                continue
            missing_identifiers: list[dict[str, str]] = []
            if not identifier_visible(instruction, str(module.get("name"))):
                missing_identifiers.append({"kind": "module", "name": str(module.get("name"))})
            for kind in ("ports", "parameters"):
                for item in module.get(kind) or []:
                    if not identifier_visible(instruction, str(item.get("name"))):
                        missing_identifiers.append(
                            {"kind": kind[:-1], "name": str(item.get("name"))}
                        )
            if missing_identifiers:
                audit.finding(
                    "review",
                    "instruction_interface_traceability",
                    "declared public interface identifiers cannot be located in the instruction",
                    missing_identifiers,
                )
            else:
                audit.checked("instruction_interface_traceability")

    properties = family_spec.get("properties") or []
    property_ids = [str(item.get("id")) for item in properties]
    audit.checked("property_binding")
    if not property_ids or len(property_ids) != len(set(property_ids)):
        audit.finding(
            "error",
            "property_binding",
            "family properties must be nonempty and uniquely identified",
            property_ids,
        )
    for name, value in (
        ("harness", harness.get("property_ids")),
        ("feedback_profile", feedback.get("property_ids")),
        ("score_profile", score.get("property_ids")),
    ):
        if value != property_ids:
            audit.finding(
                "error",
                "property_binding",
                f"{name} property IDs differ from family properties",
                {"expected": property_ids, "actual": value},
            )
    if "property_ids" in checker_profile and checker_profile["property_ids"] != property_ids:
        audit.finding(
            "error",
            "property_binding",
            "checker profile property IDs differ from family properties",
            {"expected": property_ids, "actual": checker_profile["property_ids"]},
        )

    family_required_signal_values = list(
        (family_spec.get("trace_contract") or {}).get("required_signals") or []
    )
    property_required_signal_values = [
        value
        for prop in properties
        for value in (prop.get("required_signals") or [])
    ]
    public_observable_values = list(public_contract.get("public_observables") or [])
    checker_trace = checker_profile.get("trace_contract") or {}
    checker_observable_values = list(checker_trace.get("public_observables") or [])
    checker_extra_values = list(checker_trace.get("extra_trace_signals") or [])
    saved_values = list((harness.get("deck") or {}).get("save_signals") or [])
    trace_signal_sources = {
        "family_trace_contract": family_required_signal_values,
        "property_required_signals": property_required_signal_values,
        "public_observables": public_observable_values,
        "checker_public_observables": checker_observable_values,
        "checker_extra_trace_signals": checker_extra_values,
        "harness_save_signals": saved_values,
    }
    audit.checked("trace_signal_syntax")
    for source_name, values in trace_signal_sources.items():
        invalid_names = invalid_trace_signal_names(values)
        if invalid_names:
            audit.finding(
                "error",
                "trace_signal_syntax",
                "trace contracts may contain only physical scalar or indexed signal names",
                {"source": source_name, "invalid_signal_names": invalid_names},
            )

    required_signals = normalized_signals(family_required_signal_values)
    for prop in properties:
        required_signals.update(normalized_signals(prop.get("required_signals") or []))
    public_observables = normalized_signals(public_observable_values)
    checker_observables = normalized_signals(checker_observable_values)
    checker_extra = normalized_signals(checker_extra_values)
    saved = normalized_signals(saved_values)
    for values in (required_signals, public_observables, checker_observables, checker_extra, saved):
        values.discard("time")
    audit.checked("trace_binding")
    if required_signals != public_observables | checker_extra:
        audit.finding(
            "error",
            "trace_binding",
            "property trace requirements differ from public plus declared extra observables",
            {
                "missing_observables": sorted(required_signals - public_observables - checker_extra),
                "undeclared_requirements": sorted((public_observables | checker_extra) - required_signals),
            },
        )
    if public_observables != checker_observables:
        audit.finding(
            "error",
            "trace_binding",
            "checker public observables differ from the public contract",
            {
                "missing_in_checker": sorted(public_observables - checker_observables),
                "extra_in_checker": sorted(checker_observables - public_observables),
            },
        )
    if not required_signals <= saved:
        audit.finding(
            "error",
            "trace_binding",
            "harness does not save every required signal",
            {"missing_saved_signals": sorted(required_signals - saved)},
        )

    audit.checked("profile_semantic_parity")
    if normalized_semantics(harness, feedback) != normalized_semantics(harness, score):
        audit.finding(
            "error",
            "profile_semantic_parity",
            "feedback and score profiles do not resolve to identical semantics",
        )
    if score.get("deck_overrides"):
        audit.finding(
            "error",
            "profile_semantic_parity",
            "score profile contains private stimulus overrides",
        )

    checker_id = checker_profile.get("checker_task_id")
    check_equal(
        audit,
        "checker_binding",
        checker_id,
        task_record.get("checker_task_id"),
        "task record checker ID differs from checker profile",
    )
    audit.checked("checker_binding")
    try:
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        registry = importlib.import_module("runners.checkers.v4.registry")
        checker = registry.load_checker(str(checker_id))
    except (ImportError, AttributeError, TypeError) as exc:
        checker = None
        load_error = str(exc)
    else:
        load_error = None
    if checker is None:
        audit.finding(
            "error",
            "checker_binding",
            "declared checker is not loadable from the V4 registry",
            {"checker_task_id": checker_id, "load_error": load_error},
        )

    audit.checked("gold_certification_binding")
    solution = evaluator / "solution"
    solution_files = (
        sorted(item.relative_to(solution).as_posix() for item in solution.rglob("*") if item.is_file())
        if solution.is_dir()
        else []
    )
    missing_gold = sorted(set(artifact_paths) - set(solution_files))
    if missing_gold:
        audit.finding(
            "error",
            "gold_certification_binding",
            "gold solution omits target artifacts",
            {"missing_artifacts": missing_gold},
        )
    expected_cert_hashes = {
        "checker_profile": file_sha(required["checker_profile"]),
        "family_spec": file_sha(required["family_spec"]),
        "feedback_profile": file_sha(required["feedback_profile"]),
        "gold_bundle": tree_sha_by_file_hash(solution) if solution.is_dir() else None,
        "harness_spec": file_sha(required["harness_spec"]),
        "score_profile": file_sha(required["score_profile"]),
    }
    recorded_cert_hashes = certification.get("input_hashes") or {}
    stale_cert_hashes = {
        name: {"recorded": recorded_cert_hashes.get(name), "actual": actual}
        for name, actual in expected_cert_hashes.items()
        if recorded_cert_hashes.get(name) != actual
    }
    if stale_cert_hashes:
        audit.finding(
            "error",
            "gold_certification_binding",
            "gold certification is not bound to current contract inputs",
            stale_cert_hashes,
        )
    if (
        certification.get("status") != "gate2_pass"
        or (certification.get("checks") or {}).get("gold_behavior") != "pass"
    ):
        audit.finding(
            "error",
            "gold_certification_binding",
            "current bound gold certification is not passing",
            {
                "status": certification.get("status"),
                "gold_behavior": (certification.get("checks") or {}).get("gold_behavior"),
            },
        )

    audit.checked("task_record_binding")
    for root_name, root, hashes in (
        ("evaluator", evaluator, task_record.get("evaluator_hashes") or {}),
        ("public", public, task_record.get("public_hashes") or {}),
    ):
        for relative, recorded in hashes.items():
            if relative == "solution_tree":
                continue
            path = root / relative
            if not path.is_file():
                audit.finding(
                    "error",
                    "task_record_binding",
                    "task record references a missing file",
                    {"root": root_name, "path": relative},
                )
            elif file_sha(path) != recorded:
                audit.finding(
                    "error",
                    "task_record_binding",
                    "task record contains a stale file hash",
                    {"root": root_name, "path": relative},
                )
    readiness = task_record.get("readiness_evidence") or {}
    readiness_path = task / str(readiness.get("path") or "")
    if not readiness_path.is_file() or file_sha(readiness_path) != readiness.get("sha256"):
        audit.finding(
            "error",
            "task_record_binding",
            "readiness evidence is missing or stale",
            readiness,
        )

    audit.checked("negative_property_evidence")
    cited_properties: set[str] = set()
    negative_certifications = sorted(
        (evaluator / "mutation_bundles").glob("*/certification.json")
    )
    for path in negative_certifications:
        diagnostics = (read_json(path).get("diagnostics") or {})
        violated = diagnostics.get("violated_property_ids")
        if not isinstance(violated, list) or not violated:
            audit.finding(
                "error",
                "negative_property_evidence",
                "negative certification lacks nonempty violated_property_ids",
                {"path": str(path.relative_to(task))},
            )
            continue
        unknown = sorted(str(item) for item in violated if str(item) not in property_ids)
        if unknown:
            audit.finding(
                "error",
                "negative_property_evidence",
                "negative certification cites unknown properties",
                {"path": str(path.relative_to(task)), "unknown_property_ids": unknown},
            )
        cited_properties.update(str(item) for item in violated)
    uncited = sorted(set(property_ids) - cited_properties)
    if uncited:
        audit.finding(
            "review",
            "negative_property_evidence",
            "the active negative set does not independently exercise every public property",
            {"uncited_property_ids": uncited, "negative_count": len(negative_certifications)},
        )

    evidence = {
        "task_path": task.name,
        "checker_task_id": checker_id,
        "property_ids": property_ids,
        "target_artifacts": artifact_paths,
        "gold_bundle_sha256": expected_cert_hashes["gold_bundle"],
        "certification_sha256": file_sha(required["certification"]),
    }
    return audit.shard(evidence)


def aggregate_shards(shard_dir: Path) -> dict[str, Any]:
    shards = []
    for path in sorted(shard_dir.glob("*.json")):
        value = read_json(path)
        if value.get("schema_version") == SCHEMA_VERSION:
            shards.append(value)
    shards.sort(key=lambda item: int(item["family_id"]))
    status_counts = Counter(str(item.get("status")) for item in shards)
    finding_counts = Counter(
        str(finding.get("check"))
        for shard in shards
        for finding in shard.get("findings") or []
    )
    anomalies = [
        {
            "family_id": shard["family_id"],
            "family_slug": shard["family_slug"],
            "status": shard["status"],
            "findings": shard.get("findings") or [],
        }
        for shard in shards
        if shard.get("status") != "pass"
    ]
    return {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "family_count": len(shards),
        "status_counts": {
            "pass": status_counts["pass"],
            "review": status_counts["review"],
            "error": status_counts["error"],
        },
        "finding_counts_by_check": dict(sorted(finding_counts.items())),
        "anomalies": anomalies,
        "scope": {
            "proves": [
                "identifier, artifact, property, trace, profile, checker-registry, hash, and recorded gold-certification bindings",
                "that declared public interface identifiers are lexically traceable to the instruction",
                "that active negative diagnostics cite declared public properties",
            ],
            "does_not_prove": [
                "natural-language requirements are mathematically equivalent to checker implementation",
                "stimulus and mutations completely cover the public contract",
                "all valid implementations pass or all invalid implementations fail",
                "recorded evaluator acceptance implies independent simulator parity",
            ],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="audit source families into shards")
    audit_parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    audit_parser.add_argument("--shard-dir", type=Path, required=True)
    audit_parser.add_argument("--family", action="append", default=[])
    audit_parser.add_argument("--family-range", action="append", default=[])
    aggregate_parser = subparsers.add_parser("aggregate", help="aggregate existing shards")
    aggregate_parser.add_argument("--shard-dir", type=Path, required=True)
    aggregate_parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "audit":
        families = select_families(args.source, args.family, args.family_range)
        for task in families:
            shard = audit_family(task)
            write_json(args.shard_dir / f"{shard['family_id']}.json", shard)
        print(json.dumps({"family_count": len(families), "shard_dir": str(args.shard_dir)}))
        return 0
    aggregate = aggregate_shards(args.shard_dir)
    if args.output:
        write_json(args.output, aggregate)
    print(json.dumps(aggregate, indent=2, sort_keys=True))
    return 1 if aggregate["status_counts"]["error"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

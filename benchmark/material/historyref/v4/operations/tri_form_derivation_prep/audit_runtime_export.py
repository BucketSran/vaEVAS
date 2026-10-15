#!/usr/bin/env python3
"""Audit a tri-form runtime export for public/evaluator isolation."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ALLOWED_DUT_RUNTIME_SCHEMAS = {
    "r45": {"r45-direct-evas-runtime-v1", "r45-direct-evas-runtime-v2"},
    "r47": {"r47-direct-evas-runtime-v2"},
    "r48": {"r48-direct-evas-runtime-v2"},
    "r49": {"r49-direct-evas-runtime-v2"},
    "r50": {"r50-direct-evas-runtime-v2"},
    "r51": {"r51-direct-evas-runtime-v2", "r51-direct-evas-runtime-v3"},
    "r52": {"r52-direct-evas-runtime-v2", "r52-direct-evas-runtime-v3"},
    "r53": {"r53-direct-evas-runtime-v2", "r53-direct-evas-runtime-v3"},
}
ALLOWED_TESTBENCH_RUNTIME_SCHEMAS = {
    "r45": {
        "r45-direct-evas-testbench-suite-v1",
        "r45-direct-evas-testbench-suite-v2",
    },
    "r47": {"r47-direct-evas-testbench-suite-v2"},
    "r48": {"r48-direct-evas-testbench-suite-v2"},
    "r49": {"r49-direct-evas-testbench-suite-v2"},
    "r50": {"r50-direct-evas-testbench-suite-v2"},
    "r51": {
        "r51-direct-evas-testbench-suite-v2",
        "r51-direct-evas-testbench-suite-v3",
    },
    "r52": {"r52-direct-evas-testbench-reference-v1"},
    "r53": {"r53-direct-evas-testbench-reference-v1"},
}
REFERENCE_ONLY_TESTBENCH_REVISIONS = frozenset({"r52", "r53"})
AUTHORING_ONLY_PUBLIC_MARKERS = (
    "negative_variants/",
    "/evaluator/",
    "vabench feedback run",
    "vabench feedback capabilities",
)
REAL_SKILL_MATRIX = {
    "G0": [],
    "G1": ["veriloga"],
    "G2": [],
    "G3": ["veriloga"],
    "G4": ["vabench-feedback"],
    "G5": ["veriloga", "vabench-feedback"],
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tree_sha(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def file_map(path: Path) -> dict[str, bytes]:
    return {item.relative_to(path).as_posix(): item.read_bytes() for item in sorted(path.rglob("*")) if item.is_file()}


def file_index(path: Path) -> dict[str, dict[str, object]]:
    return {
        item.relative_to(path).as_posix(): {
            "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            "bytes": item.stat().st_size,
        }
        for item in sorted(path.rglob("*"))
        if item.is_file() and not item.is_symlink()
    }


def public_text_leaks_authoring_surface(text: str) -> bool:
    normalized = text.lower()
    return any(marker in normalized for marker in AUTHORING_ONLY_PUBLIC_MARKERS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    run = args.run.expanduser().resolve()
    problems: list[str] = []
    policy = read_json(run / "MODEL_ACCESS_POLICY.json")
    attempt = read_json(run / "evidence" / "attempt_record.json")
    mode = str(policy.get("mode") or "")
    mounts = policy.get("mounts") or []
    available_skills = policy.get("available_skills") or {}
    if not isinstance(available_skills, dict):
        problems.append("model access policy available_skills must be an object")
        available_skills = {}
    real_skill_delivery = (
        policy.get("schema_version") == "r50-real-skills-model-access-policy-v1"
    )
    expected_skill_ids = REAL_SKILL_MATRIX.get(mode, []) if real_skill_delivery else []
    if real_skill_delivery and set(available_skills) != set(expected_skill_ids):
        problems.append("available skills do not match the real-skill mode matrix")
    if not real_skill_delivery and available_skills:
        problems.append("legacy runtime unexpectedly declares real skills")
    if policy.get("evaluator_mounted") is not False or any("evaluator" in str(item) for item in mounts):
        problems.append("evaluator assets are model-mounted")
    if policy.get("network") is not False:
        problems.append("network is not disabled")
    if mode in {"G0", "G1"}:
        if mounts:
            problems.append("direct one-shot mode has filesystem mounts")
        if real_skill_delivery:
            expected_tools = ["list_skills", "read_skill"] if available_skills else []
            if policy.get("provider_tools") != expected_tools:
                problems.append("direct skill lookup tools do not match available skills")
        if not (run / "direct_prompt.txt").is_file():
            problems.append("direct one-shot prompt is missing")
        else:
            direct_prompt = (run / "direct_prompt.txt").read_text(encoding="utf-8", errors="ignore")
            for marker in (
                "VABENCH_PUBLIC_CONTRACT",
                "Feedback tools",
                "feedback CLI",
                "vabench feedback",
                "private Spectre",
                "public/submission",
                "agentic mode",
                "mounted public task inputs",
            ):
                if marker.lower() in direct_prompt.lower():
                    problems.append(f"direct one-shot prompt leaks {marker!r}")
            if real_skill_delivery and (
                "Use this skill" in direct_prompt or "---\nname:" in direct_prompt
            ):
                problems.append("direct prompt inlines skill body")
        if (run / "public" / "evas_manifest.json").exists():
            problems.append("direct one-shot mode exposes an EVAS manifest")
        if (run / "public" / "task" / "public_contract.json").exists():
            problems.append("direct one-shot mode exposes a public contract file")
    else:
        expected_mounts = [
            "public/task:ro",
            "public/submission:rw",
            "public/work:rw",
        ]
        if available_skills:
            expected_mounts.append("public/skills:ro")
        if mounts != expected_mounts:
            problems.append("agentic model mounts differ from the public contract")
        if real_skill_delivery:
            expected_tools = ["list_skills", "read_skill"] if available_skills else []
            if policy.get("provider_tools") != expected_tools:
                problems.append("agentic skill lookup tools do not match available skills")
        if policy.get("executables") != ["evas", "vabench-submit"]:
            problems.append("agentic mode does not expose the declared shell helpers")
        if not (run / "public" / "evas_manifest.json").is_file():
            problems.append("agentic mode lacks the direct EVAS manifest")
        if not (run / "public" / "task" / "evas_runtime.json").is_file():
            problems.append("agentic mode lacks the transparent EVAS runtime contract")
        if not (run / "agent_prompt.txt").is_file():
            problems.append("agentic mode lacks the composed initial prompt")
        else:
            agent_prompt = (run / "agent_prompt.txt").read_text(encoding="utf-8", errors="ignore")
            if "VABENCH_PUBLIC_CONTRACT" in agent_prompt:
                problems.append("agentic prompt redundantly inlines public_contract.json")
            if real_skill_delivery and (
                "Use this skill" in agent_prompt or "---\nname:" in agent_prompt
            ):
                problems.append("agentic prompt inlines skill body")
        if (run / "public" / "task" / "public_contract.json").exists():
            problems.append("agentic mode exposes public_contract.json in the model task mount")
    public_root = (run / "public").resolve()
    for skill_id, skill in available_skills.items():
        raw_path = str(skill.get("path") or "")
        expected_path = f"public/skills/{skill_id}"
        if raw_path != expected_path:
            problems.append(f"available skill has noncanonical path: {skill_id}")
            continue
        if skill.get("skill_file") != f"{expected_path}/SKILL.md":
            problems.append(f"available skill has noncanonical SKILL.md path: {skill_id}")
        unresolved_root = run / raw_path
        cursor = run
        for part in Path(raw_path).parts:
            cursor /= part
            if cursor.is_symlink():
                problems.append(f"available skill path contains a symlink: {skill_id}")
                break
        skill_root = unresolved_root.resolve()
        try:
            skill_root.relative_to(public_root)
        except ValueError:
            problems.append(f"available skill escapes the public bundle: {skill_id}")
            continue
        if not (skill_root / "SKILL.md").is_file():
            problems.append(f"available skill is not mounted: {skill_id}")
        elif skill.get("tree_sha256") != tree_sha(skill_root):
            problems.append(f"available skill hash mismatch: {skill_id}")
    runtime_skill_manifest = run / "public" / "skills" / "SNAPSHOT_MANIFEST.json"
    if expected_skill_ids:
        if not runtime_skill_manifest.is_file() or runtime_skill_manifest.is_symlink():
            problems.append("runtime skill manifest is missing or symlinked")
        else:
            runtime_skill_data = read_json(runtime_skill_manifest)
            if runtime_skill_data.get("schema_version") != "v4-runtime-skill-manifest-v1":
                problems.append("runtime skill manifest schema mismatch")
            runtime_skills = runtime_skill_data.get("skills") or {}
            if not isinstance(runtime_skills, dict):
                problems.append("runtime skill manifest skills must be an object")
                runtime_skills = {}
            if set(runtime_skills) != set(expected_skill_ids):
                problems.append("runtime skill manifest does not match the mode matrix")
            for skill_id in expected_skill_ids:
                record = runtime_skills.get(skill_id) or {}
                if not isinstance(record, dict):
                    problems.append(f"runtime skill record is invalid: {skill_id}")
                    record = {}
                skill_root = run / "public" / "skills" / skill_id
                declared_files: dict[str, dict[str, object]] = {}
                for item in record.get("files") or []:
                    if not isinstance(item, dict):
                        problems.append(f"runtime skill file record is invalid: {skill_id}")
                        continue
                    relative = str(item.get("path") or "")
                    if relative in declared_files:
                        problems.append(f"runtime skill file index has a duplicate: {skill_id}")
                    declared_files[relative] = {
                        "sha256": item.get("sha256"),
                        "bytes": item.get("bytes"),
                    }
                if declared_files != file_index(skill_root):
                    problems.append(f"runtime skill file index mismatch: {skill_id}")
                if record.get("tree_sha256") != (available_skills.get(skill_id) or {}).get(
                    "tree_sha256"
                ):
                    problems.append(f"runtime skill policy hash mismatch: {skill_id}")
    elif (run / "public" / "skills").exists():
        problems.append("skill-free mode exposes a public skills directory")
    submission = run / "public" / "submission"
    if attempt.get("initial_submission_sha256") != tree_sha(submission):
        problems.append("initial submission hash does not match the prepared workspace")
    if attempt.get("form") == "bugfix" and mode not in {"G0", "G1"}:
        buggy = run / "public" / "task" / "buggy_bundle"
        if file_map(buggy) != file_map(submission):
            problems.append("bugfix writable submission is not an exact editable copy of the supplied buggy bundle")
        if attempt.get("submission_seeded_from_buggy_bundle") is not True:
            problems.append("bugfix attempt does not record its seeded editable workspace")
    if attempt.get("state") != "prepared" or attempt.get("private_score_decisions") != 0:
        problems.append("attempt lifecycle was not initialized safely")
    evaluator = run / "evaluator"
    if not evaluator.is_dir():
        problems.append("private evaluator bundle is missing")
    else:
        for name in ("task_record.json", "family_spec.json", "checker_profile.json", "harness_spec.json", "score_policy.json"):
            if not (evaluator / name).is_file():
                problems.append(f"private evaluator bundle missing {name}")
        if not (evaluator / "profiles").is_dir():
            problems.append("private evaluator bundle missing profiles/")
        form = str(attempt.get("form") or "")
        task_record_path = evaluator / "task_record.json"
        task_record = read_json(task_record_path) if task_record_path.is_file() else {}
        release_revision = str(task_record.get("release_revision") or "")
        if release_revision not in ALLOWED_DUT_RUNTIME_SCHEMAS:
            problems.append("private task record has an unsupported release revision")
        if form in {"dut", "bugfix"}:
            if mode not in {"G0", "G1"} and not (
                run / "public" / "task" / "visible_test.scs"
            ).is_file():
                problems.append("agentic DUT/bugfix mode lacks task-local visible_test.scs")
            if not (evaluator / "solution").is_dir():
                problems.append("private evaluator bundle missing solution/")
            if not (evaluator / "canonical_test_profile.json").is_file():
                problems.append("private evaluator bundle missing canonical_test_profile.json")
            if not (evaluator / "trusted_replay_test.scs").is_file():
                problems.append("private evaluator bundle missing trusted replay deck")
            runtime_contract = run / "public" / "task" / "evas_runtime.json"
            if mode not in {"G0", "G1"} and runtime_contract.is_file():
                runtime_data = read_json(runtime_contract)
                command = str(runtime_data.get("command") or "")
                schema_version = runtime_data.get("schema_version")
                if schema_version not in ALLOWED_DUT_RUNTIME_SCHEMAS.get(release_revision, set()):
                    problems.append("public EVAS runtime schema does not match the release")
                if schema_version in {
                    f"{release_revision}-direct-evas-runtime-v2",
                    f"{release_revision}-direct-evas-runtime-v3",
                }:
                    if "/tmp/vabench-visible/evas-output" not in command or "public/submission/evas-output" in command:
                        problems.append("public EVAS output is not isolated from submission")
                if schema_version == f"{release_revision}-direct-evas-runtime-v3":
                    if runtime_data.get("compatibility_mode") != "portable":
                        problems.append("portable public EVAS runtime mode is missing")
                    if "--spectre-strict" in command:
                        problems.append("portable public EVAS runtime still requests strict mode")
        if form == "testbench":
            for required in ("trusted_solution", "mutation_bundles"):
                if not (evaluator / required).is_dir():
                    problems.append(f"private testbench evaluator bundle missing {required}/")
            for required in (
                "mutation_catalog.json", "reference_tb.scs", "testbench_security_policy.json",
                "trusted_replay_suite.json",
            ):
                if not (evaluator / required).is_file():
                    problems.append(f"private testbench evaluator bundle missing {required}")
            if not (evaluator / "trusted_replay_fixtures").is_dir():
                problems.append("private testbench evaluator bundle missing trusted_replay_fixtures/")
        visible = run / "public" / "task" / "visible_test.scs"
        trusted = evaluator / "trusted_replay_test.scs"
        if mode not in {"G0", "G1"} and visible.is_file() and trusted.is_file():
            if visible.read_bytes() != trusted.read_bytes():
                problems.append("visible test and trusted replay deck differ")
        if (
            form == "testbench"
            and release_revision in REFERENCE_ONLY_TESTBENCH_REVISIONS
        ):
            public_task = run / "public" / "task"
            public_runtime = public_task / "evas_runtime.json"
            trusted_suite = evaluator / "trusted_replay_suite.json"
            trusted_fixtures = evaluator / "trusted_replay_fixtures"
            if not public_runtime.is_file():
                problems.append("reference-only public Testbench runtime is missing")
            else:
                runtime_data = read_json(public_runtime)
                if (
                    runtime_data.get("schema_version")
                    != f"{release_revision}-direct-evas-testbench-reference-v1"
                ):
                    problems.append("reference-only public Testbench schema mismatch")
                if runtime_data.get("feedback_scope") != "reference_dut_only":
                    problems.append("public Testbench feedback is not reference-only")
                if re.search(
                    r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                    json.dumps(runtime_data, sort_keys=True),
                ):
                    problems.append("public Testbench runtime leaks private mutation identity")
            if (public_task / "visible_fixtures").exists():
                problems.append("public Testbench runtime exposes private fixtures")
            public_reference = public_task / "supplied_dut"
            trusted_reference = trusted_fixtures / "reference" / "dut"
            if (
                not public_reference.is_dir()
                or not trusted_reference.is_dir()
                or tree_sha(public_reference) != tree_sha(trusted_reference)
            ):
                problems.append("public and trusted reference DUT trees differ")
            if not trusted_suite.is_file() or not trusted_fixtures.is_dir():
                problems.append("private Testbench trusted replay suite is incomplete")
            public_leaks = [
                path.relative_to(public_task).as_posix()
                for path in public_task.rglob("*")
                if re.search(
                    r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                    path.name,
                    flags=re.IGNORECASE,
                )
                or (
                    path.is_file()
                    and re.search(
                        r"(?<![A-Za-z])mutation_0[1-5]\b|\bneg_[A-Za-z0-9_]+\b",
                        path.read_text(encoding="utf-8", errors="ignore"),
                        flags=re.IGNORECASE,
                    )
                )
            ]
            if public_leaks:
                problems.append("public Testbench task bundle leaks private mutation surface")
        if (
            form == "testbench"
            and mode not in {"G0", "G1"}
            and release_revision not in REFERENCE_ONLY_TESTBENCH_REVISIONS
        ):
            fixtures = run / "public" / "task" / "visible_fixtures"
            fixture_names = sorted(
                path.name for path in fixtures.iterdir() if path.is_dir()
            ) if fixtures.is_dir() else []
            if fixture_names != [
                "mutation_01", "mutation_02", "mutation_03", "mutation_04", "mutation_05", "reference",
            ]:
                problems.append("public testbench runtime does not expose one reference and five mutation fixtures")
            public_suite = run / "public" / "task" / "evas_runtime.json"
            trusted_suite = evaluator / "trusted_replay_suite.json"
            trusted_fixtures = evaluator / "trusted_replay_fixtures"
            if public_suite.is_file() and trusted_suite.is_file() and public_suite.read_bytes() != trusted_suite.read_bytes():
                problems.append("public and trusted testbench suite manifests differ")
            if public_suite.is_file():
                suite_data = read_json(public_suite)
                command = str(suite_data.get("candidate_command_template") or "")
                schema_version = suite_data.get("schema_version")
                if schema_version not in ALLOWED_TESTBENCH_RUNTIME_SCHEMAS.get(release_revision, set()):
                    problems.append("public testbench suite schema does not match the release")
                if schema_version in {
                    f"{release_revision}-direct-evas-testbench-suite-v2",
                    f"{release_revision}-direct-evas-testbench-suite-v3",
                }:
                    if "/tmp/vabench-visible/runs/{case}" not in command:
                        problems.append("public testbench runs are not scratch-isolated")
                    if "public/submission/runs" in command or "public/submission/evas-output" in command:
                        problems.append("public testbench scratch pollutes submission")
                if schema_version == f"{release_revision}-direct-evas-testbench-suite-v3":
                    if suite_data.get("compatibility_mode") != "portable":
                        problems.append("portable public EVAS testbench mode is missing")
                    if "--spectre-strict" in command:
                        problems.append("portable public EVAS testbench still requests strict mode")
            if fixtures.is_dir() and trusted_fixtures.is_dir() and tree_sha(fixtures) != tree_sha(trusted_fixtures):
                problems.append("public and trusted testbench fixture trees differ")
            if (run / "public" / "task" / "visible_test.scs").exists():
                problems.append("testbench runtime exposes a gold-derived visible_test.scs")
        if attempt.get("evaluator_bundle_sha256") != tree_sha(evaluator):
            problems.append("evaluator bundle hash does not match the prepared workspace")
    for path in (run / "public").rglob("*"):
        if path.is_symlink():
            problems.append(f"public bundle contains symlink: {path}")
        if path.is_file():
            text = path.read_text(encoding="utf-8", errors="ignore")
            if public_text_leaks_authoring_surface(text):
                problems.append(f"public file leaks authoring evaluator path: {path}")
    report = {"schema_version": "v4-runtime-export-audit-v1", "status": "pass" if not problems else "fail", "problems": problems}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

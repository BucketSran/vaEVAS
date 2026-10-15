#!/usr/bin/env python3
"""Consume one benchmarkv4 task record and export an isolated runtime package."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RELEASE = PACKAGE_ROOT / "release" / "benchmarkv4-r53"
AGENTIC = {"G2", "G3", "G4", "G5"}
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
WRAPPERS_BY_PROCESS = {
    "direct_one_shot": "direct_wrapper.md",
    "agentic": "agentic_wrapper.md",
}
def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            digest.update(item.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(item.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def validate_evaluation_binding(record: dict[str, Any], task_dir: Path) -> None:
    binding = record.get("evaluation_binding") or {}
    if not binding:
        raise SystemExit(
            "legacy r44 task records are unsupported by the direct-EVAS exporter; "
            "materialize an r45 release first"
        )
    form = str(record.get("form") or "")
    release_revision = str(record.get("release_revision") or "")
    if form in {"dut", "bugfix"}:
        if binding.get("kind") != "canonical_test_deck":
            raise SystemExit("task lacks canonical test deck binding")
        profile = task_dir / str(binding.get("profile") or "")
        visible = task_dir / str(binding.get("public_test") or "")
        trusted = task_dir / str(binding.get("trusted_replay_test") or "")
        if not all(path.is_file() for path in (profile, visible, trusted)):
            raise SystemExit("canonical test binding references missing files")
        profile_payload = read_json(profile)
        deck_sha = file_sha(visible)
        if binding.get("profile_sha256") != file_sha(profile):
            raise SystemExit("canonical test profile hash mismatch")
        if (
            profile_payload.get("schema_version") != "r45-canonical-test-profile-v1"
            or profile_payload.get("profile_name") != "canonical_test"
        ):
            raise SystemExit("canonical test profile identity mismatch")
        if binding.get("canonical_semantics_sha256") != profile_payload.get(
            "canonical_semantics_sha256"
        ):
            raise SystemExit("canonical test semantic hash mismatch")
        if binding.get("test_deck_sha256") != deck_sha:
            raise SystemExit("canonical test deck hash mismatch")
        if profile_payload.get("test_deck_sha256") != deck_sha:
            raise SystemExit("canonical profile does not bind the deployed deck")
        if profile_payload.get("reuse_policy") != binding.get("reuse_policy"):
            raise SystemExit("canonical test reuse policy mismatch")
        if visible.read_bytes() != trusted.read_bytes():
            raise SystemExit("public and trusted canonical test decks differ")
        return

    if (
        form == "testbench"
        and binding.get("kind") == "reference_only_public_testbench"
    ):
        if binding.get("reuse_policy") != "public_reference_matches_trusted_reference":
            raise SystemExit("reference-only testbench reuse policy mismatch")
        public_runtime = task_dir / str(binding.get("public_runtime") or "")
        public_reference = task_dir / str(
            binding.get("public_reference_dut_tree") or ""
        )
        trusted_suite = task_dir / str(binding.get("trusted_replay_suite") or "")
        trusted_fixtures = task_dir / str(
            binding.get("trusted_replay_fixture_tree") or ""
        )
        trusted_reference = trusted_fixtures / "reference" / "dut"
        if not public_runtime.is_file() or not trusted_suite.is_file():
            raise SystemExit("reference-only testbench binding references missing manifests")
        if (
            not public_reference.is_dir()
            or not trusted_fixtures.is_dir()
            or not trusted_reference.is_dir()
        ):
            raise SystemExit("reference-only testbench binding references missing fixtures")
        runtime_payload = read_json(public_runtime)
        trusted_payload = read_json(trusted_suite)
        if (
            runtime_payload.get("schema_version")
            != f"{release_revision}-direct-evas-testbench-reference-v1"
        ):
            raise SystemExit("reference-only public runtime schema mismatch")
        if runtime_payload.get("feedback_scope") != "reference_dut_only":
            raise SystemExit("reference-only public feedback scope mismatch")
        if (
            runtime_payload.get("candidate") != "submission/testbench.scs"
            or runtime_payload.get("reference_dut_root") != "task/supplied_dut"
            or runtime_payload.get("working_directory") != "public_root"
        ):
            raise SystemExit("reference-only public runtime is not transport-neutral")
        if "mutation_" in json.dumps(runtime_payload, sort_keys=True):
            raise SystemExit("reference-only public runtime leaks a private mutation")
        if (
            trusted_payload.get("schema_version")
            != f"{release_revision}-trusted-evas-testbench-suite-v1"
        ):
            raise SystemExit("trusted replay suite schema mismatch")
        if binding.get("public_runtime_sha256") != file_sha(public_runtime):
            raise SystemExit("reference-only public runtime hash mismatch")
        if binding.get("trusted_replay_suite_sha256") != file_sha(trusted_suite):
            raise SystemExit("trusted replay suite hash mismatch")
        if (
            binding.get("trusted_replay_fixture_tree_sha256")
            != tree_sha(trusted_fixtures)
        ):
            raise SystemExit("trusted replay fixture tree hash mismatch")
        public_reference_sha = tree_sha(public_reference)
        trusted_reference_sha = tree_sha(trusted_reference)
        if (
            binding.get("public_reference_dut_tree_sha256")
            != public_reference_sha
            or binding.get("trusted_reference_dut_tree_sha256")
            != trusted_reference_sha
            or public_reference_sha != trusted_reference_sha
        ):
            raise SystemExit("public and trusted reference DUT trees differ")
        return

    if form != "testbench" or binding.get("kind") != "public_testbench_suite":
        raise SystemExit("task lacks public testbench suite binding")
    if binding.get("reuse_policy") != "public_and_trusted_replay_suite_same_bytes":
        raise SystemExit("testbench suite reuse policy mismatch")
    public_suite = task_dir / str(binding.get("public_suite") or "")
    trusted_suite = task_dir / str(binding.get("trusted_replay_suite") or "")
    public_fixtures = task_dir / str(binding.get("public_fixture_tree") or "")
    trusted_fixtures = task_dir / str(binding.get("trusted_replay_fixture_tree") or "")
    if not public_suite.is_file() or not trusted_suite.is_file():
        raise SystemExit("testbench suite binding references missing manifests")
    if not public_fixtures.is_dir() or not trusted_fixtures.is_dir():
        raise SystemExit("testbench suite binding references missing fixtures")
    suite_sha = file_sha(public_suite)
    fixture_sha = tree_sha(public_fixtures)
    if binding.get("public_suite_sha256") != suite_sha:
        raise SystemExit("public testbench suite hash mismatch")
    if binding.get("public_fixture_tree_sha256") != fixture_sha:
        raise SystemExit("public testbench fixture tree hash mismatch")
    if read_json(public_suite).get("fixture_tree_sha256") != fixture_sha:
        raise SystemExit("testbench suite manifest does not bind its fixture tree")
    if public_suite.read_bytes() != trusted_suite.read_bytes():
        raise SystemExit("public and trusted testbench suite manifests differ")
    if tree_sha(trusted_fixtures) != fixture_sha:
        raise SystemExit("public and trusted testbench fixture trees differ")


def copy_tree(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)


def public_support_files(task_dir: Path) -> list[tuple[Path, Path]]:
    """Resolve evaluator-supplied helpers that the contract marks public/read-only."""
    family_spec_path = task_dir / "evaluator" / "family_spec.json"
    if not family_spec_path.is_file():
        return []
    family_spec = read_json(family_spec_path)
    contract = family_spec.get("support_contract") or {}
    records = list(contract.get("files") or [])
    if not records:
        return []
    if (
        contract.get("visibility") != "public_readonly"
        or contract.get("source_root") != "public_support"
        or contract.get("mount_root") != "support"
    ):
        raise SystemExit("invalid public support contract")
    source_root = task_dir / "evaluator" / "solution" / "support"
    resolved = []
    for record in records:
        relative = Path(str(record.get("path") or ""))
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"unsafe public support path: {relative}")
        source = source_root / relative
        if not source.is_file() or source.is_symlink():
            raise SystemExit(f"missing declared public support artifact: {relative}")
        if file_sha(source) != record.get("sha256"):
            raise SystemExit(f"public support hash mismatch: {relative}")
        resolved.append((relative, source))
    return resolved


def task_record(release: Path, task_id: str) -> tuple[dict[str, Any], Path]:
    index = read_json(release / "TASK_INDEX.json")
    matches = [row for row in index.get("tasks") or [] if row.get("task_id") == task_id]
    if len(matches) != 1:
        raise SystemExit(f"expected one task record for {task_id}, found {len(matches)}")
    task_dir = release / str(matches[0]["task_dir"])
    record = read_json(task_dir / "task_record.json")
    contract_sha = file_sha(task_dir / "public_contract.json")
    if matches[0].get("public_contract_sha256") != contract_sha:
        raise SystemExit(f"task index public contract hash mismatch: {task_id}")
    if record.get("public_contract_sha256") != contract_sha:
        raise SystemExit(f"task record public contract hash mismatch: {task_id}")
    if record.get("public_bundle_sha256") != tree_sha(task_dir / "public"):
        raise SystemExit(f"task record public bundle hash mismatch: {task_id}")
    validate_evaluation_binding(record, task_dir)
    return record, task_dir


def serialize_public_artifacts(task_dir: Path, form: str) -> str:
    lines: list[str] = []
    public = task_dir / "public"
    roots = []
    if form == "testbench":
        roots.append(public / "supplied_dut")
    elif form == "bugfix":
        roots.append(public / "buggy_bundle")
    for root in roots:
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(public).as_posix()
            lines.extend([
                f'<<<VABENCH_INPUT_ARTIFACT path="{relative}">>>',
                path.read_text(encoding="utf-8"),
                "<<<END_VABENCH_INPUT_ARTIFACT>>>",
            ])
    if form == "testbench" and (public / "evas_runtime.json").is_file():
        runtime = read_json(public / "evas_runtime.json")
        if str(runtime.get("schema_version") or "").endswith(
            "-direct-evas-testbench-reference-v1"
        ):
            lines.extend([
                '<<<VABENCH_INPUT_ARTIFACT path="evas_runtime.json">>>',
                (public / "evas_runtime.json").read_text(encoding="utf-8"),
                "<<<END_VABENCH_INPUT_ARTIFACT>>>",
            ])
    for relative, path in public_support_files(task_dir):
        lines.extend([
            f'<<<VABENCH_INPUT_ARTIFACT path="public_support/{relative.as_posix()}">>>',
            path.read_text(encoding="utf-8"),
            "<<<END_VABENCH_INPUT_ARTIFACT>>>",
        ])
    return "\n".join(lines)


def ordered_prompt_components(mode_record: dict[str, Any]) -> list[str]:
    components: list[str] = []
    wrappers: list[str] = []
    prompt_components = set((mode_record.get("prompt_component_hashes") or {}).keys())
    for component in [str(item) for item in mode_record.get("component_order") or []]:
        if component == "instruction" or component.startswith("public_input:"):
            continue
        if component.endswith("_wrapper.md"):
            wrappers.append(component)
            components.append(component)
        elif component in prompt_components:
            components.append(component)
        else:
            raise SystemExit(f"unexpected prompt component in record: {component}")
    if len(wrappers) != 1:
        raise SystemExit(f"expected exactly one mode wrapper in prompt record, found {wrappers}")
    if components[-1] != wrappers[0]:
        raise SystemExit(f"mode wrapper must be the final prompt component: {components}")
    return components


def prompt_component_path(release: Path, component_id: str) -> Path:
    if component_id.endswith("_wrapper.md"):
        subdir = "wrappers"
    elif component_id in set(FORM_SKILLS.values()):
        subdir = "form_skills"
    elif component_id == EVAS_CORE or component_id in set(EVAS_GUIDES.values()):
        subdir = "evas_guides"
    else:
        raise SystemExit(f"unknown prompt component: {component_id}")
    return release / "prompt_modes" / subdir / component_id


def load_skill_manifest(release: Path) -> dict[str, Any]:
    manifest = read_json(release / "skills" / "SNAPSHOT_MANIFEST.json")
    if manifest.get("schema_version") != "v4-real-skill-snapshot-manifest-v1":
        raise SystemExit("release has no real skill snapshot manifest")
    return manifest


def release_skill_root(release: Path, skill_id: str, raw_path: object) -> Path:
    expected = f"skills/{skill_id}"
    if str(raw_path or "") != expected:
        raise SystemExit(f"skill package path is not canonical: {skill_id}")
    unresolved = release
    for part in Path(expected).parts:
        unresolved /= part
        if unresolved.is_symlink():
            raise SystemExit(f"skill package path contains a symlink: {skill_id}")
    source = unresolved.resolve()
    try:
        source.relative_to(release.resolve())
    except ValueError as exc:
        raise SystemExit(f"skill package escapes the release: {skill_id}") from exc
    return source


def available_skill_records(release: Path, mode: str) -> dict[str, dict[str, Any]]:
    modes = read_json(release / "prompt_modes" / "modes.json").get("modes") or {}
    policy = modes.get(mode) or {}
    if "skills" not in policy:
        return {}
    policy_skill_ids = [str(item) for item in policy.get("skills") or []]
    if not policy_skill_ids:
        return {}
    manifest = load_skill_manifest(release)
    matrix = manifest.get("mode_skill_matrix") or {}
    skill_ids = [str(item) for item in matrix.get(mode) or []]
    if skill_ids != policy_skill_ids:
        raise SystemExit(f"skill mode matrix disagrees with prompt policy: {mode}")
    skills = manifest.get("skills") or {}
    records: dict[str, dict[str, Any]] = {}
    for skill_id in skill_ids:
        record = skills.get(skill_id)
        if not isinstance(record, dict):
            raise SystemExit(f"mode references unknown skill: {skill_id}")
        source = release_skill_root(release, skill_id, record.get("path"))
        if not (source / "SKILL.md").is_file():
            raise SystemExit(f"skill package is missing SKILL.md: {skill_id}")
        if source.is_symlink() or any(item.is_symlink() for item in source.rglob("*")):
            raise SystemExit(f"skill package contains a symlink: {skill_id}")
        if record.get("tree_sha256") != tree_sha(source):
            raise SystemExit(f"skill package hash mismatch: {skill_id}")
        records[skill_id] = record
    return records


def build_mode_record(release: Path, task_dir: Path, record: dict[str, Any], mode: str) -> dict[str, Any]:
    modes = read_json(release / "prompt_modes" / "modes.json").get("modes") or {}
    policy = modes.get(mode)
    if not isinstance(policy, dict):
        raise SystemExit(f"unknown prompt mode: {mode}")
    manifest = read_json(release / "prompt_modes" / "manifest.json")
    component_records = manifest.get("components") or {
        **(manifest.get("wrappers") or {}),
        **(manifest.get("form_skills") or {}),
        **(manifest.get("evas_guides") or {}),
    }
    public_input_paths = [task_dir / "public" / "instruction.md"]
    public_inputs = ["instruction"]
    form = str(record["form"])
    if form == "testbench":
        public_input_paths.extend(sorted((task_dir / "public" / "supplied_dut").rglob("*.va")))
    elif form == "bugfix":
        public_input_paths.extend(sorted((task_dir / "public" / "buggy_bundle").rglob("*.va")))
    support_paths = [path for _, path in public_support_files(task_dir)]
    public_input_paths.extend(support_paths)
    reference_only_public_testbench = (
        form == "testbench"
        and (record.get("evaluation_binding") or {}).get("kind")
        == "reference_only_public_testbench"
    )
    if mode in AGENTIC or reference_only_public_testbench:
        public_input_paths.extend(
            path for path in sorted((task_dir / "public").rglob("*"))
            if path.is_file() and path not in public_input_paths
        )
    for path in public_input_paths[1:]:
        if path.is_relative_to(task_dir / "public"):
            relative = path.relative_to(task_dir / "public").as_posix()
        else:
            relative = f"public_support/{path.relative_to(task_dir / 'evaluator' / 'solution' / 'support').as_posix()}"
        public_inputs.append(f"public_input:{relative}")
    guide_components: list[str] = []
    if policy.get("form_skill"):
        guide_components.append(FORM_SKILLS[form])
    if policy.get("evas_guide"):
        guide_components.extend([EVAS_CORE, EVAS_GUIDES[form]])
    skill_records = available_skill_records(release, mode)
    real_skill_delivery = "skills" in policy
    wrapper = WRAPPERS_BY_PROCESS[str(policy.get("process") or "")]
    prompt_components = [*guide_components, wrapper]
    missing = [name for name in prompt_components if name not in component_records]
    if missing:
        raise SystemExit(f"prompt component(s) missing from manifest: {missing}")
    for name in prompt_components:
        if component_records[name].get("sha256") != file_sha(prompt_component_path(release, name)):
            raise SystemExit(f"prompt component hash mismatch: {name}")
    public_contract_sha = file_sha(task_dir / "public_contract.json")
    if record.get("public_contract_sha256") != public_contract_sha:
        raise SystemExit(f"task record public contract hash mismatch: {record['task_id']}")
    return {
        "schema_version": "v4-derived-prompt-plan-v1",
        "task_id": record["task_id"],
        "family_id": record["family_id"],
        "form": form,
        "mode": mode,
        "process": policy["process"],
        "evas_cli_available": bool(policy.get("evas_cli")),
        "canonical_instruction_sha256": file_sha(public_input_paths[0]),
        "public_contract_sha256": public_contract_sha,
        "public_input_hashes": {
            (
                path.relative_to(task_dir).as_posix()
                if path.is_relative_to(task_dir)
                else path.as_posix()
            ): file_sha(path)
            for path in public_input_paths
        },
        "component_order": [*public_inputs, *guide_components, wrapper],
        **(
            {
                "skill_delivery": "real_skill_lookup_v1",
                "available_skills": {
                    skill_id: {
                        "path": f"public/skills/{skill_id}",
                        "skill_file": f"public/skills/{skill_id}/SKILL.md",
                        "tree_sha256": skill_record["tree_sha256"],
                        "release_skill_path": skill_record["path"],
                    }
                    for skill_id, skill_record in skill_records.items()
                },
                "skill_hashes": {
                    skill_id: skill_record["tree_sha256"]
                    for skill_id, skill_record in skill_records.items()
                },
            }
            if real_skill_delivery
            else {
                "skill_hashes": {
                    name: component_records[name]["sha256"]
                    for name in guide_components
                },
            }
        ),
        "prompt_component_hashes": {
            name: component_records[name]["sha256"]
            for name in prompt_components
        },
        "response_protocol": "v4-exact-artifact-blocks-v1" if policy["process"] == "direct_one_shot" else "v4-workspace-finalizer-v1",
    }


def render_prompt(release: Path, task_dir: Path, record: dict[str, Any], mode_record: dict[str, Any], *, inline_artifacts: bool) -> str:
    mode = str(mode_record["mode"])
    parts = [(task_dir / "public" / "instruction.md").read_text(encoding="utf-8")]
    artifacts = serialize_public_artifacts(task_dir, str(record["form"])) if inline_artifacts else ""
    if artifacts:
        parts.append(artifacts)
    skills = mode_record.get("available_skills") or {}
    if skills:
        public_skills = {
            skill_id: {
                "path": record["path"],
                "skill_file": record["skill_file"],
                "tree_sha256": record["tree_sha256"],
            }
            for skill_id, record in skills.items()
        }
        parts.extend([
            "<<<VABENCH_SKILL_AVAILABILITY>>>",
            json.dumps({
                "available_skills": public_skills,
                "lookup_policy": (
                    "Use list_skills/read_skill in direct/tool runtimes, or inspect "
                    "public/skills/<id>/SKILL.md in bash runtimes. Skill content is "
                    "not inlined into this prompt."
                ),
            }, indent=2, sort_keys=True),
            "<<<END_VABENCH_SKILL_AVAILABILITY>>>",
        ])
    for component in ordered_prompt_components(mode_record):
        if component.endswith("_wrapper.md"):
            parts.extend([
                f'<<<VABENCH_COMPONENT id="{component}">>>',
                prompt_component_path(release, component).read_text(encoding="utf-8"),
                "<<<END_VABENCH_COMPONENT>>>",
            ])
        else:
            parts.extend([
                f'<<<VABENCH_COMPONENT id="{component}">>>',
                prompt_component_path(release, component).read_text(encoding="utf-8"),
                "<<<END_VABENCH_COMPONENT>>>",
            ])
    return "\n\n".join(parts)


def install_skills(release: Path, public_root: Path, mode_record: dict[str, Any]) -> None:
    runtime_records: dict[str, dict[str, Any]] = {}
    for skill_id, record in (mode_record.get("available_skills") or {}).items():
        source = release_skill_root(release, str(skill_id), record["release_skill_path"])
        destination = public_root / "skills" / str(skill_id)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination, symlinks=False)
        runtime_records[str(skill_id)] = {
            "id": str(skill_id),
            "path": f"public/skills/{skill_id}",
            "skill_file": f"public/skills/{skill_id}/SKILL.md",
            "tree_sha256": tree_sha(destination),
            "files": [
                {
                    "path": item.relative_to(destination).as_posix(),
                    "sha256": file_sha(item),
                    "bytes": item.stat().st_size,
                }
                for item in sorted(destination.rglob("*"))
                if item.is_file()
            ],
        }
    if runtime_records:
        write_json(public_root / "skills" / "SNAPSHOT_MANIFEST.json", {
            "schema_version": "v4-runtime-skill-manifest-v1",
            "skills": runtime_records,
        })


def install_public(task_dir: Path, public_root: Path, form: str, mode: str, release: Path | None = None, mode_record: dict[str, Any] | None = None) -> None:
    source_public = task_dir / "public"
    target = public_root / "task"
    target.mkdir(parents=True)
    shutil.copy2(source_public / "instruction.md", target / "instruction.md")
    if form == "testbench":
        copy_tree(source_public / "supplied_dut", target / "supplied_dut")
    elif form == "bugfix":
        copy_tree(source_public / "buggy_bundle", target / "buggy_bundle")
        if mode in AGENTIC:
            copy_tree(source_public / "buggy_bundle", public_root / "submission")
    for relative, source in public_support_files(task_dir):
        destination = target / "public_support" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    if release is not None and mode_record is not None:
        install_skills(release, public_root, mode_record)
    runtime_contract_path = source_public / "evas_runtime.json"
    reference_only_public_testbench = (
        form == "testbench"
        and runtime_contract_path.is_file()
        and str(read_json(runtime_contract_path).get("schema_version") or "").endswith(
            "-direct-evas-testbench-reference-v1"
        )
    )
    if reference_only_public_testbench:
        shutil.copy2(runtime_contract_path, target / "evas_runtime.json")
    if mode in AGENTIC:
        for name in ("visible_test.scs", "evas_runtime.json"):
            if (source_public / name).is_file():
                shutil.copy2(source_public / name, target / name)
        copy_tree(source_public / "visible_fixtures", target / "visible_fixtures")
        commands = ["evas --help"]
        if form in {"dut", "bugfix"}:
            runtime_contract = read_json(source_public / "evas_runtime.json")
            commands.append(str(runtime_contract["command"]))
        else:
            runtime_contract = read_json(source_public / "evas_runtime.json")
            if (
                str(runtime_contract.get("schema_version") or "").endswith(
                    "-direct-evas-testbench-reference-v1"
                )
            ):
                commands.append(str(runtime_contract["candidate_command"]))
            else:
                commands.append(
                    "use candidate_command_template from "
                    "public/task/evas_runtime.json"
                )
        write_json(public_root / "evas_manifest.json", {
            "schema_version": "r45-public-evas-manifest-v1",
            "executable": "evas",
            "commands": commands,
            "runtime_contract": "public/task/evas_runtime.json",
            "direct_simulator": True,
            "private_score_available": False,
        })


def install_evaluator(task_dir: Path, evaluator_root: Path, record: dict[str, Any]) -> None:
    task_eval = task_dir / "evaluator"
    form = str(record["form"])
    evaluator_root.mkdir(parents=True)
    shutil.copy2(task_dir / "task_record.json", evaluator_root / "task_record.json")
    for name in ("family_spec.json", "checker_profile.json", "harness_spec.json"):
        shutil.copy2(task_eval / name, evaluator_root / name)
    copy_tree(task_eval / "profiles", evaluator_root / "profiles")
    shutil.copy2(task_eval / "score_policy.json", evaluator_root / "score_policy.json")
    if form in {"dut", "bugfix"}:
        copy_tree(task_eval / "solution", evaluator_root / "solution")
        shutil.copy2(task_eval / "canonical_test_profile.json", evaluator_root / "canonical_test_profile.json")
        shutil.copy2(task_eval / "trusted_replay_test.scs", evaluator_root / "trusted_replay_test.scs")
    if form == "testbench":
        copy_tree(task_eval / "solution", evaluator_root / "trusted_solution")
        copy_tree(task_eval / "mutation_bundles", evaluator_root / "mutation_bundles")
        shutil.copy2(task_eval / "mutation_catalog.json", evaluator_root / "mutation_catalog.json")
        for name in ("reference_tb.scs", "testbench_security_policy.json"):
            shutil.copy2(task_eval / name, evaluator_root / name)
        shutil.copy2(task_eval / "trusted_replay_suite.json", evaluator_root / "trusted_replay_suite.json")
        copy_tree(task_eval / "trusted_replay_fixtures", evaluator_root / "trusted_replay_fixtures")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--task", required=True)
    parser.add_argument("--mode", choices=[f"G{x}" for x in range(6)], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--per-turn-max-tokens",
        "--working-token-budget",
        dest="per_turn_max_tokens",
        type=int,
        required=True,
        help="Provider per-call max_tokens cap; not a cumulative episode budget.",
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    release = args.release.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"output exists: {output}")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    record, task_dir = task_record(release, args.task)
    mode_record = build_mode_record(release, task_dir, record, args.mode)
    public_root = output / "public"
    (public_root / "submission").mkdir(parents=True)
    install_public(task_dir, public_root, str(record["form"]), args.mode, release, mode_record)
    install_evaluator(task_dir, output / "evaluator", record)
    prompt = render_prompt(
        release,
        task_dir,
        record,
        mode_record,
        inline_artifacts=args.mode not in AGENTIC,
    )
    prompt_name = "agent_prompt.txt" if args.mode in AGENTIC else "direct_prompt.txt"
    (output / prompt_name).write_text(prompt, encoding="utf-8")
    model_mounts = [] if args.mode not in AGENTIC else [
        "public/task:ro",
        "public/submission:rw",
        "public/work:rw",
    ]
    if args.mode in AGENTIC and mode_record.get("available_skills"):
        model_mounts.append("public/skills:ro")
    provider_tools = []
    if mode_record.get("available_skills"):
        provider_tools.extend(["list_skills", "read_skill"])
    real_skill_delivery = mode_record.get("skill_delivery") == "real_skill_lookup_v1"
    write_json(output / "MODEL_ACCESS_POLICY.json", {
        "schema_version": (
            "r50-real-skills-model-access-policy-v1"
            if real_skill_delivery
            else "r45-model-access-policy-v1"
        ),
        "mode": args.mode,
        "mounts": model_mounts,
        **(
            {
                "available_skills": mode_record.get("available_skills") or {},
                "provider_tools": provider_tools,
            }
            if real_skill_delivery
            else {}
        ),
        "executables": [] if args.mode not in AGENTIC else ["evas", "vabench-submit"],
        "network": False,
        "evaluator_mounted": False,
    })
    write_json(output / "evidence" / "attempt_record.json", {
        "schema_version": "r45-attempt-record-v1",
        "task_id": args.task,
        "family_id": record["family_id"],
        "form": record["form"],
        "mode": args.mode,
        "state": "prepared",
        "termination_policy": "wall_time",
        "per_turn_max_tokens": args.per_turn_max_tokens,
        "working_token_budget": args.per_turn_max_tokens,
        "public_bundle_sha256": tree_sha(public_root / "task"),
        "initial_submission_sha256": tree_sha(public_root / "submission"),
        "submission_seeded_from_buggy_bundle": bool(record["form"] == "bugfix" and args.mode in AGENTIC),
        "evaluator_bundle_sha256": tree_sha(output / "evaluator"),
        "prompt_record_sha256": hashlib.sha256(json.dumps(mode_record, sort_keys=True).encode("utf-8")).hexdigest(),
        **(
            {"available_skill_hashes": mode_record.get("skill_hashes") or {}}
            if real_skill_delivery
            else {}
        ),
        "final_candidate_sha256": None,
        "private_score_decisions": 0,
        "telemetry": {
            "working_tokens": None,
            "provider_tokens": None,
            "model_turns": None,
            "evas_calls": None,
            "simulator_calls": None,
            "wall_time_s": None,
        },
    })
    print(json.dumps({
        "task_id": args.task,
        "form": record["form"],
        "mode": args.mode,
        "output": str(output),
        "model_mounts": model_mounts,
        "evaluator_mounted": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Run the sealed r52 score oracle and emit the trusted-replay result protocol."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from typing import Any


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
REPO = PACKAGE.parent


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def resolve_release_task(runtime: Path, record: dict[str, Any]) -> Path:
    revision = str(record.get("release_revision") or "").strip()
    candidates = []
    configured = os.environ.get("VABENCH_RELEASE_DIR", "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    if revision:
        candidates.append(PACKAGE / "release" / f"benchmarkv4-{revision}")
    candidates.append(PACKAGE / "release" / "benchmarkv4")

    relative = Path(str(record["task_dir"]))
    if not relative.parts or relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"unsafe task_dir: {record['task_dir']!r}")
    expected_contract_sha = str(record.get("public_contract_sha256") or "")
    for release in candidates:
        release = release.resolve()
        task = (release / relative).resolve()
        if not task.is_relative_to(release):
            continue
        contract = task / "public_contract.json"
        if not contract.is_file():
            continue
        if expected_contract_sha and sha256_file(contract) != expected_contract_sha:
            continue
        return task
    raise FileNotFoundError(
        f"cannot resolve release task {record.get('task_id')} with its recorded contract hash"
    )


def taxonomy(
    primary_class: str,
    stage: str,
    *,
    case_ids: list[str] | None = None,
    property_ids: list[str] | None = None,
    mutation_ids: list[str] | None = None,
    retryable: bool = False,
    responsibility: str = "candidate",
) -> dict[str, Any]:
    return {
        "schema_version": "vabench-failure-taxonomy-v1",
        "primary_class": primary_class,
        "secondary_classes": [],
        "stage": stage,
        "responsibility": responsibility,
        "retryable": retryable,
        "case_ids": list(case_ids or []),
        "property_ids": list(property_ids or []),
        "mutation_ids": list(mutation_ids or []),
    }


def compact_diagnostics(text: str, limit: int = 16) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-limit:]


def strict_spectre_lint_submission(submission: Path) -> dict[str, Any] | None:
    command = os.environ.get("VABENCH_EVAS_COMMAND", "evas").strip() or "evas"
    evas_argv = shlex.split(command)
    if not evas_argv:
        raise ValueError("VABENCH_EVAS_COMMAND resolves to an empty command")
    candidates = [
        path
        for suffix in ("*.va", "*.scs")
        for path in sorted(submission.glob(suffix))
        if path.is_file()
    ]
    diagnostics: list[str] = []
    for path in candidates:
        completed = subprocess.run(
            [
                *evas_argv,
                "lint",
                str(path),
                "--spectre-strict",
                "--format",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )
        combined = "\n".join(
            part for part in (completed.stdout, completed.stderr) if part.strip()
        )
        if completed.returncode == 0:
            continue
        diagnostics.extend(compact_diagnostics(combined))
    if not diagnostics:
        return None
    return {
        "status": "compile_failure",
        "diagnostics": diagnostics,
        "failure_taxonomy": taxonomy("compile", "compilation"),
    }


def strict_spectre_lint_testbench_submission(
    *,
    submission: Path,
    source_eval: Path,
    target_artifacts: list[str],
    public_contract: dict[str, Any],
) -> dict[str, Any] | None:
    """Lint a candidate deck with its declared read-only DUT tree staged."""
    runners = PACKAGE / "runners"
    if str(runners) not in sys.path:
        sys.path.insert(0, str(runners))
    from derived_testbench_oracle import _prepare_dut_sources

    with tempfile.TemporaryDirectory(prefix="v4_tb_strict_lint_") as td:
        staged = Path(td)
        shutil.copy2(submission / "testbench.scs", staged / "testbench.scs")
        _prepare_dut_sources(
            package_root=PACKAGE,
            source_formal=source_eval,
            run_dir=staged,
            target_artifacts=target_artifacts,
            negative_bundle=None,
            dut_subdir="dut",
            public_contract=public_contract,
        )
        return strict_spectre_lint_submission(staged)


def classify_dut_result(returncode: int, output: str) -> dict[str, Any]:
    diagnostics = compact_diagnostics(output)
    if returncode == 0:
        return {"status": "passed", "diagnostics": diagnostics}
    if (
        "Rust core is required and could not be loaded" in output
        or "Rust backend library not found" in output
    ):
        return {
            "status": "infrastructure_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy(
                "infrastructure",
                "infrastructure",
                retryable=True,
                responsibility="system",
            ),
        }
    if (
        "SCORE_PREFLIGHT_FAIL" in output
        or "SCORE_NO_COMPILE_MARKER" in output
        or "Failed to compile Verilog-A" in output
        or "ERROR [rust_lowering]:" in output
        or ("SCORE_EVAS_FAIL" in output and "Parse error" in output)
    ):
        return {
            "status": "compile_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy("compile", "compilation"),
        }
    if (
        "SCORE_BEHAVIOR_FAIL" in output
        or "SCORE_SIDE_EFFECT_FAIL" in output
    ):
        failed_properties = sorted(
            {
                match.group(1)
                for match in re.finditer(
                    r"\b(P_[A-Z0-9_]+)\s+mismatch_count=([1-9][0-9]*)",
                    output,
                )
            }
        )
        return {
            "status": "behavior_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy(
                "property",
                "property_check",
                property_ids=failed_properties,
            ),
        }
    if (
        "SCORE_EVAS_FAIL" in output
        or "SCORE_NO_TRAN_MARKER" in output
        or "SCORE_BEHAVIOR_NO_TRACE" in output
    ):
        return {
            "status": "runtime_failure",
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy("runtime", "simulation"),
        }
    return {
        "status": "infrastructure_failure",
        "diagnostics": diagnostics or ["score_oracle_failed_without_known_marker"],
        "failure_taxonomy": taxonomy(
            "infrastructure",
            "infrastructure",
            retryable=True,
            responsibility="system",
        ),
    }


def mutation_bundle(source_eval: Path, mutation_id: str, target_artifacts: list[str]) -> Path:
    directory = source_eval / "mutation_bundles" / mutation_id
    if not directory.is_dir():
        raise FileNotFoundError(f"cannot resolve mutation bundle for {mutation_id}")
    present = {path.relative_to(directory).as_posix() for path in directory.rglob("*.va")}
    expected = set(target_artifacts)
    if not present.intersection(expected):
        raise FileNotFoundError(
            f"mutation bundle {mutation_id} does not map to declared DUT artifacts"
        )
    return directory


def testbench_negative_suite(source_eval: Path) -> list[str]:
    policy = read_json(source_eval / "score_policy.json")
    suite = [str(item) for item in policy.get("negative_suite_mutation_ids") or []]
    if len(suite) != 5 or len(set(suite)) != 5:
        raise ValueError(
            f"score_policy negative suite must contain exactly 5 unique mutations, got {len(suite)}"
        )
    return suite


def outcome_value(result: Any) -> str:
    value = getattr(result, "outcome", "")
    return str(getattr(value, "value", value))


def result_notes(result: Any) -> list[str]:
    return [str(note) for note in getattr(result, "notes", ()) if str(note)]


def compile_like_failure(notes: list[str]) -> bool:
    text = "\n".join(notes)
    return (
        "Parse error" in text
        or "Failed to compile Verilog-A" in text
        or "syntax" in text.lower()
    )


def checker_infrastructure_failure(notes: list[str]) -> bool:
    return any(
        marker in note
        for note in notes
        for marker in (
            "behavior_eval_timeout>",
            "behavior_eval_no_result",
            "behavior_eval_error=",
        )
    )


def reference_requires_mutation_replay(reference: Any) -> bool:
    """Run mutations only after the candidate testbench passes the gold DUT."""
    return outcome_value(reference) == "reference_pass"


def classify_testbench_result(
    reference: Any,
    negatives: list[Any],
    mutation_ids: list[str],
) -> dict[str, Any]:
    diagnostics = compact_diagnostics(
        "\n".join(result_notes(reference) + [note for item in negatives for note in result_notes(item)]),
        limit=32,
    )
    reference_outcome = outcome_value(reference)
    if reference_outcome == "reference_pass":
        survived = [
            mutation_id
            for mutation_id, result in zip(mutation_ids, negatives, strict=True)
            if outcome_value(result) == "survived"
        ]
        invalid = [
            mutation_id
            for mutation_id, result in zip(mutation_ids, negatives, strict=True)
            if outcome_value(result) == "invalid_run"
        ]
        if not survived and not invalid:
            return {"status": "passed", "diagnostics": diagnostics}
        if survived:
            return {
                "status": "behavior_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "mutation_survival",
                    "mutation_check",
                    case_ids=survived,
                    mutation_ids=survived,
                ),
            }
        invalid_notes = [
            note
            for mutation_id, result in zip(mutation_ids, negatives, strict=True)
            if mutation_id in invalid
            for note in result_notes(result)
        ]
        if checker_infrastructure_failure(invalid_notes):
            return {
                "status": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "infrastructure",
                    case_ids=invalid,
                    mutation_ids=invalid,
                    retryable=True,
                    responsibility="system",
                ),
            }
        status = "compile_failure" if compile_like_failure(invalid_notes) else "runtime_failure"
        return {
            "status": status,
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy(
                "compile" if status == "compile_failure" else "runtime",
                "compilation" if status == "compile_failure" else "simulation",
                case_ids=invalid,
                mutation_ids=invalid,
            ),
        }

    notes = result_notes(reference)
    if reference_outcome == "invalid_run":
        if checker_infrastructure_failure(notes):
            return {
                "status": "infrastructure_failure",
                "diagnostics": diagnostics,
                "failure_taxonomy": taxonomy(
                    "infrastructure",
                    "infrastructure",
                    case_ids=["reference"],
                    retryable=True,
                    responsibility="system",
                ),
            }
        status = "compile_failure" if compile_like_failure(notes) else "runtime_failure"
        return {
            "status": status,
            "diagnostics": diagnostics,
            "failure_taxonomy": taxonomy(
                "compile" if status == "compile_failure" else "runtime",
                "compilation" if status == "compile_failure" else "simulation",
                case_ids=["reference"],
            ),
        }
    return {
        "status": "behavior_failure",
        "diagnostics": diagnostics,
        "failure_taxonomy": taxonomy(
            "functional",
            "functional_check",
            case_ids=["reference"],
        ),
    }


def run_testbench_score(runtime: Path, record: dict[str, Any], release_task: Path) -> dict[str, Any]:
    runners = PACKAGE / "runners"
    if str(runners) not in sys.path:
        sys.path.insert(0, str(runners))
    from derived_testbench_oracle import _run_case
    from testbench_security import validate_testbench

    source_eval = release_task / "evaluator"
    contract = read_json(release_task / "public_contract.json")
    family_spec = read_json(source_eval / "family_spec.json")
    checker = read_json(source_eval / "checker_profile.json")
    mutation_ids = testbench_negative_suite(source_eval)
    target_artifacts = [
        str(item["path"])
        for item in (family_spec.get("artifact_contract") or {}).get("files") or []
    ]
    if not target_artifacts:
        raise ValueError("family_spec declares no DUT target artifacts")
    checker_task_id = str(checker["checker_task_id"])
    required_signals = set(
        str(item) for item in (checker.get("trace_contract") or {}).get("required_signals") or []
    )
    required_signals.update(
        str(item) for item in contract.get("trace_contract", {}).get("required_signals") or []
    )

    submission = Path(
        os.environ.get("VABENCH_FINAL_SUBMISSION_DIR", runtime / "evidence" / "final_submission")
    ).resolve()
    tb = submission / "testbench.scs"
    if not tb.is_file():
        return {
            "status": "compile_failure",
            "diagnostics": ["missing final submission artifact: testbench.scs"],
            "failure_taxonomy": taxonomy("compile", "compilation"),
        }

    security_policy = read_json(source_eval / "testbench_security_policy.json")
    security = validate_testbench(tb, contract, security_policy)
    if not security.valid:
        return {
            "status": "compile_failure",
            "diagnostics": compact_diagnostics(
                "\n".join(f"security: {note}" for note in security.diagnostics)
            ),
            "failure_taxonomy": taxonomy("compile", "compilation"),
        }

    lint_failure = strict_spectre_lint_testbench_submission(
        submission=submission,
        source_eval=source_eval,
        target_artifacts=target_artifacts,
        public_contract=contract,
    )
    if lint_failure is not None:
        return lint_failure

    previous_engine = os.environ.get("EVAS_ENGINE")
    previous_default_engine = os.environ.get("VAEVAS_DEFAULT_EVAS_ENGINE")
    previous_persistent_worker = os.environ.get("VAEVAS_EVAS_PERSISTENT_WORKER")
    os.environ["EVAS_ENGINE"] = "evas2"
    os.environ["VAEVAS_DEFAULT_EVAS_ENGINE"] = "evas2"
    # Trusted replay must execute the exact VABENCH_EVAS_COMMAND supplied by
    # the scorer.  The legacy persistent worker resolves a source checkout
    # independently, so keep it disabled at this identity boundary.
    os.environ["VAEVAS_EVAS_PERSISTENT_WORKER"] = "0"
    try:
        reference = _run_case(
            package_root=PACKAGE,
            tb_source=tb,
            source_formal=source_eval,
            target_artifacts=target_artifacts,
            negative_bundle=None,
            checker_task_id=checker_task_id,
            required_signals=required_signals,
            label="reference",
            dut_subdir="dut",
            public_contract=contract,
            required_evas_engine="evas2",
        )
        if not reference_requires_mutation_replay(reference):
            return classify_testbench_result(reference, [], mutation_ids)
        negatives = [
            _run_case(
                package_root=PACKAGE,
                tb_source=tb,
                source_formal=source_eval,
                target_artifacts=target_artifacts,
                negative_bundle=mutation_bundle(source_eval, mutation_id, target_artifacts),
                checker_task_id=checker_task_id,
                required_signals=required_signals,
                label=mutation_id,
                dut_subdir="dut",
                public_contract=contract,
                required_evas_engine="evas2",
            )
            for mutation_id in mutation_ids
        ]
    finally:
        if previous_engine is None:
            os.environ.pop("EVAS_ENGINE", None)
        else:
            os.environ["EVAS_ENGINE"] = previous_engine
        if previous_default_engine is None:
            os.environ.pop("VAEVAS_DEFAULT_EVAS_ENGINE", None)
        else:
            os.environ["VAEVAS_DEFAULT_EVAS_ENGINE"] = previous_default_engine
        if previous_persistent_worker is None:
            os.environ.pop("VAEVAS_EVAS_PERSISTENT_WORKER", None)
        else:
            os.environ["VAEVAS_EVAS_PERSISTENT_WORKER"] = previous_persistent_worker
    return classify_testbench_result(reference, negatives, mutation_ids)


def staged_score_task(runtime: Path, release_task: Path, root: Path) -> Path:
    task = root / "task"
    shutil.copytree(runtime / "evaluator", task / "evaluator")
    shutil.copy2(release_task / "public_contract.json", task / "public_contract.json")
    family_spec = runtime / "evaluator" / "family_spec.json"
    shutil.copy2(family_spec, task / "family_spec.json")
    public_support = runtime / "public" / "task" / "public_support"
    if public_support.is_dir():
        shutil.copytree(public_support, task / "public_support")
    return task


def run_dut_score(runtime: Path, record: dict[str, Any], release_task: Path) -> dict[str, Any]:
    for path in (PACKAGE / "runners", PACKAGE / "scripts"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from feedback_oracle import run_score

    submission = Path(
        os.environ.get("VABENCH_FINAL_SUBMISSION_DIR", runtime / "evidence" / "final_submission")
    ).resolve()
    lint_failure = strict_spectre_lint_submission(submission)
    if lint_failure is not None:
        return lint_failure
    with tempfile.TemporaryDirectory(prefix="v4_trusted_replay_") as td:
        task = staged_score_task(runtime, release_task, Path(td))
        wrapper = task / "test_score" / "run_score.py"
        wrapper.parent.mkdir(parents=True)
        previous_root = os.environ.get("VABENCH_ROOT")
        previous_source = os.environ.get("VABENCH_SCORE_SOURCE_DIR")
        previous_worker = os.environ.get("VAEVAS_EVAS_PERSISTENT_WORKER")
        os.environ["VABENCH_ROOT"] = str(REPO)
        os.environ["VABENCH_SCORE_SOURCE_DIR"] = str(submission)
        os.environ["VAEVAS_EVAS_PERSISTENT_WORKER"] = "0"
        output = io.StringIO()
        try:
            with contextlib.redirect_stdout(output):
                returncode = run_score(wrapper, timeout_s=120)
        finally:
            if previous_root is None:
                os.environ.pop("VABENCH_ROOT", None)
            else:
                os.environ["VABENCH_ROOT"] = previous_root
            if previous_source is None:
                os.environ.pop("VABENCH_SCORE_SOURCE_DIR", None)
            else:
                os.environ["VABENCH_SCORE_SOURCE_DIR"] = previous_source
            if previous_worker is None:
                os.environ.pop("VAEVAS_EVAS_PERSISTENT_WORKER", None)
            else:
                os.environ["VAEVAS_EVAS_PERSISTENT_WORKER"] = previous_worker
        return classify_dut_result(returncode, output.getvalue())


def write_result(value: dict[str, Any]) -> None:
    raw = os.environ.get("VABENCH_TRUSTED_REPLAY_RESULT", "").strip()
    if not raw:
        raise SystemExit("VABENCH_TRUSTED_REPLAY_RESULT is required")
    path = Path(raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    raw_runtime = os.environ.get("VABENCH_RUNTIME_DIR", "").strip()
    if not raw_runtime:
        raise SystemExit("VABENCH_RUNTIME_DIR is required")
    runtime = Path(raw_runtime).resolve()
    try:
        record = read_json(runtime / "evaluator" / "task_record.json")
        release_task = resolve_release_task(runtime, record)
        form = str(record.get("form") or "")
        if form in {"dut", "bugfix"}:
            result = run_dut_score(runtime, record, release_task)
        elif form == "testbench":
            result = run_testbench_score(runtime, record, release_task)
        else:
            raise NotImplementedError(f"trusted replay is not implemented for form={form}")
    except Exception as exc:
        result = {
            "status": "infrastructure_failure",
            "diagnostics": [f"{type(exc).__name__}: {str(exc)[:1000]}"],
            "failure_taxonomy": taxonomy(
                "infrastructure",
                "infrastructure",
                retryable=True,
                responsibility="system",
            ),
        }
    write_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

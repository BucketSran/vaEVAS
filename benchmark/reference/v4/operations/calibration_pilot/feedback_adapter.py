#!/usr/bin/env python3
"""Legacy hidden-oracle adapter retained only to reproduce pre-r45 experiments.

The active G2-G5 runner never exposes or invokes this module.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[1]
REPO = PACKAGE.parent
RELEASE = Path(os.environ.get("VABENCH_RELEASE_DIR", PACKAGE / "release" / "benchmarkv4")).resolve()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def runtime_task(runtime: Path) -> tuple[dict[str, Any], Path]:
    attempt = read_json(runtime / "evidence" / "attempt_record.json")
    record = read_json(runtime / "evaluator" / "task_record.json")
    if record.get("task_id") != attempt.get("task_id"):
        raise SystemExit("runtime task record does not match the attempt record")
    index = read_json(RELEASE / "TASK_INDEX.json")["tasks"]
    matches = [row for row in index if row["task_id"] == attempt["task_id"]]
    if len(matches) != 1:
        raise SystemExit(f"cannot resolve runtime task {attempt['task_id']}")
    task_dir = RELEASE / matches[0]["task_dir"]
    return record, task_dir


def runtime_or_release(runtime: Path, task_dir: Path, relative: str) -> Path:
    runtime_path = runtime / relative
    if runtime_path.exists():
        return runtime_path
    release_path = task_dir / relative.removeprefix("evaluator/")
    if release_path.exists():
        return release_path
    release_eval_path = task_dir / relative
    if release_eval_path.exists():
        return release_eval_path
    raise FileNotFoundError(f"cannot resolve {relative} in runtime or release task")


def run_dut_feedback(runtime: Path, _record: dict[str, Any], task_dir: Path) -> int:
    runners = PACKAGE / "runners"
    scripts = PACKAGE / "scripts"
    for path in (runners, scripts):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from feedback_oracle import run_feedback

    with tempfile.TemporaryDirectory(prefix="v4_calibration_oracle_") as td:
        task = Path(td) / "task"
        shutil.copytree(runtime / "evaluator", task / "evaluator")
        shutil.copy2(runtime_or_release(runtime, task_dir, "evaluator/public_contract.json"), task / "public_contract.json")
        shutil.copy2(runtime_or_release(runtime, task_dir, "evaluator/family_spec.json"), task / "family_spec.json")
        public_support = runtime / "public" / "task" / "public_support"
        if public_support.is_dir():
            shutil.copytree(public_support, task / "public_support")
        wrapper = task / "test_feedback" / "run_feedback.py"
        wrapper.parent.mkdir(parents=True)
        old_root = os.environ.get("VABENCH_ROOT")
        old_source = os.environ.get("VABENCH_FEEDBACK_SOURCE_DIR")
        os.environ["VABENCH_ROOT"] = str(REPO)
        os.environ["VABENCH_FEEDBACK_SOURCE_DIR"] = str(runtime / "public" / "submission")
        try:
            return run_feedback(wrapper, timeout_s=120)
        finally:
            if old_root is None:
                os.environ.pop("VABENCH_ROOT", None)
            else:
                os.environ["VABENCH_ROOT"] = old_root
            if old_source is None:
                os.environ.pop("VABENCH_FEEDBACK_SOURCE_DIR", None)
            else:
                os.environ["VABENCH_FEEDBACK_SOURCE_DIR"] = old_source


def mutation_bundle(source_eval: Path, mutation_id: str, target_artifacts: list[str]) -> Path:
    directory = source_eval / "mutation_bundles" / mutation_id
    if not directory.is_dir():
        raise SystemExit(f"cannot resolve mutation bundle for {mutation_id}")
    present = {path.relative_to(directory).as_posix() for path in directory.rglob("*.va")}
    expected = set(target_artifacts)
    if not present.intersection(expected):
        raise SystemExit(f"mutation bundle {mutation_id} does not map to the declared DUT artifacts")
    return directory


def testbench_negative_suite(source_eval: Path) -> list[str]:
    policy = read_json(source_eval / "score_policy.json")
    return [str(item) for item in policy.get("negative_suite_mutation_ids") or []]


def run_testbench_feedback(runtime: Path, record: dict[str, Any], task_dir: Path) -> int:
    runners = PACKAGE / "runners"
    if str(runners) not in sys.path:
        sys.path.insert(0, str(runners))
    from derived_testbench_oracle import CaseOutcome, TestbenchResult, _run_case
    from testbench_security import validate_testbench

    source_eval = runtime / "evaluator"
    contract = read_json(runtime_or_release(runtime, task_dir, "evaluator/public_contract.json"))
    family_spec = read_json(runtime_or_release(runtime, task_dir, "evaluator/family_spec.json"))
    checker = read_json(source_eval / "checker_profile.json")
    suite = testbench_negative_suite(source_eval)
    target_artifacts = [
        str(item["path"])
        for item in (family_spec.get("artifact_contract") or {}).get("files") or []
    ]
    checker_task_id = str(checker["checker_task_id"])
    required_signals = set(str(item) for item in (checker.get("trace_contract") or {}).get("required_signals") or [])
    required_signals.update(str(item) for item in contract.get("trace_contract", {}).get("required_signals") or [])
    tb = runtime / "public" / "submission" / "testbench.scs"
    if not tb.is_file():
        print("FEEDBACK_TB_MISSING testbench.scs")
        return 1

    security_policy = read_json(runtime / "evaluator" / "testbench_security_policy.json")
    security = validate_testbench(tb, contract, security_policy)
    if not security.valid:
        for note in security.diagnostics:
            print(f"security: {note}")
        print("FEEDBACK_TB_INVALID_RUN")
        return 1

    gold = _run_case(
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
    )
    for note in gold.notes:
        print(note)
    if gold.outcome is not CaseOutcome.REFERENCE_PASS:
        print(f"FEEDBACK_TB_{gold.outcome.value.upper()}")
        return 1

    if len(suite) != 5 or len(set(str(item) for item in suite)) != 5:
        print(f"FEEDBACK_TB_NEGATIVE_SUITE_INVALID count={len(suite)} expected=5")
        return 1
    negative_results = []
    for index, mutation_id in enumerate(suite, 1):
        result = _run_case(
            package_root=PACKAGE,
            tb_source=tb,
            source_formal=source_eval,
            target_artifacts=target_artifacts,
            negative_bundle=mutation_bundle(source_eval, str(mutation_id), target_artifacts),
            checker_task_id=checker_task_id,
            required_signals=required_signals,
            label=f"negative_{index}",
            dut_subdir="dut",
            public_contract=contract,
        )
        negative_results.append(result)
        for note in result.notes:
            print(note)
    aggregate = TestbenchResult(gold, tuple(negative_results))
    print(
        f"FEEDBACK_TB_{'PASS' if aggregate.passed else 'NEGATIVE_COVERAGE_FAIL'} "
        f"killed={aggregate.killed_count}/5 survived={aggregate.survived_count} invalid={aggregate.invalid_count}"
    )
    return 0 if aggregate.passed else 1


def main() -> int:
    raw = os.environ.get("VABENCH_RUNTIME_DIR")
    if not raw:
        raise SystemExit("VABENCH_RUNTIME_DIR is required")
    runtime = Path(raw).resolve()
    record, task_dir = runtime_task(runtime)
    if record["form"] in {"dut", "bugfix"}:
        return run_dut_feedback(runtime, record, task_dir)
    if record["form"] == "testbench":
        return run_testbench_feedback(runtime, record, task_dir)
    raise SystemExit(f"unsupported form: {record['form']}")


if __name__ == "__main__":
    raise SystemExit(main())

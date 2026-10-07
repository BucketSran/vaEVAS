"""Task packaging and operator calibration through the existing circuit harness.

No SSH or simulator lifecycle is reimplemented here. Each condition is one
harness job so its waveform has the existing per-job output budget.
"""
import argparse
import ast
import hashlib
import importlib
import json
from pathlib import Path
import re
import shutil
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
VERSION = "circuit-first-batch-v1-development"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def harness_modules(checkout):
    checkout = Path(checkout).resolve()
    sys.path.insert(0, str(checkout))
    try:
        modules = [importlib.import_module("alphaapollo.common.execution.chips." + name)
                   for name in ["candidate_bundle", "benchmark_spectre", "benchmark_remote"]]
    finally:
        sys.path.pop(0)
    if any(not Path(module.__file__).resolve().is_relative_to(checkout) for module in modules):
        raise ValueError("loaded harness differs from selected checkout")
    return modules


def prepare(task, candidate, output, harness_checkout, *, case_names=None):
    if Path(candidate).is_symlink():
        raise ValueError("candidate must not be a symlink")
    task, candidate, output = map(lambda p: Path(p).resolve(), (task, candidate, output))
    freeze, packages, _ = harness_modules(harness_checkout)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    contract = json.loads((task / "tests/contract.json").read_text())
    files = contract.get("candidate_files", ["dut.va"])
    source = output / "source"
    source.mkdir(mode=0o700)
    for name in files:
        if not name or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("unsafe candidate name")
        src = candidate if name == "dut.va" else candidate.parent / name
        dst = source / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink() or not src.is_file():
            raise ValueError("missing or linked candidate file")
        shutil.copyfile(src, dst)
    frozen = output / "frozen"
    freeze.freeze_candidate(source, frozen, files, task_id=task.name, task_version=VERSION, reason="first batch calibration")
    templates = {p.name: p.read_bytes() for p in (task / "tests").iterdir() if p.is_file()}
    # The actual portable runtime is coordinator-owned. Task graders are owned
    # by the task's checkout and snapshotted with the task.
    for name in ["circuit_task.py", "adc_linearity.py"]:
        templates[name] = (ROOT / "benchmark/checkers" / name).read_bytes()
    tree = ast.parse(templates["verify.py"])
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    for name in modules:
        if name.startswith("first_batch_"):
            templates[name + ".py"] = (task.parents[1] / "checkers" / (name + ".py")).read_bytes()
    # Bytecode output is excluded by the existing job archive inventory, while
    # benchmark artifacts are complete. Keep checker execution bytecode-free.
    templates["test.sh"] = b'#!/bin/sh\nset -eu\nexec python3.12 -B "$(dirname "$0")/verify.py" --candidate "$CANDIDATE" --output "$VERIFY_OUTPUT"\n'
    all_cases = json.loads(templates["cases.json"])
    if not all_cases or len({c["name"] for c in all_cases}) != len(all_cases):
        raise ValueError("empty or duplicate cases")
    cases = all_cases
    if case_names is not None:
        if not case_names or not set(case_names) <= {c["name"] for c in all_cases}:
            raise ValueError("unknown or empty case selection")
        cases = [case for case in all_cases if case["name"] in case_names]
    identity = {name: hashlib.sha256(data).hexdigest() for name, data in templates.items()}
    identity["instruction.md"] = sha(task / "instruction.md")
    criteria = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    records = []
    for case in cases:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", case["name"]):
            raise ValueError("unsafe condition name")
        package = output / "packages" / case["name"]
        (package / "tests").mkdir(mode=0o700, parents=True)
        for name, data in templates.items():
            (package / "tests" / name).write_bytes(data)
        (package / "tests/cases.json").write_text(json.dumps([case], indent=2) + "\n")
        inventory = {str(p.relative_to(package)): {"sha256": sha(p), "bytes": p.stat().st_size}
                     for p in package.rglob("*") if p.is_file()}
        manifest = {"schema_version": 1, "task_id": task.name, "task_version": VERSION,
                    "criteria_sha256": criteria, "condition_id": case["name"], "task_set": "extension",
                    "purpose": "final", "entrypoint": "tests/test.sh", "candidate_file": "dut.va",
                    "report_path": "verifier/report.json", "files": inventory, "feedback_fields": []}
        (package / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        records.append({"condition_id": case["name"], "package": str(package), "sha256": packages.package_identity(package, purpose="final")["sha256"]})
    record = {"status": "prepared_only", "simulator_executed": False, "task": str(task), "task_id": task.name,
              "candidate": freeze.verify_candidate(frozen), "criteria_sha256": criteria, "source_identity": identity, "cases": records}
    (output / "preparation.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def execute(prepared, config_path):
    """Serial within one calibration; coordinator limits simultaneous callers."""
    prepared = Path(prepared).resolve()
    config = json.loads(Path(config_path).read_text())
    _, _, remote = harness_modules(config["harness_checkout"])
    plan = json.loads((prepared / "preparation.json").read_text())
    evidence = prepared / "remote"
    evidence.mkdir(mode=0o700, exist_ok=True)
    transport = remote.RemoteBenchmarkSpectre(config["remote"], evidence)
    results = []
    for case in plan["cases"]:
        state_path = prepared / (case["condition_id"] + "-job.json")
        if state_path.exists():
            saved = json.loads(state_path.read_text())
            job_id = saved["job_id"]
            state = transport.query(job_id)
        else:
            label = re.sub(r"[^A-Za-z0-9_-]", "_", case["condition_id"][:25])
            job_id = "bf-" + uuid.uuid4().hex[:20] + "-" + label
            state_path.write_text(json.dumps({"job_id": job_id, "condition_id": case["condition_id"]}) + "\n")
            state = transport.submit(prepared / "frozen", Path(case["package"]), job_id)
        print(json.dumps({"job_id": job_id, "condition": case["condition_id"], "state": state.get("state")}), flush=True)
        deadline = time.monotonic() + 600
        while state.get("state") != "finished":
            if state.get("state") in {"missing", "unknown"} or time.monotonic() > deadline:
                raise RuntimeError("job state unresolved; resume the same calibration, do not submit a new ID")
            time.sleep(3)
            state = transport.query(job_id)
        while state.get("archive", {}).get("state") not in {"verified", "failed"}:
            if time.monotonic() > deadline:
                raise RuntimeError("archive not yet verified; recover the same job ID")
            time.sleep(3)
            state = transport.query(job_id)
        if state.get("archive", {}).get("state") == "failed":
            raise RuntimeError("job complete but archive failed: " + str(state["archive"].get("error")))
        result = transport.retrieve(job_id)
        record = {"job_id": job_id, "condition_id": case["condition_id"], "result": result}
        results.append(record)
        (prepared / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        print(json.dumps({"job_id": job_id, "execution": result.get("execution"), "score": result.get("score")}), flush=True)
        if result.get("execution") != "ok":
            break
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--task", type=Path, required=True)
    prep.add_argument("--candidate", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--harness-checkout", type=Path, required=True)
    prep.add_argument("--case", action="append")
    run = sub.add_parser("execute")
    run.add_argument("prepared", type=Path)
    run.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.task, args.candidate, args.output, args.harness_checkout, case_names=args.case)
        print(json.dumps({"status": result["status"], "conditions": len(result["cases"]), "criteria_sha256": result["criteria_sha256"]}))
    else:
        execute(args.prepared, args.config)

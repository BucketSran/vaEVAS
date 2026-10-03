"""Check pilot input identities without running models or Spectre."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]
# These wrappers changed after the run to maintain/report its provenance.
# They are recorded in future manifests, but do not define calibration answers.
REPORT_WRAPPERS = {
    "experiments/va_screen/run_pilot.py",
    "experiments/va_screen/summarize.py",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def evidence(root):
    folder = root / "experiments/va_screen"
    record = json.loads((folder / "CALIBRATION.json").read_text())
    raw = (folder / "FROZEN_INPUTS.json").read_bytes()
    if sha(raw) != record["frozen_manifest_sha256"]:
        raise ValueError("frozen manifest identity changed")
    return record, json.loads(raw)


def verify_current_inputs(root=ROOT):
    """Require unchanged calibration consumers and identical checker copies."""
    root = Path(root)
    record, frozen = evidence(root)
    for name, expected in frozen.items():
        if name in REPORT_WRAPPERS or name.endswith(".md"):
            continue
        path = root / name
        if not path.is_file() or sha(path.read_bytes()) != expected:
            raise ValueError(f"calibrated input changed or missing: {name}")
    canonical = "benchmark/checkers/spectre_waveform.py"
    expected = record["source_identity_checked_after_run"][canonical]
    if sha((root / canonical).read_bytes()) != expected:
        raise ValueError("shared checker changed: affected tasks need recalibration")
    tasks = []
    for report in record["calibration_reports"]:
        task = root / "benchmark/tasks" / report["task"]
        for key, name in [
            ("candidate_sha256", "solution/dut.va"),
            ("cases_sha256", "tests/cases.json"),
            ("checker_sha256", "tests/verify.py"),
        ]:
            if sha((task / name).read_bytes()) != report[key]:
                raise ValueError(f"calibration report mismatch: {report['task']}/{name}")
        names = [c["name"] for c in json.loads((task / "tests/cases.json").read_text())]
        if (not names or [c["name"] for c in report["cases"]] != names
                or report["status"] != "completed" or report["reward"] != 1
                or any(c["status"] != "graded" or not c["passed"] for c in report["cases"])):
            raise ValueError(f"reference calibration failed: {report['task']}")
        if report["checker_sha256"] != expected:
            raise ValueError(f"checker copy differs from shared source: {report['task']}")
        tasks.append(task)
    if not tasks or len(set(tasks)) != len(tasks):
        raise ValueError("missing or duplicate calibration tasks")
    if {p.name for p in tasks} != {p.name for p in (root / "benchmark/tasks").glob("va0[1-6]-*")}:
        raise ValueError("task inventory differs from calibration")
    mutations = record["mutation_reports"]
    if len(mutations) != len(tasks) or {r["task"] for r in mutations} != {p.name for p in tasks}:
        raise ValueError("mutation calibration inventory mismatch")
    for report in mutations:
        reference = next(r for r in record["calibration_reports"] if r["task"] == report["task"])
        if (report["reward"] != 0
                or report["status"] != "completed"
                or [c["name"] for c in report["cases"]] != [c["name"] for c in reference["cases"]]
                or not any(not c["passed"] for c in report["cases"])
                or any(c["status"] != "graded" for c in report["cases"])
                or report["cases_sha256"] != reference["cases_sha256"]
                or report["checker_sha256"] != reference["checker_sha256"]):
            raise ValueError(f"mutation calibration failed: {report['task']}")
    verify_results(root, record, frozen)
    return tasks


def verify_results(root, calibration, frozen):
    """Check the final denominator and bind each score to the frozen inputs."""
    results = json.loads((root / "experiments/va_screen/RESULTS.json").read_text())
    tasks = {r["task"]: r for r in calibration["calibration_reports"]}
    expected = {(task, channel) for task in tasks for channel in ("codex", "glm")}
    records = results["records"]
    if (results["expected_submissions"] != len(expected)
            or results["graded_submissions"] != len(expected) or len(records) != len(expected)
            or {(r["task"], r["channel"]) for r in records} != expected):
        raise ValueError("final result submission inventory mismatch")
    for result in records:
        reference = tasks[result["task"]]
        cases = result["cases"]
        passed = sum(bool(c.get("passed")) for c in cases)
        if (not cases or [c["name"] for c in cases] != [c["name"] for c in reference["cases"]]
                or result["conditions"] != len(cases) or result["passed_conditions"] != passed
                or result["reward"] != int(passed == len(cases))
                or result["cases_sha256"] != reference["cases_sha256"]
                or result["checker_sha256"] != reference["checker_sha256"]
                or result["instruction_sha256"] != frozen[f"benchmark/tasks/{result['task']}/instruction.md"]):
            raise ValueError(f"final result identity/count mismatch: {result['task']}/{result['channel']}")
    if (results["protocol"]["input_manifest_sha256"] != calibration["frozen_manifest_sha256"]
            or results["publication_identity"]["source_snapshot_commit"] != calibration["source_snapshot_commit"]):
        raise ValueError("final results and calibration source disagree")


def verify_historical_inputs(root=ROOT):
    """Resolve the frozen source from Git, including superseded report wrappers."""
    root = Path(root)
    record, frozen = evidence(root)
    expected_files = {**frozen, **record["source_identity_checked_after_run"]}
    for name, expected in expected_files.items():
        data = subprocess.check_output(
            ["git", "show", f"{record['source_snapshot_commit']}:{name}"], cwd=root
        )
        if sha(data) != expected:
            raise ValueError(f"historical source identity mismatch: {name}")
    results = json.loads((root / "experiments/va_screen/RESULTS.json").read_text())
    source = subprocess.check_output(
        ["git", "show", f"{record['source_snapshot_commit']}:experiments/va_screen/summarize.py"],
        cwd=root,
    )
    if sha(source) != results["analysis_script_sha256"]:
        raise ValueError("result analysis source identity mismatch")
    if results["protocol"]["input_manifest_sha256"] != record["frozen_manifest_sha256"]:
        raise ValueError("results and frozen manifest disagree")
    return len(expected_files)


def snapshot_files(root=ROOT, tasks=None):
    """Include executed task files, shared checker and runtime adapter sources."""
    root = Path(root)
    tasks = tasks if tasks is not None else verify_current_inputs(root)
    files = [p for task in tasks for p in task.rglob("*")
             if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    files += list((root / "experiments/va_screen").glob("*.py"))
    files += [root / "benchmark/checkers/spectre_waveform.py",
              root / "experiments/va_screen/CALIBRATION.json",
              root / "experiments/va_screen/FROZEN_INPUTS.json"]
    return {str(p.relative_to(root)): sha(p.read_bytes()) for p in sorted(set(files))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical", action="store_true", help="also verify the original Git source")
    args = parser.parse_args()
    tasks = verify_current_inputs()
    print(f"Current calibration identities: {len(tasks)} tasks passed")
    if args.historical:
        print(f"Historical identities: {verify_historical_inputs()} files passed")


if __name__ == "__main__":
    main()

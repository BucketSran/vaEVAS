"""Fixed Spectre task verifier; transport and job isolation belong to Harness.

Candidate bytes are unchanged. A nonzero simulator exit is not a circuit verdict:
retain the diagnostics for adjudication instead of turning an unknown into zero.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time

from adc_linearity import read_psf


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative_name(value):
    if (not isinstance(value, str) or not value or "\\" in value or "\0" in value
            or Path(value).is_absolute() or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("invalid relative asset path")
    return value


def validate_rows(rows, case):
    required = {"time", *case["signals"]}
    if len(rows) < 2 or any(not required.issubset(row) for row in rows):
        raise ValueError("missing required waveform")
    if any(not math.isfinite(v) for row in rows for v in row.values()):
        raise ValueError("non-finite waveform")
    times = [row["time"] for row in rows]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("non-increasing waveform times")
    tolerance = max(1e-15, abs(case["stop"]) * 1e-8)
    if abs(times[0]) > tolerance or abs(times[-1] - case["stop"]) > tolerance:
        raise ValueError("incomplete transient interval")


def write_report(output, report):
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if report["reward"] is not None:
        (output / "reward.txt").write_text(str(report["reward"]) + "\n")
    return report


def verify(candidate, output, tests, evaluate, case_name=None):
    candidate, output, tests = map(Path, (candidate, output, tests))
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise FileExistsError("verification output must be a new empty directory")
    output.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    report = {"schema_version": 2, "status": "infrastructure_error", "reward": None,
              "cases": [], "runtime_sha256": digest(__file__),
              "parser_sha256": digest(Path(__file__).with_name("adc_linearity.py"))}
    try:
        cases_path, contract_path = tests / "cases.json", tests / "contract.json"
        cases = json.loads(cases_path.read_text())
        contract = json.loads(contract_path.read_text())
        report.update(cases_sha256=digest(cases_path), contract_sha256=digest(contract_path))
        files = contract["candidate_files"]
        if not files or files[0] != "dut.va" or len(files) != len(set(files)):
            raise ValueError("candidate inventory must start with dut.va and contain no duplicates")
        for name in files:
            relative_name(name)
        if not cases or len({c["name"] for c in cases}) != len(cases):
            raise ValueError("empty or duplicate cases")
        for case in cases:
            if "/" in relative_name(case["name"]):
                raise ValueError("case name must be a single path component")
            if not math.isfinite(case["stop"]) or case["stop"] <= 0 or not case["signals"]:
                raise ValueError("invalid transient observation contract")
            for name in case.get("support", {}):
                relative_name(name)
                if name in files or name.split("/")[0] in {"tb.scs", "stdout.log", "spectre.log", "psf"}:
                    raise ValueError("support overlaps a protected asset")
        if case_name is not None:
            cases = [case for case in cases if case["name"] == case_name]
            if not cases:
                raise ValueError("unknown case selector")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.update(status="checker_error", reason=f"invalid task package: {exc}")
        return write_report(output, report)
    sources = {}
    try:
        bundle = candidate.parent.resolve()
        for name in files:
            path = candidate if name == "dut.va" else candidate.parent / name
            linked = any((bundle / Path(*Path(name).parts[:i])).is_symlink()
                         for i in range(1, len(Path(name).parts) + 1))
            if not path.is_file() or linked or not path.resolve().is_relative_to(bundle):
                raise ValueError("missing or linked candidate file: " + name)
            sources[name] = path.read_bytes()
    except (OSError, ValueError) as exc:
        report.update(status="submission_contract_violation", reward=0, reason=str(exc))
        return write_report(output, report)
    report["candidate_files"] = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    # Existing Harness validates this primary-file field before projecting scores.
    report["candidate_sha256"] = report["candidate_files"]["dut.va"]
    report["checker_files"] = {p.name: digest(p) for p in tests.glob("*.py")}
    if (tests / "verify.py").is_file():
        report["checker_sha256"] = digest(tests / "verify.py")
    binary = os.environ.get("SPECTRE", "spectre")
    if not shutil.which(binary):
        report["reason"] = "fixed Spectre backend is unavailable"
        return write_report(output, report)
    try:
        version = subprocess.run([binary, "-W"], capture_output=True, text=True, timeout=30)
        report["spectre_version"] = version.stdout + version.stderr
        if version.returncode or not report["spectre_version"].strip():
            raise ValueError("backend version probe failed")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        report["reason"] = str(exc)
        return write_report(output, report)
    for case in cases:
        work = output / case["name"]
        work.mkdir()
        for name, data in sources.items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for name, data in case.get("support", {}).items():
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(data)
        (work / "tb.scs").write_text(case["netlist"])
        record = {"name": case["name"], "netlist_sha256": digest(work / "tb.scs"),
                  "candidate_files": dict(report["candidate_files"]),
                  "support_sha256": {name: digest(work / name) for name in case.get("support", {})}}
        argv = [binary, "-64", "tb.scs", "+log", "spectre.log", "-format", "psfascii",
                "-raw", "psf", "+lqtimeout", "5", "+mt=1"]
        record["argv"] = argv
        started = time.monotonic()
        try:
            with (work / "stdout.log").open("w") as stream:
                run = subprocess.run(argv, cwd=work, stdout=stream, stderr=subprocess.STDOUT,
                                     timeout=case.get("timeout_s", 120))
            record.update(returncode=run.returncode, elapsed_s=time.monotonic() - started,
                          log_tail=(work / "stdout.log").read_text(errors="replace")[-5000:])
            protected = {**record["candidate_files"], **record["support_sha256"],
                         "tb.scs": record["netlist_sha256"]}
            changed = [name for name, expected in protected.items()
                       if not (work / name).is_file() or (work / name).is_symlink()
                       or digest(work / name) != expected]
            if changed:
                record.update(status="evidence_error", reason="executed assets changed", changed=changed)
            elif run.returncode:
                record.update(status="execution_error", reason="backend failure requires diagnosis")
            else:
                waveform = work / "psf/tran.tran.tran"
                try:
                    rows = read_psf(waveform)
                    validate_rows(rows, case)
                except (OSError, ValueError, KeyError) as exc:
                    record.update(status="evidence_error", reason=str(exc))
                else:
                    verdict = evaluate(rows, case, work)
                    if not isinstance(verdict, dict) or type(verdict.get("passed")) is not bool:
                        raise ValueError("checker must return a boolean passed field")
                    record.update(verdict)
                    record["status"] = verdict.get("status", "graded")
                    record.update(waveform_sha256=digest(waveform), waveform_rows=len(rows))
        except subprocess.TimeoutExpired:
            record.update(status="execution_error", reason="backend timeout requires diagnosis",
                          elapsed_s=time.monotonic() - started)
        except Exception as exc:
            record.update(status="checker_error", reason=f"{type(exc).__name__}: {exc}")
        report["cases"].append(record)
    if all(row["status"] == "graded" for row in report["cases"]):
        report.update(status="completed", reward=int(all(row["passed"] for row in report["cases"])))
    else:
        report["reason"] = "one or more cases lack a valid independent circuit verdict"
    return write_report(output, report)


def main(evaluate):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tests", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--case")
    args = parser.parse_args()
    report = verify(args.candidate, args.output, args.tests, evaluate, args.case)
    print(json.dumps({"status": report["status"], "reward": report["reward"]}))
    raise SystemExit(0 if report["reward"] is not None else 2)

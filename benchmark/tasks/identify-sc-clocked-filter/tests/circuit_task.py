"""Common Spectre execution boundary for circuit engineering tasks.

Task code supplies evaluate(rows, case, work); this module does not define truth.
Remote scheduling, resource enforcement and archival belong to circuit harness.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _legacy_module():
    # Reuse the already maintained byte lexer and PSF reader, with an exact copy
    # included in each portable package. No candidate-controlled import path.
    path = Path(__file__).with_name("adc_linearity.py")
    spec = importlib.util.spec_from_file_location("_circuit_adc_primitives", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative_name(name):
    if (not isinstance(name, str) or not name or "\\" in name or
            Path(name).is_absolute() or any(p in ("", ".", "..") for p in name.split("/")) or
            not re.fullmatch(r"[A-Za-z0-9_./-]+", name)):
        raise ValueError("unsafe relative filename")
    return name


def prepare_source(source, candidate_files, output_files, output_directory):
    """Validate active I/O and relocate only declared literal output paths."""
    tokens = _legacy_module().source_tokens(source)
    includes = {b'"disciplines.vams"', b'"constants.vams"'}
    includes.update(json.dumps(relative_name(name)).encode() for name in candidate_files)
    outputs = {json.dumps("/work/output/" + relative_name(name)).encode(): name for name in output_files}
    spans = []
    i = 0
    while i < len(tokens):
        kind, value, start, end = tokens[i]
        if value == b"`":
            if i + 2 >= len(tokens) or tokens[i + 1][1] != b"include" or tokens[i + 2][1] not in includes:
                raise ValueError("only standard or declared candidate includes are supported; macros are prohibited")
            i += 3
            continue
        if kind == "identifier" and value == b"$fopen":
            call = tokens[i + 1:i + 6]
            if (len(call) != 5 or [t[1] for t in call][::2] != [b"(", b",", b")"] or
                    call[1][1] not in outputs or call[3][1] != b'"w"'):
                raise ValueError("only literal write-mode opens of declared result files are permitted")
            replacement = json.dumps(str(output_directory.resolve() / outputs[call[1][1]])).encode()
            spans.append((call[1][2], call[1][3], replacement))
            i += 6
            continue
        if kind == "identifier" and (value in {b"$system", b"$fscanf", b"$fgets", b"$fread", b"$getenv", b"$popen"} or value.startswith(b"$readmem")):
            raise ValueError("external reads and system calls are prohibited")
        i += 1
    pieces, cursor, edits = [], 0, []
    for start, end, replacement in spans:
        pieces.extend([source[cursor:start], replacement])
        edits.append({"start": start, "end": end, "original_literal": source[start:end].decode(), "executed_literal": replacement.decode()})
        cursor = end
    pieces.append(source[cursor:])
    executed = b"".join(pieces)
    # Restore using the actual execution bytes, to check untouched byte regions.
    restored, old_cursor, new_cursor = [], 0, 0
    for edit in edits:
        count = edit["start"] - old_cursor
        restored.append(executed[new_cursor:new_cursor + count])
        new_cursor += count
        replacement = edit["executed_literal"].encode()
        if executed[new_cursor:new_cursor + len(replacement)] != replacement:
            raise ValueError("path relocation mismatch")
        restored.append(edit["original_literal"].encode())
        new_cursor += len(replacement)
        old_cursor = edit["end"]
    restored.append(executed[new_cursor:])
    if b"".join(restored) != source:
        raise ValueError("path relocation changed other bytes")
    return executed, {"version": "circuit-output-paths-v1", "edits": edits, "inverse_verified": True}


def validate_rows(rows, case):
    """Reject incomplete numerical evidence before calling a task's grader."""
    if len(rows) < 2:
        raise ValueError("missing waveform")
    names = {"time", *case["signals"]}
    if any(not names.issubset(row) for row in rows):
        raise ValueError("missing required signals")
    if any(not math.isfinite(value) for row in rows for value in row.values()):
        raise ValueError("non-finite waveform")
    times = [row["time"] for row in rows]
    if any(a > b for a, b in zip(times, times[1:])):
        raise ValueError("unordered waveform")
    tolerance = max(1e-15, abs(case["stop"]) * 1e-8)
    if abs(times[0]) > tolerance or abs(times[-1] - case["stop"]) > tolerance:
        raise ValueError("incomplete transient interval")


def verify(candidate, output, tests, evaluate, case_name=None):
    """Run a frozen submission; only completed numerical checks yield a score."""
    candidate, output, tests = map(Path, (candidate, output, tests))
    if candidate.is_symlink():
        raise ValueError("candidate must not be a symlink")
    candidate = candidate.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or any(output.iterdir()):
        raise FileExistsError("verification output must be a new empty directory")
    cases_path, contract_path = tests / "cases.json", tests / "contract.json"
    cases = json.loads(cases_path.read_text())
    contract = json.loads(contract_path.read_text())
    if not cases or len({c["name"] for c in cases}) != len(cases):
        raise ValueError("empty or duplicate case list")
    if case_name is not None:
        cases = [c for c in cases if c["name"] == case_name]
        if not cases:
            raise ValueError("unknown case selector")
    files = contract.get("candidate_files", ["dut.va"])
    outputs = contract.get("output_files", [])
    if (not files or files[0] != "dut.va" or len(set(files)) != len(files) or
            len(set(outputs)) != len(outputs)):
        raise ValueError("invalid candidate/output inventory")
    for name in files + outputs:
        relative_name(name)
    sources = {}
    report = {"candidate_sha256": sha(candidate), "cases_sha256": sha(cases_path),
              "contract_sha256": sha(contract_path), "checker_sha256": sha(tests / "verify.py") if (tests / "verify.py").exists() else sha(__file__),
              "runtime_sha256": sha(__file__), "parser_sha256": sha(Path(__file__).with_name("adc_linearity.py")), "cases": []}
    try:
        for name in files:
            path = candidate if name == "dut.va" else candidate.parent / name
            if not path.is_file() or path.is_symlink() or path.resolve() != path.absolute():
                raise ValueError("missing or linked candidate file: " + name)
            sources[name] = path.read_bytes()
            prepare_source(sources[name], files, outputs, output / "validation-only")
    except (ValueError, OSError) as exc:
        report.update(status="submission_contract_violation", reward=0, reason=str(exc))
        return write_report(output, report)
    report["candidate_files"] = {name: hashlib.sha256(data).hexdigest() for name, data in sources.items()}
    binary = os.environ.get("SPECTRE", "spectre")
    if not shutil.which(binary):
        report.update(status="infrastructure_error", reward=None, reason="Spectre unavailable")
        return write_report(output, report)
    try:
        version = subprocess.run([binary, "-W"], capture_output=True, text=True, timeout=30)
        report["spectre_version"] = version.stdout + version.stderr
        report["spectre_version_returncode"] = version.returncode
        if version.returncode or not report["spectre_version"].strip():
            raise ValueError("Spectre version probe failed")
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        report.update(status="infrastructure_error", reward=None, reason=str(exc))
        return write_report(output, report)
    for case in cases:
        name = relative_name(case["name"])
        if "/" in name:
            raise ValueError("case names cannot contain directories")
        work = output / name
        work.mkdir()
        results = work / "output"
        results.mkdir()
        for name in outputs:
            (results / name).parent.mkdir(parents=True, exist_ok=True)
        source_identity = {}
        for name, source in sources.items():
            original = work / "original" / name
            original.parent.mkdir(parents=True, exist_ok=True)
            original.write_bytes(source)
            executed, receipt = prepare_source(source, files, outputs, results)
            path = work / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(executed)
            source_identity[name] = {"original_sha256": sha(original), "executed_sha256": sha(path), "output_translation": receipt}
        for name, text in case.get("support", {}).items():
            relative_name(name)
            path = work / name
            if path.exists() or name.split("/")[0] in {"original", "output", "psf"} or name in {"tb.scs", "stdout.log", "spectre.log"}:
                raise ValueError("support file overlaps protected path")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        (work / "tb.scs").write_text(case["netlist"])
        argv = [binary, "-64", "tb.scs", "+log", "spectre.log", "-format", "psfascii", "-raw", "psf", "+lqtimeout", "5", "+mt=1"]
        record = {"name": case["name"], "argv": argv, "candidate_files": source_identity, "netlist_sha256": sha(work / "tb.scs")}
        started = time.monotonic()
        try:
            with (work / "stdout.log").open("w") as stream:
                run = subprocess.run(argv, cwd=work, stdout=stream, stderr=subprocess.STDOUT, timeout=90)
            log = (work / "stdout.log").read_text(errors="replace")
            record.update(returncode=run.returncode, elapsed_s=time.monotonic() - started, log_tail=log[-5000:])
            # Candidate-controlled $display/$strobe text is not evidence of an
            # infrastructure outage. The harness checks the license separately.
            if run.returncode:
                record.update(status="submission_failure", failure_kind="compile_or_simulation_failure", passed=False)
            else:
                waveform = work / "psf/tran.tran.tran"
                try:
                    rows = _legacy_module().read_psf(waveform)
                    validate_rows(rows, case)
                except (OSError, ValueError, KeyError) as exc:
                    record.update(status="submission_failure", failure_kind="invalid_waveform", passed=False,
                                  error=f"{type(exc).__name__}: {exc}")
                    report["cases"].append(record)
                    continue
                verdict = evaluate(rows, case, work)
                if not isinstance(verdict, dict) or type(verdict.get("passed")) is not bool:
                    raise ValueError("grader must return a boolean passed field")
                if verdict.get("status") in {"environment_error", "infrastructure_error", "checker_error"}:
                    record.update(verdict)
                else:
                    record.update(verdict)
                    record["status"] = "graded"
                record["waveform_sha256"] = sha(waveform)
                record["waveform_rows"] = len(rows)
        except subprocess.TimeoutExpired:
            record.update(status="submission_failure", failure_kind="simulation_timeout", passed=False, elapsed_s=time.monotonic() - started)
        except Exception as exc:
            record.update(status="checker_error", passed=False, error=f"{type(exc).__name__}: {exc}")
        report["cases"].append(record)
    complete = all(record["status"] in {"graded", "submission_failure"} for record in report["cases"])
    report.update(status="completed" if complete else "infrastructure_error",
                  reward=int(all(record["passed"] for record in report["cases"])) if complete else None)
    if complete and any(record["status"] == "submission_failure" for record in report["cases"]):
        # The harness has an explicit zero-score submission-contract category.
        # Executable, complete Verilog-A output is part of that contract. Keep
        # per-case failures distinct from numerical grading for calibration.
        report.update(status="submission_contract_violation", reason="submission did not produce a complete executable simulation")
    return write_report(output, report)


def write_report(output, report):
    (output / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    if report["reward"] is not None:
        (output / "reward.txt").write_text(str(report["reward"]) + "\n")
    return report


def main(evaluate):
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case")
    parser.add_argument("--tests", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = verify(args.candidate, args.output.absolute(), args.tests.resolve(), evaluate, args.case)
    print(json.dumps({"status": result["status"], "reward": result["reward"]}))
    raise SystemExit(0 if result["reward"] is not None else 2)

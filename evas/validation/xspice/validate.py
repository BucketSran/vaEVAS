"""Run the public compiler/build CLI and frozen Spectre/rollback contracts.

Use --reference to the retained native Spectre batch. No remote jobs are
launched, and copied references are never counted as new simulator runs.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
from cases import CASES, PROFILES, TOL, decks
from reference import expected
from check import read_ng, read_spectre, grade, compare
from rollback import analyze_extras
from native_reference import load_reference
from pilot_identity import write_identity
from trace_files import compress_traces

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "evas/examples/xspice/sample_hold.va"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(command, cwd, log, timeout):
    start = time.monotonic()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    with log.open("x") as f:
        try:
            p = subprocess.run(
                list(map(str, command)),
                cwd=cwd,
                stdout=f,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                env=dict(os.environ, OMP_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1"),
            )
            code = p.returncode
            timed = False
        except subprocess.TimeoutExpired:
            code = -9
            timed = True
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    return {
        "command": list(map(str, command)),
        "cwd": str(cwd),
        "exit_code": code,
        "timed_out": timed,
        "wall_s": time.monotonic() - start,
        "user_s": after.ru_utime - before.ru_utime,
        "system_s": after.ru_stime - before.ru_stime,
    }


def suite(output, sdk, reference, python=sys.executable):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    ref = Path(reference).resolve()
    sdk = Path(sdk).resolve()
    rows = {}
    pairs = {}
    libs = {}
    extra = {}
    contract = {
        "cases": CASES,
        "profiles": PROFILES,
        "tolerances": TOL,
        "source_sha256": sha(SOURCE),
        "reference": str(ref),
        "native_runs": "ngspice only; existing same-source Spectre executions reused",
    }
    (output / "contract.json").write_text(json.dumps(contract, indent=2) + "\n")
    answers = {k: expected(v) for k, v in CASES.items()}
    (output / "expected.json").write_text(json.dumps(answers, indent=2) + "\n")
    refs = {}
    for case, cfg in CASES.items():
        for pn in PROFILES:
            key = case + "-" + pn
            _, deck = decks(cfg, PROFILES[pn], Path("unused"))
            refs[key] = load_reference(ref / "spectre" / key, SOURCE.read_bytes(), deck)
    (output / "references.json").write_text(json.dumps(refs, indent=2) + "\n")
    commands = []
    for case, cfg in CASES.items():
        artifact = output / "models" / case
        artifact.parent.mkdir(exist_ok=True)
        cmd = [
            python,
            "-B",
            "-m",
            "evas",
            "xspice",
            "compile",
            SOURCE,
            "-o",
            artifact,
            "--model-name",
            "sample_hold_cm",
            "--test-hooks",
        ]
        for k, v in cfg.items():
            if k not in ("feedback", "clock_feedback"):
                cmd += ["--parameter", k + "=" + str(v)]
        r = run(cmd, ROOT, output / (case + "-compile.log"), 20)
        commands.append(r)
        if r["exit_code"]:
            raise RuntimeError("public compilation failed: " + case)
        r = run(
            [python, "-B", "-m", "evas", "xspice", "build", artifact, "--sdk", sdk],
            ROOT,
            output / (case + "-build.log"),
            120,
        )
        commands.append(r)
        if r["exit_code"]:
            raise RuntimeError("native SDK build failed: " + case)
        build = json.loads((artifact / "native/build.json").read_text())
        libs[case] = Path(build["library"])
    selection = [
        (case, pn, case, False, False, 0.0) for case in CASES for pn in PROFILES
    ]
    for label, at in [("cross", 0.0), ("timer", 1.08e-6), ("transition", 1.045e-6)]:
        for bad in (False, True):
            name = "rollback_" + label + ("_bad" if bad else "")
            case = "clock_feedback" if label == "cross" else "timer_after"
            selection.append((name, "tight", case, True, bad, at))
            extra[name + "-tight"] = {
                "case": case,
                "negative_control": bad,
                "injection_time": at,
                "kind": label,
            }
    (output / "extras.json").write_text(json.dumps(extra, indent=2) + "\n")
    for name, pn, case, inject, bad, at in selection:
        key = name + "-" + pn
        d = output / "ngspice" / key
        d.mkdir(parents=True)
        ng, sp = decks(CASES[case], PROFILES[pn], libs[case], inject, bad, at)
        (d / "tb.cir").write_text(ng)
        (d / "model.cm").symlink_to(libs[case])
        (d / ".spiceinit").write_text("codemodel model.cm\n")
        started = {
            "library": str(libs[case]),
            "library_sha256": sha(libs[case]),
            "deck_sha256": sha(d / "tb.cir"),
        }
        (d / "STARTED.json").write_text(json.dumps(started, indent=2) + "\n")
        r = run(
            [
                json.loads((libs[case].parent / "build.json").read_text())["ngspice"],
                "-b",
                "tb.cir",
            ],
            d,
            d / "stdout.log",
            30,
        )
        (d / "result.json").write_text(json.dumps({**started, **r}, indent=2) + "\n")
        if r["exit_code"] or not (d / "wave.raw").is_file():
            raise RuntimeError("ngspice execution failed: " + key)
        if inject:
            continue
        native = ref / "spectre" / key
        raw = native / "psf/tran.tran.tran"
        v = read_ng(d / "wave.raw")
        s = read_spectre(raw)
        rows["ngspice/" + key] = grade(v, answers[case], CASES[case])
        rows["spectre/" + key] = grade(s, answers[case], CASES[case])
        pairs[key] = compare(v, s)
    (output / "references.json").write_text(json.dumps(refs, indent=2) + "\n")
    (output / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
    rb = analyze_extras(output)
    result = {
        "passed": all(x["passed"] for x in [*rows.values(), *pairs.values()])
        and rb["passed"],
        "physical": rows,
        "pairs": pairs,
        "rollback_passed": rb["passed"],
        "new_ngspice_circuit_runs": len(selection),
        "new_ngspice_build_probes": len(libs),
        "new_spectre_runs": 0,
    }
    (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    for directory in (output / "ngspice").iterdir():
        compress_traces(directory)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--sdk", type=Path, required=True)
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--python", default=sys.executable)
    a = p.parse_args()
    r = suite(a.output, a.sdk, a.reference, a.python)
    print(
        json.dumps(
            {k: v for k, v in r.items() if k not in ("physical", "pairs")}, indent=2
        )
    )
    sys.exit(0 if r["passed"] else 1)

"""Continuous tanh, actual Newton feedback and independent derivative control."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from validate import ROOT, run, sha
from check import read_ng
from r53_cases import SOURCES, FILES
from r53_reference import score_tanh, score_tanh_derivatives
from trace_files import retained_traces
from prepare_reference import prepare_reference
from pilot_identity import write_identity

DRIVE = [(0.0, 0.47), (4e-9, 0.47), (8e-9, 0.53),
         (12e-9, 0.53), (16e-9, 0.47), (20e-9, 0.47)]


def circuit(model, feedback):
    text = "r53 tanh, differential inputs and resistive Newton feedback\n"
    text += "vdrive drive 0 pwl(" + " ".join(f"{t} {v}" for t, v in DRIVE) + ")\nvref ref 0 0.5\n"
    text += f'.model mo {model}(evas_trace="trace-open.csv")\nao drive ref open mo\nrload open 0 2k\n'
    if feedback:
        text += f'.model mf {model}(evas_trace="trace-feedback.csv")\nefb sigin drive out 0 -0.01\naf sigin ref out mf\nrfeedback out 0 1k\n'
    text += ".options method=gear maxord=2 reltol=1e-10 vntol=1e-13 abstol=1e-16\n.save v(drive) v(ref) v(open)"
    if feedback:
        text += " v(sigin) v(out)"
    return text + "\n.tran 10p 20n 0 10p\n.control\nset filetype=ascii\nset numdgt=17\nrun\nwrite wave.raw all\nquit\n.endc\n.end\n"


def validate(output, sdk):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    artifact = output / "model"
    r = run([sys.executable, "-B", "-m", "evas", "xspice", "compile", SOURCES / FILES["124"],
             "-o", artifact, "--model-name", "r53_tanh"], ROOT, output / "compile.log", 20)
    if r["exit_code"]:
        raise RuntimeError(r)
    results = {}
    for mode in ("normal", "zero-derivative-control"):
        generated = artifact
        if mode != "normal":
            generated = output / "mutant-model"
            shutil.copytree(artifact, generated, ignore=shutil.ignore_patterns("native"))
            source = generated / "cfunc.mod"
            text = source.read_text()
            assert text.count("(1-r.v*r.v)*a.d[j]") == 1
            before = sha(source)
            source.write_text(text.replace("(1-r.v*r.v)*a.d[j]", "0.0*a.d[j]"))
            manifest = json.loads((generated / "manifest.json").read_text())
            manifest["files"]["cfunc.mod"] = sha(source)
            (generated / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
            (generated / "mutation.json").write_text(json.dumps({"negative_control": True,
                "change": "zero tanh Jacobian while preserving voltage relation",
                "original_sha256": before, "mutated_sha256": sha(source)}, indent=2)+"\n")
        r = run([sys.executable, "-B", "-m", "evas", "xspice", "build", generated,
                 "--sdk", Path(sdk).resolve()], ROOT, output / (mode + "-build.log"), 120)
        if r["exit_code"]:
            results[mode] = {"passed": False, "build": r}
            continue
        build = json.loads((generated / "native/build.json").read_text())
        d = output / mode
        d.mkdir()
        (d / "model.cm").symlink_to(build["library"])
        (d / ".spiceinit").write_text("codemodel model.cm\n")
        text = circuit("r53_tanh", mode == "normal")
        (d / "tb.cir").write_text(text)
        (d / "contract.json").write_text(json.dumps({"drive": DRIVE,
            "stop": 20e-9, "voltage_budget_V": 20e-6, "derivative_budget": 1e-6,
            "feedback": 0.01 if mode == "normal" else None}, indent=2) + "\n")
        if mode == "normal":
            prepare_reference(d, [artifact])
        with retained_traces(d):
            r = run([build["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 30)
            (d / "execution.json").write_text(json.dumps(r, indent=2)+"\n")
            if r["exit_code"] or not (d / "wave.raw").exists():
                results[mode] = {"passed": False, "execution": r}
                continue
            physical = score_tanh(read_ng(d / "wave.raw"), DRIVE, mode == "normal")
            derivatives = score_tanh_derivatives(d / "trace-open.csv")
            negative = mode != "normal"
            passed = physical["passed"] and (not derivatives["passed"] if negative else derivatives["passed"])
            results[mode] = {"passed": passed, "negative_control": negative,
                             "physical": physical, "derivatives": derivatives}
            (d / "analysis.json").write_text(json.dumps(results[mode], indent=2)+"\n")
            print(mode, passed, physical, derivatives, flush=True)
    final = {"passed": len(results) == 2 and all(r["passed"] for r in results.values()),
             "runs": results, "new_spectre_runs": 0}
    (output / "analysis.json").write_text(json.dumps(final, indent=2)+"\n")
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--sdk", required=True)
    a = p.parse_args()
    result = validate(a.output, a.sdk)
    sys.exit(0 if result["passed"] else 1)

"""Independent actual clock/RC/sample composition, with each owner's rollback."""

import argparse
import json
from pathlib import Path
import sys

from validate import ROOT, run, sha
from check import read_ng
from rollback import check as rollback_check
from r53_cases import SOURCES, FILES, chain, finish
from r53_reference import score_wave, score_states
from trace_files import retained_traces
from prepare_reference import prepare_reference
from pilot_identity import write_identity


def validate(output, sdk):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    builds = {}
    for fid in ("068", "104"):
        artifact = output / ("model-" + fid)
        name = "chain_" + fid
        compile_run = run([sys.executable, "-B", "-m", "evas", "xspice", "compile",
            SOURCES / FILES[fid], "-o", artifact, "--model-name", name, "--test-hooks"],
            ROOT, output / (fid + "-compile.log"), 20)
        if compile_run["exit_code"]:
            raise RuntimeError(compile_run)
        build_run = run([sys.executable, "-B", "-m", "evas", "xspice", "build", artifact,
            "--sdk", Path(sdk).resolve()], ROOT, output / (fid + "-build.log"), 120)
        if build_run["exit_code"]:
            raise RuntimeError(build_run)
        builds[fid] = json.loads((artifact / "native/build.json").read_text())
    results = {}
    for mode in ("normal", "retry-clock", "leak-clock", "retry-sample", "leak-sample"):
        d = output / mode
        d.mkdir()
        startup = ""
        for fid, build in builds.items():
            (d / (fid + ".cm")).symlink_to(build["library"])
            startup += "codemodel " + fid + ".cm\n"
        (d / ".spiceinit").write_text(startup)
        text, cfg = chain("chain_068", "chain_104", mode)
        (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
        (d / "tb.cir").write_text(finish(text, cfg))
        if mode == "normal":
            prepare_reference(d, [output / "model-068", output / "model-104"])
        with retained_traces(d):
            result = run([builds["068"]["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 30)
            (d / "execution.json").write_text(json.dumps({**result, "deck_sha256": sha(d / "tb.cir")}, indent=2) + "\n")
            if result["exit_code"] or not (d / "wave.raw").exists():
                results[mode] = {"passed": False, "execution": result}
                continue
            physical = score_wave(read_ng(d / "wave.raw"), cfg)
            states = {inst: score_states(d / ("trace-" + inst + ".csv"), s["events"], s["indices"], s["initial"])
                      for inst, s in cfg["states"].items()}
            rb = None
            if mode != "normal":
                owner = mode.split("-")[1]
                (d / "trace.csv").symlink_to("trace-" + owner + ".csv")
                rb = rollback_check(d, "timer" if owner == "clock" else "cross")
            negative = mode.startswith("leak")
            passed = physical["passed"] and all(s["passed"] for s in states.values())
            passed = not rb["passed"] if negative else passed and (rb is None or rb["passed"])
            results[mode] = {"passed": passed, "negative_control": negative,
                             "physical": physical, "states": states, "rollback": rb}
            (d / "analysis.json").write_text(json.dumps(results[mode], indent=2) + "\n")
            print(mode, passed, physical["errors"], {i:s["errors"] for i,s in states.items()}, flush=True)
    final = {"passed": len(results) == 5 and all(r["passed"] for r in results.values()),
             "runs": results, "new_spectre_runs": 0}
    (output / "analysis.json").write_text(json.dumps(final, indent=2) + "\n")
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--sdk", required=True)
    a = p.parse_args()
    result = validate(a.output, a.sdk)
    sys.exit(0 if result["passed"] else 1)

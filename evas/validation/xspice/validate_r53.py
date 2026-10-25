"""Run selected bounded r53 sources through public CLI and actual ngspice47.

This local suite starts no remote reference jobs. Historical r53 checker passes
are recorded separately; this suite adds circuit, lifecycle and state checks.
"""

import argparse
import json
from pathlib import Path
import shutil
import sys

from validate import run, ROOT, sha
from check import read_ng
from rollback import check as rollback_check
from r53_cases import SOURCES, FILES, sampler, counter, clock, finish
from r53_reference import score_wave, score_states
from trace_files import retained_traces
from prepare_reference import prepare_reference
from pilot_identity import write_identity


def validate(output, sdk, families, run_timeout=120):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    results = {}
    for fid in families:
        source = SOURCES / FILES[fid]
        artifact = output / ("model-" + fid)
        name = "r53_" + fid
        cmd = [sys.executable, "-B", "-m", "evas", "xspice", "compile", source,
               "-o", artifact, "--model-name", name, "--test-hooks"]
        receipt = run(cmd, ROOT, output / (fid + "-compile.log"), 20)
        if receipt["exit_code"]:
            results[fid] = {"passed": False, "compile": receipt}
            continue
        receipt = run([sys.executable, "-B", "-m", "evas", "xspice", "build", artifact,
                       "--sdk", Path(sdk).resolve()], ROOT, output / (fid + "-build.log"), 120)
        if receipt["exit_code"]:
            results[fid] = {"passed": False, "build": receipt}
            continue
        build = json.loads((artifact / "native/build.json").read_text())
        rows = {}
        for mode in ("normal", "retry", "leak"):
            d = output / (fid + "-" + mode)
            d.mkdir()
            (d / "model.cm").symlink_to(build["library"])
            (d / ".spiceinit").write_text("codemodel model.cm\n")
            factory = {"115": counter, "068": clock}.get(fid, sampler)
            text, cfg = factory(fid, name, mode != "normal", mode == "leak")
            (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
            (d / "tb.cir").write_text(finish(text, cfg))
            if mode == "normal":
                prepare_reference(d, [artifact])
            with retained_traces(d):
                r = run([build["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", run_timeout)
                (d / "execution.json").write_text(json.dumps({**r, "deck_sha256": sha(d / "tb.cir"), "source_sha256": sha(source)}, indent=2)+"\n")
                if r["exit_code"] or not (d / "wave.raw").exists():
                    rows[mode] = {"passed": False, "execution": r}
                    continue
                wave = read_ng(d / "wave.raw")
                for node, (positive, negative) in cfg.get("differences", {}).items():
                    wave[node] = [a - b for a, b in zip(wave[positive], wave[negative])]
                physical = score_wave(wave, cfg)
                states = {inst: score_states(d / ("trace-" + inst + ".csv"), spec["events"], spec["indices"], spec["initial"], spec.get("integer", False))
                          for inst, spec in cfg["states"].items()}
                rb = None
                if mode != "normal":
                    # Reuse complete-frame lineage and first-retry invariants.
                    (d / "trace.csv").symlink_to("trace-a.csv")
                    rb = rollback_check(d, cfg.get("rollback_kind", "cross"))
                passed = physical["passed"] and all(s["passed"] for s in states.values())
                passed = (not rb["passed"]) if mode == "leak" else passed and (rb is None or rb["passed"])
                rows[mode] = {"passed": passed, "negative_control": mode == "leak", "physical": physical, "states": states, "rollback": rb}
                (d / "analysis.json").write_text(json.dumps(rows[mode], indent=2) + "\n")
                print(fid, mode, passed, physical["errors"], {i:s["errors"] for i,s in states.items()}, flush=True)
        results[fid] = {"passed": all(r["passed"] for r in rows.values()) and len(rows) == 3, "runs": rows}
        (output / "analysis.json").write_text(json.dumps({"passed": all(r["passed"] for r in results.values()), "families": results}, indent=2) + "\n")
    final = {"passed": all(r["passed"] for r in results.values()), "families": results, "new_spectre_runs": 0}
    (output / "analysis.json").write_text(json.dumps(final, indent=2)+"\n")
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    p.add_argument("--sdk", required=True)
    p.add_argument("--families", default="104,210,148")
    p.add_argument("--run-timeout", type=float, default=120, help="seconds per ngspice circuit")
    a = p.parse_args()
    if a.run_timeout <= 0:
        p.error("--run-timeout must be positive")
    r = validate(a.output, a.sdk, a.families.split(","), a.run_timeout)
    print("r53 scoped pilot", r["passed"])
    sys.exit(0 if r["passed"] else 1)

"""P0 installed public compilation, real host capture/RC and rollback checks."""

import argparse
import json
from pathlib import Path
import shutil
import sys

from alias_cases import CASES, FILES, SOURCES, configuration, deck
from alias_reference import score_wave, ng_state, pair
from check import read_ng
from pilot_identity import write_identity
from prepare_reference import prepare_reference
from rollback import check as rollback_check
from trace_files import retained_traces
from validate import ROOT, run, sha


def validate(output, sdk):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    builds = {}
    for kind, filename in FILES.items():
        artifact = output / ("model-" + kind)
        for command, label, timeout in [
            ([sys.executable, "-B", "-m", "evas", "xspice", "compile", SOURCES / filename,
              "-o", artifact, "--model-name", "p0_" + kind, "--test-hooks"], "compile", 20),
            ([sys.executable, "-B", "-m", "evas", "xspice", "build", artifact,
              "--sdk", Path(sdk).resolve()], "build", 120),
        ]:
            receipt = run(command, ROOT, output / (kind + "-" + label + ".log"), timeout)
            if receipt["exit_code"]:
                raise RuntimeError(receipt)
        ir = json.loads((artifact / "ir.json").read_text())
        if [s["name"] for s in ir["states"]] != ["q"]:
            raise ValueError("P0 trace observes the single original q state")
        builds[kind] = json.loads((artifact / "native/build.json").read_text())
    recipes = {case: configuration(case) for case in CASES}
    (output / "recipes.json").write_text(json.dumps(recipes, indent=2) + "\n")
    results = {}
    for case, cfg in recipes.items():
        build = builds[cfg["source"]]
        modes = ("normal", "retry", "leak", "dense") if case == "ramp" else ("normal",)
        rows = {}
        for mode in modes:
            d = output / (case + "-" + mode)
            d.mkdir()
            (d / "model.cm").symlink_to(build["library"])
            (d / ".spiceinit").write_text("codemodel model.cm\n")
            (d / "tb.cir").write_text(deck(cfg, "p0_" + cfg["source"], mode))
            (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
            if mode == "normal":
                reference = prepare_reference(d, [output / ("model-" + cfg["source"])])
                native = output / "spectre" / case
                shutil.copytree(reference, native)
                text = (native / "tb.scs").read_text().replace(
                    "iabstol=1e-16", 'iabstol=1e-16 precision="%.17g" saveahdlvars=all')
                text += "save " + " ".join("x" + i + ":q" for i in cfg["instances"]) + "\n"
                (native / "tb.scs").write_text(text)
                shutil.copy2(d / "contract.json", native / "contract.json")
            with retained_traces(d):
                receipt = run([build["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 60)
                (d / "execution.json").write_text(json.dumps({**receipt,
                    "source_sha256": sha(SOURCES / FILES[cfg["source"]]),
                    "deck_sha256": sha(d / "tb.cir")}, indent=2) + "\n")
                if receipt["exit_code"] or not (d / "wave.raw").is_file():
                    rows[mode] = {"passed": False, "execution": receipt}
                    continue
                wave = read_ng(d / "wave.raw")
                physical = score_wave(wave, cfg)
                states = {i: ng_state(d / ("trace-" + i + ".csv"), s, cfg["budgets"])
                          for i, s in cfg["instances"].items()}
                rb = paired = None
                if mode in ("retry", "leak"):
                    (d / "trace.csv").symlink_to("trace-a.csv")
                    rb = rollback_check(d, "cross")
                if mode in ("retry", "dense"):
                    normal = read_ng(output / (case + "-normal/wave.raw"))
                    paired = pair(wave, normal, cfg, cfg["budgets"]["retry_pair_V"] if mode == "retry" else None)
                passed = physical["passed"] and all(s["passed"] for s in states.values())
                passed = (not rb["passed"]) if mode == "leak" else passed and (rb is None or rb["passed"]) and (paired is None or paired["passed"])
                rows[mode] = {"passed": passed, "negative_control": mode == "leak", "physical": physical,
                              "states": states, "rollback": rb, "pair_with_normal": paired}
                (d / "analysis.json").write_text(json.dumps(rows[mode], indent=2, allow_nan=False) + "\n")
                print(case, mode, passed, physical["errors"], flush=True)
        results[case] = {"passed": len(rows) == len(modes) and all(r["passed"] for r in rows.values()), "runs": rows}
        (output / "analysis.json").write_text(json.dumps({"passed": all(r["passed"] for r in results.values()), "cases": results}, indent=2, allow_nan=False) + "\n")
    final = {"passed": len(results) == len(CASES) and all(r["passed"] for r in results.values()),
             "cases": results, "new_ngspice_circuit_runs": 8, "new_ngspice_build_probes": 3, "new_spectre_runs": 0}
    (output / "analysis.json").write_text(json.dumps(final, indent=2, allow_nan=False) + "\n")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sdk", required=True)
    args = parser.parse_args()
    result = validate(args.output, args.sdk)
    raise SystemExit(0 if result["passed"] else 1)

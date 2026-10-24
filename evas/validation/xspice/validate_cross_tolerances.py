"""Native regression: a short RC crossing must meet both event tolerances.

The unchanged r53 counter records the first crossing without waiting for a wrap.
The independent clock voltage and root are checked through accepted observations.
"""

import argparse
import json
from pathlib import Path
import sys

from validate import ROOT, run, sha
from check import read_ng, sample
from r53_cases import SOURCES, FILES, counter, finish
from r53_reference import score_states
from trace_files import retained_traces
from pilot_identity import write_identity


def validate(output, sdk):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    artifact = output / "model"
    source = SOURCES / FILES["115"]
    for command, name, limit in [
        ([sys.executable, "-B", "-m", "evas", "xspice", "compile", source,
          "-o", artifact, "--model-name", "cross_box", "--test-hooks"], "compile", 20),
        ([sys.executable, "-B", "-m", "evas", "xspice", "build", artifact,
          "--sdk", Path(sdk).resolve()], "build", 120),
    ]:
        result = run(command, ROOT, output / (name + ".log"), limit)
        if result["exit_code"]:
            raise RuntimeError(result)
    build = json.loads((artifact / "native/build.json").read_text())
    d = output / "native"
    d.mkdir()
    (d / "model.cm").symlink_to(build["library"])
    (d / ".spiceinit").write_text("codemodel model.cm\n")
    text, cfg = counter("115", "cross_box")
    cfg["stop"] = 8e-9
    for spec in cfg["states"].values():
        spec["events"] = [event for event in spec["events"] if event[0] < cfg["stop"]]
    (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
    (d / "tb.cir").write_text(finish(text, cfg))
    with retained_traces(d):
        execution = run([build["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 60)
        (d / "execution.json").write_text(json.dumps({**execution, "source_sha256": sha(source),
            "deck_sha256": sha(d / "tb.cir")}, indent=2) + "\n")
        if execution["exit_code"]:
            raise RuntimeError(execution)
        wave = read_ng(d / "wave.raw")
        states = {}
        for inst, spec in cfg["states"].items():
            state = score_states(d / ("trace-" + inst + ".csv"), spec["events"],
                                 spec["indices"], spec["initial"], True)
            residual = max((abs(sample(wave, "clk" + inst, t) - 0.5)
                            for t, values in state["observed"]), default=float("inf"))
            state["accepted_clock_residual_V"] = residual
            state["expression_budget_V"] = 1e-9
            state["passed"] = state["passed"] and residual <= 1e-9
            states[inst] = state
        result = {"passed": all(s["passed"] for s in states.values()), "states": states,
                  "purpose": "First accepted state change must satisfy the analytic RC root time and the actual clock residual; time tolerance alone is insufficient.",
                  "new_ngspice_circuit_runs": 1, "new_ngspice_build_probes": 1}
        (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    result["resolution_refusals"] = {}
    for label, floor, message in [
        ("time", "1p", "cross tolerance below host resolution"),
        ("expression", "100f", "cross expression tolerance below host resolution"),
    ]:
        rejected = output / (label + "-resolution")
        rejected.mkdir()
        (rejected / "model.cm").symlink_to(build["library"])
        (rejected / ".spiceinit").write_text("codemodel model.cm\n")
        text, cfg = counter("115", "cross_box")
        cfg["stop"] = 8e-9
        (rejected / "tb.cir").write_text(finish(text, cfg).replace(
            ".control\n", ".options minbreak=" + floor + "\n.control\n"))
        with retained_traces(rejected):
            execution = run([build["ngspice"], "-b", "tb.cir"], rejected,
                            rejected / "stdout.log", 60)
            (rejected / "execution.json").write_text(json.dumps({**execution,
                "source_sha256": sha(source), "deck_sha256": sha(rejected / "tb.cir")}, indent=2) + "\n")
            refusal = execution["exit_code"] != 0 and not execution["timed_out"] and (
                message in (rejected / "stdout.log").read_text())
            result["resolution_refusals"][label] = refusal
            result["passed"] = result["passed"] and refusal
            result["new_ngspice_circuit_runs"] += 1
            (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sdk", required=True)
    args = parser.parse_args()
    result = validate(args.output, args.sdk)
    print("cross tolerance box", result["passed"],
          {k: v["accepted_clock_residual_V"] for k, v in result["states"].items()})
    raise SystemExit(0 if result["passed"] else 1)

"""Native regression: an omitted timer tolerance must not fire before time.

Use the unchanged four-phase source and complete 57 ns loaded-reference circuit.
The cross-backend paired check remains separate.
"""

import argparse
import json
from pathlib import Path
import sys

from validate import ROOT, run, sha
from check import read_ng
from r53_cases import SOURCES, FILES, clock, finish
from r53_reference import score_wave, score_states
from trace_files import retained_traces
from pilot_identity import write_identity


def validate(output, sdk):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    write_identity(output)
    artifact = output / "model"
    source = SOURCES / FILES["068"]
    for command, name, limit in [
        ([sys.executable, "-B", "-m", "evas", "xspice", "compile", source,
          "-o", artifact, "--model-name", "timer_box", "--test-hooks"], "compile", 20),
        ([sys.executable, "-B", "-m", "evas", "xspice", "build", artifact,
          "--sdk", Path(sdk).resolve()], "build", 120),
    ]:
        receipt = run(command, ROOT, output / (name + ".log"), limit)
        if receipt["exit_code"]:
            raise RuntimeError(receipt)
    build = json.loads((artifact / "native/build.json").read_text())
    text, cfg = clock("068", "timer_box")
    d = output / "native"
    d.mkdir()
    (d / "model.cm").symlink_to(build["library"])
    (d / ".spiceinit").write_text("codemodel model.cm\n")
    (d / "tb.cir").write_text(finish(text, cfg))
    (d / "contract.json").write_text(json.dumps(cfg, indent=2) + "\n")
    with retained_traces(d):
        receipt = run([build["ngspice"], "-b", "tb.cir"], d, d / "stdout.log", 60)
        (d / "execution.json").write_text(json.dumps({**receipt,
            "source_sha256": sha(source), "deck_sha256": sha(d / "tb.cir")}, indent=2) + "\n")
        if receipt["exit_code"]:
            raise RuntimeError(receipt)
        wave = read_ng(d / "wave.raw")
        for name, (positive, negative) in cfg["differences"].items():
            wave[name] = [a - b for a, b in zip(wave[positive], wave[negative])]
        physical = score_wave(wave, cfg)
        states = {}
        for inst, spec in cfg["states"].items():
            state = score_states(d / ("trace-" + inst + ".csv"), spec["events"],
                                 spec["indices"], spec["initial"])
            state["not_early"] = bool(state["observed"]) and all(
                observed[0] >= expected[0]
                for observed, expected in zip(state["observed"], spec["events"]))
            state["passed"] = state["passed"] and state["not_early"]
            states[inst] = state
        result = {"passed": physical["passed"] and all(s["passed"] for s in states.values()),
                  "physical": physical, "states": states,
                  "purpose": "LRM2.4 section5.10.3.3 omitted timer tolerance is at or just after its scheduled time, never the early side of an implicit window.",
                  "new_ngspice_circuit_runs": 1, "new_ngspice_build_probes": 1}
        (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--sdk", required=True)
    args = parser.parse_args()
    result = validate(args.output, args.sdk)
    print("timer deadline", result["passed"], {k: v["observed"] for k, v in result["states"].items()})
    raise SystemExit(0 if result["passed"] else 1)

"""Public installed Rust checks for the same P0 VA, excluding external RC."""

import argparse
import json
import math
from pathlib import Path

from evas import CompileError, Instance, compile_sources, transient
from evas.kernel import select_kernel
from alias_cases import CASES, FILES, SOURCES, configuration
from alias_reference import event, output, score_events
from validate import sha


def validate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    results = {}
    for case in CASES:
        cfg = configuration(case)
        source = SOURCES / FILES[cfg["source"]]
        instances = [Instance(i, "alias_box", s["ports"]) for i, s in cfg["instances"].items()]
        program = compile_sources({source.name: source.read_text()}, instances, external_nodes=cfg["inputs"])
        times = {i * 1e-12 for i in range(6001)}
        for spec in cfg["instances"].values():
            at = event(spec)
            times.update((at - 2e-13, at, at + 25e-12, at + 50e-12, at + 52e-12))
        times = sorted(t for t in times if t <= cfg["stop"])
        result = transient(program, cfg["inputs"], times, stop=cfg["stop"], max_step=1e-12,
                           vabstol=cfg["budgets"]["platform_V"], reltol=0)
        if (result["transient"]["times"] != times or len(result["solutions"]) != len(times)
                or len(result["transient"]["states"]) != len(times)
                or any(len(row["voltages"]) != len(result["nodes"])
                       or not all(math.isfinite(v) for v in row["voltages"])
                       for row in result["solutions"])):
            raise ValueError("incomplete or nonfinite public Rust response")
        states, errors = {}, {}
        for inst, spec in cfg["instances"].items():
            index = result["transient"]["state_names"].index(inst + ":q")
            observed = [(e["time"], e["after"][index]) for e in result["transient"]["events"]
                        if e["before"][index] != e["after"][index]]
            states[inst] = score_events(observed, result["transient"]["states"][0][index], spec, cfg["budgets"])
            node = result["nodes"].index(spec["output"])
            plateau = edge = 0.0
            for t, row in zip(times, result["solutions"]):
                error = abs(row["voltages"][node] - output(spec, t))
                if event(spec) - cfg["budgets"]["event_s"] <= t <= event(spec) + spec["rise_s"] + cfg["budgets"]["event_s"]:
                    edge = max(edge, error)
                else:
                    plateau = max(plateau, error)
            errors[inst] = {"platform_V": plateau, "edge_V": edge}
        passed = all(s["passed"] for s in states.values()) and all(
            e["platform_V"] <= cfg["budgets"]["platform_V"] and e["edge_V"] <= cfg["budgets"]["edge_V"] for e in errors.values())
        results[case] = {"passed": passed, "source_sha256": sha(source), "states": states, "max_error": errors}
        (directory / (case + "-response.json")).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
        (directory / (case + "-contract.json")).write_text(json.dumps(cfg, indent=2) + "\n")
        print(case, passed, flush=True)
    source = (SOURCES / FILES["affine"]).read_text()
    assignment = "a=2*V(vin,vss)+0.1;"
    rejections = {}
    variants = {
        "read_before_definition": source.replace(assignment, "").replace("V(y)<+", assignment + " V(y)<+"),
        "reassigned_alias": source.replace("V(y)<+", assignment + " V(y)<+"),
        "conditional_definition": source.replace(assignment, "if(V(vin,vss)>0) " + assignment),
        "output_dependency": source.replace(assignment, "a=V(y);"),
        "state_dependency": source.replace(assignment, "a=q;"),
        "history_dependency": source.replace(assignment, "a=idt(V(vin,vss),0);"),
        "initial_and_ordinary_writer": source.replace(assignment, "@(initial_step) a=0; " + assignment),
    }
    for name, text in variants.items():
        try:
            compile_sources({name + ".va": text}, [Instance("a", "alias_box", configuration("ramp")["instances"]["a"]["ports"])])
            rejections[name] = {"passed": False, "accepted_unexpectedly": True}
        except CompileError as exc:
            rejections[name] = {"passed": True, "diagnostic": exc.diagnostic}
        (directory / (name + ".va")).write_text(text)
    answer = {"passed": all(r["passed"] for r in results.values()) and all(r["passed"] for r in rejections.values()),
              "cases": results, "admission_rejections": rejections, "kernel_sha256": sha(select_kernel()),
              "scope": "Same VA pure voltage path only; external RC circuit acceptance belongs to native ngspice/Spectre.",
              "new_rust_runs": len(results), "new_native_runs": 0}
    (directory / "analysis.json").write_text(json.dumps(answer, indent=2, allow_nan=False) + "\n")
    return answer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    raise SystemExit(0 if validate(args.output)["passed"] else 1)

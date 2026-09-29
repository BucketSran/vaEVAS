"""Replay supported DVS inputs as independent static points; no transient claim.

The existing 31-condition sources, stimuli and mathematical checkers are read
unchanged. Rejected conditions are recorded explicitly, never given fake waves.
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/dvs2-spectre-validation"))
from run_suite import T, PROFILES, conditions, v1
from check_results import check

from evas import CompileError, Instance, compile_sources, solve
from evas.syntax import Parser


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    records, rejected = [], []
    for case in conditions():
        sources = {str(ROOT / "evas/validation/cases" / card / "dut.va"):
                   (ROOT / "evas/validation/cases" / card / "dut.va").read_text()
                   for card in case["source_cards"]}
        try:
            models = [Parser(text, path).parse() for path, text in sources.items()]
            ports = {m.name: m.ports for m in models}
            instances = []
            for inst in case["instances"]:
                module = inst.get("module", case.get("module"))
                instances.append(Instance(inst["name"], module,
                    dict(zip(ports[module], inst["ports"], strict=True)), inst["params"]))
            program = compile_sources(sources, instances)
        except CompileError as exc:
            rejected.append(dict(condition=case["id"], reason=str(exc)))
            continue
        if program.states or program.events or program.operators:
            # Parsing a dynamic model is not permission to replay it as
            # unrelated static points. Keep it in the original denominator.
            rejected.append(dict(condition=case["id"],
                                 reason="unsupported_analysis: state/event/operator program requires transient execution"))
            continue
        for profile, settings in PROFILES.items():
            count = round(case["stop_x"] * T / settings["step"])
            times = [i * (case["stop_x"] * T / count) for i in range(count + 1)]
            driven = list(case["inputs"])
            inputs = [[v1.pwl(case["inputs"][n], t) for n in driven] for t in times]
            result = solve(program, driven, inputs, kernel=args.kernel.resolve(),
                           vabstol=settings["vabstol"], reltol=settings["reltol"])
            rows = [dict(time=t, **dict(zip(result["nodes"], s["voltages"], strict=True)))
                    for t, s in zip(times, result["solutions"], strict=True)]
            analysis = check(rows, case)
            work = args.output / case["id"] / profile
            work.mkdir(parents=True)
            (work / "program.json").write_text(json.dumps(program.to_dict(), indent=2) + "\n")
            (work / "condition.json").write_text(json.dumps(case, indent=2) + "\n")
            with (work / "waveform.csv").open("w") as stream:
                writer = csv.DictWriter(stream, fieldnames=["time", *result["nodes"]])
                writer.writeheader()
                writer.writerows(rows)
            records.append(dict(condition=case["id"], profile=profile, sample_count=len(rows),
                settings=dict(sample_step_s=settings["step"], residual_absolute_v=settings["vabstol"],
                              residual_relative=settings["reltol"], vabstol_v=settings["vabstol"],
                              reltol=settings["reltol"]), analysis=analysis,
                max_residual_v=max(s["max_residual_v"] for s in result["solutions"]),
                max_residual_ratio=max(s["max_residual_ratio"] for s in result["solutions"])))
            for metric in ("max_scaled_residual_ratio", "max_voltage_correction_v",
                           "max_voltage_correction_ratio"):
                if metric in result["solutions"][0]:
                    records[-1][metric] = max(s[metric] for s in result["solutions"])
            print(case["id"], profile, analysis["status"], len(rows), flush=True)
    source_files = [p for base in (ROOT / "evas/src", ROOT / "evas/tests", ROOT / "evas/rust_core/src")
                    for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    source_files += [ROOT / "evas/rust_core" / n for n in ("Cargo.toml", "Cargo.lock")]
    source_files += [ROOT / "experiments/dvs2-spectre-validation" / n for n in ("run_suite.py", "check_results.py")]
    source_files += [ROOT / "experiments/dvs2-starter-pilot" / n for n in ("suite.py", "analyze.py")]
    source_files += [ROOT / "experiments/dvs2-history-validation" / n for n in ("history.py", "recheck.py")]
    source_files += list((ROOT / "evas/validation/cases").rglob("*.va"))
    report = dict(scope="stateless polynomial operating points on two requested grids; NOT a transient simulator qualification",
        engine=result["engine"] if records else None, kernel_sha256=digest(args.kernel),
        rustc=subprocess.check_output(["rustc", "--version"], text=True).strip(),
        python=sys.version, source_sha256={str(p.relative_to(ROOT)):digest(p) for p in sorted(source_files)},
        configurations=len(records), supported_conditions=len(records)//2, rejected_conditions=len(rejected),
        total_points=sum(r["sample_count"] for r in records), records=records, rejected=rejected)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = {str(p.relative_to(args.output)):digest(p) for p in sorted(args.output.rglob("*")) if p.is_file()}
    (args.output / "SHA256.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k:report[k] for k in ("configurations", "supported_conditions", "rejected_conditions", "total_points")}))
    return 0 if records and all(r["analysis"]["status"] == "observations_within_targets" for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())

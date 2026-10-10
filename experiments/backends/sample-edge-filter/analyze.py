"""Reassess preserved observations and compare exactly equal native times.

This never changes the original execution receipts or their verdicts.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "evas/validation/sample_edge_filter"),
               str(ROOT / "experiments/backends/paper")]
from contract import CASES, T, TIME_BUDGET, assess, callbacks
from inputs import save, sha


def read(path):
    return json.loads(path.read_text())


def compare(case, reference, candidate):
    if [r["time"] for r in reference] != [r["time"] for r in candidate]:
        return {"status": "GRID_MISMATCH"}
    result = {}
    for instance in case["instances"]:
        name = instance["name"]
        events = [float(t) * T for t, _ in callbacks(instance)]
        pairs = list(zip(reference, candidate))
        outside = [(a, b) for a, b in pairs
                   if all(abs(a["time"] - t) > TIME_BUDGET for t in events)]
        same = [(a, b) for a, b in pairs if round(a[name + "n"]) == round(b[name + "n"])]
        def maximum(rows, port):
            return max((abs(a[name + port] - b[name + port]) for a, b in rows), default=None)
        result[name] = {
            "maximum_difference_V_all_rows": {p: maximum(pairs, p) for p in "hef"},
            "held_difference_V_same_callback_count": maximum(same, "h"),
            "held_difference_V_outside_event_windows": maximum(outside, "h"),
            "counter_disagreements_all_rows": sum(round(a[name + "n"]) != round(b[name + "n"]) for a, b in pairs),
            "counter_disagreements_outside_event_windows": sum(round(a[name + "n"]) != round(b[name + "n"]) for a, b in outside),
            "final_counts": [reference[-1][name + "n"], candidate[-1][name + "n"]],
        }
    return {"status": "COMPARED", "rows": len(reference), "instances": result}


def analyze(spectre, evas, output):
    if output.exists():
        raise FileExistsError(output)
    manifest = read(spectre / "FILE_MANIFEST.json")
    for name, digest in manifest.items():
        if sha(spectre / name) != digest:
            raise ValueError("modified Spectre artifact: " + name)
    records = []
    for case in CASES:
        for setting in ("base", "tight", "fine"):
            sp = spectre / case["id"] / setting
            ep = evas / case["id"] / ("native-" + setting)
            original = read(sp / "RESULT.json")
            record = {"case": case["id"], "setting": setting,
                      "original_spectre_assessment": original["assessment"],
                      "effective_settings": original.get("effective_settings"),
                      "spectre_result_sha256": sha(sp / "RESULT.json")}
            try:
                sr, er = read(sp / "rows.json"), read(ep / "rows.json")
                record.update(spectre_assessment=assess(case, sr),
                              evas_assessment=assess(case, er),
                              paired=compare(case, sr, er),
                              observation_sha256={"spectre": sha(sp / "rows.json"),
                                                  "evas": sha(ep / "rows.json")})
            except Exception as error:
                record["analysis_failure"] = str(error)
            records.append(record)
    invariant = []
    for case in CASES:
        try:
            sparse = read(evas / case["id"] / "sparse/response.json")
            dense = read(evas / case["id"] / "dense/response.json")
            indexed = dict(zip(dense["transient"]["times"], dense["solutions"], strict=True))
            mismatches = sum(r != indexed.get(t) for t, r in zip(sparse["transient"]["times"], sparse["solutions"], strict=True))
            invariant.append({"case": case["id"], "common_query_mismatches": mismatches,
                              "identical_events": sparse["transient"]["events"] == dense["transient"]["events"]})
        except Exception as error:
            invariant.append({"case": case["id"], "analysis_failure": str(error)})
    save(output, {"kind": "reanalysis_and_same_native_time_comparison",
                  "source_sha256": {str(p.relative_to(ROOT)): sha(p) for p in [Path(__file__), ROOT / "evas/validation/sample_edge_filter/contract.py"]},
                  "spectre_manifest_sha256": sha(spectre / "FILE_MANIFEST.json"),
                  "evas_identity": read(evas / "IDENTITY.json"),
                  "fixed_denominator": {"cases": 4, "spectre_configurations": 12, "paired_native_grids": 12},
                  "query_invariance": invariant, "records": records,
                  "claim_limit": "Finite observations; all-row differences retained. Windowed held values are not exact-boundary agreement."})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spectre", type=Path)
    parser.add_argument("evas", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    analyze(args.spectre, args.evas, args.output)

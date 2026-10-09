"""Prepare the authored circuit tasks and their declared semantic negatives."""
import argparse
import json
from pathlib import Path

from runtime import ROOT, prepare


def candidates(task):
    if task.name.startswith("identify-"):
        folder = ROOT / "runs/identification-candidates" / task.name
        return [("reference" if p.parent.name == "reference" else "semantic_negative", p.parent.name, p)
                for p in sorted(folder.glob("*/dut.va"))]
    result = [("reference", "reference", task / "solution/dut.va")]
    negatives = list((task / "tests/negatives").glob("*.va")) + list((task / "tests/mutants").glob("*.va"))
    result.extend(("semantic_negative", p.stem, p) for p in sorted(negatives))
    if task.name.startswith("integrate-"):
        folder = ROOT / "experiments/benchmark_first_batch/integration/mutants" / task.name
        result.extend(("semantic_negative", p.parent.name, p) for p in sorted(folder.glob("*/dut.va")))
    return result


def build(output, harness, selected=None, include="all"):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    task_names = set()
    for name in ("model_repair", "identification", "integration", "verification_measurement"):
        registry = json.loads((ROOT / "benchmark/first_batch" / (name + ".json")).read_text())
        task_names.update(t.get("id", t.get("task_id")) for t in registry["tasks"])
    task_names = {name for name in task_names if not name.startswith("va")}
    if selected:
        if not set(selected) <= task_names:
            raise ValueError("unknown task selection")
        task_names = set(selected)
    focused = json.loads((ROOT / "experiments/benchmark_first_batch/verification_measurement/calibration_plan.json").read_text())["negative_cases"]
    matrix = []
    for name in sorted(task_names):
        task = ROOT / "benchmark/tasks" / name
        choices = candidates(task)
        if sum(role == "reference" for role, _, _ in choices) != 1 or len(choices) < 2:
            raise ValueError("missing reference or semantic negatives: " + name)
        for role, variant, candidate in choices:
            if include != "all" and role != include:
                continue
            case_name = focused.get(name, {}).get(variant) if role == "semantic_negative" else None
            prepared = output / name / variant
            record = prepare(task, candidate, prepared, harness, case_names=[case_name] if case_name else None)
            matrix.append({"task_id": name, "role": role, "variant": variant, "prepared": str(prepared),
                           "expected": "all graded and passed" if role == "reference" else "all selected graded and at least one failed",
                           "candidate_sha256": record["candidate"]["candidate_sha256"],
                           "criteria_sha256": record["criteria_sha256"],
                           "conditions": [c["condition_id"] for c in record["cases"]]})
    # References are checked before negative calibration. Both remain in the
    # denominator, including failed infrastructure and compiler attempts.
    matrix.sort(key=lambda row: (row["role"] != "reference", row["task_id"], row["variant"]))
    (output / "matrix.json").write_text(json.dumps(matrix, indent=2) + "\n")
    (output / "plan.json").write_text(json.dumps([row["prepared"] for row in matrix], indent=2) + "\n")
    return matrix


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness-checkout", type=Path, required=True)
    parser.add_argument("--task", action="append")
    parser.add_argument("--include", choices=("all", "reference", "semantic_negative"), default="all")
    args = parser.parse_args()
    matrix = build(args.output, args.harness_checkout, args.task, args.include)
    print(json.dumps({"prepared_submissions": len(matrix), "tasks": len({r['task_id'] for r in matrix}),
                      "conditions": sum(len(r["conditions"]) for r in matrix), "executed": False}))

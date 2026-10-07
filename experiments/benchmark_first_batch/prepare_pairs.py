"""Freeze a declared warm-up and five sequential baseline/reference pairs."""
import argparse
import json
from pathlib import Path

from runtime import ROOT, prepare


def build(output, harness, selections):
    output = Path(output).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    registry = json.loads((ROOT / "benchmark/first_batch/optimization.json").read_text())
    candidates = {c["candidate_id"]: c for c in registry["candidates"]}
    attempts = []
    for task_id, condition in selections:
        candidate = candidates[task_id]
        for pair in range(6):
            phase = "warmup" if pair == 0 else "measurement"
            for side in ("baseline", "reference"):
                prepared = output / task_id / f"{pair:02d}-{phase}-{side}"
                record = prepare(ROOT / candidate["probe_path"], ROOT / candidate[side + "_path"],
                                 prepared, harness, case_names=[condition])
                attempts.append({"prepared": str(prepared), "task_id": task_id,
                                 "condition_id": condition, "phase": phase, "pair": pair,
                                 "side": side, "candidate_sha256": record["candidate"]["candidate_sha256"],
                                 "criteria_sha256": record["criteria_sha256"]})
    (output / "manifest.json").write_text(json.dumps(attempts, indent=2) + "\n")
    (output / "plan.json").write_text(json.dumps([a["prepared"] for a in attempts], indent=2) + "\n")
    return attempts


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness-checkout", type=Path, required=True)
    parser.add_argument("--task-case", action="append", nargs=2, required=True,
                        metavar=("TASK_ID", "CASE"))
    args = parser.parse_args()
    result = build(args.output, args.harness_checkout, args.task_case)
    print(json.dumps({"attempts": len(result), "executed": False,
                      "required_workers": 1, "other_simulator_queues": "must be paused for timing"}))

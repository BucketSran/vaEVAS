"""V2 task packaging over the existing durable benchmark transport.

This module creates task packages only. Execute with the first-batch runtime and
its bounded queue; a coordinator owns all concurrent Spectre jobs.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.benchmark_first_batch.runtime import prepare


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--harness-checkout", type=Path, required=True)
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    record = prepare(args.task, args.candidate, args.output, args.harness_checkout,
                     case_names=args.case, task_version="circuit-benchmark-v2-development")
    print(json.dumps({"status": record["status"], "criteria_sha256": record["criteria_sha256"],
                      "conditions": len(record["cases"])}))


if __name__ == "__main__":
    main()

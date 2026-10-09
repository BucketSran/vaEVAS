"""Bounded calibration queue over runtime.py and the existing circuit harness.

The plan lists already prepared directories. This tool does not submit remote
jobs itself. A failed runtime invocation stops new work; existing jobs finish.
Do not run another Spectre queue concurrently with this one.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import threading


def summarize(prepared):
    prepared = Path(prepared)
    plan = json.loads((prepared / "preparation.json").read_text())
    results = json.loads((prepared / "results.json").read_text())
    conditions = []
    for item in results:
        result = item["result"]
        archive = prepared / "remote" / item["job_id"] / "archive/job.tar.gz"
        with tarfile.open(archive) as stream:
            data = stream.extractfile("run/work/verifier/report.json").read()
        expected = result["artifacts"]["work/verifier/report.json"]["sha256"]
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("report identity mismatch")
        report = json.loads(data)
        if (result["candidate_sha256"] != plan["candidate"]["candidate_sha256"] or
                result["criteria_sha256"] != plan["criteria_sha256"]):
            raise ValueError("calibration identity mismatch")
        conditions.append({"condition_id": item["condition_id"], "job_id": item["job_id"],
                           "execution": result["execution"], "score": result.get("score"),
                           "report_status": report["status"], "reason": report.get("reason"),
                           "cases": [{k: v for k, v in c.items() if k not in {"log_tail", "candidate_files", "argv"}}
                                     for c in report["cases"]],
                           "archive": str(archive), "report_sha256": expected})
    all_graded = (len(conditions) == len(plan["cases"]) and
                  all(c["execution"] == "ok" and c["cases"] and
                      all(case["status"] == "graded" for case in c["cases"]) for c in conditions))
    return {"task_id": plan["task_id"], "candidate_sha256": plan["candidate"]["candidate_sha256"],
            "criteria_sha256": plan["criteria_sha256"], "expected_conditions": len(plan["cases"]),
            "all_conditions_graded": bool(all_graded),
            "reference_passed": bool(all_graded and all(c["score"] == 1 for c in conditions)),
            "has_graded_failure": bool(all_graded and any(c["score"] == 0 for c in conditions)),
            "conditions": conditions}


def run_queue(plan_path, config, workers):
    entries = json.loads(Path(plan_path).read_text())
    paths = [str(Path(entry).resolve()) for entry in entries]
    if len(set(paths)) != len(paths):
        raise ValueError("duplicate prepared directory")
    stop = threading.Event()
    def run(prepared):
        if stop.is_set():
            return {"prepared": prepared, "status": "not_started"}
        root = Path(prepared)
        log = root / "operator.log"
        with log.open("a") as stream:
            result = subprocess.run([sys.executable, "-B", str(Path(__file__).with_name("runtime.py")),
                                     "execute", prepared, "--config", str(config)],
                                    stdout=stream, stderr=subprocess.STDOUT)
        if result.returncode:
            stop.set()
            answer = {"prepared": prepared, "status": "runtime_failed", "returncode": result.returncode}
        else:
            try:
                summary = summarize(root)
                (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
                answer = {"prepared": prepared, "status": "completed",
                          **{key: summary[key] for key in ("task_id", "all_conditions_graded", "reference_passed", "has_graded_failure")}}
            except Exception as exc:
                stop.set()
                answer = {"prepared": prepared, "status": "summary_failed", "error": str(exc)}
        print(json.dumps(answer), flush=True)
        return answer
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(run, paths))
    Path(str(plan_path) + ".results.json").write_text(json.dumps(results, indent=2) + "\n")
    return 1 if stop.is_set() else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    args = parser.parse_args()
    raise SystemExit(run_queue(args.plan, args.config.resolve(), args.workers))

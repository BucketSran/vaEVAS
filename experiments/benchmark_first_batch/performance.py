"""Extract performance evidence from verified, functionally passing harness jobs.

This is an offline analysis. It neither launches simulations nor decides a task's
performance threshold. Candidate streams were captured together by circuit_task.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
import tarfile

from runtime import ROOT


def digest(data):
    return hashlib.sha256(data).hexdigest()


def module_at(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def extract(prepared):
    prepared = Path(prepared)
    plan = json.loads((prepared / "preparation.json").read_text())
    results = json.loads((prepared / "results.json").read_text())
    primitive_path = ROOT / "benchmark/checkers/first_batch_optimization.py"
    primitive = module_at(primitive_path, "_performance_primitives")
    if len(results) != len(plan["cases"]):
        raise ValueError("incomplete execution set")
    records = []
    for item in results:
        result = item["result"]
        if result["execution"] != "ok" or result["score"] != 1:
            raise ValueError("performance requires a functionally passing submission")
        if (result["candidate_sha256"] != plan["candidate"]["candidate_sha256"] or
                result["criteria_sha256"] != plan["criteria_sha256"]):
            raise ValueError("frozen execution identity differs")
        archive = prepared / "remote" / item["job_id"] / "archive/job.tar.gz"
        with tarfile.open(archive) as tf:
            def verified(name):
                member = tf.getmember("run/" + name)
                if not member.isfile():
                    raise ValueError("artifact is not a regular file: " + name)
                data = tf.extractfile(member).read()
                expected = result["artifacts"][name]
                if digest(data) != expected["sha256"] or len(data) != expected["bytes"]:
                    raise ValueError("artifact identity differs: " + name)
                return data
            report = json.loads(verified("work/verifier/report.json"))
            if report["status"] != "completed" or report["reward"] != 1 or len(report["cases"]) != 1:
                raise ValueError("single-condition functional report required")
            case = report["cases"][0]
            if case["status"] != "graded" or case["passed"] is not True:
                raise ValueError("numerically graded success required")
            name = case["name"]
            if name != item["condition_id"]:
                raise ValueError("condition identity differs")
            prefix = "work/verifier/" + name + "/"
            source = verified(prefix + "dut.va")
            if source != verified(prefix + "original/dut.va") or source != verified("work/candidate/dut.va"):
                raise ValueError("performance source changed during execution")
            if len(report["candidate_files"]) != 1:
                raise ValueError("this analysis requires one self-contained candidate source")
            waveform = verified(prefix + "psf/tran.tran.tran")
            if digest(waveform) != case["waveform_sha256"]:
                raise ValueError("graded waveform identity differs")
            native = verified(prefix + "spectre.log")
            combined = verified(prefix + "stdout.log")
            stats = primitive.validate_solver_evidence(source, case["returncode"], native,
                                                       combined, None, stream_layout="merged")
            records.append({"task_id": plan["task_id"], "condition_id": name,
                            "job_id": item["job_id"], "archive": str(archive),
                            "availability": "local-only", "archive_sha256": digest(archive.read_bytes()),
                            "candidate_bundle_sha256": result["candidate_sha256"],
                            "source_sha256": digest(source), "criteria_sha256": result["criteria_sha256"],
                            "source_identity": plan["source_identity"],
                            "netlist_sha256": case["netlist_sha256"],
                            "report_sha256": result["artifacts"]["work/verifier/report.json"]["sha256"],
                            "waveform_sha256": case["waveform_sha256"],
                            "functional_result": {k: v for k, v in case.items()
                                                  if k not in {"log_tail", "candidate_files", "argv"}},
                            "solver_process_elapsed_s": case["elapsed_s"],
                            "solver_argv": case["argv"], "native_statistics": stats,
                            "analysis_source_sha256": digest(Path(__file__).read_bytes()),
                            "statistics_parser_sha256": digest(primitive_path.read_bytes())})
    return records


def paired_summary(records, manifest):
    """Summarize a declared sequence; missing/invalid attempts cannot disappear."""
    if len(records) != len(manifest):
        raise ValueError("every declared attempt must have one record")
    grouped = {}
    for record, attempt in zip(records, manifest):
        if record["task_id"] != attempt["task_id"] or record["condition_id"] != attempt["condition_id"]:
            raise ValueError("attempt and execution differ")
        if attempt["phase"] == "measurement":
            grouped.setdefault(record["task_id"], []).append((attempt, record))
    summaries = {}
    for task, group in grouped.items():
        pairs = {}
        for attempt, record in group:
            side = attempt["side"]
            pair = pairs.setdefault(attempt["pair"], {})
            if side not in {"baseline", "reference"} or side in pair:
                raise ValueError("duplicate/unknown pair side")
            pair[side] = record
        if len(pairs) < 5 or any(set(p) != {"baseline", "reference"} for p in pairs.values()):
            raise ValueError("at least five complete pairs required")
        identity_keys = ("condition_id", "netlist_sha256", "criteria_sha256")
        for key in identity_keys:
            if len({record[key] for _, record in group}) != 1:
                raise ValueError("paired experimental setup changed: " + key)
        if len({record["native_statistics"]["spectre_version"] for _, record in group}) != 1:
            raise ValueError("paired simulator version changed")
        for side in ("baseline", "reference"):
            if len({r["source_sha256"] for a, r in group if a["side"] == side}) != 1:
                raise ValueError("source changed between repetitions")
        metrics = {
            "intrinsic_cpu_s": lambda r: r["native_statistics"]["intrinsic_tran"]["cpu_s"],
            "intrinsic_elapsed_s": lambda r: r["native_statistics"]["intrinsic_tran"]["elapsed_s"],
            "accepted_steps": lambda r: r["native_statistics"]["accepted_steps"],
            "solver_process_elapsed_s": lambda r: r["solver_process_elapsed_s"],
        }
        summary = {"pairs": len(pairs), "measurements": len(group), "metrics": {}}
        for name, metric in metrics.items():
            sides = {}
            for side in ("baseline", "reference"):
                values = [metric(pairs[pair][side]) for pair in sorted(pairs)]
                sides[side] = {"values": values, "median": statistics.median(values),
                               "min": min(values), "max": max(values)}
            ratios = [metric(pairs[pair]["baseline"]) / metric(pairs[pair]["reference"])
                      if metric(pairs[pair]["reference"]) > 0 else None for pair in sorted(pairs)]
            summary["metrics"][name] = {**sides, "paired_baseline_over_reference": ratios}
        summaries[task] = summary
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True,
                        help="JSON list: prepared, task_id, condition_id, phase, side, pair")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("analysis output must be new")
    manifest = json.loads(args.manifest.read_text())
    records = []
    for attempt in manifest:
        extracted = extract(attempt["prepared"])
        if len(extracted) != 1:
            raise ValueError("one condition per timing attempt is required")
        records.extend(extracted)
    result = {"kind": "offline_analysis_of_actual_spectre_jobs", "new_simulations": 0,
              "manifest_sha256": digest(args.manifest.read_bytes()), "attempts": manifest,
              "records": records, "paired_summaries": paired_summary(records, manifest)}
    args.output.write_text(json.dumps(result, indent=2) + "\n")

"""Reanalyze six V3 Spectre timing controls; never execute a simulator.

The original checker remains unchanged. Its verdict uses the original V3
contract, not the tighter cross settings of the diagnostic controls.
"""
import argparse
import json
import math
from pathlib import Path
import re

from event_writer_compare import ROOT, check, read_waveform, settings, sha, verify


def analyze(root, baseline):
    remote = root / "spectre-remote"
    reference = baseline / "spectre-remote"
    for directory in (remote, reference):
        verify(directory, "INPUT_MANIFEST.json")
        verify(directory, "FILE_MANIFEST.json")
    if sha(remote / "INPUT_MANIFEST.json") != sha(root / "INPUT_MANIFEST.json"):
        raise ValueError("remote input identity differs")
    plan = json.loads((remote / "RUN_PLAN.json").read_text())
    if plan["baseline_run"] != baseline.name or len(plan["configurations"]) != 6:
        raise ValueError("unexpected experiment denominator or baseline")
    case = json.loads((remote / "conditions.json").read_text())[0]
    tool = json.loads((remote / "TOOL_IDENTITY.json").read_text())
    if tool != json.loads((reference / "TOOL_IDENTITY.json").read_text()):
        # Probe timings/log identities vary; tool and setup must not.
        previous = json.loads((reference / "TOOL_IDENTITY.json").read_text())
        if any(tool[k] != previous[k] for k in ("binary_sha256", "setup_sha256")):
            raise ValueError("tool or setup differs from baseline")
    records = []
    for config in plan["configurations"]:
        work = remote / "runs/v3-main" / config["id"]
        old = reference / "runs/v3-main" / config["baseline_profile"]
        for name in ("dut.va", "condition.json", "requested_settings.json", "tb.scs"):
            if sha(work / name) != sha(root / "runs/v3-main" / config["id"] / name):
                raise ValueError("local/remote input mismatch: " + name)
        if sha(work / "dut.va") != config["source_sha256"] or sha(work / "tb.scs") != config["netlist_sha256"]:
            raise ValueError("input differs from frozen plan")
        if sha(work / "condition.json") != sha(old / "condition.json"):
            raise ValueError("original V3 contract changed")
        result = json.loads((work / "result.json").read_text())
        if result["status"] != "waveform_available" or result["returncode"] != 0 or result["timeout"]:
            raise ValueError("diagnostic execution failed: " + config["id"])
        waveform = work / result["waveform"]
        if sha(waveform) != result["waveform_sha256"]:
            raise ValueError("waveform identity differs")
        log = (work / "spectre.log").read_text()
        actual = settings(log)
        requested = json.loads((work / "requested_settings.json").read_text())
        if any(actual[k] != requested[k] if isinstance(actual[k], str) else
               not math.isclose(actual[k], requested[k], rel_tol=1e-12, abs_tol=0)
               for k in actual):
            raise ValueError("effective settings differ")
        rows = read_waveform(waveform, "spectre")
        checked = check(rows, case)
        screen = checked["v1_screen"]
        edges = screen["edges"]
        maximum = screen["max_observed_error"]["vout"]["error_v"]
        predicted = 1.6e7 * max(abs(e["inferred_start_error_s"]) for e in edges)
        if not math.isclose(maximum, predicted, rel_tol=1e-7, abs_tol=1e-12):
            raise ValueError("observed voltage difference does not match edge displacement")
        messages = re.findall(r"EW_DIAG (rise|fall) time=(\S+) q=(\d+)", log)
        logged = []
        identical = None
        if config["change"] == "instrument":
            if [(kind, q) for kind, _, q in messages] != [("rise", "1"), ("fall", "0")]:
                raise ValueError("missing or unexpected diagnostic events")
            old_result = json.loads((old / "result.json").read_text())
            identical = rows == read_waveform(old / old_result["waveform"], "spectre")
            if not identical:
                raise ValueError("instrumentation perturbed exported waveform")
            for (kind, time, q), edge in zip(messages, edges):
                event_time = float(time)
                inferred = edge["nominal_start_s"] + edge["inferred_start_error_s"]
                if not math.isclose(event_time, inferred, rel_tol=0, abs_tol=1e-18):
                    raise ValueError("logged event differs from inferred edge start")
                logged.append(dict(kind=kind, time_s=event_time, q=int(q),
                                   delay_s=event_time - edge["nominal_start_s"]))
        records.append(dict(configuration=config, requested_settings=requested,
                            effective_settings=actual,
                            cross_tolerances=re.findall(r"cross\([^\n]+, [+-]1, ([\deE.-]+), ([\deE.-]+)\)", (work / "dut.va").read_text()),
                            input_sha256={n: sha(work / n) for n in
                                          ("dut.va", "condition.json", "requested_settings.json", "tb.scs")},
                            waveform_sha256=sha(waveform), spectre_log_sha256=sha(work / "spectre.log"),
                            execution={k: result[k] for k in
                                       ("argv", "returncode", "timeout", "elapsed_s", "log_sha256")},
                            original_contract_status=checked["status"], sample_count=len(rows),
                            max_nominal_error_v=maximum, predicted_edge_shift_error_v=predicted,
                            plateau_error_v=screen["plateau_error_v"], edges=edges,
                            logged_events=logged, instrumentation_rows_equal_baseline=identical))
    budget = json.loads((remote / "STARTED.json").read_text())
    version = re.search(r"sub-version\s+([^\n]+)", (remote / "version.log").read_text()).group(1).strip()
    return dict(run_id=root.name, execution_use="6 new Spectre executions; baseline waveforms reused for diagnosis only",
                baseline_run=baseline.name, baseline_receipt_sha256=sha(baseline / "analysis-final.json"),
                baseline_file_manifest_sha256=sha(reference / "FILE_MANIFEST.json"),
                run_plan=plan, input_manifest_sha256=sha(remote / "INPUT_MANIFEST.json"),
                file_manifest_sha256=sha(remote / "FILE_MANIFEST.json"),
                raw_archive_sha256=sha(root / "spectre-outputs.tar.gz"),
                runner_sha256=sha(remote / "remote.py"), analysis_script_sha256=sha(Path(__file__)),
                original_checker_sha256=sha(ROOT / "experiments/dvs2-spectre-validation/check_results.py"),
                original_settings_reader_sha256=sha(ROOT / "experiments/dvs2-spectre-validation/report.py"),
                spectre_version=version, spectre_binary_sha256=tool["binary_sha256"], setup_sha256=tool["setup_sha256"],
                budget={k: budget[k] for k in ("max_runs", "cpu", "timeout_s", "license_timeout_s")},
                records=records, formal_dvs_qualification="I", continuous_time_qualified=False,
                raw_availability="local-only ignored run and thu-sui archive; not publicly downloadable",
                limits="Original-contract verdicts do not certify tightened control tolerances. No internal Spectre algorithm, full matrix, same-time writer or performance claim.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze(args.root, args.baseline)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    for row in result["records"]:
        print(row["configuration"]["id"], row["original_contract_status"],
              [edge["inferred_start_error_s"] * 1e12 for edge in row["edges"]], row["max_nominal_error_v"])

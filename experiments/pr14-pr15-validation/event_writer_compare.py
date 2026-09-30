"""Analyze a fresh V3 two-profile EVAS/Spectre batch against its frozen contract.

The runner is the existing Spectre runner with only its subset count reduced.
All exported observations go through the unchanged original checker. Pairwise
linear interpolation is diagnostic; it is not an event or continuous-time oracle.
"""
import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/dvs2-spectre-validation"))
from report import settings
from check_results import check, read_waveform


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, name):
    for rel, identity in json.loads((root / name).read_text()).items():
        path = root / rel
        if not path.resolve().is_relative_to(root.resolve()):
            raise ValueError("manifest path escapes root")
        if sha(path) != identity["sha256"] or path.stat().st_size != identity["bytes"]:
            raise ValueError("artifact drift: " + rel)


def compare(evas, spectre):
    times = [row["time"] for row in spectre]
    maximum = (0.0, None)
    for row in evas:
        t = row["time"]
        i = bisect_right(times, t)
        if i == 0:
            value = spectre[0]["vout"]
        elif i == len(times):
            value = spectre[-1]["vout"]
        else:
            a, b = spectre[i-1], spectre[i]
            if b["time"] <= a["time"]:
                raise ValueError("cannot interpolate nonincreasing observations")
            fraction = (t-a["time"]) / (b["time"]-a["time"])
            value = a["vout"] + fraction * (b["vout"]-a["vout"])
        error = abs(row["vout"]-value)
        if error > maximum[0]:
            maximum = (error, t)
    return dict(max_interpolated_difference_v=maximum[0], time_s=maximum[1],
                grid_points=len(evas), method="Spectre linear interpolation on EVAS export grid",
                interpretation="diagnostic only; V3 output is continuous; no certification between exports")


def analyze(root):
    start = json.loads((root / "LOCAL_START.json").read_text())
    remote = root / "spectre-remote"
    verify(remote, "INPUT_MANIFEST.json")
    verify(remote, "FILE_MANIFEST.json")
    if sha(remote / "INPUT_MANIFEST.json") != sha(root / "INPUT_MANIFEST.json"):
        raise ValueError("remote input identity differs")
    cases = json.loads((remote / "conditions.json").read_text())
    if len(cases) != 1 or cases[0]["id"] != "v3-main":
        raise ValueError("unexpected comparison denominator")
    case = cases[0]
    records, pairs = [], []
    for profile in ["base", "fine"]:
        rows_by_backend = {}
        for backend, base in [("evas", root / "evas"), ("spectre", remote)]:
            work = base / "runs/v3-main" / profile
            for name in ["dut.va", "condition.json", "requested_settings.json", "tb.scs"]:
                if sha(work/name) != sha(root/"runs/v3-main"/profile/name):
                    raise ValueError("backend input mismatch: " + name)
            result = json.loads((work/"result.json").read_text())
            if result["status"] != "waveform_available":
                raise ValueError("backend did not produce a waveform")
            waveform = work / result["waveform"]
            if sha(waveform) != result["waveform_sha256"]:
                raise ValueError("waveform identity differs")
            rows = read_waveform(waveform, backend)
            analysis = check(rows, case)
            row = dict(backend=backend, condition="v3-main", profile=profile,
                       analysis=analysis, source_sha256=sha(work/"dut.va"),
                       condition_sha256=sha(work/"condition.json"),
                       netlist_sha256=sha(work/"tb.scs"),
                       requested_settings_sha256=sha(work/"requested_settings.json"),
                       waveform_sha256=sha(waveform))
            execution = result if backend == "spectre" else json.loads((work/"execution.json").read_text())
            row["execution"] = {key: execution[key] for key in
                                ["returncode", "timeout", "elapsed_s", "log_sha256"]}
            if backend == "spectre":
                log = (work/"spectre.log").read_text()
                actual = settings(log)
                requested = json.loads((work/"requested_settings.json").read_text())
                match = all(actual[k] == v if isinstance(v, str) else
                            math.isclose(actual[k], v, rel_tol=1e-12, abs_tol=0)
                            for k, v in requested.items() if k in actual)
                if not match:
                    raise ValueError("Spectre effective settings differ")
                row.update(effective_settings=actual, requested_match=match,
                           warning_codes=dict(Counter(re.findall(r"WARNING \(([^)]+)\)", log))))
            records.append(row)
            rows_by_backend[backend] = rows
        pairs.append(dict(profile=profile, **compare(rows_by_backend["evas"], rows_by_backend["spectre"])))
    tool = json.loads((remote/"TOOL_IDENTITY.json").read_text())
    budget = json.loads((remote/"STARTED.json").read_text())
    version = re.search(r"sub-version\s+([^\n]+)", (remote/"version.log").read_text())
    return dict(run_id=root.name, scope="original V3 only; two configurations per backend",
                execution_use="4 new executions; no reused backend waveform",
                evas_commit=start["evas_commit"], evas_git_status=start["evas_git_status"],
                kernel_sha256=start["kernel_sha256"], source_sha256=start["source_sha256"],
                evas_source_archive_sha256=sha(root/"evas-source.tar.gz"),
                source_input_manifest_sha256=start["source_input_manifest_sha256"],
                input_manifest_sha256=sha(remote/"INPUT_MANIFEST.json"),
                spectre_file_manifest_sha256=sha(remote/"FILE_MANIFEST.json"),
                spectre_archive_sha256=sha(root/"spectre-outputs.tar.gz"),
                spectre_version=version.group(1).strip() if version else None,
                spectre_binary_sha256=tool["binary_sha256"], setup_sha256=tool["setup_sha256"],
                original_runner_sha256=start["original_runner_sha256"],
                subset_runner_sha256=start["runner_sha256"], runner_changes=start["runner_changes"],
                adapter_sha256=start["adapter_sha256"], analysis_script_sha256=sha(Path(__file__)),
                spectre_budget={key: budget[key] for key in
                                ["max_runs", "cpu", "timeout_s", "license_timeout_s"]},
                records=records, pairwise_diagnostics=pairs,
                formal_dvs_qualification="I", continuous_time_qualified=False,
                raw_availability="local-only ignored run and thu-sui archive; not publicly downloadable",
                limits="No simultaneous writer diagnosis, full matrix rerun or performance measurement.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = analyze(args.root)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")
    for record in result["records"]:
        print(record["backend"], record["profile"], record["analysis"]["status"])
    print(json.dumps(result["pairwise_diagnostics"], indent=2))

"""Audit a fresh Spectre matrix against the unchanged analog EVAS checkpoint.

EVAS observations are explicitly reused from the recorded 9c5d6c5 execution.
Every Spectre export goes through the frozen original independent checker.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from analog_boundaries import ROOT, save, sha, verify

sys.path.insert(0, str(ROOT/"experiments/dvs2-spectre-validation"))
from report import settings
from check_results import check, read_waveform
from event_writer_compare import compare


def analyze(root, old_root, output):
    remote = root/"spectre-remote"
    verify(remote, "INPUT_MANIFEST.json")
    verify(remote, "FILE_MANIFEST.json")
    verify(old_root, "RAW_MANIFEST.json")
    if sha(remote/"INPUT_MANIFEST.json") != sha(root/"spectre-input/INPUT_MANIFEST.json"):
        raise ValueError("remote input identity differs")
    frozen = json.loads((remote/"source_identity.json").read_text())
    for rel, expected in frozen.items():
        if rel.endswith(".py") and sha(ROOT/rel) != expected:
            raise ValueError("checker dependency changed: " + rel)
    old_receipt = ROOT/"experiments/pr14-pr15-validation/results/analog-conditions-acceptance-review.json"
    # Historical receipts retain their original bytes in repository gzip archives.
    old_bytes = (old_receipt.read_bytes() if old_receipt.exists() else
                 gzip.decompress(old_receipt.with_suffix(".json.gz").read_bytes()))
    prior = json.loads(old_bytes)
    checkpoint = prior["checkpoint"]
    for rel, expected in checkpoint["source_sha256"].items():
        if sha(ROOT/rel) != expected:
            raise ValueError("EVAS runtime changed since reused execution: " + rel)
    if sha(old_root/"evas-kernel") != checkpoint["kernel_sha256"]:
        raise ValueError("reused kernel identity differs")
    if sha(ROOT/"experiments/dvs2-spectre-validation/check_results.py") != checkpoint["checker_sha256"]:
        raise ValueError("reused checker identity differs")
    old_records = {(r["condition"], r["profile"]): r for r in prior["matrix"]["records"]}
    cases = json.loads((remote/"conditions.json").read_text())
    assert len(cases) == 31 and len(old_records) == 62
    records, pairs = [], []
    for case in cases:
        for profile in ["base", "fine"]:
            work = remote/"runs"/case["id"]/profile
            old = old_records[case["id"], profile]
            for name, expected in old["input_sha256"].items():
                if sha(work/name) != expected:
                    raise ValueError("paired input differs: " + name)
            result = json.loads((work/"result.json").read_text())
            row = dict(backend="spectre", evidence_use="new execution", condition=case["id"], profile=profile,
                       input_sha256={name: sha(work/name) for name in
                                     ["dut.va", "condition.json", "requested_settings.json", "tb.scs"]}, execution=result)
            if result["status"] == "waveform_available":
                path = work/result["waveform"]
                if sha(path) != result["waveform_sha256"]:
                    raise ValueError("waveform identity differs")
                rows = read_waveform(path, "spectre")
                row["analysis"] = check(rows, case)
                log = (work/"spectre.log").read_text()
                actual = settings(log)
                requested = json.loads((work/"requested_settings.json").read_text())
                match = all(actual[k] == v if isinstance(v, str) else
                            math.isclose(actual[k], v, rel_tol=1e-12, abs_tol=0)
                            for k, v in requested.items() if k in actual)
                if not match:
                    raise ValueError("effective settings differ: " + case["id"] + "/" + profile)
                row.update(effective_settings=actual, requested_match=True,
                           warning_codes=dict(Counter(re.findall(r"WARNING \(([^)]+)\)", log))))
                if case["id"] == "v1-main":
                    path = old_root/"matrix-retry-2/runs/v1-main"/profile/"waveform.csv"
                    diagnostic = compare(read_waveform(path, "evas"), rows)
                    diagnostic["interpretation"] = "diagnostic only; interpolation across V1 saturation corners can differ although both sets of exports satisfy the analytic formula"
                    pairs.append(dict(condition="v1-main", profile=profile, **diagnostic))
            else:
                row["analysis"] = dict(status=result["status"], formal_dvs_qualification="I")
            records.append(row)
            records.append(dict(backend="evas", evidence_use="reused execution", **old))
            print(case["id"], profile, "Spectre", row["analysis"]["status"], "EVAS", old["analysis"]["status"], flush=True)
    summary = {b: {p: dict(Counter(r["analysis"]["status"] for r in records
                                  if r["backend"] == b and r["profile"] == p))
                   for p in ["base", "fine"]} for b in ["spectre", "evas"]}
    version = (remote/"version.log").read_text()
    tool = json.loads((remote/"TOOL_IDENTITY.json").read_text())
    save(output, dict(run_id=root.name, conditions=31, configurations_per_backend=62,
         summary=summary, records=records, v1_pairwise_diagnostics=pairs,
         evas_checkpoint=checkpoint, reused_receipt=str(old_receipt.relative_to(ROOT)),
         reused_receipt_sha256=hashlib.sha256(old_bytes).hexdigest(), reused_raw_manifest_sha256=sha(old_root/"RAW_MANIFEST.json"),
         spectre_version=re.search(r"sub-version\s+([^\n]+)", version).group(1).strip(),
         spectre_tool_identity=tool, spectre_budget=json.loads((remote/"STARTED.json").read_text()),
         input_manifest_sha256=sha(remote/"INPUT_MANIFEST.json"),
         spectre_file_manifest_sha256=sha(remote/"FILE_MANIFEST.json"),
         spectre_archive_sha256=sha(root/"spectre-outputs.tar.gz"), frozen_analysis_source=frozen,
         analyzer_sha256=sha(Path(__file__)), formal_dvs_qualification="I", continuous_time_qualified=False,
         artifact_availability="local-only ignored runs and thu-sui; curated receipt/scripts in repository",
         limits="No new main execution, joint candidate integration, other backend run or performance comparison."))
    print(json.dumps(summary, indent=2))


def analyze_features(root, output):
    raw = root/"feature-affected"
    remote = root/"spectre-remote"
    verify(raw, "FILE_MANIFEST.json")
    verify(remote, "FILE_MANIFEST.json")
    specs = {c["id"]: c for c in json.loads((remote/"conditions.json").read_text())}
    records, identities = [], []
    for directory in sorted(p for p in raw.iterdir() if p.is_dir()):
        identity = json.loads((directory/"SOURCE_IDENTITY.json").read_text())
        identities.append(identity)
        for work in sorted((directory/"runs").glob("*/*")):
            case = specs[work.parent.name]
            profile = work.name
            paired = remote/"runs"/case["id"]/profile
            for name in ["dut.va", "condition.json", "requested_settings.json"]:
                if sha(work/name) != sha(paired/name):
                    raise ValueError("affected input differs: " + name)
            result = json.loads((work/"result.json").read_text())
            row = dict(branch=directory.name, source_commit=identity["source_commit"],
                       condition=case["id"], profile=profile, evidence_use="new EVAS execution; paired Spectre from new full matrix",
                       execution_status=result["status"], result=result,
                       input_sha256={n: sha(work/n) for n in ["dut.va", "condition.json", "requested_settings.json"]})
            if result["status"] == "waveform_available":
                waveform = work/result["waveform"]
                if sha(waveform) != result["waveform_sha256"]:
                    raise ValueError("affected waveform drift")
                row["analysis"] = check(read_waveform(waveform, "evas"), case)
                row["effective_settings"] = json.loads((work/"effective.json").read_text())
            else:
                row["analysis"] = dict(status=result["status"], reason=result.get("reason"))
            records.append(row)
            print(directory.name, case["id"], profile, row["analysis"]["status"], flush=True)
    assert len(records) == 12
    summary = {i["branch"]: dict(Counter(r["analysis"]["status"] for r in records
                                        if r["branch"] == i["branch"])) for i in identities}
    save(output, dict(configurations=12, records=records, identities=identities, summary=summary,
         artifact_manifest_sha256=sha(raw/"FILE_MANIFEST.json"),
         analyzer_sha256=sha(Path(__file__)), formal_dvs_qualification="I", continuous_time_qualified=False,
         limits="Branch-local results; all three bases are 508f5b9. No sync to current main or joint integration. Counts cannot be added as an integrated 31/31 result."))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=["matrix", "features"])
    p.add_argument("root", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument("--old-root", type=Path)
    a = p.parse_args()
    if a.action == "matrix": analyze(a.root, a.old_root, a.output)
    else: analyze_features(a.root, a.output)

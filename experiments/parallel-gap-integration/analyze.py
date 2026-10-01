"""Recheck a local EVAS original-31 replay without changing its independent oracle."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments/dvs2-spectre-validation"))
from report import settings
from check_results import check, read_waveform


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, name):
    for relative, identity in json.loads((root / name).read_text()).items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()) or sha(path) != identity["sha256"]:
            raise ValueError("artifact drift: " + relative)


def analyze(source, run, identity_path, output, spectre=None, baseline=None, spectre_receipt=None):
    verify(source, "INPUT_MANIFEST.json")
    verify(run, "FILE_MANIFEST.json")
    cases = json.loads((source / "conditions.json").read_text())
    if len(cases) != 31 or len({c["id"] for c in cases}) != 31:
        raise ValueError("expected the unchanged original 31 conditions")
    if cases != json.loads((run / "conditions.json").read_text()):
        raise ValueError("condition definitions drifted")
    started = json.loads((run / "STARTED.json").read_text())
    execution_identity = json.loads(identity_path.read_text())
    if not execution_identity["source_worktree_clean"] or execution_identity["kernel_sha256"] != started["kernel_sha256"]:
        raise ValueError("execution identity does not match this build")
    if started["source_input_manifest_sha256"] != sha(source / "INPUT_MANIFEST.json"):
        raise ValueError("wrong frozen source identity")
    for relative, digest in started["source_sha256"].items():
        if sha(ROOT / relative) != digest:
            raise ValueError("runtime source changed since execution: " + relative)
    for relative, digest in started["source_sha256"].items():
        content = subprocess.check_output(
            ["git", "show", execution_identity["runtime_commit"] + ":" + relative], cwd=ROOT)
        if hashlib.sha256(content).hexdigest() != digest:
            raise ValueError("runtime commit does not match executed source: " + relative)
    records = []
    for case in cases:
        for profile in ("base", "fine"):
            work = run / "runs" / case["id"] / profile
            original = source / "runs" / case["id"] / profile
            for name in ("dut.va", "condition.json", "requested_settings.json"):
                if sha(work / name) != sha(original / name):
                    raise ValueError("input mismatch: " + str(work / name))
            result = json.loads((work / "result.json").read_text())
            execution = json.loads((work / "execution.json").read_text())
            analysis = dict(status=result["status"], reason=result.get("reason"),
                            formal_dvs_qualification="I")
            if "detail" in result:
                analysis["kernel_error"] = result["detail"]
            if result["status"] == "waveform_available":
                waveform = work / result["waveform"]
                if sha(waveform) != result["waveform_sha256"]:
                    raise ValueError("waveform identity mismatch")
                with waveform.open() as handle:
                    rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(handle)]
                analysis = check(rows, case)
            effective = None
            if result["status"] == "waveform_available":
                effective = json.loads((work / "effective.json").read_text())
                trace = effective.pop("transient")
                effective["transient_summary"] = dict(
                    state_names=trace["state_names"], accepted_steps=trace["accepted_steps"],
                    discarded_trials=trace["discarded_trials"], event_count=len(trace["events"]))
                requested = json.loads((work / "requested_settings.json").read_text())
                if any(effective[k] != requested[j] for k, j in
                       (("vabstol", "vabstol"), ("reltol", "reltol"),
                        ("max_step", "maxstep"), ("stop", "stop"))):
                    raise ValueError("EVAS effective settings drifted")
            records.append(dict(condition=case["id"], profile=profile,
                                input_sha256={name: sha(work/name) for name in
                                              ("dut.va", "condition.json", "requested_settings.json")},
                                effective_settings=effective,
                                execution_status=result["status"],
                                execution={key: execution[key] for key in
                                           ("returncode", "timeout", "elapsed_s", "log_sha256")},
                                analysis=analysis,
                                waveform_sha256=result.get("waveform_sha256")))
    receipt = dict(
        evidence_use="62 new local EVAS requests; unchanged original checker; no new Spectre execution",
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        execution_identity=execution_identity,
        execution_identity_sha256=sha(identity_path),
        runtime_identity=started, source_input_manifest_sha256=sha(source / "INPUT_MANIFEST.json"),
        raw_manifest_sha256=sha(run / "FILE_MANIFEST.json"),
        checker_sha256=sha(ROOT / "experiments/dvs2-spectre-validation/check_results.py"),
        analysis_script_sha256=sha(Path(__file__)), configurations=len(records),
        adapter_sha256={str(path.relative_to(ROOT)): sha(path) for path in (
            ROOT / "experiments/pr14-pr15-validation/matrix.py",
            ROOT / "experiments/dvs2-spectre-validation/remote.py")},
        summary={p: dict(Counter(r["analysis"]["status"] for r in records if r["profile"] == p))
                 for p in ("base", "fine")},
        formal_dvs_qualification="I", raw_availability="local-only", records=records,
    )
    if spectre is not None:
        receipt["paired_comparison"] = compare_archived_spectre(
            source, cases, records, spectre, baseline, spectre_receipt)
    with output.open("x") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(receipt["summary"], ensure_ascii=False))


def compare_archived_spectre(source, cases, candidate, spectre, baseline_path, receipt_path):
    """Recheck unchanged archived exports; never label reuse a new execution."""
    verify(spectre, "INPUT_MANIFEST.json")
    verify(spectre, "FILE_MANIFEST.json")
    prior = json.loads(receipt_path.read_text())["matrix"]
    baseline = json.loads(baseline_path.read_text())
    if sha(spectre / "INPUT_MANIFEST.json") != prior["input_manifest_sha256"]:
        raise ValueError("Spectre frozen input identity differs")
    if sha(spectre / "FILE_MANIFEST.json") != prior["spectre_file_manifest_sha256"]:
        raise ValueError("Spectre archived output identity differs")
    if sha(ROOT / "experiments/dvs2-spectre-validation/check_results.py") != baseline["checkpoint"]["checker_sha256"]:
        raise ValueError("baseline and current checker identities differ")
    for relative, expected in prior["frozen_analysis_source"].items():
        if relative.endswith(".py") and sha(ROOT / relative) != expected:
            raise ValueError("Spectre checker dependency drifted: " + relative)
    tool = json.loads((spectre / "TOOL_IDENTITY.json").read_text())
    if tool != prior["spectre_tool_identity"]:
        raise ValueError("Spectre tool identity differs")
    old_spectre = {(r["condition"], r["profile"]): r for r in prior["records"] if r["backend"] == "spectre"}
    old_evas = {(r["condition"], r["profile"]): r for r in baseline["matrix"]["records"]}
    current = {(r["condition"], r["profile"]): r for r in candidate}
    if len(old_spectre) != 62 or len(old_evas) != 62 or len(current) != 62:
        raise ValueError("paired matrices must each contain all 62 configurations")
    records = []
    unchanged, changed, newly_passed, regressions = [], [], [], []
    for case in cases:
        for profile in ("base", "fine"):
            key = (case["id"], profile)
            work = spectre / "runs" / case["id"] / profile
            frozen = source / "runs" / case["id"] / profile
            for name, expected in current[key]["input_sha256"].items():
                if sha(work/name) != expected or sha(frozen/name) != expected or old_evas[key]["input_sha256"][name] != expected:
                    raise ValueError("paired model/stimulus/settings differ: " + str(key))
            result = json.loads((work / "result.json").read_text())
            analysis = dict(status=result["status"], formal_dvs_qualification="I")
            effective = None
            if result["status"] == "waveform_available":
                waveform = work / result["waveform"]
                if sha(waveform) != result["waveform_sha256"]:
                    raise ValueError("Spectre waveform drifted")
                analysis = check(read_waveform(waveform, "spectre"), case)
                effective = settings((work / "spectre.log").read_text())
                if effective != old_spectre[key]["effective_settings"]:
                    raise ValueError("Spectre effective settings drifted")
                if analysis != old_spectre[key]["analysis"]:
                    raise ValueError("same checker gave a different Spectre result")
            records.append(dict(condition=case["id"], profile=profile,
                evidence_use="reused Spectre execution; exports rechecked under unchanged checker",
                execution_status=result["status"], waveform_sha256=result.get("waveform_sha256"),
                input_sha256={n:sha(work/n) for n in ("dut.va","condition.json","requested_settings.json","tb.scs")},
                effective_settings=effective, analysis=analysis))
            old_ok = old_evas[key]["analysis"]["status"] == "observations_within_targets"
            new_ok = current[key]["analysis"]["status"] == "observations_within_targets"
            label = case["id"] + "/" + profile
            if old_ok:
                if not new_ok:
                    regressions.append(label)
                elif old_evas[key]["result"].get("waveform_sha256") == current[key]["waveform_sha256"]:
                    unchanged.append(label)
                else:
                    changed.append(label)
            elif new_ok:
                newly_passed.append(label)
    return dict(
        spectre_evidence_use="62 reused executions from analog-gap comparison; no new remote launch",
        spectre_receipt=str(receipt_path.relative_to(ROOT)), spectre_receipt_sha256=sha(receipt_path),
        spectre_version=prior["spectre_version"], spectre_tool_identity=tool,
        input_manifest_sha256=sha(spectre/"INPUT_MANIFEST.json"),
        file_manifest_sha256=sha(spectre/"FILE_MANIFEST.json"),
        baseline_receipt=str(baseline_path.relative_to(ROOT)), baseline_receipt_sha256=sha(baseline_path),
        baseline_source_commit=baseline["checkpoint"]["source_commit"],
        baseline_kernel_sha256=baseline["checkpoint"]["kernel_sha256"],
        baseline_summary=baseline["matrix"]["summary"],
        unchanged_prior_passing_waveforms=unchanged, changed_prior_passing_waveforms=changed,
        newly_passing_configurations=newly_passed, regressions=regressions,
        spectre_summary={p:dict(Counter(r["analysis"]["status"] for r in records if r["profile"] == p)) for p in ("base","fine")},
        spectre_records=records, formal_dvs_qualification="I", continuous_time_qualified=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--spectre", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--spectre-receipt", type=Path)
    args = parser.parse_args()
    if any((args.spectre, args.baseline, args.spectre_receipt)) and not all((args.spectre, args.baseline, args.spectre_receipt)):
        parser.error("Spectre comparison requires --spectre, --baseline and --spectre-receipt together")
    analyze(args.source.resolve(), args.run.resolve(), args.identity.resolve(), args.output,
            args.spectre.resolve() if args.spectre else None,
            args.baseline.resolve() if args.baseline else None,
            args.spectre_receipt.resolve() if args.spectre_receipt else None)

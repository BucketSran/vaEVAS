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
from check_results import check


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, name):
    for relative, identity in json.loads((root / name).read_text()).items():
        path = root / relative
        if not path.resolve().is_relative_to(root.resolve()) or sha(path) != identity["sha256"]:
            raise ValueError("artifact drift: " + relative)


def analyze(source, run, output):
    verify(source, "INPUT_MANIFEST.json")
    verify(run, "FILE_MANIFEST.json")
    cases = json.loads((source / "conditions.json").read_text())
    if len(cases) != 31 or len({c["id"] for c in cases}) != 31:
        raise ValueError("expected the unchanged original 31 conditions")
    if cases != json.loads((run / "conditions.json").read_text()):
        raise ValueError("condition definitions drifted")
    started = json.loads((run / "STARTED.json").read_text())
    if started["source_input_manifest_sha256"] != sha(source / "INPUT_MANIFEST.json"):
        raise ValueError("wrong frozen source identity")
    for relative, identity in started["source_sha256"].items():
        if sha(ROOT / relative) != identity:
            raise ValueError("runtime source changed since execution: " + relative)
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
            if result["status"] == "waveform_available":
                waveform = work / result["waveform"]
                if sha(waveform) != result["waveform_sha256"]:
                    raise ValueError("waveform identity mismatch")
                with waveform.open() as handle:
                    rows = [{k: float(v) for k, v in row.items()} for row in csv.DictReader(handle)]
                analysis = check(rows, case)
            records.append(dict(condition=case["id"], profile=profile,
                                execution_status=result["status"],
                                execution={key: execution[key] for key in
                                           ("returncode", "timeout", "elapsed_s", "log_sha256")},
                                analysis=analysis,
                                waveform_sha256=result.get("waveform_sha256")))
    receipt = dict(
        evidence_use="62 new local EVAS requests; unchanged original checker; no new Spectre execution",
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
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
    with output.open("x") as handle:
        json.dump(receipt, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(receipt["summary"], ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    analyze(args.source.resolve(), args.run.resolve(), args.output)

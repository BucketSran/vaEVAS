#!/usr/bin/env python3
"""Rebuild, audit, and seal the tracked tri-form release deterministically."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


PREP_ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = PREP_ROOT.parents[1]
DEFAULT_RELEASES = {
    "r44": PACKAGE_ROOT / "release" / "benchmarkv4",
    "r45": PACKAGE_ROOT / "release" / "benchmarkv4-r45",
    "r47": PACKAGE_ROOT / "release" / "benchmarkv4-r47",
    "r48": PACKAGE_ROOT / "release" / "benchmarkv4-r48",
    "r49": PACKAGE_ROOT / "release" / "benchmarkv4-r49",
    "r50": PACKAGE_ROOT / "release" / "benchmarkv4-r50",
    "r51": PACKAGE_ROOT / "release" / "benchmarkv4-r51",
    "r52": PACKAGE_ROOT / "release" / "benchmarkv4-r52",
    "r53": PACKAGE_ROOT / "release" / "benchmarkv4-r53",
}


def run(*args: object) -> None:
    command = [sys.executable, *(str(arg) for arg in args)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode:
        raise SystemExit(
            f"command failed ({completed.returncode}): {' '.join(command)}\n"
            f"{completed.stdout}{completed.stderr}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-revision",
        choices=tuple(DEFAULT_RELEASES),
        required=True,
    )
    parser.add_argument("--release", type=Path)
    args = parser.parse_args()
    release_revision = str(args.release_revision)
    if release_revision == "r44":
        raise SystemExit(
            "r44 is immutable; audit the tracked release instead of rebuilding it"
        )
    release = (args.release or DEFAULT_RELEASES[release_revision]).expanduser().resolve()
    if (
        release == DEFAULT_RELEASES[release_revision].resolve()
        and (release / "RELEASE_SEAL.json").is_file()
    ):
        raise SystemExit(
            f"{release_revision} is immutable; rebuild it only into an explicit comparison output"
        )
    materializer = PREP_ROOT / "materialize_tri_form_release.py"
    exporter = PREP_ROOT / "export_tri_form_runtime.py"
    runtime_auditor = PREP_ROOT / "audit_runtime_export.py"
    evidence_recorder = PREP_ROOT / "record_runtime_ingestion_evidence.py"
    release_auditor = PREP_ROOT / "audit_tri_form_release.py"

    run(
        materializer,
        "--release-revision",
        release_revision,
        "--output",
        release,
        "--force",
    )
    samples = (("v4-001", "G1"), ("v4-501", "G2"), ("v4-1001", "G5"))
    with tempfile.TemporaryDirectory(prefix="vabench-v4-rebuild-") as raw_tmp:
        tmp = Path(raw_tmp)
        runs: list[Path] = []
        for task, mode in samples:
            runtime = tmp / f"{task.lower()}-{mode.lower()}"
            run(
                exporter,
                "--release",
                release,
                "--task",
                task,
                "--mode",
                mode,
                "--working-token-budget",
                "32768",
                "--output",
                runtime,
            )
            run(
                runtime_auditor,
                "--run",
                runtime,
                "--output",
                runtime / "evidence" / "runtime_export_audit.json",
            )
            runs.append(runtime)

        evidence_args: list[object] = [evidence_recorder]
        for runtime in runs:
            evidence_args.extend(("--run", runtime))
        evidence_args.extend(("--output", release / "RUNTIME_INGESTION_EVIDENCE.json"))
        run(*evidence_args)

    run(
        release_auditor,
        "--release-revision",
        release_revision,
        "--release",
        release,
        "--output",
        release / "AUDIT_REPORT.json",
        "--seal-output",
        release / "RELEASE_SEAL.json",
    )
    print(json.dumps({
        "status": "pass",
        "release_revision": release_revision,
        "release": str(release),
        "samples": samples,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

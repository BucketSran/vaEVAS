#!/usr/bin/env python3
"""Collect declared files and retain the unchanged checker's raw evidence.

The legacy numerical checker still consumes dut.va. The primary artifact is
copied byte for byte from circuit.va; helper names and fixed cases do not change.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def execute(candidate, output, case=None, public=False):
    output = Path(output)
    if output.is_symlink():
        raise ValueError("output directory must not be a symlink")
    output.mkdir(parents=True, exist_ok=True)
    # Harbor may already have written logs here. Keep each attempt in a new
    # directory, so an old success can never supply this attempt's report.
    attempt = Path(tempfile.mkdtemp(prefix="attempt-", dir=output))
    stage = attempt / "submission"
    stage.mkdir()
    raw = attempt / "raw"
    receipt = {"schema_version": 1, "mode": "public" if public else "verifier",
               "attempt": attempt.name, "status": "infrastructure_error",
               "checker_reward": None, "semantic_failure": False,
               "artifact_sha256": {}, "source_unchanged": False}
    sources = {}
    try:
        names = json.loads((HERE / "contract.json").read_text())["candidate_files"]
        if not names or names[0] != "dut.va" or len(names) != len(set(names)):
            raise ValueError("invalid candidate inventory")
        for name in names:
            if Path(name).name != name or name in {".", "..", ""}:
                raise ValueError("this adapter requires declared flat artifact paths")
        artifact_map = json.loads((HERE / "artifacts.json").read_text())
        if artifact_map != {name: "circuit.va" if name == "dut.va" else name for name in names}:
            raise ValueError("artifact mapping differs from the declared contract")
        candidate = Path(candidate)
        for old, new in artifact_map.items():
            path = candidate if old == "dut.va" else candidate.parent / new
            if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                receipt["status"] = "submission_contract_violation"
                raise ValueError("missing, empty, or linked artifact: " + new)
            data = path.read_bytes()
            sources[old] = (path, data)
            (stage / old).write_bytes(data)
            receipt["artifact_sha256"][new] = digest(data)
        argv = [sys.executable, "-B", str(HERE / "verify.py"),
                "--candidate", str(stage / "dut.va"), "--output", str(raw),
                "--tests", str(HERE)]
        if case is not None:
            argv += ["--case", case]
        receipt["argv"] = argv
        # Leave time within the existing 600 s verifier budget to preserve logs.
        with (attempt / "checker.stdout").open("w") as stdout, \
                (attempt / "checker.stderr").open("w") as stderr:
            proc = subprocess.run(argv, stdout=stdout, stderr=stderr,
                                  timeout=570, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        receipt["checker_returncode"] = proc.returncode
        report_path = raw / "report.json"
        report_bytes = report_path.read_bytes()
        report = json.loads(report_bytes)
        receipt["report_sha256"] = digest(report_bytes)
        receipt["raw_report"] = str(report_path.relative_to(output))
        reward = report.get("reward")
        if reward is not None and not (type(reward) is int and reward in (0, 1)):
            raise ValueError("invalid checker reward")
        receipt.update(status=report.get("status", "checker_error"),
                       checker_reward=reward,
                       reason=report.get("reason"),
                       semantic_failure=report.get("status") == "completed" and reward == 0)
        receipt["source_unchanged"] = all(
            not p.is_symlink() and p.is_file() and p.read_bytes() == data
            and (stage / old).read_bytes() == data
            for old, (p, data) in sources.items())
        if not receipt["source_unchanged"]:
            receipt.update(status="evidence_error", semantic_failure=False,
                           reason="submitted bytes changed while the checker ran")
        if proc.returncode != (0 if reward is not None else 2):
            receipt.update(status="execution_error", semantic_failure=False,
                           reason="checker process exit does not match its report")
        # This is an exact copy, including a null reward on an execution error.
        (output / "report.json").write_bytes(report_bytes)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        if receipt["status"] != "submission_contract_violation":
            receipt["status"] = "infrastructure_error"
        receipt.update(reason=f"{type(exc).__name__}: {exc}", semantic_failure=False)
        # Do not leave a prior attempt's report visible as the latest report.
        stale = output / "report.json"
        if stale.exists() and not stale.is_dir():
            stale.unlink()
    qualified = (receipt["status"] == "completed" and receipt["source_unchanged"]
                 and receipt["checker_reward"] in (0, 1))
    if not public:
        receipt["harbor_reward"] = receipt["checker_reward"] if qualified else 0
        (output / "reward.txt").write_text(str(receipt["harbor_reward"]) + "\n")
    write_json(attempt / "boundary.json", receipt)
    write_json(output / "boundary.json", receipt)
    print(json.dumps({k: receipt.get(k) for k in
                     ("status", "checker_reward", "harbor_reward", "semantic_failure", "reason")}))
    return 0 if not public else (0 if qualified and receipt["checker_reward"] == 1 else 1 if qualified else 2)


def main(public=False):
    parser = argparse.ArgumentParser(description="Public diagnostics" if public else "Harbor artifact verifier")
    parser.add_argument("--candidate", type=Path, default=Path("/app/circuit.va"))
    parser.add_argument("--output", type=Path,
                        default=Path("/app/output/public-check" if public else "/logs/verifier"))
    if public:
        parser.add_argument("--case", help="one name from the public cases.json")
    args = parser.parse_args()
    raise SystemExit(execute(args.candidate, args.output, getattr(args, "case", None), public))


if __name__ == "__main__":
    main()

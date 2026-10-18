"""Reuse successful regression evidence only for the same complete tracked inputs and tools."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import subprocess
import sys

# Audited workflow prose and generated registration are checked separately.
# Unknown Markdown remains an input: fixtures may use arbitrary extensions.
EXCLUDED = {
    "evas/docs/development/diagnostic-inventory.json",
    "AGENTS.md", "CONTRIBUTING.md", "docs/contributing/workspaces.md",
    "docs/contributing/evidence.md",
    *('.agents/skills/' + skill + '/SKILL.md' for skill in (
        'evas-develop', 'evas-validate', 'vaevas-workflow',
        'vaevas-prepare-pr', 'vaevas-review-pr',
    )),
}
ENVIRONMENT = (
    "RUSTFLAGS",
    "CARGO_ENCODED_RUSTFLAGS",
    "CARGO_BUILD_TARGET",
    "CARGO_PROFILE_DEV_OPT_LEVEL",
    "CARGO_PROFILE_DEV_DEBUG_ASSERTIONS",
    "CARGO_PROFILE_DEV_OVERFLOW_CHECKS",
    "CC",
    "CXX",
    "AR",
    "LD",
    "PYTHONHASHSEED",
    "PYTHONPATH",
    "ImageOS",
    "ImageVersion",
)


def fingerprint(repo, environment):
    raw = subprocess.check_output(["git", "ls-files", "--stage", "-z"], cwd=repo)
    entries = []
    for row in raw.split(b"\0"):
        if not row:
            continue
        metadata, name = row.split(b"\t", 1)
        mode, _, stage = metadata.decode().split()
        name = os.fsdecode(name)
        if stage != "0" or mode not in ("100644", "100755"):
            raise ValueError("unsupported/conflicted tracked input: " + name)
        if name in EXCLUDED:
            continue
        path = repo / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("tracked input is not a regular file: " + name)
        entries.append(
            [
                name,
                mode,
                stat.S_IMODE(info.st_mode),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    if not entries:
        raise ValueError("no tracked inputs")
    payload = dict(version=2, files=entries, environment=environment)
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return dict(
        key=digest,
        input_count=len(entries),
        environment=environment,
        excluded=sorted(EXCLUDED),
    )


def valid_receipt(receipt, identity, shard):
    return (
        isinstance(receipt, dict)
        and receipt.get("identity") == identity
        and receipt.get("shard") == shard
        and receipt.get("successful") is True
        and isinstance(receipt.get("report_sha256"), str)
    )


def environment(repo):
    return dict(
        python=sys.version,
        platform=platform.platform(),
        machine=platform.machine(),
        kernel_sha256=hashlib.sha256(
            (repo / "evas/rust_core/target/debug/evas-kernel").read_bytes()
        ).hexdigest(),
        rustc=subprocess.check_output(["rustc", "+stable", "-vV"], text=True).strip(),
        cargo=subprocess.check_output(
            ["cargo", "+stable", "--version"], text=True
        ).strip(),
        variables={k: os.environ.get(k, "") for k in ENVIRONMENT},
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["identity", "verify", "record"])
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--shard", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.operation == "identity":
        value = fingerprint(args.repo, dict(**environment(args.repo), shard=args.shard))
        args.identity.parent.mkdir(parents=True, exist_ok=True)
        args.identity.write_text(json.dumps(value, indent=2) + "\n")
        if args.output:
            with args.output.open("a") as stream:
                stream.write("key=" + value["key"] + "\n")
        return 0
    try:
        identity = json.loads(args.identity.read_text())
        report = json.loads(args.report.read_text())
        receipt = (
            json.loads(args.receipt.read_text()) if args.operation == "verify" else None
        )
    except (OSError, ValueError):
        if args.operation == "verify":
            return 1
        raise
    report_hash = hashlib.sha256(args.report.read_bytes()).hexdigest()
    current = fingerprint(args.repo, dict(**environment(args.repo), shard=args.shard))
    if args.operation == "verify":
        if not (
            valid_receipt(receipt, identity, args.shard)
            and current == identity
            and receipt["report_sha256"] == report_hash
            and report.get("complete") is True
            and report.get("successful") is True
        ):
            return 1
    else:
        if report.get("complete") is not True or report.get("successful") is not True:
            raise ValueError("incomplete or failed evidence cannot be recorded")
        if current != identity:
            raise ValueError("tracked inputs changed during verification")
        args.receipt.write_text(
            json.dumps(
                dict(
                    identity=identity,
                    shard=args.shard,
                    successful=True,
                    report_sha256=report_hash,
                    producer_run=os.environ.get("GITHUB_RUN_ID", "local-unpublished"),
                ),
                indent=2,
            )
            + "\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

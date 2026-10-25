"""Bind bounded calibration runs to the audited inputs without overwriting evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def context():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.repository.resolve()
    bundle = Path(__file__).resolve().parent.parent
    summary = json.loads((bundle / "summary.json").read_text())
    try:
        subprocess.run(
            ["git", "diff", "--exit-code", summary["source_commit"], "--",
             "evas/src", "evas/tests", "evas/rust_core", "evas/pyproject.toml"],
            cwd=root, check=True, stdout=subprocess.DEVNULL,
        )
        for name, expected in summary["source_modules"].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                parser.error(f"audited source differs: {name}")
    except (OSError, subprocess.CalledProcessError) as error:
        parser.error(f"cannot verify audited checkout: {error}")
    output = args.output.resolve()
    if output == bundle or bundle in output.parents or output.exists():
        parser.error("output must be a new file outside the frozen evidence directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    sys.dont_write_bytecode = True
    return root, output

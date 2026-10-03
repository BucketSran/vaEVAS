#!/usr/bin/env python3
"""Measure Cargo commands in disposable source copies; never clean a checkout."""
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def measure(command, cwd, log):
    started = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    elapsed = time.perf_counter() - started
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError(f"command failed; see {log}")
    return {"command": command, "elapsed_s": elapsed, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1 or args.output.exists():
        parser.error("repeats must be positive and output must not exist")
    args.output.mkdir(parents=True)
    source = ROOT / "evas/rust_core"
    source_hashes = {
        str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(source.rglob("*"))
        if p.is_file() and "target" not in p.relative_to(source).parts
    }
    receipt = {"base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "source_sha256": source_hashes, "host": platform.platform(),
               "rustc": subprocess.check_output(["rustc", "-Vv"], text=True),
               "boundary": "wall time of Cargo subprocess; test compiles but does not execute tests; disposable target per repeat",
               "measurements": []}
    for repeat in range(args.repeats):
        with tempfile.TemporaryDirectory(prefix="evas-build-") as directory:
            checkout = Path(directory) / "rust_core"
            shutil.copytree(source, checkout, ignore=shutil.ignore_patterns("target"))
            for name, command in (("check", ["cargo", "check", "--locked", "--offline"]),
                                  ("build", ["cargo", "build", "--locked", "--offline"]),
                                  ("test", ["cargo", "test", "--no-run", "--locked", "--offline"])):
                # Separate clean targets make the three clean boundaries comparable.
                command += ["--target-dir", str(Path(directory) / f"target-{name}")]
                for phase in ("clean", "warm", "solver", "operators"):
                    changed = checkout / f"src/{phase}.rs"
                    original = changed.read_bytes() if phase in ("solver", "operators") else None
                    if original is not None:
                        # A real private HIR change with no runtime behavior change.
                        changed.write_bytes(original + b"\n#[allow(dead_code)]\nconst BUILD_MEASUREMENT_MARKER: u8 = 1;\n")
                    try:
                        row = measure(command, checkout, args.output / f"{repeat}-{name}-{phase}.log")
                    finally:
                        if original is not None:
                            changed.write_bytes(original)
                    receipt["measurements"].append({"repeat": repeat, "operation": name, "phase": phase, **row})
                    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
                    print(f"{repeat} {name} {phase}: {row['elapsed_s']:.3f}s", flush=True)
                    if original is not None:
                        # Establish an unchanged, fully built baseline before the next edit.
                        subprocess.run(command, cwd=checkout, check=True, capture_output=True)


if __name__ == "__main__":
    main()

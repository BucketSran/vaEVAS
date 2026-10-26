"""Run cheap source/metadata checks before expensive simulation acceptance."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def commands(paths, *, rust=False, maintenance=False):
    python = [
        p
        for p in paths
        if p.endswith(".py")
        and (ROOT / p).is_file()
        and (
            p.startswith(("scripts/", "evas/src/"))
            or (p.startswith("evas/tests/test_") and len(Path(p).parts) == 3)
        )
    ]
    result = []
    rust_commands = []
    for offset in range(0, len(python), 100):
        result.append(
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "--isolated",
                "--select",
                "E9,F63,F7,F82",
                "--",
                *python[offset : offset + 100],
            ]
        )
    if rust or any(
        p.startswith("evas/rust_core/") and p.endswith(".rs") for p in paths
    ):
        rust_commands.extend(
            [
                [
                    "cargo",
                    "+stable",
                    "fmt",
                    "--manifest-path",
                    "evas/rust_core/Cargo.toml",
                    "--",
                    "--check",
                ],
                [
                    "cargo",
                    "+stable",
                    "clippy",
                    "--locked",
                    "--workspace",
                    "--manifest-path",
                    "evas/rust_core/Cargo.toml",
                    "--all-targets",
                    "--",
                    "-D",
                    "warnings",
                ],
            ]
        )
    if maintenance or any(
        p.startswith(("evas/src/", "evas/rust_core/src/", "evas/tests/")) for p in paths
    ):
        result.extend(
            [
                [sys.executable, "-B", "scripts/diagnostic_inventory.py", "--check"],
                [sys.executable, "-B", "scripts/traceability.py", "--check",
                 "--catalog-data", "evas/capabilities/data"],
            ]
        )
        result.append([sys.executable, "-B", "scripts/verify_validation_version.py"])
    return result + rust_commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--paths", nargs="*", default=[])
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text()) if args.plan else {}
    paths = plan.get("iteration_paths") if plan.get("mode") == "iteration" else None
    paths = plan.get("paths", args.paths) if paths is None else paths
    if args.plan and not paths and plan.get("mode") == "delivery":
        paths = [
            str(p.relative_to(ROOT))
            for directory in ["scripts", "evas/src"]
            for p in (ROOT / directory).rglob("*.py")
        ]
    for path in paths:
        if Path(path).is_absolute() or ".." in Path(path).parts:
            parser.error("paths must stay inside the checkout")
    for command in commands(
        paths,
        rust=plan.get("regression", False) or plan.get("focused", False),
        maintenance=plan.get("maintenance", False),
    ):
        print("Check:", " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

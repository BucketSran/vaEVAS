"""Compile or execute an explicit flat circuit manifest (see examples/)."""

import argparse
import json
from pathlib import Path
import sys

from . import CompileError, Instance, KernelError, compile_sources, solve, transient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["compile", "solve", "transient"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--kernel", type=Path, help="explicit path to the built evas-kernel executable")
    args = parser.parse_args()
    if args.action in ("solve", "transient") and args.kernel is None:
        parser.error("execution requires --kernel; build evas/rust_core first")
    try:
        manifest = json.loads(args.manifest.read_text())
        unknown = set(manifest) - {"models", "instances", "driven", "samples", "tolerances", "transient"}
        if unknown:
            raise ValueError(f"unknown manifest fields: {sorted(unknown)}")
        sources = {(args.manifest.parent / p).resolve(): None for p in manifest["models"]}
        program = compile_sources({str(p): p.read_text() for p in sources},
                                  [Instance(**i) for i in manifest["instances"]])
        if args.action == "compile":
            result = program.to_dict()
        elif args.action == "transient":
            result = transient(program, kernel=args.kernel.resolve(),
                               **manifest["transient"], **manifest.get("tolerances", {}))
        else:
            result = solve(program, manifest["driven"], manifest["samples"],
                           kernel=args.kernel.resolve(), **manifest.get("tolerances", {}))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (CompileError, KernelError, OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

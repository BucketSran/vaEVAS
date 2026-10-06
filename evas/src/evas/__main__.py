"""Compile or execute an explicit flat circuit manifest (see evas/examples/ and evas/validation/smoke/)."""

import argparse
import json
from pathlib import Path
import sys

from . import CompileError, Instance, KernelError, compile_sources, solve, transient
from .manifest import parse_manifest
from .runtime import DEFAULT_TIMEOUT
from .errors import diagnostic


def main():
    if sys.argv[1:2] == ['version']:
        from .identity import main as identity_main
        return identity_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["compile", "solve", "transient", "simulate"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--kernel", type=Path, help="explicit path to the built evas-kernel executable")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="kernel execution timeout in seconds (default: %(default)s)")
    args = parser.parse_args()
    if args.action in ("solve", "transient", "simulate") and args.kernel is None:
        parser.error("execution requires --kernel; build evas/rust_core first")
    try:
        if args.action == 'simulate':
            from .scs import simulate_scs
            result = simulate_scs(args.manifest, kernel=args.kernel.resolve(), timeout=args.timeout)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        manifest = parse_manifest(args.manifest.read_text())
        sources = {(args.manifest.parent / p).resolve(): None for p in manifest["models"]}
        program = compile_sources({str(p): p.read_text() for p in sources},
                                  [Instance(**i) for i in manifest["instances"]])
        if args.action == "compile":
            result = program.to_dict()
        elif args.action == "transient":
            result = transient(program, kernel=args.kernel.resolve(), timeout=args.timeout,
                               **manifest["transient"], **manifest.get("tolerances", {}))
        else:
            result = solve(program, manifest["driven"], manifest["samples"],
                           kernel=args.kernel.resolve(), timeout=args.timeout, **manifest.get("tolerances", {}))
        print(json.dumps(result, indent=2, allow_nan=False))
    except KernelError as exc:
        print(json.dumps(exc.diagnostic, allow_nan=False), file=sys.stderr)
        return 2
    except CompileError as exc:
        print(json.dumps(exc.diagnostic, allow_nan=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(diagnostic('input_io' if isinstance(exc, OSError) else 'input_error', str(exc)), allow_nan=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

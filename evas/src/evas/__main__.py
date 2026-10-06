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
    parser.add_argument("action", choices=["compile", "solve", "transient", "simulate", "lint"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--kernel", type=Path, help="override the bundled evas-kernel with an explicit executable")
    parser.add_argument("--timeout", type=float, default=None, help=f"kernel execution timeout in seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()
    try:
        if args.action == 'lint':
            if args.kernel is not None or args.timeout is not None:
                raise CompileError('lint does not accept --kernel or --timeout; no kernel is checked or executed', code='input_error')
            from .lint import lint_manifest
            print(json.dumps(lint_manifest(args.manifest), allow_nan=False))
            return 0
        if args.timeout is None:
            args.timeout = DEFAULT_TIMEOUT
        if args.action == 'simulate':
            from .scs import simulate_scs
            result = simulate_scs(args.manifest, kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        manifest = parse_manifest(args.manifest.read_text())
        sources = {(args.manifest.parent / p).resolve(): None for p in manifest["models"]}
        program = compile_sources({str(p): p.read_text() for p in sources},
                                  [Instance(**i) for i in manifest["instances"]])
        if args.action == "compile":
            result = program.to_dict()
        elif args.action == "transient":
            result = transient(program, kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout,
                               **manifest["transient"], **manifest.get("tolerances", {}))
        else:
            result = solve(program, manifest["driven"], manifest["samples"],
                           kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout, **manifest.get("tolerances", {}))
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

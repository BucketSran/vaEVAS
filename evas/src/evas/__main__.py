"""Compile or execute an explicit flat circuit manifest (see evas/examples/ and evas/validation/smoke/)."""

import argparse
import json
from pathlib import Path
import re
import sys
import warnings

from . import CompileError, Instance, KernelError, compile_sources, solve, transient
from .runtime import DEFAULT_TIMEOUT
from .errors import DiagnosticArgumentParser, diagnostic
from .limits import MAX_PROOF_WORK_LIMIT


def _proof_work_limit(text):
    """Digits only: 1e9, 1.5, signs and spaces are not integers of work units."""
    if not re.fullmatch(r'[0-9]+', text) or not 1 <= int(text) <= MAX_PROOF_WORK_LIMIT:
        raise argparse.ArgumentTypeError(
            f'--proof-work-limit must be an integer between 1 and {MAX_PROOF_WORK_LIMIT}')
    return int(text)


def main():
    if sys.argv[1:2] == ['xspice']:
        from .xspice.__main__ import main as xspice_main
        return xspice_main(sys.argv[2:])
    if sys.argv[1:2] == ['version']:
        from .identity import main as identity_main
        return identity_main(sys.argv[2:])
    parser = DiagnosticArgumentParser(description=__doc__, epilog="XSPICE compilation: evas-rebuild xspice --help")
    parser.add_argument("action", choices=["compile", "solve", "transient", "simulate", "lint"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--kernel", type=Path, help="override the bundled evas-kernel with an explicit executable")
    parser.add_argument("--timeout", type=float, default=None, help=f"kernel execution timeout in seconds (default: {DEFAULT_TIMEOUT})")
    parser.add_argument("--proof-work-limit", type=_proof_work_limit, default=None,
                        help="transient/simulate only: source-transition proof work limit for this request, "
                             f"1..{MAX_PROOF_WORK_LIMIT} (default 1000000000)")
    args = parser.parse_args()
    if args.proof_work_limit is not None and args.action not in ('transient', 'simulate'):
        parser.error('--proof-work-limit applies only to transient and simulate')
    warning_reports = []
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
            from .scs import ScsIgnoredOptionWarning, simulate_scs
            with warnings.catch_warnings(record=True) as recorded:
                warnings.simplefilter('always', ScsIgnoredOptionWarning)
                try:
                    result = simulate_scs(args.manifest, kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout,
                                          proof_work_limit=args.proof_work_limit)
                finally:
                    warning_reports.extend(w.message.report for w in recorded if isinstance(w.message, ScsIgnoredOptionWarning))
            if warning_reports:
                print(json.dumps(dict(warnings=warning_reports), allow_nan=False), file=sys.stderr)
            print(json.dumps(result, indent=2, allow_nan=False))
            return 0
        from .lint import load_manifest
        manifest, sources = load_manifest(args.manifest)
        program = compile_sources(sources, [Instance(**i) for i in manifest['instances']])
        if args.action == "compile":
            result = program.to_dict()
        elif args.action == "transient":
            if args.proof_work_limit is not None and "proof_work_limit" in manifest["transient"]:
                raise ValueError("proof_work_limit is set in both the manifest and --proof-work-limit")
            result = transient(program, kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout,
                               **manifest["transient"], **manifest.get("tolerances", {}),
                               **({} if args.proof_work_limit is None else dict(proof_work_limit=args.proof_work_limit)))
        else:
            result = solve(program, manifest["driven"], manifest["samples"],
                           kernel=args.kernel.resolve() if args.kernel is not None else None, timeout=args.timeout, **manifest.get("tolerances", {}))
        print(json.dumps(result, indent=2, allow_nan=False))
    except (KernelError, CompileError) as exc:
        report = dict(exc.diagnostic)
        if warning_reports:
            report['warnings'] = warning_reports
        print(json.dumps(report, allow_nan=False), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = diagnostic('input_io' if isinstance(exc, OSError) else 'input_error', str(exc))
        if warning_reports:
            report['warnings'] = warning_reports
        print(json.dumps(report, allow_nan=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

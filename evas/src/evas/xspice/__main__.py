"""Compile VA source artifacts or build them with a matching ngspice SDK."""

import json
from pathlib import Path
import sys
from ..errors import CompileError, DiagnosticArgumentParser, diagnostic
from ..lint import decode_input, read_input_bytes
from . import compile_model, build_model


def main(argv=None):
    parser = DiagnosticArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    comp = commands.add_parser(
        "compile", help="compile the supported VA subset; no external tools required"
    )
    comp.add_argument("sources", nargs="+", type=Path)
    comp.add_argument("-o", "--output", required=True, type=Path)
    comp.add_argument("--module")
    comp.add_argument("--model-name")
    comp.add_argument("--parameter", action="append", default=[], metavar="NAME=VALUE")
    comp.add_argument(
        "--test-hooks",
        action="store_true",
        help="allow explicit rejected-step fault-injection parameters",
    )
    build = commands.add_parser(
        "build", help="build and probe a source artifact with an explicit SDK"
    )
    build.add_argument("artifact", type=Path)
    build.add_argument(
        "--sdk",
        required=True,
        type=Path,
        help="matching ngspice source/binary/ABI JSON",
    )
    build.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compile":
            sources = {
                str(p.resolve()): decode_input(
                    read_input_bytes(p, "source_io"), "source_input"
                )
                for p in args.sources
            }
            params = {}
            for item in args.parameter:
                name, value = item.split("=", 1)
                if name in params:
                    raise ValueError("duplicate parameter: " + name)
                params[name] = float(value)
            metadata = compile_model(
                sources,
                args.output,
                module=args.module,
                parameters=params,
                model_name=args.model_name,
                test_hooks=args.test_hooks,
            )
            result = {
                "status": "compiled",
                "output": str(args.output.resolve()),
                **{
                    k: metadata[k]
                    for k in (
                        "model_name",
                        "ports",
                        "parameters",
                        "ir_schema_version",
                        "test_hooks",
                    )
                },
            }
        else:
            sdk = json.loads(
                decode_input(read_input_bytes(args.sdk, "input_io"), "input_error")
            )
            receipt = build_model(args.artifact, sdk, args.output)
            result = {
                k: receipt[k]
                for k in (
                    "status",
                    "library",
                    "startup_file",
                    "model_include",
                    "abi_probe_passed",
                )
            }
            result["receipt"] = str(Path(receipt["library"]).parent / "build.json")
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except CompileError as exc:
        print(json.dumps(exc.diagnostic, allow_nan=False), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(
            json.dumps(
                diagnostic(
                    "input_io" if isinstance(exc, OSError) else "input_error", str(exc)
                )
            ),
            file=sys.stderr,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

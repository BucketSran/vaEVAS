#!/usr/bin/env python3
"""Recompile EVAS manifests from source into the current IR."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "evas/src"))

from evas.migrate import recompile_manifests  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="new output directory; must not already exist")
    parser.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        help="manifest files or directories; defaults to evas/validation/smoke",
    )
    args = parser.parse_args()
    try:
        batch = recompile_manifests(args.inputs or None, args.output, repo_root=REPO_ROOT)
    except (FileNotFoundError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(batch.to_dict(), indent=2, sort_keys=True))
    return 0 if batch.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

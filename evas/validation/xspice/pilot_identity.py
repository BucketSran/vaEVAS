"""Freeze validator/checker source identity before a native pilot starts."""

import hashlib
import json
from pathlib import Path
import sys


def write_identity(output):
    root = Path(__file__).resolve().parent
    identity = {"python": sys.version, "executable": sys.executable,
                "validation_files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in sorted(root.glob("*.py"))},
                "new_spectre_runs": 0, "availability": "local-only raw evidence"}
    (Path(output) / "checker-identity.json").write_text(json.dumps(identity, indent=2) + "\n")
    return identity

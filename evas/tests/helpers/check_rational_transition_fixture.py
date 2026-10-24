"""Check frozen rational-transition snapshots without rewriting them.

good.json and bad.json stay IR31 historical programs. The VA is compiled
with the current public frontend only to record that generation. This
command does not write either snapshot.
"""
import hashlib
import json
import sys
from pathlib import Path


FROZEN_SCHEMA = 31


def main():
    root = Path(__file__).resolve().parents[3]
    fixtures = root / "evas/tests/fixtures/rational-transition-rollback"
    source_path = fixtures / "dut.va"
    frozen = {}
    for name in ("good.json", "bad.json"):
        path = fixtures / name
        program = json.loads(path.read_text())
        if program.get("schema_version") != FROZEN_SCHEMA:
            raise SystemExit(f"{name} is not the frozen IR31 snapshot")
        frozen[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    sys.path.insert(0, str(root / "evas/src"))
    from evas import Instance, compile_sources

    compiled = compile_sources(
        {"dut.va": source_path.read_text()},
        [Instance("dut", "m", dict(u="u", y="y"))],
    ).to_dict()
    if compiled["schema_version"] == FROZEN_SCHEMA:
        raise SystemExit("current frontend still emits the frozen schema; re-audit before comparing")
    frontend = root / "evas/src/evas/frontend.py"
    print(json.dumps({
        "frozen_schema": FROZEN_SCHEMA,
        "frozen_rewritten": False,
        "current_schema": compiled["schema_version"],
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "good_sha256": frozen["good.json"],
        "bad_sha256": frozen["bad.json"],
        "compiler_sha256": hashlib.sha256(frontend.read_bytes()).hexdigest(),
    }))


if __name__ == "__main__":
    main()

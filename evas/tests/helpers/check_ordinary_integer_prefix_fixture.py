"""Check the ordinary integer-prefix fixture against the public frontend.

The VA file and the request recipe are the working source. The program
object in the JSON is a derived snapshot. This command compares them in
memory and does not write.
"""
import hashlib
import json
import sys
from pathlib import Path


def main():
    evas = Path(__file__).resolve().parents[2]
    fixtures = evas / "rust_core/tests/fixtures"
    source_path = fixtures / "ordinary_integer_prefix_joint.va"
    request_path = fixtures / "ordinary_integer_prefix_joint.request.json"
    request = json.loads(request_path.read_text())
    sys.path.insert(0, str(evas / "src"))
    from evas import Instance, compile_sources

    program = compile_sources(
        {"ordinary_integer_prefix_joint.va": source_path.read_text()},
        [Instance("M", "joint", dict(u="u", y="y", h="h"))],
    )
    compiled = json.loads(json.dumps(program.to_dict()))
    if compiled != request["program"]:
        raise SystemExit("ordinary integer prefix program differs from current public frontend")
    recipe = {key: request[key] for key in ("driven", "samples", "tolerances", "transient")}
    frontend = evas / "src/evas/frontend.py"
    print(json.dumps({
        "program_matches_frontend": True,
        "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
        "recipe_sha256": hashlib.sha256(
            json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "compiler_sha256": hashlib.sha256(frontend.read_bytes()).hexdigest(),
        "schema_version": compiled["schema_version"],
    }))


if __name__ == "__main__":
    main()

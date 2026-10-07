"""Copy maintained verifier modules into self-contained Harbor task tests."""
import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sync(check=False):
    stale = []
    count = 0
    for contract in sorted((ROOT / "benchmark/tasks").glob("*/tests/contract.json")):
        tests = contract.parent
        if tests.parent.name.startswith("va"):
            continue
        tree = ast.parse((tests / "verify.py").read_text())
        modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
        names = {"circuit_task", "adc_linearity", *[m for m in modules if m.startswith("first_batch_")]}
        for name in sorted(names):
            source = ROOT / "benchmark/checkers" / (name + ".py")
            target = tests / source.name
            data = source.read_bytes()
            if not target.exists() or target.read_bytes() != data:
                stale.append(str(target.relative_to(ROOT)))
                if not check:
                    target.write_bytes(data)
        count += 1
    return count, stale


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count, stale = sync(args.check)
    print(f"{count} task runtimes; {len(stale)} {'stale' if args.check else 'updated'} copies")
    if args.check and stale:
        print("\n".join(stale))
        raise SystemExit(1)

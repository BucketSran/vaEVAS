#!/usr/bin/env python3
"""Synchronize public testbench bindings with canonical reference decks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PACKAGE_ROOT / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"
RUNNERS = PACKAGE_ROOT / "runners"
if str(RUNNERS) not in sys.path:
    sys.path.insert(0, str(RUNNERS))

from testbench_security import (  # noqa: E402
    _INSTANCE_RE,
    _instance_parameters,
    _logical_lines,
)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_task(family_id: str) -> Path:
    matches = sorted(SOURCE_ROOT.glob(f"{family_id}-*"))
    if len(matches) != 1:
        raise RuntimeError(f"expected one source task for family {family_id}, found {len(matches)}")
    return matches[0]


def reference_deck(task: Path) -> Path:
    independent = task / "evaluator" / "reference_tb.scs"
    if independent.is_file():
        return independent
    fallback = task / "evaluator" / "score_tb.scs"
    if fallback.is_file():
        return fallback
    raise RuntimeError(f"reference deck is missing: {task}")


def entry_modules(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for file_record in (spec.get("artifact_contract") or {}).get("files") or []:
        for module in file_record.get("modules") or []:
            if module.get("role") == "entry":
                result[str(module["name"]).lower()] = module
    return result


def binding_instances(spec: dict[str, Any], deck: Path) -> list[dict[str, Any]]:
    modules = entry_modules(spec)
    prior = list((spec.get("testbench_binding") or {}).get("instances") or [])
    prior_by_module: dict[str, list[dict[str, Any]]] = {}
    for instance in prior:
        prior_by_module.setdefault(str(instance.get("module_ref") or "").lower(), []).append(instance)

    result: list[dict[str, Any]] = []
    for line in _logical_lines(deck.read_text(encoding="utf-8")):
        match = _INSTANCE_RE.match(line)
        if match is None:
            continue
        name, node_text, kind, trailing = match.groups()
        module = modules.get(kind.lower())
        if module is None:
            continue
        nodes = tuple(token for token in re.split(r"[\s,]+", node_text.strip()) if token)
        candidates = prior_by_module.get(kind.lower()) or []
        previous = candidates.pop(0) if candidates else {}
        connections = sorted(
            previous.get("connections") or [], key=lambda item: int(item.get("position", 0))
        )
        ports = sorted(module.get("ports") or [], key=lambda item: int(item.get("position", 0)))
        if len(connections) == len(nodes):
            connections = [
                {**connection, "net": nodes[index], "position": index}
                for index, connection in enumerate(connections)
            ]
        elif len(ports) == len(nodes):
            connections = [
                {
                    "net": nodes[index],
                    "port_ref": str(port["name"]),
                    "position": index,
                }
                for index, port in enumerate(ports)
            ]

        instance: dict[str, Any] = {
            "name": name,
            "module_ref": str(module["name"]),
            "connections": connections,
        }
        if len(connections) != len(nodes):
            instance["ordered_nets"] = list(nodes)
        parameters = dict(_instance_parameters(trailing))
        if parameters:
            instance["parameter_overrides"] = parameters
        result.append(instance)
    if not result:
        raise RuntimeError(f"reference deck instantiates no declared entry module: {deck}")
    return result


def sync_family(family_id: str, *, write: bool) -> bool:
    task = source_task(family_id)
    spec_path = task / "evaluator" / "family_spec.json"
    spec = read_json(spec_path)
    binding = dict(spec.get("testbench_binding") or {})
    expected = binding_instances(spec, reference_deck(task))
    changed = binding.get("instances") != expected
    if changed and write:
        binding["instances"] = expected
        spec["testbench_binding"] = binding
        write_json(spec_path, spec)
    print(f"{family_id}: {'updated' if changed and write else 'stale' if changed else 'current'}")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family", action="append", required=True)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    changed = sum(sync_family(value.zfill(3), write=args.write) for value in args.family)
    print(f"families={len(args.family)} changed={changed} write={args.write}")
    return 0 if args.write or changed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

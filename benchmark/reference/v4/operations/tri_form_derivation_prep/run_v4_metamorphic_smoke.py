#!/usr/bin/env python3
"""Run stimulus-relative timing metamorphic checks for v4 testbench tasks.

The transformed deck keeps the source waveform amplitudes and event ordering,
while applying a small affine timing change to stay within normal task
constraints. This is a Rust EVAS2 smoke/regression check.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "runners"))

from run_v4_reference_evas_smoke import (  # noqa: E402
    REQUIRED_EVAS_ENGINE,
    REQUIRED_EVAS_VERSION,
    RUST_EVAS_LOG_ENGINE,
    require_evas2_environment,
    required_evas_version_for_release,
    run_one_case,
    task_dir_for_id,
)


TIME_UNITS = {
    "": 1.0,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
}
TIME_RE = re.compile(
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?P<unit>[fpnumk]?)$"
)
PARAM_RE = re.compile(
    r"(?P<key>delay|stop|period|width|rise|fall|maxstep)="
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[fpnumk]?)"
)


def parse_time(value: str) -> float:
    match = TIME_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"invalid time literal: {value}")
    return float(match.group("number")) * TIME_UNITS[match.group("unit")]


def format_time(seconds: float) -> str:
    if seconds == 0:
        return "0"
    for suffix, scale in (("n", 1e-9), ("p", 1e-12), ("u", 1e-6), ("m", 1e-3), ("f", 1e-15)):
        value = seconds / scale
        if abs(value) >= 1 or suffix == "f":
            return f"{value:.9g}{suffix}"
    return f"{seconds:.9g}"


def affine_time(value: str, scale: float, shift_s: float) -> str:
    original = parse_time(value)
    # Keep the initial point at t=0 so source initial conditions remain valid.
    return format_time(0.0 if original == 0 else scale * original + shift_s)


def scale_duration(value: str, scale: float) -> str:
    return format_time(scale * parse_time(value))


def transform_deck(deck: str, scale: float, shift_s: float) -> str:
    """Apply affine timing to PWL/absolute events and scale durations."""
    transformed: list[str] = []
    for line in deck.splitlines():
        if "wave=[" in line:
            prefix, suffix = line.split("wave=[", 1)
            body, tail = suffix.split("]", 1)
            tokens = body.split()
            for index in range(0, len(tokens), 2):
                tokens[index] = affine_time(tokens[index], scale, shift_s)
            line = f"{prefix}wave=[{' '.join(tokens)}]{tail}"

        def replace_parameter(match: re.Match[str]) -> str:
            key = match.group("key")
            value = match.group("value")
            if key in {"delay", "stop"}:
                value = affine_time(value, scale, shift_s)
            else:
                value = scale_duration(value, scale)
            return f"{key}={value}"

        transformed.append(PARAM_RE.sub(replace_parameter, line))
    return "\n".join(transformed).rstrip() + "\n"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_task(
    release: Path,
    task_id: str,
    work_root: Path,
    scale: float,
    shift_s: float,
    timeout_s: int,
    *,
    required_evas_version: str = REQUIRED_EVAS_VERSION,
) -> dict[str, Any]:
    source_task = task_dir_for_id(release, task_id)
    record = read_json(source_task / "task_record.json")
    if record.get("form") != "testbench":
        raise SystemExit(f"{task_id}: metamorphic smoke expects a testbench task")

    task_copy = work_root / source_task.name
    if task_copy.exists():
        shutil.rmtree(task_copy)
    shutil.copytree(source_task, task_copy)
    reference = task_copy / "evaluator" / "reference_tb.scs"
    reference.write_text(
        transform_deck(reference.read_text(encoding="utf-8"), scale, shift_s),
        encoding="utf-8",
    )

    policy = read_json(task_copy / "evaluator" / "score_policy.json")
    case_rows: list[dict[str, Any]] = []
    mutation_ids = [str(value) for value in policy.get("negative_suite_mutation_ids") or []]
    for mutation_id in [None, *mutation_ids]:
        case_id = "correct" if mutation_id is None else mutation_id
        row = run_one_case(
            task_dir=task_copy,
            checker_task_id=str(record.get("checker_task_id") or ""),
            case_id=case_id,
            mutation_id=mutation_id,
            output_root=work_root / "runs" / task_id,
            timeout_s=timeout_s,
            required_evas_version=required_evas_version,
        )
        expected = "reference_pass" if mutation_id is None else "mutation_killed"
        case_rows.append(
            {
                "case_id": case_id,
                "expected_status": expected,
                "observed_status": row["status"],
                "status": "pass" if row["status"] == expected else "fail",
                "checker_notes": row.get("checker_notes") or [],
                "simulator_ok": row.get("simulator_ok", False),
                "checker_ok": row.get("checker_ok", False),
                "evas_engine": row.get("evas_engine", ""),
                "evas_engine_used": row.get("evas_engine_used", ""),
                "evas_version": row.get("evas_version", ""),
                "evas_backend_used": row.get("evas_backend_used", ""),
                "evas_engine_validation": row.get("evas_engine_validation") or {},
            }
        )
    return {
        "task_id": task_id,
        "task_dir": source_task.name,
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": required_evas_version,
        "evas_backend_required": RUST_EVAS_LOG_ENGINE,
        "case_count": len(case_rows),
        "pass_count": sum(row["status"] == "pass" for row in case_rows),
        "status": "pass" if all(row["status"] == "pass" for row in case_rows) else "fail",
        "cases": case_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.05)
    parser.add_argument("--shift-ns", type=float, default=1.0)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    require_evas2_environment()

    if args.scale <= 0:
        raise SystemExit("--scale must be positive")
    work_root = args.work_root.expanduser().resolve()
    if work_root.exists():
        if not args.force:
            raise SystemExit(f"work root exists: {work_root}")
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True)
    release = args.release.expanduser().resolve()
    required_evas_version = required_evas_version_for_release(release)
    rows = [
        run_task(
            release,
            task_id,
            work_root,
            args.scale,
            args.shift_ns * 1e-9,
            args.timeout_s,
            required_evas_version=required_evas_version,
        )
        for task_id in args.task_id
    ]
    report = {
        "schema_version": "v4-metamorphic-evas-smoke-v1",
        "release": str(release),
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": required_evas_version,
        "evas_backend_required": RUST_EVAS_LOG_ENGINE,
        "transform": {"scale": args.scale, "shift_ns": args.shift_ns},
        "task_count": len(rows),
        "case_count": sum(row["case_count"] for row in rows),
        "pass_count": sum(row["status"] == "pass" for row in rows),
        "fail_count": sum(row["status"] != "pass" for row in rows),
        "status": "pass" if all(row["status"] == "pass" for row in rows) else "fail",
        "results": rows,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {key: report[key] for key in ("schema_version", "status", "task_count", "case_count", "pass_count", "fail_count")},
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

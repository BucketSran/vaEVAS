#!/usr/bin/env python3
"""Exercise V4 testbench gold and mutations under affine stimulus timing.

The checker must infer events from the submitted trace.  This runner applies
``t' = scale * t + shift`` to source waveforms and analysis limits, then
replays the same gold and five mutation cases.  A second deck with all source
waveforms held at zero is used to make insufficient excitation an explicit,
non-infrastructure failure.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OPS = ROOT / "benchmark-vabench-release-v4" / "operations" / "tri_form_derivation_prep"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "runners"))
sys.path.insert(0, str(OPS))

from run_v4_reference_evas_smoke import (  # noqa: E402
    case_evas2_runtime,
    overlay_mutation,
    probe_evas2_runtime,
    require_evas2_environment,
    stage_case,
    task_dir_for_id,
)
from runners.simulate_evas import (  # noqa: E402
    effective_evas_engine,
    evaluate_behavior_with_timeout,
    parse_evas_performance_counters,
    parse_evas_timing,
    required_trace_signals_for_checker,
    run_evas,
)
from score_denominator_registry import score_denominator_registry_sha256  # noqa: E402


REQUIRED_EVAS_ENGINE = "evas2"
REQUIRED_EVAS_VERSION = "0.8.7"
LEGACY_EVAS_VERSION = "0.8.3"
REQUIRED_EVAS_BACKEND = "evas-rust"
DEFAULT_RELEASE_REVISION = "r53"
SUPPORTED_RELEASE_REVISIONS = ("r44", "r45", "r47", "r48", "r49", "r50", "r51", "r52", "r53")
EVAS_VERSION_BY_RELEASE = {
    "r52": "0.8.5",
    "r53": REQUIRED_EVAS_VERSION,
}
SOURCE_ROOT = ROOT / "benchmark-vabench-release-v4" / "provenance" / "dut-base-v3-exact-five-hash-bound-v2"

# Scaling the stimulus changes the physical operating point when the DUT owns
# fixed absolute delay/frequency constants. Translation still exercises the
# checker against a shifted time origin without making a false invariance claim.
TRANSLATION_ONLY_FAMILIES = {"077", "081", "358", "361", "362"}
INSUFFICIENT_EXCITATION_NOT_APPLICABLE_REASONS = {
    "077": "autonomous_dither_remains_exercised_at_zero_input",
    "299": "free_running_vco_remains_exercised_at_zero_input",
}


_QUANTITY = re.compile(r"^(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?P<unit>[a-zA-Z]*)$")
_SCALE = {
    "": 1.0,
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
    "ps": 1e-12,
    "fs": 1e-15,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


def compact_evidence_identity(release_revision: str) -> tuple[str, str]:
    if release_revision not in SUPPORTED_RELEASE_REVISIONS:
        raise ValueError(f"unsupported release revision: {release_revision}")
    release_label = (
        "release/benchmarkv4"
        if release_revision == "r44"
        else f"release/benchmarkv4-{release_revision}"
    )
    schema_version = f"v4-{release_revision}-stimulus-metamorphic-compact-v1"
    return release_label, schema_version

def required_evas_version(release_revision: str) -> str:
    return EVAS_VERSION_BY_RELEASE.get(release_revision, LEGACY_EVAS_VERSION)


def effective_affine_scale(family_id: str, requested_scale: float) -> float:
    return 1.0 if family_id in TRANSLATION_ONLY_FAMILIES else requested_scale


def insufficient_excitation_not_applicable_reason(family_id: str) -> str | None:
    return INSUFFICIENT_EXCITATION_NOT_APPLICABLE_REASONS.get(family_id)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def release_provenance(release: Path, release_revision: str) -> dict[str, str]:
    manifest_path = release / "MANIFEST.json"
    if not manifest_path.is_file():
        raise SystemExit(f"release manifest is missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("release_revision") != release_revision:
        raise SystemExit(
            "release manifest revision does not match --release-revision: "
            f"declared={manifest.get('release_revision')!r} selected={release_revision!r}"
        )
    source_registry_sha = str(
        manifest.get("source_score_denominator_registry_sha256") or ""
    )
    if re.fullmatch(r"[0-9a-f]{64}", source_registry_sha) is None:
        raise SystemExit("release manifest lacks a valid source denominator binding")
    if int(release_revision.removeprefix("r")) >= 47:
        current_source_sha = score_denominator_registry_sha256(SOURCE_ROOT)
        if source_registry_sha != current_source_sha:
            raise SystemExit("release manifest is not bound to the current source denominator")
    return {
        "source_score_denominator_registry_sha256": source_registry_sha,
        "release_manifest_sha256": file_sha(manifest_path),
    }


def parse_time(value: str) -> float:
    match = _QUANTITY.fullmatch(value.strip())
    if match is None or match.group("unit").lower() not in _SCALE:
        raise ValueError(f"unsupported time quantity: {value!r}")
    return float(match.group("number")) * _SCALE[match.group("unit").lower()]


def format_time(seconds: float) -> str:
    magnitude = abs(seconds)
    if magnitude >= 1e-6:
        return f"{seconds / 1e-6:.12g}u"
    if magnitude >= 1e-9:
        return f"{seconds / 1e-9:.12g}n"
    if magnitude >= 1e-12:
        return f"{seconds / 1e-12:.12g}p"
    return f"{seconds / 1e-15:.12g}f"


def require_rust_evas2(
    combined: str, *, required_version: str = REQUIRED_EVAS_VERSION
) -> dict[str, str]:
    """Reject metamorphic evidence unless the pinned Rust EVAS actually ran."""
    configured = effective_evas_engine()
    explicit_engine = os.environ.get("EVAS_ENGINE", "").strip().lower()
    default_engine = os.environ.get("VAEVAS_DEFAULT_EVAS_ENGINE", "").strip().lower()
    if (
        configured != REQUIRED_EVAS_ENGINE
        or explicit_engine != REQUIRED_EVAS_ENGINE
        or default_engine != REQUIRED_EVAS_ENGINE
    ):
        raise RuntimeError(
            "EVAS2 evidence requires EVAS_ENGINE=evas2 and "
            "VAEVAS_DEFAULT_EVAS_ENGINE=evas2; "
            f"configured={configured!r} explicit={explicit_engine!r} default={default_engine!r}"
        )
    if f"Version {required_version}" not in combined:
        raise RuntimeError(
            f"EVAS2 evidence missing EVAS {required_version} version marker"
        )
    if f"evas_engine = {REQUIRED_EVAS_BACKEND}" not in combined:
        raise RuntimeError("EVAS2 evidence missing Rust backend marker")
    return {
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": required_version,
        "evas_backend": REQUIRED_EVAS_BACKEND,
    }


def affine_time(value: str, scale: float, shift: float, *, absolute: bool) -> str:
    parsed = parse_time(value)
    return format_time(scale * parsed + shift if absolute else scale * parsed)


def _transform_wave(match: re.Match[str], scale: float, shift: float) -> str:
    # Spectre decks commonly use a bare backslash for PWL line continuation.
    # It is syntax, not a time/value token; emit an equivalent single-line wave.
    tokens = [token for token in match.group("tokens").split() if token != "\\"]
    if len(tokens) % 2:
        raise ValueError(f"PWL wave has an odd token count: {match.group(0)!r}")
    for index in range(0, len(tokens), 2):
        tokens[index] = affine_time(tokens[index], scale, shift, absolute=True)
    return "wave=[" + " ".join(tokens) + "]"


def transform_stimulus(text: str, *, scale: float = 1.37, shift: float = 2e-9) -> str:
    """Apply an affine transform only to stimulus/analysis timing fields."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    transformed = re.sub(
        r"wave=\[(?P<tokens>[^\]]*)\]",
        lambda match: _transform_wave(match, scale, shift),
        text,
    )

    def replace_duration(match: re.Match[str]) -> str:
        return f"{match.group('key')}={affine_time(match.group('value'), scale, shift, absolute=False)}"

    def replace_absolute(match: re.Match[str]) -> str:
        return f"{match.group('key')}={affine_time(match.group('value'), scale, shift, absolute=True)}"

    transformed = re.sub(
        r"\b(?P<key>period|width|rise|fall|maxstep|unit_phase_delay|tr|clk_period|deadzone|pulse_w|poll_dt|lock_window)=(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[a-zA-Z]*)",
        replace_duration,
        transformed,
    )
    transformed = re.sub(
        r"\b(?P<key>delay|stop|clk_delay)=(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?[a-zA-Z]*)",
        replace_absolute,
        transformed,
    )
    return transformed


def suppress_stimulus(text: str) -> str:
    """Keep a legal deck while removing all source excitation."""
    def suppress_dynamic_pwl(match: re.Match[str]) -> str:
        tokens = [token for token in match.group("tokens").split() if token != "\\"]
        if len(tokens) % 2:
            return match.group(0)
        values = tokens[1::2]
        try:
            numeric_values = [float(value) for value in values]
        except ValueError:
            return match.group(0)
        if not numeric_values or max(numeric_values) == min(numeric_values):
            return match.group(0)
        return "vsource dc=0"

    suppressed = re.sub(
        r"vsource\s+type=pwl\s+wave=\[(?P<tokens>[^\]]*)\]",
        suppress_dynamic_pwl,
        text,
    )
    suppressed = re.sub(r"vsource\s+type=pulse\s+[^\n]*", "vsource dc=0", suppressed)
    return suppressed


def run_case(
    *,
    task_dir: Path,
    checker_task_id: str,
    deck_text: str,
    case_id: str,
    mutation_id: str | None,
    output_root: Path,
    timeout_s: int,
    required_evas_version: str = REQUIRED_EVAS_VERSION,
) -> dict[str, Any]:
    case_dir = output_root / case_id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    tb_path, changed = stage_case(task_dir=task_dir, case_dir=case_dir, mutation_id=mutation_id)
    tb_path.write_text(deck_text, encoding="utf-8")
    case_output = case_dir / "output"
    required_signals = required_trace_signals_for_checker(checker_task_id)
    started = time.perf_counter()
    proc = run_evas(
        case_dir,
        tb_path,
        case_output,
        timeout_s,
        required_trace_signals=required_signals,
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    case_runtime = case_evas2_runtime(
        case_output, required_evas_version=required_evas_version
    )
    csv_path = case_output / "tran.csv"
    simulator_ok = (
        proc.returncode == 0
        and csv_path.is_file()
        and case_runtime["evas_runtime_valid"] is True
    )
    checker_score = 0.0
    checker_notes: list[str] = []
    if simulator_ok:
        checker_score, checker_notes = evaluate_behavior_with_timeout(
            checker_task_id, csv_path, timeout_s=timeout_s
        )
    behavior_ok = checker_score > 0.0
    if mutation_id is None:
        status = "reference_pass" if simulator_ok and behavior_ok else (
            "reference_fail" if simulator_ok else "infrastructure_error"
        )
    else:
        status = "mutation_survived" if simulator_ok and behavior_ok else (
            "mutation_killed" if simulator_ok else "infrastructure_error"
        )
    return {
        "case_id": case_id,
        "mutation_id": mutation_id,
        "status": status,
        "simulator_ok": simulator_ok,
        "checker_ok": behavior_ok,
        "checker_notes": checker_notes,
        "changed_artifacts": changed,
        "returncode": proc.returncode,
        "required_trace_signal_count": len(required_signals - {"time"}) if required_signals else 0,
        **case_runtime,
        "timing": parse_evas_timing(combined),
        "performance_counters": parse_evas_performance_counters(combined),
        "wall_time_s": time.perf_counter() - started,
        "stdout_tail": combined[-1200:],
    }


def run_task(
    *,
    release: Path,
    task_id: str,
    output_root: Path,
    scale: float,
    shift: float,
    timeout_s: int,
    required_evas_version: str = REQUIRED_EVAS_VERSION,
) -> dict[str, Any]:
    task_dir = task_dir_for_id(release, task_id)
    record = json.loads((task_dir / "task_record.json").read_text(encoding="utf-8"))
    if record.get("form") != "testbench":
        raise SystemExit(f"{task_id}: expected testbench task")
    checker_task_id = str(record.get("checker_task_id") or "")
    score_policy = json.loads((task_dir / "evaluator" / "score_policy.json").read_text(encoding="utf-8"))
    base_text = (task_dir / "evaluator" / "reference_tb.scs").read_text(encoding="utf-8")
    transformed = transform_stimulus(base_text, scale=scale, shift=shift)
    task_root = output_root / task_id
    task_root.mkdir(parents=True, exist_ok=True)
    cases = [
        run_case(
            task_dir=task_dir,
            checker_task_id=checker_task_id,
            deck_text=transformed,
            case_id="correct",
            mutation_id=None,
            output_root=task_root / "affine",
            timeout_s=timeout_s,
            required_evas_version=required_evas_version,
        )
    ]
    for mutation_id in score_policy.get("negative_suite_mutation_ids") or []:
        cases.append(
            run_case(
                task_dir=task_dir,
                checker_task_id=checker_task_id,
                deck_text=transformed,
                case_id=str(mutation_id),
                mutation_id=str(mutation_id),
                output_root=task_root / "affine",
                timeout_s=timeout_s,
                required_evas_version=required_evas_version,
            )
        )
    family_id = str(record.get("family_id") or "")
    not_applicable_reason = insufficient_excitation_not_applicable_reason(family_id)
    suppressed = base_text if not_applicable_reason else suppress_stimulus(base_text)
    insufficient = None
    if suppressed != base_text:
        insufficient = run_case(
            task_dir=task_dir,
            checker_task_id=checker_task_id,
            deck_text=suppressed,
            case_id="insufficient_excitation",
            mutation_id=None,
            output_root=task_root,
            timeout_s=timeout_s,
            required_evas_version=required_evas_version,
        )
    kills = sum(case["status"] == "mutation_killed" for case in cases[1:])
    infra = sum(case["status"] == "infrastructure_error" for case in cases)
    survivors = sum(case["status"] == "mutation_survived" for case in cases[1:])
    affine_pass = cases[0]["status"] == "reference_pass" and kills == len(cases) - 1 and infra == 0 and survivors == 0
    insufficient_explicit = (
        insufficient is not None
        and insufficient["status"] == "reference_fail"
        and insufficient["simulator_ok"]
    )
    insufficient_valid = insufficient is None or insufficient_explicit
    insufficient_report = (
        {
            "status": "not_applicable",
            "reason": (
                not_applicable_reason
                or "deck_has_no_suppressible_pwl_or_pulse_input_source"
            ),
            "simulator_ok": None,
            "checker_ok": None,
            "case": None,
        }
        if insufficient is None
        else {
            "status": "explicit_failure" if insufficient_explicit else "invalid",
            "simulator_ok": insufficient["simulator_ok"],
            "checker_ok": insufficient["checker_ok"],
            "checker_notes": insufficient["checker_notes"],
            "case": insufficient,
        }
    )
    return {
        "task_id": task_id,
        "family_id": record.get("family_id"),
        "checker_task_id": checker_task_id,
        "affine": {
            "scale": scale,
            "shift_s": shift,
            "status": "pass" if affine_pass else "fail",
            "reference_pass": cases[0]["status"] == "reference_pass",
            "mutation_kill_count": kills,
            "mutation_count": len(cases) - 1,
            "infrastructure_error_count": infra,
            "mutation_survivor_count": survivors,
            "cases": cases,
        },
        "insufficient_excitation": insufficient_report,
        "status": "pass" if affine_pass and insufficient_valid else "fail",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--task-id", action="append", default=[])
    parser.add_argument("--family-range", default="001-400")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--compact-output", type=Path)
    parser.add_argument(
        "--base-report",
        type=Path,
        help="replace selected task results in a prior full raw report",
    )
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--scale", type=float, default=1.37)
    parser.add_argument("--shift", type=float, default=2e-9)
    parser.add_argument("--timeout-s", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--release-revision",
        choices=SUPPORTED_RELEASE_REVISIONS,
        default=DEFAULT_RELEASE_REVISION,
        help="release identity written into evidence (default: r52)",
    )
    args = parser.parse_args()
    release_label, compact_schema = compact_evidence_identity(args.release_revision)
    require_evas2_environment()
    evas_version = required_evas_version(args.release_revision)
    runtime = probe_evas2_runtime(required_evas_version=evas_version)
    release = args.release.expanduser().resolve()
    provenance = release_provenance(release, args.release_revision)
    if args.work_root.exists():
        shutil.rmtree(args.work_root)
    args.work_root.mkdir(parents=True)
    task_ids = list(args.task_id)
    if not task_ids:
        left, separator, right = args.family_range.partition("-")
        if not separator:
            right = left
        start, stop = int(left), int(right)
        if start < 1 or stop < start or stop > 400:
            raise SystemExit(f"invalid family range: {args.family_range}")
        task_ids = [f"v4-{500 + family:03d}" for family in range(start, stop + 1)]

    def execute(task_id: str) -> dict[str, Any]:
        family = f"{int(task_id.split('-', 1)[1]) - 500:03d}"
        effective_scale = effective_affine_scale(family, args.scale)
        return run_task(
            release=release,
            task_id=task_id,
            output_root=args.work_root,
            scale=effective_scale,
            shift=args.shift,
            timeout_s=args.timeout_s,
            required_evas_version=evas_version,
        )

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(execute, task_ids))
    if args.base_report:
        base = json.loads(args.base_report.read_text(encoding="utf-8"))
        combined = {
            str(item["task_id"]): item
            for item in base.get("results") or []
        }
        combined.update({str(item["task_id"]): item for item in results})
        expected = {f"v4-{value:03d}" for value in range(501, 901)}
        if set(combined) != expected:
            raise SystemExit(
                "base report plus replacements must cover exactly v4-501 through v4-900"
            )
        results = [combined[task_id] for task_id in sorted(combined, key=lambda value: int(value.split("-", 1)[1]))]
    report = {
        "schema_version": "v4-stimulus-metamorphic-evidence-v1",
        "evas_engine": REQUIRED_EVAS_ENGINE,
        "evas_engine_used": REQUIRED_EVAS_ENGINE,
        "evas_version": evas_version,
        "evas_backend": REQUIRED_EVAS_BACKEND,
        "runtime": runtime,
        "release": release_label,
        "release_revision": args.release_revision,
        **provenance,
        "transform": {
            "default_scale": args.scale,
            "shift_s": args.shift,
            "translation_only_family_ids": sorted(TRANSLATION_ONLY_FAMILIES),
            "insufficient_excitation_not_applicable_family_ids": sorted(
                INSUFFICIENT_EXCITATION_NOT_APPLICABLE_REASONS
            ),
        },
        "task_count": len(results),
        "pass_count": sum(item["status"] == "pass" for item in results),
        "fail_count": sum(item["status"] != "pass" for item in results),
        "status": "pass" if all(item["status"] == "pass" for item in results) else "fail",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.compact_output:
        compact_results = [
            {
                "task_id": item["task_id"],
                "family_id": item["family_id"],
                "checker_task_id": item["checker_task_id"],
                "status": item["status"],
                "affine": {
                    key: item["affine"][key]
                    for key in (
                        "status",
                        "reference_pass",
                        "mutation_kill_count",
                        "mutation_count",
                        "infrastructure_error_count",
                        "mutation_survivor_count",
                    )
                },
                "insufficient_excitation": {
                    key: item["insufficient_excitation"].get(key)
                    for key in ("status", "simulator_ok", "checker_ok", "reason")
                    if key in item["insufficient_excitation"]
                },
            }
            for item in results
        ]
        compact = {
            "schema_version": compact_schema,
            "status": report["status"],
            "certification_policy": "rust_evas2_only",
            "evas_engine": REQUIRED_EVAS_ENGINE,
            "evas_engine_used": REQUIRED_EVAS_ENGINE,
            "evas_version": evas_version,
            "evas_backend": REQUIRED_EVAS_BACKEND,
            "runtime": runtime,
            "release": release_label,
            "release_revision": args.release_revision,
            **provenance,
            "input_report_sha256": file_sha(args.output),
            "transform": report["transform"],
            "summary": {
                "task_count": len(results),
                "affine_gold_pass_count": sum(
                    item["affine"]["reference_pass"] for item in results
                ),
                "affine_mutation_kill_count": sum(
                    item["affine"]["mutation_kill_count"] for item in results
                ),
                "affine_infrastructure_error_count": sum(
                    item["affine"]["infrastructure_error_count"] for item in results
                ),
                "insufficient_excitation_rejection_count": sum(
                    item["insufficient_excitation"]["status"] == "explicit_failure"
                    for item in results
                ),
                "insufficient_excitation_not_applicable_count": sum(
                    item["insufficient_excitation"]["status"] == "not_applicable"
                    for item in results
                ),
            },
            "results": compact_results,
        }
        args.compact_output.parent.mkdir(parents=True, exist_ok=True)
        args.compact_output.write_text(
            json.dumps(compact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps({
        "schema_version": report["schema_version"],
        "status": report["status"],
        "task_count": report["task_count"],
        "pass_count": report["pass_count"],
        "fail_count": report["fail_count"],
        "output": str(args.output),
        "tasks": [
            {
                "task_id": item["task_id"],
                "status": item["status"],
                "affine": item["affine"]["status"],
                "insufficient_excitation": item["insufficient_excitation"]["status"],
                "mutation_kill_count": item["affine"]["mutation_kill_count"],
                "mutation_count": item["affine"]["mutation_count"],
            }
            for item in results
        ],
    }, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

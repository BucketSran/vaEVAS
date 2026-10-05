"""Local va07 development acceptance through the circuit harness, without Spectre."""

import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
import types
from pathlib import Path

# Compile the canonical source bytes directly so a cached import from before an
# edit cannot be mistaken for the source recorded in the execution receipt.
_CHECKER_PATH = Path(__file__).with_name("triangle_oscillator.py").resolve()
_CHECKER_SOURCE = _CHECKER_PATH.read_bytes()
checker = types.ModuleType("_triangle_evas_oracle")
checker.__file__ = str(_CHECKER_PATH)
exec(compile(_CHECKER_SOURCE, str(_CHECKER_PATH), "exec"), checker.__dict__)
_LOADED_TASK = {
    Path(__file__).resolve(): checker.sha(Path(__file__)),
    _CHECKER_PATH: hashlib.sha256(_CHECKER_SOURCE).hexdigest(),
}

CASE_FIELDS = {
    "name",
    "lo",
    "hi",
    "initial",
    "direction",
    "control",
    "stop",
    "maxstep",
    "ttol",
    "vtol",
    "wave_atol",
    "time_atol",
    "reltol",
    "vabstol",
    "iabstol",
    "method",
    "netlist",
}


def prepare_requests(case):
    """Freeze both observation grids before running either candidate."""
    if set(case) != CASE_FIELDS:
        raise ValueError(f"case fields differ: {sorted(set(case) ^ CASE_FIELDS)}")
    if case["name"] != "constant-tighter":
        raise ValueError("only constant-tighter has a local EVAS acceptance mapping")
    times = sorted(
        {
            0.0,
            case["stop"],
            *[i * case["maxstep"] for i in range(int(case["stop"] / case["maxstep"]) + 1)],
        }
    )
    baseline = {
        "models": ["dut.va"],
        "instances": [
            {
                "name": "dut",
                "module": "triangle",
                "connections": {"ctl": "ctl", "z": "z", "count": "count", "r": "0"},
                "parameters": {
                    "lower": case["lo"],
                    "upper": case["hi"],
                    "initial_voltage": case["initial"],
                    "direction": case["direction"],
                    "ttol": case["ttol"],
                    "vtol": case["vtol"],
                },
            }
        ],
        "transient": {
            "sources": {"ctl": copy.deepcopy(case["control"])},
            "output_times": times,
            "stop": case["stop"],
            "max_step": case["maxstep"],
        },
        "tolerances": {"vabstol": 1e-8, "reltol": 0},
    }
    observation = copy.deepcopy(baseline)
    additions = [
        t + offset
        for t in checker.roots(case)
        for offset in [-case["time_atol"] / 2, case["time_atol"] / 2]
        if 0 < t + offset < case["stop"]
    ]
    observation["transient"]["output_times"] = sorted(set(times + additions))
    mapping = {
        "source_case": copy.deepcopy(case),
        "spectre_settings": {k: case[k] for k in ["vabstol", "reltol", "iabstol", "method"]},
        "evas_requested_settings": dict(baseline["tolerances"]),
        "unsupported": {
            "iabstol": {
                "requested": case["iabstol"],
                "reason": "EVAS transient has no current tolerance option",
            },
            "method": {
                "requested": case["method"],
                "reason": "EVAS transient has no Spectre integration-method option",
            },
        },
        "basis": (
            "Fixed mapping from "
            "experiments/backends/dvs2-spectre-validation/oscillator_compatibility.py: "
            "vabstol=1e-8, reltol=0; no per-candidate tuning."
        ),
        "settings_evidence": (
            "The recorded manifest is forwarded by the captured EVAS CLI/runtime; "
            "EVAS does not independently echo effective tolerances."
        ),
        "netlist": (
            "Spectre source netlist retained as source configuration; not executed "
            "or translated by the harness."
        ),
        "observation": {
            "baseline_points": len(times),
            "added_times": additions,
            "basis": (
                "Independent analytic roots +/- time_atol/2; same grid for both "
                "candidates; no engine event times used."
            ),
        },
        "scope": (
            "Development acceptance of one case; neither equivalent Spectre settings "
            "nor continuous-time numerical qualification."
        ),
    }
    return {"baseline": baseline, "observation": observation}, mapping


def _rows(data, times):
    nodes = data["nodes"]
    if (
        not isinstance(nodes, list)
        or any(not isinstance(n, str) for n in nodes)
        or len(set(nodes)) != len(nodes)
        or not {"z", "count"} <= set(nodes)
        or data["transient"]["times"] != times
        or len(data["solutions"]) != len(times)
    ):
        raise ValueError("incomplete task signals or observation grid")
    rows = []
    for t, solution in zip(times, data["solutions"], strict=True):
        voltages = solution["voltages"]
        if len(voltages) != len(nodes) or any(
            type(v) not in (float, int) or not math.isfinite(v) for v in voltages
        ):
            raise ValueError("invalid task voltage row")
        rows.append(dict(time=t, **dict(zip(nodes, voltages, strict=True))))
    return rows


def assess(baseline, observation, case):
    """Use sampled count and z only. Self-reported event records are diagnostic."""
    requests, _ = prepare_requests(case)
    result = {"execution": "ok", "verdict": "not_evaluated", "timing_authority": "sampled_count"}
    try:
        base_rows = _rows(baseline, requests["baseline"]["transient"]["output_times"])
        obs_rows = _rows(observation, requests["observation"]["transient"]["output_times"])
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        return dict(result, execution="invalid_result", reason=str(error))
    # The unchanged oracle checks waveform and count in each run. The baseline's
    # first changed sample cannot resolve event timing; only the supplemented run
    # supplies that evidence. Never pass the optional event_times argument.
    for label, rows in [("baseline", base_rows), ("observation", obs_rows)]:
        try:
            result[label] = checker.evaluate(rows, case)
        except ValueError as error:
            result[label] = {"passed": False, "reason": str(error)}
    common = {r["time"]: r for r in obs_rows}
    discrepancy = max(abs(r["z"] - common[r["time"]]["z"]) for r in base_rows)
    result["common_grid_max_voltage_difference_v"] = discrepancy
    result["baseline_waveform_and_count_passed"] = (
        result["baseline"].get("max_voltage_error_v", math.inf) <= case["wave_atol"]
    )
    result["verdict"] = (
        "pass"
        if (result["baseline_waveform_and_count_passed"] and result["observation"]["passed"])
        else "fail"
    )
    # A first changed sample is an upper bound, not the event's exact time. Its
    # preceding old-count sample supplies the lower bound. Sparse evidence can
    # confuse a legal 150ns lead with an illegal 1us lead, so keep it inconclusive.
    if result["verdict"] == "pass":
        brackets = [
            [a["time"], b["time"]]
            for a, b in zip(obs_rows, obs_rows[1:], strict=False)
            if round(a["count"]) != round(b["count"])
        ]
        expected = checker.roots(case)
        result["observed_event_brackets_s"] = brackets
        bounded = len(brackets) == len(expected) and all(
            max(abs(a - root), abs(b - root)) <= case["time_atol"]
            for (a, b), root in zip(brackets, expected, strict=True)
        )
        if not bounded:
            result.update(
                verdict="inconclusive",
                reason="sampled count does not bound event timing within time_atol",
            )
    if discrepancy > case["wave_atol"]:
        result.update(
            verdict="inconclusive",
            reason="observation-grid change altered shared waveform samples beyond wave_atol",
        )
    return result


def run_candidate(
    *,
    harness_checkout,
    evas_checkout,
    kernel,
    candidate,
    case_name,
    output,
    timeout_s,
    max_output_bytes,
):
    """Run one candidate twice and preserve execution failures without grading."""
    root = Path(__file__).resolve().parents[2]
    harness_checkout = Path(harness_checkout).resolve()
    # Explicit dependency selection; refuse a cached import from another checkout.
    sys.path.insert(0, str(harness_checkout))
    try:
        from alphaapollo.common.execution.chips import current_evas as harness
        from alphaapollo.common.execution.chips.journal import atomic_json
    finally:
        sys.path.pop(0)
    expected = harness_checkout / "alphaapollo/common/execution/chips/current_evas.py"
    if Path(harness.__file__).resolve() != expected:
        raise ValueError("loaded harness does not match the selected checkout")
    cases_path = root / "benchmark/tasks/va07-triangle-repair/tests/cases.json"
    matches = [c for c in json.loads(cases_path.read_text()) if c["name"] == case_name]
    if len(matches) != 1:
        raise ValueError(f"unknown or duplicate case: {case_name}")
    case = matches[0]
    requests, mapping = prepare_requests(case)
    if (
        not math.isfinite(timeout_s)
        or timeout_s <= 0
        or type(max_output_bytes) is not int
        or max_output_bytes <= 0
    ):
        raise ValueError("positive finite timeout and positive integer output limit are required")
    candidate = Path(candidate).resolve()
    candidate_bytes = candidate.read_bytes()
    output = Path(output).resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    inputs = output / "inputs"
    inputs.mkdir()
    (inputs / "dut.va").write_bytes(candidate_bytes)
    (inputs / "cases.json").write_bytes(cases_path.read_bytes())
    atomic_json(inputs / "mapping.json", mapping)
    for name, request in requests.items():
        atomic_json(inputs / f"{name}.json", request)
    report = {
        "schema_version": 1,
        "task": "va07-triangle-repair",
        "case": case_name,
        "execution": "infrastructure_error",
        "verdict": "not_evaluated",
        "benchmark_score": None,
        "purpose": "development_backend_acceptance",
        "availability": "local-only",
        "candidate_sha256": checker.sha(inputs / "dut.va"),
        "cases_sha256": checker.sha(inputs / "cases.json"),
        "mapping": mapping,
        "executions": {},
        "timeout_s_per_execution": timeout_s,
        "planned_executions": ["baseline", "observation"],
        "limits": (
            "One configuration, two observation grids. No Spectre equivalence, "
            "formal benchmark score, holdout evidence, or continuous-time "
            "qualification."
        ),
    }
    try:
        report["benchmark_source"] = harness.snapshot_repository(
            root,
            output / "source/benchmark",
            (
                "benchmark/checkers/triangle_oscillator.py",
                "benchmark/checkers/triangle_evas.py",
                "benchmark/checkers/test_triangle_evas.py",
                "benchmark/tasks/va07-triangle-repair",
            ),
        )
        for path, digest in _LOADED_TASK.items():
            recorded = report["benchmark_source"]["files"][str(path.relative_to(root))]["sha256"]
            if digest != recorded:
                raise ValueError(
                    "task source identity changed after module load; use a fresh process"
                )
        raw = {}
        common_identity = None
        for name in requests:
            execution = harness.run_evas(
                checkout=evas_checkout,
                kernel=kernel,
                manifest=inputs / f"{name}.json",
                output=output / name,
                timeout_s=timeout_s,
                max_output_bytes=max_output_bytes,
                python=sys.executable,
            )
            report["executions"][name] = execution
            if execution["execution"] != "ok":
                report.update(
                    execution=execution["execution"], reason=f"{name} execution did not complete"
                )
                break
            receipt = json.loads((output / name / "request.json").read_text())
            identity = {
                "evas": receipt["source"]["files"],
                "kernel": receipt["kernel"]["sha256"],
                "harness": receipt["harness"]["files"],
                "environment": receipt["environment"],
                "python": receipt["python"],
            }
            if common_identity is not None and identity != common_identity:
                raise ValueError("execution identity changed between observation grids")
            common_identity = identity
            raw_path = output / name / execution["raw_result"]
            if checker.sha(raw_path) != execution["artifacts"][execution["raw_result"]]["sha256"]:
                raise ValueError("raw result digest mismatch before task assessment")
            raw[name] = json.loads(raw_path.read_text())
        else:
            if any(checker.sha(path) != digest for path, digest in _LOADED_TASK.items()):
                raise ValueError("task source identity changed during execution")
            report.update(assess(raw["baseline"], raw["observation"], case))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        report.update(execution="infrastructure_error", verdict="not_evaluated", reason=str(error))
    report["artifacts"] = {
        str(path.relative_to(output)): {"sha256": checker.sha(path), "bytes": path.stat().st_size}
        for path in sorted(output.rglob("*"))
        if path.is_file()
    }
    atomic_json(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness-checkout", type=Path, required=True)
    parser.add_argument("--evas-checkout", type=Path, required=True)
    parser.add_argument("--kernel", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--case", dest="case_name", required=True, choices=["constant-tighter"])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-s", type=float, required=True)
    parser.add_argument("--max-output-bytes", type=int, required=True)
    try:
        result = run_candidate(**vars(parser.parse_args()))
    except (OSError, ValueError, ImportError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps({k: result[k] for k in ["execution", "verdict", "benchmark_score"]}))
    return 0 if result["verdict"] == "pass" else 1 if result["verdict"] == "fail" else 2


if __name__ == "__main__":
    raise SystemExit(main())

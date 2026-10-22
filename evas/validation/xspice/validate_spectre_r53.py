"""Admit and score native same-source references for the frozen r53 circuits."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re

from check import read_ng, read_spectre, sample
from r53_reference import TIME_BUDGET, VOLTAGE_BUDGET, score_wave, score_tanh


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def admit(directory, expected):
    """Require complete native receipts and every original VA input byte."""
    d = Path(directory)
    names = ["tb.scs", *expected["sources"]]
    for name in names:
        if sha(d / name) != expected["files"][name]:
            raise ValueError("native input differs: " + name)
    result = json.loads((d / "result.json").read_text())
    if type(result.get("exit_code")) is not int or result["exit_code"] != 0 or result.get("timed_out") is not False:
        raise ValueError("native process failed or timed out")
    log = (d / "spectre.log").read_text()
    version = re.search(r"^Version (\S+)", log, re.M)
    if not version or "Spectre (R) Circuit Simulator" not in log or not re.search(r"^spectre completes with 0 errors,", log, re.M) or "Total time required for tran analysis" not in log:
        raise ValueError("native completion/version evidence missing")
    started = json.loads((d / "STARTED.json").read_text())
    if any(started.get("files", {}).get(name) != sha(d / name) for name in names):
        raise ValueError("STARTED input identity differs")
    tool = d.parent.parent / "TOOL_IDENTITY.json"
    identity = json.loads(tool.read_text())
    if not re.fullmatch(r"[0-9a-f]{64}", identity.get("spectre_sha256", "")):
        raise ValueError("native tool identity missing")
    raw = d / "psf/tran.tran.tran"
    if not raw.is_file() or not raw.stat().st_size:
        raise ValueError("native waveform missing")
    # PSF header distinguishes actual tolerances from requested global options.
    header = raw.read_text().split("TYPE\n", 1)[0]
    effective = {}
    for key in ("reltol", "abstol(V)", "abstol(I)", "maxstep", "errpreset", "method", "tolerance.relative"):
        match = re.search(r'^"' + re.escape(key) + r'"\s+([^\n]+)$', header, re.M)
        if not match:
            raise ValueError("effective setting missing: " + key)
        value = match.group(1)
        effective[key] = value.strip('"') if value.startswith('"') else float(value)
    return {"version": version.group(1), "effective": effective,
            "files": {name: sha(d / name) for name in names},
            "wave_sha256": sha(raw), "log_sha256": sha(d / "spectre.log"),
            "result_sha256": sha(d / "result.json"), "started_sha256": sha(d / "STARTED.json"),
            "tool_identity_sha256": sha(tool), "spectre_binary_sha256": identity["spectre_sha256"]}


def score_states(wave, names, spec):
    required = ["time", *names]
    if any(name not in wave for name in required) or not wave["time"]:
        return {"passed": False, "errors": ["missing state vectors"]}
    if any(len(wave[name]) != len(wave["time"]) or any(not math.isfinite(v) for v in wave[name]) for name in required):
        return {"passed": False, "errors": ["nonfinite/inconsistent state vectors"]}
    values = list(zip(*(wave[name] for name in names)))
    if not names or len(values[0]) != len(spec["initial"]):
        return {"passed": False, "errors": ["state dimensions"]}
    observed = [[t, list(v)] for i, (t, v) in enumerate(zip(wave["time"], values)) if i and v != values[i - 1]]
    expected = spec["events"]
    errors = []
    if any(b < a for a, b in zip(wave["time"], wave["time"][1:])):
        errors.append("nonmonotone state time")
    if any(abs(a - b) > VOLTAGE_BUDGET for a, b in zip(values[0], spec["initial"])):
        errors.append("initial state")
    if spec.get("integer") and any(v != math.trunc(v) for row in values for v in row):
        errors.append("noninteger counter state")
    if len(observed) != len(expected):
        errors.append("event count")
    time_error = max((abs(a[0] - b[0]) for a, b in zip(observed, expected)), default=0.0)
    value_error = max((abs(x - y) for a, b in zip(observed, expected) for x, y in zip(a[1], b[1])), default=0.0)
    if time_error > TIME_BUDGET:
        errors.append("event time")
    if value_error > VOLTAGE_BUDGET:
        errors.append("captured state")
    return {"passed": not errors, "errors": errors, "observed": observed, "expected": expected,
            "max_time_error_s": time_error, "max_state_error": value_error}


def compare_states(native, ng):
    a, b = native["observed"], ng["observed"]
    same = len(a) == len(b) and all(len(x[1]) == len(y[1]) for x, y in zip(a, b))
    dt = max((abs(x[0] - y[0]) for x, y in zip(a, b)), default=0.0)
    dv = max((abs(u - v) for x, y in zip(a, b) for u, v in zip(x[1], y[1])), default=0.0)
    return {"passed": same and dt <= TIME_BUDGET and dv <= VOLTAGE_BUDGET,
            "same_event_count_and_dimensions": same, "max_event_time_s": dt, "max_state_V": dv}


def compare_waves(a, b, names, stop, grid=1e-9):
    if not names or any(name not in wave for wave in (a, b) for name in ("time", *names)):
        return {"passed": False, "errors": ["missing pair vectors"]}
    if any(not wave["time"] or any(len(wave[n]) != len(wave["time"]) or any(not math.isfinite(v) for v in wave[n]) for n in ("time", *names)) or any(x > y for x, y in zip(wave["time"], wave["time"][1:])) for wave in (a, b)):
        return {"passed": False, "errors": ["nonfinite/inconsistent pair vectors"]}
    if any(abs(wave["time"][0]) > 1e-15 or abs(wave["time"][-1] - stop) > 1e-15 for wave in (a, b)):
        return {"passed": False, "errors": ["pair range"]}
    times = sorted({*(i * grid for i in range(int(math.floor(stop / grid)) + 1)), stop})
    maxima = {name: max(abs(sample(a, name, t) - sample(b, name, t)) for t in times) for name in names}
    return {"passed": all(e <= VOLTAGE_BUDGET for e in maxima.values()), "max_difference_V": maxima,
            "grid_s": grid, "points": len(times), "voltage_bound_V": VOLTAGE_BUDGET,
            "scope": "Linear interpolation on existing common 1ns grid, including stop; each backend separately checked at all native points against the unchanged event-time envelope."}


def selection_verdict(results, selected, protocol):
    selection_passed = bool(results) and len(results) == len(selected) and all(r["passed"] for r in results.values())
    complete = set(results) == set(protocol["cases"]) and len(results) == protocol["fixed_denominator"]
    return {"passed": selection_passed and complete, "selection_passed": selection_passed,
            "complete_selection": complete}


def analyze(phase, batch, output, cases, protocol_path=None):
    phase, batch, output = map(lambda p: Path(p).resolve(), (phase, batch, output))
    output.mkdir(parents=True, exist_ok=False)
    protocol_path = Path(protocol_path).resolve() if protocol_path else phase / "protocol.json"
    protocol = json.loads(protocol_path.read_text())
    identities = {p.name: sha(p) for p in Path(__file__).parent.glob("*.py")}
    (output / "checker-identity.json").write_text(json.dumps(identities, indent=2) + "\n")
    for name, identity in protocol["prior_local_checker_sha256"].items():
        if sha(Path(__file__).parent / name) != identity:
            raise ValueError("original checker changed: " + name)
    results = {}
    for case in cases:
        spec = protocol["cases"][case]
        d = Path(protocol.get("reference_directories", {}).get(case, batch / "spectre" / case))
        try:
            identity = admit(d, spec)
            wave = read_spectre(d / "psf/tran.tran.tran")
            cfg = json.loads((d / "contract.json").read_text())
            original = Path(spec["ng_directory"])
            if sha(d / "contract.json") != spec["files"]["contract.json"] or (original / "contract.json").read_bytes() != (d / "contract.json").read_bytes():
                raise ValueError("independent contract differs")
            ng = read_ng(original / "wave.raw")
            previous = json.loads((original / "analysis.json").read_text())
            if previous["passed"] is not True:
                raise ValueError("selected prior ngspice run did not pass")
            for name, (positive, negative) in cfg.get("differences", {}).items():
                for data in (wave, ng):
                    data[name] = [a - b for a, b in zip(data[positive], data[negative])]
            physical = score_tanh(wave, cfg["drive"]) if case == "124" else score_wave(wave, cfg)
            states = {inst: score_states(wave, names, cfg["states"][inst]) for inst, names in spec["state_vectors"].items()}
            state_pairs = {inst: compare_states(value, previous["states"][inst]) for inst, value in states.items() if "observed" in value}
            names = ["open", "out"] if case == "124" else list(dict.fromkeys([*cfg.get("inputs", {}), *cfg["signals"]]))
            pair = compare_waves(wave, ng, names, cfg["stop"], protocol["budgets"]["continuous_pair_grid_s"])
            passed = physical["passed"] and all(s["passed"] for s in states.values()) and len(state_pairs) == len(states) and all(s["passed"] for s in state_pairs.values()) and pair["passed"]
            results[case] = {"passed": passed, "identity": identity, "physical": physical, "states": states,
                             "state_pairs": state_pairs, "continuous_pair": pair,
                             "ng_reused": {"directory": str(original), "wave_sha256": sha(original / "wave.raw"), "analysis_sha256": sha(original / "analysis.json")}}
        except (OSError, ValueError, KeyError, StopIteration) as exc:
            results[case] = {"passed": False, "admission_or_analysis_error": str(exc)}
        (output / (case + ".json")).write_text(json.dumps(results[case], indent=2) + "\n")
        print(case, results[case]["passed"], flush=True)
    final = {**selection_verdict(results, cases, protocol),
             "analysis_only": True, "availability": "local-only", "cases": results,
             "fixed_denominator": protocol["fixed_denominator"], "analyzed": len(results),
             "new_simulator_runs_in_analysis": 0, "input_protocol_sha256": sha(protocol_path)}
    (output / "analysis.json").write_text(json.dumps(final, indent=2) + "\n")
    return final


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--batch", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--cases", default="104,210,148,115,068,chain,124")
    parser.add_argument("--protocol", help="versioned protocol for an explicitly recorded numerical retry")
    args = parser.parse_args()
    result = analyze(args.phase, args.batch, args.output, args.cases.split(","), args.protocol)
    raise SystemExit(0 if result["passed"] else 1)

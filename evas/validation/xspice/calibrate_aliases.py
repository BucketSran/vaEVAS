"""Independent analytic controls for P0 waveform/state and denominator gates."""

import argparse
import copy
import json
import math
from pathlib import Path

from alias_cases import configuration, CASES
from alias_reference import score_wave, score_events, pair
from validate_spectre_r53 import selection_verdict


def rc_step(q, at, rise, tau, t):
    z = t - at
    if z <= 0:
        return 0.0
    if z < rise:
        return q / rise * (z - tau * (1 - math.exp(-z / tau)))
    return q * (1 - tau / rise * (math.exp(-(z - rise) / tau) - math.exp(-z / tau)))


def calibrate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    cfg = configuration("ramp")
    # Direct arithmetic and a separate two-piece RC formula check the generic
    # segment recurrence used by the checker, without using it to make data.
    at, q, rise, tau = 28 / 11 * 1e-9, 221 / 550, 50e-12, .6e-9
    times = [0, .5e-9, 1e-9, at - 1e-12, at, at + 25e-12,
             at + 50e-12, 3e-9, 3.02e-9, 4e-9, 6e-9]
    wave = {"time": times, "clka": [.3 * min(t / 1e-9, 4) for t in times],
            "vdda": [1.2 + .05 * min(t / 1e-9, 4) for t in times],
            "vssa": [.2] * len(times),
            "vina": [.3 + .02 * (t / 1e-9) if t <= 3e-9 else .36 + (.8 - .36) * (t - 3e-9) / .02e-9 if t < 3.02e-9 else .8 for t in times],
            "ya": [q * min(1, max(0, (t - at) / rise)) for t in times],
            "rca": [rc_step(q, at, rise, tau, t) for t in times]}
    rows = {"analytic_correct": score_wave(wave, cfg)["passed"]}
    rows["pair_correct"] = pair(wave, wave, cfg)["passed"]
    for mode, node, index, delta in [
        ("platform", "ya", -1, 2.01e-4),
        ("RC", "rca", -1, 2.01e-4),
        ("edge", "ya", 5, 1.01e-2),
        ("retry", "ya", -1, 5.01e-8),
        ("nonfinite", "ya", -1, float("nan")),
    ]:
        bad = copy.deepcopy(wave)
        bad[node][index] += delta
        rows["pair_" + mode + "_rejected"] = not pair(wave, bad, cfg, 5e-8 if mode == "retry" else None)["passed"]
    bad = copy.deepcopy(wave); bad["ya"].pop()
    rows["pair_truncated_rejected"] = not pair(wave, bad, cfg)["passed"]
    for mode, wrong_q in [("frozen_alias", .3), ("wrong_reference_binding", q + .4)]:
        bad = copy.deepcopy(wave)
        bad["ya"] = [wrong_q * min(1, max(0, (t - at) / rise)) for t in times]
        bad["rca"] = [rc_step(wrong_q, at, rise, tau, t) for t in times]
        rows[mode + "_rejected"] = not score_wave(bad, cfg)["passed"]
    for mode in ("continuous_tracking", "missing_RC", "nonfinite", "platform", "edge", "RC", "truncated", "range"):
        bad = copy.deepcopy(wave)
        if mode == "continuous_tracking":
            bad["ya"][-1] = 1.3
        elif mode == "missing_RC":
            bad["rca"] = bad["ya"][:]
        elif mode == "nonfinite":
            bad["ya"][-1] = float("nan")
        elif mode == "platform":
            bad["ya"][-1] += 1.01e-4
        elif mode == "edge":
            bad["ya"][5] += 5.01e-3
        elif mode == "RC":
            bad["rca"][-1] += 1.01e-4
        elif mode == "truncated":
            bad["ya"].pop()
        elif mode == "range":
            for values in bad.values():
                values.pop()
        rows[mode + "_rejected"] = not score_wave(bad, cfg)["passed"]
    spec = cfg["instances"]["a"]
    for mode, observed, initial in [
        ("correct_state", [[at, q]], 0), ("late", [[at + 2e-13, q]], 0),
        ("early", [[at - 2e-13, q]], 0), ("lost", [], 0),
        ("duplicate", [[at, q], [5e-9, q]], 0),
        ("wrong_initial", [[at, q]], .1), ("wrong_capture", [[at, q + 1.01e-4]], 0),
    ]:
        actual = score_events(observed, initial, spec, cfg["budgets"])["passed"]
        rows[mode] = actual == (mode == "correct_state")
    names = [*CASES, "nearzero"]
    protocol = {"cases": dict.fromkeys(names), "fixed_denominator": 6}
    all_good = {n: {"passed": True} for n in names}
    rows["complete_selection"] = selection_verdict(all_good, names, protocol)["passed"]
    rows["partial_not_overall_pass"] = not selection_verdict({"ramp": {"passed": True}}, ["ramp"], protocol)["passed"]
    missing = dict(all_good); missing.pop("nearzero")
    rows["missing_case_not_overall_pass"] = not selection_verdict(missing, list(missing), protocol)["passed"]
    result = {"passed": all(rows.values()), "controls": rows, "total": len(rows),
              "new_simulator_runs": 0, "scope": "Independent two-piece RC positive and targeted waveform/state/fixed-denominator mutations; not a substitute for native execution."}
    (output / "analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    args = parser.parse_args()
    result = calibrate(args.output)
    print("P0 calibration", result["passed"], result["total"])
    raise SystemExit(0 if result["passed"] else 1)

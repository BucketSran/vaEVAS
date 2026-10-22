"""Calibrate the P1 public Rust response checker without executing a kernel."""

import argparse
import copy
import json
from pathlib import Path

from clock_cases import configuration
from validate import sha
from validate_clock_rust import analyze_response


def calibrate(response_path, output):
    response_path, output = Path(response_path).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    original = json.loads(response_path.read_text())
    rows = {}
    for mode in ("correct", "duplicate_event", "lost_event", "wrong_event_id", "late_event",
                 "bad_last_state", "nonfinite_state", "short_state", "wrong_t0", "missing_wave"):
        response = copy.deepcopy(original)
        rt = response["transient"]
        if mode == "duplicate_event": rt["events"].insert(1, copy.deepcopy(rt["events"][0]))
        if mode == "lost_event": rt["events"].pop(1)
        if mode == "wrong_event_id": rt["events"][0]["event"] = 999
        if mode == "late_event": rt["events"][-1]["time"] += 2e-13
        if mode == "bad_last_state": rt["states"][-1] = [999] * len(rt["state_names"])
        if mode == "nonfinite_state": rt["states"][-1][0] = float("nan")
        if mode == "short_state": rt["states"][-1].pop()
        if mode == "wrong_t0": rt["states"][0][0] += .001
        if mode == "missing_wave": response["solutions"].pop()
        observed = analyze_response(response, configuration("default32"))
        rows[mode] = {"passed": observed["passed"] == (mode == "correct"), "checker_accepted": observed["passed"]}
    result = {"passed": all(r["passed"] for r in rows.values()), "controls": rows,
              "response_sha256": sha(response_path), "checker_sha256": sha(Path(__file__).with_name("validate_clock_rust.py")),
              "new_simulator_runs": 0}
    (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("response")
    parser.add_argument("output")
    args = parser.parse_args()
    raise SystemExit(0 if calibrate(args.response, args.output)["passed"] else 1)

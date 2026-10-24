"""Accept/reject controls for native admission, state extraction and pairing."""

import argparse
import copy
import json
from pathlib import Path
import shutil
import tempfile

from validate_spectre_r53 import admit, compare_states, compare_waves, score_states, selection_verdict


def calibrate(pilot, expected, output):
    rows = {}
    fixed = {"cases": {"a": {}, "b": {}}, "fixed_denominator": 2}
    rows["selection_full"] = selection_verdict({"a": {"passed": True}, "b": {"passed": True}}, ["a", "b"], fixed)["passed"]
    subset = selection_verdict({"a": {"passed": True}}, ["a"], fixed)
    rows["selection_subset_not_complete"] = subset["selection_passed"] and not subset["passed"] and not subset["complete_selection"]
    rows["selection_failed_member"] = not selection_verdict({"a": {"passed": True}, "b": {"passed": False}}, ["a", "b"], fixed)["passed"]
    rows["selection_empty"] = not selection_verdict({}, [], fixed)["passed"]
    spec = {"initial": [0.0], "events": [[1e-9, [0.2]], [2e-9, [0.3]]]}
    wave = {"time": [0.0, 1e-9, 2e-9], "s": [0.0, 0.2, 0.3]}
    correct = score_states(wave, ["s"], spec)
    rows["state_correct"] = correct["passed"]
    for name, mutant in {
        "state_missing": {"time": wave["time"]},
        "state_initial": {"time": wave["time"], "s": [0.1, 0.2, 0.3]},
        "state_count": {"time": wave["time"], "s": [0.0, 0.2, 0.2]},
        "state_time": {"time": [0, 1.002e-9, 2e-9], "s": wave["s"]},
        "state_value": {"time": wave["time"], "s": [0, 0.20004, 0.3]},
        "state_nonfinite": {"time": wave["time"], "s": [0, float("nan"), 0.3]},
        "state_nonmonotone": {"time": [0, 2e-9, 1e-9], "s": wave["s"]},
    }.items():
        rows[name] = not score_states(mutant, ["s"], spec)["passed"]
    integer_spec = {"initial": [0], "events": [[1e-9, [1.5]], [2e-9, [2]]], "integer": True}
    rows["state_integer"] = not score_states({"time": wave["time"], "s": [0, 1.5, 2]}, ["s"], integer_spec)["passed"]
    rows["state_pair_correct"] = compare_states(correct, correct)["passed"]
    for name in ("time", "value", "count", "dimensions"):
        mutant = copy.deepcopy(correct)
        if name == "time":
            mutant["observed"][0][0] += 2e-12
        elif name == "value":
            mutant["observed"][0][1][0] += 40e-6
        elif name == "count":
            mutant["observed"].pop()
        else:
            mutant["observed"][0][1].append(0)
        rows["state_pair_" + name] = not compare_states(correct, mutant)["passed"]
    rows["wave_pair_correct"] = compare_waves(wave, wave, ["s"], 2e-9)["passed"]
    for name, mutant in {
        "wave_pair_voltage": {"time": wave["time"], "s": [0, 0.20004, 0.3]},
        "wave_pair_missing": {"time": wave["time"]},
        "wave_pair_nonfinite": {"time": wave["time"], "s": [0, float("nan"), 0.3]},
        "wave_pair_range": {"time": [0, 1e-9, 1.5e-9], "s": wave["s"]},
    }.items():
        rows[name] = not compare_waves(wave, mutant, ["s"], 2e-9)["passed"]
    pilot = Path(pilot)
    for mode in ("correct", "failed_exit", "timeout", "log", "started", "source", "tool", "effective"):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "batch/spectre/104"
            d.mkdir(parents=True)
            for name in ("tb.scs", *expected["sources"], "STARTED.json", "result.json", "spectre.log"):
                shutil.copy2(pilot / name, d / name)
            (d / "psf").mkdir()
            raw = d / "psf/tran.tran.tran"
            raw.symlink_to((pilot / "psf/tran.tran.tran").resolve())
            tool = d.parent.parent / "TOOL_IDENTITY.json"
            shutil.copy2(pilot.parent.parent / "TOOL_IDENTITY.json", tool)
            if mode in ("failed_exit", "timeout"):
                r = json.loads((d / "result.json").read_text())
                r["exit_code" if mode == "failed_exit" else "timed_out"] = 1 if mode == "failed_exit" else True
                (d / "result.json").write_text(json.dumps(r))
            elif mode == "log":
                (d / "spectre.log").write_text("incomplete run\n")
            elif mode == "started":
                (d / "STARTED.json").write_text('{"files":{}}')
            elif mode == "source":
                with (d / expected["sources"][0]).open("a") as stream:
                    stream.write("\n// changed input\n")
            elif mode == "tool":
                tool.write_text('{"spectre_sha256":""}')
            elif mode == "effective":
                raw.unlink()
                raw.write_text('HEADER\nTYPE\nVALUE\n"time" 0\n')
            try:
                admit(d, expected)
                accepted = True
            except ValueError:
                accepted = False
            rows["admission_" + mode] = accepted == (mode == "correct")
    result = {"passed": all(rows.values()), "controls": rows, "total": len(rows),
              "native_runs": 0, "scope": "Synthetic state/pair controls plus isolated metadata/source copies of one actual native pilot; original raw/reference files untouched."}
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / "analysis.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    protocol = json.loads((Path(args.phase) / "protocol.json").read_text())
    result = calibrate(args.pilot, protocol["cases"]["104"], args.output)
    print("native checker calibration", result["passed"], result["total"])
    raise SystemExit(0 if result["passed"] else 1)

"""Known-good analytic records and targeted wrong observations, no DUT import."""

import argparse
import copy
import csv
import json
from pathlib import Path

from r53_cases import sampler, counter, clock
from r53_reference import value, ramp_input, score_wave, score_states


def analytic_wave(cfg):
    times = {0.0, cfg["stop"]}
    times.update(cfg["stop"] * i / 1000 for i in range(1001))
    for signal in cfg["signals"].values():
        times.update(t for t, _ in signal["knots"] if 0 <= t <= cfg["stop"])
    times = sorted(times)
    return {"time": times,
            **{n: [ramp_input(p, t) for t in times] for n, p in cfg.get("inputs", {}).items()},
            **{n: [value(p["knots"], t, p.get("tau", 0)) for t in times] for n, p in cfg["signals"].items()}}


def write_states(path, cfg, events=None, initial=None):
    events = cfg["events"] if events is None else events
    initial = cfg["initial"] if initial is None else initial
    rows = [(0.0, initial), *events]
    with path.open("w") as stream:
        w = csv.writer(stream)
        w.writerow(["accepted_time", "prev_hash", *("prev_s" + str(i) for i in cfg["indices"])])
        for i, (t, states) in enumerate(rows):
            w.writerow([t, str(i), *states])


def calibrate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    fixtures = {"104": sampler("104", "unused")[1], "148": sampler("148", "unused")[1],
                "115": counter("115", "unused")[1], "068": clock("068", "unused")[1]}
    result = {}
    for fid, cfg in fixtures.items():
        wave = analytic_wave(cfg)
        result[fid + "_correct_wave"] = score_wave(wave, cfg)["passed"]
        for inst, spec in cfg["states"].items():
            path = output / (fid + inst + ".csv")
            write_states(path, spec)
            result[fid + inst + "_correct_states"] = score_states(path, spec["events"], spec["indices"], spec["initial"], spec.get("integer", False))["passed"]
    cfg = fixtures["148"]
    wave = analytic_wave(cfg)
    wave["outa0"], wave["outa1"] = wave["outa1"], wave["outa0"]
    result["swapped_channels_rejected"] = not score_wave(wave, cfg)["passed"]
    wave = analytic_wave(fixtures["104"])
    wave["rca0"] = [0.0] * len(wave["time"])
    result["missing_RC_response_rejected"] = not score_wave(wave, fixtures["104"])["passed"]
    wave["time"][0] = float("nan")
    result["nonfinite_rejected"] = not score_wave(wave, fixtures["104"])["passed"]
    wave = analytic_wave(fixtures["068"])
    wave["vssa"] = [v + 0.02 for v in wave["vssa"]]
    result["wrong_reference_rejected"] = not score_wave(wave, fixtures["068"])["passed"]
    wave = analytic_wave(fixtures["115"])
    wave["outa"] = [1.0 if t > 35.2e-9 else v for t, v in zip(wave["time"], wave["outa"])]
    result["marker_never_returns_low_rejected"] = not score_wave(wave, fixtures["115"])["passed"]
    spec = fixtures["148"]["states"]["a"]
    for name, events, initial in [
        ("lost_capture", spec["events"][1:], spec["initial"]),
        ("late_capture", [(t + 3e-12, s) for t, s in spec["events"]], spec["initial"]),
        ("wrong_initial", spec["events"], [0.1] * 4),
    ]:
        path = output / (name + ".csv")
        write_states(path, spec, events, initial)
        result[name + "_rejected"] = not score_states(path, spec["events"], spec["indices"], spec["initial"])["passed"]
    final = {"passed": all(result.values()), "controls": result}
    (output / "analysis.json").write_text(json.dumps(final, indent=2) + "\n")
    return final


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output")
    a = p.parse_args()
    r = calibrate(a.output)
    print(json.dumps(r, indent=2))
    raise SystemExit(0 if r["passed"] else 1)

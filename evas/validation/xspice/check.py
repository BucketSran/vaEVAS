"""Score raw accepted waveforms against independent hybrid RC answers."""

import bisect, sys, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from reference import value
from cases import TOL


def read_ng(path):
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("Variables:"))
    count = int(
        next(line.split(":")[1] for line in lines if line.startswith("No. Variables:"))
    )
    points = int(
        next(line.split(":")[1] for line in lines if line.startswith("No. Points:"))
    )
    names = [lines[start + i + 1].split()[1].lower() for i in range(count)]
    names = [name[2:-1] if name.startswith("v(") else name for name in names]
    values = {name: [] for name in names}
    cursor = next(i for i, line in enumerate(lines) if line.startswith("Values:")) + 1
    for _ in range(points):
        while not lines[cursor].strip():
            cursor += 1
        for name in names:
            values[name].append(float(lines[cursor].split()[-1]))
            cursor += 1
    return values


def read_spectre(path):
    lines = path.read_text().splitlines()
    start = lines.index("VALUE") + 1
    values = {}
    for line in lines[start:]:
        m = re.fullmatch(r'"([^"]+)"\s+([-+\d.eE]+)', line)
        if m:
            values.setdefault(m[1].lower(), []).append(float(m[2]))
    return values


def sample(v, name, time):
    ts = v["time"]
    k = bisect.bisect_left(ts, time)
    if k == 0:
        return v[name][0]
    if k == len(ts):
        return v[name][-1]
    ratio = (time - ts[k - 1]) / (ts[k] - ts[k - 1])
    return v[name][k - 1] + ratio * (v[name][k] - v[name][k - 1])


def events(v):
    result = []
    prior = 0
    for i, o in enumerate(v["order"]):
        if round(o) != prior:
            prior = round(o)
            result.append(
                {
                    "time": v["stamp"][i] * 1e-6,
                    "held": v["held"][i],
                    "count": round(v["count"][i]),
                    "ticks": round(v["ticks"][i]),
                    "order": prior,
                    "kind": "cross" if prior % 10 == 1 else "timer",
                }
            )
    return result


def grade(v, answer, cfg, tol=TOL):
    required = ("time", "out", "din", "clk", "held", "count", "ticks", "order", "stamp")
    if (
        any(n not in v for n in required)
        or not v["time"]
        or any(len(v[n]) != len(v["time"]) for n in required)
    ):
        return {"passed": False, "errors": ["missing or inconsistent vector"]}
    if any(not math.isfinite(x) for n in required for x in v[n]):
        return {"passed": False, "errors": ["nonfinite waveform"]}
    if any(b < a for a, b in zip(v["time"], v["time"][1:])):
        return {"passed": False, "errors": ["nonmonotone accepted times"]}
    es = events(v)
    want = answer["events"]
    errors = []
    if [e["order"] for e in es] != [e["order"] for e in want]:
        errors.append("event order/count")
    te = max((abs(a["time"] - b["time"]) for a, b in zip(es, want)), default=0.0)
    he = max((abs(a["held"] - b["held"]) for a, b in zip(es, want)), default=0.0)
    if te > tol["event_time_s"]:
        errors.append("event time")
    if he > tol["voltage_V"]:
        errors.append("sampled voltage")
    maxerr = {
        n: 0.0
        for n in ("out", "din", "clk", "held", "count", "ticks", "order", "stamp")
    }
    # All accepted points, excluding only the fixed event-time uncertainty band
    # for instantaneous state outputs. Continuous out/din/clk never excluded.
    for i, t in enumerate(v["time"]):
        for n in maxerr:
            if n not in ("out", "din", "clk") and any(
                abs(t - e["time"]) <= 2 * tol["event_time_s"] for e in want
            ):
                continue
            maxerr[n] = max(maxerr[n], abs(v[n][i] - value(answer, cfg, t, n)))
    for n, e in maxerr.items():
        limit = (
            tol["voltage_V"]
            if n in ("out", "din", "clk", "held", "stamp")
            else tol["sequence"]
        )
        if e > limit:
            errors.append(n + " waveform")
    if abs(v["time"][-1] - answer["stop"]) > 1e-15:
        errors.append("missing stop")
    return {
        "passed": not errors,
        "errors": errors,
        "events": es,
        "max_event_time_s": te,
        "max_sample_V": he,
        "max_error": maxerr,
        "points": len(v["time"]),
    }


def compare(a, b, voltage_tolerance=None):
    bound = TOL["voltage_V"] if voltage_tolerance is None else voltage_tolerance
    ea, eb = events(a), events(b)
    result = {
        "event_order_equal": [e["order"] for e in ea] == [e["order"] for e in eb],
        "max_event_time_s": max(
            (abs(x["time"] - y["time"]) for x, y in zip(ea, eb)), default=0
        ),
        "max_sample_V": max(
            (abs(x["held"] - y["held"]) for x, y in zip(ea, eb)), default=0
        ),
    }
    # Continuous outputs compared on a shared fixed observation grid.
    result["max_out_V"] = max(
        abs(sample(a, "out", i * 1e-9) - sample(b, "out", i * 1e-9))
        for i in range(int(math.floor(min(a["time"][-1], b["time"][-1]) / 1e-9)) + 1)
    )
    result["voltage_bound_V"] = bound
    result["passed"] = (
        result["event_order_equal"]
        and result["max_event_time_s"] <= TOL["event_time_s"]
        and max(result["max_sample_V"], result["max_out_V"]) <= bound
    )
    return result

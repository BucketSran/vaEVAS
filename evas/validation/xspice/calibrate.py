"""Calibrate known-correct answers and distinct deliberately wrong behaviors."""

import copy, json
from pathlib import Path
from check import grade, compare
from cases import CASES
from reference import expected, value

ROOT = Path(__file__).resolve().parent
cfg = CASES["timer_after"]
answer = expected(cfg)
times = sorted(
    set([i * 1e-9 for i in range(8401)] + [e["time"] + 1e-15 for e in answer["events"]])
)
v = {"time": times}
v.update(
    {
        n: [value(answer, cfg, t, n) for t in times]
        for n in ("out", "din", "clk", "held", "count", "ticks", "order", "stamp")
    }
)
rows = {"exact_answer": grade(v, answer, cfg)}
b = copy.deepcopy(v)
b["order"] = [x + 1 if x else x for x in b["order"]]
rows["wrong_event_order"] = grade(b, answer, cfg)
b = copy.deepcopy(v)
b["ticks"] = [0 for _ in times]
rows["lost_timer_cursor"] = grade(b, answer, cfg)
b = copy.deepcopy(v)
for i, t in enumerate(times):
    if 1.12e-6 <= t <= 1.52e-6:
        y = value(answer, cfg, 1.12e-6, "out")
        b["out"][i] = y + (0.05 - y) * (t - 1.12e-6) / 400e-9
rows["restart_full_fall_duration"] = grade(b, answer, cfg)
cfgq = CASES["queued_pulse"]
aq = expected(cfgq)
q = {"time": times}
q.update(
    {
        n: [value(aq, cfgq, t, n) for t in times]
        for n in ("out", "din", "clk", "held", "count", "ticks", "order", "stamp")
    }
)
for i, t in enumerate(times):
    if 1.12e-6 <= t <= 1.145e-6:
        q["out"][i] = 0.1
rows["lost_delayed_short_pulse"] = grade(q, aq, cfgq)
b = copy.deepcopy(v)
b["out"][12] = float("nan")
rows["nonfinite_waveform"] = grade(b, answer, cfg)
b = copy.deepcopy(v)
b["out"] = [x + 1e-7 for x in b["out"]]
rows["rollback_100nV_drift"] = compare(v, b, 5e-8)
result = {
    "passed": rows["exact_answer"]["passed"]
    and all(not r["passed"] for k, r in rows.items() if k != "exact_answer"),
    "controls": rows,
}
(Path(__import__("sys").argv[1]) / "calibration.json").write_text(
    json.dumps(result, indent=2) + "\n"
)
print("calibration", result["passed"])
raise SystemExit(0 if result["passed"] else 1)

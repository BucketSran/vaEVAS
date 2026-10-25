"""Check same-process host history lineage and observable rollback, incl faults."""

import csv, json
from pathlib import Path
from check import read_ng, grade, compare
from cases import CASES, TOL
from reference import expected
from trace_files import open_trace


def check(d, kind):
    with open_trace(d / "trace.csv") as stream:
        rows = list(csv.DictReader(stream))
    inj = next((i for i, r in enumerate(rows) if int(r["injected"])), None)
    if inj is None:
        return {"passed": False, "errors": ["no injection observed"]}
    first = rows[inj]
    rb = next((r for r in rows[inj + 1 :] if r["rollback"] == "1"), None)
    if rb is None:
        return {"passed": False, "errors": ["no time backtrack after injection"]}
    correct_kind = (
        int(first["event_mask"]) == 1
        if kind == "cross"
        else int(first["event_mask"]) == 2
        if kind == "timer"
        else int(first["event_mask"]) == 0
        and int(first["prev_q0"]) > int(first["trial_q0"])
    )
    # Replay the observed accepted-frame lineage. Current speculative entries
    # never become accepted just because callbacks ran at that time.
    seen = {}
    lineage_errors = 0
    checked = 0
    for r in rows:
        key = float(r["accepted_time"])
        if key in seen:
            checked += 1
            if r["prev_hash"] != seen[key]:
                lineage_errors += 1
        seen[float(r["time"])] = r["trial_hash"]
    # On the first retry before the event/deadline, none of these physical
    # histories is due. Compare all emitted states and every timer cursor,
    # queue length and edge end. Hash lineage also covers queue content.
    same = []
    for key in rb:
        if (
            key.startswith("prev_s")
            or key.startswith("prev_tick")
            or key.startswith("prev_q")
            or key.startswith("prev_end")
        ):
            suffix = key[5:]
            same.append((suffix, rb[key] == rb["trial_" + suffix]))
    invariants = (
        all(v for _, v in same)
        and rb["prev_armed"] == rb["trial_armed"]
        and rb["event_mask"] == "0"
    )
    errors = []
    if not correct_kind:
        errors.append("injection kind mismatch")
    if not invariants:
        errors.append("rejected physical history leaked on first retry")
    if lineage_errors:
        errors.append("host accepted history differs from observed accepted candidate")
    if not checked:
        errors.append("no accepted lineage comparisons")
    return {
        "passed": not errors,
        "errors": errors,
        "injection_call": int(first["call"]),
        "injection_time": float(first["time"]),
        "injection_event_mask": int(first["event_mask"]),
        "first_retry_time": float(rb["time"]),
        "accepted_time": float(rb["accepted_time"]),
        "first_retry_matches": dict(same),
        "accepted_lineage_checked": checked,
        "accepted_lineage_errors": lineage_errors,
        "injection": first,
        "first_retry": rb,
        "backtrack_calls": sum(int(r["rollback"]) for r in rows),
    }


def analyze_extras(batch):
    batch = Path(batch)
    extras = json.loads((batch / "extras.json").read_text())
    rows = {}
    for key, cfg in extras.items():
        d = batch / "ngspice" / key
        case = cfg["case"]
        v = read_ng(d / "wave.raw")
        cfgcase = CASES[case]
        g = grade(v, expected(cfgcase), cfgcase)
        rb = check(d, cfg["kind"])
        normal = read_ng(batch / "ngspice" / (case + "-tight") / "wave.raw")
        pair = compare(v, normal, TOL["rollback_pair_V"])
        good = g["passed"] and rb["passed"] and pair["passed"]
        verdict = (not rb["passed"]) if cfg["negative_control"] else good
        rows[key] = {
            "passed": verdict,
            "negative_control": cfg["negative_control"],
            "physical": g,
            "rollback": rb,
            "pair_with_normal": pair,
        }
    out = {"passed": all(v["passed"] for v in rows.values()), "checks": rows}
    (batch / "rollback-analysis.json").write_text(json.dumps(out, indent=2) + "\n")
    return out

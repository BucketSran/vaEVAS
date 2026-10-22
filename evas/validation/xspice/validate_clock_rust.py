"""Public installed Rust observations for the same P1 clock sources."""

import argparse
import bisect
import json
import math
from pathlib import Path

from evas import Instance, compile_sources, transient
from evas.kernel import select_kernel

from clock_cases import CASES, FILES, MODULES, SOURCES, answers, configuration
from clock_reference import score_wave, state_series
from validate import sha


def query_times(cfg):
    times = {0.0, cfg["stop"], *(i * 1e-9 for i in range(int(cfg["stop"] / 1e-9) + 1))}
    for a in answers(cfg).values():
        for state, rise in a["outputs"].values():
            times.update(at + rise * j / 4 for at, _ in a["histories"][state] for j in range(5))
    return sorted(t for t in times if 0 <= t <= cfg["stop"])


def analyze_response(response, cfg):
    expected, times, rt = answers(cfg), query_times(cfg), response["transient"]
    state_names = [tag + ":" + n for tag, a in expected.items() for n in a["initial"]]
    complete = (rt["times"] == times and len(response["solutions"]) == len(times)
                and len(rt["states"]) == len(times) and len(set(rt["state_names"])) == len(state_names)
                and set(rt["state_names"]) == set(state_names) and all(
                    len(r) == len(state_names) and all(math.isfinite(v) for v in r) for r in rt["states"])
                and all(len(r["voltages"]) == len(response["nodes"]) and all(math.isfinite(v) for v in r["voltages"])
                        for r in response["solutions"]))
    if not complete:
        return {"passed": False, "complete": False, "error": "incomplete/nonfinite public response"}
    wave = {"time": times}
    for i, node in enumerate(response["nodes"]):
        wave[node] = [r["voltages"][i] for r in response["solutions"]]
    physical = score_wave(wave, cfg)
    states, queried = {}, {}
    events = [e for e in rt["events"] if e["time"] > 0]
    for tag, a in expected.items():
        for name, initial in a["initial"].items():
            key = tag + ":" + name
            index = rt["state_names"].index(key)
            changes = a["histories"][name]
            states[key] = state_series([0, *(e["time"] for e in events)],
                [rt["states"][0][index], *(e["after"][index] for e in events)],
                initial, changes, cfg["budgets"], name == "hits")
            maximum = 0.0
            for t, values in zip(times, rt["states"]):
                k = bisect.bisect_right([at for at, _ in changes], t) - 1
                allowed = [initial if k < 0 else changes[k][1]]
                if t > 0:
                    for j in (k, k + 1):
                        if 0 <= j < len(changes) and abs(t - changes[j][0]) <= cfg["budgets"]["event_s"]:
                            allowed.extend((initial if j == 0 else changes[j - 1][1], changes[j][1]))
                maximum = max(maximum, min(abs(values[index] - v) for v in allowed))
            queried[key] = {"passed": maximum <= (0 if name == "hits" else cfg["budgets"]["platform_V"]),
                            "max_error": maximum}
    expected_events, offset = {}, 0
    for a in expected.values():
        for e in a["occurrences"]:
            expected_events[(offset + e["id"], e["cycle"])] = e["time"]
        offset += a["timer_count"]
    observed, cursors = {}, {}
    for e in rt["events"]:
        ident = e["event"]
        cycle = cursors.get(ident, 0)
        observed[(ident, cycle)] = e["time"]
        cursors[ident] = cycle + 1
    same = set(observed) == set(expected_events) and all(e["kind"] == "timer" for e in rt["events"])
    dt = max((abs(observed[k] - t) for k, t in expected_events.items()), default=0) if same else None
    calendar = {"passed": same and dt <= cfg["budgets"]["event_s"], "expected_count": len(expected_events),
                "observed_count": len(observed), "max_time_s": dt}
    return {"passed": physical["passed"] and calendar["passed"] and all(s["passed"] for s in states.values())
                      and all(s["passed"] for s in queried.values()),
            "complete": complete, "physical": physical, "states": states, "queried_states": queried,
            "calendar": calendar, "event_records": len(rt["events"])}


def validate(directory, cases, reanalyze=None):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    rows = {}
    for case in cases:
        cfg = configuration(case)
        sources, instances, identities = {}, [], {}
        for m in cfg["models"]:
            source = SOURCES / FILES[m["kind"]]
            sources[source.name] = source.read_text()
            identities[source.name] = sha(source)
            pins = {"zero": ("y", "count"), "clock": ("RST", "S", "SS", "NC_AZ", "NC", "CONV"),
                    "binary": ("y0", "y1", "y2"), "reverse": ("y0", "y1", "y2"), "near": ("y0", "y1")}[m["kind"]]
            instances.append(Instance(m["tag"], MODULES[m["kind"]],
                                      {p: p.lower() + m["tag"] for p in pins}, m["parameters"]))
        (directory / (case + "-contract.json")).write_text(json.dumps(cfg, indent=2) + "\n")
        try:
            if reanalyze:
                old = Path(reanalyze)
                assert json.loads((old / (case + "-contract.json")).read_text()) == cfg
                previous = json.loads((old / (case + ".json")).read_text())
                assert previous["source_sha256"] == identities
                response = json.loads((old / (case + "-response.json")).read_text())
            else:
                program = compile_sources(sources, instances)
                response = transient(program, {}, query_times(cfg), stop=cfg["stop"], max_step=cfg["maxstep_s"],
                                     vabstol=cfg["budgets"]["platform_V"], reltol=0)
                (directory / (case + "-response.json")).write_text(json.dumps(response, allow_nan=False) + "\n")
            row = {**analyze_response(response, cfg), "source_sha256": identities}
            if reanalyze:
                row["response_sha256"] = sha(old / (case + "-response.json"))
        except Exception as exc:
            row = {"passed": False, "exception": type(exc).__name__, "error": str(exc),
                   "diagnostic": getattr(exc, "diagnostic", None), "source_sha256": identities}
        rows[case] = row
        (directory / (case + ".json")).write_text(json.dumps(row, indent=2, allow_nan=False) + "\n")
        print(case, row["passed"], row.get("error", ""), flush=True)
    complete = set(cases) == set(CASES) and len(cases) == len(CASES)
    result = {"passed": complete and all(r["passed"] for r in rows.values()),
              "selection_passed": bool(rows) and all(r["passed"] for r in rows.values()),
              "complete_selection": complete, "fixed_denominator": len(CASES), "cases": rows,
              "kernel_sha256": sha(select_kernel()), "new_native_runs": 0,
              "new_rust_runs": 0 if reanalyze else len(rows), "checker_sha256": sha(Path(__file__)),
              "scope": "Same-source public Rust voltage/state observations; XSPICE cursor and host rollback are separate obligations."}
    (directory / "analysis.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output")
    parser.add_argument("--cases", default=",".join(CASES))
    parser.add_argument("--reanalyze")
    args = parser.parse_args()
    raise SystemExit(0 if validate(args.output, args.cases.split(","), args.reanalyze)["passed"] else 1)

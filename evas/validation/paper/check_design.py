"""Check A0 design consistency and independent nominal arithmetic, without a backend."""
import hashlib
import json
import math
import re
from collections import Counter
from fractions import Fraction
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKENDS = {"spectre", "evas", "openvaf_r_ngspice", "gnucap_modelgen"}
GROUPS = {"voltage", "expression", "event", "history", "continuous", "structure", "combination"}


def fraction(value):
    return Fraction(str(value))


def pwl(points, t):
    t = fraction(t)
    for (a, va), (b, vb) in zip(points, points[1:]):
        if fraction(a) <= t <= fraction(b):
            return fraction(va) + (fraction(vb)-fraction(va)) * (t-fraction(a)) / (fraction(b)-fraction(a))
    raise ValueError(f"PWL does not cover {t}")


def phase_integral(x):
    # These rational prefix integrals derive from integrating F on its exact breakpoints.
    knots = [Fraction(v) for v in [0, Fraction(6, 5), 2, Fraction(16, 5), 4, Fraction(24, 5), 6, Fraction(34, 5), 8]]
    rates = [Fraction(v) for v in [Fraction(1, 5), Fraction(1, 5), Fraction(2, 5), 1, 1, 1, Fraction(2, 5), Fraction(1, 5), Fraction(1, 5)]]
    x, phase = fraction(x), Fraction(1, 8)
    for a, b, fa, fb in zip(knots, knots[1:], rates, rates[1:]):
        z = max(Fraction(0), min(x, b)-a)
        phase += fa*z + (fb-fa)*z*z/(2*(b-a))
    return phase


def expected(card, t):
    x = fraction(t)
    name = card["id"]
    if name == "VR-01":
        v = {k: pwl(s["points_T_V"], x) for k, s in card["stimulus"].items()}
        return {"out_V": v["ref"]+Fraction(3, 2)*(v["ip"]-v["im"])-Fraction(1, 8)}
    if name == "EX-01":
        u = pwl(card["stimulus"]["ctl"]["points_T_V"], x)
        return {"freq_V": min(1, max(Fraction(1, 5), Fraction(2, 5)+u/2))}
    if name in {"EV-HC-01", "CO-HC-01"}:
        q = int(Fraction(11, 8) < x < Fraction(27, 8))
        n = int(x > Fraction(11, 8)) + int(x > Fraction(27, 8))
        if name == "EV-HC-01":
            return {"out_V": Fraction(1, 10)+Fraction(4, 5)*q, "count_V": n}
        rise = min(1, max(0, (x-Fraction(3, 2))/Fraction(1, 4)))
        fall = min(1, max(0, (x-Fraction(7, 2))/Fraction(1, 2)))
        return {"out_V": Fraction(1, 10)+Fraction(4, 5)*(rise-fall)}
    if name == "EV-HC-02":
        q = int(x < Fraction(11, 4) or x > Fraction(43, 8))
        return {"out_V": Fraction(1, 10)+Fraction(4, 5)*q, "count_V": int(x > Fraction(11, 4))+int(x > Fraction(43, 8))}
    if name == "EV-SH-01":
        n = int(x//2)
        q = Fraction(-1, 4) if n == 0 else pwl(card["stimulus"]["in"]["points_T_V"], 2*n)
        return {"out_V": q, "count_V": n}
    if name == "TM-01":
        rise = min(1, max(0, (x-Fraction(9, 4))/Fraction(1, 2)))
        fall = min(1, max(0, x-Fraction(25, 4)))
        return {"out_V": rise-fall}
    if name == "CP-01":
        if x <= 2:
            p = Fraction(1, 8)+Fraction(3, 10)*x
        elif x <= 4:
            z = x-2
            p = Fraction(29, 40)+Fraction(3, 10)*z+Fraction(3, 20)*z*z
        else:
            p = Fraction(77, 40)+Fraction(9, 10)*(x-4)
        return {"phase_V": p}
    if name == "CP-02":
        p = Fraction(1, 8)+Fraction(3, 4)*x
        return {"phase_V": p % 1, "out_V": math.sin(2*math.pi*float(p))}
    if name == "SI-01":
        na, nb = int(x//2), int(x//3)
        return {"oa_V": Fraction(-1, 4) if na == 0 else Fraction(na, 5), "ob_V": Fraction(3, 4) if nb == 0 else 1-Fraction(3*nb, 10), "na_V": na, "nb_V": nb}
    if name == "CO-SH-01":
        if x < 2:
            q, n = Fraction(-1, 4), 0
        elif x < 3:
            q, n = Fraction(0), 1
        elif x < 4:
            q, n = Fraction(-1, 4), 2
        elif x < 6:
            q, n = Fraction(-1, 4), 3
        elif x < 8:
            q, n = Fraction(4, 5), 4
        else:
            q, n = Fraction(6, 5), 5
        # Card anchors deliberately occur after each uninterrupted edge settles.
        return {"state_V": q, "out_V": q, "count_V": n}
    if name == "CO-VCO-01":
        u = pwl(card["stimulus"]["ctl"]["points_T_V"], x)
        return {"freq_V": min(1, max(Fraction(1, 5), Fraction(2, 5)+u/2)), "phase_V": phase_integral(x) % 1, "out_V": math.sin(2*math.pi*float(phase_integral(x)))}
    raise ValueError(name)


def main():
    raw = (HERE / "core-v1.json").read_bytes()
    batch = json.loads(raw)
    inventory = json.loads((HERE / "inventory-v1.json").read_text())
    cards, candidates = batch["cards"], inventory["candidates"]
    ids = {c["id"] for c in cards}
    assert len(ids) == len(cards) == batch["counting"]["declared_N"] == 12
    assert {c["primary_group"] for c in cards} == GROUPS
    assert len({c["id"] for c in candidates}) == len(candidates)
    for candidate in candidates:
        for key in ("capability_entry", "contract", "historical_navigation"):
            assert (HERE.parents[2]/candidate["current_evidence"][key]).is_file()
        assert candidate["classification"] in {"selected", "deferred", "outside"}
        assert candidate["reason"] and candidate["engineering_purpose"]
        assert set(candidate["condition_ids"]) <= ids
        assert bool(candidate["condition_ids"]) == (candidate["classification"] == "selected")
    covered = {id for c in candidates for id in c["condition_ids"]}
    assert covered == ids
    anchors = 0
    for card in cards:
        assert card["primary_group"] in GROUPS
        assert set(card["status_by_backend"]) == BACKENDS
        assert set(card["status_by_backend"].values()) == {"T"}
        assert "module " in card["source"] and card["source"].endswith("endmodule\n")
        for key in ["requirements", "features", "initial_state", "oracle", "anchors", "distinguishable_faults", "uncovered"]:
            assert card[key], (card["id"], key)
        for stim in card["stimulus"].values():
            if stim["kind"] == "pwl":
                pts = stim["points_T_V"]
                assert pts[0][0] == 0 and pts[-1][0] == card["stop_T"]
                assert all(a[0] < b[0] for a, b in zip(pts, pts[1:]))
                assert all(math.isfinite(v) for pair in pts for v in pair)
            else:
                assert stim["kind"] == "dc" and math.isfinite(stim["value_V"])
        expected_centers = {t for e in card["event_contract"] for t in e.get("nominal_T", [])}
        assert {w["center_T"] for w in card["observation_windows"]} == expected_centers
        for window in card["observation_windows"]:
            assert window["start_T"] < window["center_T"] < window["end_T"]
            assert window["max_gap_s"] <= 2e-11 and window["include_exact_center"]
        assert sum(card["callback_counts"].values()) == sum(e["expected_count"] for e in card["event_contract"] if e["kind"] != "wrap")
        guards = re.findall(r"cross\(V\((\w+)\)-([0-9.]+),([+-]1),([^,]+),([^)]+)\)", card["source"])
        for event in card["event_contract"]:
            assert event["expected_count"] == len(event["nominal_T"])
            assert event["window_T"][0] <= event["window_T"][1]
            assert all(0 < t < card["stop_T"] for t in event.get("nominal_T", []))
            if event["kind"] == "timer":
                assert event["window_T"] == [-.001, .001]
            if event["kind"] == "cross":
                assert event["window_T"][0] == 0
                matched = [g for g in guards if ("channel" not in event or g[0] == event["channel"]) and ("direction" not in event or int(g[2]) == event["direction"])]
                assert len(matched) == 1, (card["id"], event, guards)
                node, threshold, direction, time_tol, expr_tol = matched[0]
                points = card["stimulus"][node]["points_T_V"]
                for root in event["nominal_T"]:
                    assert pwl(points, root) == fraction(threshold)
                    segment = next((a,va,b,vb) for (a,va),(b,vb) in zip(points,points[1:]) if fraction(a) < fraction(root) < fraction(b))
                    a,va,b,vb = map(fraction,segment)
                    slope = (vb-va)/(b-a)
                    assert (slope > 0) == (int(direction) > 0)
                    width = min(fraction(time_tol)/fraction(batch["units"]["T_s"]),fraction(expr_tol)/abs(slope))
                    assert abs(float(width)-event["window_T"][1]) < 1e-15
            if event["kind"] == "wrap":
                assert len(event["unwrapped_integer_levels"]) == len(event["nominal_T"])
                for level, t in zip(event["unwrapped_integer_levels"], event["nominal_T"]):
                    phase = phase_integral(t) if card["id"] == "CO-VCO-01" else Fraction(1, 8)+Fraction(3, 4)*fraction(t)
                    assert abs(float(phase)-level) < 1e-12
        for anchor in card["anchors"]:
            answer = expected(card, anchor["t_T"])
            for key, actual in anchor.items():
                if key != "t_T":
                    assert abs(float(answer[key])-actual) < 1e-12, (card["id"], anchor, answer)
                    anchors += 1
    for x, phase in zip([0, 1.2, 2, 3.2, 4, 4.8, 6, 6.8, 8], [.125,.365,.605,1.445,2.245,3.045,3.885,4.125,4.365]):
        assert abs(float(phase_integral(x))-phase) < 1e-12
    print(f"PASS: {len(candidates)} candidates; {len(cards)} unique conditions; {anchors} nominal scalar anchors")
    print("Primary counts:", dict(Counter(c["primary_group"] for c in cards)))
    print("Candidate classification:", dict(Counter(c["classification"] for c in candidates)))
    print("core-v1 sha256:", hashlib.sha256(raw).hexdigest())
    print("Design arithmetic only: no source compilation, checker calibration or backend execution.")


if __name__ == "__main__":
    main()

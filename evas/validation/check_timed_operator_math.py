"""Check fixed hand-derived examples, not EVAS or simulator waveforms.

All times are ns, voltages V, and rates V/ns. Fractions are exact rationals.
There is deliberately no generic transition queue or slew solver here: each
branch checks the stated closed form for a specific documented example.
"""
from fractions import Fraction as F
import json
from pathlib import Path


def equal(actual, expected, label):
    if actual != expected:
        raise AssertionError(f"{label}: {actual!r} != {expected!r}")


def require(condition, label):
    if not condition:
        raise AssertionError(label)


def ramp(t, start, end, left, right):
    require(end > start, "positive edge duration required")
    fraction = min(F(1), max(F(0), (t-start)/(end-start)))
    return left+(right-left)*fraction


def pwl(points, t):
    require(points[0][0] <= t <= points[-1][0], "PWL query outside history")
    for (a, x), (b, y) in zip(points, points[1:]):
        require(b > a, "PWL times must increase")
        if a <= t <= b:
            return x+(y-x)*(t-a)/(b-a)
    raise AssertionError("PWL segment missing")


def main():
    path = Path(__file__).with_name("timed_operator_math.json")
    data = json.loads(path.read_text())
    equal(data["status"], "design_math_only_not_simulator_results", "evidence kind")
    equal(data["units"], {"time": "ns", "voltage": "V", "slope": "V/ns"}, "units")
    cases = {c["id"]: c for c in data["cases"]}
    equal(len(cases), len(data["cases"]), "unique IDs")
    checked = []
    for name, c in cases.items():
        number = lambda key: F(c[key])
        vector = lambda key: list(map(F, c[key]))
        observations = vector("observations") if "observations" in c else []
        values = None

        if name == "TI-PERIOD":
            start, period, stop = number("start"), number("period"), number("stop")
            require(start > 0 and period > 0 and stop >= start, name+" domain")
            count = (stop-start)//period+1
            events = [start+k*period for k in range(count)]
            equal(events, vector("expected_events"), name+" schedule")
            equal([sum(t >= e for e in events) for t in observations],
                  c["expected_counts"], name+" counts")
        elif name == "TI-ONCE":
            require(0 < number("start") <= number("stop"), name+" domain")
            for period in c["periods"]:
                require(period is None or F(period) <= 0, name+" nonpositive period")
                equal([number("start")], vector("expected_events"), name+" schedule")
        elif name == "TR-EDGE":
            first, second = vector("events")
            a, b = first+number("delay"), second+number("delay")
            ae, be = a+number("rise"), b+number("fall")
            require(ae < b, name+" separated edges")
            equal([a, ae, b, be], vector("expected_corners"), name+" corners")
            values = [ramp(t, a, ae, number("initial"), number("high")) if t < b
                      else ramp(t, b, be, number("high"), number("low"))
                      for t in observations]
        elif name in ("TR-REVERSE", "TR-EXTEND"):
            start, change, rise = number("start"), number("change"), number("rise")
            origin, old, new = number("initial"), number("old_target"), number("new_target")
            require(start < change < start+rise and old > origin, name+" interrupted rise")
            current = ramp(change, start, start+rise, origin, old)
            if name == "TR-REVERSE":
                require(new < current, name+" reverse target")
                slope = (new-old)/number("fall")
                equal(change+number("fall"), number("wrong_restart_finish"), name+" wrong control")
            else:
                require(new > current, name+" forward target")
                slope = (new-origin)/rise
            finish = change+(new-current)/slope
            equal(slope, number("expected_slope"), name+" slope")
            equal(finish, number("expected_finish"), name+" finish")
            if name == "TR-REVERSE":
                require(finish != number("wrong_restart_finish"), name+" discrimination")
            values = [ramp(t, start, start+rise, origin, old) if t < change
                      else ramp(t, change, finish, current, new) for t in observations]
        elif name == "TR-REPEAT":
            start, end = number("start"), number("start")+number("rise")
            require(start < number("repeat") < end, name+" repeat during edge")
            equal(end, number("expected_finish"), name+" finish")
            values = [ramp(t, start, end, number("initial"), number("target")) for t in observations]
        elif name == "TR-QUEUE":
            first, second = vector("events")
            a, b = first+number("delay"), second+number("delay")
            require(second < a < b < a+number("rise"), name+" queued short pulse")
            current = ramp(b, a, a+number("rise"), number("initial"), number("high"))
            slope = (number("low")-number("high"))/number("fall")
            finish = b+(number("low")-current)/slope
            equal(finish, number("expected_finish"), name+" finish")
            values = [ramp(t, a, a+number("rise"), number("initial"), number("high")) if t < b
                      else ramp(t, b, finish, current, number("low")) for t in observations]
            require(current > number("initial"), name+" lost-pulse control differs")
        elif name in ("AD-RAMP", "AD-ZERO"):
            points = [list(map(F, p)) for p in c["input"]]
            require(number("delay") >= 0, name+" delay")
            if name == "AD-ZERO":
                equal(c["domain"], "EVAS_candidate_extension", name+" nonstandard domain")
                equal(number("delay"), F(0), name+" zero extension")
            else:
                require(number("delay") > 0, name+" positive standard delay")
            values = [pwl(points, max(F(0), t-number("delay"))) for t in observations]
        elif name == "SL-CATCH":
            (t0, y0), (turn, level), (stop, last) = [list(map(F, p)) for p in c["input"]]
            rate = number("positive_rate")
            require(rate > 0 and (level-y0)/(turn-t0) > rate and level == last,
                    name+" input rises faster then holds")
            finish = t0+(level-y0)/rate
            require(turn < finish < stop, name+" catch on plateau")
            equal(finish, number("expected_catch"), name+" catch")
            values = [min(level, y0+rate*(t-t0)) for t in observations]
        elif name == "SL-REVERSE":
            (t0, y0), (turn, high), (flat, low), (stop, last) = [list(map(F, p)) for p in c["input"]]
            up, down = number("positive_rate"), number("negative_rate")
            input_slope = (low-high)/(flat-turn)
            require((high-y0)/(turn-t0) > up > 0 and input_slope < down < 0 and last == low,
                    name+" reversal regime")
            at_turn = y0+up*(turn-t0)
            intersection = turn+(high-at_turn)/(up-input_slope)
            require(turn < intersection < flat, name+" intersection in segment")
            at_intersection = at_turn+up*(intersection-turn)
            finish = intersection+(low-at_intersection)/down
            require(flat < finish < stop, name+" final catch on plateau")
            equal(intersection, number("expected_intersection"), name+" intersection")
            equal(finish, number("expected_finish"), name+" finish")
            values = [y0+up*(t-t0) if t <= intersection else
                      max(low, at_intersection+down*(t-intersection)) for t in observations]
        elif name == "SL-PASS":
            points = [list(map(F, p)) for p in c["input"]]
            for (a, x), (b, y) in zip(points, points[1:]):
                require(number("negative_rate") <= (y-x)/(b-a) <= number("positive_rate"), name+" slopes")
            values = [pwl(points, t) for t in observations]
        elif name == "CO-CROSS":
            source = cases[c["source"]]
            start = F(source["events"][0])+F(source["delay"])
            slope = (F(source["high"])-F(source["initial"]))/F(source["rise"])
            root = start+(number("threshold")-F(source["initial"]))/slope
            require(start < root < start+F(source["rise"]), name+" interior root")
            equal(root, number("expected_root"), name+" root")
            equal(1 if slope > 0 else -1, c["expected_direction"], name+" direction")
        else:
            raise AssertionError(f"unhandled math example {name}")
        if values is not None:
            equal(values, vector("expected_values"), name+" voltage anchors")
        checked.append(name)
    print(json.dumps({"kind": data["status"], "checked_math_groups": checked,
                      "simulators_executed": [], "formal_condition_count": None}, indent=2))


if __name__ == "__main__":
    main()

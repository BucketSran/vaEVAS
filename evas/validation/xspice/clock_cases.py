"""P1 frozen recipes and independent design calendars, not generated IR."""

from fractions import Fraction as F
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[2] / "examples/xspice/clock1800"
FILES = {"zero": "zero_start.va", "clock": "clock1800_standard.va",
         "binary": "independent_batch.va", "reverse": "independent_batch_reverse.va",
         "near": "independent_near.va"}
MODULES = {"zero": "zero_start", "clock": "CLOCK_VA_SAMPLE_1800n",
           "binary": "independent_batch", "reverse": "independent_batch", "near": "independent_near"}
BUDGETS = {"event_s": 1e-13, "pair_event_s": 2e-13, "platform_V": 1e-4,
           "pair_platform_V": 2e-4, "edge_V": .006, "pair_edge_V": .012, "retry_V": 5e-8}
CASES = ("zero", "fall", "positive", "tiny", "binary", "reverse", "near",
         "default32", "variant42", "empty", "once", "instances", "long1000", "stopbefore", "stopafter")
NS = F(1, 10**9)


def model(kind, tag="a", **params):
    return {"kind": kind, "tag": tag, "parameters": params}


def configuration(case):
    if case not in CASES:
        raise ValueError(case)
    models, stop = [model("zero")], F(25) * NS
    if case == "fall": models = [model("zero", old=1.1, level=0)]
    if case == "positive": models = [model("zero", start=1e-9, old=.4)]
    if case == "tiny": models, stop = [model("zero", start=1e-15)], F(1, 10**9)
    if case in ("binary", "reverse"):
        models, stop = [model(case)], F(5, 2) * F(1, 2**20)
    if case == "near": models = [model("near")]
    if case in ("default32", "variant42", "empty", "once", "instances"):
        models, stop = [model("clock")], F(3700) * NS
        if case in ("variant42", "empty", "once"):
            n = {"variant42": 4, "empty": 0, "once": 1}[case]
            params = {g + "_num": n for g in ("S", "SS", "NC_AZ", "NC", "CONV")}
            if n == 4: params["RST_period"], stop = 2400e-9, F(4900) * NS
            models = [model("clock", **params)]
        if case == "instances":
            models.append(model("clock", "b", vdd=.8, init_delay=7e-9,
                                **{g + "_num": 1 for g in ("S", "SS", "NC_AZ", "NC", "CONV")}))
    if case == "long1000": stop = F(10005) * NS
    if case == "stopbefore": stop = F(20) * NS - F(200, 10**15)
    if case == "stopafter": stop = F(20) * NS + F(200, 10**15)
    return {"case": case, "models": models, "stop": float(stop), "budgets": BUDGETS,
            "maxstep_s": 1e-9 if case not in ("tiny", "near") else 1e-12}


def design(m, stop):
    """Decimal design arithmetic independent of VA parser/folding/runtime."""
    kind, params, tag = m["kind"], m["parameters"], m["tag"]
    fraction = lambda v: F(str(v))
    states, outputs, timers = {}, {}, []
    if kind == "zero":
        start, period = fraction(params.get("start", 0)), fraction(params.get("period", 1e-8))
        level, old = params.get("level", 1.1), params.get("old", 0)
        states = {"q": old, "hits": 0}
        outputs = {"y" + tag: ["q", params.get("edge", 20e-12)]}
        timers = [(start, period, {"q": level, "hits": "increment"})]
    elif kind == "clock":
        states = dict.fromkeys(("rst", "s", "ss", "nc_az", "nc", "conv"), 0)
        outputs = {s + tag: [s, params.get("trise", 20e-12)] for s in states}
        t0, period = fraction(params.get("init_delay", 0)), fraction(params.get("RST_period", 1800e-9))
        level = params.get("vdd", 1.1)
        timers = [(t0, period, {"rst": level}), (t0 + fraction(params.get("RST_width", 20e-9)), period, {"rst": 0})]
        for name, delay, width in (("S",20,36),("SS",20,50),("NC_AZ",52,4),("NC",58,10),("CONV",72,538)):
            for j in range(params.get(name + "_num", 3)):
                at = t0 + fraction(params.get(name + "_delay", delay * 1e-9)) + j * fraction(params.get(name + "_interval", 600e-9))
                timers.extend(((at, period, {name.lower(): level}),
                               (at + fraction(params.get(name + "_width", width * 1e-9)), period, {name.lower(): 0})))
    else:
        states = dict.fromkeys(("a", "b") if kind == "near" else ("a", "b", "c"), 0)
        outputs = {"y" + str(i) + tag: [s, 20e-12] for i, s in enumerate(states)}
        if kind == "near":
            timers = [(F(1)*NS,F(10)*NS,{"a":1.1}), (F(2001,2000)*NS,F(10)*NS,{"b":1.1}),
                      (F(2)*NS,F(10)*NS,{"a":0}), (F(4001,2000)*NS,F(10)*NS,{"b":0})]
        else:
            period = F(1,2**20)
            timers = [(period/8,period,{s:1.1}) for s in states] + [(period/4,period,{s:0}) for s in states]
            if kind == "reverse": timers.reverse()
    occurrences = []
    for index, (start, period, writes) in enumerate(timers):
        k = 0
        while start + k * period <= F(str(stop)):
            occurrences.append({"time": float(start + k * period), "id": index, "cycle": k, "writes": writes})
            k += 1
    occurrences.sort(key=lambda x: (x["time"], x["id"]))
    histories = {n: [] for n in states}
    initial = dict(states)
    for e in occurrences:
        for n, value in e["writes"].items():
            target = states[n] + 1 if value == "increment" else value
            if e["time"] == 0: initial[n] = target
            elif target != states[n]: histories[n].append([e["time"], target])
            states[n] = target
    return {"tag": tag, "initial": initial, "histories": histories, "outputs": outputs,
            "occurrences": occurrences, "timer_count": len(timers)}


def answers(cfg):
    return {m["tag"]: design(m, cfg["stop"]) for m in cfg["models"]}

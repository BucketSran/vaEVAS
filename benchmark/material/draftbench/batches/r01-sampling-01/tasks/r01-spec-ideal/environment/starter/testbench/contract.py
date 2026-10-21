"""Analytical interval reference and trace diagnostics. No VA execution."""
import csv
import math

SIGNALS = ("vin", "track", "rst")

def pwl(points, t):
    if t <= points[0][0]:
        return points[0][1]
    for (a, x), (b, y) in zip(points, points[1:]):
        if t <= b:
            return x + (y-x)*(t-a)/(b-a)
    return points[-1][1]

def crossings(points, threshold, direction=None):
    found = []
    for (a,x),(b,y) in zip(points,points[1:]):
        if (x < threshold < y) or (y < threshold < x):
            sign = 1 if y > x else -1
            if direction is None or direction == sign:
                found.append(a+(threshold-x)*(b-a)/(y-x))
    return found

def events(i):
    return sorted(set(crossings(i["track"],i["vth"])+crossings(i["rst"],i["vth"])))

def validate(cases):
    names = set()
    for case in cases:
        if case["name"] in names or not math.isfinite(case["stop"]) or case["stop"] <= 0:
            raise ValueError("invalid or duplicate case")
        names.add(case["name"])
        ids = set()
        if not case["instances"]:
            raise ValueError("empty case")
        for i in case["instances"]:
            if i["name"] in ids or not all(math.isfinite(i[x]) for x in ("vth","vinit")):
                raise ValueError("invalid or duplicate instance")
            ids.add(i["name"])
            for signal in SIGNALS:
                points = i[signal]
                if len(points)<2 or points[0][0]!=0 or points[-1][0]!=case["stop"]:
                    raise ValueError("stimulus must span [0, stop]")
                if not all(math.isfinite(v) for point in points for v in point):
                    raise ValueError("nonfinite stimulus")
                if any(b[0]<=a[0] for a,b in zip(points,points[1:])):
                    raise ValueError("stimulus times must increase")
                if signal != "vin" and any(v==i["vth"] for _,v in points[1:]) and not all(v==i["vth"] for _,v in points):
                    raise ValueError("later threshold endpoint is TBD")
            if set(crossings(i["track"],i["vth"])) & set(crossings(i["rst"],i["vth"])):
                raise ValueError("same-instance coincident crossings are TBD")
    return cases

def expected(i,t):
    """Evaluate the most recent completed tracking/reset interval directly.

    In hold, the last reset release erases all earlier tracking intervals.
    A close strictly after it supplies vin(close); absent one, use vinit.
    Initial reset release is handled without relying on a synthetic t=0 edge.
    """
    th = i["vth"]
    if pwl(i["rst"],t)>th:
        return i["vinit"], "reset"
    if pwl(i["track"],t)>th:
        return pwl(i["vin"],t), "track"
    released = [e for e in crossings(i["rst"],th,-1) if e<t]
    start = max(released,default=0.0)
    closes = [e for e in crossings(i["track"],th,-1)
              if start<e<t and pwl(i["rst"],e)<=th]
    if closes:
        return pwl(i["vin"],max(closes)), "hold_sample"
    return i["vinit"], "hold_initial_or_reset"

def observations(cases,step,guard):
    if not math.isfinite(step) or step<=0 or not math.isfinite(guard) or guard<=0:
        raise ValueError("positive finite step and guard required")
    validate(cases)
    rows=[]
    for c in cases:
        for i in c["instances"]:
            es=events(i)
            times={0.0,c["stop"]}
            n=math.ceil(c["stop"]/step)
            if n>100000:
                raise ValueError("diagnostic grid exceeds 100000 intervals")
            times.update(k*step for k in range(1,n) if k*step<c["stop"])
            knots=sorted(set([0.,c["stop"]]+es+[t for t,_ in i["vin"]]))
            times.update((a+b)/2 for a,b in zip(knots,knots[1:]))
            times.update(e+d for e in es for d in (-2*guard,2*guard)
                         if 0<e+d<c["stop"])
            kept=[t for t in sorted(times) if t==0 or all(abs(t-e)>guard for e in es)]
            if c["stop"] not in kept:
                raise ValueError("stop observation conflicts with event guard")
            # Each mode interval must retain a probe even with the exclusion.
            if any(not any(a<t<b for t in kept) for a,b in zip([0.]+es,es+[c["stop"]])):
                raise ValueError("event guard erases a required interval")
            for j,t in enumerate(kept):
                value,mode=expected(i,t)
                rows.append(dict(case=c["name"],instance=i["name"],probe=j,time=t,
                                 vin=pwl(i["vin"],t),track=pwl(i["track"],t),
                                 rst=pwl(i["rst"],t),vout=value,mode=mode))
    return rows

def load_csv(path):
    with open(path,newline="") as f:
        rows=list(csv.DictReader(f))
    out=[]
    for row in rows:
        out.append({**{k:row[k] for k in ("case","instance")},
                    "probe":int(row["probe"]),
                    **{k:float(row[k]) for k in ("time",*SIGNALS,"vout")}})
    return out

def diagnose(plan,observed,voltage_atol,time_atol):
    for x in (voltage_atol,time_atol):
        if not math.isfinite(x) or x<0:
            raise ValueError("finite nonnegative diagnostic tolerances required")
    key=lambda r:(r["case"],r["instance"],r["probe"])
    expected_map={key(r):r for r in plan}
    if not plan or len(expected_map)!=len(plan):
        raise ValueError("empty or duplicate observation plan")
    actual={}
    issues=[]
    for r in observed:
        k=key(r)
        if k in actual:
            issues.append(dict(kind="duplicate",key=k))
        actual[k]=r
    for k in actual.keys()-expected_map.keys():
        issues.append(dict(kind="unexpected",key=k))
    for k,e in expected_map.items():
        if k not in actual:
            issues.append(dict(kind="missing",key=k)); continue
        a=actual[k]
        for field in ("time",*SIGNALS,"vout"):
            value=a[field]
            limit=time_atol if field=="time" else voltage_atol
            if not math.isfinite(value) or abs(value-e[field])>limit:
                issues.append(dict(kind="nonfinite" if not math.isfinite(value) else "error",
                                   key=k,field=field,actual=str(value),expected=e[field],
                                   limit=limit,time=e["time"],mode=e["mode"]))
    return dict(status="fail" if issues else "pass",diagnostic_only=True,
                observations=len(plan),issues=issues)

def render(case, plan, destination, settings=None):
    """Render native PSF observations. No candidate-printed values are consumed."""
    from pathlib import Path
    import json
    dst = Path(destination)
    dst.mkdir(parents=True, exist_ok=True)
    lines = ['simulator lang=spectre', 'global 0', 'ahdl_include "circuit.va"']
    ports = []
    mapping = {}
    for index, i in enumerate(case["instances"]):
        nodes = {s: f"{s}_{index}" for s in (*SIGNALS, "vout")}
        mapping[i["name"]] = nodes
        for signal in SIGNALS:
            wave = ' '.join(f'{t:.17g} {v:.17g}' for t, v in i[signal])
            lines.append(f'V{signal}{index} ({nodes[signal]} 0) vsource type=pwl wave=[{wave}]')
        lines.append(f'X{index} ({nodes["vin"]} {nodes["track"]} {nodes["rst"]} {nodes["vout"]}) track_hold vth={i["vth"]:.17g} vinit={i["vinit"]:.17g}')
        ports.extend(nodes.values())
    own_plan = [r for r in plan if r["case"] == case["name"]]
    strobes = ' '.join(f'{t:.17g}' for t in sorted({r["time"] for r in own_plan}))
    options = ''
    if settings is not None:
        n = settings["numerical_settings"]
        lines.append(f'simulatorOptions options precision="%.17g" reltol={n["reltol"]:.17g} vabstol={n["vabstol"]:.17g} iabstol={n["iabstol"]:.17g}')
        options = f' maxstep={n["maxstep"]:.17g} errpreset=conservative method=traponly'
    lines.append(f'tran tran stop={case["stop"]:.17g}{options} strobetimes=[{strobes}] strobeoutput=all compression=no skipcount=1')
    lines.append('save ' + ' '.join(ports))
    (dst / 'tb.scs').write_text('\n'.join(lines) + '\n')
    (dst / 'nodes.json').write_text(json.dumps(mapping, indent=2) + '\n')
    (dst / 'expected.json').write_text(json.dumps(own_plan, indent=2) + '\n')
    return mapping

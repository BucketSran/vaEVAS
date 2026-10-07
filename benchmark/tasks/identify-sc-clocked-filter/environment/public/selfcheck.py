"""Compare an exported candidate CSV against one complete public observation.

This is public feedback only. It never reads task tests or hidden truth.
Input candidate CSV has time_s and out_V, and tune_V for the PLL task.
"""
import argparse
import bisect
import csv
import json
import math
from pathlib import Path


def read(path):
    with path.open() as f:return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(f)]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--experiment",required=True)
    p.add_argument("--candidate-csv",required=True,type=Path)
    args=p.parse_args()
    public=Path(__file__).resolve().parent
    expected=read(public/"data"/(args.experiment+".csv"))
    actual=read(args.candidate_csv)
    if len(actual)<2:raise ValueError("at least two samples required")
    ts=[r["time_s"] for r in actual]
    if any(not math.isfinite(x) for r in actual for x in r.values()) or any(b<=a for a,b in zip(ts,ts[1:])):raise ValueError("invalid trace")
    nodes=[n for n in ("out_V","tune_V") if n in expected[0]]
    errors={n:0.0 for n in nodes};comp="clk_V" in expected[0]
    events=[]
    if comp:
        for a,b in zip(expected,expected[1:]):
            if a["out_V"]!=b["out_V"]:events.extend((a["time_s"],b["time_s"]))
    for target in expected:
        t=target["time_s"]
        if comp and any(abs(t-at)<2e-9 for at in events):continue
        if "track_V" in target:
            events=[b["time_s"] for a,b in zip(expected,expected[1:]) if a["track_V"]!=b["track_V"]]
            if any(abs(t-at)<5e-9 for at in events):continue
        if not ts[0]<=t<=ts[-1]:raise ValueError("candidate does not cover full experiment")
        j=max(0,min(len(actual)-2,bisect.bisect_right(ts,t)-1));a,b=actual[j:j+2]
        for node in nodes:
            y=a[node]+(b[node]-a[node])*(t-a["time_s"])/(b["time_s"]-a["time_s"])
            errors[node]=max(errors[node],abs(y-target[node]))
    print(json.dumps(dict(experiment=args.experiment,max_voltage_error_V=errors,scope="public observations only; not final score"),indent=2))


if __name__=="__main__":main()

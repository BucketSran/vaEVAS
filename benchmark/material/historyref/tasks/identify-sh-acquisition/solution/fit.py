"""Estimate a feasible voltage model using only supplied public experiments."""
import argparse
import csv
import json
import math
from pathlib import Path
import statistics


def fit(public):
    experiments = json.loads((public / "experiments.json").read_text())
    tau_samples, droop_samples, steps = [], [], []
    for c in experiments:
        with (public / "data" / f"{c['name']}.csv").open() as source:
            rows = list(csv.DictReader(source))
        data = [{k: float(v) for k,v in row.items()} for row in rows]
        a,b,amp = c["hold_start"],c["track_again"],c["amplitude"]
        for r in data:
            t,y = r["time_s"],r["out_V"]
            if 0.15*a<t<0.85*a and 0 < y/amp < 1:
                tau_samples.append(-t/math.log1p(-y/amp))
        held = [r for r in data if a+0.15*(b-a)<r["time_s"]<a+0.85*(b-a)]
        first,last=held[0],held[-1]
        slope=(last["out_V"]-first["out_V"])/(last["time_s"]-first["time_s"])
        droop_samples.append(slope)
        steps.append((c, first, slope))
    tau=statistics.median(tau_samples)
    xy=[]
    for c,r,slope in steps:
        before=c["amplitude"]*(-math.expm1(-c["hold_start"]/tau))
        held_at_start=r["out_V"]-slope*(r["time_s"]-c["hold_start"])
        xy.append((before,held_at_start-before))
    xmean=statistics.mean(x for x,y in xy)
    ymean=statistics.mean(y for x,y in xy)
    h1=sum((x-xmean)*(y-ymean) for x,y in xy)/sum((x-xmean)**2 for x,y in xy)
    h0=ymean-h1*xmean
    return tau,h0,h1,statistics.median(droop_samples)


def model(parameters, variant="reference"):
    tau,h0,h1,droop=parameters
    if variant == "no-droop":
        droop=0
    if variant == "no-hold-step":
        h0=h1=0
    if variant == "wrong-polarity-step":
        h1=-h1
    if variant == "fast-acquisition":
        tau *= 0.2
    return f'''`include "constants.vams"
`include "disciplines.vams"
module identified_sh(vin, track, out);
input vin, track;
output out;
electrical vin, track, out;
parameter real tau = {tau:.15g};
parameter real step_offset = {h0:.15g};
parameter real step_gain = {h1:.15g};
parameter real hold_drift = {droop:.15g};
real accumulated_step, velocity;
analog begin
  @(initial_step) accumulated_step = 0.0;
  @(cross(V(track)-0.5, -1))
    accumulated_step = accumulated_step + step_offset + step_gain*V(out);
  if (V(track) > 0.5)
    velocity = (V(vin)-V(out))/tau;
  else
    velocity = hold_drift;
  V(out) <+ idt(velocity, 0.0) + accumulated_step;
end
endmodule
'''


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--public",type=Path,default=Path("/work/public"))
    parser.add_argument("--output",type=Path,default=Path("/work/dut.va"))
    parser.add_argument("--variant",default="reference",choices=["reference","no-droop","no-hold-step","wrong-polarity-step","fast-acquisition"])
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(model(fit(args.public),args.variant))


if __name__ == "__main__":
    main()

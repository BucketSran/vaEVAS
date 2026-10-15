import argparse, csv, json, math, statistics
from pathlib import Path

def solve(matrix,vector):
    a=[list(row)+[y] for row,y in zip(matrix,vector)]
    for k in range(len(a)):
        j=max(range(k,len(a)),key=lambda j:abs(a[j][k]))
        a[k],a[j]=a[j],a[k]
        div=a[k][k]
        if abs(div)<1e-25:raise ValueError("singular observations")
        a[k]=[x/div for x in a[k]]
        for j in range(len(a)):
            if j!=k:
                factor=a[j][k];a[j]=[x-factor*y for x,y in zip(a[j],a[k])]
    return [row[-1] for row in a]

def regress(xs,ys):
    n=len(xs[0])
    return solve([[sum(x[i]*x[j] for x in xs) for j in range(n)] for i in range(n)], [sum(x[i]*y for x,y in zip(xs,ys)) for i in range(n)])

def read(public,c):
    with (public/"data"/(c["name"]+".csv")).open() as source:
        return [{k:float(v) for k,v in row.items()} for row in csv.DictReader(source)]

def fit(public):
    cs=json.loads((public/"experiments.json").read_text());byname={c["name"]:c for c in cs}
    plateaus=[]
    for name in ("public-small-positive","public-small-negative"):
        c=byname[name];r=read(public,c)
        plateau=statistics.mean(x["out_V"] for x in r if .9*c["switch_time"]<x["time_s"]<.98*c["switch_time"])
        plateaus.append((c["first_amplitude"],plateau))
    (x1,y1),(x2,y2)=plateaus
    gain=(y1-y2)/(x1-x2);offset=y1-gain*x1
    sr=0;low=1e10;high=-1e10;taus=[]
    for c in cs:
        rows=read(public,c)
        plateau=statistics.mean(r["out_V"] for r in rows if .9*c["switch_time"]<r["time_s"]<.98*c["switch_time"])
        if c["first_amplitude"]>.95:high=plateau
        if c["first_amplitude"]<-.95:low=plateau
        for a,b in zip(rows,rows[1:]):
            if b["time_s"]<.2*c["switch_time"]:sr=max(sr,abs((b["out_V"]-a["out_V"])/(b["time_s"]-a["time_s"])))
        if abs(c["first_amplitude"])<.2:
            goal=gain*c["first_amplitude"]+offset
            samples=[r for r in rows if 60e-9<r["time_s"]<180e-9]
            a,b=samples[0],samples[-1]
            taus.append(-(b["time_s"]-a["time_s"])/math.log(abs((goal-b["out_V"])/(goal-a["out_V"]))))
    return gain,offset,statistics.mean(taus),sr,low,high

def model(parameters,variant="reference"):
    gain,offset,tau,sr,low,high=parameters
    if variant=="no-slew":sr*=10000
    if variant=="wrong-bandwidth":tau*=2
    if variant=="no-rails":low,high=-10,10
    if variant=="restart-on-input":reset=True
    else:reset=False
    # Restart mutation deliberately resets state whenever the input changes.
    if reset:
        # A separate algebraic memoryless model is a valid but wrong submission.
        return '''`include "disciplines.vams"
module identified_driver(vin,out);input vin;output out;electrical vin,out;
analog V(out)<+V(vin);
endmodule
'''
    return f'''`include "constants.vams"
`include "disciplines.vams"
module identified_driver(vin,out);
input vin;output out;electrical vin,out;
real target,velocity;
analog begin
  target=max({low:.15g},min({high:.15g},{gain:.15g}*V(vin)+{offset:.15g}));
  velocity=max(-{sr:.15g},min({sr:.15g},(target-V(out))/{tau:.15g}));
  V(out)<+idt(velocity,0);
end
endmodule
'''

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--public",type=Path,default=Path("/work/public"))
    p.add_argument("--output",type=Path,default=Path("/work/dut.va"))
    p.add_argument("--variant",default="reference")
    args=p.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(model(fit(args.public),args.variant))

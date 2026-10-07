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
    values=[]
    for c in json.loads((public/"experiments.json").read_text()):
        rows=read(public,c);hop=c["steps"][0]
        sign=1 if hop["command_V"]>c["initial_command_V"] else -1
        peaks=[]
        for i in range(1,len(rows)-1):
            a,b,d=rows[i-1:i+2]
            ya,yb,yd=[sign*r["phase_error_cycles"] for r in (a,b,d)]
            if b["time_s"]>hop["time"] and yb>0 and ya<yb>=yd:
                offset=.5*(ya-yd)/(ya-2*yb+yd)
                dt=d["time_s"]-b["time_s"]
                time=b["time_s"]+offset*dt
                height=yb-.25*(ya-yd)*offset
                peaks.append((time,height))
        a,b=peaks[:2]
        wd=2*math.pi/(b[0]-a[0]);alpha=math.log(a[1]/b[1])/(b[0]-a[0])
        values.append((2*alpha,wd*wd+alpha*alpha))
    return tuple(statistics.mean(x[k] for x in values) for k in (0,1))

def model(parameters,variant="reference"):
    kp,ki=parameters
    if variant=="wrong-damping":kp*=.35
    if variant=="no-integral":ki=0
    if variant=="wrong-loop-rate":kp*=.6;ki*=.36
    phase_expression="idt(1e6*V(cmd),0)-V(phase_error)"
    if variant=="wrong-clock-phase":phase_expression="idt(1e6*V(cmd),0)"
    ripple="+0.1*sin(6.283185307179586*$abstime/5e-7)" if variant=="grid-alias-ripple" else ""
    return f'''`include "constants.vams"
`include "disciplines.vams"
module identified_pll(cmd,out,tune);
input cmd;output out,tune;
electrical cmd,out,tune,phase_error,integrated_error;
real deviation;
analog begin
  deviation={kp:.15g}*V(phase_error)+{ki:.15g}*V(integrated_error);
  V(phase_error)<+idt(1e6*V(cmd)-8e5-deviation,0);
  V(integrated_error)<+idt(V(phase_error),0);
  V(tune)<+0.8+deviation/1e6;
  V(out)<+sin(6.283185307179586*({phase_expression})){ripple};
  $bound_step(1e-8);
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

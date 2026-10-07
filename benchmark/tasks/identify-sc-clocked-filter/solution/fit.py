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
    xs=[];ys=[]
    for c in json.loads((public/"experiments.json").read_text()):
        rows=read(public,c);prev=prev2=0
        for r in rows:
            xs.append([prev,prev2,r["vin_V"]]);ys.append(r["out_V"])
            prev2,prev=prev,r["out_V"]
    return regress(xs,ys)

def model(parameters,variant="reference"):
    a,b,c=parameters
    edge=1
    if variant=="single-pole":a,b,c=a+b,0,1-a-b
    if variant=="wrong-clock-edge":edge=-1
    if variant=="no-history":a=b=0
    if variant=="wrong-gain":c*=.75
    return f'''`include "constants.vams"
`include "disciplines.vams"
module identified_sc(vin, clk, out);
input vin,clk;output out;
electrical vin,clk,out;
real y,yold,ynew;
analog begin
  @(initial_step) begin y=0;yold=0;end
  @(cross(V(clk)-0.5,{edge})) begin
    ynew={a:.15g}*y+{b:.15g}*yold+{c:.15g}*V(vin);
    yold=y;y=ynew;
  end
  V(out)<+transition(y,0,5e-9,5e-9);
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

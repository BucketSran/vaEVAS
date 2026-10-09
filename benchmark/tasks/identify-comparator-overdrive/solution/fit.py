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
        rows=read(public,c)
        for k,v in enumerate(c["amplitudes"]):
            start=c["first_rise"]+k*c["period"];end=start+c["widths"][k]
            direction=1 if v>0 else -1;threshold=.5*direction
            for a,b in zip(rows,rows[1:]):
                if start<a["time_s"]<end and direction*(a["out_V"]-threshold)<0<=direction*(b["out_V"]-threshold):
                    at=a["time_s"]+(b["time_s"]-a["time_s"])*(threshold-a["out_V"])/(b["out_V"]-a["out_V"])
                    xs.append((abs(v),int(v<0)));ys.append(at-start-.5e-9);break
    best=None
    for j in range(1,2001):
        q=j*1e-5
        design=[[1,sign,1/(v+q)] for v,sign in xs]
        p=regress(design,ys)
        error=sum((sum(a*b for a,b in zip(x,p))-y)**2 for x,y in zip(design,ys))
        if best is None or error<best[0]:best=(error,p,q)
    d,asym,k=best[1]
    return d,d+asym,k,best[2]

def model(parameters,variant="reference"):
    dp,dn,k,q=parameters
    cancel="if (active > 0.5 && V(clk)>0.5)"
    if variant=="constant-delay":dp=dn=(dp+dn)/2+k/(.08+q);k=0
    if variant=="symmetric-delay":dn=dp
    if variant=="late-after-reset":cancel=""
    if variant=="wrong-dispersion":k*=.25
    return f'''`include "constants.vams"
`include "disciplines.vams"
module identified_comparator(vin,clk,out);
input vin,clk;output out;electrical vin,clk,out;
real due,active,pending,result,d;
analog begin
  @(initial_step) begin due=1e9;active=0;pending=0;result=0;end
  @(cross(V(clk)-0.5,+1)) begin
    pending=(V(vin)>0)?1:-1;
    d=((V(vin)>0)?{dp:.15g}:{dn:.15g})+{k:.15g}/(abs(V(vin))+{q:.15g});
    due=$abstime+d;active=1;
  end
  @(cross(V(clk)-0.5,-1)) begin result=0;active=0;end
  @(timer(due)) begin {cancel} result=pending;end
  V(out)<+transition(result,0,1e-9,1e-9);
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

"""Fit split channel acquisition dynamics exclusively from public training CSVs."""
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy import __version__ as SCIPY_VERSION
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent;TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification'

def components(p,u,y,gn=1.8,gp=0):
    kn,kp,vtn,vtp,bn,bp,ln,lp,tn,tp=p
    lo=np.minimum(u,y);hi=np.maximum(u,y);delta=hi-lo
    on=np.maximum(0,gn-lo-vtn-bn*(np.sqrt(.7+lo)-np.sqrt(.7)))
    op=np.maximum(0,hi-gp-vtp-bp*(np.sqrt(2.5-hi)-np.sqrt(.7)))
    dn=np.minimum(delta,on);dp=np.minimum(delta,op)
    n=kn*(on-.5*dn)*np.where(delta>1e-8,dn/np.maximum(delta,1e-8),1)*(1+ln*delta)/(1+tn*on)
    p=kp*(op-.5*dp)*np.where(delta>1e-8,dp/np.maximum(delta,1e-8),1)*(1+lp*delta)/(1+tp*op)
    return n,p

def observations(exps,records):
    samples=[]
    for exp in exps['train']:
        rows=records[exp['name']]
        for k in range(1,len(rows)-1):
            t,u,clock,y=rows[k];a=rows[k-1];b=rows[k+1]
            # Fit settled channels, avoiding clock and input charge injection.
            if not any(lo+.15e-9<t<hi-.05e-9 for lo,hi in exp['tracks']):continue
            if any(abs(t-vt)<.2e-9 for vt,v in exp['vin'] if vt>0):continue
            if abs(u-y)<.025 or max(abs(a[1]-u),abs(b[1]-u))>1e-6 or a[2]>.1 or b[2]>.1:continue
            dv=(b[3]-a[3])/(b[0]-a[0])*1e-9
            if .01<dv/(u-y)<10:samples.append((u,y,dv))
    return np.array(samples)

def validate(parameters,table,tau,exps,records):
    # A dense gate table accelerates offline integration; candidate VA uses
    # the channel equation itself. This is not actual VA/backend evidence.
    inputs=np.array(table['input_grid_V']);states=np.array(table['state_grid_V']);correction=np.array(table['correction'])
    ug=np.linspace(.2,1.6,57);gg=np.linspace(0,1.8,37);u,y,g=np.meshgrid(ug,ug,gg,indexing='ij')
    c=np.array([np.interp(ug,states,row) for row in correction]);c=np.array([np.interp(ug,inputs,c[:,j]) for j in range(len(ug))]).T
    n,p=components(parameters,u,y,gn=g,gp=1.8-g);n*=c[:,:,None];p*=c[:,:,None]
    def lookup(arr,u,y,g):
        pu=max(0,min(55.999999,(u-.2)/.025));py=max(0,min(55.999999,(y-.2)/.025));pg=max(0,min(35.999999,g/.05));i=int(pu);j=int(py);k=int(pg);a=pu-i;b=py-j;c=pg-k
        return (1-a)*((1-b)*((1-c)*arr[i,j,k]+c*arr[i,j,k+1])+b*((1-c)*arr[i,j+1,k]+c*arr[i,j+1,k+1]))+a*((1-b)*((1-c)*arr[i+1,j,k]+c*arr[i+1,j,k+1])+b*((1-c)*arr[i+1,j+1,k]+c*arr[i+1,j+1,k+1]))
    out={}
    for exp in exps['train']+exps['selftest']:
        times=np.arange(round(exp['stop']/1e-11)+1)*1e-11;vp=np.array(exp['vin']);cp=np.array(exp['clock']);vs=np.interp(times,vp[:,0],vp[:,1]);clocks=np.interp(times,cp[:,0],cp[:,1]);y=exp['initial'];z=1.8;pred=[]
        for vin,clock in zip(vs,clocks):
            pred.append(y);rate=lookup(n,vin,y,z)+lookup(p,vin,y,1.8-clock)
            y+=.01*rate*(vin-y);z+=.01*(1.8-clock-z)/(tau[0] if 1.8-clock>z else tau[1])
        rows=records[exp['name']];err=abs(np.interp(rows[:,0],times,pred)-rows[:,3])
        track=[float(np.sqrt(np.mean(err[(rows[:,0]>=a)&(rows[:,0]<=b)]**2))) for a,b in exp['tracks']]
        hold=[float(np.max(err[(rows[:,0]>=a)&(rows[:,0]<=b)])) for a,b in exp['holds']]
        samples=[float(np.interp(t,rows[:,0],err)) for t in exp['samples']]
        out[exp['name']]={'track_rms':max(track),'sample_max':max(samples),'hold_max':max(hold)}
    return out

def main():
    exps=json.loads((TASK/'environment/public/experiments.json').read_text());records={e['name']:np.loadtxt(TASK/'environment/public/data'/(e['name']+'.csv'),delimiter=',',skiprows=1) for e in exps['train']+exps['selftest']};s=observations(exps,records)
    def residual(p):
        n,pp=components(p,s[:,0],s[:,1]);return (n+pp)*(s[:,0]-s[:,1])-s[:,2]
    fit=least_squares(residual,[3,.6,.45,.45,.4,.4,.1,.1,.1,.1],bounds=([.01,.01,.2,.2,0,0,0,0,0,0],[10,10,.9,.9,2,2,2,2,3,3]),max_nfev=2000,xtol=1e-12,ftol=1e-12,gtol=1e-12)
    if not fit.success:raise RuntimeError('public channel fit did not converge')
    parameters=fit.x;n,pp=components(parameters,s[:,0],s[:,1]);bins={}
    for (u,y,dv),rate in zip(s,n+pp):
        key=(round(u,5),round(y/.025)*.025)
        if rate>.01:bins.setdefault(key,[]).append(np.log(dv/(u-y)/rate))
    nodes=np.array(list(bins));values=np.array([np.median(v) for v in bins.values()])
    # Selected by minimum worst training acquisition RMS over scale {.2,.4},
    # tau_up {.06,.07,.08,.09} ns with tau_down .08 ns. Selftest/hidden truth
    # did not enter parameter selection; the full public study is retained.
    scale=.2;regularization=.01;tau=[.09,.08]
    kernel=np.exp(-np.sum((nodes[:,None]-nodes[None,:])**2,axis=-1)/(2*scale**2));coefs=np.linalg.solve(kernel+regularization*np.eye(len(nodes)),values)
    summary={'fit_library_versions':{'numpy':np.__version__,'scipy':SCIPY_VERSION},'fit_public_samples':len(s),'parameters':parameters.tolist(),'parameter_order':['kn','kp','vtn','vtp','body_n','body_p','lambda_n','lambda_p','theta_n','theta_p'],'tau_ns':tau,'kernel_scale_V':scale,'kernel_regularization':regularization,'correction_bounds':[.7,1.3],'steady_derivative_rms_V_per_ns':float(np.sqrt(np.mean(residual(parameters)**2))),'training_sha256':{e['name']:hashlib.sha256((TASK/'environment/public/data'/(e['name']+'.csv')).read_bytes()).hexdigest() for e in exps['train']}}
    for count in [15,29]:
        grid=np.linspace(.2,1.6,count);query=np.stack(np.meshgrid(grid,grid,indexing='ij'),axis=-1).reshape(-1,2);correction=np.clip(np.exp(np.exp(-np.sum((query[:,None]-nodes[None,:])**2,axis=-1)/(2*scale**2))@coefs).reshape(count,count),.7,1.3)
        table={'input_grid_V':grid.tolist(),'state_grid_V':grid.tolist(),'correction':correction.tolist()};metrics=validate(parameters,table,tau,exps,records);table['public_offline_validation']=metrics
        print(count,'training RMS max',max(v['track_rms'] for k,v in metrics.items() if k.startswith('train')),'selftest',{k:v for k,v in metrics.items() if k.startswith('selftest')},flush=True)
        (HERE/f'rate-table-{count}.json').write_text(json.dumps(table,indent=2)+'\n')
    (HERE/'switch-fit.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main()

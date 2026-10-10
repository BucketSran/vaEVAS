"""Infer a positive state-dependent rate from public static-step trajectories."""
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3];TASK=ROOT/'benchmark/tasks/v2-data-sampling-identification'
exps=json.loads((TASK/'environment/public/experiments.json').read_text());us=[.2,.3,.5,.6,.9,1.1,1.2,1.4,1.5,1.6]
def table(grid):
    result=[]
    for i,u in enumerate(us):
        samples=[]
        for j in [0,1]:
            rows=np.loadtxt(TASK/'environment/public/data'/f'train-sweep-{i}-{j}.csv',delimiter=',',skiprows=1)
            for k in range(1,len(rows)-1):
                t,uu,clk,y=rows[k]
                if 40.45e-9<t<45.85e-9 and abs(u-y)>.015:
                    rate=(rows[k+1,3]-rows[k-1,3])/(rows[k+1,0]-rows[k-1,0])*1e-9/(u-y)
                    if .01<rate<10:samples.append((y,rate))
        samples.sort();ys,rs=zip(*samples);result.append(np.interp(grid,ys,rs).tolist())
    return result
for count in [15,29]:
    ys=np.linspace(.2,1.6,count);rates=table(ys);out={}
    def rate(u,y):return np.interp(u,us,[np.interp(y,ys,row) for row in rates])
    for exp in exps['selftest']:
        truth=np.loadtxt(TASK/'environment/public/data'/(exp['name']+'.csv'),delimiter=',',skiprows=1);dt=.01e-9;y=exp['initial'];pred=[];vp=np.array(exp['vin']);cp=np.array(exp['clock'])
        for n in range(round(exp['stop']/dt)+1):
            t=n*dt;u=np.interp(t,vp[:,0],vp[:,1]);clock=np.interp(t-.08e-9,cp[:,0],cp[:,1]);pred.append(y)
            if clock<.9:y+=dt*rate(u,y)*1e9*(u-y)
        err=abs(np.interp(truth[:,0],np.arange(len(pred))*dt,pred)-truth[:,3]);track=[];hold=[]
        for a,b in exp['tracks']:track.append(float(np.sqrt(np.mean(err[(truth[:,0]>=a)&(truth[:,0]<=b)]**2))))
        for a,b in exp['holds']:hold.append(float(np.max(err[(truth[:,0]>=a)&(truth[:,0]<=b)])))
        out[exp['name']]={'track_rms':max(track),'hold_max':max(hold)}
    print(count,out)
    (Path(__file__).parent/f'rate-table-{count}.json').write_text(json.dumps({'input_grid_V':us,'state_grid_V':ys.tolist(),'rate_per_ns':rates,'public_offline_selftest':out},indent=2)+'\n')

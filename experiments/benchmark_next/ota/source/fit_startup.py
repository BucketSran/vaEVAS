"""Identify startup bias memory from full public enable experiments."""
import json,argparse
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

def fit(source,out):
 truth=[];levels=[]
 tt=np.arange(0,300.1,.25)
 for name in ['train-0','train-1','train-2']:
  r=np.array(json.loads((source/(name+'.json')).read_text())['rows']);t=r[:,0]*1e9
  for base in [1000,15000]:
   truth.append(np.interp(base+tt,t,r[:,3]));levels.append(np.interp(base+250,t,r[:,3]))
 Y=np.array(truth);L=np.array(levels)
 bias=np.array([np.clip((tt-100)/100,0,1) if i%2==0 else np.ones(len(tt)) for i in range(6)])
 enable=1.5*np.clip(tt/100,0,1)
 def predict(p):
  tau,threshold,width,negative,center,negwidth,en_threshold,ytau=p
  b=np.zeros(6);y=b.copy();pred=[y.copy()]
  for k in range(1,len(tt)):
   current=bias[:,k] if enable[k]>en_threshold else np.zeros(6)
   db=(current-b)/tau;b=b+.25*db
   f=1/(1+np.exp(np.clip(-(b-threshold)/width,-700,700)))
   target=L*f-negative*db*np.exp(-((b-center)/negwidth)**2)
   y=y+(1-np.exp(-.25/ytau))*(target-y);pred.append(y.copy())
  return np.array(pred).T
 p=[20,.7,.03,6,.5,.22,.9,1]
 res=least_squares(lambda p:(predict(p)-Y).ravel(),p,bounds=([2,.3,.005,0,.1,.03,.5,.1],[80,.95,.15,20,.9,.5,1.3,10]),max_nfev=100)
 pred=predict(res.x)
 r=np.array(json.loads((source/'train-0.json').read_text())['rows']);m=(r[:,0]>=14.55e-6)&(r[:,0]<=14.558e-6);en=r[m,2];yy=r[m,3];base=np.interp(14.5e-6,r[:,0],r[:,3])
 def down(p):c,w=p;return base*np.exp(-w/.015*np.exp((c-en)/w))
 shutdown=least_squares(lambda p:down(p)-yy,[.70,.007],bounds=([.65,.001],[.75,.03])).x
 result=dict(startup=res.x.tolist(),shutdown=shutdown.tolist(),max_V=float(np.max(abs(pred-Y))),rms_V=float(np.sqrt(np.mean((pred-Y)**2))),training_records=['train-0','train-1','train-2']);out.write_text(json.dumps(result,indent=2)+'\n');print(result)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();fit(a.source,a.output)

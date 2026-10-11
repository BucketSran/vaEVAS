"""Fit a nonlinear second-order response; training trajectories only."""
import json,argparse
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares
from scipy.interpolate import CubicSpline

def fit(source,out):
 segments=[];knots=[]
 for name in ['train-0','train-1','train-2']:
  d=json.loads((source/(name+'.json')).read_text());r=np.array(d['rows']);t=r[:,0]*1e9;u=r[:,1];y=r[:,3]
  for edge in [3000,5000,7000,9000,11000,13000]:
   tt=np.arange(0,40.01,.1);yy=np.interp(edge+tt,t,y);uu=np.interp(edge+tt,t,u)
   segments.append((uu,yy));knots.append([np.interp(edge+100,t,u),np.interp(edge+100,t,y)])
 knots=sorted(knots);kx,ky=np.array(knots).T
 U=np.array([s[0] for s in segments]);Y=np.array([s[1] for s in segments]);T=np.interp(U,kx,ky)
 # Give the low-output large step equal influence despite its longer transient.
 weights=np.where((T[:,-1]<.45)&(Y[:,0]>.9),2.0,1.0)[:,None]
 def predict(p):
  omega,zeta,saturation,asym,slowhigh,slowlo,zeta_asym=p
  state=Y[:,0].copy();vel=state*0;pred=[state.copy()]
  for i in range(1,len(U[0])):
   target=(T[:,i-1]+T[:,i])/2;err=target-state
   om=omega*(1+asym*np.tanh(err/.05))*(1-slowhigh/(1+np.exp(-(state-1.2)*30)))*(1-slowlo/(1+np.exp((state-.5)*30)))
   damp=zeta*(1+zeta_asym*np.tanh(err/.05))
   accel=om**2*saturation*np.tanh(err/saturation)-2*damp*om*vel
   # midpoint integration using one predictor half step.
   vhalf=vel+.05*accel;yhalf=state+.05*vel;eh=target-yhalf
   accel=om**2*saturation*np.tanh(eh/saturation)-2*damp*om*vhalf
   state=state+.1*vhalf;vel=vel+.1*accel;pred.append(state.copy())
  return np.array(pred).T
 res=least_squares(lambda p:((predict(p)-Y)*weights).ravel(),[.9,.65,.5,0,.15,.5,0],bounds=([.1,.2,.05,-.5,0,0,-.5],[4,2,10,.5,.8,.9,.5]),max_nfev=90)
 pred=predict(res.x);result=dict(knots=knots,dynamics=res.x.tolist(),training_records=['train-0','train-1','train-2'],max_V=float(np.max(abs(pred-Y))),rms_V=float(np.sqrt(np.mean((pred-Y)**2))))
 out.write_text(json.dumps(result,indent=2)+'\n');print(out.read_text())
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();fit(a.source,a.output)

"""Independent finite history sampling references, no simulator imports."""
from fractions import Fraction as F
from pathlib import Path
import json
from spec_b_checker import rat,read_psf
V=F(1,10**6);T=F(1,10**9);US=F(1,10**6)
A=F.from_float(2e-6);B=F.from_float(3e-6);C=F.from_float(6e-6);STOP=F.from_float(7e-6);M=F.from_float(1e6)

def analytic(case,t):
 t=rat(t);area=sum((max(F(0),t-k*A) for k in (1,2,3)),F(0))+10*sum((max(F(0),t-k*B) for k in (1,2)),F(0))
 u=t/C if case=='linear_pwl_near' and t<C else F(1) if case=='linear_pwl_near' else t/STOP
 integral_u=t*t/(2*C) if t<=C else C/2+t-C
 z=1/(1+M*area) if case=='nonlinear_near' else M*(area+integral_u)
 last=max((k*B for k in (1,2) if t>k*B),default=F(0))
 if last==0:y=F(1)
 else:
  a=sum((max(F(0),last-k*A) for k in (1,2,3)),F(0))+10*sum((max(F(0),last-k*B) for k in (1,2)),F(0))
  y=1/(1+M*a) if case=='nonlinear_near' else M*(a+last*last/(2*C))
 return dict(u=u,z=z,y=y,n=F(sum(t>k*A for k in (1,2,3))),m=F(sum(t>k*B for k in (1,2))),h=F(0))

def select_names(rows):
 # Exact named aliases only; duplicate candidates are ambiguous, not silently combined.
 names=set(rows[0]);mapping={};missing=[]
 for short,aliases in {'u':['u'],'y':['y'],'z':['Xdut.z','xdut.z','dut.z','z'],'n':['Xdut:n','Xdut.n','xdut:n','xdut.n','dut.n','n'],'m':['Xdut:m','Xdut.m','xdut:m','xdut.m','dut.m','m'],'h':['Xdut:h','Xdut.h','xdut:h','xdut.h','dut.h','h']}.items():
  matches=[x for x in aliases if x in names]
  if len(matches)>1:raise ValueError('ambiguous '+short+' signals '+str(matches))
  if matches:mapping[short]=matches[0]
  else:missing.append(short)
 return mapping,missing

def inspect(rows,case,step):
 out={'case':case,'rows':len(rows),'numeric_status':'I','event_status':'I','qualification_status':'I','failures':[]}
 if len(rows)<3:out['failures'].append('missing waveform');return out
 try:
  mapping,missing=select_names(rows);out['signal_mapping']=mapping;out['missing_signals']=missing
  if any(k in missing for k in ('u','y','z')):out['failures'].append('missing physical output');return out
  rows=[{'time':rat(row['time']),**{k:rat(row[v]) for k,v in mapping.items()}} for row in rows]
 except (KeyError,ValueError,OverflowError) as e:out.update(numeric_status='F',event_status='F');out['failures'].append(str(e));return out
 if any(b['time']<a['time'] for a,b in zip(rows,rows[1:])):out.update(numeric_status='F',event_status='F');out['failures'].append('unordered records');return out
 domain=rows[0]['time']==0 and rows[-1]['time']==STOP;out['domain_exact_rational_complete']=domain
 if not domain:out['failures'].append('missing exact scientific endpoint')
 maxgap=max(b['time']-a['time'] for a,b in zip(rows,rows[1:]));dense=maxgap<=rat(step)*(1+F(1,10**8));out['max_observed_gap_s']=float(maxgap)
 if not dense:out['failures'].append('sparse global observation')
 err={k:F(0) for k in ('u','y','z')};centers=[B,2*B]
 for row in rows:
  ans=analytic(case,row['time'])
  for k in err:
   if k=='y' and any(abs(row['time']-c)<=T for c in centers):continue
   err[k]=max(err[k],abs(row[k]-ans[k]))
 out['max_errors_V']={k:float(v) for k,v in err.items()};out['finite_numeric_status']='F' if any(v>V for v in err.values()) else 'P';out['numeric_status']='F' if out['finite_numeric_status']=='F' else 'P' if domain and dense else 'I'
 brackets=[];bad=False;insufficient=False
 for signal,targets in [('n',[A,2*A,3*A]),('m',[B,2*B])]:
  if signal in missing:insufficient=True;out['failures'].append('missing counter '+signal);continue
  old=F(0);prev=None;changes=[]
  for row in rows:
   value=row[signal]
   if value.denominator!=1 or value<0:bad=True;out['failures'].append('noninteger '+signal)
   if value!=old:
    if value!=old+1:bad=True;out['failures'].append('nonunit/reversed '+signal)
    changes.append((prev['time'] if prev else row['time'],row['time']));old=value
   if all(abs(row['time']-c)>T for c in targets) and value!=sum(row['time']>c for c in targets):bad=True
   prev=row
  if len(changes)!=len(targets):bad=True;out['failures'].append('wrong event count '+signal)
  for (lo,hi),nominal in zip(changes,targets):
   brackets.append({'signal':signal,'nominal_rational':str(nominal),'lower':str(lo),'upper':str(hi),'width_s':float(hi-lo)})
   if lo>nominal+T or hi<nominal-T:bad=True
   elif lo<nominal-T or hi>nominal+T or hi-lo>T:insufficient=True
 if 'h' in mapping and any(row['h']!=0 for row in rows):bad=True;out['failures'].append('spurious cross')
 if 'h' in missing:insufficient=True;out['failures'].append('unobserved cross counter')
 out['event_brackets']=brackets;out['finite_event_status']='F' if bad else 'I' if insufficient else 'P';out['event_status']='F' if bad else 'I' if insufficient or not domain else 'P'
 out['exact_boundaries']=[{'rational':str(c),'records':[{k:str(row[k]) for k in row} for row in rows if row['time']==c],'status':'I','note':'Actual retained tokens only; does not infer nearby-clock callback order or correctly rounded export origin.'} for c in (A,B,2*A,3*A,2*B)]
 out['qualification_status']='F' if 'F' in (out['numeric_status'],out['event_status']) else 'I';out['limits']='PSF origin, unobserved nearby n/m callback order at3A<2B, true exact boundaries and continuous-time certification remain unqualified.'
 return out

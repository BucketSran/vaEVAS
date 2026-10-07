"""Independent exact binary-literal model oracle; no frontend/kernel imports."""
from fractions import Fraction as F
import math
V=F(1,10**6);T=F(1,10**9)
def Q(v):return F.from_float(v) if isinstance(v,float) else F(v)
A=Q(.1);P=Q(.2);TAU=A+P;ONE=Q(.30000000000000004)
SOURCE_ROOT=Q(.4)*Q(.3)/(Q(.3)+Q(.1));HIDDEN_ROOT=TAU+Q(1e-18)
def clocks(case):return [(0,A),(1,SOURCE_ROOT),(0,TAU),(2,ONE)] if case=='mixed_source' else [(0,A),(0,TAU),(2,HIDDEN_ROOT),(1,ONE)]
def formula(case,t):
 t=Q(t)
 if case=='mixed_source':
  u=-Q(.3)+(Q(.3)+Q(.1))*min(t,Q(.4))/Q(.4)
  n=Q(int(t>A)+int(t>TAU));k=Q(int(t>SOURCE_ROOT));j=Q(int(t>ONE))
  return dict(u=u,y=n+k+j,n=n,k=k,j=j)
 n=Q(int(t>A)+int(t>TAU));q=max(Q(0),n-1);h=Q(int(t>HIDDEN_ROOT));m=Q(int(t>ONE))
 return dict(u=t,z=max(Q(0),t-TAU),y=h,n=n,q=q,h=h,m=m)
def inspect(rows,case,stop,events=None,rejection=None):
 out={'case':case,'numeric_status':'I','event_status':'I','exact_order_status':'I','qualification_status':'I','failures':[]}
 if case=='hidden_tight':
  representative=float(HIDDEN_ROOT)
  if Q(representative)<HIDDEN_ROOT:representative=math.nextafter(representative,math.inf)
  delay=Q(representative)-HIDDEN_ROOT
  out['minimum_binary64_representative_delay_s']=float(delay);out['declared_ttol_s']=1e-20
  if rejection is not None:
   out['rejection_status']='P' if rejection.get('semantic_category')=='cross_ttol_unrepresentable' and rejection.get('accepted_waveform') is False else 'F'
  else:out['rejection_status']='I'
  out['rejection_obligation']='EVAS must specifically reject unrepresentable cross ttol. Spectre finite counts/waveform cannot establish this obligation.'
 if not rows:return out
 signals=formula(case,Q(0)).keys();mapped=[]
 for row in rows:
  r={'time':Q(row['time'])}
  for k in signals:
   aliases=[k,'Xdut:'+k,'Xdut.'+k];found=[x for x in aliases if x in row]
   if len(found)>1:raise ValueError('ambiguous '+k)
   if found:r[k]=Q(row[found[0]])
  mapped.append(r)
 if any(b['time']<a['time'] for a,b in zip(mapped,mapped[1:])):out['failures'].append('unordered records');out.update(numeric_status='F',event_status='F');return out
 missing=[k for k in signals if k not in mapped[0]];out['missing_signals']=missing
 err={k:Q(0) for k in ['u','y']+([] if case=='mixed_source' else ['z']) if k not in missing};bad=False
 for row in mapped:
  ans=formula(case,row['time']);near=any(abs(row['time']-c)<=T for _,c in clocks(case))
  for k in err:
   if k=='y' and near:continue
   err[k]=max(err[k],abs(row[k]-ans[k]))
  for k in signals:
   if k in ['u','y','z'] or k in missing:continue
   if row[k].denominator!=1 or (not near and row[k]!=ans[k]):bad=True
 budget=Q(1e-7) if case=='mixed_source' else V
 out['max_errors_V']={k:float(v) for k,v in err.items()};out['finite_numeric_status']='F' if any(v>budget for v in err.values()) else 'I' if any(k in missing for k in ['u','y']+([] if case=='mixed_source' else ['z'])) else 'P'
 out['domain_exact_rational_complete']=mapped[0]['time']==0 and mapped[-1]['time']==Q(stop)
 out['numeric_status']=out['finite_numeric_status'] if out['finite_numeric_status']!='P' or out['domain_exact_rational_complete'] else 'I'
 changes={};insufficient=any(k not in mapped[0] for k in signals if k not in ['u','y','z'])
 targets={'n':[A,TAU],'k':[SOURCE_ROOT],'j':[ONE]} if case=='mixed_source' else {'n':[A,TAU],'q':[TAU],'h':[HIDDEN_ROOT],'m':[ONE]}
 for k,ts in targets.items():
  if k in missing:continue
  old=Q(0);prev=mapped[0];cs=[]
  for row in mapped:
   if row[k]!=old:
    if row[k]!=old+1:bad=True
    cs.append((prev['time'],row['time']));old=row[k]
   prev=row
  if len(cs)!=len(ts):bad=True
  changes[k]=[{'lower':str(lo),'upper':str(hi),'nominal':str(c)} for (lo,hi),c in zip(cs,ts)]
  for (lo,hi),c in zip(cs,ts):
   if lo>c+T or hi<c-T:bad=True
   elif lo<c-T or hi>c+T or hi-lo>T:insufficient=True
 out['event_brackets']=changes;out['finite_event_status']='F' if bad else 'I' if insufficient else 'P';out['event_status']=out['finite_event_status'] if out['finite_event_status']!='P' or out['domain_exact_rational_complete'] else 'I'
 if events is not None:
  order=[e['event_index'] for e in events];out['actual_event_index_order']=order;out['exact_order_status']='P' if order==[i for i,_ in clocks(case)] else 'F'
 out['limits']='Finite named signal records only. Decimal PSF origin, exact boundary convention and sub-ULP callback order remain I without separate proof. EVAS event-index order and tight rejection are separate obligations.'
 return out

"""Derived actual stderr JSON and actual per-query state adapter, no kernel imports."""
from fractions import Fraction as F
from adapter import event_contract
import json

def transport_rejection(stdout,stderr,returncode):
 if stdout.strip():
  try:r=json.loads(stdout)
  except ValueError:return {'status':'F','reason':'stdout malformed'}
  detail=r.get('detail',{});accepted='solutions' in r or 'transient' in r;channel='stdout detail'
 else:
  try:detail=json.loads(stderr)
  except ValueError:return {'status':'F','reason':'stderr malformed'}
  accepted=False;channel='stderr top-level structured error'
 out={'returncode':returncode,'channel':channel,'actual_kind':detail.get('kind'),'actual_message':detail.get('message'),'accepted_waveform':accepted}
 out['status']='P' if returncode!=0 and detail.get('kind')=='event_resolution' and 'cross_ttol_unrepresentable' in str(detail.get('message','')) and not accepted else 'F'
 return out

def query_state_contract(transient,checker,family):
 names=transient.get('state_names',[]);states=transient.get('states',[]);times=transient['times'];out={'status':'P','checked':[],'exact_boundary_records':[],'failures':[]}
 if len(states)!=len(times):return {'status':'F','failures':['missing actual query state vectors']}
 short=[n.split(':')[-1] for n in names]
 for t,values in zip(times,states):
  if len(values)!=len(names):out['status']='F';out['failures'].append('state vector dimension');continue
  clock=F.from_float(t);actual={k:F.from_float(v) for k,v in zip(short,values)}
  if any(clock==c for _,c in checker.clocks(family)):
   out['exact_boundary_records'].append({'time':t,'actual':{k:str(v) for k,v in actual.items()},'status':'I'});continue
  expected=checker.formula(family,clock);wanted={k:expected[k] for k in actual};wrong=[k for k in actual if actual[k]!=wanted[k]]
  if wrong:out['status']='F';out['failures'].append({'time':t,'wrong_states':wrong})
  out['checked'].append({'time':t,'exact_numeric_query_rational':str(clock),'actual':{k:str(v) for k,v in actual.items()},'expected':{k:str(v) for k,v in wanted.items()},'status':'F' if wrong else 'P'})
 out['scope']='Actual transient.states at actual numeric querytimes, compared independently to exact Fraction phases. Never reconstructed from eventrepresentatives. Exactclock boundaries remain separateI. This is stronger phaseobligation, not change to frozen finite1ns waveformwindow checker.'
 return out

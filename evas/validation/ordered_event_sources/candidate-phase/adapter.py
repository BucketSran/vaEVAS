"""Actual event records and structured error adapter, independent of frontend/kernel."""
from fractions import Fraction as F
import importlib.util

def event_contract(events,states,checker,family):
 names=[s['name'] for s in states];expected={s['name']:F.from_float(s['initial']) for s in states};clocks=checker.clocks(family);out={'status':'P','actual_order':[e['event'] for e in events],'expected_order':[i for i,_ in clocks],'failures':[],'max_representative_clock_distance_s':0.0}
 def fail(message):out['status']='F';out['failures'].append(message)
 if out['actual_order']!=out['expected_order']:fail('wrong exact event source sequence')
 if len(events)!=len(clocks):fail('wrong callback count')
 for event,(index,clock) in zip(events,clocks):
  if len(event['before'])!=len(names) or len(event['after'])!=len(names):fail('state vector length');continue
  before={k:F.from_float(v) for k,v in zip(names,event['before'])};after={k:F.from_float(v) for k,v in zip(names,event['after'])}
  if before!=expected:fail('wrong before state or unrelated state restoration')
  target=dict(expected)
  if family=='mixed_source':target[{0:'n',1:'k',2:'j'}[index]]+=1
  elif index==0:target['n']+=1;target['q']=target['n']-1
  elif index==1:target['m']+=1
  elif index==2:target['h']+=1
  if after!=target:fail('wrong callback body state transition')
  distance=abs(F.from_float(event['time'])-clock);out['max_representative_clock_distance_s']=max(out['max_representative_clock_distance_s'],float(distance))
  if distance>checker.T:fail('representative outside fixed physical1ns target')
  expected=target
 out['final_actual_state']={k:str(F.from_float(v)) for k,v in zip(names,events[-1]['after'])} if events else {k:str(v) for k,v in expected.items()}
 out['exact_float_boundary_status']='I';out['scope']='Explicit event source sequence and authoritative before/after states checked independently. Representativetime distance isfinite timing evidence, not claim floattime equals exact physical clock or queryside convention.'
 return out

def rejection_contract(response,returncode):
 detail=response.get('detail',{}) if isinstance(response,dict) else {};accepted=isinstance(response,dict) and ('solutions' in response or 'transient' in response)
 actual={'kind':detail.get('kind'),'message':detail.get('message'),'accepted_waveform':accepted,'returncode':returncode}
 actual['status']='P' if isinstance(detail,dict) and detail.get('kind')=='event_resolution' and 'cross_ttol_unrepresentable' in str(detail.get('message','')) and not accepted else 'F'
 return actual

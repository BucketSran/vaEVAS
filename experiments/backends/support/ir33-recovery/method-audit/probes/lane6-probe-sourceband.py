"""Calibrate unchanged SourceMath small-box test through public response validator."""
import sys,math,json,copy,unittest,hashlib
from pathlib import Path
from fractions import Fraction as Q
from unittest.mock import patch
from probe_context import context
R,P=context()
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
import test_source_math as t
from evas.protocol import validate_response
from evas.ir import SCHEMA_VERSION
center=.1;radius=1e-14
lo=math.nextafter(float(Q(center)-Q(radius)),-math.inf);hi=math.nextafter(float(Q(center)+Q(radius)),math.inf)
def outward(value,up):
 v=float(value)
 return math.nextafter(v,math.inf if up else -math.inf)
records=[]
for mutation in ['correct_source_band','dropped_source_band','wrong_output']:
 requests=[]
 def fake(program,sources,times,**kw):
  a,b=(center,center) if mutation=='dropped_source_band' else (lo,hi)
  y=float(t.reference(center));yl=outward(t.reference(a),False);yh=outward(t.reference(b),True)
  if mutation=='wrong_output':y+=.01;yl+=.01;yh+=.01
  nodes=list(program.nodes);n=len(nodes);u=nodes.index('u');yi=nodes.index('y')
  values=[0.]*n;values[u]=center;values[yi]=y
  frame=[[v,v] for v in values];frame[u]=[a,b];frame[yi]=[yl,yh]
  response=dict(schema_version=SCHEMA_VERSION,engine='synthetic-calibration',nodes=nodes,
   solutions=[dict(voltages=list(values),max_residual_v=0.,max_residual_ratio=0.) for _ in times],
   transient=dict(times=list(times),state_names=[],states=[[] for _ in times],events=[],display_records=[],accepted_steps=0,discarded_trials=0),
   observation_evidence=dict(schema_version=1,nodes=nodes,effective_controls=dict(absolute_V=1e-12,relative=1e-10,stop_s=1.,max_step_s=.1,max_step_applied=False),sample_origins=['stateless_working_point']*len(times),initial_settled=True,voltage_bounds_V=[copy.deepcopy(frame) for _ in times]))
  validate_response(response,program,len(times),times)
  requests.append(dict(program=program.to_dict(),sources=sources,times=times,options={k:str(v) if isinstance(v,Path) else v for k,v in kw.items()},response=response,public_validator='accepted'))
  return response
 result=unittest.TestResult()
 with patch.object(t,'transient',side_effect=fake):
  t.SourceMath('test_small_true_source_box_encloses_both_independent_endpoint_roots').run(result)
 records.append(dict(mutation=mutation,actual=dict(testsRun=result.testsRun,passed=result.wasSuccessful(),failures=[s for _,s in result.failures],errors=[s for _,s in result.errors]),requests=requests))
out=dict(scope='Full unchanged unittest method; transient transport replaced by synthetic response that passed actual protocol.validate_response. No kernel run.',input_exact=dict(center=str(Q(center)),radius=str(Q(radius)),low=str(Q(center)-Q(radius)),high=str(Q(center)+Q(radius))),derivation='g=x*tanh(x/.05) is strictly increasing on the positive requested domain. Endpoint references must use original requested domain; original method instead derives endpoints from DUT-reported input bounds.',expected={'correct_source_band':'accept','dropped_source_band':'reject','wrong_output':'reject'},source_sha256=hashlib.sha256((R/'evas/tests/test_source_math.py').read_bytes()).hexdigest(),records=records)
P.write_text(json.dumps(out,indent=2)+'\n')
print([(v['mutation'],v['actual']['passed'],bool(v['actual']['errors'])) for v in records])

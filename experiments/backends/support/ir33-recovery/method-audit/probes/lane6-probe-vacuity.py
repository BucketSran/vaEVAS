"""Run three unchanged unittest methods with bounded synthetic transport results.
No kernel, build, simulator, or source mutation. Positive/empty/truncated/wrong controls.
"""
import sys,json,math,copy,hashlib,unittest
from pathlib import Path
from unittest.mock import patch
from probe_context import context
R,P=context()
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
import test_root_recovery as t

def report(kind):
 ds={
 'sample':[('root_demand',dict(source='current_root',consumer='y',target_width=.1)),('root_refinement',dict(stop='target_reached',width_after=.01))],
 'second':[('root_refinement',dict(target_width=.1,iterations=1)),('root_refinement',dict(target_width=None,iterations=1))],
 'time':[('root_demand',dict(time_sensitivity=1))]}
 return dict(counters={},records=[dict(kind=k,reason=json.dumps(v)) for k,v in ds[kind]])
cases=[('test_sample_gets_voltage_demand_and_stops_at_a_certified_target','sample',[0,0,math.sqrt(2),math.sqrt(2)]),('test_second_consumer_can_require_a_bounded_fallback','second',[0,0,1e6*math.sqrt(2),1e6*math.sqrt(2)]),('test_sampling_and_observation_time_do_not_cancel','time',[0,0,math.sqrt(2)-2,math.sqrt(2)-3])]
records=[]
for name,kind,wants in cases:
 for mutation in ['correct_numeric','empty','truncated_prefix','wrong_value']:
  values=wants if mutation=='correct_numeric' else [] if mutation=='empty' else wants[:2] if mutation=='truncated_prefix' else wants[:-1]+[0]
  response=dict(nodes=['0','u','y'],solutions=[dict(voltages=[0,float(k),v]) for k,v in enumerate(values)],transient=dict(events=[dict(kind='cross',time=math.sqrt(2))]))
  diagnostic=report(kind);requests=[]
  def observe(request):
   requests.append(copy.deepcopy(request));return copy.deepcopy(response),None,copy.deepcopy(diagnostic)
  def invoke(request,*args,**kwargs):return copy.deepcopy(response)
  result=unittest.TestResult()
  with patch.object(t,'observe',side_effect=observe),patch.object(t,'_invoke',side_effect=invoke):
   t.RootRecovery(name).run(result)
  records.append(dict(test='test_root_recovery.RootRecovery.'+name,mutation=mutation,requests=requests,response=response,diagnostic=diagnostic,actual=dict(testsRun=result.testsRun,passed=result.wasSuccessful(),failures=[s for _,s in result.failures],errors=[s for _,s in result.errors])))
out=dict(scope='Full unchanged Python unittest methods invoked; only observe/_invoke transport dependencies replaced. All other assertions retained. No production/kernel execution.',positive_definition='Correct numeric synthetic y trace at requested times with the exact runtime-event-only metadata expected by these old methods. This is not a qualified IR33 initial event trace.',expected={'correct_numeric':'accept','empty':'reject','truncated_prefix':'reject','wrong_value':'reject'},source_sha256=hashlib.sha256((R/'evas/tests/test_root_recovery.py').read_bytes()).hexdigest(),probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),records=records)
P.write_text(json.dumps(out,indent=2)+'\n')
print([(r['test'].split('.')[-1],r['mutation'],r['actual']['passed']) for r in records])

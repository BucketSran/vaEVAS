"""Original SourceMath methods with independent protocol-valid numerical controls."""
import sys,json,math,unittest
from pathlib import Path
from decimal import Decimal,localcontext
from unittest.mock import patch
R=Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night');S=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
import test_source_math as tests
records=[];controls=[]
for mutation in ('correct','wrong_representative_wide_box'):
 def invoke(request,kernel,timeout):
  p=json.loads(json.dumps(request['program']));nodes=p['nodes'];ts=request['transient']['output_times'];x=request['transient']['pwl'][0][0][1]
  with localcontext() as c:
   c.prec=120;d=Decimal.from_float(x);z=d/Decimal.from_float(.05);a,b=z.exp(),(-z).exp();answer=d*(a-b)/(a+b)
   if 'dut:z' in nodes:answer+=Decimal('.25')
  target=float(answer);reported=target if mutation=='correct' else target+.01
  values={'0':0.,'u':x,'y':reported,'dut:z':.25};row=[values[n] for n in nodes]
  bounds=[[math.nextafter(v,-math.inf),math.nextafter(v,math.inf)] for v in row]
  if mutation!='correct':bounds[nodes.index('y')]=[-1000.,1000.]
  response=dict(schema_version=p['schema_version'],engine='independent-synthetic-control',nodes=nodes,solutions=[dict(voltages=row.copy(),max_residual_v=0.,max_residual_ratio=0.) for _ in ts],transient=dict(times=ts,state_names=[],states=[[] for _ in ts],events=[],accepted_steps=0,discarded_trials=0),observation_evidence=dict(schema_version=1,nodes=nodes,effective_controls=dict(absolute_V=1e-12,relative=1e-10,stop_s=1.,max_step_s=.1,max_step_applied=False),sample_origins=['stateless_working_point']*len(ts),initial_settled=True,voltage_bounds_V=[bounds for _ in ts]))
  controls.append(dict(mutation=mutation,independent_answer=str(answer),request=request,response=response));return response
 for method in ('test_product_contains_independent_decimal_root_in_reported_box','test_multinode_certificate_uses_same_original_constraint_system'):
  case=tests.SourceMath(method);result=unittest.TestResult()
  with patch('evas.runtime._invoke',side_effect=invoke):case.run(result)
  records.append(dict(mutation=mutation,test=case.id(),passed=result.wasSuccessful(),failures=[x[1] for x in result.failures],errors=[x[1] for x in result.errors]))
(S/'source-math-calibration-raw.json').write_text(json.dumps(dict(results=records,controls=controls),indent=2));print(json.dumps(records,indent=2))
assert all(x['passed'] for x in records)

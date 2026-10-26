"""Run original tests against independent controls through the real public protocol."""
import sys, json, math, unittest, hashlib
from pathlib import Path
from unittest.mock import patch
R=Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
S=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
import test_selected_ln as tests
from history_migration_contract import selected_ln_oracle
records=[]
responses=[]
for mutation in ('correct','constant_wrong_output'):
 def invoke(request,kernel,timeout):
  p=json.loads(json.dumps(request['program'])); ts=request['transient']['output_times']; nodes=p['nodes']; sols=[]; boxes=[]
  for t in ts:
   values={'0':0.,'u':.7-t,'y':float(selected_ln_oracle(t)) if mutation=='correct' else 0.}
   row=[values[n] for n in nodes]
   sols.append(dict(voltages=row,max_residual_v=0.,max_residual_ratio=0.))
   boxes.append([[math.nextafter(v,-math.inf),math.nextafter(v,math.inf)] for v in row])
  out=dict(schema_version=p['schema_version'],engine='independent-synthetic-control',nodes=nodes,solutions=sols,
   transient=dict(times=ts,state_names=[s['instance']+':'+s['name'] for s in p['states']],states=[[] for _ in ts],events=[],accepted_steps=0,discarded_trials=0),
   observation_evidence=dict(schema_version=1,nodes=nodes,effective_controls=dict(absolute_V=1e-12,relative=1e-10,stop_s=1.,max_step_s=1.,max_step_applied=False),sample_origins=['stateless_working_point']*len(ts),voltage_bounds_V=boxes,initial_settled=True))
  responses.append(dict(mutation=mutation,request=request,response=out)); return out
 for method in ('test_extra_queries_preserve_common_physical_values','test_hidden_interior_clamp_uses_original_source_at_every_query'):
  case=tests.SelectedLn(method); result=unittest.TestResult()
  with patch('evas.runtime._invoke',side_effect=invoke):case.run(result)
  records.append(dict(mutation=mutation,test=case.id(),passed=result.wasSuccessful(),failures=[x[1] for x in result.failures],errors=[x[1] for x in result.errors]))
(S/'calibration-raw.json').write_text(json.dumps(dict(results=records,controls=responses),indent=2))
print(json.dumps(records,indent=2))
assert [x['passed'] for x in records]==[True,True,True,False]

"""Portable finite evidence replay, no simulations or local raw dependency."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as Q
import json,hashlib
import oracle_a,oracle_b
import deadline_oracle as finite_oracle
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def number(v):
 if isinstance(v,float):return F(v)
 d=Q(str(v));assert d.is_finite();return F(d)

def gate(v,iv):
 x=number(v);return max(abs(x-iv[0]),abs(x-iv[1]))<=F('1e-7')

def analyze_case(data):
 contract=data['contract'];times=contract['native_exact_query_tokens'];label=contract['label'];pairs=[];missing=[];mathchecks=[]
 for mode,r in data['dut'].items():
  assert [format(t,'.17g') for t in r['transient']['times']]==times
  assert all(number(v) is not None for row in r['solutions'] for v in row['voltages'])
  for i,t in enumerate(times):
   expected=finite_oracle.nominal(label,float(t));native=data['exact_query_rows'][t]
   if not native:missing.append({'mode':mode,'time_token':t})
   for node,iv in expected.items():
    dut=r['solutions'][i]['voltages'][r['nodes'].index(node)];mathchecks.append({'mode':mode,'time_token':t,'node':node,'pass':gate(dut,iv),'error_upper_V':float(max(abs(number(dut)-iv[0]),abs(number(dut)-iv[1])))})
    for row in native:
     assert Q(row['time'])==Q(t);native_name=next(n for n,v in contract['spectre_to_evas_nodes'].items() if v==node);ref=row['voltages'][native_name];difference=abs(number(dut)-number(ref))
     pairs.append({'mode':mode,'time_token':t,'node':node,'dut_voltage':dut,'native_voltage_token':ref,'oracle_interval':[str(x) for x in iv],'reference_math_error_upper_V':float(max(abs(number(ref)-iv[0]),abs(number(ref)-iv[1]))),'pair_error_V':float(difference),'pass':gate(dut,iv) and gate(ref,iv) and difference<=F('1e-7')})
  # Preserve original unit relational/consumer assertions independently of Spectre coverage.
  if label=='same_source_two_fresh':assert all(row['voltages'][r['nodes'].index('dut:a')]==2*row['voltages'][r['nodes'].index('y')] for row in r['solutions'])
  if label=='delay_two_instances':assert all(row['voltages'][r['nodes'].index('y0')]==row['voltages'][r['nodes'].index('y1')] for row in r['solutions'])
  if label=='idt_laplace_consumers':
   end=r['solutions'][-1]['voltages'];assert abs(end[r['nodes'].index('dut:i')]-(.5-1/3-.005))<.5e-7 and end[r['nodes'].index('dut:f')]>1.9
 assert data['dut']['ordinary']['solutions']==data['dut']['forced']['solutions']
 return {'label':label,'budget_V':1e-7,'execution_modes':2,'dut_independent_math_pass':all(x['pass'] for x in mathchecks),'original_relational_assertions_pass':True,'ordinary_forced_solutions_equal':True,'available_numeric_pair_pass':bool(pairs) and all(x['pass'] for x in pairs),'native_queries_complete':not missing,'qualified_finite_pair':not missing and bool(pairs) and all(x['pass'] for x in pairs),'missing_exact_native_queries':missing,'pairs':pairs,'mathchecks':mathchecks,'max_pair_error_V':max(x['pair_error_V'] for x in pairs),'max_reference_math_error_V':max(x['reference_math_error_upper_V'] for x in pairs),'max_dut_math_error_V':max(x['error_upper_V'] for x in mathchecks)}

def run():
 manifest=load(P/'PACKAGE-MANIFEST.json');assert all(sha(P/k)==h for k,h in manifest['files'].items())
 status=load(P/'STATUS.json');assert status['n09_retained_kernel_sha256']=='0538fee02ce67fb51c3da921f2607a27e64ccdcd1db257040aa118d14d065717'
 passed=0;pairs=0
 for f in sorted((P/'n09').glob('*/evidence.json')):
  a=load(f);assert a['kernel_sha256']==status['n09_retained_kernel_sha256']
  assert sha(f.parent/'dut.va')==a['reference_input_identity']['dut.va'] and sha(f.parent/'tb.scs')==a['reference_input_identity']['tb.scs']
  budget=F(str(a['budget_V']))
  for row in a['pairs']:
   t=F(Q(row['requested_time_token']));assert Q(row['native_time_token'])==Q(row['requested_time_token'])==Q(row['dut_time_token'])
   if a['group']=='n09-readout-v1':
    kind='linear_isolation' if a['case']=='linear_idt_unrelated_transition_no_events' else 'isolation';expected={n:(v,v) for n,v in oracle_a.expected(t,kind).items()}
   else:expected=oracle_b.expected(a['case'],t,'closed_form')
   iv=expected[row['node']];v=number(row['dut_voltage']);r=number(row['native_voltage_token'])
   assert max(abs(v-iv[0]),abs(v-iv[1]))<=budget and max(abs(r-iv[0]),abs(r-iv[1]))<=budget and abs(v-r)<=budget;pairs+=1
  passed+=1
 assert passed==6 and pairs==169
 deadline=[]
 for f in sorted((P/'deadline').glob('*/evidence.json')):
  a=load(f);assert sha(f.parent/'dut.va')==a['contract']['source_sha256'] and sha(f.parent/'tb.scs')==a['contract']['deck_sha256']
  result=analyze_case(a);assert result['available_numeric_pair_pass'] and result['dut_independent_math_pass'] and not result['qualified_finite_pair'];assert all(x['time_token']=='0.5' for x in result['missing_exact_native_queries']);deadline.append(result['label'])
 assert len(deadline)==3 and load(P/'ORIGINAL-FULL-STATUS.json')['completed']==1
 for name in ['DEADLINE-V2-PILOT.json','DEADLINE-V3-PILOT.json']:
  pilot=load(P/name);assert pilot['missing_exact_native_queries']==['0.5'] and pilot['complete_finite_pair'] is False
  assert not any(row.get('exact_native_rows') for row in pilot['queries'] if row.get('time_token',row.get('requested_time_token'))=='0.5')
 assert load(P/'DEADLINE-V3-PILOT.json')['further_mode_parameter_trials_stopped'] is True
 assert load(P/'ORIGINAL-REFERENCE-VERDICT.json')['passed'] is True
 history=load(P/'HISTORICAL-FAILURES.json');assert len(history)>=11 and all(x['status']=='failed' for x in history)
 return {'artifact_replay_consistent':True,'scope':'Retained finite data only; not a simulator/full raw replay','n09_controls_passed':6,'n09_voltage_pairs':169,'deadline_available_modes_passed':6,'deadline_original_complete_modes':0,'original_full_completed':1,'historical_failures_preserved':len(history),'final_N09_pending':status['n09_final_current_status']=='pending'}
if __name__=='__main__':print(json.dumps(run(),indent=2))

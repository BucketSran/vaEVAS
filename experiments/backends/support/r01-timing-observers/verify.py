"""Portable replay of 17 retained finite gates. Standard library only."""
from pathlib import Path
from decimal import Decimal as Q
import hashlib,json,copy
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
BUDGET=Q('1e-9')
def gate(a,b):
 x,y=Q(str(a)),Q(str(b));return x.is_finite() and y.is_finite() and abs(x-y)<=BUDGET

def oracle(family,label,t):
 t=Q(t)
 if family=='array':
  # Integer quotient truncates toward zero; remainder keeps dividend sign.
  quotient=lambda a,b: (1 if a*b>=0 else -1)*(abs(a)//abs(b))
  assert quotient(5,3)==1 and 5-quotient(5,3)*3==2
  assert quotient(-5,3)==-1 and -5-quotient(-5,3)*3==-2
  assert quotient(5,-3)==-1
  if label=='instances':return {'y1':Q(0 if t==0 else 3),'y2':Q(0 if t==0 else 5)}
  assert label in ['positive_modulo','negative_modulo','negative_divisor','default_zero_write','default_zero_read','scalar_dynamic_rhs']
  return {'y':Q(0 if t==0 else 7)}
 if family=='frontend':
  if label=='predicate_loops':
   n=0;u=-1
   if abs(u)>.5:n+=1
   if min(u,0)<-.5:n+=10
   if max(u,0)<.5:n+=100
   v=0 if t==0 else n
  elif label=='ordered_predicate':
   n=-2
   for _ in range(3):
    n+=1
    if abs(n)<.5:n+=10
   v=-2 if t==0 else n
  elif label in ['parameter_math','typed_integer','typed_real']:v=0 if t==0 else 2
  elif label=='selection_arm':v=1
  else:raise AssertionError(label)
  return {'y':Q(v)}
 assert family in ['passive','passive_v2']
 if label=='integral_sample':v=t
 elif label=='transition_sample':v=max(Q(0),min(Q(1),(t-Q('.5'))/Q('.5')))
 else:assert label in ['simultaneous_state','later_state'];v=Q(0 if t<Q('.5') else 1)
 return {'y':v}

def check(a):
 family,label=a['family'],a['label'];assert a['budget_V']==1e-9
 times=['0','0.75','1'] if family in ['array','frontend'] else ['0','0.25','0.5','0.75','0.875','1']
 rows=a['queries'];assert len(rows)==len(times)
 assert [Q(x['time']) for x in rows]==list(map(Q,times))
 comparisons=0;max_pair=Q(0)
 for row,t in zip(rows,times):
  assert Q(row['native_time_token'])==Q(t)==Q(row['dut_time_token'])
  expected=oracle(family,label,t)
  assert {n:Q(str(v)) for n,v in row['independent_expected'].items()}==expected
  for node,e in expected.items():
   dut,ref=row['dut_voltages'][node],row['native_voltages'][node]
   assert gate(dut,e) and gate(ref,e) and gate(dut,ref)
   lo,hi=row['dut_voltage_bounds'][node];assert Q(str(lo)).is_finite() and Q(str(hi)).is_finite() and Q(str(lo))<=Q(str(dut))<=Q(str(hi))
   comparisons+=1;max_pair=max(max_pair,abs(Q(str(dut))-Q(ref)))
 if family in ['passive','passive_v2']:
  seen=Q(1) if label in ['later_state','simultaneous_state'] else Q('.5')
  sample=Q('.5') if label in ['simultaneous_state','integral_sample'] else Q('.75')
  due=Q('.75') if label in ['simultaneous_state','integral_sample'] else Q('.875')
  texts=['seen '+str(seen),'due 1','final '+str(seen)+' 1']
  assert [r['text'] for r in a['dut_display_records']]==texts==[r['text'] for r in a['spectre_display_records']]
  assert [Q(str(r['time'])) for r in a['dut_display_records']]==[sample,due,Q(1)]
  assert a['spectre_callback_time_directly_measured'] is False
  for row in rows:
   t=Q(row['time']);state=row['dut_states']
   assert gate(state['M:seen'],0 if t<sample else seen)
   assert gate(state['M:due'],100 if t<sample else due)
   assert state['M:count']==(0 if t<due else 1)
  final=a['dut_final_states'];assert gate(final['M:seen'],seen) and final['M:count']==1 and gate(final['M:due'],due)
 if label=='selection_arm':
  assert [row['dut_states']['X_dut:x'] for row in rows]==[0,1,1]
  assert a['spectre_hidden_x_measured'] is False
 assert a['stderr_empty'] and a['kernel_sha256']=='e13f60ee52e5fd558e08ddd468dff6d7c980bfce9daceb9c1e159682f240458a'
 assert a['effective_dut_controls']=={'absolute_V':1e-9,'relative':1e-6,'stop_s':1.0,'max_step_s':.125,'max_step_applied':True}
 assert a['reference_effective']['reltol']=='1.00000e-06' and a['reference_effective']['abstol(V)']=='1.00000e-09'
 return {'family':family,'label':label,'query_points':len(rows),'voltage_values':comparisons,'max_pair_error_V':str(max_pair),'pass':True}

def rejected(action):
 try:action()
 except (AssertionError,ValueError,ArithmeticError):return True
 raise AssertionError('negative control accepted')

def run():
 manifest=load(P/'PACKAGE-MANIFEST.json');assert all(sha(P/k)==v['normalized_sha256'] for k,v in manifest['files'].items())
 summary=load(P/'SUMMARY.json');assert summary['denominator']==17 and summary['original_scores_and_Q_changed'] is False
 outcomes=[];cases=[]
 for c in summary['cases']:
  folder=P/c['family']/c['label'];a=load(folder/'evidence.json')
  assert all(sha(folder/n)==h for n,h in a['input_sha256'].items())
  outcomes.append(check(a));cases.append(a)
 assert len(outcomes)==17 and sum(x['query_points'] for x in outcomes)==63 and sum(x['voltage_values'] for x in outcomes)==66
 adaptation=load(P/'final-source-adaptation.json');assert adaptation['kernel_matches_original_e13'] is True
 assert adaptation['kernel_sha256']==cases[0]['kernel_sha256'] and len(adaptation['cases'])==17
 by_case={(x['family'],x['label']):x for x in cases}
 for row in adaptation['cases']:
  original=by_case[(row['family'],row['label'])]
  assert row['unchanged'] and row['before_stdout_sha256']==row['after_stdout_sha256']==original['stdout_sha256']
  assert row['input_sha256']==original['input_sha256']
 history=load(P/'simultaneous-v1-failure.json');assert history['execution']['returncode']==2 and history['classification']=='deck_configuration_failure_not_semantics_result'
 assert any('SFE-23' in x['text'] for x in history['errors'])
 assert summary['original_timing_evidence']['completed']==0 and summary['original_timing_evidence']['code']=='kernel.unsupported_operator'
 provenance=load(P/'reference-provenance.json');assert len(provenance)==4 and all(x['tools_before_after_equal'] and x['raw_availability']=='local-only' for x in provenance.values())
 a=copy.deepcopy(cases[0]);node=next(iter(a['queries'][1]['dut_voltages']));a['queries'][1]['dut_voltages'][node]+=1e-7
 b=copy.deepcopy(cases[0]);b['queries'][1]['native_voltages'][node]='NaN'
 c=copy.deepcopy(cases[0]);c['queries'][1]['dut_time_token']='0.75000000000000001'
 d=copy.deepcopy(next(x for x in cases if x['family']=='passive'));d['dut_display_records'][1]['text']='due 2'
 calibration={'correct_values_accepted':True,'over_budget_dut_rejected':rejected(lambda:check(a)),'nonfinite_reference_rejected':rejected(lambda:check(b)),'nonexact_query_time_rejected':rejected(lambda:check(c)),'wrong_display_count_rejected':rejected(lambda:check(d))}
 return {'status':'pass','scope':'Portable retained finite replay only, no simulator/raw replay','cases_passed':17,'query_points':63,'voltage_values':66,'outcomes':outcomes,'calibration':calibration,'historical_v1_configuration_failure_preserved':True,'original_timing_completed':False,'Q_changed':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))

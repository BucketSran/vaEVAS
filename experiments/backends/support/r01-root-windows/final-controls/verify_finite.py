"""Replay retained finite comparisons only. Standard library; no EVAS or simulators."""
from pathlib import Path
from fractions import Fraction as F
import hashlib,json,copy
import oracle
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def check_case(folder,initial=False,data=None,response=None):
 a=data if data is not None else load(folder/'evidence.json')
 r=response if response is not None else load(folder/'dut-response.json')
 budget=a['budget_V'];rows=a['native_query_tokens'];times=a['query_times']
 assert len(rows)==len(times)==len(r['solutions'])
 observed=[F(x['time']) for x in rows];assert observed==list(map(F,times)) and len(set(observed))==len(times)
 if 'transient' in r:assert list(map(F,r['transient']['times']))==list(map(F,times))
 pairs=0;max_pair=F(0)
 for i,(t,row,solution) in enumerate(zip(times,rows,r['solutions'])):
  expected={'y':oracle.exact(a['independent_oracle']['waveform'][i])} if initial else oracle.expected(a['label'],F(t))
  for node,iv in expected.items():
   native=F(row['voltages'][node]);dut=F(solution['voltages'][r['nodes'].index(node)])
   assert oracle.gate(native,iv,budget) and oracle.gate(dut,iv,budget)
   difference=abs(native-dut);assert difference<=F(str(budget));pairs+=1;max_pair=max(max_pair,difference)
 if initial:
  displays=[x['text'] for x in a['spectre_display']]
  assert displays==a['independent_oracle']['display']==[x['text'] for x in r['transient']['display_records']]
  assert a['spectre_display_callback_times_directly_recorded'] is False
 else:
  assert a['original_native_analysis']['qualified'] and a['original_native_analysis']['effective_gate']
  assert not a['original_native_analysis']['native_math_failures']
  if a['label']=='display_final':
   assert a['spectre_callbacks']==[['0.5',1,'before'],['0.5',2,'after'],['1',7,'final']]
   assert [x['text'] for x in r['transient']['display_records']]==['BASE before 0.5 1','BASE after 0.5 2','BASE final 1 7']
 return {'label':a['label'],'query_points':len(rows),'voltage_pairs':pairs,'max_pair_error_V':float(max_pair),'pass':True}

def reject(action):
 try:action()
 except (AssertionError,ValueError,OverflowError):return True
 raise AssertionError('negative control unexpectedly passed')

def run():
 manifest=load(P/'MANIFEST.json');assert all(sha(P/k)==h for k,h in manifest.items())
 p=load(P/'provenance.json');assert sha(P/'oracle.py')==p['base_oracle_sha256']
 outcomes=[]
 for group,labels,initial in [('base',p['base_labels'],False),('initial',p['initial_labels'],True)]:
  for label in labels:
   f=P/group/label;a=load(f/'evidence.json')
   source=load(f/'dut-source.json')['source'].encode('utf8') if (f/'dut-source.json').exists() else (f/'dut.va').read_bytes()
   assert hashlib.sha256(source).hexdigest()==a['source_sha256'] and sha(f/'tb.scs')==a['deck_sha256']
   if initial:assert sha(f/'dut-response.json')==a['dut_response_sha256']
   else:
    assert sha(f/'REQUEST.json')==a['request_sha256'] and sha(f/'tb.evas.scs')==a['evas_deck_sha256']
    assert sha(f/'dut-response.json')==load(f/'dut-RECEIPT.json')['response_sha256']
   outcomes.append(check_case(f,initial))
 f=P/'base/held_exponential';a=load(f/'evidence.json');r=load(f/'dut-response.json')
 altered=copy.deepcopy(a);altered['native_query_tokens'][1]['voltages']['y']='1'
 altered_time=copy.deepcopy(a);altered_time['native_query_tokens'][1]['time']='0.25000000000000001'
 altered_dut=copy.deepcopy(r);altered_dut['solutions'][1]['voltages'][r['nodes'].index('y')]=1
 initial=P/'initial/ordered_records';order=load(initial/'evidence.json');order['spectre_display'].reverse()
 calibration={'oracle':oracle.calibration(),'wrong_reference_rejected':reject(lambda:check_case(f,data=altered)),'nonexact_time_rejected':reject(lambda:check_case(f,data=altered_time)),'wrong_dut_rejected':reject(lambda:check_case(f,response=altered_dut)),'wrong_display_order_rejected':reject(lambda:check_case(initial,True,data=order))}
 return {'status':'pass','scope':'retained finite points only; no simulation or complete raw replay','manifest_files':len(manifest),'base_cases':7,'initial_cases':3,'initial_exact_native_points':18,'outcomes':outcomes,'calibration':calibration,'historical_scores_changed':False,'issue_131_changed':False}
if __name__=='__main__':print(json.dumps(run(),indent=2))

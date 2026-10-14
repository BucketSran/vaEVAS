"""Recompute retained finite gates only, stdlib; never launches a simulator."""
from pathlib import Path
import json,hashlib,math
from decimal import Decimal as D,localcontext
from fractions import Fraction as F
import finite_verify
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def numeric(v):
 d=D(str(v));assert d.is_finite(),v;return d
def gate(v,e,b='1e-8'):
 try:return abs(numeric(v)-numeric(e))<=D(b)
 except (AssertionError,ValueError):return False
def lookup(rows,t):return next((r for r in rows if D(r['time'])==D(t)),None)
def atan_small(x):
 s=D(0);power=x
 for k in range(160):s+=power/D(2*k+1);power*=-x*x
 return s
def flow(label,t):
 with localcontext() as c:
  c.prec=80;x=D(t.numerator)/D(t.denominator)
  if label=='autonomous':return +(x.exp()-1)
  x*=3
  return +((4*atan_small(D(1)/5)-atan_small(D(1)/239)+atan_small((x-1)/(x+1)) if x>D('.5') else atan_small(x))/3)
def interp(br,t,n):
 if len(br)==1:return float(br[0]['values'][n])
 a,b=br;ta=float(a['time']);tb=float(b['time']);assert ta<=t<=tb
 va=float(a['values'][n]);vb=float(b['values'][n]);assert all(math.isfinite(x) for x in [ta,tb,va,vb]);return va+(vb-va)*(t-ta)/(tb-ta)
def run():
 m=load(P/'PACKAGE-MANIFEST.json');assert all(sha(P/n)==h for n,h in m['files'].items())
 finite=finite_verify.run();status=load(P/'STATUS.json');full=load(P/'ORIGINAL-FULL-STATUS.json');ref=load(P/'ORIGINAL-REFERENCE-IDENTITY.json')
 assert full['kernel_sha256']==status['fixed_kernel_sha256']==load(P/'SOURCE-IDENTITY.json')['kernel_sha256']
 assert full['elapsed_seconds']<full['timeout_seconds']==120 and full['waveform_rows']==9001 and full['source_before_after_equal'] and full['source_before_sha256']==full['source_after_sha256']
 oc=full['original_checker'];assert oc['passed'] and oc['protected_circuit']['passed'] and oc['protected_circuit']['checks']==2219 and not oc['failures'] and oc['expected_records']==oc['actual_records'] and sum(oc['actual_records'].values())==55
 assert ref['native_VALUE_body_identity']['exact_VALUE_body_bytes_equal'] and ref['native_VALUE_body_identity']['fresh_VALUE_body_sha256']==ref['native_VALUE_body_identity']['historical_VALUE_body_sha256']
 assert ref['native_rows']==12024 and ref['tool_before_after_equal'] and full['checker_sha256']==ref['checker_sha256']
 for n,h in ref['source_identity'].items():assert sha(P/'original'/n)==h
 brackets=load(P/'original/FINITE-BRACKETS.json');assert brackets['count']==len(brackets['rows'])==291
 maxima={n:0.0 for n in brackets['nodes']}
 for row in brackets['rows']:
  t=row['time']
  for n in brackets['nodes']:
   diff=abs(interp(row['dut_bracket'],t,n)-interp(row['reference_bracket'],t,n));assert math.isfinite(diff);maxima[n]=max(maxima[n],diff)
 receipt=full['paired_observation_receipt']
 for n,error in maxima.items():
  assert error<=receipt['tolerances'][n]
  assert abs(error-receipt['max_abs_difference'][n])<=max(1e-13,receipt['max_abs_difference'][n]*1e-7),(n,error,receipt['max_abs_difference'][n])
 assert maxima['sample_time']*full['sample_time_encoding_seconds_per_V']<=2.5e-10
 displays=load(P/'original/DISPLAY.json');assert len(displays['dut_records'])==55 and len(displays['reference_records'])==55 and displays['reference_time_fields']==62
 passive=load(P/'passive/evidence.json');assert passive['summary']['complete_original_native_gate_pass']==0 and passive['identity']['tool_before_after_equal']
 for case in passive['cases']:
  label=case['label'];base=P/'passive'/label;contract=load(base/'CONTRACT.json');dut=load(base/'DUT.json');assert sha(base/'dut.va')==case['source_sha256'] and sha(base/'tb.scs')==case['deck_sha256']
  assert D(case['effective_psf_header']['reltol'])==D('1e-10') and D(case['effective_psf_header']['abstol(V)'])==D('1e-12') and D(case['effective_psf_header']['maxstep'])==D('1e-5')
  assert case['effective_psf_header']['method']=='"traponly"' and 'saveahdlvars = all' in case['actual_global_options'] and 'precision = %.17g' in case['actual_global_options']
  assert dut['kernel_sha256']==passive['identity']['fixed_kernel_sha256'];assert hashlib.sha256(json.dumps(dut['program'],sort_keys=True,separators=(',',':')).encode()).hexdigest()==case['program_canonical_sha256']
  missing=[];phase=[];zidx=dut['result']['nodes'].index('z');tr=dut['result']['transient'];ci=tr['state_names'].index('M:count');si=tr['state_names'].index('M:seen');due=F(contract['exact_due_fraction'])
  for i,t in enumerate(contract['query_tokens']):
   expected=flow(label,F(contract['query_times_binary64'][i]));v=dut['result']['solutions'][i]['voltages'][zidx];assert gate(v,expected) and tr['states'][i][ci]==contract['original_count_oracle'][i];assert gate(tr['states'][i][si],flow(label,due) if contract['original_count_oracle'][i] else 0)
   nr=lookup(case['native_rows'],t)
   if nr is None:missing.append(t);continue
   assert gate(nr['values']['z'],expected) and gate(nr['values']['z'],v)
   count=numeric(nr['values']['M:count']);assert gate(nr['values']['M:seen'],flow(label,due) if count else 0)
   if count!=contract['original_count_oracle'][i]:phase.append(t)
  assert missing==case['missing_tokens'] and len(missing)==3 and phase==case['boundary_phase_divergences']==[contract['boundary_neighbor_tokens'][0]]
  assert case['display_texts']==['sample 1'] and numeric(case['native_rows'][-1]['values']['M:count'])==1
 initial=[]
 for group,want in [('initial-v1',False),('initial-v2',True)]:
  ev=load(P/group/'evidence.json');contract=load(P/group/'initial_horizon/CONTRACT.json');dut=load(P/group/'DUT.json');assert sha(P/group/'initial_horizon/dut.va')==contract['source_sha256'] and sha(P/group/'initial_horizon/tb.scs')==contract['deck_sha256'];assert sha(P/group/'REQUEST.json')==contract['request_sha256']
  assert D(ev['effective_psf_header']['reltol'])==D('1e-10' if group=='initial-v1' else '1e-11') and D(ev['effective_psf_header']['abstol(V)'])==D('1e-12' if group=='initial-v1' else '1e-13') and D(ev['effective_psf_header']['maxstep'])==D('1e-5' if group=='initial-v1' else '1e-6')
  assert ev['effective_psf_header']['method']=='"traponly"' and 'precision = %.17g' in ev['actual_global_options'] and 'saveahdlvars = all' in ev['actual_global_options']
  assert ev['binding']['tool_before_after_equal'] and ev['binding']['kernel_sha256']==status['fixed_kernel_sha256'];assert ev['display_texts']==['initial=1'];complete=True;missing=[];volt=True
  for i,t in enumerate(contract['query_tokens']):
   x=F(t);expected=F(1)/(1-x) if x<F('.5') else F(1)/x
   with localcontext() as c:c.prec=80;e=D(expected.numerator)/D(expected.denominator)
   v=dut['solutions'][i]['voltages'][dut['nodes'].index('z')];assert gate(v,e)
   nr=lookup(ev['native_rows'],t)
   if nr is None:missing.append(t);complete=False;continue
   ok=gate(nr['values']['z'],e) and gate(nr['values']['z'],v);volt&=ok;complete&=ok and numeric(nr['values']['D:q'])==(1 if x<F('.5') else -1)
  assert complete==want==ev['summary']['complete_original_native_gate'];assert volt==ev['summary']['available_voltage_gate'];assert missing==ev['missing_tokens']
  assert any('SPECTRE-470' in w for w in ev['warnings']);initial.append({'variant':group,'complete_gate':complete,'missing_tokens':missing})
 summary=load(P/'n09-final/SUMMARY.json');ident=load(P/'n09-final/IDENTITY.json');assert status['n09_final_current_status']=='passed' and ident['source_kernel_unchanged_after'] and summary['kernel_sha256']==ident['kernel_sha256']==status['fixed_kernel_sha256']
 latest_pairs=0;latest_cases=0;latest_times=0
 for f in sorted((P/'n09-final').glob('*.json')):
  if f.name in ['SUMMARY.json','IDENTITY.json']:continue
  a=load(f);label=a['label'];assert a['kernel_sha256']==status['fixed_kernel_sha256'];assert sha(P/'n09'/label/'dut.va')==a['reference_input_identity']['dut.va'] and sha(P/'n09'/label/'tb.scs')==a['reference_input_identity']['tb.scs']
  assert sha(P/'n09-final'/label/'program.json')==a['compiled_program_sha256'];receipt=load(P/'n09-final'/label/'RECEIPT.json');assert receipt['kernel_sha256']==a['kernel_sha256'] and receipt['source_sha256']==a['reference_input_identity']['dut.va'] and receipt['response_sha256']==a['response_sha256']
  budget=F(str(a['budget_V']))
  for row in a['pairs']:
   assert D(row['native_time_token'])==D(row['requested_time_token'])==D(row['dut_time_token']);t=F(D(row['requested_time_token']))
   if a['group']=='n09-readout-v1':
    kind='linear_isolation' if a['case']=='linear_idt_unrelated_transition_no_events' else 'isolation';expected={n:(v,v) for n,v in finite_verify.oracle_a.expected(t,kind).items()}
   else:expected=finite_verify.oracle_b.expected(a['case'],t,'closed_form')
   iv=expected[row['node']];v=finite_verify.number(row['dut_voltage']);r=finite_verify.number(row['native_voltage_token']);assert max(abs(v-iv[0]),abs(v-iv[1]))<=budget and max(abs(r-iv[0]),abs(r-iv[1]))<=budget and abs(v-r)<=budget;latest_pairs+=1
  latest_cases+=1;latest_times+=a['query_points']
 assert latest_cases==6 and latest_pairs==169 and latest_times==44 and all(summary['calibration'].values())
 assert not gate('NaN',0) and not gate('Infinity',0) and not gate('2e-8',0) and lookup([{'time':'2.000000000000001'}],'2') is None
 return {'retained_hashes_and_finite_recompute':True,'scope':'No simulator/full-raw replay; original fullchecker verdict is retained receipt identity, not recomputed from bulk raw.','full_original_completed':1,'full_original_protected_checks_receipt':2219,'full_finite_interpolated_times':291,'full_finite_maxima_V':maxima,'sample_time_maximum_error_s':maxima['sample_time']*1e-6,'records':55,'reference_time_fields':62,'historical_failures_preserved':len(load(P/'HISTORICAL-FAILURES.json')),'n09_historical0538':finite,'n09_latest_c5':{'controls':latest_cases,'query_points':latest_times,'voltage_pairs':latest_pairs,'kernel_sha256':summary['kernel_sha256']},'passive_complete':0,'passive_controls':2,'initial':initial}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))

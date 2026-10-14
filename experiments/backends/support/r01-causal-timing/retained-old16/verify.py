"""Check compact casewise receipts, not original raw/simulator replay."""
from pathlib import Path
import json,hashlib,math
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
def run():
 m=load(P/'MANIFEST.json');assert all(hashlib.sha256((P/k).read_bytes()).hexdigest()==v for k,v in m.items())
 rows=load(P/'CASEWISE.json');status=load(P/'STATUS.json');assert len(rows)==16 and len({r['case_id'] for r in rows})==16
 first_success=0;qualified=0;pairpass=0;inputfail=0;unchanged_gaps=0
 for r in rows:
  assert r['kernel_sha256']==status['kernel_sha256'];a=r['attempts'][0]['result'];first_success+=a['status']=='completed';assert len(r['attempts'])==(2 if r['case_id']=='r01-extend-hold/c2' else 1)
  if r['case_id']=='r01-extend-hold/c2':
   b=r['attempts'][1]['result'];assert a['status']=='failed' and a['diagnostic']['code']=='kernel.kernel_timeout' and a['timeout_seconds']==b['timeout_seconds']==120 and a['input_sha256']==b['input_sha256'] and a['command']==b['command'];assert b['status']=='completed' and b['elapsed_seconds']<120 and r['first_failure_retained'] and r['qualification_basis']=='separate_same_kernel_retest'
  if r['qualified']:
   g=r['qualified_regrade'];assert g['original_checker']['passed'] and not g['original_checker']['failures'];po=g['paired_observation'];assert po['output_passed'];assert po['observation_count']>0
   for n in po['output_nodes']:assert math.isfinite(po['max_abs_difference'][n]) and po['max_abs_difference'][n]<=po['tolerances'][n]
   ip=all(math.isfinite(po['max_abs_difference'][n]) and po['max_abs_difference'][n]<=po['tolerances'][n] for n in po['input_nodes']);assert ip==po['input_passed'] and po['passed']==(ip and po['output_passed']);pairpass+=po['passed'];inputfail+=not ip;qualified+=1
  else:
   assert a['status']=='failed' and a['diagnostic']['code']=='kernel.unsupported_transient';assert 'jointly affine' in a['diagnostic']['message'] or 'joint-affine' in a['diagnostic']['message'];unchanged_gaps+=1
 assert first_success==11 and qualified==12 and unchanged_gaps==4 and pairpass==6 and inputfail==6
 assert status['qualified_original_cases']==status['qualified_original_checker_pass']==12 and status['qualified_denominator']==16 and not status['formal_13_of_70_score_claim']
 return {'casewise_identity_and_receipt_consistency':True,'scope':'Retained checker verdicts and finite maxima only; no raw checker/simulator rerun.','first_attempt_completed':11,'first_attempt_denominator':16,'first_c2_timeout_preserved':True,'qualified_checker_pass':12,'qualified_denominator':16,'joint_affine_gaps':4,'finite_output_pass':12,'finite_input_and_output_pass':6,'finite_input_failures_retained':6,'CI_Python':'pending'}
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))

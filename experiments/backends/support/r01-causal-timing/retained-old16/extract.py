"""Compact casewise receipts, no raw bulk or simulations. Supply local run root."""
from pathlib import Path
import json,hashlib,argparse,re
P=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def scrub(v):
 if isinstance(v,dict):return {k:scrub(x) for k,x in v.items()}
 if isinstance(v,list):return [scrub(x) for x in v]
 if isinstance(v,str):return re.sub(r'/(?:Users|home|edamgr|opt)/[^\s"\'\],)]+',lambda m:'local-only/'+Path(m.group()).name,v)
 return v
def dump(n,v):(P/n).write_text(json.dumps(scrub(v),ensure_ascii=False,separators=(',',':'))+'\n')
def key(x):return x['task_id']+'/'+x['condition']
def main():
 ap=argparse.ArgumentParser();ap.add_argument('run_root',type=Path);R=ap.parse_args().run_root;F=R/'final-originals';first=load(F/'c5-v1/r01-results.json');retest=load(F/'c2-v2/r01-results.json')[0];grades={key(x):x for x in load(F/'c5-v1/regrade.json')};rg=load(F/'c2-v2/regrade.json')[0];assert key(retest)==key(rg)=='r01-extend-hold/c2';assert len(first)==16 and len(grades)==11
 identity=load(R/'initial-horizon-implementation/IDENTITY.json');kernel=R/'initial-horizon-implementation/initial-release-evas-kernel';assert sha(kernel)==identity['kernel_sha256'];casewise=[]
 for row in first:
  k=key(row);f=F/'c5-v1/r01'/row['task_id']/row['condition'];attempts=[{'stage':'c5-v1','receipt_sha256':sha(f/'result.json'),'response_sha256':sha(f/'stdout.json'),'stderr_sha256':sha(f/'stderr.json'),'result':row}]
  assert row['command'][row['command'].index('--kernel')+1].endswith('initial-release-evas-kernel')
  grade=grades.get(k);qualification='first_attempt' if grade else 'unqualified_common_gap'
  if k==key(retest):
   assert row['diagnostic']['code']=='kernel.kernel_timeout' and row['input_sha256']==retest['input_sha256'] and row['timeout_seconds']==retest['timeout_seconds']==120 and row['command']==retest['command']
   f=F/'c2-v2/r01'/row['task_id']/row['condition'];attempts.append({'stage':'c2-v2','receipt_sha256':sha(f/'result.json'),'response_sha256':sha(f/'stdout.json'),'stderr_sha256':sha(f/'stderr.json'),'result':retest});grade=rg;qualification='separate_same_kernel_retest'
  if grade:
   grade=dict(grade);po=dict(grade['paired_observation']);po['observation_count']=len(po.pop('observation_times'));grade['paired_observation']=po
   assert grade['original_checker']['passed'] and po['output_passed']
  casewise.append({'case_id':k,'kernel_sha256':identity['kernel_sha256'],'kernel_identity_limit':'Both commands point to retained fixedc5 artifact; extraction checks implementation identity. Per-attempt before/after source snapshots are not present here and not invented.','attempts':attempts,'qualification_basis':qualification,'qualified':grade is not None,'qualified_regrade':grade,'first_failure_retained':row['status']=='failed'})
 dump('CASEWISE.json',casewise)
 origins={n:sha(F/n) for n in ['c5-v1/r01-results.json','c5-v1/regrade.json','c2-v2/r01-results.json','c2-v2/regrade.json']};dump('ORIGINS.json',{'local_receipt_sha256':origins,'implementation_identity_sha256':sha(R/'initial-horizon-implementation/IDENTITY.json'),'source_bytes_availability':'bulk raw local-only; casewise original receipt SHA differs from normalized retained JSON SHA'})
 dump('STATUS.json',{'kernel_sha256':identity['kernel_sha256'],'first_original_denominator':16,'first_completed':11,'first_checker_pass':11,'first_failures':5,'first_common_joint_affine_gap':4,'first_c2_kernel_timeout_retained':True,'c2_retest_same_input_command_timeout':True,'c2_retest_elapsed_seconds':retest['elapsed_seconds'],'qualified_original_cases':12,'qualified_original_checker_pass':12,'finite_output_pass':12,'finite_input_and_output_pass':6,'finite_input_failures_retained':6,'qualified_denominator':16,'unqualified_old_common_gaps':4,'combined_with_new_timing_qualified':13,'combined_reviewed_denominator':17,'new_completed_original_task':1,'other_original70_cases_not_currently_accepted':53,'formal_13_of_70_score_claim':False,'Python_CI_status':'pending; no all-green claim','resource_context_limit':'Root reports first c2 executed under concurrent Rust/Python load. Receipts show timeout then separate success; no claim that all Python mesh/resource failures are resolved.'})
 print('casewise',len(casewise),'qualified',sum(x['qualified'] for x in casewise))
if __name__=='__main__':main()

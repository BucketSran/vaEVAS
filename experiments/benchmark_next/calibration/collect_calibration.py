"""Keep every actual attempt, verify reports, and summarize frozen calibration."""
import argparse,hashlib,json,re,tarfile
from pathlib import Path

def sha(data):return hashlib.sha256(data).hexdigest()

def read_prepared(prepared,final):
 plan=json.loads((prepared/'preparation.json').read_text())
 results_path=prepared/'results.json'
 results=json.loads(results_path.read_text()) if results_path.exists() else []
 conditions=[]
 for item in results:
  archive=prepared/'remote'/item['job_id']/'archive/job.tar.gz'
  with tarfile.open(archive) as stream:data=stream.extractfile('run/work/verifier/report.json').read()
  expected=item['result']['artifacts']['work/verifier/report.json']['sha256']
  if sha(data)!=expected:raise ValueError('report SHA mismatch')
  report=json.loads(data);result=item['result']
  if result['candidate_sha256']!=plan['candidate']['candidate_sha256'] or result['criteria_sha256']!=plan['criteria_sha256']:raise ValueError('frozen identity mismatch')
  version=re.findall(r'sub-version\s+(\S+)',report.get('spectre_version',''))
  cases=[]
  for case in report['cases']:
   metrics={}
   for check in case.get('checks',[]):
    key=re.sub(r'^\d+:','',check['name']);value=metrics.setdefault(key,{'maximum_actual':check['actual'],'limit':check['limit'],'checks':0,'passed':True})
    value['maximum_actual']=max(value['maximum_actual'],check['actual']);value['checks']+=1;value['passed'] &=check['passed']
   cases.append({k:case[k] for k in ('name','status','passed','netlist_sha256','support_sha256','waveform_sha256','waveform_rows','returncode','reason') if k in case})
   cases[-1]['measurements']=metrics
  conditions.append(dict(condition_id=item['condition_id'],job_id=item['job_id'],execution=result['execution'],score=result.get('score'),report_status=report['status'],report_sha256=expected,archive_sha256=sha(archive.read_bytes()),backend_version=version[-1] if version else 'unavailable',candidate_files=report.get('candidate_files',{}),checker_files=report.get('checker_files',{}),cases=cases))
 return dict(task_id=plan['task_id'],variant=prepared.name.split('--',1)[-1],attempt_stage=prepared.parent.name,final=final,candidate_sha256=plan['candidate']['candidate_sha256'],criteria_sha256=plan['criteria_sha256'],source_identity=plan['source_identity'],expected_conditions=len(plan['cases']),conditions=conditions)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--final',type=Path,required=True);parser.add_argument('--history',type=Path,action='append',default=[]);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 requests=json.loads((args.final/'requests.json').read_text());final=[]
 for request in requests:
  record=read_prepared(Path(request['prepared']),True);record['expected']=request['expected'];record['reference_script_sha256']=request.get('reference_script_sha256')
  graded=len(record['conditions'])==record['expected_conditions'] and all(c['execution']=='ok' and c['cases'] and all(x['status']=='graded' for x in c['cases']) for c in record['conditions'])
  record['all_conditions_graded']=graded
  record['calibration_satisfied']=graded and (all(c['score']==1 for c in record['conditions']) if request['expected']=='pass' else any(c['score']==0 for c in record['conditions']))
  final.append(record)
 history=[]
 for root in args.history:
  for prepared in sorted(root.glob('*/preparation.json')):
   record=read_prepared(prepared.parent,False)
   if record['conditions']:
    if record['variant']=='detached_feedback' and record['task_id']!='v3-calibration-fractional-pll':record['disposition']='redundant identical-reference diagnostic, not an effective semantic negative'
    history.append(record)
 report=dict(spec_issue=150,task_count=3,registered_variants=len(final),final_conditions=sum(r['expected_conditions'] for r in final),final_satisfied=all(r['calibration_satisfied'] for r in final),model_trials=0,variants=final,attempt_history=history,history_actual_conditions=sum(len(r['conditions']) for r in history),limits='Actual author calibration only; no model solving, noise performance, arbitrary algorithm proof, or open-source backend equivalence')
 root=Path(__file__).resolve().parents[3]
 material={}
 for task_id in sorted({r['task_id'] for r in final}):
  task=root/'benchmark/tasks'/task_id
  for path in sorted(task.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts:material[str(path.relative_to(root))]=sha(path.read_bytes())
 report['material_assets']=material
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('registered_variants','final_conditions','final_satisfied','history_actual_conditions')}))
if __name__=='__main__':main()

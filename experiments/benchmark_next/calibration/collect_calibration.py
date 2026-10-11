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
 parser=argparse.ArgumentParser();parser.add_argument('--final',type=Path,required=True);parser.add_argument('--reuse-final',type=Path,action='append',default=[]);parser.add_argument('--reanalysis',type=Path);parser.add_argument('--history',type=Path,action='append',default=[]);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 requests=json.loads((args.final/'requests.json').read_text());final=[]
 changed={Path(request['task']).name for request in requests}
 for reused in args.reuse_final:
  for request in json.loads((reused/'requests.json').read_text()):
   if Path(request['task']).name not in changed:requests.append({**request,'reused_from':reused.name})
 for request in requests:
  record=read_prepared(Path(request['prepared']),True);record['expected']=request['expected'];record['reference_script_sha256']=request.get('reference_script_sha256')
  if 'reused_from' in request:
   if not args.reanalysis:raise ValueError('Reused execution requires explicit current-checker reanalysis')
   analyses=json.loads(args.reanalysis.read_text())
   for name,expected in analyses['unchanged_material_assets'].items():
    if sha((Path(__file__).resolve().parents[3]/name).read_bytes())!=expected:raise ValueError('Reused circuit material changed')
   record['reuse_reason']=analyses['reason'];record['reused_from']=request['reused_from']
   for condition in record['conditions']:
    analysis=next(a for a in analyses['conditions'] if a['job_id']==condition['job_id'])
    identity={k:v for k,v in analysis.items() if k!='analysis_identity_sha256'}
    if sha(json.dumps(identity,sort_keys=True,separators=(',',':')).encode())!=analysis['analysis_identity_sha256']:raise ValueError('Reanalysis identity mismatch')
    task=Path(__file__).resolve().parents[3]/request['task']
    for name,expected in analysis['analysis_sources'].items():
     path=task/name if name=='instruction.md' else task/'tests'/name
     if sha(path.read_bytes())!=expected:raise ValueError('Current analysis source changed')
    if analysis['execution_candidate_sha256']!=record['candidate_sha256'] or analysis['execution_criteria_sha256']!=record['criteria_sha256'] or analysis['execution_report_sha256']!=condition['report_sha256']:raise ValueError('Reanalysis execution identity mismatch')
    if analysis['score']!=condition['score']:raise ValueError('Reanalysis result differs')
    condition['reanalysis_identity_sha256']=analysis['analysis_identity_sha256'];condition['analysis_sources']=analysis['analysis_sources'];condition['analysis_score']=analysis['score']
  graded=len(record['conditions'])==record['expected_conditions'] and all(c['execution']=='ok' and c['cases'] and all(x['status']=='graded' for x in c['cases']) for c in record['conditions'])
  record['all_conditions_graded']=graded
  record['calibration_satisfied']=graded and (all(c['score']==1 for c in record['conditions']) if request['expected']=='pass' else any(c['score']==0 for c in record['conditions']))
  final.append(record)
 history=[]
 for root in args.history:
  for prepared in sorted(root.glob('*/preparation.json')):
   record=read_prepared(prepared.parent,False)
   if any(record['task_id']==r['task_id'] and record['variant']==r['variant'] and record['candidate_sha256']==r['candidate_sha256'] and record['criteria_sha256']==r['criteria_sha256'] for r in final):continue
   if record['conditions']:
    if record['variant']=='detached_feedback' and record['task_id']!='v3-calibration-fractional-pll':record['disposition']='redundant identical-reference diagnostic, not an effective semantic negative'
    history.append(record)
 report=dict(spec_issue=150,task_count=3,registered_variants=len(final),final_conditions=sum(r['expected_conditions'] for r in final),final_satisfied=all(r['calibration_satisfied'] for r in final),model_trials=0,variants=final,attempt_history=history,history_actual_conditions=sum(len(r['conditions']) for r in history),limits='Actual author calibration only; no model solving, noise performance, arbitrary algorithm proof, or open-source backend equivalence')
 report['new_final_simulations']=sum(len(r['conditions']) for r in final if 'reused_from' not in r)
 report['collector_sha256']=sha(Path(__file__).read_bytes())
 report['reused_simulations_reanalyzed']=sum(len(r['conditions']) for r in final if 'reused_from' in r)
 if args.reanalysis:report['reanalysis_report_sha256']=sha(args.reanalysis.read_bytes())
 root=Path(__file__).resolve().parents[3]
 material={}
 for task_id in sorted({r['task_id'] for r in final}):
  task=root/'benchmark/tasks'/task_id
  for path in sorted(task.rglob('*')):
   if path.is_file() and '__pycache__' not in path.parts:material[str(path.relative_to(root))]=sha(path.read_bytes())
 report['material_assets']=material
 args.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ('registered_variants','final_conditions','final_satisfied','history_actual_conditions')}))
if __name__=='__main__':main()

"""Curate actual author runs with material identities, excluding private config."""
import argparse,hashlib,json,pathlib,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def report_for(out,record):
 job=out/'remote'/record['job_id']/'archive/job.tar.gz'
 with tarfile.open(job) as t:
  reports=[m for m in t if m.name.endswith('work/verifier/report.json')]
  if not reports:return {},sha(job)
  return json.load(t.extractfile(reports[0])),sha(job)

def main():
 p=argparse.ArgumentParser();p.add_argument('--runs',type=pathlib.Path,required=True);a=p.parse_args()
 manifest=json.loads((HERE/'manifest.json').read_text());items=[];attempts=[]
 for item in manifest['calibration']:
  revision='final-r7'
  out=a.runs/revision/(pathlib.Path(item['task']).name+'-'+item['variant'])
  frozen=out/'frozen/files/dut.va'
  assert sha(frozen)==item['candidate_file_sha256'],str(frozen)
  preparation=json.loads((out/'preparation.json').read_text())
  for name,value in preparation['source_identity'].items():
   if name=='test.sh':continue  # Harness freezes its canonical unchanged CLI wrapper.
   if name=='instruction.md':current=ROOT/item['task']/name
   else:current=ROOT/item['task']/'tests'/name
   if name.startswith('v2_') and current.suffix=='.py':current=ROOT/'benchmark/checkers'/name
   if current.exists():assert sha(current)==value,str(current)
  conditions=[]
  for r in json.loads((out/'results.json').read_text()):
   report,archive_sha=report_for(out,r); result=r['result'];case=report.get('cases',[{}])[0]
   assert result['execution']=='ok',r['job_id']
   if item['expected_pass']:assert result['score']==1,r['job_id']
   conditions.append(dict(condition=r['condition_id'],job_id=r['job_id'],execution=result['execution'],score=result['score'],archive_sha256=archive_sha,criteria_sha256=result['criteria_sha256'],candidate_sha256=result['candidate_sha256'],task_package_sha256=result['task_package_sha256'],backend_version=report.get('spectre_version'),candidate_file_sha256=report.get('candidate_files',{}).get('dut.va'),checker_sha256=report.get('checker_sha256'),waveform_sha256=case.get('waveform_sha256'),waveform_rows=case.get('waveform_rows'),metrics=case.get('metrics'),observation_current_peaks=case.get('observation_current_peaks'),stage_end_times=[s[0] for s in case.get('stages',[])],failures=case.get('failures',[])[:4]))
  if not item['expected_pass']:assert any(r['score']==0 for r in conditions)
  items.append(dict(task=item['task'],variant=item['variant'],expected_pass=item['expected_pass'],semantic_behavior=item['semantic_behavior'],candidate_file_sha256=item['candidate_file_sha256'],conditions=conditions))
 for file in sorted(a.runs.rglob('results.json')):
  for r in json.loads(file.read_text()):
   result=r['result'];attempts.append(dict(run=str(file.parent.relative_to(a.runs)),condition=r['condition_id'],job_id=r['job_id'],execution=result['execution'],score=result['score'],criteria_sha256=result.get('criteria_sha256'),candidate_sha256=result.get('candidate_sha256')))
 summary=dict(status='passed',model_trials=0,tasks=2,variants=len(items),conditions=sum(len(i['conditions']) for i in items),correct_implementations=sum(i['expected_pass'] for i in items),semantic_wrong_implementations=sum(not i['expected_pass'] for i in items),material_sha256=manifest['material_sha256'],source_calibration_sha256=sha(HERE/'source-calibration.json'),calibration=items,all_attempts=attempts)
 (HERE/'author-calibration.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(dict(status=summary['status'],variants=summary['variants'],conditions=summary['conditions'],attempts=len(attempts))))
if __name__=='__main__':main()

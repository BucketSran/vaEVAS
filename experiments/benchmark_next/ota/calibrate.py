"""Run frozen author variants sequentially; supply operator configuration privately."""
import sys,json,subprocess,tarfile,hashlib,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.runtime import prepare,execute
p=argparse.ArgumentParser();p.add_argument('--operator',type=Path,required=True);p.add_argument('--harness',type=Path,required=True);p.add_argument('--slug');p.add_argument('--variant');p.add_argument('--revision',required=True);args=p.parse_args()
plan=json.loads((ROOT/'experiments/benchmark_next/ota/calibration-plan.json').read_text())
for item in plan:
 if args.slug and item['task'].split('/')[-1]!='v3-ota-'+args.slug:continue
 if args.variant and item['variant']!=args.variant:continue
 task=ROOT/item['task'];candidate=ROOT/item['candidate']/'dut.va'
 out=ROOT/'runs'/('ota-calibration-'+args.revision)/task.name/item['variant']
 if item['variant']=='reference':
  work=out/'solve-candidate';work.mkdir(parents=True,exist_ok=True)
  subprocess.run(['docker','run','--rm','-v',str(task/'solution')+':/solution:ro','-v',str(work)+':/work','--entrypoint','sh','python:3.12.12-slim-bookworm','/solution/solve.sh'],check=True)
  if (work/'dut.va').read_bytes()!=candidate.read_bytes():raise ValueError('solve reference differs from frozen variant')
  candidate=work/'dut.va'
 prepared=out/'prepared'
 if not prepared.exists():prepare(task,candidate,prepared,args.harness,task_version='circuit-benchmark-next-development')
 results=execute(prepared,args.operator)
 for row in results:
  job=row['job_id'];archive=prepared/'remote'/job/'archive/job.tar.gz'
  with tarfile.open(archive) as tf:
   name=next(n for n in tf.getnames() if n.endswith('/verifier/report.json'));report=json.loads(tf.extractfile(name).read())
  (prepared/(row['condition_id']+'-verifier.json')).write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'task':task.name,'variant':item['variant'],'expected_pass':item['expected_pass'],'actual':[(r['condition_id'],r['result'].get('execution'),r['result'].get('score')) for r in results]}),flush=True)

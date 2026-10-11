"""Prepare author variants through existing runtime; does not submit jobs."""
import argparse,json,sys,subprocess,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.runtime import prepare
p=argparse.ArgumentParser();p.add_argument('--operator',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--variants',choices=['reference','others'],required=True);p.add_argument('--tasks',nargs='+');a=p.parse_args()
config=json.loads(a.operator.read_text());manifest=json.loads((Path(__file__).parent/'manifest.json').read_text());plan=[]
for row in manifest['calibrations']:
 if (row['variant']=='reference')!=(a.variants=='reference'):continue
 if a.tasks and Path(row['task']).name not in a.tasks:continue
 task=ROOT/row['task'];candidate=ROOT/row['candidate']/'dut.va'
 output=a.output/row['task'].split('/')[-1]/row['variant']
 output.parent.mkdir(parents=True,exist_ok=True)
 if row['variant']=='reference':
  # Run original solve.sh bytes with path-mapped cp, no rewrite of the script.
  oracle=output.parent/'oracle';(oracle/'bin').mkdir(parents=True,exist_ok=True)
  wrapper=oracle/'bin/cp';wrapper.write_text('#!/bin/sh\nset -eu\n[ "$1" = /solution/dut.va ]\n[ "$2" = /work/dut.va ]\n/bin/cp "$AUTHOR_SOURCE" "$AUTHOR_TARGET"\n');wrapper.chmod(0o755)
  candidate=oracle/'dut.va'
  env={**os.environ,'PATH':str((oracle/'bin').resolve())+':'+os.environ['PATH'],'AUTHOR_SOURCE':str(task/'solution/dut.va'),'AUTHOR_TARGET':str(candidate.resolve())}
  subprocess.run(['/bin/sh',str(task/'solution/solve.sh')],env=env,check=True)
 prepare(task,candidate,output,Path(config['harness_checkout']),case_names=row.get('case_names'),task_version='circuit-benchmark-next-development')
 plan.append(str(output.resolve()))
a.output.mkdir(parents=True,exist_ok=True);(a.output/(a.variants+'-plan.json')).write_text(json.dumps(plan,indent=2)+'\n')
print(json.dumps({'variants':len(plan),'plan':str(a.output/(a.variants+'-plan.json'))}))

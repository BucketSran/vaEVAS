"""Prepare fixed author variants over the existing runtime; does not submit jobs."""
import argparse,json,sys,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.benchmark_first_batch.runtime import prepare

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--harness-checkout',type=Path,required=True)
 parser.add_argument('--task',action='append');parser.add_argument('--variant',action='append')
 args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((Path(__file__).with_name('manifest.json')).read_text());plan=[];records=[]
 for request in manifest['calibration_requests']:
  if args.task and Path(request['task']).name not in args.task:continue
  if args.variant and request['variant'] not in args.variant:continue
  task=ROOT/request['task'];candidate=ROOT/request['candidate_directory']/'dut.va'
  if request['variant']=='reference':
   generated=out/'solve-outputs'/task.name;generated.mkdir(parents=True,exist_ok=True)
   script=task/'solution/solve.sh';invocation=script.read_text().replace('/solution/',str(task/'solution')+'/').replace('/work/',str(generated)+'/')
   subprocess.run(['sh','-c',invocation],check=True)
   candidate=generated/'dut.va'
   if candidate.read_bytes()!=(task/'solution/dut.va').read_bytes():raise ValueError('reference entrypoint byte mismatch')
  target=out/(task.name+'--'+request['variant'])
  if not target.exists():prepare(task,candidate,target,args.harness_checkout,task_version='circuit-benchmark-next-development')
  plan.append(str(target));records.append({**request,'prepared':str(target),'reference_script_sha256':hashlib.sha256((task/'solution/solve.sh').read_bytes()).hexdigest() if request['variant']=='reference' else None})
 (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');(out/'requests.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps({'prepared_variants':len(plan),'plan':str(out/'plan.json')}))
if __name__=='__main__':main()

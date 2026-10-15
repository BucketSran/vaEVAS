"""Author-only serial Spectre calibration; explicit private operator required."""
import argparse,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).parent
sys.path.insert(0,str(ROOT))
from experiments.benchmark_paths import material_path
from experiments.benchmark_first_batch.runtime import prepare,execute

def main():
 p=argparse.ArgumentParser();p.add_argument('--config',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--variant',action='append');a=p.parse_args()
 cfg=json.loads(a.config.read_text());plan=json.loads((HERE/'manifest.json').read_text())['calibration']
 a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=True)
 for item in plan:
  if a.variant and item['variant'] not in a.variant:continue
  task=material_path(ROOT, item['task']);out=a.output/(task.name+'-'+item['variant']);candidate=material_path(ROOT, item['candidate'])/'dut.va'
  if item['variant']=='reference':
   # Execute original oracle script using its unchanged fixed paths in a Docker
   # container; /work is a fresh host directory, /solution is immutable.
   reference_dir=a.output/'solution-output'/task.name;reference_dir.mkdir(parents=True,exist_ok=True)
   subprocess.run(['docker','run','--rm','-v',str(task/'solution')+':/solution:ro','-v',str(reference_dir)+':/work','python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c','sh','/solution/solve.sh'],check=True)
   candidate=reference_dir/'dut.va'
  if not (out/'preparation.json').exists():prepare(task,candidate,out,pathlib.Path(cfg['harness_checkout']),task_version='circuit-benchmark-next-development')
  execute(out,a.config)
  results=json.loads((out/'results.json').read_text())
  good=all(r['result']['execution']=='ok' and (r['result']['score']==int(item['expected_pass']) if item['expected_pass'] else r['result']['score'] in [0,1]) for r in results)
  if item['expected_pass']: good=good and all(r['result']['score']==1 for r in results)
  else: good=good and any(r['result']['score']==0 for r in results)
  print(json.dumps(dict(task=task.name,variant=item['variant'],expected_pass=item['expected_pass'],author_calibration_matches=good)),flush=True)
if __name__=='__main__':main()

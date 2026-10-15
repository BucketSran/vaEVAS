"""Freeze author matrix through existing runtime; never launches a job."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from experiments.benchmark_paths import material_path
from experiments.benchmark_first_batch.runtime import prepare

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--harness-checkout',type=Path,required=True)
    parser.add_argument('--solve-artifacts',type=Path,required=True)
    args=parser.parse_args()
    paths=[];smoke=[]
    for entry in json.loads((Path(__file__).with_name('run-plan.json')).read_text()):
        name=Path(entry['task']).name
        candidate=args.solve_artifacts/name/'dut.va' if entry['variant']=='reference' else material_path(ROOT, entry['candidate_directory'])/'dut.va'
        target=args.output/name/entry['variant']
        prepare(material_path(ROOT, entry['task']),candidate,target,args.harness_checkout,task_version='circuit-benchmark-next-development')
        paths.append(str(target.resolve()))
        if entry['variant']=='reference':smoke.append(str(target.resolve()))
    (args.output/'full.json').write_text(json.dumps(paths,indent=2)+'\n')
    (args.output/'smoke.json').write_text(json.dumps(smoke,indent=2)+'\n')
    (args.output/'remaining.json').write_text(json.dumps([p for p in paths if p not in smoke],indent=2)+'\n')
    print(json.dumps({'variants':len(paths),'reference_variants':len(smoke),'status':'prepared_only'}))
if __name__=='__main__':main()

"""Freeze calibrated inputs, then execute one Harbor attempt per task and model."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]


def main():
    tasks=sorted((ROOT/'benchmark/tasks').glob('va0[1-6]-*'))
    assert len(tasks)==6
    for task in tasks:
        r=json.loads((ROOT/'runs/va-screen/calibration'/task.name/'report.json').read_text())
        assert r['reward']==1,task.name
        assert r['candidate_sha256']==hashlib.sha256((task/'solution/dut.va').read_bytes()).hexdigest()
        assert r['cases_sha256']==hashlib.sha256((task/'tests/cases.json').read_bytes()).hexdigest()
        assert r['checker_sha256']==hashlib.sha256((task/'tests/verify.py').read_bytes()).hexdigest()
    mutations=json.loads((ROOT/'runs/va-screen/mutations/summary.json').read_text())
    assert len(mutations)==6 and all(m['compiled_and_rejected'] for m in mutations)
    output=ROOT/'runs/va-screen'/time.strftime('pilot-%Y%m%d-%H%M%S')
    output.mkdir(parents=True,exist_ok=False)
    files=[p for task in tasks for p in task.rglob('*') if p.is_file()]
    files += [p for p in (ROOT/'experiments/va_screen').glob('*.py')]
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
    (output/'input-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    metadata=dict(protocol='one-shot-no-tools-no-feedback',models=['glm-5.3','gpt-6.1-sol'],effort='xhigh',harbor='0.23.0',
                  attempts_per_task=1,task_count=6,model_calls_max=12,model_retry=0,
                  git_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  input_manifest_sha256=hashlib.sha256((output/'input-manifest.json').read_bytes()).hexdigest())
    (output/'protocol.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print('PILOT_ROOT='+str(output),flush=True)
    env=os.environ.copy();env['PYTHONPATH']=str(ROOT)
    def run(model):
        name='glm' if model.startswith('glm') else 'codex'
        argv=['uvx','--from','harbor==0.23.0','harbor','run','--path','benchmark/tasks',
              '--agent','experiments.va_screen.harbor_adapters:OneShotAgent','--model',model,
              '--verifier','experiments.va_screen.harbor_adapters:RemoteSpectreVerifier',
              '--jobs-dir',str(output),'--job-name',name,'--n-attempts','1','--n-concurrent','1','--max-retries','0']
        (output/f'{name}-command.json').write_text(json.dumps(argv,indent=2)+'\n')
        with (output/f'{name}-harbor.log').open('w') as log:
            process=subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=7200)
        print(name,'Harbor process exit',process.returncode,flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run,metadata['models']))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==s for p,s in manifest.items()),'frozen input changed during pilot'
    print('Pilot execution ended; inspect trial reports including exceptions.',flush=True)


if __name__=='__main__':main()

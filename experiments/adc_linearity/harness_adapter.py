"""Task-owned packaging and Harbor score adapter; harness owns all remote execution."""
import argparse
import hashlib
import importlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
TASK=ROOT/'benchmark/tasks/va08-adc-linearity'
VERSION='adc-linearity-v1-local-candidate'


def load_harness(checkout):
    checkout=Path(checkout).resolve()
    sys.path.insert(0,str(checkout))
    try:
        freeze=importlib.import_module('alphaapollo.common.execution.chips.candidate_bundle')
        packages=importlib.import_module('alphaapollo.common.execution.chips.benchmark_spectre')
        remote=importlib.import_module('alphaapollo.common.execution.chips.benchmark_remote')
    finally: sys.path.pop(0)
    for module in [freeze,packages,remote]:
        if not Path(module.__file__).resolve().is_relative_to(checkout):
            raise ValueError('loaded harness differs from explicitly selected checkout')
    return freeze,packages,remote


def prepare(harness_checkout,candidate,output,case_names=None):
    """Freeze original bytes and build private task manifests using existing APIs."""
    freeze,packages,_=load_harness(harness_checkout)
    candidate=Path(candidate).resolve();output=Path(output).resolve()
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    source=output/'source';source.mkdir(mode=0o700)
    (source/'dut.va').write_bytes(candidate.read_bytes())
    frozen=output/'frozen'
    freeze.freeze_candidate(source,frozen,['dut.va'],task_id=TASK.name,task_version=VERSION,reason='ADC first-task independent evaluation')
    cases=json.loads((TASK/'tests/cases.json').read_text())
    if case_names is not None:
        known={case['name'] for case in cases}
        if not case_names or not set(case_names)<=known: raise ValueError('unknown or empty case selection')
        cases=[case for case in cases if case['name'] in case_names]
    criteria=hashlib.sha256((TASK/'instruction.md').read_bytes()+(TASK/'tests/verify.py').read_bytes()+(TASK/'tests/cases.json').read_bytes()).hexdigest()
    identities=[]
    for case in cases:
        package=output/case['name'];(package/'tests').mkdir(mode=0o700,parents=True)
        for name in ['test.sh','verify.py']: (package/'tests'/name).write_bytes((TASK/'tests'/name).read_bytes())
        (package/'tests/cases.json').write_text(json.dumps([case],indent=2)+'\n')
        inventory={str(p.relative_to(package)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
                   for p in package.rglob('*') if p.is_file()}
        manifest=dict(schema_version=1,task_id=TASK.name,task_version=VERSION,criteria_sha256=criteria,
                      condition_id=case['name'],task_set='extension',purpose='final',entrypoint='tests/test.sh',
                      candidate_file='dut.va',report_path='verifier/report.json',files=inventory,feedback_fields=[])
        (package/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        identities.append(dict(condition_id=case['name'],package=str(package),sha256=packages.package_identity(package,purpose='final')['sha256']))
    record=dict(status='prepared_only',simulator_executed=False,candidate=freeze.verify_candidate(frozen),cases=identities)
    (output/'preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def aggregate(results):
    if not results or any(result.get('execution')!='ok' or type(result.get('score')) not in [int,float] or result.get('score') not in [0,1] for result in results):
        return dict(status='infrastructure_error',reward=None,results=results)
    return dict(status='completed',reward=int(all(result['score']==1 for result in results)),results=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--harness-checkout',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--case',action='append')
    args=parser.parse_args();print(json.dumps(prepare(args.harness_checkout,args.candidate,args.output,args.case),indent=2))

"""Task-owned packaging and Harbor score adapter; harness owns all remote execution."""
import argparse
import hashlib
import importlib
import json
import os
import tempfile
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
TASK=ROOT/'benchmark/tasks/va08-adc-linearity'
VERSION='adc-linearity-v2-local-candidate'


def validate_private_location(path,visible_paths,*,directory=True):
    """Check lexical and resolved paths against every candidate-visible mount."""
    path=Path(path).absolute()
    if '..' in path.parts or path.is_symlink(): raise ValueError('private location must not use symlink or parent traversal')
    resolved=path.resolve(strict=True)
    if (directory and not resolved.is_dir()) or (not directory and not resolved.is_file()): raise ValueError('invalid private location type')
    if resolved.stat().st_uid!=os.getuid() or resolved.stat().st_mode & 0o077:
        raise ValueError('private location must be owned and inaccessible to group/other')
    for mount in visible_paths:
        mount=Path(mount).absolute()
        for private in [path,resolved]:
            for visible in [mount,mount.resolve()]:
                if private==visible or private.is_relative_to(visible) or visible.is_relative_to(private):
                    raise ValueError('private location overlaps candidate-visible mount')
    return resolved


def visible_mount_roots(environment,task_directory,trial_directory):
    """Consume Harbor 0.23's actual mount inventory; unknown backends fail closed."""
    extras=getattr(environment,'extra_docker_compose_paths',None)
    if not isinstance(extras,list) or extras:
        raise ValueError('ADC requires no extra Docker Compose overlays')
    envdir=Path(getattr(environment,'environment_dir','')).resolve()
    if envdir!=(Path(task_directory)/'environment').resolve():
        raise ValueError('ADC requires the task Dockerfile environment')
    if not (envdir/'Dockerfile').is_file() or (envdir/'Dockerfile').is_symlink():
        raise ValueError('ADC requires a regular Dockerfile')
    if (envdir/'docker-compose.yaml').exists() or (envdir/'docker-compose.yaml').is_symlink():
        raise ValueError('ADC does not support task Docker Compose definitions')
    config=getattr(environment,'task_env_config',None)
    if config is None or getattr(config,'docker_image',None) is not None:
        raise ValueError('ADC does not support prebuilt environment entrypoints')
    mounts=getattr(environment,'_mounts',None)
    if not isinstance(mounts,list): raise ValueError('candidate host mount inventory unavailable')
    visible=[Path(task_directory),Path(trial_directory)]
    for mount in mounts:
        if not isinstance(mount,dict) or mount.get('type')!='bind' or not Path(mount.get('source','')).is_absolute():
            raise ValueError('unsupported candidate mount type or source')
        visible.append(Path(mount['source']))
    return visible


def private_workspace(root,visible_paths,context):
    root=validate_private_location(root,visible_paths)
    if not context or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in context): raise ValueError('invalid private workspace context')
    work=root/context; work.mkdir(mode=0o700,exist_ok=False)
    return work


def publish_result(output,report):
    """Publish only scalar status/reward; never follow candidate-created links."""
    output=Path(output)
    if output.is_symlink(): raise ValueError('verifier log directory is a symlink')
    output.mkdir(parents=True,exist_ok=True)
    projection={key:report[key] for key in ['status','reward']}
    files={'report.json':json.dumps(projection,indent=2)+'\n'}
    if report['reward'] is not None: files['reward.txt']=str(report['reward'])+'\n'
    for name,text in files.items():
        descriptor,temporary=tempfile.mkstemp(dir=output,prefix='.adc-projection-')
        try:
            with os.fdopen(descriptor,'w') as stream: stream.write(text)
            os.replace(temporary,output/name)
        finally: Path(temporary).unlink(missing_ok=True)
    if report['reward'] is None: (output/'reward.txt').unlink(missing_ok=True)


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

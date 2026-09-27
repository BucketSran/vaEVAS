"""Bounded server runner; raw deployment paths and outputs stay outside Git.

Uses the existing private environment's container launcher, not its old models
or grading code. Run Spectre first, then the other backends against frozen input.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time

from suite import conditions, netlists, PROFILES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')


def execute(argv, work, stage, root, env, container_name=None, limit=90):
    record=dict(argv=argv, stage=stage, started_unix=time.time(), timeout_s=limit,
                container_name=container_name, cwd=str(work))
    with (root/'commands.jsonl').open('a') as stream:
        stream.write(json.dumps(record)+'\n')
    start=time.perf_counter()
    with (work/(stage+'.log')).open('x') as log:
        proc=subprocess.Popen(argv,cwd=work,stdout=log,stderr=subprocess.STDOUT,
                              start_new_session=True,env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'})
        try:
            record.update(exit_code=proc.wait(timeout=limit),timed_out=False)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid,signal.SIGKILL)
            proc.wait(timeout=5)
            record.update(exit_code=None,timed_out=True)
            if container_name:
                cleanup=subprocess.run(env.podman()+['rm','-f',container_name],capture_output=True,text=True,timeout=15)
                record['cleanup_exit_code']=cleanup.returncode
                exists=subprocess.run(env.podman()+['container','exists',container_name],timeout=5)
                if exists.returncode!=1:
                    raise RuntimeError('container timeout cleanup unconfirmed')
    record['elapsed_s']=time.perf_counter()-start
    record['log_sha256']=sha(work/(stage+'.log'))
    save(work/(stage+'.json'),record)
    return record


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--environment',required=True,type=Path)
    parser.add_argument('--spectre-profile',required=True,type=Path)
    parser.add_argument('--backend',required=True,choices=['spectre','evas','openvaf_ngspice','gnucap'])
    parser.add_argument('--profiles',nargs='+',default=['base','fine'],choices=list(PROFILES))
    parser.add_argument('--conditions',nargs='*')
    args=parser.parse_args()
    root=args.root.resolve(); source=Path(__file__).resolve().parents[2]
    manifest=json.loads((source/'INPUT_MANIFEST.json').read_text())
    for name,digest in manifest.items():
        if sha(source/name)!=digest:
            raise ValueError('frozen input mismatch: '+name)
    spec=importlib.util.spec_from_file_location('environment',args.environment/'environment.py')
    env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
    images=env.check_inputs()
    identity=dict(backend=args.backend,images=images,input_manifest_sha256=sha(source/'INPUT_MANIFEST.json'),
        environment_py_sha256=sha(args.environment/'environment.py'),cpu=min(os.sched_getaffinity(0)),
        uname=list(os.uname()),load_average=list(os.getloadavg()),profiles=args.profiles)
    (root/'identities').mkdir(exist_ok=True)
    identity_file=root/'identities'/(args.backend+'-'+','.join(args.profiles)+'.json')
    if identity_file.exists():
        raise ValueError('invocation identity exists; use a separate attempt root')
    save(identity_file,identity)
    profile=json.loads(args.spectre_profile.read_text())
    for path in [profile['spectre']]+profile['setup_scripts']:
        if not re.fullmatch(r'/[A-Za-z0-9_./-]+',path):
            raise ValueError('unsafe csh path')

    def container(image,exe,argv,work,stage):
        cmd,name=env.container(images[image]['config_id'],exe,argv,work)
        return execute(cmd,work,stage,root,env,name)

    compiled={}
    def compile_model(card):
        if card in compiled:
            return compiled[card]
        work=root/'build'/args.backend/card
        work.mkdir(parents=True,exist_ok=False)
        shutil.copy2(source/'evas/validation/cases'/card/'dut.va',work/'dut.va')
        if args.backend=='openvaf_ngspice':
            stages=[('openvaf_runtime','/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',
                     ['dut.va','-o','dut.osdi'],'compile','dut.osdi')]
        else:
            stages=[('gnucap','/opt/gnucap/bin/gnucap-mg-vams',
                     ['-I','/opt/gnucap/include/gnucap','-o','dut.cc','--cc','dut.va'],'modelgen','dut.cc'),
                    ('gnucap','/usr/bin/c++',['-std=c++14','-I','/opt/gnucap/include/gnucap',
                     '-fPIC','-shared','dut.cc','-o','dut.so'],'cpp_compile','dut.so')]
        result=dict(source_sha256=sha(work/'dut.va'),build_directory=str(work),status='compiled',stages=[])
        for image,exe,argv,stage,artifact in stages:
            record=container(image,exe,argv,work,stage)
            result['stages'].append(record)
            if record['exit_code']!=0 or not (work/artifact).is_file():
                result['status']='compile_timeout' if record['timed_out'] else 'compile_failed'
                result['failure_stage']=stage
                break
            result[artifact+'_sha256']=sha(work/artifact)
        save(work/'result.json',result)
        compiled[card]=result
        return result

    selected=[c for c in conditions() if not args.conditions or c['id'] in args.conditions]
    if args.conditions and set(args.conditions)!=set(c['id'] for c in selected):
        raise ValueError('unknown condition')
    results=[]
    for case in selected:
        build=compile_model(case['card']) if args.backend in ['gnucap','openvaf_ngspice'] else None
        for setting in args.profiles:
            work=root/'runs'/args.backend/case['id']/setting
            work.mkdir(parents=True,exist_ok=False)
            shutil.copy2(source/'evas/validation/cases'/case['card']/'dut.va',work/'dut.va')
            save(work/'condition.json',case)
            save(work/'requested_settings.json',PROFILES[setting])
            for name,content in netlists(case,setting).items():
                (work/name).write_text(content)
            result=dict(backend=args.backend,condition=case['id'],card=case['card'],profile=setting,
                        source_sha256=sha(work/'dut.va'),status='not_run',build=build)
            if build and build['status']!='compiled':
                result.update(status=build['status'],failure_stage=build['failure_stage'])
            else:
                previous=[json.loads(line) for line in (root/'commands.jsonl').read_text().splitlines()] if (root/'commands.jsonl').exists() else []
                if sum(r['stage']=='simulate' for r in previous)>=120:
                    raise RuntimeError('simulation launch cap exceeded')
                if args.backend=='spectre':
                    (work/'run.csh').write_text('\n'.join('source '+s for s in profile['setup_scripts'])+'\n'+
                        f"{profile['spectre']} -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n")
                    record=execute(['taskset','-c',str(identity['cpu']),'/bin/csh','-f','run.csh'],work,'simulate',root,env)
                    artifact=work/'psf/tran.tran.tran'
                elif args.backend=='evas':
                    record=container('evas','/usr/local/bin/evas',
                                     ['simulate','tb.scs','-o','output','--spectre-strict'],work,'simulate')
                    artifact=work/'output/tran.csv'
                elif args.backend=='gnucap':
                    shutil.copy2(Path(build['build_directory'])/'dut.so',work/'dut.so')
                    record=container('gnucap','/opt/gnucap/bin/gnucap',['tb.gc'],work,'simulate')
                    artifact=work/'waveform.txt'
                else:
                    shutil.copy2(Path(build['build_directory'])/'dut.osdi',work/'dut.osdi')
                    record=container('ngspice','/opt/ngspice/bin/ngspice',['-b','tb.cir'],work,'simulate')
                    artifact=work/'waveform.txt'
                result['execution']=record
                if record['timed_out']:
                    result['status']='runtime_timeout'
                elif record['exit_code']!=0:
                    result['status']='execution_failed'
                elif not artifact.is_file():
                    result['status']='missing_waveform'
                else:
                    result.update(status='waveform_available',waveform=str(artifact.relative_to(work)),
                                  waveform_sha256=sha(artifact))
            save(work/'result.json',result)
            results.append(result)
            print(json.dumps({k:result[k] for k in ['backend','condition','profile','status']}) ,flush=True)
    save(root/(args.backend+'-'+','.join(args.profiles)+'-execution.json'),results)


if __name__=='__main__':
    main()

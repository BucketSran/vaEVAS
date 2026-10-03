"""Serial, pinned-container supplementary execution; immutable inputs and no retries."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p,d):
    with p.open('x') as f:json.dump(d,f,indent=2);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--environment',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();os.umask(0o077)
    for rel,d in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        p=root/rel
        if not p.resolve().is_relative_to(root) or sha(p)!=d['sha256'] or p.stat().st_size!=d['bytes']:
            raise ValueError('frozen input drift: '+rel)
    provenance=json.loads((root/'provenance.json').read_text())
    path=args.environment/'environment.py'
    if sha(path)!=provenance['environment_sha256']:raise ValueError('environment launcher drift')
    spec=importlib.util.spec_from_file_location('environment',path)
    env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
    images=env.check_inputs();expected=json.loads((root/'expected_images.json').read_text())
    if {k:v['config_id'] for k,v in images.items()}!={k:v['config_id'] for k,v in expected.items()}:
        raise ValueError('pinned image identity drift')
    plan=json.loads((root/'RUN_PLAN.json').read_text())
    assert len(plan)==provenance['max_configurations']==130
    save(root/'STARTED.json',dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),images=images,cpu=min(os.sched_getaffinity(0)),
        environment_sha256=sha(path),max_simulations=130,max_compiler_stages=35,timeout_s=90))
    shutil.copyfile(path,root/'environment.snapshot.py')
    calls=[]
    def execute(image,exe,argv,work,stage,limit=90):
        if stage=='simulate' and sum(c['stage']=='simulate' for c in calls)>=130:raise RuntimeError('simulation budget exhausted')
        if stage in ('compile','modelgen','cpp_compile') and sum(c['stage'] in ('compile','modelgen','cpp_compile') for c in calls)>=35:
            raise RuntimeError('compiler budget exhausted')
        cmd,name=env.container(images[image]['config_id'],exe,argv,work)
        record=dict(stage=stage,argv=cmd,container=name,started_unix=time.time(),timeout_s=limit)
        calls.append(record)
        with (root/'commands.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
        start=time.monotonic()
        with (work/(stage+'.log')).open('x') as log:
            process=subprocess.Popen(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,
                env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
            try:record.update(exit_code=process.wait(timeout=limit),timed_out=False)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
                cleanup=subprocess.run(env.podman()+['rm','-f',name],capture_output=True,text=True,timeout=15)
                exists=subprocess.run(env.podman()+['container','exists',name],capture_output=True,timeout=5)
                record.update(exit_code=None,timed_out=True,cleanup_exit_code=cleanup.returncode,container_absent=exists.returncode==1)
                if exists.returncode!=1:raise RuntimeError('owned container cleanup not confirmed')
        record.update(elapsed_s=time.monotonic()-start,log_sha256=sha(work/(stage+'.log')))
        save(work/(stage+'.json'),record)
        return record
    versions=root/'versions';versions.mkdir()
    checks=[('evas','/usr/local/bin/evas',['--version']),
            ('openvaf_runtime','/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',['--version']),
            ('ngspice','/opt/ngspice/bin/ngspice',['--version']),
            ('gnucap','/opt/gnucap/bin/gnucap-mg-vams',['--version']),
            ('gnucap','/bin/sh',['-c','sha256sum /opt/gnucap/bin/gnucap /opt/gnucap/bin/gnucap-mg-vams /opt/gnucap/lib/libgnucap.so'])]
    for i,(image,exe,argv) in enumerate(checks):
        r=execute(image,exe,argv,versions,'version-'+str(i),30)
        if r['exit_code']!=0 or r['timed_out']:raise RuntimeError('tool identity preflight failed')
    compiled={};records=[]
    for item in plan:
        backend=item['backend'];work=root/'runs'/backend/item['condition']/item['profile']
        if sha(work/'dut.va')!=item['source_sha256']:raise ValueError('DUT drift')
        build=None
        if backend!='evas':
            key=(backend,item['source_sha256'])
            if key not in compiled:
                directory=root/'build'/backend/item['source_sha256'];directory.mkdir(parents=True)
                shutil.copyfile(work/'dut.va',directory/'dut.va')
                stages=[('openvaf_runtime','/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',
                         ['dut.va','-o','dut.osdi'],'compile','dut.osdi')] if backend=='openvaf_ngspice' else [
                         ('gnucap','/opt/gnucap/bin/gnucap-mg-vams',['-I','/opt/gnucap/include/gnucap','-o','dut.cc','--cc','dut.va'],'modelgen','dut.cc'),
                         ('gnucap','/usr/bin/c++',['-std=c++14','-I','/opt/gnucap/include/gnucap','-fPIC','-shared','dut.cc','-o','dut.so'],'cpp_compile','dut.so')]
                build=dict(directory=str(directory.relative_to(root)),source_sha256=item['source_sha256'],status='compiled',stages=[])
                for image,exe,argv,stage,artifact in stages:
                    r=execute(image,exe,argv,directory,stage);build['stages'].append(r)
                    if r['timed_out'] or r['exit_code']!=0 or not (directory/artifact).exists():
                        build.update(status='compile_timeout' if r['timed_out'] else 'compile_failed',failure_stage=stage);break
                    build[artifact+'_sha256']=sha(directory/artifact)
                save(directory/'result.json',build);compiled[key]=build
            build=compiled[key]
        result=dict(item,status='not_run',build=build)
        if build and build['status']!='compiled':result.update(status=build['status'],failure_stage=build['failure_stage'])
        else:
            if backend=='evas':image,exe,argv,artifact='evas','/usr/local/bin/evas',['simulate','tb.scs','-o','output','--spectre-strict'],'output/tran.csv'
            elif backend=='gnucap':
                shutil.copyfile(root/build['directory']/'dut.so',work/'dut.so')
                image,exe,argv,artifact='gnucap','/opt/gnucap/bin/gnucap',['tb.gc'],'waveform.txt'
            else:
                shutil.copyfile(root/build['directory']/'dut.osdi',work/'dut.osdi')
                image,exe,argv,artifact='ngspice','/opt/ngspice/bin/ngspice',['-b','tb.cir'],'waveform.txt'
            r=execute(image,exe,argv,work,'simulate');result['execution']=r
            result['status']='runtime_timeout' if r['timed_out'] else 'execution_failed' if r['exit_code']!=0 else 'waveform_available' if (work/artifact).exists() else 'missing_waveform'
            if (work/artifact).exists():result.update(waveform=artifact,waveform_sha256=sha(work/artifact))
        save(work/'result.json',result);records.append(result)
        print(len(records),backend,item['condition'],item['profile'],result['status'],flush=True)
    save(root/'EXECUTION.json',records)
    save(root/'STAGE_COUNTS.json',{stage:sum(c['stage']==stage for c in calls) for stage in sorted({c['stage'] for c in calls})})
    save(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):dict(sha256=sha(p),bytes=p.stat().st_size)
        for p in sorted(root.rglob('*')) if p.is_file()})


if __name__=='__main__':main()

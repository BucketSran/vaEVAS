"""Serial Spectre-only runner. Immutable input manifest; 62 attempts maximum."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p, value):
    with p.open('x') as stream:
        json.dump(value,stream,indent=2)
        stream.write('\n')


def execute(argv, work, log, limit):
    start=time.monotonic()
    env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with (work/log).open('x') as out:
        process=subprocess.Popen(argv,cwd=work,stdout=out,stderr=subprocess.STDOUT,env=env,start_new_session=True)
        timed_out=False
        try:
            code=process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            timed_out=True
            os.killpg(process.pid,signal.SIGTERM)
            try: code=process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                code=process.wait()
    return dict(argv=argv,returncode=code,timeout=timed_out,elapsed_s=time.monotonic()-start,log=log,log_sha256=digest(work/log))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--spectre-profile',type=Path,required=True)
    args=parser.parse_args(); root=args.root.resolve()
    os.umask(0o077)
    manifest=json.loads((root/'INPUT_MANIFEST.json').read_text())
    for rel, identity in manifest.items():
        p=root/rel
        if not p.resolve().is_relative_to(root) or digest(p)!=identity['sha256'] or p.stat().st_size!=identity['bytes']:
            raise ValueError('input drift: '+rel)
    inputs_sha=digest(root/'INPUT_MANIFEST.json')
    profile=json.loads(args.spectre_profile.read_text())
    binary=profile['spectre']; scripts=profile['setup_scripts']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]):
        raise ValueError('unsupported tool path')
    source='\n'.join('source '+p for p in scripts)+'\n'
    cpu=min(os.sched_getaffinity(0))
    # A started job cannot be silently restarted over partial results.
    dump(root/'STARTED.json',dict(utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
        input_manifest_sha256=inputs_sha,max_runs=62,cpu=cpu,timeout_s=90,license_timeout_s=30))
    (root/'version.csh').write_text(source+binary+' -W\nexit $status\n')
    version=execute(['/bin/csh','-f','version.csh'],root,'version.log',30)
    dump(root/'TOOL_IDENTITY.json',dict(binary_sha256=digest(Path(binary)),version_probe=version,
        setup_sha256=[digest(Path(s)) for s in scripts]))
    if version['returncode'] != 0 or version['timeout']:
        raise RuntimeError('Spectre version preflight failed')
    cases=json.loads((root/'conditions.json').read_text())
    assert len(cases)==31
    records=[]
    for case in cases:
        for setting in ['base','fine']:
            work=root/'runs'/case['id']/setting
            (work/'run.csh').write_text(source+binary+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
            result=execute(['taskset','-c',str(cpu),'/bin/csh','-f','run.csh'],work,'stdout.log',90)
            waveform=work/'psf/tran.tran.tran'
            result.update(backend='spectre',condition=case['id'],profile=setting,source_sha256=digest(work/'dut.va'),
                netlist_sha256=digest(work/'tb.scs'),waveform='psf/tran.tran.tran' if waveform.exists() else None)
            result['status']='timeout' if result['timeout'] else 'execution_failure' if result['returncode']!=0 else 'waveform_available' if waveform.exists() else 'missing_waveform'
            if waveform.exists(): result['waveform_sha256']=digest(waveform)
            dump(work/'result.json',result)
            records.append(result)
            print(len(records),case['id'],setting,result['status'],round(result['elapsed_s'],2),flush=True)
    assert len(records)==62
    dump(root/'EXECUTION.json',records)
    dump(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):dict(sha256=digest(p),bytes=p.stat().st_size)
        for p in sorted(root.rglob('*')) if p.is_file()})


if __name__=='__main__': main()

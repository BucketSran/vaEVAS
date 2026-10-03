"""Bounded post-baseline diagnostic contrasts; never changes baseline evidence."""
import argparse, hashlib, importlib.util, json, os, shutil, signal, subprocess, time
from pathlib import Path


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p, value):
    with p.open('x') as f: json.dump(value, f, indent=2); f.write('\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',type=Path);ap.add_argument('environment',type=Path)
    args=ap.parse_args();root=args.root.resolve();os.umask(0o077)
    for rel,identity in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        p=root/rel
        assert p.resolve().is_relative_to(root) and sha(p)==identity['sha256'] and p.stat().st_size==identity['bytes']
    assert sha(args.environment)=='3b85fddd09d943b331b0f6ca1b8d687c5932d6f2e2ec7683133f418e4901edba'
    spec=importlib.util.spec_from_file_location('env',args.environment);env=importlib.util.module_from_spec(spec);spec.loader.exec_module(env)
    images=env.check_inputs();expected=json.loads((root/'expected_images.json').read_text())
    assert {k:v['config_id'] for k,v in images.items()}=={k:v['config_id'] for k,v in expected.items()}
    plan=json.loads((root/'PLAN.json').read_text());assert len(plan)==15
    save(root/'STARTED.json',dict(input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),images=images,max_simulations=13,max_compilations=5,timeout_s=45))
    calls=[];compiled={};results=[]
    def call(work,image,exe,argv,stage):
        assert sum(c['stage']=='simulate' for c in calls)<13 if stage=='simulate' else sum(c['stage']=='compile' for c in calls)<5
        cmd,name=env.container(images[image]['config_id'],exe,argv,work)
        r=dict(stage=stage,argv=cmd,container=name,timeout_s=45,started_unix=time.time());calls.append(r)
        with (root/'commands.jsonl').open('a') as f:f.write(json.dumps(r)+'\n')
        start=time.monotonic()
        with (work/(stage+'.log')).open('x') as log:
            proc=subprocess.Popen(cmd,cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:r.update(exit_code=proc.wait(timeout=45),timed_out=False)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=5)
                cleanup=subprocess.run(env.podman()+['rm','-f',name],capture_output=True,timeout=15)
                exists=subprocess.run(env.podman()+['container','exists',name],capture_output=True,timeout=5)
                r.update(exit_code=None,timed_out=True,cleanup_exit_code=cleanup.returncode,container_absent=exists.returncode==1)
                if exists.returncode!=1:raise RuntimeError('cleanup not confirmed')
        r.update(elapsed_s=time.monotonic()-start,log_sha256=sha(work/(stage+'.log')));save(work/(stage+'.json'),r)
        return r
    for item in plan:
        w=root/'probes'/item['id'];b=item['backend'];r=dict(item)
        if b=='openvaf_ngspice':
            r['compile']=call(w,'openvaf_runtime','/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',['--dump-mir','dut.va','-o','dut.osdi'],'compile')
        else:
            if b=='gnucap':
                key=sha(w/'dut.cc')
                if key not in compiled:
                    compiled[key]=(w,call(w,'gnucap','/usr/bin/c++',['-std=c++14','-I','/opt/gnucap/include/gnucap','-fPIC','-shared','dut.cc','-o','dut.so'],'compile'))
                build,result=compiled[key];r['compile']=result;r['compiled_in']=str(build.relative_to(root))
                if result['exit_code']==0 and build!=w:shutil.copyfile(build/'dut.so',w/'dut.so')
            if b=='evas' or r['compile']['exit_code']==0:
                exe,argv,artifact=('/usr/local/bin/evas',['simulate','tb.scs','-o','output','--spectre-strict'],'output/tran.csv') if b=='evas' else ('/opt/gnucap/bin/gnucap',['tb.gc'],'waveform.txt')
                r['execution']=call(w,b,exe,argv,'simulate')
                if (w/artifact).exists():r.update(waveform=artifact,waveform_sha256=sha(w/artifact))
        save(w/'result.json',r);results.append(r);print(item['id'],r.get('execution',r.get('compile'))['exit_code'],flush=True)
    save(root/'RESULTS.json',results)
    save(root/'STAGE_COUNTS.json',{s:sum(r['stage']==s for r in calls) for s in ['simulate','compile']})
    save(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in sorted(root.rglob('*')) if p.is_file()})


if __name__=='__main__':main()

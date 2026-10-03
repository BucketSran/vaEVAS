"""Transfer private tests + one candidate to an existing licensed Spectre host."""
import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import tarfile
import uuid


BOOTSTRAP=r'''
import io,json,os,pathlib,re,subprocess,sys,tarfile
os.umask(0o077)
root=pathlib.Path(sys.argv[1]);root.mkdir(parents=True,exist_ok=False)
data=sys.stdin.buffer.read()
with tarfile.open(fileobj=io.BytesIO(data)) as tar:
 for member in tar.getmembers():
  if not member.isfile() or pathlib.PurePosixPath(member.name).is_absolute() or '..' in pathlib.PurePosixPath(member.name).parts:raise ValueError('invalid input archive')
  path=root/member.name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(tar.extractfile(member).read())
profile=json.loads(pathlib.Path(sys.argv[2]).read_text())
paths=[profile['spectre'],*profile['setup_scripts']]
if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in paths):raise ValueError('unsupported configured path')
command='\n'.join('source '+p for p in profile['setup_scripts'])+'\n'
command+='setenv SPECTRE '+profile['spectre']+'\n'
command+='setenv CANDIDATE '+str(root/'dut.va')+'\nsetenv VERIFY_OUTPUT '+str(root/'verifier')+'\n'
command+='/bin/sh '+str(root/'tests/test.sh')+'\nexit $status\n'
run=subprocess.run([profile.get('shell','/bin/csh'),'-f','-c',command],cwd=root,capture_output=True,text=True,timeout=580)
reportpath=root/'verifier/report.json'
if reportpath.exists():report=json.loads(reportpath.read_text())
else:report=dict(status='infrastructure_error',reward=None,error=run.stdout[-3000:]+run.stderr[-3000:])
report['remote_root']=str(root);report['launcher_returncode']=run.returncode
print(json.dumps(report))
'''


def grade(task, candidate, output, host=None, profile=None):
    task=Path(task);candidate=Path(candidate);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    host=host or os.environ.get('VA_SCREEN_SSH_HOST','thu-sui')
    profile=profile or os.environ.get('VA_SCREEN_SPECTRE_PROFILE','/home/jinzhihong/chips-private/config/spectre/rc.profile.json')
    run_root=os.environ.get('VA_SCREEN_REMOTE_ROOT','/home/jinzhihong/chips-private/validation/va-screen')
    remote=f'{run_root}/{task.name}-{uuid.uuid4().hex[:12]}'
    buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w') as tar:
        tar.add(candidate,arcname='dut.va')
        for path in sorted((task/'tests').rglob('*')):
            if path.is_file():tar.add(path,arcname=str(path.relative_to(task)))
    encoded=base64.b64encode(BOOTSTRAP.encode()).decode()
    code=f'import base64;exec(base64.b64decode("{encoded}"))'
    remote_command='python3 -c '+shlex.quote(code)+' '+shlex.quote(remote)+' '+shlex.quote(profile)
    run=subprocess.run(['ssh','-T','-o','BatchMode=yes',host,remote_command],input=buffer.getvalue(),capture_output=True,timeout=600)
    (output/'transport.stderr').write_bytes(run.stderr)
    if run.returncode!=0:raise RuntimeError('SSH verifier failed: '+run.stderr.decode(errors='replace')[-2000:])
    report=json.loads(run.stdout)
    report['transport_input_sha256']=hashlib.sha256(buffer.getvalue()).hexdigest()
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if report['reward'] is not None:(output/'reward.txt').write_text(str(report['reward'])+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('task',type=Path);p.add_argument('candidate',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();r=grade(a.task,a.candidate,a.output)
    print(json.dumps({k:r[k] for k in ['status','reward','remote_root']}))
    for c in r.get('cases',[]):print(c['name'],c['status'],c.get('passed'),c.get('failures',[])[:2])

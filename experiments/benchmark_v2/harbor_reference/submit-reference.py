"""One mechanical submission of original solve.sh outputs, no model or simulation."""
import hashlib,json,subprocess
from pathlib import Path
binding=json.loads(Path('/solution/oracle-binding.json').read_text())
def action(action_id,tool,arguments):
 p=subprocess.run(['harness-public','action'],input=json.dumps({'action_id':action_id,'tool':tool,'arguments':arguments}),text=True,capture_output=True,check=True)
 print(p.stdout,flush=True);r=json.loads(p.stdout)
 if r.get('error') or r.get('ok') is not True:raise RuntimeError('public action incomplete; preserve same ID, never retry here')
 return r['result']
for i,(name,spec) in enumerate(binding['files'].items()):
 p=Path(spec['work_path']);assert not p.is_symlink();b=p.read_bytes();assert hashlib.sha256(b).hexdigest()==spec['sha256']
 r=action(f'oracle-write-{i}','evas_write',{'path':name,'content':b.decode('utf-8')});assert r['sha256']==spec['sha256']
action('oracle-submit','evas_submit',{})

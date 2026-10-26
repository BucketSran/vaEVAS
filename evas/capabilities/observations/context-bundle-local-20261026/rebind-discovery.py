"""Rebind only changed workflow source lines; preserve the observed receipt."""
import hashlib, importlib.util, json
from pathlib import Path
R=Path(__file__).resolve().parent
C=json.loads((R/'config-unpublished.json').read_text())
S=Path(C['source_root'])
spec=importlib.util.spec_from_file_location('bundle_inventory',S/'scripts/capabilities/collect_ci_inventory.py')
inv=importlib.util.module_from_spec(spec);spec.loader.exec_module(inv)
entries=inv.parse_workflow((S/inv.WORKFLOW).read_bytes())['entries']
changes=[]
for item in C['discoveries']:
    wrapper=json.loads(Path(item['entry_file']).read_text()); old=wrapper['entry']
    if old.get('mode')!='declared-ci-literal' or old in entries: continue
    matches=[e for e in entries if {k:v for k,v in old.items() if k not in ('line','entry_id')}=={k:v for k,v in e.items() if k not in ('line','entry_id')}]
    assert len(matches)==1, 'Non-location workflow change requires new discovery'
    new=matches[0]
    for row in wrapper['receipt']['methods']:
        assert hashlib.sha256((S/row['module_path']).read_bytes()).hexdigest()==row['module_sha256']
    path=R/'entry-differential-rebound.json'; assert not path.exists()
    path.write_text(json.dumps(dict(entry=new,receipt=wrapper['receipt'],reuse=dict(original_file=item['entry_file'],original_sha256=hashlib.sha256(Path(item['entry_file']).read_bytes()).hexdigest(),reason='only workflow line moved; command/environment and all observed module bytes unchanged')),indent=2)+'\n')
    changes.append(dict(old_entry=old['entry_id'],new_entry=new['entry_id'],old_line=old['line'],new_line=new['line'],unchanged_methods=wrapper['receipt']['discovered_instances']))
    item['entry_file']=str(path)
assert len(changes)==1
(R/'discovery-rebinding.json').write_text(json.dumps(changes,indent=2)+'\n')
(R/'config-rebound.json').write_text(json.dumps(C,indent=2)+'\n')
print(json.dumps(changes))

"""Follow-up after slew reversal failed: vary only maxstep, retain the target."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import operators as op


def build(source, root):
    op.verify(source)
    root.mkdir(parents=True, exist_ok=False)
    cases=[]
    for old in json.loads((source/'conditions.json').read_text()):
        if old['name'] not in ['sl-reverse','sl-reflected'] or old['profile']!='fine': continue
        for denominator in [128,512,2048,8192]:
            c=copy.deepcopy(old)
            c.update(id=old['name']+'-step-'+str(denominator),profile='step-'+str(denominator),
                     maxstep=old['unit']/denominator,source_configuration=old['id'])
            c['settings']['step']=1/denominator
            cases.append(c)
            work=root/c['id'];work.mkdir()
            shutil.copyfile(source/old['id']/'probe.va',work/'probe.va')
            deck=(source/old['id']/'tb.scs').read_text()
            deck=deck.replace(f' step={old["maxstep"]!r} maxstep={old["maxstep"]!r}',
                              f' step={c["maxstep"]!r} maxstep={c["maxstep"]!r}')
            (work/'tb.scs').write_text(deck)
    op.dump(root/'conditions.json',cases)
    op.dump(root/'contract.json',dict(max_spectre_attempts=len(cases), timeout_s=90, license_timeout_s=30,
        parent_input_manifest_sha256=op.digest(source/'INPUT_MANIFEST.json'),
        reason='Main-run reversal error decreased from base to fine; isolate step refinement.',
        changed='step/maxstep only; same physical model, stimuli, reltol/vabstol, common grid and 1 mV target',
        formal_qualification=False))
    identities=json.loads((source/'checker_identity.json').read_text())
    identities[str(Path(__file__).resolve().relative_to(op.ROOT))]=op.digest(Path(__file__))
    op.dump(root/'checker_identity.json',identities)
    op.dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):op.digest(p)
        for p in sorted(root.rglob('*')) if p.is_file()})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();build(a.source,a.root)

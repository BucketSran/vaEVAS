"""31-condition Spectre verification input builder; no simulator-derived answers."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'evas/validation'))
from dvs2.cases import T, PROFILES, conditions, v1, pulse, reset, instance
from dvs2 import source_files as scientific_sources


def netlist(c, profile):
    p = PROFILES[profile]
    lines = ['simulator lang=spectre', 'ahdl_include "dut.va"']
    for name, points in c['inputs'].items():
        wave=' '.join(f'{x*T:.17g} {y:.17g}' for x,y in points)
        lines.append(f'V{name} ({name} 0) vsource type=pwl wave=[{wave}]')
    for inst in c['instances']:
        params=' '.join(f'{k}={v:.17g}' for k,v in inst['params'].items())
        lines.append(f"{inst['name']} ({' '.join(inst['ports'])}) {inst.get('module',c.get('module'))} {params}")
    lines += [f"simulatorOptions options reltol={p['reltol']:.17g} vabstol={p['vabstol']:.17g} iabstol={p['iabstol']:.17g}",
              f"tran tran stop={c['stop_x']*T:.17g} step={p['step']:.17g} maxstep={p['step']:.17g} method=traponly",
              'save '+' '.join(list(c['inputs'])+c['outputs'])]
    return '\n'.join(lines)+'\n'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(root):
    root.mkdir(parents=True, exist_ok=False)
    specs=conditions()
    (root/'conditions.json').write_text(json.dumps(specs,indent=2)+'\n')
    for c in specs:
        for profile in PROFILES:
            work=root/'runs'/c['id']/profile
            work.mkdir(parents=True)
            (work/'condition.json').write_text(json.dumps(c,indent=2)+'\n')
            (work/'requested_settings.json').write_text(json.dumps({**PROFILES[profile], 'method':'traponly',
                'stop':c['stop_x']*T,'maxstep':PROFILES[profile]['step'],'forced_strobe':False},indent=2)+'\n')
            (work/'dut.va').write_text('\n'.join((ROOT/'evas/validation/cases'/card/'dut.va').read_text() for card in c['source_cards']))
            (work/'tb.scs').write_text(netlist(c,profile))
    shutil.copyfile(Path(__file__).with_name('remote.py'),root/'remote.py')
    provenance={}
    dependencies=[ROOT/'experiments/archive/dvs2-starter-pilot'/name for name in ['suite.py','analyze.py']]
    dependencies += scientific_sources(ROOT)
    dependencies += list(Path(__file__).parent.glob('*.py'))
    dependencies += [Path(__file__).with_name('PROTOCOL.md')]
    dependencies += [ROOT/'evas/validation'/name for name in ['CASE_CARDS.md','NEXT_CASE_CARDS.md','METHOD_QUALIFICATION.md']]
    for path in dependencies:
        rel=path.relative_to(ROOT)
        target=root/'analysis-source'/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        provenance[str(rel)]=digest(path)
    (root/'source_identity.json').write_text(json.dumps(provenance,indent=2)+'\n')
    manifest={str(p.relative_to(root)):dict(sha256=digest(p),bytes=p.stat().st_size)
              for p in sorted(root.rglob('*')) if p.is_file()}
    (root/'INPUT_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Frozen {len(specs)} conditions, {len(specs)*len(PROFILES)} configurations, {len(manifest)} input files')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    build(parser.parse_args().root)

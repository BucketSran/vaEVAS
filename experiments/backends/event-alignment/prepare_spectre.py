"""Prepare Spectre input decks locally; never dispatch a simulator."""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

def num(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('invalid finite numeric setting')
    return format(value,'.17g')
def ident(value):
    if not isinstance(value,str) or not re.fullmatch('[A-Za-z_][A-Za-z_0-9]*',value):raise ValueError('unsafe Spectre identifier')
    return value
def deck(case,profile):
    ports=[ident(n) for n in case['ports']];ground=ident(case['ground_port'])
    nodes=[ident(n) for n in case['voltage_nodes']]
    if ground not in ports or any(n not in ports or n==ground for n in nodes):raise ValueError('node/port mismatch')
    stop=case['stop'];num(stop)
    times=case['times']
    if stop<=0 or not times or times[0]!=0 or times[-1]!=stop or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('invalid query domain')
    if any(not 0<=float(num(t))<=stop for t in times):raise ValueError('invalid strobe time')
    if set(profile)!={'id','reltol','vabstol','iabstol','maxstep'}:raise ValueError('unknown/missing profile fields')
    if any(float(num(profile[k]))<=0 for k in ('reltol','vabstol','iabstol','maxstep')):raise ValueError('nonpositive solver setting')
    settings=case['settings']
    if settings['strobeoutput']!='all' or settings['save_all_named_outputs'] is not True:raise ValueError('must retain native records and all declared outputs')
    lines=['simulator lang=spectre','ahdl_include "dut.va"']
    for index,(node,points) in enumerate(case['inputs'].items()):
        ident(node)
        if node not in ports or node==ground or not points or points[0][0]!=0 or points[-1][0]<stop or any(b[0]<=a[0] for a,b in zip(points,points[1:])):raise ValueError('invalid PWL source')
        wave=' '.join(num(x) for pair in points for x in pair)
        lines.append(f'V{index} ({node} 0) vsource type=pwl wave=[{wave}]')
    lines.append('Xdut ('+' '.join('0' if p==ground else p for p in ports)+') '+ident(case['module']))
    lines.append('simulatorOptions options '+' '.join(k+'='+num(profile[k]) for k in ('reltol','vabstol','iabstol'))+' precision="%24.17g" saveahdlvars=allwithnodes')
    lines.append('tran tran stop='+num(stop)+' maxstep='+num(profile['maxstep'])+' method=traponly strobeoutput=all strobetimes=['+' '.join(num(t) for t in times)+']')
    lines.append('save '+' '.join(dict.fromkeys([*case['inputs'],*nodes])))
    return '\n'.join(lines)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_dir', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    case = json.loads((args.case_dir/'case.json').read_text())
    model = (args.case_dir/'dut.va').read_bytes()
    prepared = [(profile, deck(case, profile)) for profile in case['settings']['spectre_profiles']]
    args.output.mkdir(parents=True, exist_ok=False)
    for profile, text in prepared:
        target = args.output/ident(profile['id'])
        target.mkdir()
        (target/'dut.va').write_bytes(model)
        (target/'tb.scs').write_text(text)
        (target/'PROFILE.json').write_text(json.dumps(profile, indent=2)+'\n')
    files = {str(p.relative_to(args.output)): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size} for p in sorted(args.output.rglob('*')) if p.is_file()}
    (args.output/'MANIFEST.json').write_text(json.dumps({'status':'prepared_not_executed','files':files}, indent=2)+'\n')


if __name__ == '__main__':
    main()

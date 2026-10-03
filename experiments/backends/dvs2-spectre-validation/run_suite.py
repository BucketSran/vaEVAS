"""31-condition Spectre verification input builder; no simulator-derived answers."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'experiments/archive/dvs2-starter-pilot'))
import suite as v1
T = v1.T
PROFILES = copy.deepcopy(v1.PROFILES)


def pulse(roots, high_until=.25, low_at=.35, initial_high=False):
    points = [(0, 1 if initial_high else 0)]
    if initial_high:
        points += [(.1, 1), (.2, 0)]
    for r in roots:
        points += [(r-.1, 0), (r+.1, 1), (r+high_until, 1), (r+low_at, 0)]
    if points[-1][0] < 4:
        points.append((4, 0))
    return points


def reset(initial_high=False):
    return ([(0, 1), (1.1, 1), (1.2, 0)] if initial_high else [(0, 0)]) + [
        (2.1, 0), (2.2, 1), (2.8, 1), (2.9, 0), (4, 0)]


def instance(name, module, ports, **params):
    return dict(name=name, module=module, ports=ports, params=params)


def conditions():
    result = []
    for old in v1.conditions():
        c = copy.deepcopy(old)
        c.update(kind='v1', stop_x=4, source_cards=[c['card']])
        if c['id'] == 'v6-main':
            c['id'] = 'v6-standard'
            c['source_cards'] = ['d2_v6_01_standard']
            c['revision_of'] = 'v6-main; only standard array literal spelling changed'
        result.append(c)

    def add(name, card, kind, inputs, outputs, instances, sources=None, **extra):
        result.append(dict(id=name, card=card, kind=kind, inputs=inputs, outputs=outputs,
                           instances=instances, source_cards=sources or [card], stop_x=4, **extra))

    for name, delta, slope in [('e1-aligned', 0, 2), ('e1-shifted', .000037, 2), ('e1-slow', 0, .5)]:
        points = [(0, .4)]
        for r, a, b in [(.5+delta,.4,.6),(1.5+delta,.6,.4),(2.5+delta,.4,.6)]:
            points += [(r-.1/slope, a), (r+.1/slope, b)]
        points.append((3, .6))
        add(name, 'n_v3_02', 'e1', {'vin':points}, ['up','down'],
            [instance('dut','dvs_event_counts',['vin','up','down','0'])], delta=delta, slope=slope)
        result[-1]['stop_x'] = 3
    for name in ['e2-low', 'e2-clock-high', 'e2-reset-high']:
        add(name, 'n_v4_02', 'e2',
            {'vin':[(0,.8),(4,.4)], 'clk':pulse([.5,1.5,2.5,3.5], initial_high=name=='e2-clock-high'),
             'rst':reset(name=='e2-reset-high')}, ['vout'],
            [instance('dut','dvs_sampler',['vin','clk','rst','vout','0'])])
    for name in ['c1-main', 'c1-swapped', 'c1-no-reset-a']:
        instances = [instance('sampler_a','dvs_sampler',['vina','clka','rsta','outa','0']),
                     instance('sampler_b','dvs_sampler',['vinb','clkb','rstb','outb','0'],initial_value=.3,edge_time=40e-9)]
        if name == 'c1-swapped': instances.reverse()
        add(name, 'n_v7_03', 'c1',
            {'vina':[(0,.8),(4,.4)],'clka':pulse([.5,1.5,2.5,3.5]),
             'rsta':[(0,0),(4,0)] if name=='c1-no-reset-a' else reset(),
             'vinb':[(0,.2),(4,.6)],'clkb':pulse([.75,1.75,2.75,3.75],.15,.25),
             'rstb':[(0,0),(4,0)]}, ['outa','outb'], instances, sources=['n_v4_02'])
    add('c2-main', 'n_v7_04', 'c2',
        {'vin':[(0,0),(1,0),(2,.6),(4,.6)],'clk':pulse([1.5,2.5,3.5]),'rst':[(0,0),(4,0)]},
        ['z','vout'], [instance('filter','dvs_v6',['vin','z','0']),
                      instance('sampler','dvs_sampler',['z','clk','rst','vout','0'])],
        sources=['d2_v6_01_standard','n_v4_02'])
    for name in ['d1-free', 'd1-reset']:
        add(name, 'n_v6_02', 'd1', {'vin':[(0,.2),(4,-.2)], 'rst':[(0,0),(4,0)] if name=='d1-free'
            else [(0,0),(1.4,0),(1.6,1),(2.4,1),(2.6,0),(4,0)]}, ['vout','flag'],
            [instance('dut','dvs_integrator',['vin','rst','vout','flag','0'])])
    for name, alpha in [('d2-constant',0), ('d2-chirp',.25)]:
        add(name,'n_v6_03','d2', {'fcode':[(0,.5),(4,.5+4*alpha)]}, ['accumulated','wrapped','vout'],
            [instance('dut','dvs_phase',['fcode','accumulated','wrapped','vout','0'])], alpha=alpha)
    for name in ['s1-default','s1-override']:
        params = {} if name=='s1-default' else dict(g1=-.5,g2=2,bias=-.25)
        add(name,'n_v1_02','s1', {'u':[(0,0),(1,.4),(2,.4),(3,-.2),(4,-.2)],
                               'v':[(0,-.2),(1,-.2),(2,.3),(3,.3),(4,-.1)]}, ['vout'],
            [instance('dut','dvs_sum',['u','v','vout','0'], **params)])
    assert len(result) == 31 and len({c['id'] for c in result}) == 31
    for c in result:
        for points in c['inputs'].values():
            assert points[0][0] == 0 and points[-1][0] == c['stop_x']
            assert all(a[0] < b[0] for a,b in zip(points,points[1:]))
    return result


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
    dependencies += [ROOT/'experiments/archive/dvs2-history-validation'/name for name in ['history.py','recheck.py']]
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

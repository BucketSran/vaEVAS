"""The maintained 31-condition DVS scientific inputs, without backend tools."""
import copy
from . import legacy as v1

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

"""Physical stimuli and independent mathematical answers for the DVS-2 pilot.

Time is seconds and voltage is volts outside normalized oracle calculations.
No simulator output or legacy benchmark checker supplies the reference.
"""
from bisect import bisect_right
import math

T = 1e-6
STOP = 4*T
PROFILES = {
    'base': {'step': 1e-9, 'reltol': 1e-5, 'vabstol': 1e-8, 'iabstol': 1e-12},
    'fine': {'step': 1e-10, 'reltol': 1e-6, 'vabstol': 1e-9, 'iabstol': 1e-13},
}


def pwl(points, t):
    x = t/T
    if x <= points[0][0]:
        return points[0][1]
    if x >= points[-1][0]:
        return points[-1][1]
    i = bisect_right([p[0] for p in points], x)-1
    a, b = points[i:i+2]
    return a[1] + (b[1]-a[1])*(x-a[0])/(b[0]-a[0])


def conditions():
    result = []

    def add(name, card, module, inputs, outputs, instances=None, **extra):
        result.append(dict(id=name, card=card, module=module, inputs=inputs,
                           outputs=outputs, instances=instances or [
                               {'name':'dut', 'ports':list(inputs)+outputs+['0'], 'params':{}}],
                           **extra))

    add('v1-main', 'd2_v1_01', 'dvs_v1',
        {'vin':[(0,-1),(1,0),(2,1),(3,0),(4,-1)]}, ['vout'])
    for variant in ['main','reference-zero','supply-fixed','input-common-mode']:
        def values(x):
            r = 0 if variant == 'reference-zero' else x/10
            h = 1 if variant == 'supply-fixed' else 1+x/10
            d = .2-.1*x
            cm = .6 if variant == 'input-common-mode' else .3
            return {'vip':r+cm+d/2,'vin':r+cm-d/2,'vdd':r+h,'vref':r}
        inputs = {n:[(x,values(x)[n]) for x in [0,4]] for n in values(0)}
        add('v2-'+variant, 'd2_v2_01', 'dvs_v2', inputs, ['op','on'],
            [{'name':'dut','ports':['vip','vin','vdd','vref','op','on'],'params':{}}])
    add('v3-main', 'd2_v3_01', 'dvs_v3', {'vin':[(0,.1),(2,.9),(4,.1)]}, ['vout'])
    clk = sorted({(n+x,y) for n in range(4)
                  for x,y in [(0,0),(.4,0),(.6,1),(.8,1),(.9,0),(1,0)]})
    for variant, end in [('c0',1.3),('c1',1.8)]:
        add('v4-'+variant, 'd2_v4_01', 'dvs_v4',
            {'vin':[(0,.2),(4,.8)],'clk':clk,
             'rst':[(0,0),(1.1,0),(1.2,1),(end,1),(end+.1,0),(4,0)]}, ['vout'])
    add('v5-main', 'd2_v5_01', 'dvs_v5', {}, ['vout'])
    add('v6-main', 'd2_v6_01', 'dvs_v6', {'vin':[(0,0),(1,0),(2,.6),(4,.6)]}, ['vout'])
    for variant in ['main','swapped','a-half']:
        scale = .5 if variant == 'a-half' else 1
        instances = [
            {'name':'dut_a','ports':['vina','outa','0'],'params':{'gain':.5}},
            {'name':'dut_b','ports':['vinb','outb','0'],'params':{'gain':-.5}},
        ]
        if variant == 'swapped':
            instances.reverse()
        add('v7-linear-'+variant, 'd2_v7_01', 'dvs_v7_linear',
            {'vina':[(0,.2*scale),(4,.6*scale)],'vinb':[(0,.6),(4,.4)]},
            ['outa','outb'], instances)
    for cubic in [.5,2.0]:
        knots = [(x,q+cubic*q**3) for x,q in enumerate([-.5,-.25,0,.25,.5])]
        add('v7-nonlinear-'+str(cubic), 'd2_v7_02', 'dvs_v7_nonlinear',
            {'vin':knots}, ['vout'],
            [{'name':'dut','ports':['vin','vout','0'],'params':{'cubic':cubic}}], cubic=cubic)
    return result


def events(case):
    """Nominal output edge start, target, duration, allowed start offset, sample slope."""
    card = case['card']
    if card == 'd2_v3_01':
        return [(x*T,y,.05*T,0,.0005*T,0) for x,y in [(1.375,.9),(3.375,.1)]]
    if card == 'd2_v4_01':
        seq = [(x,.2+.15*x,.00004,.15/T) for x in [.5,1.5,2.5,3.5]
               if not (case['id']=='v4-c1' and x==1.5)]
        seq.append((1.15,.1,.00002,0))
        return [(x*T,y,.025*T,0,w*T,slope) for x,y,w,slope in sorted(seq)]
    if card == 'd2_v5_01':
        return [((.475+.75*n)*T, .9 if n%2==0 else .1,
                 (.2 if n%2==0 else .1)*T,-.0001*T,.0001*T,0) for n in range(5)]
    return []


def reference(case, t, offsets=None):
    card = case['card']
    u = {n:pwl(p,t) for n,p in case['inputs'].items()}
    if card == 'd2_v1_01':
        return {'vout': max(-.75,min(.875,1.5*u['vin']+.125))}
    if card == 'd2_v2_01':
        cm = (u['vdd']+u['vref'])/2
        d = u['vip']-u['vin']
        return {'op':cm+d,'on':cm-d}
    if card in ['d2_v3_01','d2_v4_01','d2_v5_01']:
        old = .1
        for i,(start,target,duration,lo,hi,slope) in enumerate(events(case)):
            offset = 0 if offsets is None else offsets[i]
            start += offset
            target += slope*offset
            if t < start:
                return {'vout':old}
            if t < start+duration:
                return {'vout':old+(target-old)*(t-start)/duration}
            old = target
        return {'vout':old}
    if card == 'd2_v6_01':
        x=t/T
        def ramp(z):
            return 0 if z<=0 else z+.5*math.expm1(-2*z)
        return {'vout':.6*(ramp(x-1)-ramp(x-2))}
    if card == 'd2_v7_01':
        return {'outa':2*u['vina'],'outb':u['vinb']/1.5}
    if card == 'd2_v7_02':
        # Monotone bracket: after 55 iterations the reference interval is < 6e-17 V.
        lo,hi=-1.,1.
        for _ in range(55):
            mid=(lo+hi)/2
            if mid+case['cubic']*mid**3 < u['vin']: lo=mid
            else: hi=mid
        return {'vout':(lo+hi)/2}
    raise ValueError(card)


def netlists(case, profile):
    p=PROFILES[profile]
    signals=list(case['inputs'])+case['outputs']
    spice=[];scs=[]
    for name,points in case['inputs'].items():
        wave=' '.join(f'{x*T:.17g} {y:.17g}' for x,y in points)
        spice.append(f'V{name} {name} 0 PWL({wave})')
        scs.append(f'V{name} ({name} 0) vsource type=pwl wave=[{wave}]')
    gc=['load mgsim','load ./dut.so','verilog']
    ng=[]
    for i,inst in enumerate(case['instances']):
        ports=inst['ports'];params=inst['params'];module=case['module']
        values=' '.join(f'{k}={v:.17g}' for k,v in params.items())
        scs.append(f"{inst['name']} ({' '.join(ports)}) {module} {values}")
        ng.extend([f"N{i} {' '.join(ports)} model{i}",f'.model model{i} {module} {values}'])
        override=(' #('+', '.join(f'.{k}({v:.17g})' for k,v in params.items())+')') if params else ''
        gc.append(f"\\{module}{override} {inst['name']}({','.join(ports)});")
    steps=f"{p['step']:.17g} {STOP:.17g} 0 {p['step']:.17g}"
    opt=f"reltol={p['reltol']:.17g} vntol={p['vabstol']:.17g} abstol={p['iabstol']:.17g}"
    scs_text=('simulator lang=spectre\nahdl_include "dut.va"\n'+ '\n'.join(scs)+
        f"\nsimulatorOptions options reltol={p['reltol']:.17g} vabstol={p['vabstol']:.17g} iabstol={p['iabstol']:.17g}\n"+
        f"tran tran stop={STOP:.17g} step={p['step']:.17g} maxstep={p['step']:.17g} method=traponly\n"+
        'save '+' '.join(signals)+'\n')
    ng_text=('DVS-2 '+case['id']+'\n'+'\n'.join(spice+ng)+f'\n.options {opt} method=trap\n'+
        '.control\npre_osdi dut.osdi\nset filetype=ascii\nset wr_singlescale\nset wr_vecnames\nset numdgt=16\n'+
        f'tran {steps}\nwrdata waveform.txt '+' '.join('v('+s+')' for s in signals)+'\nquit\n.endc\n.end\n')
    gc_text=('\n'.join(gc+['spice']+spice)+f'\n.options numdgt=16 {opt}\n.options\n'+
        '.print tran '+' '.join('v('+s+')' for s in signals)+f'\n.tran {steps} > waveform.txt\n.end\n')
    return {'tb.scs':scs_text,'tb.cir':ng_text,'tb.gc':gc_text}

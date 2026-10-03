"""Frozen absdelay/slew comparisons against explicit rational PWL contracts."""
import argparse
from collections import Counter
from fractions import Fraction as Q
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'evas/src'), str(ROOT/'experiments/backends/dvs2-spectre-validation')]
from cross_touch import Instance, compile_sources, transient, digest, dump, verify, read_waveform
from timer_reference import run_spectre

UNIT = 2.0**-30
TARGET = 1e-3
INPUT_TARGET = 1e-7
PROFILES = dict(base=dict(step=.5, reltol=1e-5, vabstol=1e-8),
                fine=dict(step=1/32, reltol=1e-7, vabstol=1e-10))


def specs():
    ramp = [[0,-1],[4,1],[10,1]]
    reversal = [[0,0],[2,4],[4,-4],[8,-4]]
    reverse_answer = [[0,0],['12/5','12/5'],['28/5',-4],[8,-4]]
    cases = []
    def add(name, family, inputs, calls, answers, stop=8, unit=UNIT):
        cases.append(dict(name=name, family=family, inputs=inputs, calls=calls, answers=answers, stop_x=stop, unit=unit))
    add('ad-ramp','absdelay',dict(u=ramp),dict(y='absdelay(V(u),3*U)'),
        dict(y=[[0,-1],[3,-1],[7,1],[10,1]]),10)
    add('ad-zero','absdelay',dict(u=ramp),dict(y='absdelay(V(u),0)'),dict(y=ramp),10)
    add('ad-after-stop','absdelay',dict(u=ramp),dict(y='absdelay(V(u),12*U)'),
        dict(y=[[0,-1],[10,-1]]),10)
    add('ad-affine-reference','absdelay',dict(u=[[0,3],[2,5],[8,5]],v=[[0,1],[1,1],[8,1]],r=[[0,2],[8,2]]),
        dict(y='2+absdelay(2*V(u,r)+V(v,r)+1,U)'),dict(y=[[0,4],[1,4],[3,8],[8,8]]))
    add('ad-call-isolation','absdelay',dict(u=ramp),dict(y='absdelay(V(u),U)',z='absdelay(-V(u),2*U)'),
        dict(y=[[0,-1],[1,-1],[5,1],[10,1]],z=[[0,1],[2,1],[6,-1],[10,-1]]),10)
    add('ad-fraction-gain','absdelay',dict(u=[[0,0],[3,1],[8,1]]),dict(y='32*absdelay(V(u),U)'),
        dict(y=[[0,0],[1,0],[4,32],[8,32]]))
    add('sl-catch','slew',dict(u=[[0,0],[2,4],[8,4]]),dict(y='slew(V(u),1/U,-2/U)'),
        dict(y=[[0,0],[4,4],[8,4]]))
    add('sl-reverse','slew',dict(u=reversal),dict(y='slew(V(u),1/U,-2/U)'),dict(y=reverse_answer))
    add('sl-tracking','slew',dict(u=[[0,-1],[4,0],[8,0]]),dict(y='slew(V(u),1/U,-2/U)'),
        dict(y=[[0,-1],[4,0],[8,0]]))
    add('sl-reflected','slew',dict(u=[[t,-v] for t,v in reversal]),dict(y='slew(V(u),2/U,-1/U)'),
        dict(y=[[0,0],['12/5','-12/5'],['28/5',4],[8,4]]))
    add('sl-affine-reference','slew',dict(u=[[0,3],[2,5],[8,5]],v=[[0,1],[1,1],[8,1]],r=[[0,2],[8,2]]),
        dict(y='2+slew(2*V(u,r)+V(v,r)+1,1/U,-2/U)'),dict(y=[[0,4],[4,8],[8,8]]))
    add('sl-corner-catch','slew',dict(u=[[0,0],[2,4],[4,4],[6,2],[8,2]]),dict(y='slew(V(u),1/U,-2/U)'),
        dict(y=[[0,0],[4,4],[6,2],[8,2]]))
    add('sl-equal-rate','slew',dict(u=[[0,0],[2,2],[4,-2],[8,-2]]),dict(y='slew(V(u),1/U,-2/U)'),
        dict(y=[[0,0],[2,2],[4,-2],[8,-2]]))
    add('sl-time-scale','slew',dict(u=reversal),dict(y='slew(V(u),1/U,-2/U)'),dict(y=reverse_answer),unit=2.0**-20)
    return [dict(c, id=c['name']+'-'+profile, profile=profile, maxstep=p['step']*c['unit'],
                 stop=c['stop_x']*c['unit'], settings=p,
                 output_times=[i*c['unit']/16 for i in range(c['stop_x']*16+1)])
            for c in cases for profile,p in PROFILES.items()]


def source(c):
    ports = [*c['inputs'], *c['calls']]
    return ('`include "disciplines.vams"\nmodule probe('+','.join(ports)+');\ninput '+','.join(c['inputs'])+
            '; output '+','.join(c['calls'])+';\nelectrical '+','.join(ports)+';\n'+
            f'parameter real U={c["unit"]!r};\nanalog begin\n'+
            '\n'.join('V('+n+')<+'+e+';' for n,e in c['calls'].items())+'\nend endmodule\n')


def interpolate(points, x):
    x = Q(x)
    if x <= Q(points[0][0]): return Q(points[0][1])
    for (a,y),(b,z) in zip(points,points[1:]):
        a,y,b,z = map(Q,[a,y,b,z])
        if x <= b: return y+(z-y)*(x-a)/(b-a)
    return Q(points[-1][1])


def check(c, rows):
    required = {'time', *c['inputs'], *c['calls']}
    if len(rows)<3 or any(not required.issubset(r) or any(not math.isfinite(r[n]) for n in required) for r in rows):
        raise ValueError('missing/nonfinite observations')
    if abs(rows[0]['time'])>1e-20 or abs(rows[-1]['time']-c['stop'])>32*math.ulp(c['stop']):
        raise ValueError('incomplete extent')
    if any(b['time']<=a['time'] for a,b in zip(rows,rows[1:])):
        raise ValueError('nonincreasing times')
    seen = {round(r['time']/(c['unit']/16)) for r in rows
            if abs(r['time']-round(r['time']/(c['unit']/16))*(c['unit']/16)) <= 32*math.ulp(r['time'])}
    if not set(range(len(c['output_times']))).issubset(seen):
        raise ValueError('missing common-grid observations')
    errors = {n:0.0 for n in c['calls']}
    input_errors = {n:0.0 for n in c['inputs']}
    worst = {}
    for r in rows:
        x = Q(r['time'])/Q(c['unit'])
        for group, values in [(c['inputs'],input_errors),(c['answers'],errors)]:
            for n, points in group.items():
                err = float(abs(Q(r[n])-interpolate(points,x)))
                if err>values[n]:
                    values[n] = err
                    if n in errors: worst[n] = dict(time_s=r['time'], actual_v=r[n], expected_v=float(interpolate(points,x)))
    status = ('observation_invalid' if any(v>INPUT_TARGET for v in input_errors.values()) else
              'observed_violation' if any(v>TARGET for v in errors.values()) else 'observations_within_targets')
    return dict(status=status, points=len(rows), common_grid_points=len(c['output_times']),
                max_error_v=errors, worst=worst, input_max_error_v=input_errors, target_v=TARGET,
                formal_qualification=False)


def build(root):
    root.mkdir(parents=True,exist_ok=False)
    cases = specs()
    dump(root/'conditions.json',cases)
    dump(root/'contract.json',dict(max_spectre_attempts=len(cases), timeout_s=90, license_timeout_s=30,
         output_target_v=TARGET, input_target_v=INPUT_TARGET, common_grid='U/16, all accepted Spectre points retained',
         expectation='Explicit rational PWL vertices fixed before execution; AD and SL candidate math contracts.',
         formal_qualification=False, limits='Finite development observations; no certified export uncertainty or speed comparison. Zero delay is an explicit EVAS extension.'))
    for c in cases:
        work = root/c['id']; work.mkdir()
        (work/'probe.va').write_text(source(c))
        lines = ['simulator lang=spectre','ahdl_include "probe.va"']
        for n,points in c['inputs'].items():
            wave = ' '.join(f'{t*c["unit"]!r} {v!r}' for t,v in points)
            lines.append(f'V{n} ({n} 0) vsource type=pwl wave=[{wave}]')
        ports = [*c['inputs'],*c['calls']]
        lines += ['Xdut ('+' '.join(ports)+') probe',
                  f'simulatorOptions options reltol={c["settings"]["reltol"]!r} vabstol={c["settings"]["vabstol"]!r} iabstol=1e-14',
                  f'tran tran stop={c["stop"]!r} step={c["maxstep"]!r} maxstep={c["maxstep"]!r} method=traponly strobeperiod={c["unit"]/16!r} strobeoutput=all',
                  'save '+' '.join(ports)]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    deps = [Path(__file__), Path(__file__).with_name('test_operators.py')]
    deps += [ROOT/'experiments/backends/dvs2-spectre-validation'/n for n in ['cross_touch.py','timer_reference.py','remote.py','report.py']]
    deps += [ROOT/'experiments/archive/dvs2-starter-pilot'/n for n in ['analyze.py','suite.py']]
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in deps})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel,backend,family):
    verify(root)
    dump(root/(backend+'-started.json'),dict(kernel_sha256=digest(kernel), family=family,
         source_sha256={str(p.relative_to(ROOT)):digest(p) for p in (ROOT/'evas/src').rglob('*.py')}))
    for c in json.loads((root/'conditions.json').read_text()):
        if family and c['family']!=family: continue
        work=root/c['id']
        try:
            ports = [*c['inputs'],*c['calls']]
            program=compile_sources({'probe.va':(work/'probe.va').read_text()},[Instance('dut','probe',dict(zip(ports,ports)))])
            result=transient(program,{n:[[t*c['unit'],v] for t,v in points] for n,points in c['inputs'].items()},
                             c['output_times'],stop=c['stop'],max_step=c['maxstep'],kernel=kernel,
                             vabstol=c['settings']['vabstol'],reltol=c['settings']['reltol'])
            dump(work/(backend+'.json'),result)
            print(backend,c['id'],'ok',flush=True)
        except Exception as error:
            dump(work/(backend+'-failure.json'),dict(type=type(error).__name__,error=str(error)))
            print(backend,c['id'],str(error),flush=True)


def analyze(root, output):
    verify(root); records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        for backend in ['evas','spectre']+(['evas-pr14'] if c['family']=='absdelay' else []):
            work=root/c['id']; r=dict(case=c['id'],family=c['family'],profile=c['profile'],backend=backend)
            try:
                if backend.startswith('evas'):
                    if (work/(backend+'-failure.json')).exists(): raise ValueError((work/(backend+'-failure.json')).read_text())
                    path=work/(backend+'.json'); result=json.loads(path.read_text())
                    rows=[dict(time=t,**dict(zip(result['nodes'],s['voltages'],strict=True)))
                          for t,s in zip(result['transient']['times'],result['solutions'],strict=True)]
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']: raise ValueError('execution failure')
                    path=work/'psf/tran.tran.tran'; rows=read_waveform(path,'spectre')
                r.update(waveform_sha256=digest(path),**check(c,rows))
            except (OSError,ValueError,KeyError) as error:
                r.update(status='unavailable_or_invalid',reason=str(error))
            records.append(r)
    dump(output,dict(records=records,summary={b:dict(Counter(r['status'] for r in records if r['backend']==b))
         for b in ['evas','evas-pr14','spectre']},formal_qualification=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','evas','spectre','check'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--kernel',type=Path)
    p.add_argument('--spectre-profile',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--backend',default='evas');p.add_argument('--family',choices=['absdelay','slew'])
    a=p.parse_args()
    if a.action=='build':build(a.root)
    elif a.action=='evas':run_evas(a.root,a.kernel,a.backend,a.family)
    elif a.action=='spectre':run_spectre(a.root,a.spectre_profile)
    else:analyze(a.root,a.output)

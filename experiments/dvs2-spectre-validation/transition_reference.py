"""Bounded transition comparison against explicit, independently derived PWL anchors.

Finite observations only. No simulator is used as another simulator's oracle.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import subprocess

from cross_touch import ROOT, Instance, compile_sources, digest, dump, read_waveform, transient, verify
from timer_reference import run_spectre

UNIT = 2.0**-30
TTOL = UNIT/1024
VOLTAGE_ALLOWANCE = 1e-8
PORTS = ['u','y','q','h1','h2','p','r']


def cases():
    # Times are in UNIT. These knots are hand-derived, not EVAS-produced values.
    specs = [
        dict(name='ordinary', initial=.25, times=[2,16], changes=[.75,-1],
             delay=2, rise=4, fall=8, knots=[[0,.25],[4,.25],[8,1],[18,1],[26,0],[32,0]]),
        dict(name='reverse', initial=0, times=[2,6], changes=[1,-1],
             delay=0, rise=10, fall=20, knots=[[0,0],[2,0],[6,.4],[14,0],[32,0]]),
        dict(name='extend', initial=0, times=[2,6], changes=[1,1],
             delay=0, rise=10, fall=20, knots=[[0,0],[2,0],[6,.4],[14,2],[32,2]]),
        dict(name='reverse-negative', initial=0, times=[2,6], changes=[-1,1],
             delay=0, rise=20, fall=10, knots=[[0,0],[2,0],[6,-.4],[14,0],[32,0]]),
        dict(name='extend-negative', initial=0, times=[2,6], changes=[-1,-1],
             delay=0, rise=20, fall=10, knots=[[0,0],[2,0],[6,-.4],[14,-2],[32,-2]]),
        dict(name='delay-pulse', initial=0, times=[2,3], changes=[1,-1],
             delay=10, rise=2, fall=2, knots=[[0,0],[12,0],[13,.5],[14,0],[32,0]]),
        dict(name='repeat', initial=0, times=[2,6], changes=[1,0],
             delay=0, rise=10, fall=10, knots=[[0,0],[2,0],[12,1],[32,1]]),
        dict(name='voltage-target', initial=0, times=[4], changes=[1],
             delay=0, rise=4, fall=4, knots=[[0,0],[4,0],[8,1],[32,1]]),
    ]
    return [dict(s,id=s['name']+'-'+profile,profile=profile,maxstep=step*UNIT,
                 stop=32*UNIT,output_times=[i*UNIT/8 for i in range(257)],
                 inputs={'u':[[0,0],[32*UNIT,32]]})
            for s in specs for profile,step in [('coarse',3),('fine',.125)]]


def source(c):
    if c['name']=='voltage-target':
        events=f'''@(timer({4*UNIT!r},0,{TTOL!r})) n=1;
          @(timer({4*UNIT!r},0,{TTOL!r})) begin a=V(p,r); stamp1=V(u,r); end'''
    else:
        events='\n'.join(f'@(timer({t*UNIT!r},0,{TTOL!r})) begin {var}={delta}; stamp{i}=V(u,r); end'
                         for i,(var,t,delta) in enumerate(zip(['a','b'],c['times'],c['changes']),1))
    return f'''`include "disciplines.vams"
module probe(u,y,q,h1,h2,p,r); input u; output y,q,h1,h2,p; inout r;
electrical u,y,q,h1,h2,p,r; real a,b,stamp1,stamp2; integer n;
analog begin
 @(initial_step) begin a=0; b=0; stamp1=-1; stamp2=-1; n=0; end
 {events}
 V(q,r)<+{c['initial']}+a+b; V(p,r)<+n; V(h1,r)<+stamp1; V(h2,r)<+stamp2;
 V(y,r)<+transition({c['initial']}+a+b,{c['delay']*UNIT!r},{c['rise']*UNIT!r},{c['fall']*UNIT!r});
end endmodule
'''


def instance():
    return Instance('dut','probe',connections={p:('0' if p=='r' else p) for p in PORTS})


def expected(c,t):
    for (a,y0),(b,y1) in zip(c['knots'],c['knots'][1:]):
        if t<=b:
            return y0+(y1-y0)*(t-a)/(b-a)
    return c['knots'][-1][1]


def check(c,rows,require_grid=False):
    if len(rows)<3 or abs(rows[0]['time'])>1e-20 or abs(rows[-1]['time']-c['stop'])>1e-20:
        raise ValueError('incomplete trace')
    if any(b['time']<a['time'] for a,b in zip(rows,rows[1:])):
        raise ValueError('unordered trace')
    # Two independently located input changes affect the interruption value and
    # its start time. 4*eta*max_slope conservatively covers these frozen cases.
    slope=max(abs((b[1]-a[1])/(b[0]-a[0])) for a,b in zip(c['knots'],c['knots'][1:]))
    allowance=VOLTAGE_ALLOWANCE+4*TTOL/UNIT*slope
    worst=0.0
    for row in rows:
        t=row['time']/UNIT
        if not all(__import__('math').isfinite(v) for v in row.values()):
            raise ValueError('nonfinite observation')
        worst=max(worst,abs(row['y']-expected(c,t)))
        if any(abs(t-e)<=2*TTOL/UNIT for e in c['times']):
            continue  # Discrete monitor transitions have a declared time window.
        q=c['initial']+sum(d for e,d in zip(c['times'],c['changes']) if t>e)
        if abs(row['q']-q)>VOLTAGE_ALLOWANCE:
            raise ValueError('wrong held target')
        for i in [1,2]:
            active=i<=len(c['times']) and t>c['times'][i-1]
            value=c['times'][i-1] if active else -1
            bound=TTOL/UNIT+VOLTAGE_ALLOWANCE if active else VOLTAGE_ALLOWANCE
            if abs(row['h'+str(i)]-value)>bound:
                raise ValueError('wrong event timestamp or held stamp')
    if worst>allowance:
        raise ValueError(f'waveform error {worst:.9g} exceeds {allowance:.9g} V')
    # Require an observation inside every nonflat expected segment.
    for (a,y0),(b,y1) in zip(c['knots'],c['knots'][1:]):
        if y0!=y1 and not any(a<r['time']/UNIT<b for r in rows):
            raise ValueError('unobserved edge segment')
    if require_grid and any(not any(abs(r['time']-t)<=32*math.ulp(t) for r in rows)
                            for t in c['output_times']):
        raise ValueError('missing common observation time')
    return dict(points=len(rows),max_error_v=worst,conditional_allowance_v=allowance,
                common_grid_points=len(c['output_times']) if require_grid else None,
                status='finite_consistent',formal_qualification=False)


def build(root, strobe=False):
    root.mkdir(parents=True,exist_ok=False)
    dump(root/'conditions.json',cases())
    dump(root/'contract.json',dict(max_spectre_attempts=16,timeout_s=90,license_timeout_s=30,
         timer_tolerance_s=TTOL,voltage_allowance_v=VOLTAGE_ALLOWANCE,
         reference='Explicit PWL knots derived from LRM 2.4 section 4.5.8; voltage-target uses reviewed EVAS same-time contract.',
         observation='Check every exported point; held targets and stamps checked outside event windows. Compare each backend independently. Coarse/fine maxstep. '+('Spectre strobes on the EVAS output grid, retaining all accepted points.' if strobe else 'No forced Spectre strobes.'),
         strobeperiod_s=UNIT/8 if strobe else None, strobeoutput='all' if strobe else None,
         limits='Finite development observations, conditional export allowance, no continuous-time qualification or speed ranking. Nominal waveform allowance is 4*timer_tolerance*maximum_reference_slope + 1e-8 V.'))
    for c in cases():
        work=root/c['id']; work.mkdir(); (work/'probe.va').write_text(source(c))
        (work/'tb.scs').write_text('\n'.join(['simulator lang=spectre','ahdl_include "probe.va"',
            f'Vu (u 0) vsource type=pwl wave=[0 0 {c["stop"]!r} 32]',
            'Xdut (u y q h1 h2 p 0) probe',
            'simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
            f'tran tran stop={c["stop"]!r} step={c["maxstep"]!r} maxstep={c["maxstep"]!r} method=traponly'+(f' strobeperiod={UNIT/8!r} strobeoutput=all' if strobe else ''),
            'save u y q h1 h2 p'])+'\n')
    deps=[Path(__file__),Path(__file__).with_name('test_transition_reference.py'),
          *[Path(__file__).with_name(n+'.py') for n in ['timer_reference','cross_touch','remote','report']],
          *[ROOT/'experiments/dvs2-starter-pilot'/n for n in ['analyze.py','suite.py']]]
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in deps})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        kernel_sha256=digest(kernel),source_sha256={str(p.relative_to(ROOT)):digest(p)
        for directory,pattern in [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')]
        for p in directory.rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        try:
            p=compile_sources({'probe.va':(work/'probe.va').read_text()},[instance()])
            result=transient(p,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],
                             kernel=kernel,reltol=1e-8,vabstol=1e-10)
            dump(work/'evas.json',result)
        except Exception as error:
            dump(work/'evas-failure.json',dict(error=str(error)))


def analyze(root,output):
    verify(root)
    require_grid=json.loads((root/'contract.json').read_text()).get('strobeperiod_s') is not None
    records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        for backend in ['evas','spectre']:
            work=root/c['id']; record=dict(case=c['id'],backend=backend)
            try:
                if backend=='evas':
                    path=work/'evas.json'; result=json.loads(path.read_text())
                    rows=[dict(time=t,**{n:row['voltages'][i] for i,n in enumerate(result['nodes']) if n!='0'})
                          for t,row in zip(result['transient']['times'],result['solutions'],strict=True)]
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']: raise ValueError('execution failure')
                    path=work/'psf/tran.tran.tran'; rows=read_waveform(path,'spectre')
                record.update(waveform_sha256=digest(path),**check(c,rows,require_grid))
            except (ValueError,KeyError,OSError) as error:
                record.update(status='finite_inconsistent_or_unavailable',reason=str(error))
            records.append(record)
    dump(output,dict(input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),records=records,
         summary={b:dict(Counter(r['status'] for r in records if r['backend']==b)) for b in ['evas','spectre']},
         formal_qualification=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('action',choices=['build','evas','spectre','check'])
    p.add_argument('--root',type=Path,required=True); p.add_argument('--kernel',type=Path)
    p.add_argument('--spectre-profile',type=Path); p.add_argument('--output',type=Path)
    p.add_argument('--strobe',action='store_true',help='Force Spectre observations on the EVAS output grid')
    a=p.parse_args()
    if a.action=='build': build(a.root,a.strobe)
    elif a.action=='evas': run_evas(a.root,a.kernel)
    elif a.action=='spectre': run_spectre(a.root,a.spectre_profile)
    else: analyze(a.root,a.output)

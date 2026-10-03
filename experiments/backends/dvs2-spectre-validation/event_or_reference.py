"""Bounded OR and reset comparison with explicit independent event tables.

These extra probes do not change the frozen original31 denominator. Event time
windows are semantic candidates, not qualified physical observation bounds.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import json
import math
from pathlib import Path
from cross_touch import (ROOT, Instance, compile_sources, transient, digest, dump,
                         verify, read_waveform, audit_settings, pwl)
from timer_reference import run_spectre

UNIT = 2.0**-20
ALLOWANCE = 1e-8


def specifications():
    cases=[]
    for family in ['distinct','same','reversed','duplicate','nearby',
                   'reset_same','reset_active','unrelated_knots']:
        for profile,step in [('coarse',1e-7),('fine',1e-9)]:
            inputs={'u':[[0,0],[UNIT,1]],'clock':[[0,0],[UNIT,1]],
                    'reset':[[0,0],[UNIT,0]],'data':[[0,.8],[UNIT,.7]],
                    'unused':[[0,0],[UNIT,0]]}
            times=[Q(1,4),Q(3,4)] if family=='distinct' else [Q(1,2)]
            sample=[Q(0)]*len(times)
            ttol=UNIT/1024; etol=1e-8
            if family=='nearby':
                times=[Q(1,2),Q(513,1024)]; sample=[Q(0),Q(0)]
                ttol=UNIT/16; etol=.01
            if family=='reset_same':sample=[Q(1,10)]; inputs['reset']=[[0,0],[UNIT,1]]
            if family=='reset_active':
                inputs['u']=[[0,0],[UNIT/2,1],[UNIT,0]]
                inputs['reset']=[[0,1],[UNIT/2,1],[UNIT*.625,0],[UNIT,0]]
                times=[Q(1,4),Q(3,4)]; sample=[Q(1,10),Q(29,40)]
            if family=='unrelated_knots':
                inputs['u']=[[0,0]]
                inputs['unused']=[[0,0]]
                times=[Q(j*4+3,16) for j in range(4)]; sample=[Q(0)]*4
                for j in range(4):
                    inputs['u'] += [[UNIT*(j/4+Q(5,32)),0],
                                    [UNIT*(j/4+Q(7,32)),1],
                                    [UNIT*(j/4+Q(15,64)),1],[UNIT*(j+1)/4,0]]
                    inputs['unused'].append([UNIT*float(times[j]),0])
                inputs['unused'].append([UNIT,0])
            roots=[float(t)*UNIT for t in times]
            outputs=sorted({0.,UNIT,*[UNIT*i/1024 for i in range(1,1024)],
                            *[t for root in roots for t in [root-UNIT/4096,root+UNIT/4096]]})
            cases.append(dict(id=family+'-'+profile,family=family,profile=profile,
                              stop=UNIT,maxstep=step,ttol=ttol,etol=etol,inputs=inputs,
                              output_times=outputs,events=[dict(root_s=t,count=i+1,
                                  stamp=float(times[i]),sample=float(sample[i])) for i,t in enumerate(roots)]))
    return cases


def source(c):
    tol=f',{c["ttol"]!r},{c["etol"]!r}'
    cross=lambda g,d=1:'cross('+g+','+str(d)+tol+')'
    a=cross('V(u,r)-0.5'); b=cross('2*V(u,r)-1')
    family=c['family']
    if family=='distinct':a=cross('V(u,r)-0.25');b=cross('V(u,r)-0.75')
    if family=='nearby':b=cross('V(u,r)-0.5009765625')
    if family=='duplicate':b=a
    if family=='reversed':a,b=b,a
    initial='q=0;'; action='q=0;'
    if family=='reset_same':
        b=cross('V(reset,r)-0.5'); initial='q=0.1;'
        action='if(V(reset,r)>0.4) q=0.1; else q=V(data,r);'
    if family=='reset_active':
        b=cross('V(u,r)-0.5',-1);initial='q=0.1;'
        action='if(V(reset,r)>0.5) q=0.1; else q=V(data,r);'
    return '''`include "disciplines.vams"
module probe(u,clock,reset,data,unused,count,stamp,sample,r);
input u,clock,reset,data,unused; output count,stamp,sample; inout r;
electrical u,clock,reset,data,unused,count,stamp,sample,r;
integer n; real held,q;
analog begin
 @(initial_step) begin n=0; held=0; '''+initial+''' end
 @('''+a+' or '+b+''') begin n=n+1; held=V(clock,r); '''+action+''' end
 V(count,r)<+n; V(stamp,r)<+held; V(sample,r)<+q;
end
endmodule
'''


def build(root):
    root.mkdir(parents=True,exist_ok=False)
    cases=specifications();dump(root/'conditions.json',cases)
    dump(root/'contract.json',dict(max_spectre_attempts=16,timeout_s=90,license_timeout_s=30,
        formal_qualification=False,observation_allowance_v=ALLOWANCE,
        independent_answers='Explicit rational event tables; counts, sampled values and normalized stamps.',
        limits='Finite observations; no physical observation error certificate or continuous-time proof.'))
    for c in cases:
        work=root/c['id'];work.mkdir();(work/'probe.va').write_text(source(c))
        lines=['simulator lang=spectre','ahdl_include "probe.va"']
        for name,points in c['inputs'].items():
            lines.append(f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t:.17g} {v:.17g}' for t,v in points)+']')
        lines+=['Xprobe (u clock reset data unused count stamp sample 0) probe',
                'simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                'save u clock reset data unused count stamp sample']
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    dependencies=[Path(__file__),*[Path(__file__).with_name(n+'.py') for n in
                    ['test_event_or_reference','cross_touch','timer_reference','remote','report']],
                  ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py',ROOT/'experiments/archive/dvs2-starter-pilot/suite.py']
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in dependencies})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(kernel_sha256=digest(kernel),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for folder,pattern in
            [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')] for p in folder.rglob(pattern)}))
    ports='u clock reset data unused count stamp sample r'.split()
    inst=Instance('probe','probe',{p:'0' if p=='r' else p for p in ports},{})
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        try:
            program=compile_sources({'probe.va':(work/'probe.va').read_text()},[inst])
            result=transient(program,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],
                             kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(work/'evas.json',result);print(c['id'],'ok',flush=True)
        except Exception as error:
            dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['id'],type(error).__name__,str(error),flush=True)


def window(c,event):
    # Slope is 1/U for ramp guards, 2/U for triangular guards, 16/U for pulses.
    slope=(2 if c['family']=='reset_active' else 16 if c['family']=='unrelated_knots' else 1)/UNIT
    return min(c['ttol'],c['etol']/slope)


def inspect(rows,c):
    required={'time',*c['inputs'],'count','stamp','sample'}
    if not rows or any(not required<=r.keys() for r in rows):raise ValueError('missing observations')
    if any(not math.isfinite(r[k]) for r in rows for k in required):raise ValueError('nonfinite observations')
    if rows[0]['time']!=0 or abs(rows[-1]['time']-c['stop'])>1e-18:raise ValueError('incomplete observations')
    if any(not 0<b['time']-a['time']<=c['maxstep']*1.01+1e-18 for a,b in zip(rows,rows[1:])):raise ValueError('invalid time order or gap')
    violations=[];checked=0;input_error=0.;hit=[False]*(len(c['events'])+1)
    for row in rows:
        t=row['time']
        for n,points in c['inputs'].items():input_error=max(input_error,abs(row[n]-pwl(points,t)))
        if any(abs(t-e['root_s'])<=window(c,e)+1e-18 for e in c['events']):continue
        previous=[e for e in c['events'] if e['root_s']<t]
        index=len(previous);hit[index]=True
        expected=previous[-1] if previous else dict(count=0,stamp=0,sample=.1 if c['family'].startswith('reset_') else 0)
        allowance=dict(count=ALLOWANCE,stamp=ALLOWANCE+(window(c,previous[-1])/UNIT if previous else 0),
                       sample=ALLOWANCE+(.1*window(c,previous[-1])/UNIT if previous else 0))
        for n in ['count','stamp','sample']:
            if abs(row[n]-expected[n])>allowance[n]:violations.append(dict(time_s=t,node=n,observed=row[n],expected=expected[n],allowance=allowance[n]))
        checked+=1
    if input_error>ALLOWANCE:raise ValueError('input fidelity violation')
    # Wide root windows can cover the tiny middle plateau of nearby roots.
    # Require initial and terminal observations; do not claim all hidden plateaus.
    if not hit[0] or not hit[-1]:raise ValueError('missing initial or terminal plateau')
    return dict(status='observed_violation' if violations else 'observations_within_candidate_windows',
                points=len(rows),checked_points=checked,plateaus_observed=hit,input_max_error_v=input_error,
                violation_count=len(violations),first_violations=violations[:8],
                observed_terminal={n:rows[-1][n] for n in ['count','stamp','sample']},formal_qualification=False)


def analyze(root,output,backends):
    verify(root);records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        for backend in backends:
            work=root/c['id'];r=dict(configuration=c['id'],family=c['family'],profile=c['profile'],backend=backend)
            try:
                if backend=='evas':
                    if (work/'evas-failure.json').exists():raise ValueError((work/'evas-failure.json').read_text())
                    path=work/'evas.json';result=json.loads(path.read_text())
                    rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in zip(result['transient']['times'],result['solutions'])]
                    r['event_records']=result['transient']['events']
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']:raise ValueError('execution failure or timeout')
                    path=work/'psf/tran.tran.tran';rows=read_waveform(path,'spectre')
                    actual,stop=audit_settings((work/'spectre.log').read_text(),c,rows)
                    r.update(effective_settings=actual,stop_audit=stop,elapsed_s=execution['elapsed_s'])
                r.update(inspect(rows,c),waveform_sha256=digest(path))
            except (ValueError,KeyError,FileNotFoundError) as error:r.update(status='failed_or_invalid',reason=str(error))
            records.append(r)
    dump(output,dict(records=records,summary=dict(Counter(r['backend']+':'+r['status'] for r in records)),
                     input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),checker_identity=json.loads((root/'checker_identity.json').read_text()),
                     formal_qualification=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','evas','spectre','check'])
    p.add_argument('root',type=Path);p.add_argument('--kernel',type=Path);p.add_argument('--spectre-profile',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--backends',nargs='+',default=['evas','spectre'],choices=['evas','spectre'])
    a=p.parse_args()
    if a.action=='build':build(a.root)
    elif a.action=='evas':run_evas(a.root,a.kernel)
    elif a.action=='spectre':run_spectre(a.root,a.spectre_profile)
    else:analyze(a.root,a.output,a.backends)

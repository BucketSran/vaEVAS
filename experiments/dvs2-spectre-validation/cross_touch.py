"""Frozen PWL touch diagnostic: 12 configurations, 18 monitors each.

Nonzero valleys have independent analytic crossing answers. Exact-touch counts
are classified observations, not a pass/fail choice between simulator semantics.
"""
import argparse
from collections import Counter
from decimal import Decimal
from fractions import Fraction as Q
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'evas/src'))
from evas import Instance, compile_sources, transient
from remote import digest, dump, execute
# The legacy pilot also has report.py; resolve the owning helper explicitly.
_report_spec = importlib.util.spec_from_file_location('cross_touch_report', Path(__file__).with_name('report.py'))
_report = importlib.util.module_from_spec(_report_spec)
_report_spec.loader.exec_module(_report)
settings = _report.settings
sys.path.insert(0, str(ROOT/'experiments/dvs2-starter-pilot'))
from analyze import read_waveform

ALLOWANCE = 1e-8
STEPS = {'coarse': 100e-9, 'fine': 7e-9}
TOLERANCES = {'nominal': (1e-10,1e-5), 'time_tight': (1e-12,1e-5),
              'expression_tight': (1e-10,1e-7)}
VALLEYS = {'above': .501, 'touch': .5, 'below': .499}
DIRECTIONS = {'both': 0, 'rising': 1, 'falling': -1}
POLARITIES = {'pos': 1, 'neg': -1}


def monitors():
    return [dict(id=f'{valley}_{pol}_{direction}', valley=valley, polarity=p,
                 direction=d, module=f'probe_{pol}_{direction}')
            for valley in VALLEYS for pol,p in POLARITIES.items()
            for direction,d in DIRECTIONS.items()]


def specifications():
    result=[]
    for phase,shift in [('original',0.),('shifted',37e-12)]:
        center,stop=1.5e-6+shift,3e-6+shift
        inputs={name: ([[0,.6]] if shift else [])+
                [[shift,.6],[center,minimum],[stop,.6]] for name,minimum in VALLEYS.items()}
        inputs['clock']=[[0,0],[stop,stop*1e6]]
        times=sorted({0.,shift,center-20e-9,center,center+20e-9,stop,
                      *[i*.25e-6 for i in range(1,12)]})
        for profile,step in STEPS.items():
            for accuracy,(ttol,etol) in TOLERANCES.items():
                result.append(dict(id=f'{phase}-{profile}-{accuracy}',phase=phase,
                    profile=profile,accuracy=accuracy,center=center,stop=stop,
                    maxstep=step,ttol=ttol,etol=etol,inputs=inputs,output_times=times))
    return result


def model(m, case):
    return f'''`include "disciplines.vams"
module {m['module']}(u,clock,count,stamp,guard,r);
input u,clock; output count,stamp,guard; inout r;
electrical u,clock,count,stamp,guard,r;
integer n; real held,sampled;
analog begin
 @(initial_step) begin n=0; held=0; sampled=0; end
 @(cross({m['polarity']}*(V(u,r)-0.5),{m['direction']},{case['ttol']!r},{case['etol']!r})) begin
  n=n+1; held=V(clock,r); sampled={m['polarity']}*(V(u,r)-0.5);
 end
 V(count,r)<+n; V(stamp,r)<+held; V(guard,r)<+sampled;
end
endmodule
'''


def sources(case):
    return {m['module']+'.va':model(m,case) for m in monitors()}


def roots(case, m):
    """Strict nonzero crossings; exact-touch semantics deliberately excluded."""
    result=[]
    points=case['inputs'][m['valley']]
    for (t0,v0),(t1,v1) in zip(points,points[1:]):
        a,b=Q(m['polarity'])*(Q(v0)-Q(.5)),Q(m['polarity'])*(Q(v1)-Q(.5))
        if a*b >= 0: continue
        slope=(b-a)/(Q(t1)-Q(t0))
        if m['direction'] and (1 if slope>0 else -1)!=m['direction']: continue
        time=Q(t0)-a/slope
        width=min(Q(case['ttol']),Q(case['etol'])/abs(slope))
        result.append((time,width))
    return result


def pwl(points, t):
    for (t0,a),(t1,b) in zip(points,points[1:]):
        if Q(t0)<=t<=Q(t1): return Q(a)+(Q(b)-Q(a))*(t-Q(t0))/(Q(t1)-Q(t0))
    raise ValueError('time outside input domain')


def classify(counts, polarity):
    arrival=[1,0,1] if polarity==1 else [1,1,0]
    departure=[1,1,0] if polarity==1 else [1,0,1]
    if counts==[0,0,0]: return 'no_touch_event'
    if counts==arrival: return 'arrival_direction_once'
    if counts==departure: return 'departure_direction_once'
    if counts==[2,1,1]: return 'both_directions'
    return 'other'


def audit_settings(log, case, rows):
    actual=settings(log)
    requested=dict(vabstol=1e-10,iabstol=1e-14,reltol=1e-8,
                   step=case['maxstep'],maxstep=case['maxstep'],method='traponly')
    if not all(actual[k]==v if isinstance(v,str) else math.isclose(actual[k],v,rel_tol=1e-12)
               for k,v in requested.items()):
        raise ValueError('effective settings mismatch')
    # Logs round stop to a few significant digits. Check its display interval,
    # then independently require the high-precision waveform endpoint.
    units={u:Q('1e'+str(e)) for u,e in [('s',0),('ms',-3),('us',-6),('ns',-9),('ps',-12),('fs',-15)]}
    intervals=[]
    for raw in re.findall(r'^\s*stop = ([^\n]+)$',log,re.M):
        tokens=raw.split(',')[0].split(); value=Decimal(tokens[0])
        scale=units[tokens[1]] if len(tokens)>1 else Q(1)
        radius=Q(10)**value.as_tuple().exponent*scale/2
        center=Q(value)*scale; lo,hi=center-radius,center+radius
        if not lo<=Q(case['stop'])<=hi: raise ValueError('stop outside log display precision')
        intervals.append([float(lo),float(hi)])
    if not intervals or not rows or abs(rows[-1]['time']-case['stop'])>1e-18:
        raise ValueError('waveform stop mismatch')
    return actual,dict(log_stop_s=actual['stop'],requested_stop_s=case['stop'],
        waveform_stop_s=rows[-1]['time'],log_display_intervals_s=intervals,
        exact_log_match=math.isclose(actual['stop'],case['stop'],rel_tol=1e-12),
        waveform_matches_requested=True)


def inspect(rows, case):
    required={'time',*case['inputs'],*[prefix+m['id'] for m in monitors() for prefix in ['n_','t_','g_']]}
    if not rows or any(not required<=row.keys() for row in rows): raise ValueError('missing observations')
    if any(not math.isfinite(row[k]) for row in rows for k in required): raise ValueError('nonfinite observations')
    if rows[0]['time']!=0 or abs(rows[-1]['time']-case['stop'])>1e-18: raise ValueError('incomplete observations')
    if any(not 0<b['time']-a['time']<=.501e-6 for a,b in zip(rows,rows[1:])): raise ValueError('invalid time order or gap')
    for row in rows:
        for name,points in case['inputs'].items():
            if abs(Q(row[name])-pwl(points,Q(row['time'])))>Q(ALLOWANCE): raise ValueError('input mismatch')
    rate=Q(case['inputs']['clock'][-1][1])/Q(case['stop'])
    reserve=Q(ALLOWANCE)/rate
    records=[]
    for m in monitors():
        key=m['id']; expected=roots(case,m); changes=[]; seen=set(); common={}; previous=0
        record=dict(m, final_count=rows[-1]['n_'+key])
        try:
            for row in rows:
                n=round(row['n_'+key]); t=Q(row['time']); held=Q(row['t_'+key]); sampled=Q(row['g_'+key])
                if abs(row['n_'+key]-n)>ALLOWANCE or n<previous: raise ValueError('invalid count')
                if n!=previous:
                    changes.append(dict(exported_time_s=row['time'],count=n,held_clock_v=float(held),
                                        witness_time_s=float(held/rate),sampled_guard_v=float(sampled)))
                seen.add(n)
                if m['valley']!='touch':
                    earliest=sum(t>r+w+reserve for r,w in expected)
                    latest=sum(t>=r-reserve for r,w in expected)
                    if not earliest<=n<=latest: raise ValueError('count violates crossing windows')
                if not n:
                    if abs(held)>Q(ALLOWANCE) or abs(sampled)>Q(ALLOWANCE): raise ValueError('initial state changed')
                else:
                    if m['valley']=='touch':
                        points=case['inputs']['touch']
                        slopes=[abs((Q(b)-Q(a))/(Q(t1)-Q(t0))) for (t0,a),(t1,b) in zip(points,points[1:])]
                        root=Q(case['center']); width=min(Q(case['ttol']),Q(case['etol'])/max(slopes))
                    else:
                        root,width=expected[n-1]
                    witness=held/rate
                    if not root-reserve<=witness<=root+width+reserve: raise ValueError('held time outside window')
                    lo,hi=common.get(n,(root,root+width)); common[n]=max(lo,witness-reserve),min(hi,witness+reserve)
                    if common[n][0]>common[n][1]: raise ValueError('inconsistent held time')
                    if abs(sampled)>Q(case['etol'])+Q(ALLOWANCE): raise ValueError('sampled guard outside tolerance')
                previous=n
            if m['valley']!='touch' and seen!=set(range(len(expected)+1)): raise ValueError('missing count plateau')
            record['status']='diagnostic_observation' if m['valley']=='touch' else 'control_pass'
        except (ValueError,IndexError) as error:
            record.update(status='failed',reason=str(error))
        record['observed_changes']=changes
        records.append(record)
    touch={pol:classify([round(next(r['final_count'] for r in records if r['id']==f'touch_{pol}_{d}'))
                        for d in DIRECTIONS],p) for pol,p in POLARITIES.items()}
    return dict(points=len(rows),monitors=records,touch_classification=touch,
                formal_qualification=False,observation_allowance_v=ALLOWANCE)


def inspect_arrivals(rows, case):
    """Opt-in compatibility contract; the original diagnostic stays unchanged."""
    result=inspect(rows,case)
    rate=Q(case['inputs']['clock'][-1][1])/Q(case['stop'])
    reserve=Q(ALLOWANCE)/rate
    points=case['inputs']['touch']
    slopes=[abs((Q(b)-Q(a))/(Q(t1)-Q(t0))) for (t0,a),(t1,b) in zip(points,points[1:])]
    root=Q(case['center']); width=min(Q(case['ttol']),Q(case['etol'])/max(slopes))
    for record in result['monitors']:
        if record['valley']!='touch' or record['status']=='failed': continue
        expected=int(record['direction'] in [0,-record['polarity']])
        key=record['id']
        try:
            for row in rows:
                t=Q(row['time']); n=round(row['n_'+key])
                earliest=expected*int(t>root+width+reserve)
                latest=expected*int(t>=root-reserve)
                if not earliest<=n<=latest: raise ValueError('count violates isolated-zero arrival contract')
            if round(record['final_count'])!=expected: raise ValueError('missing arrival count')
            record['status']='arrival_pass'
        except ValueError as error:
            record.update(status='failed',reason=str(error))
    result['contract']='isolated-pwl-zero-arrival-v1'
    return result


def build(root):
    root.mkdir(parents=True,exist_ok=False)
    specs=specifications()
    dump(root/'conditions.json',specs)
    dump(root/'contract.json',dict(configurations=12,monitors_per_configuration=18,max_spectre_attempts=12,
        timeout_s=90,license_timeout_s=30,observation_allowance_v=ALLOWANCE,
        controls='Above: zero events. Below: two for both, one per direction, polarity reverses order.',
        touch='Classify observed counts as none, arrival, departure, both, or other; do not assume a winning semantics.',
        limits='Finite observations under assumed voltage allowance; no formal qualification or general smooth-touch claim.'))
    for c in specs:
        work=root/c['id'];work.mkdir()
        src=sources(c)
        for name,source in src.items(): (work/name).write_text(source)
        lines=['simulator lang=spectre',*[f'ahdl_include "{name}"' for name in src]]
        for name,points in c['inputs'].items():
            lines.append(f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t:.17g} {v:.17g}' for t,v in points)+']')
        for m in monitors():
            key=m['id']; lines.append(f'{key} ({m["valley"]} clock n_{key} t_{key} g_{key} 0) {m["module"]}')
        lines+=['simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                'save '+' '.join([*c['inputs'],*[prefix+m['id'] for m in monitors() for prefix in ['n_','t_','g_']]])]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    dependencies=[Path(__file__),Path(__file__).with_name('test_cross_touch.py'),Path(__file__).with_name('remote.py'),
                  Path(__file__).with_name('report.py'),ROOT/'experiments/dvs2-starter-pilot/analyze.py',ROOT/'experiments/dvs2-starter-pilot/suite.py']
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in dependencies})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def verify(root):
    root=root.resolve()
    for rel,h in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        if not (root/rel).resolve().is_relative_to(root) or digest(root/rel)!=h: raise ValueError('input drift: '+rel)
    for rel,h in json.loads((root/'checker_identity.json').read_text()).items():
        if digest(ROOT/rel)!=h: raise ValueError('checker drift: '+rel)


def run_evas(root,kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(kernel_sha256=digest(kernel),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for directory,pattern in [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')] for p in directory.rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        instances=[Instance(m['id'],m['module'],dict(u=m['valley'],clock='clock',count='n_'+m['id'],stamp='t_'+m['id'],guard='g_'+m['id'],r='0'),{}) for m in monitors()]
        try:
            program=compile_sources({p.name:p.read_text() for p in work.glob('*.va')},instances)
            result=transient(program,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(work/'evas.json',result)
            print(c['id'],'ok',flush=True)
        except Exception as error:
            dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['id'],type(error).__name__,flush=True)


def run_spectre(root,profile):
    verify(root)
    config=json.loads(profile.read_text());binary,scripts=config['spectre'],config['setup_scripts']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]): raise ValueError('unsupported tool path')
    setup='\n'.join('source '+s for s in scripts)+'\n';cpu=min(os.sched_getaffinity(0))
    dump(root/'SPECTRE_STARTED.json',dict(max_attempts=12,timeout_s=90,license_timeout_s=30,cpu=cpu,
        binary_sha256=digest(Path(binary)),setup_sha256=[digest(Path(s)) for s in scripts],input_manifest_sha256=digest(root/'INPUT_MANIFEST.json')))
    (root/'version.csh').write_text(setup+binary+' -W\nexit $status\n')
    version=execute(['/bin/csh','-f','version.csh'],root,'version.log',30);dump(root/'version.json',version)
    if version['returncode'] or version['timeout']: raise RuntimeError('version preflight failed')
    specs=json.loads((root/'conditions.json').read_text());assert len(specs)==12
    for c in specs:
        work=root/c['id']
        (work/'run.csh').write_text(setup+binary+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
        result=execute(['taskset','-c',str(cpu),'/bin/csh','-f','run.csh'],work,'stdout.log',90)
        dump(work/'spectre-execution.json',result);print(c['id'],result['returncode'],flush=True)
    dump(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def analyze(root,output,require_arrival=False):
    verify(root); records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        for backend in ['evas','spectre']:
            r=dict(configuration=c['id'],backend=backend)
            try:
                if backend=='evas':
                    path=work/'evas.json'; result=json.loads(path.read_text())
                    rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in zip(result['transient']['times'],result['solutions'])]
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']: raise ValueError('execution failed or timed out')
                    path=work/'psf/tran.tran.tran'; rows=read_waveform(path,'spectre')
                    actual,stop_audit=audit_settings((work/'spectre.log').read_text(),c,rows)
                    r.update(effective_settings=actual,stop_audit=stop_audit,elapsed_s=execution['elapsed_s'])
                inspector=inspect_arrivals if require_arrival else inspect
                r.update(inspector(rows,c),waveform_sha256=digest(path),status='analyzed')
            except (FileNotFoundError,ValueError,KeyError) as error:
                r.update(status='failed_or_missing',reason=str(error))
            records.append(r)
    dump(output,dict(records=records,summary=dict(Counter(r['status'] for r in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','evas','spectre','check']);p.add_argument('root',type=Path)
    p.add_argument('--kernel',type=Path);p.add_argument('--spectre-profile',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--require-arrival',action='store_true',help='check the isolated PWL zero-arrival compatibility contract')
    a=p.parse_args()
    if a.action=='build': build(a.root)
    elif a.action=='evas': run_evas(a.root,a.kernel)
    elif a.action=='spectre': run_spectre(a.root,a.spectre_profile)
    else: analyze(a.root,a.output,a.require_arrival)

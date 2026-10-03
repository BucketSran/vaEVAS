"""Frozen endpoint/zero-plateau diagnostic; hypotheses are not simulator truth.

Six configurations share 21 PWL shapes and three direction monitors per shape.
Answers are explicit hand cases, independent of the EVAS root implementation.
"""
import argparse
from collections import Counter
from fractions import Fraction as Q
import json
import math
import os
from pathlib import Path
import re

from cross_touch import (ALLOWANCE, ROOT, STEPS, TOLERANCES, Instance,
                         audit_settings, compile_sources, digest, dump, execute,
                         pwl, read_waveform, transient, verify)

DIRECTIONS = {'both': 0, 'rising': 1, 'falling': -1}
STOP = 3e-6


def shapes():
    # Positive-side templates: (points, candidate [arrival time, direction], kind).
    templates = {
        'terminal': ([[0,.625],[STOP,.5]], [(STOP,-1)], 'boundary'),
        'continued_terminal': ([[0,.625],[STOP,.5],[3.5e-6,.375]], [(STOP,-1)], 'boundary'),
        'plateau_return': ([[0,.625],[1e-6,.5],[2e-6,.5],[STOP,.625]], [(1e-6,-1)], 'boundary'),
        'plateau_cross': ([[0,.625],[1e-6,.5],[2e-6,.5],[STOP,.375]], [(1e-6,-1)], 'boundary'),
        'initial_plateau': ([[0,.5],[1e-6,.5],[STOP,.625]], [], 'boundary'),
        'terminal_plateau': ([[0,.625],[1e-6,.5],[STOP,.5]], [(1e-6,-1)], 'boundary'),
        'short_plateau': ([[0,.625],[1.5e-6,.5],[1.5e-6+20e-12,.5],[STOP,.625]], [(1.5e-6,-1)], 'boundary'),
        'near_plateau': ([[0,.625],[1e-6,.500001],[2e-6,.500001],[STOP,.625]], [], 'control'),
        'isolated': ([[0,.625],[1.5e-6,.5],[STOP,.625]], [(1.5e-6,-1)], 'control'),
        'ordinary': ([[0,.625],[STOP,.375]], [(STOP/2,-1)], 'control'),
    }
    result = {}
    for name,(points,events,kind) in templates.items():
        for polarity in [1,-1]:
            key = name+('_pos' if polarity==1 else '_neg')
            result[key] = dict(points=[[t,.5+polarity*(v-.5)] for t,v in points],
                               events=[[t,polarity*d] for t,d in events], kind=kind)
    result['all_zero'] = dict(points=[[0,.5],[STOP,.5]], events=[], kind='boundary')
    return result


def specifications():
    inputs = {k:s['points'] for k,s in shapes().items()}
    inputs['clock'] = [[0,0],[STOP,STOP*1e6]]
    times = sorted({*[i*.25e-6 for i in range(13)], 1e-6, 2e-6, 1.5e-6+20e-12})
    return [dict(id=f'{profile}-{accuracy}', profile=profile, accuracy=accuracy,
                 maxstep=step, ttol=ttol, etol=etol, stop=STOP,
                 inputs=inputs, output_times=times)
            for profile,step in STEPS.items()
            for accuracy,(ttol,etol) in TOLERANCES.items()]


def monitors():
    return [dict(id=key+'_'+label, shape=key, direction=d, kind=s['kind'])
            for key,s in shapes().items() for label,d in DIRECTIONS.items()]


def model(case):
    ports = [p+label for label in DIRECTIONS for p in ['n_','t_','g_']]
    states = ','.join('n'+str(i) for i in range(3))
    reals = ','.join(p+str(i) for i in range(3) for p in ['t','g'])
    lines = ['`include "disciplines.vams"',
             'module probe(u,clock,'+','.join(ports)+',r);',
             'input u,clock; output '+','.join(ports)+'; inout r;',
             'electrical u,clock,'+','.join(ports)+',r;',
             f'integer {states}; real {reals};', 'analog begin',
             '@(initial_step) begin '+''.join(f'n{i}=0;t{i}=0;g{i}=0;' for i in range(3))+' end']
    for i,(label,d) in enumerate(DIRECTIONS.items()):
        lines += [f'@(cross(V(u,r)-0.5,{d},{case["ttol"]!r},{case["etol"]!r})) begin',
                  f'n{i}=n{i}+1; t{i}=V(clock,r); g{i}=V(u,r)-0.5; end',
                  f'V(n_{label},r)<+n{i}; V(t_{label},r)<+t{i}; V(g_{label},r)<+g{i};']
    return '\n'.join(lines+['end', 'endmodule', ''])


def expected(case, monitor):
    result = []
    for time,direction in shapes()[monitor['shape']]['events']:
        if monitor['direction'] not in [0,direction]:
            continue
        width = Q(case['ttol'])
        if monitor['shape'].startswith('ordinary_'):
            width = min(width, Q(case['etol'])*Q(STOP)/Q(.25))
        result.append((Q(time),width))
    return result


def inspect(rows, case):
    required = {'time',*case['inputs'],*[p+m['id'] for m in monitors() for p in ['n_','t_','g_']]}
    if not rows or any(not required<=r.keys() for r in rows):
        raise ValueError('missing observations')
    if any(not math.isfinite(r[k]) for r in rows for k in required):
        raise ValueError('nonfinite observations')
    if rows[0]['time']!=0 or abs(rows[-1]['time']-case['stop'])>1e-18:
        raise ValueError('incomplete observations')
    if any(not 0<b['time']-a['time']<=.501e-6 for a,b in zip(rows,rows[1:])):
        raise ValueError('invalid time order or gap')
    for r in rows:
        for name,points in case['inputs'].items():
            if abs(Q(r[name])-pwl(points,Q(r['time'])))>Q(ALLOWANCE):
                raise ValueError('input mismatch')
    rate = Q(case['inputs']['clock'][-1][1])/Q(case['stop'])
    reserve = Q(ALLOWANCE)/rate
    records = []
    for m in monitors():
        key=m['id']; events=expected(case,m); previous=0; seen=set(); changes=[]; common={}
        record=dict(m,final_count=rows[-1]['n_'+key],expected_count=len(events))
        try:
            for r in rows:
                n=round(r['n_'+key]); t=Q(r['time']); held=Q(r['t_'+key]); guard=Q(r['g_'+key])
                if abs(r['n_'+key]-n)>ALLOWANCE or n<previous:
                    raise ValueError('invalid count')
                if n!=previous:
                    changes.append(dict(exported_time_s=r['time'],count=n,
                                        witness_time_s=float(held/rate),sampled_guard_v=float(guard)))
                earliest=sum(t>root+width+reserve for root,width in events)
                latest=sum(t>=root-reserve for root,width in events)
                if not earliest<=n<=latest:
                    raise ValueError('count violates candidate windows')
                seen.add(n)
                if n:
                    root,width=events[n-1]; witness=held/rate
                    lo,hi=common.get(n,(root,min(root+width,Q(case['stop']))))
                    common[n]=max(lo,witness-reserve),min(hi,witness+reserve)
                    if common[n][0]>common[n][1]:
                        raise ValueError('held time outside candidate window')
                    # The stamp must be a past event, and guard/stamp must agree
                    # with the frozen input. Allowance is observational, not etol.
                    if witness>t+reserve or abs(guard)>Q(case['etol'])+Q(ALLOWANCE):
                        raise ValueError('invalid sampled guard or future stamp')
                    sample_time=max(Q(0),min(witness,Q(case['stop'])))
                    wanted=pwl(case['inputs'][m['shape']],sample_time)-Q(.5)
                    slope=max(abs((Q(b)-Q(a))/(Q(t1)-Q(t0))) for (t0,a),(t1,b) in
                              zip(case['inputs'][m['shape']],case['inputs'][m['shape']][1:]))
                    if abs(guard-wanted)>Q(ALLOWANCE)+slope*reserve:
                        raise ValueError('guard disagrees with held time')
                elif abs(held)>Q(ALLOWANCE) or abs(guard)>Q(ALLOWANCE):
                    raise ValueError('initial state changed')
                previous=n
            if seen!=set(range(len(events)+1)) or previous!=len(events):
                raise ValueError('missing candidate event')
            record['status']='control_pass' if m['kind']=='control' else 'candidate_consistent'
        except (ValueError,IndexError) as error:
            record.update(status='control_failed' if m['kind']=='control' else 'candidate_inconsistent',reason=str(error))
        # Preserve final observations even when the candidate was rejected early.
        record.update(changes=changes,final_stamp_v=rows[-1]['t_'+key],final_guard_v=rows[-1]['g_'+key])
        records.append(record)
    return dict(points=len(rows),monitors=records,formal_qualification=False,
                summary=dict(Counter(m['status'] for m in records)))


def build(root):
    root.mkdir(parents=True,exist_ok=False)
    specs=specifications()
    dump(root/'conditions.json',specs)
    dump(root/'contract.json',dict(configurations=6,shapes=21,monitors_per_configuration=63,
        max_spectre_attempts=6,timeout_s=90,license_timeout_s=30,observation_allowance_v=ALLOWANCE,
        candidate='One event on nonzero-to-zero arrival, including stop and plateau entry; none on departure, initial zero, or all-zero input.',
        boundaries='Candidate-consistent/inconsistent are diagnostic classifications, not a correctness ranking.',
        controls='Ordinary crossing and reviewed isolated zero: one arrival. Near-zero plateau: no event.',
        limits='Finite exported observations under assumed voltage allowance; no full LRM or continuous-time qualification.'))
    for c in specs:
        work=root/c['id'];work.mkdir();(work/'probe.va').write_text(model(c))
        lines=['simulator lang=spectre','ahdl_include "probe.va"']
        for name,points in c['inputs'].items():
            lines.append(f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t:.17g} {v:.17g}' for t,v in points)+']')
        for shape in shapes():
            nodes=[p+shape+'_'+d for d in DIRECTIONS for p in ['n_','t_','g_']]
            lines.append(f'X{shape} ({shape} clock '+ ' '.join(nodes)+' 0) probe')
        lines += ['simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                  f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                  'save '+' '.join([*c['inputs'],*[p+m['id'] for m in monitors() for p in ['n_','t_','g_']]])]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    dependencies=[Path(__file__),Path(__file__).with_name('test_cross_boundaries.py'),
                  *[Path(__file__).with_name(n+'.py') for n in ['cross_touch','remote','report']],
                  *[ROOT/'experiments/archive/dvs2-starter-pilot'/n for n in ['analyze.py','suite.py']]]
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in dependencies})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(kernel_sha256=digest(kernel),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for directory,pattern in
                      [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')] for p in directory.rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id'];instances=[]
        for shape in shapes():
            ports={p+d:p+shape+'_'+d for d in DIRECTIONS for p in ['n_','t_','g_']}
            instances.append(Instance(shape,'probe',dict(ports,u=shape,clock='clock',r='0'),{}))
        try:
            program=compile_sources({'probe.va':(work/'probe.va').read_text()},instances)
            result=transient(program,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],
                             kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(work/'evas.json',result); print(c['id'],'ok',flush=True)
        except Exception as error:
            dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['id'],type(error).__name__,flush=True)


def run_spectre(root,profile):
    verify(root)
    config=json.loads(profile.read_text()); binary,scripts=config['spectre'],config['setup_scripts']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]):
        raise ValueError('unsupported tool path')
    setup='\n'.join('source '+s for s in scripts)+'\n';cpu=min(os.sched_getaffinity(0))
    dump(root/'SPECTRE_STARTED.json',dict(max_attempts=6,timeout_s=90,license_timeout_s=30,cpu=cpu,
        binary_sha256=digest(Path(binary)),setup_sha256=[digest(Path(s)) for s in scripts],
        input_manifest_sha256=digest(root/'INPUT_MANIFEST.json')))
    (root/'version.csh').write_text(setup+binary+' -W\nexit $status\n')
    version=execute(['/bin/csh','-f','version.csh'],root,'version.log',30);dump(root/'version.json',version)
    if version['returncode'] or version['timeout']: raise RuntimeError('version preflight failed')
    specs=json.loads((root/'conditions.json').read_text()); assert len(specs)==6
    for c in specs:
        work=root/c['id']
        (work/'run.csh').write_text(setup+binary+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
        result=execute(['taskset','-c',str(cpu),'/bin/csh','-f','run.csh'],work,'stdout.log',90)
        dump(work/'spectre-execution.json',result);print(c['id'],result['returncode'],flush=True)
    dump(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def analyze(root,output,backends):
    verify(root);records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        for backend in backends:
            r=dict(configuration=c['id'],backend=backend)
            try:
                if backend=='evas':
                    path=work/'evas.json'; result=json.loads(path.read_text())
                    rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in zip(result['transient']['times'],result['solutions'])]
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']: raise ValueError('execution failed or timed out')
                    path=work/'psf/tran.tran.tran';rows=read_waveform(path,'spectre')
                    actual,stop_audit=audit_settings((work/'spectre.log').read_text(),c,rows)
                    r.update(effective_settings=actual,stop_audit=stop_audit,elapsed_s=execution['elapsed_s'])
                r.update(inspect(rows,c),waveform_sha256=digest(path),status='analyzed')
            except (FileNotFoundError,ValueError,KeyError) as error:
                r.update(status='failed_or_missing',reason=str(error))
            records.append(r)
    dump(output,dict(records=records,summary=dict(Counter(r['status'] for r in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','evas','spectre','check']);p.add_argument('root',type=Path)
    p.add_argument('--kernel',type=Path);p.add_argument('--spectre-profile',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--backends',nargs='+',choices=['evas','spectre'],default=['evas','spectre'])
    a=p.parse_args()
    if a.action=='build': build(a.root)
    elif a.action=='evas': run_evas(a.root,a.kernel)
    elif a.action=='spectre': run_spectre(a.root,a.spectre_profile)
    else: analyze(a.root,a.output,a.backends)

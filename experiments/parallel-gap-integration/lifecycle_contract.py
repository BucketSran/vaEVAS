"""Bounded lifecycle diagnostics: frozen inputs, independent answers, both backends.

This is a development experiment, not a new independent31 matrix or proof of
LRM conformance. Reset sample alternatives are classified rather than silently
choosing Spectre as the oracle. Full raw output stays in a fresh ignored run.
"""
import argparse
from collections import Counter
from decimal import Decimal
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'evas/validation'), str(ROOT/'evas/src'),
               str(ROOT/'experiments/dvs2-spectre-validation')]
from check_lifecycle_math import (UNIT, crossing_window, integral_after_event,
                                  filter_after_event, common_event_interval)
from evas import Instance, compile_sources
from cross_touch import digest, dump, read_waveform, settings
from timer_reference import run_spectre

FAMILIES = ['cross-condition', 'inactive-timer', 'inactive-cross-nonlinear',
            'active-forward', 'active-reverse', 'active-cross-nonlinear',
            'reset-only', 'release-sample', 'warm-restart', 'cold-nonstationary']
PORTS = ['u', 'clock', 'y', 'z', 'held', 'stamp', 'flag', 'r']
ALLOWANCE = 1e-6  # Assumed finite observation allowance; not a physical bound.


def verify_frozen(root):
    """Verify the executed snapshot even when a separately identified analyzer changes."""
    root=root.resolve()
    for manifest, base in [('INPUT_MANIFEST.json', root),
                           ('checker_identity.json', root/'snapshot')]:
        for rel, expected in json.loads((root/manifest).read_text()).items():
            path=(base/rel).resolve()
            if not path.is_relative_to(base.resolve()) or digest(path)!=expected:
                raise ValueError('frozen input drift: '+rel)


def audit_displayed_settings(log, case, rows):
    """Match exact submitted settings to rounded log intervals, then check the endpoint.

    This audits display compatibility, not undocumented internal binary64 values.
    It changes no waveform allowance or observation decision.
    """
    actual=settings(log)
    requested=dict(vabstol=1e-10, iabstol=1e-14, reltol=1e-8,
                   stop=case['stop'], step=case['maxstep'], maxstep=case['maxstep'])
    if actual['method']!='traponly':
        raise ValueError('integration method mismatch')
    units={u:Q(10)**e for u,e in [('s',0),('ms',-3),('us',-6),
                                 ('ns',-9),('ps',-12),('fs',-15)]}
    intervals={}
    for name, value in requested.items():
        intervals[name]=[]
        for raw in re.findall(r'^\s*'+name+r' = ([^\n]+)$',log,re.M):
            tokens=raw.split(',')[0].split()
            if len(tokens) not in [1,2]:
                raise ValueError('invalid setting display: '+name)
            printed=Decimal(tokens[0])
            if not printed.is_finite() or printed<=0:
                raise ValueError('nonfinite/nonpositive setting: '+name)
            scale=units[tokens[1]] if len(tokens)==2 else Q(1)
            radius=Q(10)**printed.as_tuple().exponent*scale/2
            center=Q(printed)*scale; lo,hi=center-radius,center+radius
            if not lo<=Q(value)<=hi:
                raise ValueError('requested setting outside log display precision: '+name)
            intervals[name].append([float(lo),float(hi)])
        if not intervals[name]:
            raise ValueError('missing setting display: '+name)
    if not rows or not math.isfinite(rows[-1]['time']) or abs(rows[-1]['time']-case['stop'])>1e-18:
        raise ValueError('waveform stop mismatch')
    return actual,dict(requested=requested, display_intervals=intervals,
        waveform_stop_s=rows[-1]['time'], waveform_matches_requested=True,
        scope='requested values compatible with rounded display; internal full precision is not exposed')


def specifications():
    cases = []
    for family in FAMILIES:
        for profile, divisions in [('base', 8), ('fine', 256)]:
            cases.append(dict(id=family+'-'+profile, family=family, profile=profile,
                stop=UNIT, maxstep=UNIT/divisions,
                ttol=UNIT/(128 if profile=='base' else 2**20),
                etol=1/(128 if profile=='base' else 2**20),
                inputs={'u': [[0., 0. if family=='warm-restart' else .2],
                              [UNIT, 0. if family=='warm-restart' else .8]],
                        'clock': [[0., 0.], [UNIT, 1.]]},
                output_times=[i*UNIT/32 for i in range(33)]))
    return cases


def source(case):
    f, rate = case['family'], 1/UNIT
    initial, actions = 'q=1; rst=0; stamp=-1; flag=0;', []
    z, y = f'idt(q*{rate!r},1,rst)', f'laplace_nd(V(z,r),\'{{1}},\'{{1,{UNIT!r}}})'
    primary = (f'cross(V(u,r)-0.5,1,{case["ttol"]!r},{case["etol"]!r})'
               if 'cross' in f or f=='cross-condition' else f'timer({UNIT/2!r},0,{case["ttol"]!r})')
    if f=='cross-condition':
        initial = 'q=0; rst=0; stamp=-1; flag=0;'
        actions = [f'@({primary}) begin q=V(u,r); stamp=V(clock,r); '
                   'if (V(u,r)>0.5) flag=2; else flag=3; end']
        z, y = '0', 'q'
    elif f.startswith('inactive'):
        actions = [f'@({primary}) begin q=V(z,r); stamp=V(clock,r); flag=1; end']
    elif f.startswith('active') or f=='reset-only':
        update = ('q=V(z,r); rst=1;' if f=='active-reverse' else
                  'rst=1;' if f=='reset-only' else 'rst=1; q=V(z,r);')
        actions = [f'@({primary}) begin {update} stamp=V(clock,r); flag=1; end',
                   f'@(timer({3*UNIT/4!r},0,{case["ttol"]!r})) begin rst=0; stamp=V(clock,r); flag=2; end']
    elif f=='release-sample':
        actions = [f'@(timer({UNIT/4!r},0,{case["ttol"]!r})) begin rst=1; stamp=V(clock,r); flag=1; end',
                   f'@(timer({UNIT/2!r},0,{case["ttol"]!r})) begin rst=0; q=V(z,r); stamp=V(clock,r); flag=2; end']
    elif f=='warm-restart':
        initial = 'q=0; rst=0; stamp=-1; flag=0;'
        actions = [f'@(timer({UNIT/4!r},0,{case["ttol"]!r})) begin q=0.5; stamp=V(clock,r); flag=1; end']
        z = f'idt(pow(V(u,r),2)*{rate!r},1)'
        y = f'laplace_nd(pow(q*V(y,r),2)+V(z,r),\'{{1}},\'{{1,{UNIT!r}}})'
    elif f=='cold-nonstationary':
        z = f'idt({rate!r},3)'
    extra = (f'V(aux,r)<+idt(pow(V(u,r),2)*{rate!r},0);'
             if 'nonlinear' in f else '')
    initial=initial.replace('stamp=', 'h=').replace('flag=', 'phase=')
    actions=[a.replace('stamp=', 'h=').replace('flag=', 'phase=') for a in actions]
    return ('`include "disciplines.vams"\nmodule probe('+','.join(PORTS)+');\n'
            'input u,clock; output y,z,held,stamp,flag; inout r;\n'
            'electrical '+','.join(PORTS)+('; electrical aux;' if extra else ';')+
            ' real q,h; integer rst,phase;\n'
            'analog begin\n @(initial_step) begin '+initial+' end\n '+
            '\n '.join(actions)+f'\n V(z,r)<+{z}; V(y,r)<+{y};\n '+
            'V(held,r)<+q; V(stamp,r)<+h; V(flag,r)<+phase;\n '+extra+'\nend\nendmodule\n')


def build(root):
    root.mkdir(parents=True, exist_ok=False)
    cases = specifications()
    dump(root/'conditions.json', cases)
    dump(root/'contract.json', dict(max_spectre_attempts=len(cases), timeout_s=90,
        license_timeout_s=30, evas_timeout_s=30, families=FAMILIES,
        assumed_observation_allowance_v=ALLOWANCE,
        purpose='shared lifecycle contracts and classified reset/trigger observations',
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='local development evidence; reset sample alternatives are not normative verdicts',
        qualification='I; no physical observation bound, continuous-time guarantee or performance claim'))
    for c in cases:
        work = root/c['id']; work.mkdir()
        (work/'probe.va').write_text(source(c))
        lines = ['simulator lang=spectre', 'ahdl_include "probe.va"']
        for node, points in c['inputs'].items():
            lines.append(f'V{node} ({node} 0) vsource type=pwl wave=['+
                         ' '.join(f'{t:.17g} {v:.17g}' for t,v in points)+']')
        lines += ['Xdut ('+' '.join('0' if p=='r' else p for p in PORTS)+') probe',
                  'simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                  f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                  'save '+' '.join(p for p in PORTS if p!='r')]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    # Snapshot every Python dependency of both runners/checkers. No private
    # profile or kernel is included in the public input identity.
    for directory in ['evas/src', 'experiments/dvs2-spectre-validation',
                      'experiments/dvs2-starter-pilot']:
        for p in (ROOT/directory).rglob('*.py'):
            target=root/'snapshot'/p.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(p,target)
    for p in [Path(__file__), Path(__file__).with_name('test_lifecycle_contract.py'),
              ROOT/'evas/validation/check_lifecycle_math.py']:
        target=root/'snapshot'/p.relative_to(ROOT); target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)
    dump(root/'checker_identity.json', {str(p.relative_to(root/'snapshot')):digest(p)
        for p in sorted((root/'snapshot').rglob('*.py'))})
    dump(root/'INPUT_MANIFEST.json', {str(p.relative_to(root)):digest(p)
        for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root, kernel):
    verify_frozen(root)
    for rel, expected in json.loads((root/'checker_identity.json').read_text()).items():
        if digest(ROOT/rel)!=expected:
            raise ValueError('execution source drift: '+rel+'; execute the frozen runner')
    dump(root/'EVAS_STARTED.json', dict(kernel_sha256=digest(kernel), timeout_s=30,
        input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),
        runner_sha256=digest(Path(__file__))))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']; start=time.monotonic()
        try:
            program=compile_sources({'probe.va':(work/'probe.va').read_text()},
                [Instance('dut','probe',{p:'0' if p=='r' else p for p in PORTS})])
            request=dict(program=program.to_dict(), driven=list(c['inputs']), samples=[],
                transient=dict(pwl=list(c['inputs'].values()), output_times=c['output_times'],
                               stop=c['stop'],max_step=c['maxstep']),
                tolerances=dict(absolute=1e-6,relative=1e-6))
            dump(work/'evas-request.json',request)
            result=subprocess.run([str(kernel)],input=json.dumps(request,allow_nan=False),
                                  text=True,capture_output=True,timeout=30)
            (work/'evas-stdout.json').write_text(result.stdout)
            (work/'evas-stderr.json').write_text(result.stderr)
            record=dict(returncode=result.returncode,elapsed_s=time.monotonic()-start,
                        request_sha256=digest(work/'evas-request.json'))
            if result.returncode:
                record.update(status='kernel_refusal', error=json.loads(result.stderr))
            else:
                response=json.loads(result.stdout)
                if (response['nodes']!=list(program.nodes) or
                    response['schema_version']!=request['program']['schema_version'] or
                    response['transient']['times']!=c['output_times'] or
                    len(response['solutions'])!=len(c['output_times'])):
                    raise ValueError('response identity mismatch')
                rows=[dict(time=t,**dict(zip(response['nodes'],s['voltages'])))
                      for t,s in zip(c['output_times'],response['solutions'])]
                dump(work/'evas-rows.json',rows)
                record.update(status='waveform_available')
        except subprocess.TimeoutExpired:
            record=dict(status='timeout',timeout_s=30)
        except Exception as error:
            record=dict(status='execution_failure',error=str(error))
        dump(work/'evas-execution.json',record)
        print(c['id'],record['status'],flush=True)


def inspect(rows, c):
    required={'time',*PORTS[:-1]}
    if not rows or any(not required<=r.keys() or any(not math.isfinite(r[k]) for k in required) for r in rows):
        raise ValueError('missing/nonfinite observations')
    if rows[0]['time']!=0 or abs(rows[-1]['time']-UNIT)>1e-18:
        raise ValueError('incomplete observations')
    if any(b['time']<a['time'] for a,b in zip(rows,rows[1:])):
        raise ValueError('time reversal')
    for r in rows:
        for name,points in c['inputs'].items():
            expected=points[0][1]+(points[-1][1]-points[0][1])*r['time']/UNIT
            if abs(r[name]-expected)>ALLOWANCE:
                raise ValueError('input differs from the frozen stimulus')
        if abs(r['flag']-round(r['flag']))>ALLOWANCE:
            raise ValueError('noninteger flag')
    family=c['family']; witnesses={}
    for r in rows:
        flag=round(r['flag'])
        if flag:
            if flag in witnesses and abs(r['stamp']-witnesses[flag])>ALLOWANCE:
                raise ValueError('stamp changed without a new stage')
            witnesses[flag]=r['stamp']
    if family=='cold-nonstationary':
        if witnesses: raise ValueError('unexpected event')
        errors=[abs(r['z']-(3+r['time']/UNIT)) for r in rows]
        errors += [abs(r['y']-(2+r['time']/UNIT+math.exp(-r['time']/UNIT))) for r in rows]
        return dict(status='finite_consistent' if max(errors)<=ALLOWANCE else 'finite_inconsistent',
                    max_observed_error_v=max(errors),event_witnesses={})
    expected_flags=({2,3} if family=='cross-condition' else {1} if family.startswith('inactive') or family=='warm-restart' else {1,2})
    if not witnesses or not set(witnesses)<=expected_flags:
        raise ValueError('missing or unexpected event stages')
    if family!='cross-condition' and set(witnesses)!=expected_flags:
        raise ValueError('missing event stage')
    if family=='cross-condition' and len(witnesses)!=1:
        raise ValueError('condition changed after the held event')
    if any(round(b['flag'])<round(a['flag']) for a,b in zip(rows,rows[1:])):
        raise ValueError('event stage went backwards')
    primary_flag=next(iter(witnesses)) if family=='cross-condition' else 1
    event=witnesses[primary_flag]; release=witnesses.get(2) if family!='cross-condition' else None
    if 'cross' in family:
        lo,hi=crossing_window(.2,.8,UNIT,c['ttol'],c['etol'])
        lo,hi=float(lo/Q(UNIT)),float(hi/Q(UNIT))
    else:
        nominal=.25 if family in ['warm-restart','release-sample'] else .5
        lo,hi=nominal-c['ttol']/UNIT,nominal+c['ttol']/UNIT
    if not lo-ALLOWANCE<=event<=hi+ALLOWANCE:
        raise ValueError('primary stamp outside independently allowed event window')
    if release is not None:
        nominal=.5 if family=='release-sample' else .75
        if abs(release-nominal)>c['ttol']/UNIT+ALLOWANCE or release<=event:
            raise ValueError('release stamp outside its own window or out of order')
    final=rows[-1]; sample=final['held']; reset=family.startswith('active') or family in ['reset-only','release-sample']
    initial_sample=0 if family in ['cross-condition','warm-restart'] else 1
    for r in rows:
        phase=round(r['flag'])
        sample_is_held=bool(phase) and not (family=='release-sample' and phase==1)
        expected=sample if sample_is_held else initial_sample
        if abs(r['held']-expected)>ALLOWANCE:
            raise ValueError('held sample changed outside its event')
        if not round(r['flag']) and abs(r['stamp']+1)>ALLOWANCE:
            raise ValueError('stamp changed before the event')
    label=None
    if family=='cross-condition':
        if any(abs(r['y']-r['held'])>ALLOWANCE for r in rows):
            raise ValueError('sample output does not equal held state')
        joint=common_event_interval(final['stamp'],sample,ALLOWANCE)
        if joint is None or max(float(joint[0]),lo)>min(float(joint[1]),hi):
            raise ValueError('stamp and data sample cannot share one allowed event time')
        return dict(status='classified_trigger_observation',event_witnesses=witnesses,
                    held_sample_v=sample,strict_condition_flag=round(final['flag']),
                    exact_root_x=float(crossing_window(.2,.8,UNIT,c['ttol'],c['etol'])[0]/Q(UNIT)),
                    sample_minus_threshold_v=sample-.5,
                    interpretation='flag 3 is exact-root convention; flag 2 can arise at a later trigger; neither alone is an LRM violation')
    if family.startswith('active'):
        label=('post_reset_sample' if abs(sample-1)<=ALLOWANCE else
               'pre_reset_sample' if abs(sample-(1+event))<=ALLOWANCE else 'other_sample')
        if label=='other_sample':
            raise ValueError('sample matches neither independently defined reset alternative')
    elif family.startswith('inactive'):
        if abs(sample-(1+event))>ALLOWANCE: raise ValueError('inactive reset did not preserve the event sample')
    elif family in ['reset-only','release-sample']:
        if abs(sample-1)>ALLOWANCE: raise ValueError('held/reset-release state differs from IC')
    errors=[]; skipped=0
    for r in rows:
        x=r['time']/UNIT
        if abs(x-event)<=4*ALLOWANCE or (release is not None and abs(x-release)<=4*ALLOWANCE):
            skipped+=1  # Preserve raw left/right exports; do not interpolate a jump.
            continue
        if family=='warm-restart':
            z=1.; y=1. if x<event else 2-4/(4+x-event)
            if abs(sample-.5)>ALLOWANCE: raise ValueError('wrong held nonlinear mode')
        else:
            z=float(integral_after_event(x,event,sample,reset=reset,release=release))
            y=filter_after_event(x,event,sample,reset=reset,release=release)
        errors += [abs(r['z']-z),abs(r['y']-y)]
    maximum=max(errors,default=math.inf)
    return dict(status='finite_consistent' if maximum<=4*ALLOWANCE else 'finite_inconsistent',
                event_witnesses=witnesses,held_sample_v=sample,reset_sample_class=label,
                max_observed_error_v=maximum,excluded_boundary_rows=skipped,
                interpretation='one common observed event history, assumed finite observation allowance; no continuous-time qualification')


def analyze(root, output):
    verify_frozen(root)
    cases=json.loads((root/'conditions.json').read_text()); records=[]
    for backend in ['evas','spectre']:
        base=root if backend=='evas' else root/'spectre-remote'
        verify_frozen(base)
        if backend=='spectre':
            for rel, expected in json.loads((base/'FILE_MANIFEST.json').read_text()).items():
                path=(base/rel).resolve()
                if not path.is_relative_to(base.resolve()) or digest(path)!=expected:
                    raise ValueError('remote output drift: '+rel)
        if digest(base/'INPUT_MANIFEST.json')!=digest(root/'INPUT_MANIFEST.json'):
            raise ValueError('backend inputs differ')
        for c in cases:
            work=base/c['id']; record=dict(backend=backend,case=c['id'],family=c['family'],profile=c['profile'])
            try:
                execution=json.loads((work/(backend+'-execution.json')).read_text())
                record['execution']=execution
                if backend=='evas' and execution['status']!='waveform_available':
                    record.update(status=execution['status'])
                elif backend=='spectre' and (execution['returncode'] or execution['timeout']):
                    record.update(status='timeout' if execution['timeout'] else 'execution_failure')
                else:
                    wave=work/('evas-rows.json' if backend=='evas' else 'psf/tran.tran.tran')
                    rows=json.loads(wave.read_text()) if backend=='evas' else read_waveform(wave,backend)
                    record['waveform_sha256']=digest(wave)
                    if backend=='spectre':
                        record['displayed_settings'],record['settings_audit']=audit_displayed_settings((work/'spectre.log').read_text(),c,rows)
                        if any(b['time']-a['time']>c['maxstep']*1.01 for a,b in zip(rows,rows[1:])):
                            raise ValueError('accepted export gap exceeds requested maxstep')
                    record.update(inspect(rows,c))
            except Exception as error:
                record.update(status='analysis_failure',reason=str(error))
            records.append(record)
    dump(output, dict(source_commit=json.loads((root/'contract.json').read_text())['source_commit'],
        run_id=root.name,records=records,configurations_per_backend=len(cases),families=len(FAMILIES),
        counts={b:dict(Counter(r['status'] for r in records if r['backend']==b)) for b in ['evas','spectre']},
        input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),
        analysis_source_sha256=digest(Path(__file__)),
        frozen_runner_sha256=digest(root/'snapshot/experiments/parallel-gap-integration/lifecycle_contract.py'),
        analysis_kind='reanalysis of preserved new executions; rounded-log audit and release-stage binding v3',
        oracle_source_sha256=digest(ROOT/'evas/validation/check_lifecycle_math.py'),
        evas_identity=json.loads((root/'EVAS_STARTED.json').read_text()),
        spectre_identity=json.loads((root/'spectre-remote/SPECTRE_STARTED.json').read_text()),
        spectre_version_log_sha256=digest(root/'spectre-remote/version.log'),
        new_evas_execution=True,new_spectre_execution=True,raw_availability='local-only ignored run and thu-sui',
        qualification='I',limits=['development cases, not untouched confirmation set',
            'assumed observation allowance, not a proven physical bound',
            'boundary exports preserved but excluded from smooth-trajectory error metric',
            'reset sample classification is not an LRM verdict; no runtime rollback test or performance measurement']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','evas','spectre','analyze'])
    parser.add_argument('root',type=Path)
    parser.add_argument('--kernel',type=Path)
    parser.add_argument('--spectre-profile',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args(); root=args.root.resolve()
    if args.action=='build': build(root)
    elif args.action=='evas': run_evas(root,args.kernel.resolve())
    elif args.action=='spectre': run_spectre(root,args.spectre_profile)
    else: analyze(root,args.output)


if __name__=='__main__':
    main()

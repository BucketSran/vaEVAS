"""PR12 fixed-timer comparison with an independent rational event history.

Freeze inputs/checker before execution. Each backend is checked separately;
simultaneous voltage-state reads are diagnostics, not universal LRM assertions.
"""
import argparse
from bisect import bisect_left, bisect_right
from collections import Counter
from fractions import Fraction as Q
import json
import math
import os
from pathlib import Path
import re

from cross_touch import (ROOT, Instance, audit_settings, compile_sources, digest,
                         dump, execute, pwl, read_waveform, transient, verify)

UNIT = 2.0**-30
ALLOWANCE = 1e-8  # Conditional exported-voltage allowance, not a measured bound.
IMPLEMENTATION = '9a25a401aefa29df3472f4fea17878737ebc0b9e'
STEPS = {'coarse': 5e-9, 'fine': 0.5e-9}


def probe(name, start, period=0.0, initial=0, enable=1, omitted=False):
    return dict(id=name, start=start, period=period, initial=initial,
                enable=enable, omitted=omitted)


def specifications():
    regular = [probe('periodic', 2*UNIT, 5*UNIT),
               probe('once_omitted', 2*UNIT, omitted=True),
               probe('once_zero', 2*UNIT), probe('once_negative', 2*UNIT, -5*UNIT),
               probe('disabled', 2*UNIT, 5*UNIT, enable=0),
               probe('enable_negative', 2*UNIT, 5*UNIT, enable=-2),
               probe('enable_fraction', 2*UNIT, 5*UNIT, enable=0.5),
               probe('initial_once', 0.0, initial=7),
               probe('initial_periodic', 0.0, 5*UNIT, initial=7),
               probe('isolation_a', UNIT, 7*UNIT, initial=2),
               probe('isolation_b', 3*UNIT, 6*UNIT, initial=5),
               probe('simultaneous_a', 8*UNIT), probe('simultaneous_b', 8*UNIT),
               probe('after_stop', 21*UNIT)]
    pairs = [dict(id=kind+'_'+name, kind=kind, start=8*UNIT,
                  receive=8*UNIT+delta, expected_read=int(delta > 0))
             for kind in ['timer', 'cross']
             for name, delta in [('before', -UNIT/8), ('same', 0.0), ('after', UNIT/8)]]
    cases = []
    for profile, step in STEPS.items():
        for reverse in [False, True]:
            cases.append(dict(id=f'ordinary-{profile}-'+('reversed' if reverse else 'forward'),
                              family='ordinary', stop=19*UNIT, probes=regular, pairs=pairs,
                              rate=1/UNIT, ttol=UNIT/1024, reverse=reverse, maxstep=step))
        for suffix, stop in [('before', 16*UNIT-UNIT/8), ('at', 16*UNIT),
                             ('after', 16*UNIT+UNIT/8)]:
            cases.append(dict(id=f'endpoint-{suffix}-{profile}', family='endpoint',
                              stop=stop, probes=[probe('endpoint', 16*UNIT)], pairs=[],
                              rate=1/UNIT, ttol=UNIT/1024, reverse=False, maxstep=step))
        start, period = 0.13e-6, 7e-9
        cases.append(dict(id=f'long-{profile}', family='long',
                          stop=float(Q(start)+(2000-Q(1, 2))*Q(period)),
                          probes=[probe('long', start, period)], pairs=[],
                          rate=1e6, ttol=1e-12, reverse=False, maxstep=step*10))
    for c in cases:
        c['inputs'] = {'clock': [[0, 0], [c['stop'], c['stop']*c['rate']]],
                       'data': [[0, 0.25], [c['stop'], 0.25+2*c['stop']*c['rate']]]}
        # Distinct output grids for EVAS. Spectre exports all accepted points,
        # without forced strobe; its controls are maxstep and declaration order.
        times = {0.0, c['stop']}
        for p in c['probes']:
            for t in nominal(p, c):
                times.update(float(t+d*Q(c['ttol'])) for d in [-4, 4])
                if not c['reverse']:
                    times.add(float(t))
        for p in c['pairs']:
            for t in [p['start'], p['receive']]:
                times.update([t-4*c['ttol'], t+4*c['ttol']])
        spacing = c['maxstep']/2
        phase = spacing/7 if c['reverse'] else 0
        times.update(phase+i*spacing for i in range(math.ceil(c['stop']/spacing)))
        c['output_times'] = sorted(t for t in times if 0 <= t <= c['stop'])
    return cases


def nominal(p, case):
    """Exact real schedule of the submitted binary64 parameters, not EVAS output."""
    if not p['enable']:
        return []
    start, period = Q(p['start']), Q(p['period'])
    limit = Q(case['stop'])+Q(case['ttol'])
    if start > limit:
        return []
    count = 1 if period <= 0 else int((limit-start)//period)+1
    if count > 10000:
        raise ValueError('comparison budget exceeded')
    return [start+k*period for k in range(count)]


def isolation_specifications():
    """Follow-up keeps rejected combined cases; separates three circuit groups."""
    cases = []
    for c in specifications():
        if c['family'] != 'ordinary':
            continue
        for group in ['timers', 'cross_neighbors', 'cross_same']:
            pairs = [p for p in c['pairs'] if
                     (p['kind']=='timer' if group=='timers' else
                      p['kind']=='cross' and ((p['id']=='cross_same') == (group=='cross_same')))]
            case = dict(c, id=c['id']+'-'+group, family=group,
                        probes=c['probes'] if group=='timers' else [], pairs=pairs)
            if group != 'timers':
                case['inputs'] = {'clock':c['inputs']['clock']}
            cases.append(case)
    return cases


def sources(c):
    result = {}
    for omitted in [False, True]:
        name = 'timer_once' if omitted else 'timer_probe'
        period = '' if omitted else 'period'
        result[name+'.va'] = f'''`include "disciplines.vams"
module {name}(clock,data,count,stamp,sample,r);
input clock,data; output count,stamp,sample; inout r;
electrical clock,data,count,stamp,sample,r;
parameter real start=0; parameter real period=0;
parameter real tol=1e-12; parameter real enable=1;
parameter real init_value=0;
integer n; real h,s;
analog begin
 @(initial_step) begin n=init_value; h=-1; s=-3; end
 @(timer(start,{period},tol,enable)) begin n=n+1; h=V(clock,r); s=V(data,r); end
 V(count,r)<+n; V(stamp,r)<+h; V(sample,r)<+s;
end
endmodule
'''
    for p in c['pairs']:
        receive = (f'timer({p["receive"]!r},0,{c["ttol"]!r})' if p['kind']=='timer' else
                   f'cross(V(clock,r)-{p["receive"]*c["rate"]!r},1,{c["ttol"]!r},{c["ttol"]*c["rate"]!r})')
        blocks = [f'@(timer({p["start"]!r},0,{c["ttol"]!r})) begin n=n+1; a=V(clock,r); end',
                  f'@({receive}) begin m=m+1; b=V(clock,r); h=V(count,r); end']
        if c['reverse']:
            blocks.reverse()
        name = 'pair_'+p['id']
        result[name+'.va'] = f'''`include "disciplines.vams"
module {name}(clock,count,stamp,received,rstamp,sample,r);
input clock; output count,stamp,received,rstamp,sample; inout r;
electrical clock,count,stamp,received,rstamp,sample,r;
integer n,m; real a,b,h;
analog begin
 @(initial_step) begin n=0; m=0; a=-1; b=-1; h=-1; end
 {' '.join(blocks)}
 V(count,r)<+n; V(stamp,r)<+a; V(received,r)<+m; V(rstamp,r)<+b; V(sample,r)<+h;
end
endmodule
'''
    return result


def instances(c):
    result = []
    for p in c['probes']:
        result.append(Instance(p['id'], 'timer_once' if p['omitted'] else 'timer_probe',
            dict(clock='clock', data='data', r='0', **{x:x+'_'+p['id'] for x in ['count','stamp','sample']}),
            dict(start=p['start'], period=p['period'], tol=c['ttol'], enable=p['enable'], init_value=p['initial'])))
    for p in c['pairs']:
        result.append(Instance(p['id'], 'pair_'+p['id'],
            dict(clock='clock', r='0', **{x:x+'_'+p['id'] for x in ['count','stamp','received','rstamp','sample']}), {}))
    return result[::-1] if c['reverse'] else result


def history(rows, c, p, count, stamp, sample=None, cross=False):
    events = nominal(p, c)
    tolerance, allowance = Q(c['ttol']), Q(ALLOWANCE)
    rate = Q(c['inputs']['clock'][-1][1])/Q(c['stop'])
    reserve = allowance/rate
    windows = [(max(Q(0), t if cross else t-tolerance), t+tolerance) for t in events]
    common = [list(w) for w in windows]
    early = [lo-reserve for lo, hi in windows]
    late = [hi+reserve for lo, hi in windows]
    seen, previous, max_error = set(), 0, Q(0)
    for row in rows:
        t = Q(row['time'])
        n = round(row[count])-p['initial']
        if abs(Q(row[count])-n-p['initial']) > allowance or n < previous:
            raise ValueError('noninteger or decreasing count')
        if not bisect_left(late, t) <= n <= bisect_right(early, t):
            raise ValueError('count outside independently allowed event windows')
        if n > previous+1:
            raise ValueError('unobserved intermediate event history')
        if n < len(events):
            common[n][0] = max(common[n][0], t-reserve)
        if n:
            seen.add(n)
            witness = Q(row[stamp])/rate
            lo, hi = common[n-1]
            lo, hi = max(lo, witness-reserve), min(hi, witness+reserve, t+reserve)
            if sample:
                # All probes use the same affine data input, independently
                # checked below. Both held outputs must admit ONE event time.
                points = c['inputs']['data']
                slope = (Q(points[-1][1])-Q(points[0][1]))/Q(c['stop'])
                sample_time = (Q(row[sample])-Q(points[0][1]))/slope
                lo, hi = max(lo, sample_time-allowance/slope), min(hi, sample_time+allowance/slope)
            if lo > hi:
                raise ValueError('no common event time for count, stamp and held value')
            common[n-1] = [lo, hi]
            max_error = max(max_error, abs(witness-events[n-1]))
        elif abs(Q(row[stamp])+1) > allowance or (sample and abs(Q(row[sample])+3) > allowance):
            raise ValueError('initial held value changed without an event')
        previous = n
    if seen != set(range(1, previous+1)):
        raise ValueError('missing event observation')
    # Unseen endpoint events can occur beyond stop inside their FULL window.
    # Do not clip them to stop or require the EVAS endpoint convention.
    if any(hi < Q(c['stop'])-reserve for lo, hi in windows[previous:]):
        raise ValueError('missing required event')
    if any(lo > hi for lo, hi in common):
        raise ValueError('inconsistent observation brackets')
    if any(a[0] >= b[1] for a,b in zip(common[:previous],common[1:previous])):
        raise ValueError('no ordered event history')
    return dict(status='finite_consistent', events_observed=previous,
                possible_events=len(events), pending_at_stop=len(events)-previous,
                max_stamp_phase_error_s=float(max_error),
                first_count=rows[0][count], final_count=rows[-1][count],
                final_stamp_v=rows[-1][stamp])


def inspect(rows, c):
    required = {'time', *c['inputs'], *[node for inst in instances(c)
                  for node in inst.connections.values() if node != '0']}
    if not rows or any(not required <= r.keys() for r in rows):
        raise ValueError('missing signals')
    if any(not math.isfinite(r[k]) for r in rows for k in required):
        raise ValueError('nonfinite observations')
    if rows[0]['time'] != 0 or abs(rows[-1]['time']-c['stop']) > 1e-18:
        raise ValueError('incomplete time coverage')
    # Keep same-time left/right exports; check both. Never interpolate jumps.
    if any(not 0 <= b['time']-a['time'] <= c['maxstep']*1.001 for a,b in zip(rows,rows[1:])):
        raise ValueError('invalid time order or output gap')
    for r in rows:
        for name, points in c['inputs'].items():
            if abs(Q(r[name])-pwl(points,Q(r['time']))) > Q(ALLOWANCE):
                raise ValueError('input mismatch')
    records = []
    for p in c['probes']:
        try:
            r = history(rows,c,p,'count_'+p['id'],'stamp_'+p['id'],'sample_'+p['id'])
        except ValueError as error:
            r = dict(status='finite_inconsistent', reason=str(error))
        records.append(dict(id=p['id'], kind='timer', **r))
    for p in c['pairs']:
        key = p['id']
        try:
            tx = history(rows,c,probe(key,p['start']),'count_'+key,'stamp_'+key)
            rx = history(rows,c,probe(key,p['receive']),'received_'+key,'rstamp_'+key,cross=p['kind']=='cross')
            values = [r['sample_'+key] for r in rows if r['received_'+key] > 0.5]
            if any(abs(r['sample_'+key]+1)>ALLOWANCE for r in rows if r['received_'+key]<0.5):
                raise ValueError('sample changed before receiver event')
            if not values or any(abs(v-values[0])>ALLOWANCE for v in values):
                raise ValueError('received state is missing or not held')
            if min(abs(values[0]),abs(values[0]-1))>ALLOWANCE:
                raise ValueError('received value is not a valid producer state')
            matches = abs(values[0]-p['expected_read']) <= ALLOWANCE
            simultaneous = p['receive']==p['start']
            if not simultaneous and not matches:
                raise ValueError('separated event windows gave wrong state order')
            r = dict(status=('candidate_consistent' if matches else 'candidate_differs') if simultaneous else 'finite_consistent',
                     observed_read=values[0], candidate_read=p['expected_read'], producer=tx, receiver=rx)
        except ValueError as error:
            r = dict(status='finite_inconsistent', reason=str(error))
        records.append(dict(id=key,kind='interaction',**r))
    return dict(points=len(rows), records=records,
                summary=dict(Counter(r['status'] for r in records)), formal_qualification=False)


def build(root,isolate=False):
    root.mkdir(parents=True, exist_ok=False)
    cases = isolation_specifications() if isolate else specifications()
    dump(root/'conditions.json',cases)
    dump(root/'contract.json',dict(implementation=IMPLEMENTATION, configurations=len(cases),
        circuit_layout='isolated-follow-up' if isolate else 'combined-original',
        max_spectre_attempts=len(cases), timeout_s=90, license_timeout_s=30,
        observation_allowance_v=ALLOWANCE, unit_s=UNIT,
        semantic_source='Verilog-AMS LRM 2.4 section 5.10.3.3',
        time_rule='Exact Fraction(start)+k*Fraction(period), symmetric explicit timer tolerance; cross uses one-sided window.',
        endpoint_rule='Full windows retained past stop; before/at/after runs are separate observations, not a forced endpoint count.',
        same_time_rule='Independent counts/stamps required. Old-voltage read is an EVAS candidate; report other valid state reads as differences.',
        limits='Conditional finite observations with assumed 1e-8 V allowance; no proven physical observation bound, continuous-time qualification or performance ranking.',
        controls='Coarse/fine maxstep and reversed declarations; EVAS also shifts output grid. Spectre saves all accepted points without strobe.'))
    for c in cases:
        work=root/c['id']; work.mkdir()
        used={inst.module+'.va' for inst in instances(c)}
        src={name:source for name,source in sources(c).items() if name in used}
        for name,source in src.items(): (work/name).write_text(source)
        lines=['simulator lang=spectre', *[f'ahdl_include "{name}"' for name in src]]
        for name,points in c['inputs'].items():
            lines.append(f'V{name} ({name} 0) vsource type=pwl wave=['+' '.join(f'{t:.17g} {v:.17g}' for t,v in points)+']')
        for inst in instances(c):
            ports = ['clock','count','stamp','received','rstamp','sample','r'] if inst.module.startswith('pair_') else ['clock','data','count','stamp','sample','r']
            lines.append('X'+inst.name+' ('+' '.join(inst.connections[p] for p in ports)+') '+inst.module+' '+
                         ' '.join(f'{k}={v!r}' for k,v in inst.parameters.items()))
        saved=sorted({node for inst in instances(c) for node in inst.connections.values() if node!='0'})
        lines += ['simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14',
                  f'tran tran stop={c["stop"]:.17g} step={c["maxstep"]:.17g} maxstep={c["maxstep"]:.17g} method=traponly',
                  'save '+' '.join(saved)]
        (work/'tb.scs').write_text('\n'.join(lines)+'\n')
    deps=[Path(__file__),Path(__file__).with_name('test_timer_reference.py'),
          *[Path(__file__).with_name(n+'.py') for n in ['cross_touch','remote','report']],
          *[ROOT/'experiments/dvs2-starter-pilot'/n for n in ['analyze.py','suite.py']]]
    dump(root/'checker_identity.json',{str(p.relative_to(ROOT)):digest(p) for p in deps})
    dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root,kernel):
    verify(root)
    dump(root/'EVAS_STARTED.json',dict(implementation=IMPLEMENTATION,kernel_sha256=digest(kernel),
        source_sha256={str(p.relative_to(ROOT)):digest(p) for directory,pattern in
                      [(ROOT/'evas/src','*.py'),(ROOT/'evas/rust_core/src','*.rs')] for p in directory.rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        try:
            src={p.name:p.read_text() for p in work.glob('*.va')}
            program=compile_sources(src,instances(c))
            result=transient(program,c['inputs'],c['output_times'],stop=c['stop'],max_step=c['maxstep'],
                             kernel=kernel,vabstol=1e-10,reltol=1e-8)
            dump(work/'evas.json',result); print(c['id'],'ok',flush=True)
        except Exception as error:
            dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['id'],type(error).__name__,str(error),flush=True)


def run_spectre(root,profile):
    verify(root)
    c=json.loads(profile.read_text()); binary,scripts=c['spectre'],c['setup_scripts']
    if any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]):
        raise ValueError('unsupported tool path')
    setup='\n'.join('source '+s for s in scripts)+'\n'; cpu=min(os.sched_getaffinity(0))
    cases=json.loads((root/'conditions.json').read_text())
    contract=json.loads((root/'contract.json').read_text())
    if len(cases)!=contract['max_spectre_attempts']: raise ValueError('budget drift')
    dump(root/'SPECTRE_STARTED.json',dict(max_attempts=len(cases),timeout_s=90,license_timeout_s=30,cpu=cpu,
        binary_sha256=digest(Path(binary)),setup_sha256=[digest(Path(s)) for s in scripts],
        input_manifest_sha256=digest(root/'INPUT_MANIFEST.json')))
    (root/'version.csh').write_text(setup+binary+' -W\nexit $status\n')
    version=execute(['/bin/csh','-f','version.csh'],root,'version.log',30); dump(root/'version.json',version)
    if version['returncode'] or version['timeout']: raise RuntimeError('version preflight failed')
    for c in cases:
        work=root/c['id']
        (work/'run.csh').write_text(setup+binary+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
        result=execute(['taskset','-c',str(cpu),'/bin/csh','-f','run.csh'],work,'stdout.log',90)
        dump(work/'spectre-execution.json',result); print(c['id'],result['returncode'],flush=True)
    dump(root/'FILE_MANIFEST.json',{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*')) if p.is_file()})


def analyze(root,output,backends):
    verify(root); records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        for backend in backends:
            r=dict(configuration=c['id'],family=c['family'],backend=backend)
            try:
                if backend=='evas':
                    failure=work/'evas-failure.json'
                    if failure.exists():
                        details=json.loads(failure.read_text())
                        raise ValueError(details['type']+': '+details['message'])
                    path=work/'evas.json'; result=json.loads(path.read_text())
                    rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in zip(result['transient']['times'],result['solutions'])]
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode'] or execution['timeout']: raise ValueError('execution failure or timeout')
                    path=work/'psf/tran.tran.tran'; rows=read_waveform(path,'spectre')
                    actual,stop_audit=audit_settings((work/'spectre.log').read_text(),c,rows)
                    r.update(effective_settings=actual,stop_audit=stop_audit,elapsed_s=execution['elapsed_s'])
                r.update(inspect(rows,c),waveform_sha256=digest(path),status='analyzed')
            except (FileNotFoundError,ValueError,KeyError) as error:
                r.update(status='failed_or_missing',reason=str(error))
            records.append(r)
    dump(output,dict(records=records,summary=dict(Counter(r['status'] for r in records))))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['build','evas','spectre','check']); p.add_argument('root',type=Path)
    p.add_argument('--kernel',type=Path); p.add_argument('--spectre-profile',type=Path); p.add_argument('--output',type=Path)
    p.add_argument('--backends',nargs='+',choices=['evas','spectre'],default=['evas','spectre'])
    p.add_argument('--isolate',action='store_true',help='Freeze follow-up groups; does not replace original cases')
    a=p.parse_args()
    if a.action=='build': build(a.root,a.isolate)
    elif a.action=='evas': run_evas(a.root,a.kernel)
    elif a.action=='spectre': run_spectre(a.root,a.spectre_profile)
    else: analyze(a.root,a.output,a.backends)

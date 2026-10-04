"""Separate crossing detection from integral restart; bounded development evidence.

The original feedback model has no prescribed event-count oracle. Controls have
z(t)=t before tau and z(t)=2*tau-t afterwards, with roots .5 and 2*tau-.5.
This runner reuses the existing process bounds and PSF parser without changing
their frozen implementations. Python 3.9 is sufficient on the reference host.
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import sys

import oscillator_compatibility as common
import report

ROOT = common.ROOT
check = common.check


def tool_identity():
    paths = [Path(__file__).resolve(), Path(common.__file__).resolve(), common.CHECKER, Path(report.__file__).resolve()]
    return {str(p.relative_to(ROOT)): check.sha(p) for p in paths}


def cases():
    result = []
    for family in ['pwl-small', 'pwl-large', 'timer-small', 'timer-large', 'original']:
        for profile in ['baseline', 'tight-solver', 'tight-cross', 'gear2']:
            tau = .500001 if family.endswith('large') else .5000000005
            stop = .500004 if family.endswith('large') else .50000006
            rel = 1e-12 if profile == 'tight-solver' else 1e-8
            c = dict(name=family+'-'+profile, family=family, profile=profile,
                     tau=tau, stop=stop, maxstep=.002, reltol=rel,
                     vabstol=rel/100, iabstol=rel/1e6,
                     method='gear2only' if profile == 'gear2' else 'traponly',
                     ttol=1e-11 if profile == 'tight-cross' else 1e-9,
                     vtol=1e-10 if profile == 'tight-cross' else 1e-8,
                     evas_vabstol=1e-10 if profile == 'tight-solver' else 1e-8)
            c['control'] = [[0, 0], [tau, tau], [stop, 2*tau-stop]] if family.startswith('pwl') else [[0, 0], [stop, stop]]
            result.append(c)
    return result


def source(c):
    if c['family'] == 'original':
        text=common.diagnostic_source(dict(c, family='bidirectional'))
        if 'discontinuity' in c:
            text=text.replace('slope=-slope; n=n+1;',f'slope=-slope; n=n+1; $discontinuity({c["discontinuity"]});')
        return text
    timer = c['family'].startswith('timer')
    declaration = 'real slope; integer q; integer n;' if timer else 'integer n;'
    init = 'slope=1; q=0; n=0;' if timer else 'n=0;'
    event = f'@(timer({c["tau"]},0,1e-12)) begin slope=-1; q=1; end' if timer else ''
    if 'discontinuity' in c:
        event=event.replace('q=1;',f'q=1; $discontinuity({c["discontinuity"]});')
    expression = 'idt(slope,0)' if timer else 'V(ctl,r)'
    count = 'n+10*q' if timer else 'n'
    return f'''`include "disciplines.vams"
module triangle(ctl,z,count,r);
input ctl; output z,count; inout r; electrical ctl,z,count,r;
{declaration}
analog begin
@(initial_step) begin {init} end
{event}
V(z,r)<+{expression};
@(cross((V(z,r)-0.5)*(V(z,r)+0.5),0,{c['ttol']},{c['vtol']})) n=n+1;
V(count,r)<+{count};
end
endmodule
'''


def prepare(root, suite='decomposition'):
    root.mkdir(parents=True, exist_ok=False)
    conditions = cases()
    if suite=='discontinuity':
        conditions=[dict(c,name=c['name']+'-discontinuity'+str(order),discontinuity=order)
                    for c in conditions if c['profile']=='baseline' and c['family'] in ['timer-small','timer-large','original']
                    for order in [0,1]]
    for c in conditions:
        work = root/c['name']; work.mkdir()
        (work/'dut.va').write_text(source(c))
        (work/'tb.scs').write_text(common.netlist(c, False))
    check.dump(root/'conditions.json', conditions)
    check.dump(root/'contract.json', dict(tools=tool_identity(), suite=suite, denominator=len(conditions),
        timeout_s=15, output_limit_per_file_bytes=16*1024*1024,
        oracle='Controls: t before tau, 2*tau-t after; roots .5 and 2*tau-.5. Original: report only.',
        control_voltage_limit_v=1e-10, control_event_limit_s=2e-9, control_cross_count=2,
        count_encoding='timer marker adds 10; each cross adds 1; no feedback from counter',
        purpose='Diagnose finite precision and restart; measurements are not an LRM compliance verdict, holdout, or speed comparison.'))
    check.dump(root/'INPUT_MANIFEST.json', {str(p.relative_to(root)):check.sha(p) for p in sorted(root.rglob('*')) if p.is_file()})


def verify(root, execution=True):
    for name, digest in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        if check.sha(root/name) != digest: raise ValueError('input drift: '+name)
    if execution and json.loads((root/'contract.json').read_text())['tools'] != tool_identity():
        raise ValueError('tool drift; use a new execution identity')


def execute(root, backend, binary):
    verify(root)
    stamp = root/(backend.upper()+'_STARTED.json')
    if stamp.exists(): raise ValueError('execution already started; use a new identity')
    if backend == 'spectre':
        version = subprocess.run([str(binary), '-W'], capture_output=True, text=True, timeout=15, check=True).stdout.strip()
        identity = dict(binary_sha256=check.sha(binary), version=version)
    else:
        sys.path.insert(0, str(ROOT/'evas/src'))
        from evas import Instance, compile_sources, transient
        identity = dict(binary_sha256=check.sha(binary), source_sha256={
            str(p.relative_to(ROOT)):check.sha(p) for folder, pattern in [('evas/src','*.py'), ('evas/rust_core/src','*.rs')]
            for p in (ROOT/folder).rglob(pattern)})
    check.dump(stamp, identity)
    for c in json.loads((root/'conditions.json').read_text()):
        work = root/c['name']
        if backend == 'spectre':
            rec = check.execute(str(binary), work, timeout=15)
            check.dump(work/'spectre-execution.json', rec)
            if 'SPECTRE-209' in (work/'stdout.log').read_text(errors='replace'):
                raise RuntimeError('license unavailable; remaining cases not attempted')
        else:
            try:
                program = compile_sources({'dut.va':(work/'dut.va').read_text()}, [Instance('dut','triangle',dict(ctl='ctl',z='z',count='count',r='0'))])
                times = sorted({0., c['stop'], *[i*c['maxstep'] for i in range(int(c['stop']/c['maxstep'])+1)]})
                data = transient(program, {'ctl':c['control']}, times, stop=c['stop'], max_step=c['maxstep'],
                                 kernel=binary, timeout=15, vabstol=c['evas_vabstol'], reltol=0)
                check.dump(work/'evas.json', data)
                rec = dict(status='completed')
            except Exception as error:
                rec = dict(status='rejected', type=type(error).__name__, message=str(error))
                check.dump(work/'evas-failure.json', rec)
        print(c['name'], backend, rec, flush=True)


def measure(rows, c, event_trace=None):
    if len(rows) < 3 or rows[0]['time'] != 0 or abs(rows[-1]['time']-c['stop']) > 1e-14:
        raise ValueError('incomplete interval')
    if any(not math.isfinite(v) for row in rows for v in row.values()): raise ValueError('nonfinite')
    gaps = [b['time']-a['time'] for a,b in zip(rows,rows[1:])]
    if min(gaps) < 0 or max(gaps) > c['maxstep']*(1+1e-7): raise ValueError('time grid')
    timer = c['family'].startswith('timer')
    events, timers = [], []
    if event_trace is not None:
        prior = 0.
        for e in event_trace:
            if not math.isfinite(e['time']) or not prior <= e['time'] <= c['stop']:
                raise ValueError('invalid event log time')
            prior=e['time']
            if e['kind']=='cross': events.append(e)
            elif e['kind']=='timer' and timer: timers.append(e['time'])
            else: raise ValueError('unexpected event kind')
    old_n, old_q = 0, 0
    for row in rows:
        raw = row['count']; value = round(raw)
        if abs(raw-value) > 1e-6 or value < 0: raise ValueError('invalid count')
        q, n = divmod(value, 10) if timer else (0, value)
        if timer and q not in [0,1]: raise ValueError('invalid timer marker')
        if event_trace is not None:
            if n != sum(e['time']<=row['time'] for e in events) or q != sum(t<=row['time'] for t in timers):
                raise ValueError('counter disagrees with event log')
            continue
        if q != old_q:
            if q != old_q+1: raise ValueError('reversed timer marker')
            timers.append(row['time']); old_q=q
        if n != old_n:
            if n != old_n+1: raise ValueError('count jump')
            events.append({k:row[k] for k in ['time','z','count']}); old_n=n
    result = dict(rows=len(rows), actual_stop_s=rows[-1]['time'], cross_count=len(events),
                  first_cross_events=events[:8], timer_events_s=timers)
    # Saved points only: expose the step around the slope switch. This does not
    # assert knowledge of the reference simulator's internal history objects.
    if event_trace is None:
        index=next((i for i,r in enumerate(rows) if r['count'] >= (10 if timer else 1)),None)
        if index is not None and (timer or c['family']=='original'):
            start,end=(index-1,index) if timer else (index,index+1)
            if start>=0 and end<len(rows):
                a,b=rows[start],rows[end]
                result['first_switch_step']=dict(before=a,after=b,step_s=b['time']-a['time'],
                                                integral_increment_v=b['z']-a['z'])
    if c['family'] == 'original':
        result['status']='observed_without_unique_event_oracle'
        return result
    tau = c['tau']
    expected = [.5, 2*tau-.5]
    wave = max(abs(r['z']-(r['time'] if r['time'] <= tau else 2*tau-r['time'])) for r in rows)
    timing = max(abs(a['time']-b) for a,b in zip(events,expected)) if len(events) == 2 else None
    result.update(status='measured_control', expected_cross_s=expected,
                  max_voltage_error_v=wave, max_cross_time_error_s=timing,
                  meets_diagnostic_targets=len(events)==2 and wave<=1e-10 and timing<=2e-9 and (not timer or len(timers)==1))
    if timer and len(timers)==1:
        actual_tau=timers[0]
        result['timer_delay_s']=actual_tau-tau
        result['max_error_with_observed_timer_v']=max(abs(r['z']-(r['time'] if r['time'] <= actual_tau else 2*actual_tau-r['time'])) for r in rows)
    return result


def analyze(root, output):
    verify(root, execution=False)
    if output.exists(): raise ValueError('analysis output exists')
    results=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['name']; item=dict(condition=c, backends={})
        for backend in ['evas','spectre']:
            path=work/('evas.json' if backend=='evas' else 'psf/tran.tran.tran')
            rec={}
            if backend=='evas' and (work/'evas-failure.json').exists(): rec=json.loads((work/'evas-failure.json').read_text())
            try:
                if backend=='spectre':
                    rec['execution']=json.loads((work/'spectre-execution.json').read_text())
                    rec['effective_settings']=report.settings((work/'spectre.log').read_text(errors='replace'))
                    rec['settings_match']=all(rec['effective_settings'][k]==c[k] if isinstance(c[k],str) else math.isclose(rec['effective_settings'][k],c[k],rel_tol=1e-12) for k in ['reltol','vabstol','iabstol','method','maxstep'])
                    if rec['execution']['returncode']!=0 or rec['execution']['timeout'] or not rec['settings_match']: raise ValueError('execution or settings failed')
                if path.exists():
                    rec['waveform_sha256']=check.sha(path)
                    data=json.loads(path.read_text()) if backend=='evas' else None
                    rows=common.evas_rows(data) if data is not None else check.read_psf(path)
                    rec.update(measure(rows,c,data['transient']['events'] if data is not None else None))
                elif not rec.get('status'): raise ValueError('missing waveform')
            except (OSError, ValueError, KeyError) as error: rec.update(status='failed', reason=str(error))
            item['backends'][backend]=rec
        results.append(item)
    check.dump(output, dict(run_id=root.name, contract=json.loads((root/'contract.json').read_text()),
        analysis_tools=tool_identity(), inputs=json.loads((root/'INPUT_MANIFEST.json').read_text()),
        identities={b:json.loads((root/(b.upper()+'_STARTED.json')).read_text()) for b in ['evas','spectre']},
        results=results, availability='Raw outputs retained locally and on authorized host, not publicly downloadable.'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','evas','spectre','analyze']);p.add_argument('root',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--output',type=Path);p.add_argument('--suite',choices=['decomposition','discontinuity'],default='decomposition')
    a=p.parse_args()
    if a.action=='prepare': prepare(a.root,a.suite)
    elif a.action=='analyze': analyze(a.root,a.output)
    else: execute(a.root,a.action,a.binary or ROOT/'evas/rust_core/target/debug/evas-kernel')

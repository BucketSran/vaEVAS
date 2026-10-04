"""Frozen, bounded model-portability experiments; not a speed benchmark.

No changes to history_relocalization.py or its original receipts. Both backends
use identical VA. Internal settings are explicit; external criteria stay fixed.
"""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
TASK = ROOT/'benchmark/tasks/va07-triangle-repair'
CHECKER = ROOT/'benchmark/checkers/triangle_oscillator.py'
spec = importlib.util.spec_from_file_location('triangle_checker', CHECKER)
check = importlib.util.module_from_spec(spec); spec.loader.exec_module(check)


def bench_cases():
    families = [
        dict(name='constant', lo=-.5,hi=.5,initial=0.,direction=1,stop=3.,maxstep=.005,control=[[0,1],[3,1]]),
        dict(name='descending',lo=-.25,hi=.75,initial=.125,direction=-1,stop=6.,maxstep=.01,control=[[0,.5],[6,.5]]),
        dict(name='ramp',lo=-.5,hi=.5,initial=0.,direction=1,stop=3.,maxstep=.005,control=[[0,1],[3,2.5]]),
        dict(name='segments',lo=-.2,hi=.3,initial=-.05,direction=1,stop=2.,maxstep=.004,control=[[0,1],[.3,1],[.7,.4],[1.2,.4],[2,.8]])]
    out=[]
    for family in families:
        for label, rel in [('tight',1e-11),('tighter',1e-12)]:
            c=dict(family, name=family['name']+'-'+label, wave_atol=1e-6,time_atol=2e-7,
                   ttol=1e-10,vtol=1e-10,method='traponly',reltol=rel,vabstol=rel/100,iabstol=rel/1e6)
            c['netlist']=netlist(c, True)
            out.append(c)
    return out


def netlist(c, benchmark):
    wave=' '.join(str(x) for p in c['control'] for x in p)
    if benchmark:
        instance=f"Xdut (ctl z count 0) triangle lower={c['lo']} upper={c['hi']} initial_voltage={c['initial']} direction={c['direction']} ttol={c['ttol']} vtol={c['vtol']}"
    else:
        instance='Xdut (ctl z count 0) triangle'
    return f'''simulator lang=spectre
ahdl_include "dut.va"
Vctl (ctl 0) vsource type=pwl wave=[{wave}]
{instance}
simulatorOptions options reltol={c['reltol']} vabstol={c['vabstol']} iabstol={c['iabstol']}
tran tran stop={c['stop']} step={c['maxstep']} maxstep={c['maxstep']} method={c['method']}
save ctl z count
'''


def diagnostic_source(c):
    passive=c['family']=='passive'
    guard='V(z,r)-0.375' if passive else '(V(z,r)-0.5)*(V(z,r)+0.5)'
    direction=1 if c['family']=='outward' else 0
    body='n=n+1;' if passive else 'slope=-slope; n=n+1;'
    init='n=0;' if passive else 'slope=1; n=0;'
    decl='integer n;' if passive else 'real slope; integer n;'
    return f'''`include "disciplines.vams"
module triangle(ctl,z,count,r);
input ctl; output z,count; inout r; electrical ctl,z,count,r;
{decl}
analog begin
@(initial_step) begin {init} end
V(z,r)<+idt({'1-V(ctl,r)' if passive else 'slope'},0);
@(cross({guard},{direction},{c['ttol']},{c['vtol']})) begin {body} end
V(count,r)<+n;
end
endmodule
'''


def experiments():
    out=[]
    for family in ['bidirectional','outward','passive']:
        for label in ['baseline','tight-solver','tight-cross','short-step','gear2']:
            rel=1e-12 if label=='tight-solver' else 1e-8
            stop=.50000006 if family=='bidirectional' else 2. if family=='passive' else 3.
            c=dict(name=family+'-'+label,family=family,kind='diagnostic',oracle='passive' if family=='passive' else 'triangle',
                lo=-.5,hi=.5,initial=0.,direction=1,stop=stop,maxstep=.0002 if label=='short-step' else .002,
                control=[[0,0],[stop,stop]],wave_atol=1e-6,time_atol=2e-7,
                reltol=rel,vabstol=rel/100,iabstol=rel/1e6,method='gear2only' if label=='gear2' else 'traponly',
                ttol=1e-11 if label=='tight-cross' else 1e-9,vtol=1e-10 if label=='tight-cross' else 1e-8,
                evas_vabstol=1e-10 if label=='tight-solver' else 1e-8)
            # Triangle oracle assumes unit speed; control here only drives passive.
            c['netlist']=netlist(c,False)
            c['source']=diagnostic_source(c)
            out.append(c)
    reference=(TASK/'solution/dut.va').read_text()
    for c in bench_cases():
        out.append(dict(c,kind='benchmark',family='reference',oracle='triangle',source=reference,evas_vabstol=1e-8))
    for family in ['equivalent','bidirectional-starter','wrong-speed','wrong-initial','fixed-speed']:
        source=reference
        if family=='equivalent':
            source=source.replace('cross(V(z,r)-upper,+1,ttol,vtol) or cross(V(z,r)-lower,-1,ttol,vtol)',
                                  'cross((V(z,r)-upper)*(V(z,r)-lower),+1,ttol,vtol*(upper-lower))')
        elif family=='bidirectional-starter':
            source=source.replace('upper,+1','upper,0').replace('lower,-1','lower,0')
        elif family=='wrong-speed': source=source.replace('sign*V(ctl,r)','0.5*sign*V(ctl,r)')
        elif family=='wrong-initial': source=source.replace('idt(sign*V(ctl,r), initial_voltage)','idt(sign*V(ctl,r), 0.0)')
        elif family=='fixed-speed': source=source.replace('sign*V(ctl,r)','sign')
        names=['constant-tighter','segments-tighter'] if family=='equivalent' else [{'bidirectional-starter':'constant-tighter','wrong-speed':'constant-tighter','wrong-initial':'descending-tighter','fixed-speed':'ramp-tighter'}[family]]
        for case in bench_cases():
            if case['name'] in names:
                out.append(dict(case,name=family+'-'+case['name'],kind='calibration',family=family,oracle='triangle',source=source,evas_vabstol=1e-8))
    return out


def prepare(root, group=None):
    root.mkdir(parents=True,exist_ok=False)
    cases=[c for c in experiments() if group is None or c["kind"] in ["benchmark","calibration"]]
    for c in cases:
        work=root/c['name'];work.mkdir()
        (work/'dut.va').write_text(c.pop('source'))
        (work/'tb.scs').write_text(c['netlist'])
    check.dump(root/'conditions.json',cases)
    check.dump(root/'contract.json',dict(runner_sha256=check.sha(__file__),checker_sha256=check.sha(CHECKER),
        cases_sha256=check.sha(TASK/'tests/cases.json'),settings_parser_sha256=check.sha(Path(__file__).with_name('report.py')),denominator=len(cases),timeout_s=15,output_limit_per_file_bytes=16*1024*1024,
        wave_allowance_v=1e-6,event_time_allowance_s=2e-7,event_count='exact',
        groups={kind:sum(c['kind']==kind for c in cases) for kind in ['diagnostic','benchmark','calibration']},
        evas_timeout_s=300, spectre_timeout_s=15,
        evidence='Development saved-point and discrete-event evidence; not holdout, continuous-time qualification, or performance comparison.',
        hypothesis='Self-reversing bidirectional guards may chatter; solver/cross/step/method sweeps are separate interventions.'))
    check.dump(root/'INPUT_MANIFEST.json',{str(p.relative_to(root)):check.sha(p) for p in sorted(root.rglob('*')) if p.is_file()})


def verify(root, execution=True):
    for name,digest in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        if check.sha(root/name)!=digest:raise ValueError('input drift '+name)
    contract=json.loads((root/'contract.json').read_text())
    if execution and (check.sha(__file__)!=contract['runner_sha256'] or check.sha(CHECKER)!=contract['checker_sha256']):
        raise ValueError('runner/checker drift')


def evas(root):
    verify(root)
    if (root/'EVAS_STARTED.json').exists(): raise ValueError('reuse forbidden')
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import Instance,compile_sources,transient
    kernel=ROOT/'evas/rust_core/target/debug/evas-kernel'
    check.dump(root/'EVAS_STARTED.json',dict(binary_sha256=check.sha(kernel),source_sha256={
        str(p.relative_to(ROOT)):check.sha(p) for directory,pattern in [('evas/src','*.py'),('evas/rust_core/src','*.rs')]
        for p in (ROOT/directory).rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['name']
        # Negative controls test the benchmark grader on its reference backend.
        if c['kind']=='calibration' and c['family']!='equivalent':continue
        try:
            params={} if c['kind']=='diagnostic' else dict(lower=c['lo'],upper=c['hi'],initial_voltage=c['initial'],direction=c['direction'],ttol=c['ttol'],vtol=c['vtol'])
            program=compile_sources({'dut.va':(work/'dut.va').read_text()},[Instance('dut','triangle',dict(ctl='ctl',z='z',count='count',r='0'),params)])
            times=sorted({0.,c['stop'],*[i*c['maxstep'] for i in range(int(c['stop']/c['maxstep'])+1)]})
            result=transient(program,{'ctl':c['control']},times,stop=c['stop'],max_step=c['maxstep'],kernel=kernel,vabstol=c['evas_vabstol'],reltol=0)
            check.dump(work/'evas.json',result)
            print(c['name'],'ok',flush=True)
        except Exception as error:
            check.dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['name'],str(error),flush=True)


def spectre(root,binary):
    verify(root)
    if (root/'SPECTRE_STARTED.json').exists():raise ValueError('reuse forbidden')
    version=subprocess.run([binary,'-W'],capture_output=True,text=True,timeout=15,check=True)
    check.dump(root/'SPECTRE_STARTED.json',dict(binary_sha256=check.sha(binary),version=version.stdout.strip()))
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['name']
        record=check.execute(binary,work)
        check.dump(work/'spectre-execution.json',record)
        print(c['name'],record,flush=True)
        if 'SPECTRE-209' in (work/'stdout.log').read_text(errors='replace'):
            raise RuntimeError('license unavailable; remaining cases not attempted')


def assess(rows,c,events=None):
    if c['kind']=='diagnostic' and c['family']!='passive':
        c=dict(c,control=[[0,1],[c['stop'],1]])
    if c['oracle']=='triangle':return check.evaluate(rows,c,events)
    # Passive integral is t-t^2/2; strict roots are 1/2 and 3/2.
    if len(rows)<3 or rows[0]['time']!=0 or abs(rows[-1]['time']-c['stop'])>1e-12:
        raise ValueError('incomplete interval')
    if any(not math.isfinite(v) for row in rows for v in row.values()):raise ValueError('nonfinite')
    observed=[];old=0
    for row in rows:
        n=round(row['count'])
        if abs(n-row['count'])>c['wave_atol']:raise ValueError('noninteger')
        if n!=old:
            if n!=old+1:raise ValueError('count jump')
            observed.append(row['time']);old=n
        if all(abs(row['time']-r)>c['time_atol'] for r in [.5,1.5]) and n!=sum(row['time']>r for r in [.5,1.5]):
            raise ValueError('wrong count')
    actual=observed if events is None else events
    if len(observed)!=2 or len(actual)!=2:raise ValueError('event count')
    if any(b['time']<a['time'] or b['time']-a['time']>c['maxstep']*(1+1e-7) for a,b in zip(rows,rows[1:])):raise ValueError('time grid')
    wave=max(abs(r['z']-(r['time']-r['time']**2/2)) for r in rows)
    timing=max(abs(a-b) for a,b in zip(actual,[.5,1.5]))
    return dict(passed=wave<=c['wave_atol'] and timing<=c['time_atol'],max_voltage_error_v=wave,max_event_error_s=timing,expected_events=[.5,1.5],observed_events=actual,rows=len(rows))


def evas_rows(data):
    times=data['transient']['times']
    if len(times)!=len(data['solutions']):raise ValueError('EVAS time/solution length mismatch')
    return [dict(time=t,**dict(zip(data['nodes'],r['voltages']))) for t,r in zip(times,data['solutions'])]


def analyze(root,output):
    verify(root, execution=False)
    if output.exists():raise ValueError('analysis output already exists')
    # This module only parses logs; no archived checker import side effects.
    import report as report_module
    results=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['name']
        row=dict(name=c['name'],kind=c['kind'],family=c['family'],source_sha256=check.sha(work/'dut.va'),netlist_sha256=check.sha(work/'tb.scs'),backends={})
        for backend in ['evas','spectre']:
            path=work/('evas.json' if backend=='evas' else 'psf/tran.tran.tran')
            rec=dict(passed=False)
            if backend=='evas' and (work/'evas-failure.json').exists():rec.update(status='rejected',**json.loads((work/'evas-failure.json').read_text()))
            elif backend=='spectre':
                execfile=work/'spectre-execution.json'
                rec['execution']=json.loads(execfile.read_text()) if execfile.exists() else None
                log=work/'spectre.log'
                try:
                    rec['effective_settings']=report_module.settings(log.read_text(errors='replace')) if log.exists() else {}
                except ValueError as error:rec['settings_error']=str(error)
                rec['requested_settings']={k:c[k] for k in ['reltol','vabstol','iabstol','stop','maxstep','method']}
                effective=rec.get('effective_settings',{})
                rec['settings_match']=all(k in effective and (effective[k]==v if isinstance(v,str) else math.isclose(effective[k],v,rel_tol=1e-12,abs_tol=0)) for k,v in rec['requested_settings'].items() if k!='stop')
                rec['stop_audit']='Log stop may be rounded; require final saved time to match requested stop.'
            if path.exists():
                rec['waveform_sha256']=check.sha(path)
                try:
                    events=None
                    if backend=='evas':
                        data=json.loads(path.read_text())
                        rows=evas_rows(data)
                        events=[e['time'] for e in data['transient']['events']]
                    else:rows=check.read_psf(path)
                    if abs(rows[-1]['time']-c['stop'])>1e-12*max(1.,c['stop']):raise ValueError('actual stop does not match requested stop')
                    rec['actual_stop_s']=rows[-1]['time']
                    rec['observed_count']=rows[-1]['count']
                    rec['first_count_changes']=[{k:r[k] for k in ['time','z','count']} for a,r in zip(rows,rows[1:]) if a['count']!=r['count']][:8]
                    rec.update(assess(rows,c,events),status='checked')
                except (ValueError,KeyError,OSError) as error:rec.update(status='failed',reason=str(error))
            elif 'status' not in rec:rec['status']='missing'
            if backend=='spectre' and (not rec.get('settings_match') or not rec['execution'] or rec['execution']['returncode']!=0 or rec['execution']['timeout']):rec['passed']=False
            row['backends'][backend]=rec
        results.append(row)
    check.dump(output,dict(analysis_identity=dict(runner_sha256=check.sha(__file__),checker_sha256=check.sha(CHECKER),settings_parser_sha256=check.sha(Path(__file__).with_name('report.py')),mode='new analysis; execution identities unchanged'),contract=json.loads((root/'contract.json').read_text()),inputs=json.loads((root/'INPUT_MANIFEST.json').read_text()),
        evas_identity=json.loads((root/'EVAS_STARTED.json').read_text()),spectre_identity=json.loads((root/'SPECTRE_STARTED.json').read_text()),results=results,
        availability='Inputs and tools in repository; raw logs and waveforms retained locally/on authorized host, not publicly downloadable.'))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['cases','prepare','evas','spectre','analyze']);p.add_argument('root',type=Path);p.add_argument('--binary');p.add_argument('--output',type=Path);p.add_argument('--group',choices=['benchmark'])
    a=p.parse_args()
    if a.action=='cases':check.dump(a.root,bench_cases())
    elif a.action=='prepare':prepare(a.root,a.group)
    elif a.action=='evas':evas(a.root)
    elif a.action=='spectre':spectre(a.root,a.binary)
    else:analyze(a.root,a.output)

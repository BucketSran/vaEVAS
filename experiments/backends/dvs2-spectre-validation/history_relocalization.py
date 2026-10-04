"""Bounded development comparison of event-mutated integral cross calendars.

Freeze with prepare, run EVAS locally and Spectre on the explicitly chosen host,
then analyze each backend against the same piecewise analytic reference.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
WAVE_ALLOWANCE = 1e-6
TIME_ALLOWANCE = 2e-7
STEPS = {'base': .02, 'fine': .002}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def specs():
    families = [('faster', 2., [.5]), ('slower', .5, [1.25]),
                ('stopped', 0., []), ('reversed', -1., []),
                ('oscillator', None, [.5, 1.5, 2.5]),
                ('nonexact', None, [1/3]), ('threshold', None, [.75])]
    return [dict(id=f'{name}-{profile}', family=name, slope=slope, roots=roots,
                 stop=3. if name == 'oscillator' else 2., maxstep=step)
            for name, slope, roots in families for profile, step in STEPS.items()]


def source(c):
    if c['family'] == 'oscillator':
        body = '''@(initial_step) begin slope=1; n=0; end
V(z,r)<+idt(slope,0);
@(cross((V(z,r)-.5)*(V(z,r)+.5),0,1e-9,1e-8)) begin slope=-slope; n=n+1; end'''
    elif c['family'] == 'nonexact':
        body = '''@(initial_step) begin slope=3; n=0; end
V(z,r)<+idt(slope,0);
@(cross(V(z,r)-1,1,1e-9,1e-8)) begin slope=1; n=n+1; end'''
    elif c['family'] == 'threshold':
        body = '''@(initial_step) begin slope=.125; n=0; end
@(timer(.25,0,1e-12)) slope=.28125;
V(z,r)<+idt(V(u,r),0);
@(cross(V(z,r)-slope,1,1e-9,1e-8)) n=n+1;'''
    else:
        body = f'''@(initial_step) begin slope=1; n=0; end
@(timer(.25,0,1e-12)) slope={c['slope']};
V(z,r)<+idt(slope,0);
@(cross(V(z,r)-.75,1,1e-9,1e-8)) n=n+1;'''
    text = '''`include "disciplines.vams"
module m(u,y,z,r);
input u; output y,z; inout r; electrical u,y,z,r;
real slope; integer n;
analog begin
''' + body + '\nV(y,r)<+n;\nend\nendmodule\n'
    # Spectre requires the leading zero in real literals (0.25, not .25).
    return re.sub(r'(?<![\w.])\.(\d)', r'0.\1', text)


def reference(c, t):
    f = c['family']
    if f == 'threshold': return t*t/2
    if f == 'nonexact': return 3*t if t <= 1/3 else 1+t-1/3
    if f == 'oscillator':
        if t <= .5: return t
        if t <= 1.5: return 1-t
        if t <= 2.5: return t-2
        return 3-t
    return t if t <= .25 else .25+c['slope']*(t-.25)


def verify(root):
    for name, identity in json.loads((root/'INPUT_MANIFEST.json').read_text()).items():
        if digest(root/name) != identity: raise ValueError('input drift: '+name)
    if digest(Path(__file__)) != json.loads((root/'contract.json').read_text())['runner_sha256']:
        raise ValueError('runner changed since inputs were frozen')


def prepare(root):
    root.mkdir(parents=True, exist_ok=False)
    cases = specs()
    dump(root/'conditions.json', cases)
    dump(root/'CHECKER_IDENTITY.json', {str(p.relative_to(ROOT)):digest(p) for p in [
        Path(__file__), Path(__file__).with_name('cross_touch.py'),
        Path(__file__).with_name('report.py'),
        ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py',
        ROOT/'experiments/archive/dvs2-starter-pilot/suite.py']})
    dump(root/'contract.json', dict(denominator=len(cases), runner_sha256=digest(Path(__file__)),
        wave_allowance_v=WAVE_ALLOWANCE, event_time_allowance_s=TIME_ALLOWANCE,
        expected='Independent piecewise integrals and hand-computed strict crossings.',
        spectre=dict(reltol=1e-8,vabstol=1e-10,iabstol=1e-14,method='traponly'),
        evas=dict(vabstol=1e-8,reltol=0), timeout_s=90, license_timeout_s=30,
        limits='Development evidence at saved points; assumed observation allowances, not continuous-time qualification or performance comparison.'))
    for c in cases:
        work = root/c['id']; work.mkdir()
        (work/'dut.va').write_text(source(c))
        (work/'tb.scs').write_text(f'''simulator lang=spectre
ahdl_include "dut.va"
Vu (u 0) vsource type=pwl wave=[0 0 {c['stop']} {c['stop']}]
Xdut (u y z 0) m
simulatorOptions options reltol=1e-8 vabstol=1e-10 iabstol=1e-14
tran tran stop={c['stop']} step={c['maxstep']} maxstep={c['maxstep']} method=traponly
save u y z
''')
    dump(root/'INPUT_MANIFEST.json', {str(p.relative_to(root)):digest(p)
        for p in sorted(root.rglob('*')) if p.is_file()})


def run_evas(root):
    verify(root)
    if (root/'EVAS_STARTED.json').exists(): raise ValueError('use a new run identity')
    sys.path.insert(0, str(ROOT/'evas/src'))
    from evas import Instance, compile_sources, transient
    kernel = ROOT/'evas/rust_core/target/debug/evas-kernel'
    dump(root/'EVAS_STARTED.json', dict(kernel_sha256=digest(kernel), source_sha256={
        str(p.relative_to(ROOT)):digest(p) for folder, pattern in [('evas/src','*.py'),('evas/rust_core/src','*.rs')]
        for p in (ROOT/folder).rglob(pattern)}))
    for c in json.loads((root/'conditions.json').read_text()):
        work = root/c['id']
        try:
            program = compile_sources({'dut.va':(work/'dut.va').read_text()},
                [Instance('dut','m',dict(u='u',y='y',z='z',r='0'),{})])
            times = sorted({0.,c['stop'],*[i*c['maxstep'] for i in range(int(c['stop']/c['maxstep'])+1)],
                            *[r+d for r in c['roots'] for d in [-1e-6,1e-6]]})
            result = transient(program, {'u':[[0,0],[c['stop'],c['stop']]]}, times,
                stop=c['stop'],max_step=c['maxstep'],kernel=kernel,vabstol=1e-8,reltol=0)
            dump(work/'evas.json', result)
            print(c['id'], 'ok', flush=True)
        except Exception as error:
            dump(work/'evas-failure.json',dict(type=type(error).__name__,message=str(error)))
            print(c['id'], str(error), flush=True)


def run_spectre(root, binary, scripts):
    verify(root)
    if (root/'SPECTRE_STARTED.json').exists(): raise ValueError('use a new run identity')
    if not scripts or any(not re.fullmatch(r'/[A-Za-z0-9_./-]+',p) for p in [binary,*scripts]):
        raise ValueError('unsupported tool path')
    setup='\n'.join('source '+s for s in scripts)+'\n'
    dump(root/'SPECTRE_STARTED.json', dict(binary_sha256=digest(Path(binary)),setup_sha256=[digest(Path(s)) for s in scripts]))
    version = subprocess.run(['/bin/csh','-f','-c',setup+binary+' -W'],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
    (root/'version.log').write_text(version.stdout)
    version.check_returncode()
    blocked = False
    for c in json.loads((root/'conditions.json').read_text()):
        work = root/c['id']; start = time.monotonic()
        if blocked:
            dump(work/'spectre-execution.json', dict(returncode=None,timeout=False,
                status='not_attempted',reason='earlier configuration could not obtain a license'))
            continue
        (work/'run.csh').write_text(setup+f'{binary} -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
        with (work/'stdout.log').open('w') as output:
            process = subprocess.Popen(['/bin/csh','-f','run.csh'],cwd=work,
                stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                record = dict(returncode=process.wait(timeout=90),timeout=False)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
                record = dict(returncode=None,timeout=True)
        if (work/'spectre.log').exists() and 'SPECTRE-209' in (work/'spectre.log').read_text():
            record.update(status='infrastructure_blocked',reason='SPECTRE-209: license unavailable')
            blocked = True
        dump(work/'spectre-execution.json', dict(record,elapsed_s=time.monotonic()-start))
        print(c['id'],record,flush=True)


def inspect(rows, c, event_times=None):
    if len(rows)<3: raise ValueError('missing waveform')
    if any(not math.isfinite(row[k]) for row in rows for k in ['time','u','y','z']):
        raise ValueError('nonfinite waveform')
    if rows[0]['time'] != 0 or abs(rows[-1]['time']-c['stop'])>1e-12:
        raise ValueError('incomplete time domain')
    if any(b['time']<a['time'] for a,b in zip(rows,rows[1:])): raise ValueError('unordered waveform')
    max_gap = max(b['time']-a['time'] for a,b in zip(rows,rows[1:]))
    if max_gap > c['maxstep']*(1+1e-8): raise ValueError('sparse waveform')
    u_error = max(abs(row['u']-row['time']) for row in rows)
    z_error = max(abs(row['z']-reference(c,row['time'])) for row in rows)
    observed = []; old=0
    for row in rows:
        count = round(row['y'])
        if abs(row['y']-count)>WAVE_ALLOWANCE: raise ValueError('noninteger count')
        if count != old:
            if count != old+1: raise ValueError('lost, reversed or grouped events')
            observed.append(row['time']); old=count
        distance = min([abs(row['time']-r) for r in c['roots']],default=math.inf)
        if distance>TIME_ALLOWANCE and count!=sum(row['time']>r for r in c['roots']):
            raise ValueError('incorrect count away from event window')
    if len(observed) != len(c['roots']): raise ValueError('incorrect total event count')
    # EVAS exposes certified events; sparse output samples only check the state.
    actual = observed if event_times is None else event_times
    if len(actual) != len(c['roots']): raise ValueError('incorrect event record count')
    t_error=max([abs(a-b) for a,b in zip(actual,c['roots'])],default=0.)
    return dict(pass_=u_error<=WAVE_ALLOWANCE and z_error<=WAVE_ALLOWANCE and t_error<=TIME_ALLOWANCE,
        rows=len(rows),events=actual,max_input_error_v=u_error,max_history_error_v=z_error,max_event_error_s=t_error)


def analyze(root, output):
    verify(root)
    for name, identity in json.loads((root/'CHECKER_IDENTITY.json').read_text()).items():
        if digest(ROOT/name) != identity: raise ValueError('checker dependency drift: '+name)
    from cross_touch import read_waveform, settings
    records=[]
    for c in json.loads((root/'conditions.json').read_text()):
        work=root/c['id']
        for backend in ['evas','spectre']:
            r=dict(id=c['id'],backend=backend)
            try:
                events=None
                if backend=='evas':
                    path=work/'evas.json'; result=json.loads(path.read_text())
                    rows=[dict(zip(result['nodes'],s['voltages']),time=t) for t,s in zip(result['transient']['times'],result['solutions'])]
                    # Timers are not count events. All cross records have source kind.
                    events=[e['time'] for e in result['transient']['events'] if e['kind']=='cross']
                else:
                    execution=json.loads((work/'spectre-execution.json').read_text())
                    if execution['returncode']!=0 or execution['timeout']:
                        raise ValueError(execution.get('reason','Spectre execution failed'))
                    path=work/'psf/tran.tran.tran';rows=read_waveform(path,'spectre')
                    actual=settings((work/'spectre.log').read_text())
                    requested=dict(reltol=1e-8,vabstol=1e-10,iabstol=1e-14,method='traponly',step=c['maxstep'],maxstep=c['maxstep'])
                    for k,v in requested.items():
                        if (actual[k]!=v if isinstance(v,str) else not math.isclose(actual[k],v,rel_tol=1e-6)):
                            raise ValueError('effective setting mismatch: '+k)
                    r['effective_settings']=actual
                r.update(inspect(rows,c,events),waveform_sha256=digest(path),status='analyzed')
            except (ValueError,KeyError,OSError) as error:
                r.update(status='failed_or_missing',pass_=False,reason=str(error))
            records.append(r)
    dump(output,dict(records=records,contract=json.loads((root/'contract.json').read_text()),
        checker_identity=json.loads((root/'CHECKER_IDENTITY.json').read_text()),
        input_manifest_sha256=digest(root/'INPUT_MANIFEST.json'),
        evas_identity=json.loads((root/'EVAS_STARTED.json').read_text()),
        spectre_identity=json.loads((root/'SPECTRE_STARTED.json').read_text()),
        spectre_version=(root/'version.log').read_text().strip(),
        raw_availability='local-only ignored run directory; models and runner are repository-contained'))
    for r in records: print(r['id'],r['backend'],r['pass_'],r.get('reason',r.get('max_history_error_v')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','evas','spectre','analyze']);p.add_argument('root',type=Path)
    p.add_argument('--binary');p.add_argument('--setup',action='append');p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.root)
    elif a.action=='evas':run_evas(a.root)
    elif a.action=='spectre':run_spectre(a.root,a.binary,a.setup)
    else:analyze(a.root,a.output)

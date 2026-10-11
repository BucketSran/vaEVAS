"""Freeze and assess issue #66 C3 fixed two-stage slew; no DUT-derived oracle."""
from fractions import Fraction as F
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE = '''`include "disciplines.vams"
module m(u,y,r); input u; output y; inout r; electrical u,y,r,h;
analog begin
V(h,r)<+slew(V(u,r),0.5,-0.5);
V(y,r)<+slew(V(h,r),0.25,-0.25);
end endmodule
'''
CASES = {'ramp': [[0, 0], [4, 4]],
         'catch': [[0, 0], [4, 4], [20, 4]],
         'reverse': [[0, 0], [2, 4], [4, -4], [24, -4]]}
BUDGET = 1e-6

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')

def expected(case, time):
    t = F(time)
    if case == 'ramp':
        return dict(u=t, h=t/2, y=t/4)
    if case == 'catch':
        return dict(u=min(t,F(4)), h=min(t/2,F(4)), y=min(t/4,F(4)))
    return dict(u=2*t if t <= 2 else max(F(-4),12-4*t),
                h=t/2 if t <= F(8,3) else max(F(-4), F(8,3)-t/2),
                y=t/4 if t <= F(32,9) else max(F(-4), F(16,9)-t/4))

def assess(case, rows):
    errors = {k: 0. for k in ('u','h','y')}
    failures = []
    stop = CASES[case][-1][0]
    if not rows or rows[0]['time'] != 0 or rows[-1]['time'] != stop:
        failures.append('endpoint coverage')
    if any(a['time'] >= b['time'] for a,b in zip(rows,rows[1:])):
        failures.append('time order')
    for row in rows:
        if not all(math.isfinite(row[k]) for k in ('time','u','h','y')):
            failures.append('nonfinite'); continue
        if not 0 <= row['time'] <= stop:
            failures.append('time range'); continue
        truth = expected(case,row['time'])
        for k in errors:
            errors[k] = max(errors[k],float(abs(F(row[k])-truth[k])))
    return dict(passed=not failures and all(e <= BUDGET for e in errors.values()),
                maximum_error_V=errors, failures=sorted(set(failures)), rows=len(rows))

def calibrate():
    controls=[]
    for case, points in CASES.items():
        grid = sorted(set([0,1,2,3,4,points[-1][0]]))
        good = [dict(time=t,**{k:float(v) for k,v in expected(case,t).items()}) for t in grid]
        assert assess(case,good)['passed']
        for fault in ('output', 'inner_history', 'missing_end', 'nonfinite', 'duplicate_time'):
            bad=copy.deepcopy(good)
            if fault == 'output': bad[2]['y'] += 10*BUDGET
            elif fault == 'inner_history': bad[2]['h'] += 10*BUDGET
            elif fault == 'missing_end': bad.pop()
            elif fault == 'nonfinite': bad[2]['y'] = float('nan')
            else: bad.insert(1,bad[0].copy())
            assert not assess(case,bad)['passed'], (case,fault)
            controls.append(case+':'+fault)
    return dict(positive_cases=3, negative_controls_rejected=controls)

def freeze(output, refinement=False):
    output.mkdir(parents=True,exist_ok=False)
    cases = {'reverse': CASES['reverse']} if refinement else CASES
    profiles = ([('tolerance',1e-9,1e-11,.01),('local',1e-9,1e-11,.01)] if refinement
                else [('base',1e-7,1e-9,.01),('tight',1e-9,1e-11,.0005)])
    for case, points in cases.items():
        for profile, reltol, atol, step in profiles:
            work=output/(case+'-'+profile); work.mkdir()
            (work/'dut.va').write_text(SOURCE)
            settings=dict(stop_s=points[-1][0],maxstep_s=step,reltol=reltol,vabstol_V=atol,
                          iabstol_A=1e-15,method='traponly',errpreset='conservative',strobe='none')
            dynamic = ''
            if profile == 'local':
                # Independently derived slope changes; refine only the solver grid.
                schedule = [[0.,step]]
                for root in (F(8,3),F(32,9),F(40,3),F(208,9)):
                    schedule.extend([[float(root-F(1,1000)),1e-7],
                                     [float(root+F(1,1000)),step]])
                settings['maxstep_schedule_s'] = schedule
                vector = ' '.join(format(x,'.17g') for p in schedule for x in p)
                dynamic = f' param=maxstep param_vec=[{vector}] param_step=0'
            save(work/'requested_settings.json',settings)
            wave=' '.join(str(x) for p in points for x in p)
            deck=('simulator lang=spectre\nahdl_include "dut.va"\n'
                  f'Vu (u 0) vsource type=pwl wave=[{wave}]\ndut (u y 0) m\n'
                  f'simulatorOptions options precision="%.17g" reltol={reltol:.17g} vabstol={atol:.17g} iabstol=1e-15\n'
                  f'tran tran stop={points[-1][0]} maxstep={step:.17g} errpreset=conservative method=traponly compression=no skipcount=1{dynamic}\n'
                  'save u y dut.h\n')
            (work/'tb.scs').write_text(deck)
            save(work/'case.json',dict(case=case,inputs={'u':points},budget_V=BUDGET,
                 selection='First profile meeting the independent 1 uV observed-voltage budget; keep both outcomes.',
                 observations='All native times, exact endpoints, no boundary exclusions; sampled evidence, not a whole-time theorem.'))
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})

def analyze(inputs, raw, output, kernel):
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import compile_sources, Instance, transient
    output.mkdir(parents=True,exist_ok=False)
    for directory in (inputs,raw):
        manifest=json.loads((directory/'MANIFEST.json').read_text())
        if not manifest: raise ValueError('empty manifest')
        for name,digest in manifest.items():
            if sha(directory/name) != digest: raise ValueError('changed '+str(directory/name))
    results=[]
    for work in sorted(p for p in inputs.iterdir() if p.is_dir()):
        case=work.name.rsplit('-',1)[0]
        record=json.loads((raw/work.name/'RESULT.json').read_text())
        # Failed executions are retained as such; they never become waveform passes.
        if not (raw/work.name/'rows.json').exists():
            results.append(dict(case=work.name,execution=record,passed=False));continue
        source=(work/'dut.va').read_text()
        assert sha(work/'dut.va') == record['source_sha256'] == sha(raw/work.name/'dut.va')
        assert sha(work/'tb.scs') == record['deck_sha256'] == sha(raw/work.name/'tb.scs')
        native=json.loads((raw/work.name/'rows.json').read_text())
        grid=[r['time'] for r in native]
        spectral=[dict(time=r['time'],u=r['u'],h=r['dut.h'],y=r['y']) for r in native]
        sr=assess(case,spectral)
        # Out-of-range native points are a reference failure, never clamped for EVAS.
        if any(not 0 <= t <= CASES[case][-1][0] for t in grid):
            results.append(dict(case=work.name,spectre=sr,evas=None,execution=record));continue
        program=compile_sources({'dut.va':source},[Instance('dut','m',dict(u='u',y='y',r='0'))])
        response=transient(program,{'u':CASES[case]},grid,stop=CASES[case][-1][0],
                           max_step=1, vabstol=1e-10,reltol=0,kernel=kernel)
        save(output/(work.name+'-evas.json'),response)
        ev=[]
        for t,row in zip(grid,response['solutions']):
            v=dict(zip(response['nodes'],row['voltages']))
            ev.append(dict(time=t,u=v['u'],h=v['dut:h'],y=v['y']))
        assert len(ev)==len(native) and response['transient']['times']==grid
        results.append(dict(case=work.name,spectre=sr,evas=assess(case,ev),
            same_time_maximum_difference_V={k:max(abs(a[k]-b[k]) for a,b in zip(ev,spectral)) for k in ('u','h','y')},
            source_sha256=sha(work/'dut.va'),raw_sha256=record['raw_sha256'],
            native_rows_sha256=sha(raw/work.name/'rows.json'),evas_response_sha256=sha(output/(work.name+'-evas.json')),
            requested_settings=json.loads((work/'requested_settings.json').read_text()),effective_settings=record['effective_settings']))
    summary=dict(calibration=calibrate(),checker_sha256=sha(Path(__file__)),kernel_sha256=sha(kernel),
                 inputs_manifest_sha256=sha(inputs/'MANIFEST.json'),raw_manifest_sha256=sha(raw/'MANIFEST.json'),
                 tool_identity=json.loads((raw/'TOOL_IDENTITY.json').read_text()),results=results)
    save(output/'summary.json',summary)
    print(json.dumps([dict(case=r['case'],spectre=r.get('spectre'),evas=r.get('evas')) for r in results],indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['freeze','freeze-refinement','analyze','calibrate'])
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--raw',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--kernel',type=Path)
    args=parser.parse_args()
    if args.mode in ('freeze','freeze-refinement'): freeze(args.output,args.mode=='freeze-refinement')
    elif args.mode=='calibrate': print(json.dumps(calibrate(),indent=2))
    else: analyze(args.inputs,args.raw,args.output,args.kernel)

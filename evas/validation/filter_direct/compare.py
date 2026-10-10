"""Freeze and assess issue #66 C4 source-polynomial direct filter; no DUT-derived oracle."""
from decimal import Decimal as D, localcontext
from pathlib import Path
import argparse
import copy
import hashlib
import json
import math
import sys

ROOT = Path(__file__).resolve().parents[3]
SOURCE = """`include "disciplines.vams"
module m(u,y,r); input u; output y; inout r; electrical u,y,r;
analog begin
V(y,r)<+laplace_nd(pow(V(u,r),2),'{1,1},'{2,1});
end endmodule
"""
CASES = {'ramp': [[0, 0], [2, 2]],
         'reverse': [[0, 1], [.5, 2], [1, -1], [2, 1]],
         'nondyadic': [[0, 0], [2, 2]]}
BUDGET = 1e-6

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')

def expected(case, time):
    # Independent convolution integral for H=(1+s)/(2+d1*s), w=u^2.
    # On each PWL segment, x'=w-lambda*x and y=D*w+C*x.
    # Evaluate the closed antiderivative at 60 decimal digits. No EVAS rows.
    with localcontext() as ctx:
        ctx.prec = 60
        d1 = D(3 if case == 'nondyadic' else 1)
        rate = 2/d1
        direct = 1/d1
        gain = 1/d1-direct*rate
        source = CASES[case]
        x = D(source[0][1])**2/rate
        for (start, initial), (end, final) in zip(source, source[1:]):
            dt = D(min(time, end))-D(start)
            slope = (D(final)-D(initial))/(D(end)-D(start))
            initial = D(initial)
            u = initial+slope*dt
            def particular(v):
                return v*v/rate-2*slope*v/rate**2+2*slope*slope/rate**3
            x = particular(u)+(x-particular(initial))*(-rate*dt).exp()
            if time <= end: break
        return dict(u=u, y=direct*u*u+gain*x)

def assess(case, rows):
    errors = {k: 0. for k in ('u','y')}
    failures = []
    stop = CASES[case][-1][0]
    if not rows or rows[0]['time'] != 0 or rows[-1]['time'] != stop:
        failures.append('endpoint coverage')
    if not all(t in {r['time'] for r in rows} for t, _ in CASES[case]):
        failures.append('PWL corner coverage')
    if any(a['time'] >= b['time'] for a,b in zip(rows,rows[1:])):
        failures.append('time order')
    for row in rows:
        if not all(math.isfinite(row[k]) for k in ('time','u','y')):
            failures.append('nonfinite'); continue
        if not 0 <= row['time'] <= stop:
            failures.append('time range'); continue
        truth = expected(case,row['time'])
        for k in errors:
            errors[k] = max(errors[k],float(abs(D(row[k])-truth[k])))
    return dict(passed=not failures and all(e <= BUDGET for e in errors.values()),
                maximum_error_V=errors, failures=sorted(set(failures)), rows=len(rows))

def calibrate():
    controls=[]
    for case, points in CASES.items():
        grid = [0, .125, .5, .75, 1, 1.5, 2]
        good = [dict(time=t,**{k:float(v) for k,v in expected(case,t).items()}) for t in grid]
        assert assess(case,good)['passed']
        for fault in ('output', 'input', 'missing_end', 'nonfinite', 'duplicate_time'):
            bad=copy.deepcopy(good)
            if fault == 'output': bad[2]['y'] += 10*BUDGET
            elif fault == 'input': bad[2]['u'] += 10*BUDGET
            elif fault == 'missing_end': bad.pop()
            elif fault == 'nonfinite': bad[2]['y'] = float('nan')
            else: bad.insert(1,bad[0].copy())
            assert not assess(case,bad)['passed'], (case,fault)
            controls.append(case+':'+fault)
        if len(points) > 2:
            bad = [row for row in good if row['time'] != points[1][0]]
            assert not assess(case,bad)['passed']
            controls.append(case+':missing_PWL_corner')
    return dict(positive_cases=3, negative_controls_rejected=controls)

def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    for case, points in CASES.items():
        for profile, reltol, atol, step in [('base',1e-7,1e-9,.01),('tight',1e-9,1e-11,.001)]:
            work=output/(case+'-'+profile); work.mkdir()
            source = SOURCE.replace("'{2,1}", "'{2,3}") if case == 'nondyadic' else SOURCE
            (work/'dut.va').write_text(source)
            settings=dict(stop_s=2,maxstep_s=step,reltol=reltol,vabstol_V=atol,
                          iabstol_A=1e-15,method='traponly',errpreset='conservative',strobe='none')
            save(work/'requested_settings.json',settings)
            wave=' '.join(str(x) for p in points for x in p)
            deck=('simulator lang=spectre\nahdl_include "dut.va"\n'
                  f'Vu (u 0) vsource type=pwl wave=[{wave}]\ndut (u y 0) m\n'
                  f'simulatorOptions options precision="%.17g" reltol={reltol:.17g} vabstol={atol:.17g} iabstol=1e-15\n'
                  f'tran tran stop=2 maxstep={step:.17g} errpreset=conservative method=traponly compression=no skipcount=1\n'
                  'save u y\n')
            (work/'tb.scs').write_text(deck)
            save(work/'case.json',dict(case=case,inputs={'u':points},budget_V=BUDGET,
                 selection='First profile meeting independent 1 uV voltage budget; retain both outcomes.',
                 observations='All native times and exact endpoints; no exclusions; finite observation claim.'))
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
        execution = record['execution']
        if (execution.get('returncode') != 0 or execution.get('timeout')
                or not execution.get('cleanup', {}).get('complete')
                or record.get('analysis_failure')
                or not (raw/work.name/'rows.json').exists()):
            results.append(dict(case=work.name,execution=record,passed=False));continue
        source=(work/'dut.va').read_text()
        assert sha(work/'dut.va') == record['source_sha256'] == sha(raw/work.name/'dut.va')
        assert sha(work/'tb.scs') == record['deck_sha256'] == sha(raw/work.name/'tb.scs')
        native=json.loads((raw/work.name/'rows.json').read_text())
        grid=[r['time'] for r in native]
        spectral=[dict(time=r['time'],u=r['u'],y=r['y']) for r in native]
        sr=assess(case,spectral)
        # Out-of-range native points are a reference failure, never clamped for EVAS.
        if any(not 0 <= t <= CASES[case][-1][0] for t in grid):
            results.append(dict(case=work.name,spectre=sr,evas=None,execution=record));continue
        program=compile_sources({'dut.va':source},[Instance('dut','m',dict(u='u',y='y',r='0'))])
        response=transient(program,{'u':CASES[case]},grid,stop=CASES[case][-1][0],
                           max_step=.125, vabstol=1e-9,reltol=0,kernel=kernel,timeout=180)
        save(output/(work.name+'-evas.json'),response)
        ev=[]
        for t,row in zip(grid,response['solutions']):
            v=dict(zip(response['nodes'],row['voltages']))
            ev.append(dict(time=t,u=v['u'],y=v['y']))
        assert len(ev)==len(native) and response['transient']['times']==grid
        results.append(dict(case=work.name,spectre=sr,evas=assess(case,ev),
            same_time_maximum_difference_V={k:max(abs(a[k]-b[k]) for a,b in zip(ev,spectral)) for k in ('u','y')},
            source_sha256=sha(work/'dut.va'),raw_sha256=record['raw_sha256'],
            native_rows_sha256=sha(raw/work.name/'rows.json'),evas_response_sha256=sha(output/(work.name+'-evas.json')),
            requested_settings=json.loads((work/'requested_settings.json').read_text()),effective_settings=record['effective_settings']))
        print(work.name, 'Spectre:', sr['passed'], 'EVAS:', results[-1]['evas']['passed'], flush=True)
    summary=dict(calibration=calibrate(),checker_sha256=sha(Path(__file__)),kernel_sha256=sha(kernel),
                 inputs_manifest_sha256=sha(inputs/'MANIFEST.json'),raw_manifest_sha256=sha(raw/'MANIFEST.json'),
                 tool_identity=json.loads((raw/'TOOL_IDENTITY.json').read_text()),results=results)
    save(output/'summary.json',summary)
    print(json.dumps([dict(case=r['case'],spectre=r.get('spectre'),evas=r.get('evas')) for r in results],indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode',choices=['freeze','analyze','calibrate'])
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--raw',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--kernel',type=Path)
    args=parser.parse_args()
    if args.mode == 'freeze': freeze(args.output)
    elif args.mode=='calibrate': print(json.dumps(calibrate(),indent=2))
    else: analyze(args.inputs,args.raw,args.output,args.kernel)

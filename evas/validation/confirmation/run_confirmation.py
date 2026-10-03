"""Frozen finite-observation confirmation; independent rational/Decimal answers."""
import argparse
import copy
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'evas/src'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decimal(value):
    if isinstance(value, Q):
        return Decimal(value.numerator) / Decimal(value.denominator)
    return Decimal.from_float(value)


def stimulus(t):
    if t <= Q(3, 4): return 1 + Q(8, 3)*t
    if t <= Q(5, 4): return Q(3)
    if t <= 2: return 3-Q(16, 3)*(t-Q(5, 4))
    return Q(-1)


def expected(name, t):
    if name == 'language': return {'y':16*t}
    if name == 'histories': return {'y':Q(-1,4)+2*t+t*t}
    if name == 'calendar':
        return {'y':1/(Q(4,3)-t) if t<=Q(3,8) else 1/(Q(7,12)+t)}
    if name == 'projected':
        if t<=Q(3,4): y=Q(5,6)+2*t
        elif t<=Q(5,6): y=Q(7,3)+2*(t-Q(3,4))
        elif t<=Q(5,4): y=Q(5,2)
        else: y=max(Q(-5,6), Q(5,2)-Q(3,2)*(t-Q(5,4)))
        return {'y':y, 'd':Q(5,6)*stimulus(max(t-Q(1,8),Q(0)))}
    if name == 'roots': return {'y':Q(int(t>=Q(1,2))+int(t>=Q(3,4)))}
    if name == 'implicit': return {'y':Q(1,4)+t-t*t/2}
    if name == 'reset_filter':
        y=Q(1,8)+t if t<Q(3,8) else Q(1,8) if t<=Q(5,8) else Q(1,8)+t-Q(5,8)
        td=decimal(t)
        return {'y':y, 'f':td-1+(-td).exp()}
    raise ValueError('unknown frozen case')


def grids(case):
    sparse=case['times']
    # Midpoints avoid interpreting an observation at the mathematical root as
    # occurring after a rounded upper-endpoint cross representative.
    dense=sorted(set(sparse+[0,case['stop']]+[(i+.5)*case['stop']/128 for i in range(128)]))
    return {'sparse':sparse, 'dense':dense}


def check(case, times, response, target):
    if response['transient']['times'] != times or len(response['solutions']) != len(times):
        raise ValueError('missing, extra or reordered observations')
    nodes=response['nodes']
    if len(set(nodes)) != len(nodes): raise ValueError('duplicate node identity')
    worst=Decimal(0)
    with localcontext() as context:
        context.prec=80
        for t,row in zip(times,response['solutions'],strict=True):
            voltage=row['voltages']
            if len(voltage)!=len(nodes) or any(not math.isfinite(v) for v in voltage):
                raise ValueError('nonfinite or malformed voltage vector')
            for name, value in expected(case['id'],Q.from_float(float(t))).items():
                reference=decimal(value) if isinstance(value,Q) else value
                # This reference-computation reserve is independent of EVAS.
                error=abs(decimal(voltage[nodes.index(name)])-reference)+Decimal('1e-60')
                worst=max(worst,error)
                if error>target: raise ValueError(f'{name}@{t}: voltage error {error}')
        events=response['transient']['events']
        if len(events)!=len(case['events']): raise ValueError('wrong event count')
        for record,(event,time) in zip(events,case['events'],strict=True):
            nominal=Q(time)
            actual=record['time']
            lo,hi=record.get('observation_time_bounds',[actual,actual])
            if record['event']!=event or not all(math.isfinite(v) for v in (lo,hi,actual)):
                raise ValueError('wrong event identity or nonfinite time')
            if not Q.from_float(lo)<=nominal<=Q.from_float(hi) or not lo<=actual<=hi:
                raise ValueError('event window does not enclose the fixed root')
            if abs(Q.from_float(actual)-nominal)>Q('1e-10'):
                raise ValueError('event exceeds the frozen time target')
    return {'status':'pass','maximum_voltage_error_bound':str(worst),
            'observations':len(times),'events':len(events)}


def calibrate(suite):
    target=Decimal(suite['voltage_target'])
    with localcontext() as context:
        context.prec=80
        for case in suite['cases']:
            times=case['times']
            names=list(expected(case['id'],Q(0)))
            good={'nodes':names, 'solutions':[{'voltages':[float(v) for v in expected(
                case['id'],Q.from_float(float(t))).values()]} for t in times],
                'transient':{'times':times,'events':[{'event':i,'time':float(Q(t)),
                    'observation_time_bounds':[float(Q(t)),float(Q(t))]} for i,t in case['events']]}}
            check(case,times,good,target)
            bad=[]
            voltage=copy.deepcopy(good);voltage['solutions'][-1]['voltages'][0]+=.001;bad.append(voltage)
            nonfinite=copy.deepcopy(good);nonfinite['solutions'][0]['voltages'][0]=math.nan;bad.append(nonfinite)
            missing=copy.deepcopy(good);missing['solutions'].pop();bad.append(missing)
            if case['events']:
                event=copy.deepcopy(good);event['transient']['events'].pop();bad.append(event)
                wrong=copy.deepcopy(good);wrong['transient']['events'][0]['event']=99;bad.append(wrong)
            for response in bad:
                try: check(case,times,response,target)
                except ValueError: pass
                else: raise AssertionError('checker accepted a negative calibration')
    return {'status':'pass','positive_cases':len(suite['cases']),
            'negative_controls':'voltage, NaN, missing observation, event count/identity'}


def run(suite, kernel, out):
    from evas import CompileError, KernelError, Instance, compile_sources, transient
    if suite['denominator']!=len(suite['cases']) or len(suite['variants'])!=2:
        raise ValueError('frozen denominator/variant mismatch')
    frozen=json.loads((HERE/'INPUT_MANIFEST.json').read_text())
    for name,digest in frozen.items():
        path=(HERE/name).resolve()
        if not path.is_relative_to(HERE) or sha(path)!=digest:
            raise ValueError('frozen confirmation asset drift: '+name)
    out.mkdir(parents=True,exist_ok=False)
    def save(name,value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    source={str(p.relative_to(ROOT)):sha(p) for pattern in ('evas/src/**/*.py',
        'evas/rust_core/src/**/*.rs','evas/rust_core/ir/src/**/*.rs',
        'evas/rust_core/Cargo.toml','evas/rust_core/ir/Cargo.toml','evas/rust_core/Cargo.lock')
        for p in ROOT.glob(pattern)}
    save('STARTED.json',{'input_manifest_sha256':sha(HERE/'INPUT_MANIFEST.json'),
        'input_sha256':frozen,'kernel_sha256':sha(kernel),'source_sha256':source,
        'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'python':sys.version,'maximum_attempts':14,'kernel_timeout_seconds':60,
        'settings':{'vabstol':suite['vabstol'],'reltol':suite['reltol']},
        'continuous_time_qualified':False,'formal_dvs_qualification':'I'})
    save('calibration.json',calibrate(suite))
    records=[]
    for case in suite['cases']:
        responses={}
        for variant,times in grids(case).items():
            record={'case':case['id'],'variant':variant}
            try:
                sources={name:(HERE/'cases'/name).read_text() for name in case['models']}
                program=compile_sources(sources,[Instance('dut',case['id'],
                    {p:'0' if p=='r' else p for p in case['ports']})])
                response=transient(program,case['sources'],times,stop=case['stop'],
                    max_step=case['stop'] if variant=='sparse' else case['stop']/32,
                    vabstol=suite['vabstol'],reltol=suite['reltol'],kernel=kernel,timeout=60)
                save(case['id']+'-'+variant+'.json',response)
                responses[variant]=response
                record.update(check(case,times,response,Decimal(suite['voltage_target'])))
            except (CompileError,KernelError,ValueError,RuntimeError,TimeoutError) as error:
                record.update(status='failed',reason=str(error))
            records.append(record)
            print(case['id'],variant,record['status'],flush=True)
        if len(responses)==2:
            dense=responses['dense'];sparse=responses['sparse']
            for t,row in zip(sparse['transient']['times'],sparse['solutions'],strict=True):
                other=dense['solutions'][dense['transient']['times'].index(t)]
                if max(abs(a-b) for a,b in zip(row['voltages'],other['voltages'],strict=True))>float(suite['voltage_target']):
                    records[-1].update(status='failed',reason='query grid changes common observations')
                    break
            if sparse['transient']['events']!=dense['transient']['events']:
                records[-1].update(status='failed',reason='query grid changes certified event history')
    save('RESULTS.json',{'suite':suite['id'],'records':records,
        'passed':sum(r['status']=='pass' for r in records),'attempts':len(records),
        'continuous_time_qualified':False,'formal_dvs_qualification':'I'})
    files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
    save('FILE_MANIFEST.json',files)
    if any(r['status']!='pass' for r in records): raise SystemExit(1)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibrate',action='store_true')
    parser.add_argument('--kernel',type=Path)
    parser.add_argument('--out',type=Path)
    args=parser.parse_args()
    suite=json.loads((HERE/'suite.json').read_text())
    if args.calibrate: print(json.dumps(calibrate(suite))); return
    if args.kernel is None or args.out is None: parser.error('execution requires --kernel and --out')
    run(suite,args.kernel.resolve(),args.out.resolve())


if __name__=='__main__': main()

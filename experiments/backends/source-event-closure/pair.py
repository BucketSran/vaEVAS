"""Reanalyze retained Spectre rows and execute the same DUT with the selected kernel."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
from evas import Instance, compile_sources
from check import assess, event_times

ROOT = Path(__file__).resolve().parents[3]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')

def direct(case, native, rows, contract):
    indexed={row['time']:row['voltages'] for row in rows}
    differences=[];boundaries=[];maximum=0.;compared=0
    events=event_times(case,contract['stop'])
    for row in native:
        time=row['time']
        if not math.isfinite(time) or time not in indexed:
            differences.append(dict(time=str(time),reason='missing finite paired time'));continue
        near=any(abs(time-event)<=contract['acceptance']['event_window_s'] for event in events)
        for node in ['y','z','w','count','flag','mark']:
            a=indexed[time].get(node);b=row['voltages'].get(node)
            if a is None or b is None or not math.isfinite(a) or not math.isfinite(b):
                differences.append(dict(time=time,node=node,reason='missing or nonfinite voltage'));continue
            compared+=1;error=abs(a-b)
            if node in ['y','z','w']:
                maximum=max(maximum,error)
                if error>contract['acceptance']['voltage_absolute_V']:differences.append(dict(time=time,node=node,error=error))
            elif error:
                (boundaries if near else differences).append(dict(time=time,node=node,evas=a,spectre=b))
    return dict(numerical='F' if differences else ('P' if compared else 'I'),compared_values=compared,max_voltage_error_V=maximum,failures=differences,boundary_differences=boundaries)


def stability(base, tight, contract):
    missing=[];bad=[];maximum=0.;compared=0
    for time in contract['times']:
        a=[r['voltages'] for r in base if r['time']==time]
        b=[r['voltages'] for r in tight if r['time']==time]
        if len(a)!=1 or len(b)!=1:missing.append(time);continue
        for node in ['y','z','w']:
            x=a[0].get(node);y=b[0].get(node)
            if x is None or y is None or not math.isfinite(x) or not math.isfinite(y):
                bad.append(dict(time=time,node=node,reason='missing or nonfinite voltage'));continue
            error=abs(x-y);compared+=1;maximum=max(maximum,error)
            if error>contract['acceptance']['reference_stability_absolute_V']:bad.append(dict(time=time,node=node,error=error))
    return dict(coverage='I' if missing else 'P',ambiguous_or_missing=missing,compared_values=compared,max_voltage_error_V=maximum,numerical='F' if bad else ('P' if compared else 'I'),failures=bad)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('reference',type=Path)
    parser.add_argument('output',type=Path)
    parser.add_argument('--kernel',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    contract_path=ROOT/'evas/validation/source-event-closure/contract.json'
    contract=json.loads(contract_path.read_text())
    source_path=contract_path.with_name('dut.va')
    manifest=json.loads((args.reference/'FILE_MANIFEST.json').read_text())
    for name,identity in manifest.items():
        path=args.reference/name
        assert sha(path)==identity['sha256'] and path.stat().st_size==identity['bytes'],name
    normalizer_path=ROOT/'experiments/backends/event-alignment/normalize_psf.py'
    spec=importlib.util.spec_from_file_location('native_psf',normalizer_path)
    normalizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(normalizer)
    records=[];native_rows={}
    source_identity={p:sha(ROOT/p) for p in subprocess.check_output(['git','ls-files','evas/rust_core/src','evas/src/evas'],cwd=ROOT,text=True).splitlines()}
    source_identity['evas/rust_core/src/pwl_local.rs']=sha(ROOT/'evas/rust_core/src/pwl_local.rs')
    kernel_identity=sha(args.kernel)
    executions=json.loads((args.reference/'EXECUTION.json').read_text())
    assert sorted(e['condition'] for e in executions)==sorted(f'{case}-{profile}' for case in contract['cases'] for profile in contract['profiles'])
    for execution in executions:
        name=execution['condition'];case_name,profile=name.rsplit('-',1)
        case=contract['cases'][case_name]
        folder=args.reference/'runs'/name
        assert sha(folder/'dut.va')==sha(source_path)==execution['source_sha256']
        assert sha(folder/'tb.scs')==execution['deck_sha256']
        assert execution['status']=='waveform_available'
        native=normalizer.normalize(folder/execution['waveform'],contract)
        save(args.output/f'{name}.spectre.json',native)
        reference=assess(case,native['rows'],contract)
        times=sorted(set(row['time'] for row in native['rows'] if 0<=row['time']<=contract['stop'])|set(contract['times']))
        program=compile_sources({str(source_path):source_path.read_text()},[Instance('dut','source_closure',dict(zip(['u','y','z','w','count','flag','mark','r'],['u','y','z','w','count','flag','mark','0'])),{'polarity':case['polarity']})])
        request=dict(program=program.to_dict(),driven=['u'],samples=[],transient=dict(pwl=[case['inputs']],output_times=times,stop=contract['stop'],max_step=.005),tolerances=dict(absolute=1e-7,relative=0.))
        save(args.output/f'{name}.request.json',request)
        record=dict(condition=name,reference=reference,native_rows=len(native['rows']),query_count=len(times),psf_sha256=native['psf_sha256'],deck_sha256=execution['deck_sha256'],effective_settings=execution['effective_settings'])
        native_rows[name]=native['rows']
        try:
            run=subprocess.run([str(args.kernel.resolve())],input=json.dumps(request),text=True,capture_output=True,timeout=300)
        except subprocess.TimeoutExpired as error:
            (args.output/f'{name}.stdout').write_bytes(error.stdout or b'')
            (args.output/f'{name}.stderr').write_bytes(error.stderr or b'')
            record.update(execution_returncode=None,execution='timeout',evas={'numerical':'I'},direct={'numerical':'I'})
            records.append(record);save(args.output/f'{name}.assessment.json',record)
            print(json.dumps({'condition':name,'execution':'timeout'}),flush=True)
            continue
        (args.output/f'{name}.stdout').write_text(run.stdout)
        (args.output/f'{name}.stderr').write_text(run.stderr)
        record.update(execution_returncode=run.returncode,execution='completed' if run.returncode==0 else 'rejected',evas={'numerical':'I'},direct={'numerical':'I'})
        if run.returncode==0:
            result=json.loads(run.stdout)
            rows=[dict(time=t,voltages=dict(zip(result['nodes'],solution['voltages']))) for t,solution in zip(times,result['solutions'])]
            assert len(rows)==len(times)
            save(args.output/f'{name}.evas.json',rows)
            record['evas']=assess(case,rows,contract)
            record['direct']=direct(case,native['rows'],rows,contract)
        records.append(record)
        save(args.output/f'{name}.assessment.json',record)
        print(json.dumps({k:record[k] for k in ['condition','execution_returncode','native_rows']}),flush=True)
    convergence=[dict(case=name,**stability(native_rows[name+'-base'],native_rows[name+'-tight'],contract)) for name in contract['cases']]
    assert kernel_identity==sha(args.kernel), 'kernel changed during execution'
    assert all(sha(ROOT/p)==identity for p,identity in source_identity.items()), 'source changed during execution'
    save(args.output/'summary.json',dict(records=records,stability=convergence,kernel_sha256=kernel_identity,source_sha256=sha(source_path),contract_sha256=sha(contract_path),checker_sha256=sha(Path(__file__).with_name('check.py')),analyzer_sha256=sha(Path(__file__)),normalizer_sha256=sha(normalizer_path),source_files=source_identity,reference_manifest_sha256=sha(args.reference/'FILE_MANIFEST.json'),scope='New actual Spectre paired finite behavior, fixed 1uV/2ns criteria. Exact boundary differences remain. Effective-settings qualification remains as recorded; no public raw distribution claim.'))

if __name__=='__main__':main()

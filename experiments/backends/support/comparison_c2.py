"""Re-execute the original filter-to-sampler case; historical grading is unchanged.

This runner preserves both original modules and their original port bindings.
Its additional top module only supplies the common multi-instance fixture.
The old finite checker is reported separately from common Q-tier qualification.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/backends/support'),str(ROOT/'experiments/backends/paper'),
             str(ROOT/'experiments/backends/dvs2-spectre-validation')]
import precision_run as execution
from inputs import BACKENDS, decks, sha, save
from observations import read_native, READER_DEPENDENCIES
from run_suite import conditions
from check_results import check


def load(p):return json.loads(p.read_text())


def card():
    c=next(c for c in conditions() if c['id']=='c2-main')
    modules='\n'.join((ROOT/'evas/validation/cases'/s/'dut.va').read_text() for s in c['source_cards'])
    fixture=('\nmodule c2_fixture(vin,clk,rst,z,vout,r); '
             'input vin,clk,rst; output z,vout; inout r; '
             'electrical vin,clk,rst,z,vout,r; '
             'dvs_v6 filter(vin,z,r); dvs_sampler sampler(z,clk,rst,vout,r); '
             'endmodule\n')
    return dict(id='c2-main',legacy=c,source=modules+fixture,
                source_modules={s:sha(ROOT/'evas/validation/cases'/s/'dut.va') for s in c['source_cards']},
                inputs={n:[[t*1e-6,v] for t,v in pts] for n,pts in c['inputs'].items()},
                binding=dict(top_module='c2_fixture',ports=['vin','clk','rst','z','vout','r'],parameters={}),
                stop_s=4e-6)


def freeze(output):
    output.mkdir(parents=True,exist_ok=False)
    c=card();inputs=dict(c['inputs'],r=[[0.,0.],[c['stop_s'],0.]])
    profiles={p['id']:p for p in load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']}
    settings=dict(profiles['deep'],stop_s=c['stop_s'],maxstep_s=2e-10,spice_maxstep_s=2e-10,
                  target='original c2 finite thresholds; Q qualification reported separately')
    # Preserve the input corners and both sides of every sampling/edge boundary.
    times={i*2e-10 for i in range(20001)}
    for pts in inputs.values():times.update(t for t,v in pts)
    for t in (1.5e-6,2.5e-6,3.5e-6,1.525e-6,2.525e-6,3.525e-6):
        times.update(t+i*2e-12 for i in range(-30,31))
    # Coalesce only the auxiliary grid, retaining each exact declared root.
    critical={0.,c['stop_s'],1.5e-6,2.5e-6,3.5e-6,1.525e-6,2.525e-6,3.525e-6}
    times=sorted(critical|{t for t in times if not any(0<abs(t-q)<1e-15 for q in critical)})
    physical=dict(id=c['id'],stimulus={n:dict(points_s_V=v) for n,v in inputs.items()})
    generated=decks(physical,settings,c['binding'],times,dict(records=[dict(time_s=t) for t in times]))
    plan=[]
    for backend in BACKENDS:
        work=output/'runs'/backend/'c2-main';work.mkdir(parents=True)
        name,text=generated[backend]
        if backend=='spectre':
            text='\n'.join(line+' precision="%.17g" digits=17 notation=sci' if line.startswith('simulatorOptions ') else
                           line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line for line in text.splitlines())+'\n'
        if backend=='gnucap_modelgen':
            text=text.replace('.options numdgt=17 dtmin=1e-15',
                              '.options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9')
        (work/name).write_text(text);(work/'dut.va').write_text(c['source'])
        save(work/'condition.json',c);save(work/'requested_settings.json',settings);save(work/'requested_times.json',times)
        plan.append(dict(backend=backend,label='c2-main',condition='c2-main',work=str(work.relative_to(output)),deck=name))
    save(output/'PLAN.json',plan)
    paths=set(execution.source_files())|{Path(__file__),ROOT/'evas/validation/paper/precision-v2.json',*READER_DEPENDENCIES}
    paths.update((ROOT/'experiments/backends/dvs2-spectre-validation').glob('*.py'))
    paths.update((ROOT/'experiments/archive/dvs2-history-validation').glob('*.py'))
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps(dict(positions=4,times=len(times),manifest_sha256=sha(output/'MANIFEST.json'))))


def run(inputs,output,backend,profile):
    execution.verify(inputs);row=next(r for r in load(inputs/'PLAN.json') if r['backend']==backend)
    output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',dict(selected=[row],limits=execution.LIMITS,input_manifest_sha256=sha(inputs/'MANIFEST.json')))
    tool,env=execution.preflight(backend,load(profile),output,execution.LIMITS)
    save(output/'TOOL_IDENTITY.json',tool);execution.verify_tool(tool,load(profile),env)
    work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
    results=[]
    try:
        result=dict(row,**execution.execute_one(backend,tool,env,work))
        result['directory_budget']=execution.directory_budget(work)
        save(work/'RESULT.json',result);results.append(result)
        print(json.dumps(dict(backend=backend,status=result['status'])),flush=True)
    finally:
        save(output/'EXECUTION.json',results or [dict(row,status='not_run',reason='execution interrupted')])
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):dict(sha256=sha(p),bytes=p.stat().st_size)
                                         for p in sorted(output.rglob('*')) if p.is_file()})


def analyze(lanes,output):
    from precision_readback_audit import verify_lane
    records=[]
    for lane in lanes:
        verify_lane(lane)
        for r in load(lane/'EXECUTION.json'):
            w=lane/'runs'/r['label'];record=dict(backend=r['backend'],execution=r['status'],result_sha256=sha(w/'RESULT.json'))
            if r['status']=='waveform_available':
                rows=read_native(w/r['waveform'],r['backend'])
                record['historical_assessment']=check(rows,load(w/'condition.json')['legacy'])
                record['effective_settings']=execution.effective_settings(w,r['backend'])
                record['common_Q_qualification']='not established by the historical checker'
            records.append(record)
    save(output,dict(schema='c2-reexecution-v1',records=records,checker_sha256=sha(ROOT/'experiments/backends/dvs2-spectre-validation/check_results.py'),
                     history='New execution. Historical model modules, scientific checker and old scores retained.'))


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path)
    r=s.add_parser('run');r.add_argument('inputs',type=Path);r.add_argument('output',type=Path)
    r.add_argument('--backend',choices=BACKENDS,required=True);r.add_argument('--profile',type=Path,required=True)
    a=s.add_parser('analyze');a.add_argument('--lane',action='append',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    elif a.mode=='run':run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve())
    else:analyze(a.lane,a.output)

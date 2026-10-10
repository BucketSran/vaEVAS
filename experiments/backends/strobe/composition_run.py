"""Bounded timer/strobe composition comparison; existing cards stay unchanged."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'experiments/backends/support'),str(ROOT/'evas/validation/strobe')]
import precision_run as run
from precision_report import qualification
from timer_composition import CASES,INTEGRAL,assess,sef
from timer_report import time_coverage
load=run.load
save=run.save
sha=run.sha


def freeze(output, timer_diagnostic=False):
    output.mkdir(parents=True,exist_ok=False);plan=[]
    profiles=load(ROOT/'evas/validation/paper/precision-v1.json')['profiles']
    cases=CASES
    if timer_diagnostic:
        # Additional controls, not replacements for the frozen four failures.
        # Keep the original 100 uV nominal integral and observation grid.
        both=next(p for p in profiles if p['id']=='both')
        profiles=[{**both,'id':'both-TT'+label,'timer_tolerance_s':tt}
                  for label,tt in [('10ps',1e-11),('1ps',1e-12)]]
        cases=[INTEGRAL]
    save(output/'cards.json',{'cases':cases,'profiles':profiles,
                             'timer_tolerance_diagnostic':timer_diagnostic})
    for case in cases:
        integral=case['id']==INTEGRAL['id']
        ports=case['ports'] if integral else ['u','clk','rst',*[p['name']+x for p in case['instances'] for x in 'hefn']]
        stimulus=case['inputs'] if integral else {n:[[t*sef.T,v] for t,v in pts] for n,pts in [('u',sef.INPUT),('clk',sef.CLOCK),('rst',sef.RESET)]}
        times=run.times_for(case) if integral else sef.times(case,True)
        source=case['source'] if integral else sef.source(case)
        binding={'ports':ports,'top_module':case['top'] if integral else 'dut','parameters':case['parameters'] if integral else {}}
        for profile in profiles:
            settings={**profile,'stop_s':sef.STOP,'maxstep_s':sef.T*profile['step_units'],'spice_maxstep_s':sef.T*profile['step_units']}
            current_binding=binding
            if timer_diagnostic:
                current_binding={**binding,'parameters':{**binding['parameters'],'TT':profile['timer_tolerance_s']}}
            generated=run.decks({'id':case['id'],'stimulus':{n:{'points_s_V':v} for n,v in stimulus.items()}},settings,current_binding,times,{'records':[]})
            for backend in ('spectre','evas'):
                label=case['id']+'--'+profile['id'];work=output/'runs'/backend/label;work.mkdir(parents=True)
                filename,text=generated[backend]
                if backend=='spectre':
                    text='\n'.join(line+' precision="%.17g"' if line.startswith('simulatorOptions ') else
                                   line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line
                                   for line in text.splitlines())+'\n'
                (work/filename).write_text(text);(work/'dut.va').write_text(source)
                save(work/'condition.json',case);save(work/'requested_settings.json',settings);save(work/'requested_times.json',times)
                plan.append(dict(condition=case['id'],profile=profile['id'],backend=backend,label=label,work=str(work.relative_to(output))))
    save(output/'PLAN.json',plan)
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})


def verify(inputs):
    for rel,digest in load(inputs/'MANIFEST.json').items():
        p=(inputs/rel).resolve()
        if not p.is_relative_to(inputs.resolve()) or sha(p)!=digest:raise ValueError('composition input drift: '+rel)


def execute(inputs,output,backend,profile_path):
    verify(inputs);output.mkdir(parents=True,exist_ok=False)
    plan=[r for r in load(inputs/'PLAN.json') if r['backend']==backend];results=[]
    save(output/'STARTED.json',dict(limits=run.LIMITS,selected=plan,input_manifest_sha256=sha(inputs/'MANIFEST.json'),profile_sha256=sha(profile_path)))
    profile=load(profile_path)
    try:
        tool,env=run.preflight(backend,profile,output,run.LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            verify(inputs);run.verify_tool(tool,profile,env)
            work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
            result={**row,**run.execute_one(backend,tool,env,work)}
            if result['status']=='waveform_available':
                try:
                    native=run.read_native(work/result['waveform'],backend)
                    result['assessment']=assess(load(work/'condition.json'),native)
                    result['effective_settings']=run.effective_settings(work,backend)
                    result['qualification']=qualification(work,backend,result,native)
                    result['time_coverage']=time_coverage(load(work/'requested_times.json'),native,backend,load(work/'requested_settings.json')['stop_s'])
                    result['verdict']='pass' if result['assessment']['status']=='pass' and result['qualification']['status']=='qualified' and (backend!='evas' or result['time_coverage']['status']=='covered') else 'fail'
                except Exception as exc:result.update(verdict='evidence_insufficient',analysis_error=repr(exc))
            else:result['verdict']='execution_failed'
            result['directory_budget']=run.directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            print(json.dumps({'case':row['label'],'execution':result['status'],'verdict':result['verdict']}),flush=True)
            if result['abort_batch'] or result['directory_budget']['status']!='within_limit':break
    finally:
        recorded={r['label'] for r in results}
        results.extend({**r,'verdict':'not_run'} for r in plan if r['label'] not in recorded)
        save(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()})


if __name__=='__main__':
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path)
    f.add_argument('--timer-diagnostic',action='store_true')
    e=s.add_parser('run');e.add_argument('inputs',type=Path);e.add_argument('output',type=Path)
    e.add_argument('--backend',choices=('evas','spectre'),required=True);e.add_argument('--profile',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve(),a.timer_diagnostic)
    else:execute(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve())

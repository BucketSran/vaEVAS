"""Freeze and run the finite precision pilot; serial, bounded, no automatic retries.

Backend process ownership, compiler identity and format readers reuse the paper
adapter. This pilot owns its new cards, observation grid and independent checker.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
from inputs import BACKENDS, decks, save, sha
from runner import (preflight, verify_tool, stage, container_stage, stage_failure,
                    result_state, effective_settings, directory_budget, evas_effective_record, save_raw_response)
from observations import read_native
from precision_checker import assess

LIMITS={'stage_timeout_s':90,'license_timeout_s':30,'memory_limit_bytes':4*1024**3,
        'file_limit_bytes':32*1024**2,'threads':1}

def load(path):return json.loads(path.read_text())

def times_for(card):
    step=card['unit_s']/32
    critical={0.,card['stop_s'],*(t for pts in card['inputs'].values() for t,v in pts),*card.get('events_s',[])}
    points=set(critical)
    for t in critical:
        points.update([t-2e-12,t+2e-12])
    for t in card.get('events_s',[]):
        points.update(t+i*2e-12 for i in range(-52,53))
    # Keep exact critical points when floating arithmetic produces a near duplicate.
    for i in range(math.ceil(card['stop_s']/step)+1):
        t=i*step
        if not any(abs(t-c)<1e-15 for c in points):points.add(t)
    ordered=[]
    for t in sorted(q for q in points if 0<=q<=card['stop_s']):
        if not ordered or t-ordered[-1]>1e-15:ordered.append(t)
    return ordered


def source_files():
    paths=[p for area in ('evas/src','evas/rust_core','experiments/backends/paper','evas/validation/paper')
           for p in (ROOT/area).rglob('*') if p.is_file() and
           (p.suffix in ('.py','.rs','.toml') or p.name=='Cargo.lock') and
           'target' not in p.parts and '__pycache__' not in p.parts]
    paths += [Path(__file__),ROOT/'experiments/backends/support/precision_report.py',ROOT/'evas/pyproject.toml',
              ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py',
              ROOT/'experiments/archive/dvs2-starter-pilot/suite.py',
              ROOT/'evas/validation/paper/precision-v1.json']
    return sorted(set(paths))


def freeze(output):
    data=load(ROOT/'evas/validation/paper/precision-v1.json')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'cards.json',data);plan=[]
    for card in data['cards']:
        times=times_for(card)
        bind={'top_module':card['top'],'ports':card['ports'],'parameters':card['parameters']}
        physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
        breaks={'records':[{'time_s':t} for t in times]}
        for profile in data['profiles']:
            settings={**profile,'stop_s':card['stop_s'],'maxstep_s':card['unit_s']*profile['step_units'],
                      'spice_maxstep_s':card['unit_s']*profile['step_units']}
            generated=decks(physical,settings,bind,times,breaks)
            for backend in BACKENDS:
                label=card['id']+'--'+profile['id']; work=output/'runs'/backend/label;work.mkdir(parents=True)
                filename,text=generated[backend]
                if backend=='spectre':
                    lines=text.splitlines()
                    lines=[line+' precision="%.17g"' if line.startswith('simulatorOptions ') else
                           line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line for line in lines]
                    text='\n'.join(lines)+'\n'
                if backend=='gnucap_modelgen':
                    text=text.replace('.options numdgt=17 dtmin=1e-15', '.options numdgt=17 method=trap dtmin=1e-16')
                (work/filename).write_text(text);(work/'dut.va').write_text(card['source'])
                save(work/'condition.json',card);save(work/'requested_settings.json',settings)
                save(work/'requested_times.json',times)
                plan.append({'condition':card['id'],'profile':profile['id'],'family':card['family'],
                             'backend':backend,'label':label,'work':str(work.relative_to(output)),
                             'deck':filename,'source_sha256':sha(work/'dut.va')})
    save(output/'PLAN.json',plan)
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in source_files()})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps({'configurations':len(plan),'manifest_sha256':sha(output/'MANIFEST.json')}))


def verify(inputs):
    for rel,digest in load(inputs/'MANIFEST.json').items():
        p=(inputs/rel).resolve()
        if not p.is_relative_to(inputs.resolve()) or sha(p)!=digest:raise ValueError('input drift: '+rel)
    for rel,digest in load(inputs/'SOURCE_IDENTITY.json').items():
        p=(ROOT/rel).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=digest:raise ValueError('source drift: '+rel)


def worker(work,kernel):
    sys.path.insert(0,str(ROOT/'evas/src'))
    from evas import compile_sources, transient, Instance, CompileError, KernelError
    request=load(work/'request.json');times=load(work/'requested_times.json')
    try:
        instances=[Instance(i['name'],i['module'],i['ports'],i['parameters']) for i in request['instances']]
        program=compile_sources({'dut.va':(work/'dut.va').read_text()},instances)
        save(work/'program.json',program.to_dict())
        response=transient(program,request['inputs'],times,stop=request['stop'],max_step=request['max_step'],
                           strobetimes=times,kernel=kernel,vabstol=request['vabstol'],reltol=request['reltol'],timeout=None)
        save_raw_response(work/'raw-response.json',response)
        strobe=response['strobe_evidence']
        if strobe['times']!=times:raise ValueError('strobe time mismatch')
        with (work/'waveform.csv').open('x') as stream:
            writer=csv.writer(stream);writer.writerow(['time',*response['nodes']])
            writer.writerows([t,*v] for t,v in zip(strobe['times'],strobe['voltages_V'],strict=True))
        save(work/'effective.json',evas_effective_record(request,response))
        result={'status':'waveform_available','origins':sorted(set(strobe['sample_origins']))}
    except CompileError as exc:result={'status':'compile_failed','reason':str(exc)}
    except KernelError as exc:result={'status':'execution_failed','reason':str(exc),'detail':exc.detail}
    except Exception as exc:result={'status':'execution_failed','reason':repr(exc)}
    save(work/'worker-result.json',result)


def qualify(work,backend,result):
    # Execution and archived reanalysis use the same readback/provenance gates.
    from precision_report import qualification
    rows=read_native(work/result['waveform'],backend)
    check=qualification(work,backend,result,rows)
    candidate=result.get('assessment',{}).get('status','evidence_insufficient')
    return {**check,'status':'evidence_insufficient' if check['issues'] and candidate=='pass' else candidate}


def execute_one(backend, tool, env, work):
    stages=[];compiled=None;worker_result=None
    if backend=='evas':
        waveform='waveform.csv'
        stages.append(stage([sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(work),tool['kernel']],work,'simulate',LIMITS))
        worker_result=load(work/'worker-result.json') if (work/'worker-result.json').is_file() else {'status':'execution_failed','reason':'worker result missing'}
    elif backend=='spectre':
        waveform='psf/tran.tran.tran'
        command=tool['setup']+tool['binary']+' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n'
        (work/'run.csh').write_text(command)
        stages.append(stage(['/bin/csh','-f','run.csh'],work,'simulate',LIMITS))
    else:
        waveform='waveform.txt'
        if backend=='openvaf_r_ngspice':
            compiled='dut.osdi'
            stages.append(container_stage(env,tool['images']['openvaf_runtime']['config_id'],
                '/compiler/openvaf-r-v24.0.2mob-linux-x86_64/bin/openvaf-r',['dut.va','-o',compiled],work,'compile',LIMITS))
            image=tool['images']['ngspice']['config_id'];exe='/opt/ngspice/bin/ngspice';args=['-b','tb.cir']
        else:
            compiled='dut.so';image=tool['images']['gnucap']['config_id']
            command='/opt/gnucap/bin/gnucap-mg-vams -I /opt/gnucap/include/gnucap -o dut.cc --cc dut.va && /usr/bin/c++ -std=c++14 -I /opt/gnucap/include/gnucap -fPIC -shared dut.cc -o dut.so'
            stages.append(container_stage(env,image,'/bin/sh',['-c',command],work,'compile',LIMITS))
            exe='/opt/gnucap/bin/gnucap';args=['tb.gc']
        if not stage_failure(stages[-1]) and (work/compiled).is_file():
            stages.append(container_stage(env,image,exe,args,work,'simulate',LIMITS))
    return {**result_state(stages,work,waveform,compiled,worker_result,backend=backend),
            'stages':stages,'compiled_artifacts':{n:sha(work/n) for n in ('dut.osdi','dut.so','dut.cc') if (work/n).is_file()}}


def run(inputs,output,backend,profile_path,family):
    verify(inputs);data=load(inputs/'cards.json');profile=load(profile_path)
    plan=[r for r in load(inputs/'PLAN.json') if r['backend']==backend and r['family']==family]
    output.mkdir(parents=True,exist_ok=False);results=[]
    save(output/'STARTED.json',{'limits':LIMITS,'family':family,'backend':backend,'selected':plan,
                              'input_manifest_sha256':sha(inputs/'MANIFEST.json'),'profile_sha256':sha(profile_path)})
    try:
        tool,env=preflight(backend,profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
            result={**row,**execute_one(backend,tool,env,work)}
            if result['status']=='waveform_available':
                try:
                    native=read_native(work/result['waveform'],backend)
                    assessment=assess(load(work/'condition.json'),native,data['budgets'])
                    save(work/'ASSESSMENT.json',assessment)
                    result['assessment']=assessment
                except Exception as exc:result['assessment']={'status':'evidence_insufficient','reason':repr(exc)}
                try:result['effective_settings']=effective_settings(work,backend)
                except Exception as exc:result['effective_settings']={'status':'unknown','reason':repr(exc)}
            if result['status']=='waveform_available':
                result['engineering_verdict']=qualify(work,backend,result)
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            print(json.dumps({'case':row['label'],'execution':result['status'],'assessment':result.get('assessment',{}).get('status')}),flush=True)
            if result['abort_batch'] or result['directory_budget']['status']!='within_limit':break
    finally:
        recorded={r['label'] for r in results}
        results.extend({**r,'status':'not_run','reason':'batch did not reach this case'} for r in plan if r['label'] not in recorded)
        save(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(output.rglob('*')) if p.is_file()})


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('worker');p.add_argument('work',type=Path);p.add_argument('kernel')
    p=sub.add_parser('freeze');p.add_argument('output',type=Path)
    p=sub.add_parser('run');p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--backend',choices=BACKENDS,required=True);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--family',choices=('sample_hold','first_order'),required=True)
    a=parser.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    elif a.mode=='worker':worker(a.work.resolve(),a.kernel)
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),a.family)

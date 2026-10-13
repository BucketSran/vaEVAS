"""Freeze and execute precision-v2 without modifying any v1 recipe or result.

Shares bounded process/backend adapters with the original pilot. One invocation
runs one backend/family serially. Failed and unrun slots remain in the plan.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from precision_v2 import load_contract, observation_plan, assess
from precision_run import (LIMITS, source_files, verify, execute_one, load,
                           preflight, verify_tool, effective_settings, directory_budget)
from inputs import BACKENDS, decks, save, sha
from observations import read_native


def freeze(output):
    data=load_contract();output.mkdir(parents=True,exist_ok=False)
    save(output/'cards.json',data);plan=[];estimates=[]
    for card in data['cards']:
        observation=observation_plan(card,data);times=observation['times_s']
        estimated_rows=2*(len(times)+int(card['stop_s']/(card['unit_s']/2048))+1)
        estimated_bytes=estimated_rows*(len(card['ports'])+2)*32
        if estimated_bytes>LIMITS['file_limit_bytes']*.8:
            raise ValueError('preflight waveform estimate exceeds file budget: '+card['id'])
        estimates.append({'condition':card['id'],'requested_points':len(times),
                          'estimated_rows':estimated_rows,'estimated_waveform_bytes':estimated_bytes})
        bind={'top_module':card['top'],'ports':card['ports'],'parameters':card['parameters']}
        physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
        for profile in data['profiles']:
            settings={**profile,'stop_s':card['stop_s'],'maxstep_s':card['unit_s']*profile['step_units'],
                      'spice_maxstep_s':card['unit_s']*profile['step_units']}
            generated=decks(physical,settings,bind,times,{'records':[{'time_s':t} for t in times]})
            for backend in BACKENDS:
                label=card['id']+'--'+profile['id'];work=output/'runs'/backend/label;work.mkdir(parents=True)
                filename,text=generated[backend]
                if backend=='spectre':
                    text='\n'.join(line+' precision="%.17g"' if line.startswith('simulatorOptions ') else
                          line+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line
                          for line in text.splitlines())+'\n'
                elif backend=='openvaf_r_ngspice':
                    text=text.replace(' method=trap\n',' method=trap trtol=7 chgtol=1e-14 itl4=10\n')
                elif backend=='gnucap_modelgen':
                    text=text.replace('.options numdgt=17 dtmin=1e-15',
                                      '.options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9')
                (work/filename).write_text(text);(work/'dut.va').write_text(card['source'])
                save(work/'condition.json',card);save(work/'requested_settings.json',settings)
                save(work/'requested_times.json',times);save(work/'observation_plan.json',observation)
                plan.append({'condition':card['id'],'profile':profile['id'],'family':card['family'],
                             'backend':backend,'label':label,'work':str(work.relative_to(output)),
                             'deck':filename,'source_sha256':sha(work/'dut.va')})
    save(output/'PLAN.json',plan);save(output/'PREFLIGHT.json',{'estimates':estimates,'limits':LIMITS,
         'claim':'planning allowance, not runtime bound; file and condition limits remain active'})
    paths=source_files()+[ROOT/'evas/validation/paper/precision-v2.json',Path(__file__),
                         ROOT/'experiments/backends/support/precision_v2_report.py']
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(set(paths))})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps({'configurations':len(plan),'manifest_sha256':sha(output/'MANIFEST.json'),'estimates':estimates}))


def run(inputs,output,backend,profile_path,family,*,defer_analysis=False):
    verify(inputs);data=load(inputs/'cards.json');profile=load(profile_path)
    plan=[r for r in load(inputs/'PLAN.json') if r['backend']==backend and r['family']==family]
    output.mkdir(parents=True,exist_ok=False);results=[]
    save(output/'STARTED.json',{'limits':LIMITS,'selected':plan,'input_manifest_sha256':sha(inputs/'MANIFEST.json'),
                              'profile_sha256':sha(profile_path),'schema_version':2,
                              'defer_analysis':defer_analysis})
    try:
        tool,env=preflight(backend,profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
            try:
                result={**row,**execute_one(backend,tool,env,work)}
            except Exception as exc:
                result={**row,'status':'execution_failed','reason':repr(exc),'abort_batch':True,
                        'stages':[load(work/(n+'.json')) for n in ('compile','simulate') if (work/(n+'.json')).is_file()]}
                if defer_analysis:result['analysis_status']='not_available'
                save(work/'RESULT.json',result);results.append(result)
                raise
            if defer_analysis:
                result['analysis_status']='pending' if result['status']=='waveform_available' else 'not_available'
            elif result['status']=='waveform_available':
                try:
                    native=read_native(work/result['waveform'],backend)
                    result['assessment']=assess(load(work/'condition.json'),native,data)
                    save(work/'ASSESSMENT-v2.json',result['assessment'])
                except Exception as exc:result['analysis_error']=repr(exc)
                try:result['effective_settings']=effective_settings(work,backend)
                except Exception as exc:result['effective_settings']={'status':'unknown','reason':repr(exc)}
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            print(json.dumps({'case':row['label'],'execution':result['status'],
                              'tiers':{k:v['status'] for k,v in result.get('assessment',{}).get('tiers',{}).items()}}),flush=True)
            if result['abort_batch'] or result['directory_budget']['status']!='within_limit':break
    finally:
        recorded={r['label'] for r in results}
        results.extend({**r,'status':'not_run','reason':'batch did not reach this case'} for r in plan if r['label'] not in recorded)
        save(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                       for p in sorted(output.rglob('*')) if p.is_file()})


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('freeze');p.add_argument('output',type=Path)
    p=sub.add_parser('run');p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--backend',choices=BACKENDS,required=True);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--family',choices=('sample_hold','first_order'),required=True)
    p.add_argument('--defer-analysis',action='store_true',help='save raw evidence; analyze locally with precision_v2_report.py')
    a=parser.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),a.family,defer_analysis=a.defer_analysis)

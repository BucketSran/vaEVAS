"""Freeze and execute independent finite primitive cards on existing backends.

Uses the maintained compiler, solver, subprocess controls and native readers.
No solver source is changed. Scientific grading runs separately after collection.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'evas/validation/paper'))
sys.path.insert(0, str(ROOT/'experiments/backends/paper'))
from primitives import cards, T, assess, TIERS
from inputs import BACKENDS, decks, save, sha
from precision_run import LIMITS, execute_one
from runner import preflight, verify_tool, effective_settings, directory_budget
from observations import read_native


def load(path):
    return json.loads(path.read_text())


def verify(inputs):
    manifest=load(inputs/'MANIFEST.json')
    actual={str(p.relative_to(inputs)) for p in inputs.rglob('*')
            if p.is_file() and p!=inputs/'MANIFEST.json'}
    if actual!=set(manifest):raise ValueError('frozen primitive inventory changed')
    for name,digest in manifest.items():
        p=inputs/name
        if p.is_symlink() or not p.resolve().is_relative_to(inputs.resolve()) or sha(p)!=digest:
            raise ValueError('frozen primitive input changed: '+name)
    for name,digest in load(inputs/'SOURCE_IDENTITY.json')['files'].items():
        p=ROOT/name
        if p.is_symlink() or not p.resolve().is_relative_to(ROOT) or sha(p)!=digest:
            raise ValueError('bound primitive source changed: '+name)


def freeze(output):
    output.mkdir(parents=True, exist_ok=False)
    contract=load(ROOT/'evas/validation/paper/precision-v2.json')
    profiles={p['id']:p for p in contract['profiles']}
    binding={'Q1':'base','Q2':'both','Q3':'deep'}
    plan=[]
    for card in cards():
        times=sorted({i*T/16 for i in range(round(card['stop_s']/T)*16+1)} |
                     {t for t,v in card['inputs']['u'] if 0<=t<=card['stop_s']})
        for tier,name in binding.items():
            profile=dict(profiles[name])
            # Static maps have no integrated history. Hold the observation/step
            # plan fixed while tightening point-solve controls in each Q tier.
            if card['function'] not in ('idt','ddt'):
                profile['step_units']=.03125
            settings={**profile,'target_tier':tier,'stop_s':card['stop_s'],
                      'maxstep_s':T*profile['step_units'],'spice_maxstep_s':T*profile['step_units']}
            physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
            bind={'top_module':card['top'],'ports':card['ports'],'parameters':{}}
            generated=decks(physical,settings,bind,times,{'records':[{'time_s':t} for t in times]})
            for backend in BACKENDS:
                label=card['id']+'--'+tier
                work=output/'runs'/backend/label;work.mkdir(parents=True)
                filename,text=generated[backend]
                if backend=='spectre':
                    for prefix in ('simulatorOptions ','tran tran '):
                        if sum(line.startswith(prefix) for line in text.splitlines())!=1:
                            raise ValueError('Spectre precision insertion target changed: '+prefix)
                    text='\n'.join(line+' precision="%.17g" digits=17 notation=sci'
                         if line.startswith('simulatorOptions ') else
                         line+' skipcount=1 compression=no annotate=steps annotatedigits=16'
                         if line.startswith('tran tran ') else line for line in text.splitlines())+'\n'
                if backend=='gnucap_modelgen':
                    if text.count('.options numdgt=17 dtmin=1e-15')!=1:
                        raise ValueError('Gnucap precision insertion target changed')
                    text=text.replace('.options numdgt=17 dtmin=1e-15',
                                      '.options numdgt=17 method=trap dtmin=1e-16')
                (work/filename).write_text(text); (work/'dut.va').write_text(card['source'])
                for file,value in [('condition.json',card),('requested_settings.json',settings),
                                   ('requested_times.json',times)]: save(work/file,value)
                plan.append({'label':label,'condition':card['id'],'backend':backend,'tier':tier,
                             'work':str(work.relative_to(output)), 'deck':filename})
    save(output/'PLAN.json',plan)
    save(output/'CONTRACT.json',{'id':'finite-primitives-v1','cards':cards(),
                                'binding':binding,'budgets_V':TIERS,'historical_criteria':'unchanged'})
    sources=set()
    for directory,patterns in [('evas',('*.py','*.rs','Cargo.toml','Cargo.lock')),
                               ('experiments/backends/paper',('*.py',)),
                               ('experiments/backends/support',('*.py',)),
                               ('experiments/archive/dvs2-starter-pilot',('analyze.py','suite.py')),
                               ('evas/validation/paper',('precision-v2.json',))]:
        for pattern in patterns:
            sources.update(p for p in (ROOT/directory).rglob(pattern)
                           if 'target' not in p.parts and '__pycache__' not in p.parts)
    sources.update((Path(__file__),ROOT/'experiments/backends/support/precision_readback_audit.py'))
    save(output/'SOURCE_IDENTITY.json',{
        'checkpoint':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'scope':'checkpoint EVAS sources plus separately hashed local testing changes',
        'files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(sources)}})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in output.rglob('*') if p.is_file()})
    print(json.dumps({'positions':len(plan),'cards':len(cards()),'manifest_sha256':sha(output/'MANIFEST.json')}))


def run(inputs,output,backend,profile_path,selection=None):
    verify(inputs);profile=load(profile_path)
    selected=[r for r in load(inputs/'PLAN.json') if r['backend']==backend
              and (not selection or r['condition'] in selection)]
    if not selected:raise ValueError('empty primitive selection')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'STARTED.json',{'selected':selected,'limits':LIMITS,
                              'inputs_manifest_sha256':sha(inputs/'MANIFEST.json'),
                              'tool_profile_sha256':sha(profile_path)})
    results=[]
    try:
        tool,env=preflight(backend,profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for item in selected:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/'runs'/item['label'];shutil.copytree(inputs/item['work'],work)
            result={**item,**execute_one(backend,tool,env,work)}
            if result['status']=='waveform_available':
                try: result['settings_readback']=effective_settings(work,backend)
                except (ValueError,OSError) as exc:
                    result['settings_readback']={'status':'unknown','reason':str(exc)}
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            print(json.dumps({'label':item['label'],'status':result['status']}),flush=True)
            if result['abort_batch'] or result['directory_budget']['status']!='within_limit': break
    finally:
        completed={r['label'] for r in results}
        results.extend({**r,'status':'not_run','reason':'lane did not reach this position'}
                       for r in selected if r['label'] not in completed)
        save(output/'EXECUTION.json',results)
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                         for p in output.rglob('*') if p.is_file()})


def analyze(lanes,output):
    from precision_readback_audit import verify_lane
    from observations import READER_DEPENDENCIES
    source_paths=[Path(__file__),ROOT/'evas/validation/paper/primitives.py',
                  ROOT/'evas/validation/paper/precision_reference.py',
                  ROOT/'experiments/backends/paper/observations.py',
                  ROOT/'experiments/backends/support/precision_readback_audit.py',*READER_DEPENDENCIES]
    analysis_identity={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    results=[]
    for lane in lanes:
        verify_lane(lane)
        for original in load(lane/'EXECUTION.json'):
            record={'backend':original['backend'],'label':original['label'],'tier':original['tier'],
                    'execution':original['status'],'settings':original.get('settings_readback'),
                    'full_qualification':'pending independent settings and native-source audit',
                    'result_sha256':sha(lane/'runs'/original['label']/'RESULT.json')
                    if original['status']!='not_run' else None}
            if original['status']=='waveform_available':
                work=lane/'runs'/original['label']
                native=read_native(work/original['waveform'],original['backend'])
                record['assessment']=assess(load(work/'condition.json'),native,original['tier'])
            results.append(record)
    if output.exists(): raise ValueError('refusing to overwrite primitive results')
    if analysis_identity!={str(p.relative_to(ROOT)):sha(p) for p in source_paths}:
        raise ValueError('analysis source changed while grading')
    save(output,{'schema':'finite-primitives-results-v1','records':results,
                 'checker_sha256':sha(ROOT/'evas/validation/paper/primitives.py'),
                 'analysis_source_identity':analysis_identity,'budgets_V':TIERS,
                 'claim':'finite numerical observations; origin/settings qualification reported separately',
                 'history':'new execution and checker identity, no replacement of prior scores'})


if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('freeze');a.add_argument('output',type=Path)
    a=sub.add_parser('run');a.add_argument('inputs',type=Path);a.add_argument('output',type=Path)
    a.add_argument('--backend',choices=BACKENDS,required=True);a.add_argument('--profile',type=Path,required=True)
    a.add_argument('--card',action='append')
    a=sub.add_parser('analyze');a.add_argument('--lane',type=Path,action='append',required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output)
    elif a.mode=='run':run(a.inputs,a.output,a.backend,a.profile,a.card)
    else:analyze(a.lane,a.output)

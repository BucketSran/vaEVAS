"""Immutable breadth inputs and bounded serial four-backend execution receipts.

Q targets bind candidate controls before execution; they are not qualifications.
Scientific grading and actual settings/provenance remain separate records.
"""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from precision_run import (LIMITS, source_files, execute_one, load, preflight,
                           verify_tool, effective_settings, directory_budget)
from inputs import BACKENDS, decks, save, sha
from observations import read_native
from precision_report import qualification

TIER_PROFILES={'Q1':'base','Q2':'both','Q3':'deep'}
BREADTH_LIMITS={**LIMITS,'condition_limit_bytes':256*1024**2}


def load_contract():
    from precision_breadth import load_contract as loader
    return loader()


def observation_plan(card,contract):
    from precision_breadth import observation_plan as planner
    return planner(card,contract)


def assess(card,rows,contract):
    from precision_breadth import assess as checker
    return checker(card,rows,contract)


def verify(inputs):
    """Reject changed frozen inputs and any current source/checker drift."""
    for file, digest in load(inputs/'MANIFEST.json').items():
        path=(inputs/file).resolve()
        if not path.is_relative_to(inputs.resolve()) or not path.is_file() or sha(path)!=digest:
            raise ValueError('input drift: '+file)
    for file, digest in load(inputs/'SOURCE_IDENTITY.json').items():
        path=(ROOT/file).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path)!=digest:
            raise ValueError('source drift: '+file)


def freeze(output):
    data=load_contract();profiles={p['id']:p for p in data['profiles']}
    if not set(TIER_PROFILES.values())<=profiles.keys():raise ValueError('missing candidate profiles')
    cards=data['cards']
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('duplicate card identity')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'cards.json',data);plan=[];estimates=[]
    for card in cards:
        observation=observation_plan(card,data);times=observation['times_s']
        estimated_rows=2*(len(times)+int(card['stop_s']/(card['unit_s']/2048))+1)
        estimated_bytes=estimated_rows*(len(card['ports'])+2)*32
        if estimated_bytes>BREADTH_LIMITS['file_limit_bytes']*.8:
            raise ValueError('waveform estimate exceeds file budget: '+card['id'])
        estimates.append({'condition':card['id'],'requested_points':len(times),
                          'estimated_waveform_bytes':estimated_bytes})
        physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
        bind={'top_module':card['top'],'ports':card['ports'],'parameters':card['parameters']}
        for tier,profile_id in TIER_PROFILES.items():
            profile=profiles[profile_id]
            settings={**profile,'target_tier':tier,'candidate_status':'unqualified',
                      'stop_s':card['stop_s'],'maxstep_s':card['unit_s']*profile['step_units'],
                      'spice_maxstep_s':card['unit_s']*profile['step_units']}
            generated=decks(physical,settings,bind,times,{'records':[{'time_s':t} for t in times]})
            for backend in BACKENDS:
                label=card['id']+'--'+tier;work=output/'runs'/backend/label;work.mkdir(parents=True)
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
                plan.append({'condition':card['id'],'group_id':card['group_id'],'tier':tier,
                             'profile':profile_id,'family':card['family'],'backend':backend,
                             'label':label,'work':str(work.relative_to(output)),'deck':filename,
                             'source_sha256':sha(work/'dut.va')})
    save(output/'PLAN.json',plan)
    save(output/'PREFLIGHT.json',{'limits':BREADTH_LIMITS,'estimates':estimates,
                                'claim':'planning estimate; runtime limits still apply'})
    paths=set(source_files())|{Path(__file__),ROOT/'experiments/backends/support/precision_report.py',
                ROOT/'evas/validation/paper/precision-v2.json'}
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    return plan


def select_plan(plan,backend,family,groups=(),cards=(),tiers=()):
    selected=[r for r in plan if r['backend']==backend and r['family']==family and
              (not groups or r['group_id'] in groups) and (not cards or r['condition'] in cards) and
              (not tiers or r['tier'] in tiers)]
    if not selected:raise ValueError('selection contains no frozen slots')
    return selected


def run(inputs,output,backend,profile_path,family,*,groups=(),cards=(),tiers=()):
    plan=select_plan(load(inputs/'PLAN.json'),backend,family,groups,cards,tiers)
    output.mkdir(parents=True,exist_ok=False);results=[];attempts=[]
    save(output/'STARTED.json',{'schema_version':'breadth-v1','limits':BREADTH_LIMITS,'selected':plan,
         'input_manifest_sha256':sha(inputs/'MANIFEST.json'),'profile_sha256':sha(profile_path)})
    try:
        verify(inputs);data=load(inputs/'cards.json');profile=load(profile_path)
        tool,env=preflight(backend,profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            verify(inputs);verify_tool(tool,profile,env)
            work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
            save(work/'INPUT_IDENTITY.json',{'source_sha256':sha(work/'dut.va'),
                 'requested_settings_sha256':sha(work/'requested_settings.json'),'deck_sha256':sha(work/row['deck'])})
            attempt={'index':len(attempts)+1,'backend':backend,'label':row['label'],
                     'status':'invoked','stages':[],'stage_receipts_complete':False}
            attempts.append(attempt);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
            try:
                result={**row,**execute_one(backend,tool,env,work)}
                attempt.update(status=result['status'],stages=result.get('stages',[]),stage_receipts_complete=True)
            except Exception as exc:
                attempt.update(status='adapter_error',reason=repr(exc),
                               stages=[load(work/(n+'.json')) for n in ('compile','simulate') if (work/(n+'.json')).is_file()])
                result={**row,'status':'execution_failed','reason':repr(exc),'abort_batch':True}
                save(work/'RESULT.json',result);results.append(result)
                raise
            if result['status']=='waveform_available':
                try:
                    native=read_native(work/result['waveform'],backend)
                    result['assessment']=assess(load(work/'condition.json'),native,data)
                    save(work/'ASSESSMENT-breadth.json',result['assessment'])
                    result['effective_settings']=effective_settings(work,backend)
                    result['qualification']=qualification(work,backend,result,native)
                except Exception as exc:
                    result['qualification']={'status':'evidence_insufficient','issues':[repr(exc)]}
                q=result['qualification']
                result['qualified_tiers']={tier:{'status':a['status'] if q['status']=='qualified' or a['status']!='pass'
                      else 'evidence_insufficient','settings_and_provenance':q['status']}
                      for tier,a in result.get('assessment',{}).get('tiers',{}).items()}
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            checkpoint(output/'EXECUTION.json',results);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
            if result.get('abort_batch') or result['directory_budget']['status']!='within_limit':break
    finally:
        recorded={r['label'] for r in results}
        results.extend({**r,'status':'not_run','reason':'lane did not reach this frozen slot'}
                       for r in plan if r['label'] not in recorded)
        checkpoint(output/'EXECUTION.json',results);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
        save(output/'FILE_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
             for p in sorted(output.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.json'})
    return results


def checkpoint(path,data):
    """Replace a mutable lane receipt atomically; frozen files use exclusive save."""
    temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+'\n')
    temporary.replace(path)


def attempt_receipt(attempts):
    return {'backend_invocations':len(attempts),'stage_invocations':sum(len(a['stages']) for a in attempts),
            'stage_counts_complete':all(a.get('stage_receipts_complete',False) for a in attempts),
            'attempts':attempts,'claim':'adapter invocations and actual returned stage receipts; interrupted stage counts unknown'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    p=sub.add_parser('freeze');p.add_argument('output',type=Path)
    p=sub.add_parser('run');p.add_argument('inputs',type=Path);p.add_argument('output',type=Path)
    p.add_argument('--backend',choices=BACKENDS,required=True);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--family',choices=('foundation','composition'),required=True)
    p.add_argument('--group',action='append',default=[]);p.add_argument('--card',action='append',default=[])
    p.add_argument('--tier',choices=tuple(TIER_PROFILES),action='append',default=[])
    a=parser.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),a.family,
             groups=a.group,cards=a.card,tiers=a.tier)

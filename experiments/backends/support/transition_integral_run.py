"""Separate EC05 area qualification; preserves the old support-probe result."""
import argparse
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'evas/validation/paper'),str(ROOT/'experiments/backends/paper')]
import transition_integral_precision as q
import precision_run as execution
import legacy_pipeline as pipeline
from legacy_chain_run import source_identity,source_provenance,verify,build_identity,validate_spectre_controls
from actual_observation import production_dependencies
from inputs import decks,sha,save
from observations import read_native
from precision_report import spectre_fullprecision_settings,qualification


def freeze(output):
    output.mkdir(parents=True,exist_ok=False);c=q.card();plan=[]
    profiles={p['id']:p for p in execution.load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']}
    times=set(c['times'])
    # Cover the unchanged +/-100ps timer windows and the induced reversal end.
    for center in (c['unit_s'],1.25*c['unit_s'],1.75*c['unit_s']):
        # end=3*b-2*a moves by up to 500ps for the original +/-100ps
        # callback windows. Keep room for both mandatory neighboring samples.
        times.update(center+i*1e-12 for i in range(-610,611))
    times=sorted(t for t in times if 0<=t<=c['stop_s'])
    c={**c,'times':times}
    for tier,pid in q.PROFILES.items():
        s={**profiles[pid],'stop_s':c['stop_s'],'maxstep_s':c['unit_s']*profiles[pid]['step_units']}
        s['spice_maxstep_s']=s['maxstep_s']
        generated=decks({'id':c['id'],'stimulus':{}},s,{'top_module':c['top'],'ports':c['ports'],'parameters':c['parameters']},times,{'records':[]})
        for backend,variant in [('evas','original'),('spectre','original'),('spectre','trace')]:
            label=c['id']+'--'+tier+'--'+variant;w=output/'runs'/backend/label;w.mkdir(parents=True)
            name,text=generated[backend]
            if backend=='spectre':
                text='\n'.join(line+' precision="%.17g" digits=17 notation=sci' if line.startswith('simulatorOptions ') else
                    line.replace('tran tran ','tran tran transres=1e-20 ')+' skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line
                    for line in text.splitlines() if not line.startswith('Vpaper_observer'))+'\n'
            source=q.trace_source(c['source']) if variant=='trace' else c['source']
            if backend=='spectre':validate_spectre_controls(text)
            (w/name).write_text(text);(w/'dut.va').write_text(source);(w/'original.va').write_text(c['source'])
            save(w/'SOURCE_BINDING.json',dict(production_sources=production_dependencies(ROOT),source_identity=analysis_identity(),provenance=source_provenance()))
            for filename,value in [('condition.json',c),('requested_settings.json',s),('requested_times.json',times)]:save(w/filename,value)
            plan.append(dict(condition=c['id'],tier=tier,profile=pid,backend=backend,variant=variant,label=label,work=str(w.relative_to(output)),
                deck=name,deck_sha256=sha(w/name),source_binding_sha256=sha(w/'SOURCE_BINDING.json'),original_source_sha256=__import__('hashlib').sha256(c['source'].encode()).hexdigest(),executed_source_sha256=sha(w/'dut.va')))
    identity=analysis_identity()
    save(output/'PLAN.json',plan);save(output/'SOURCE_IDENTITY.json',identity)
    save(output/'PRODUCTION_IDENTITY.json',{'provenance':source_provenance(),'production_sources':production_dependencies(ROOT)})
    save(output/'CONTRACT.json',{'criterion':'EC05-Q-v2','budgets':q.TIERS,'bindings':q.PROFILES,'scope':'original EC05 source + separate readonly trace source','limits':execution.LIMITS})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps({'configurations':len(plan),'manifest_sha256':sha(output/'MANIFEST.json')}))


def analysis_identity():
    sources=source_identity()
    for name in ('experiments/backends/support/transition_integral_run.py',
                 'evas/validation/paper/transition_integral_precision.py',
                 'evas/validation/paper/precision_breadth_composition.py'):
        sources[name]=sha(ROOT/name)
    return sources


def analyze_work(work,record,tool,*,producer_repo=None):
    backend=record['backend'];rows=read_native(work/record['waveform'],backend)
    events=q.callbacks(execution.load(work/'raw-response.json') if backend=='evas' else
        (work/'spectre.log').read_text() if record['variant']=='trace' else '',backend)
    result=dict(assessment=(dict(status='evidence_insufficient',
        reason='unmodified Spectre source has no callback observation; waveform retained for observer comparison',criterion='EC05-Q-v2')
        if backend=='spectre' and record['variant']=='original' else
        q.assess(execution.load(work/'condition.json'),rows,events,record['tier'])))
    try:
        result['effective_settings']=(execution.effective_settings(work,backend) if backend=='evas' else
            spectre_fullprecision_settings(work,tool,frozen_deck_sha256=record['deck_sha256']))
        result['qualification']=qualification(work,backend,{**record,**result},rows,spectre_tool=tool)
    except Exception as exc:
        result['effective_settings']=dict(status='evidence_insufficient',reason=repr(exc))
        result['qualification']=dict(status='evidence_insufficient',issues=['settings/qualification error: '+repr(exc)])
    if backend=='evas':
        result['source_build_qualification']=build_identity(work,record,tool,producer_repo=producer_repo)
        result['qualification']['issues'].extend(result['source_build_qualification']['issues'])
    original=work/'original.va'
    original_hash=sha(original) if original.is_file() else __import__('hashlib').sha256(execution.load(work/'condition.json')['source'].encode()).hexdigest()
    result['original_source_binding_basis']='original.va' if original.is_file() else 'frozen condition.json source text'
    if original_hash!=record.get('original_source_sha256'):result['qualification']['issues'].append('frozen original source identity mismatch')
    for name,field in [('dut.va','executed_source_sha256'),(record['deck'],'deck_sha256')]:
        if sha(work/name)!=record.get(field):result['qualification']['issues'].append('executed/frozen identity mismatch: '+name)
    result['analysis_sources']=analysis_identity()
    result['engineering_verdict']=result['assessment']['status'] if not result['qualification']['issues'] else 'evidence_insufficient'
    return result


def reanalyze(lanes,output,producer_repo=None):
    records=[];parents=[];comparisons=[]
    for lane in lanes:
        parents.append(pipeline.verify_lane(lane,Path(producer_repo) if producer_repo is not None else ROOT))
        comparisons.extend(observer_comparisons(lane,execution.load(lane/'EXECUTION.json')))
        for record in execution.load(lane/'EXECUTION.json'):
            result=dict(record)
            if record['status']=='waveform_available':
                try:result.update(analyze_work(lane/'runs'/record['label'],record,execution.load(lane/'TOOL_IDENTITY.json'),producer_repo=producer_repo))
                except Exception as exc:result.update(engineering_verdict='evidence_insufficient',analysis_error=repr(exc))
            records.append(result)
    pipeline.save_exclusive(output,dict(schema='EC05-Q-v2-reanalysis',records=records,parent_executions=parents,observer_comparison=comparisons,
        claim='new analysis only; original execution receipts and verdicts unchanged',analysis_sources=analysis_identity()),lanes)


def observer_comparisons(output,results):
    from legacy_chain_precision import scientific_identity
    comparisons=[]
    for tier in q.TIERS:
        pair={r['variant']:r for r in results if r['backend']=='spectre' and r['tier']==tier and r['status']=='waveform_available'}
        if set(pair)=={'original','trace'}:
            try:
                waves={v:read_native(output/'runs'/r['label']/r['waveform'],'spectre') for v,r in pair.items()}
                comparison=scientific_identity(waves['original'],waves['trace'],['edge_v','y','n'])
            except Exception as exc:comparison=dict(status='evidence_insufficient',reason='observer analysis_error: '+repr(exc))
            comparisons.append(dict(tier=tier,comparison=comparison,claim='observer comparison only; no original-source Q verdict inferred'))
    return comparisons


def finalize(output,results,deferred):
    if any(r['backend']=='spectre' for r in results):
        save(output/'OBSERVER_COMPARISON.json',dict(status='pending',reason='analysis deferred') if deferred else observer_comparisons(output,results))


def recipe_check(inputs,plan):
    profiles={p['id']:p for p in execution.load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']}
    c=q.card()
    return pipeline.inspect_plan(inputs,plan,{c['id']:c},profiles,q.PROFILES,
        lambda card:q.trace_source(card['source']),validate_spectre_controls)


def precheck(inputs,backend,*,tiers=None,variant=None,pilot=False):
    c=q.card()
    return pipeline.precheck(inputs,backend,verify,recipe_check,{c['id']:c},tiers=tiers,variant=variant,pilot=pilot)


def run(inputs,output,backend,profile,*,defer_analysis=False,pilot=False,tiers=None,variant=None):
    c=q.card()
    return pipeline.run(inputs,output,backend,profile,execution,verify,recipe_check,{c['id']:c},
        analyze_work,execution.execute_one,tiers=tiers,variant=variant,defer_analysis=defer_analysis,pilot=pilot,finalize=finalize)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path)
    r=s.add_parser('run');r.add_argument('inputs',type=Path);r.add_argument('output',type=Path);r.add_argument('--backend',required=True,choices=['evas','spectre']);r.add_argument('--profile',required=True,type=Path)
    r.add_argument('--pilot',action='store_true');r.add_argument('--defer-analysis',action='store_true');r.add_argument('--tier',action='append',choices=q.TIERS);r.add_argument('--variant',choices=['original','trace'])
    pc=s.add_parser('precheck');pc.add_argument('inputs',type=Path);pc.add_argument('--backend',required=True,choices=['evas','spectre']);pc.add_argument('--pilot',action='store_true');pc.add_argument('--tier',action='append',choices=q.TIERS);pc.add_argument('--variant',choices=['original','trace'])
    re=s.add_parser('analyze');re.add_argument('--lane',action='append',type=Path,required=True);re.add_argument('--output',type=Path,required=True);re.add_argument('--producer-repo',type=Path)
    a=p.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    elif a.mode=='run':run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),defer_analysis=a.defer_analysis,pilot=a.pilot,tiers=a.tier,variant=a.variant)
    elif a.mode=='precheck':print(json.dumps(precheck(a.inputs.resolve(),a.backend,tiers=a.tier,variant=a.variant,pilot=a.pilot)))
    else:reanalyze(a.lane,a.output,a.producer_repo)

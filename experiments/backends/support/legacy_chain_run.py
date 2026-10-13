"""Freeze -> bounded serial execution -> independent legacy-chain Q analysis."""
import argparse
import copy
import json
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'evas/validation/paper'),str(ROOT/'experiments/backends/support'),str(ROOT/'experiments/backends/paper'),str(ROOT/'experiments/backends/dvs2-spectre-validation')]
import precision_run as execution
import legacy_chain_precision as q
from actual_observation import production_dependencies, production_dependency, canonical_sha, WORKER_DEPENDENCIES
from inputs import sha,save,decks
from observations import read_native
import legacy_pipeline as pipeline
load=execution.load


def cards():
    result=[]
    for c in q.sef.CASES:
        for observation in (['native','strobe'] if c['id']!='SEF-RESET' else ['native']):
            result.append(dict(id=c['id'] if observation=='native' else 'ST:'+c['id'],kind='sef',instances=c['instances'],
                source=q.sef.source(c),inputs={n:[[t*q.sef.T,v] for t,v in pts] for n,pts in [('u',q.sef.INPUT),('clk',q.sef.CLOCK),('rst',q.sef.RESET)]},
                binding=dict(top_module='dut',ports=['u','clk','rst',*[p['name']+x for p in c['instances'] for x in 'hefn']],parameters={}),
                outputs=[p['name']+x for p in c['instances'] for x in 'hefn'],stop_s=q.sef.STOP,unit_s=q.sef.T,
                times=q.sef.times(c,observation=='strobe'),max_gap_s=q.sef.T/16,
                event_early_s=q.sef.TIME_BUDGET,event_late_s=q.sef.TIME_BUDGET,original_input_budget_V=q.sef.INPUT_BUDGET,
                boundary_distance_s=2.1e-12,history_lipschitz_V_s=1e9,legacy_case=c,observation=observation))
    c=copy.deepcopy(q.st.INTEGRAL)
    c.update(kind='integral',binding=dict(top_module=c['top'],ports=c['ports'],parameters=c['parameters']),times=execution.times_for(c),
             max_gap_s=q.sef.T/16,original_input_budget_V=1.01e-8,boundary_distance_s=2.1e-12,history_lipschitz_V_s=1e7)
    result.append(c)
    from comparison_c2 import card
    c=card();c.update(kind='c2',source_time_tol_s=1e-9,original_acceptance_late_s=4e-11,outputs=['z','vout'],unit_s=1e-6,max_gap_s=2e-10,event_early_s=0,event_late_s=4e-11,
        original_input_budget_V=1e-8,boundary_distance_s=2.1e-12,history_lipschitz_V_s=5e7)
    c['inputs']['r']=[[0.,0.],[c['stop_s'],0.]]
    critical={0.,c['stop_s'],*[t for pts in c['inputs'].values() for t,v in pts],1.5e-6,2.5e-6,3.5e-6,1.525e-6,2.525e-6,3.525e-6}
    times=set(critical)
    for t in critical:times.update(t+i*2e-12 for i in range(-5,6) if 0<=t+i*2e-12<=c['stop_s'])
    times.update(i*2e-10 for i in range(20001) if not any(0<abs(i*2e-10-t)<1e-15 for t in critical))
    c['times']=sorted(times);result.append(c)
    for old in q.nt.CASES:
        c=dict(old,id='NT:'+old['id'],kind='nt',source=q.nt.source(old['held'],old['chain']),inputs={'u':[[0.,0.],[1.,0.]]},
            binding=dict(top_module='m',ports=['u','y','r'],parameters={}),outputs=['y']+(['h','e','f','i'] if old['chain'] else []),
            physical_variant='original-ground-binding-v2',stop_s=1.,unit_s=1.,times=sorted(set(q.nt.STROBES+[i/64 for i in range(65)])),max_gap_s=.1,event_early_s=old['tt'],event_late_s=old['tt'],
            original_input_budget_V=1e-8,boundary_distance_s=16*__import__('math').ulp(1.),history_lipschitz_V_s=100.,legacy_case=old)
        result.append(c)
    if len(result)!=12:raise ValueError('fixed twelve-condition scope incomplete')
    return result


def source_provenance():
    supplied=ROOT/'SOURCE_PROVENANCE.json'
    if supplied.is_file():return dict(snapshot_provenance=load(supplied),provenance_sha256=sha(supplied),identity_kind='copied source snapshot; no Git/build qualification inferred')
    try:
        return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL).strip(),
            porcelain=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True,stderr=subprocess.DEVNULL),identity_kind='local checkout')
    except subprocess.CalledProcessError:
        raise ValueError('source snapshot requires ROOT/SOURCE_PROVENANCE.json supplied by coordinator')


def source_identity():
    paths=set(production_dependencies(ROOT))
    paths.update(str(p.relative_to(ROOT)) for p in (Path(__file__),ROOT/'evas/validation/paper/legacy_chain_precision.py',ROOT/'evas/validation/paper/legacy_chain_bounds.py',
         ROOT/'experiments/backends/support/precision_run.py',ROOT/'experiments/backends/support/comparison_c2.py',
         ROOT/'experiments/backends/support/legacy_pipeline.py',ROOT/'experiments/backends/support/precision_precheck.py',
         ROOT/'evas/validation/sample_edge_filter/contract.py',ROOT/'evas/validation/strobe/timer_composition.py',ROOT/'evas/validation/strobe/near_timer.py',
         ROOT/'evas/validation/paper/precision_checker.py',ROOT/'experiments/backends/support/precision_report.py',
         ROOT/'experiments/backends/paper/fixtures/spectre-21.1.0.509-format-calibration.json',ROOT/'evas/validation/paper/precision-v1.json',ROOT/'evas/validation/paper/precision-v2.json',
         ROOT/'experiments/backends/paper/actual_observation.py',ROOT/'experiments/backends/dvs2-spectre-validation/run_suite.py',
         ROOT/'experiments/backends/dvs2-spectre-validation/check_results.py',ROOT/'experiments/archive/dvs2-history-validation/history.py',ROOT/'experiments/archive/dvs2-history-validation/recheck.py',
         ROOT/'evas/validation/cases/n_v4_02/dut.va',ROOT/'evas/validation/cases/d2_v6_01_standard/dut.va'))
    return {p:sha(ROOT/p) for p in sorted(paths)}



def analysis_identity():
    """Record the full source closure used by execution and new analysis."""
    return source_identity()


def compiled_dependency(name):
    """Fixed Rust audit scope, independent of the historical manifest entries.

    This is an audit superset, not Cargo dep-info. Python readers and workers
    are execution/analysis inputs, not inputs to the compiled Rust kernel.
    """
    return (any(name.startswith(prefix) for prefix in
                ('evas/rust_core/src/', 'evas/rust_core/ir/src/')) and name.endswith('.rs')
            or production_dependency(name) and name.startswith('evas/rust_core/')
            and not name.endswith('.py'))


def build_identity(work,record,tool,*,producer_repo=None):
    """Bind the actual kernel and original execution snapshot separately.

    Reanalysis uses an explicitly preserved producer tree. It never attributes
    today's Python reader bytes to the earlier execution or changes its receipt.
    """
    repo=Path(producer_repo) if producer_repo is not None else ROOT
    issues=[];identity=dict(verified=False,issues=issues)
    try:
        binding_path=work/'SOURCE_BINDING.json'
        if sha(binding_path)!=record.get('source_binding_sha256'):raise ValueError('frozen source binding hash mismatch')
        binding=load(binding_path);frozen=binding['production_sources'];actual=production_dependencies(repo)
        if frozen!=actual:issues.append('frozen/executed production closure mismatch')
        sources=binding['source_identity']
        if {name:digest for name,digest in sources.items() if production_dependency(name)}!=frozen:
            issues.append('SOURCE_IDENTITY/production closure mismatch')
        # Includes the actual precision_run worker/driver as well as Python
        # frontend, readers and the original analysis files in the snapshot.
        changed=sorted(name for name,digest in sources.items()
                       if not (repo/name).is_file() or sha(repo/name)!=digest)
        if changed:issues.append('original execution snapshot source mismatch: '+','.join(changed))
        if 'experiments/backends/support/precision_run.py' not in sources:
            issues.append('missing actual precision_run worker source binding')
        provenance=binding['provenance'];provenance=provenance.get('snapshot_provenance',provenance)
        manifest_path=repo.parent/'BUILD_SOURCE_MANIFEST.json';build_path=repo.parent/'BUILD.json'
        manifest=load(manifest_path);build=load(build_path)
        compiled={name:digest for name,digest in actual.items() if compiled_dependency(name)}
        from_build={name:digest for name,digest in manifest.items() if compiled_dependency(name)}
        from_provenance={name:digest for name,digest in provenance.get('production_source_sha256',{}).items() if compiled_dependency(name)}
        if from_build!=compiled:issues.append('BUILD/required Rust audit closure mismatch')
        if from_provenance!=compiled:issues.append('provenance/required Rust audit closure mismatch')
        if sha(manifest_path)!=build.get('source_manifest_sha256'):issues.append('BUILD source manifest hash mismatch')
        if sha(build_path)!=provenance.get('previous_build_record_sha256'):issues.append('provenance BUILD record hash mismatch')
        stage=build.get('stage',{})
        if (build.get('returncode')!=0 or stage.get('status')!='completed' or stage.get('returncode')!=0
            or stage.get('timeout') is not False or stage.get('cleanup',{}).get('complete') is not True):
            issues.append('BUILD did not complete successfully')
        if not all(build.get('compiler_identity',{}).get(name,{}).get('actual_binary_sha256') for name in ('cargo','rustc')):
            issues.append('missing actual cargo/rustc binary identities')
        if build.get('cargo_lock_sha256')!=compiled.get('evas/rust_core/Cargo.lock'):issues.append('BUILD Cargo.lock hash mismatch')
        kernel=(tool or {}).get('kernel_sha256')
        if not kernel or kernel!=build.get('kernel_sha256') or kernel!=provenance.get('kernel_sha256'):issues.append('actual kernel/BUILD/provenance mismatch')
        identity.update(build_sha256=sha(build_path),build_source_manifest_sha256=sha(manifest_path),actual_kernel_sha256=kernel,
            compiled_kernel_identity=dict(basis='independently enumerated Rust audit superset; no Cargo dep-info claim',sources=compiled,source_manifest_sha256=canonical_sha(compiled),
                historical_noncompiled_sources=sorted(set(manifest)-set(from_build))),
            execution_runtime_identity=dict(basis='preserved original producer snapshot; separate from current analysis',sources=sources,source_manifest_sha256=canonical_sha(sources)))
    except Exception as exc:issues.append('missing/invalid source BUILD kernel identity chain: '+str(exc))
    identity['verified']=not issues
    return identity


def validate_spectre_controls(text):
    """Reject an inconsistent generated deck before running any simulator."""
    options=[line for line in text.splitlines() if line.startswith('simulatorOptions ')]
    transient=[line for line in text.splitlines() if line.startswith('tran tran ')]
    if len(options)!=1 or len(transient)!=1:raise ValueError('expected one Spectre options and tran statement')
    for name,value,line in [('digits','17',options[0]),('notation','sci',options[0]),
                            ('precision','"%.17g"',options[0]),('transres','1e-20',transient[0]),
                            ('errpreset','conservative',transient[0]),('method','traponly',transient[0])]:
        found=re.findall(r'\b'+name+r'\s*=\s*("[^"\n]*"|\S+)',line)
        if found!=[value]:raise ValueError('inconsistent frozen Spectre control: '+name)


def freeze(output,cases=None,tiers=None,variants=None):
    selected=[c for c in cards() if not cases or c['id'] in cases]
    if cases and (len(cases)!=len(set(cases)) or set(cases)!={c['id'] for c in selected}):raise ValueError('unknown or duplicate case selection')
    tiers=tiers or list(q.TIERS);variants=variants or ['original','trace']
    if len(tiers)!=len(set(tiers)) or set(tiers)-set(q.TIERS):raise ValueError('unknown or duplicate tier')
    if len(variants)!=len(set(variants)) or set(variants)-{'original','trace'}:raise ValueError('unknown or duplicate variant')
    output.mkdir(parents=True,exist_ok=False);profiles={p['id']:p for p in load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']};plan=[]
    save(output/'CONTRACT.json',dict(scope=[c['id'] for c in cards()],selected=[c['id'] for c in selected],tiers=q.TIERS,profile_binding=q.PROFILE_BINDING,
        limits=execution.LIMITS,automatic_retries=0,trace_claim='new readonly observational source; no transfer to original source'))
    frozen_sources=source_identity();production_sources=production_dependencies(ROOT);provenance=source_provenance()
    for card in selected:
        # Additional Q observations never replace the original requested set.
        nominal=[dict(label=label,index=i,time_s=t) for label,ts in q.callback_specs(card).items() for i,t in enumerate(ts,1)]
        from decimal import localcontext
        with localcontext() as ctx:
            ctx.prec=80
            _,polygons=q.references(card,nominal)
        key_times={0.,card['stop_s'],*[t for pts in card['inputs'].values() for t,v in pts],*[r['time_s'] for r in nominal],*[float(k[0]) for poly in polygons.values() for k in poly.knots]}
        extra=set(card['times'])
        for t in key_times:
            extra.add(t)
            for offset in (-card['boundary_distance_s']*.9,card['boundary_distance_s']*.9):
                if 0<=t+offset<=card['stop_s']:extra.add(t+offset)
        card={**card,'times':sorted(extra),'q_observation_type':'original requested set plus finite Q boundary observations; EVAS strobe readback/Spectre native rows','historical_reanalysis_claim':'historical checker reanalysis under new Q observations; no old execution reproduction'}
        for tier in tiers:
            settings=dict(profiles[q.PROFILE_BINDING[tier]],stop_s=card['stop_s'],maxstep_s=card['unit_s']*profiles[q.PROFILE_BINDING[tier]]['step_units'])
            settings['spice_maxstep_s']=settings['maxstep_s']
            for variant in variants:
                src=q.trace_source(card) if variant=='trace' else card['source'];condition={**card,'variant':variant}
                scientific_ports=card['binding']['ports']
                generated=decks(dict(id=card['id'],stimulus={n:dict(points_s_V=pts) for n,pts in card['inputs'].items()}),settings,card['binding'],card['times'],dict(records=[]))
                for backend in ('evas','spectre'):
                    if backend=='evas' and variant=='trace':continue
                    label=card['id'].replace(':','_')+'--'+tier+'--'+variant;work=output/'runs'/backend/label;work.mkdir(parents=True)
                    name,text=generated[backend]
                    if backend=='spectre':
                        text='\n'.join(line+' precision="%.17g" digits=17 notation=sci' if line.startswith('simulatorOptions ') else line+' transres=1e-20 skipcount=1 compression=no annotate=steps annotatedigits=16' if line.startswith('tran tran ') else line for line in text.splitlines() if not line.startswith('Vpaper_observer'))+'\n'
                        if card['kind']=='nt':
                            text=text.replace('dut (u y r)','dut (u y 0)').replace('save u y r','save u y'+(' dut.h dut.e dut.f dut.i' if card['chain'] else ''))
                    elif card['kind']=='nt':
                        request=json.loads(text);request['instances'][0]['ports']['r']='0';text=json.dumps(request,indent=2)+'\n'
                    if backend=='spectre':validate_spectre_controls(text)
                    save(work/'SOURCE_BINDING.json',dict(production_sources=production_sources,source_identity=frozen_sources,provenance=provenance))
                    (work/name).write_text(text);(work/'dut.va').write_text(src);(work/'original.va').write_text(card['source'])
                    for filename,value in [('condition.json',condition),('requested_settings.json',settings),('requested_times.json',card['times'])]:save(work/filename,value)
                    plan.append(dict(condition=card['id'],tier=tier,profile=settings['id'],variant=variant,backend=backend,label=label,work=str(work.relative_to(output)),deck=name,
                        source_binding_sha256=sha(work/'SOURCE_BINDING.json'),physical_variant=card.get('physical_variant','preserved-source-fixture-v1'),original_source_sha256=sha(work/'original.va'),executed_source_sha256=sha(work/'dut.va'),deck_sha256=sha(work/name)))
    save(output/'PLAN.json',plan)
    save(output/'SOURCE_IDENTITY.json',frozen_sources)
    save(output/'PRODUCTION_IDENTITY.json',dict(provenance=provenance,production_sources=production_sources,
        claim='working checkout identity; dirty runner/checker is not called a clean revision'))
    save(output/'SOURCE_PROVENANCE.json',provenance)
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    print(json.dumps(dict(cases=len(selected),configurations=len(plan),manifest_sha256=sha(output/'MANIFEST.json'))))
    return plan


def verify(inputs):
    manifest=load(inputs/'MANIFEST.json')
    actual={str(p.relative_to(inputs)) for p in inputs.rglob('*') if p.is_file() and p!=inputs/'MANIFEST.json'}
    if actual!=set(manifest):raise ValueError('frozen file set drift')
    for name,digest in manifest.items():
        p=(inputs/name).resolve()
        if not p.is_relative_to(inputs.resolve()) or sha(p)!=digest:raise ValueError('frozen input drift: '+name)
    from actual_observation import production_dependency
    frozen_sources=load(inputs/'SOURCE_IDENTITY.json')
    frozen_production={n:d for n,d in frozen_sources.items() if production_dependency(n)}
    if production_dependencies(ROOT)!=frozen_production:raise ValueError('production dependency closure drift')
    for name,digest in frozen_sources.items():
        if sha(ROOT/name)!=digest:raise ValueError('bound source drift: '+name)


def worker(work,kernel):
    # The maintained worker only executes and saves raw evidence. Its old
    # precision checker is never used to assess these new conditions.
    execution.worker(work,kernel)


def normalize(card,rows,backend):
    if card['kind']=='nt' and card['chain']:
        return [{**r,**{k:r.get(('dut.' if backend=='spectre' else 'dut:')+k) for k in 'hefi'}} for r in rows]
    return rows


def historical(card,rows):
    if card['kind']=='sef':return q.sef.assess(card['legacy_case'],rows)
    if card['kind']=='integral':return q.st.assess(q.st.INTEGRAL,rows)
    if card['kind']=='nt':return q.nt.assess(card['legacy_case'],rows)
    from check_results import check
    return check(rows,card['legacy'])


def analyze_work(work,record,tool=None,*,persist=True,producer_repo=None):
    from precision_report import qualification,spectre_fullprecision_settings
    card=load(work/'condition.json');raw_rows=read_native(work/record['waveform'],record['backend'])
    rows=normalize(card,raw_rows,record['backend'])
    if record['backend']=='evas':callbacks=q.evas_callbacks(card,load(work/'raw-response.json'))
    else:callbacks=q.parse_trace((work/'spectre.log').read_text(errors='replace')) if card['variant']=='trace' else []
    assessment=q.assess(card,rows,callbacks,record['tier'])
    if persist:save(work/'ASSESSMENT.json',assessment)
    try:old=historical(card,rows)
    except Exception as exc:old=dict(status='analysis_failure',reason=repr(exc))
    issues=[]
    try:
        settings=(spectre_fullprecision_settings(work,tool or {},frozen_deck_sha256=record.get('deck_sha256'))
                  if record['backend']=='spectre' else execution.effective_settings(work,'evas'))
        evidence=qualification(work,record['backend'],dict(record,effective_settings=settings),raw_rows,spectre_tool=tool)
        issues.extend(evidence['issues'])
    except Exception as exc:
        settings=dict(status='evidence_insufficient',reason=repr(exc));evidence=dict(status='evidence_insufficient',issues=[str(exc)]);issues.extend(evidence['issues'])
    source_build=build_identity(work,record,tool,producer_repo=producer_repo) if record['backend']=='evas' else dict(verified=None,basis='Spectre source/deck/tool qualification; EVAS BUILD chain not applicable')
    if record['backend']=='evas':
        issues.extend(source_build['issues'])
        if not tool or not tool.get('kernel_sha256'):issues.append('missing actual EVAS preflight kernel identity')
        if type(settings.get('actual',{}).get('stop')) not in (float,int):issues.append('missing actual EVAS stop readback')
    if sha(work/record['deck'])!=record.get('deck_sha256'):issues.append('executed/frozen deck identity mismatch')
    if sha(work/'dut.va')!=record.get('executed_source_sha256'):issues.append('executed/frozen source identity mismatch')
    if sha(work/'original.va')!=record.get('original_source_sha256'):issues.append('frozen original source identity mismatch')
    status=assessment['status'] if not issues else 'evidence_insufficient'
    return dict(assessment=assessment,historical_assessment=old,historical_reanalysis_claim=card.get('historical_reanalysis_claim','new Q observation reanalysis; original execution reproduction unproved'),effective_settings=settings,observation_qualification=evidence,source_build_qualification=source_build,analysis_sources=analysis_identity(),
        Q_qualification=dict(status=status,issues=issues,analysis_identity=q.ANALYSIS_ID,failure_owner='protocol_fail' if issues else assessment.get('failure_owner','unresolved'),
            source_variant=card['variant'],scope='this executed source only; trace qualification never transfers to original'),
        waveform_sha256=sha(work/record['waveform']),callback_evidence='raw-response.json' if record['backend']=='evas' else 'spectre.log')


def recipe_check(inputs,plan):
    profiles={p['id']:p for p in load(ROOT/'evas/validation/paper/precision-v2.json')['profiles']}
    return pipeline.inspect_plan(inputs,plan,{c['id']:c for c in cards()},profiles,q.PROFILE_BINDING,q.trace_source,validate_spectre_controls)


def precheck(inputs,backend,cases=None,tiers=None,variant=None,*,pilot=False):
    return pipeline.precheck(inputs,backend,verify,recipe_check,{c['id']:c for c in cards()},
        cases=cases,tiers=tiers,variant=variant,pilot=pilot)


def execute_one(backend,tool,env,work):
    if backend!='evas':return execution.execute_one(backend,tool,env,work)
    stages=[execution.stage([sys.executable,'-B',str(Path(__file__).resolve()),'worker',str(work),tool['kernel']],work,'simulate',execution.LIMITS)]
    wr=load(work/'worker-result.json') if (work/'worker-result.json').is_file() else dict(status='execution_failed',reason='missing worker receipt')
    return {**execution.result_state(stages,work,'waveform.csv',None,wr,backend=backend),'stages':stages}


def run(inputs,output,backend,profile_path,cases=None,tiers=None,variant=None,*,defer_analysis=False,pilot=False):
    return pipeline.run(inputs,output,backend,profile_path,execution,verify,recipe_check,
        {c['id']:c for c in cards()},analyze_work,execute_one,cases=cases,tiers=tiers,variant=variant,
        defer_analysis=defer_analysis,pilot=pilot)


def analyze(lanes,output,producer_repo=None):
    records=[];waveforms={};identities=[];parents=[]
    for lane in lanes:
        parents.append(pipeline.verify_lane(lane,Path(producer_repo) if producer_repo is not None else ROOT))
        for record in load(lane/'EXECUTION.json'):
            result=dict(record)
            if record['status']=='waveform_available':
                try:
                    work=lane/'runs'/record['label'];card=load(work/'condition.json')
                    rows=normalize(card,read_native(work/record['waveform'],record['backend']),record['backend'])
                    result.update(analyze_work(work,record,load(lane/'TOOL_IDENTITY.json'),persist=False,producer_repo=producer_repo))
                    waveforms[(record['backend'],record['condition'],record['tier'],record['variant'])]=(card,rows)
                except Exception as exc:
                    result['Q_qualification']=dict(status='evidence_insufficient',issues=['analysis_error: '+repr(exc)],failure_owner='protocol_fail')
            records.append(result)
    for key,(card,rows) in waveforms.items():
        if key[-1]!='original':continue
        trace=waveforms.get((*key[:-1],'trace'))
        if trace:identities.append(dict(backend=key[0],case=key[1],tier=key[2],**q.scientific_identity(rows,trace[1],[*card['inputs'],*card['outputs']])))
    pipeline.save_exclusive(output,dict(schema=q.ANALYSIS_ID,records=records,scientific_waveform_identity=identities,analysis_sources=analysis_identity(),parent_executions=parents,claim='new analysis only; original receipts and verdicts unchanged'),lanes)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    f=s.add_parser('freeze');f.add_argument('output',type=Path);f.add_argument('--case',action='append');f.add_argument('--tier',action='append',choices=q.TIERS);f.add_argument('--variant',action='append',choices=['original','trace'])
    r=s.add_parser('run');r.add_argument('inputs',type=Path);r.add_argument('output',type=Path);r.add_argument('--backend',required=True,choices=['evas','spectre']);r.add_argument('--profile',required=True,type=Path);r.add_argument('--case',action='append');r.add_argument('--tier',action='append',choices=q.TIERS);r.add_argument('--variant',choices=['original','trace'])
    r.add_argument('--pilot',action='store_true');r.add_argument('--defer-analysis',action='store_true')
    pc=s.add_parser('precheck');pc.add_argument('inputs',type=Path);pc.add_argument('--backend',required=True,choices=['evas','spectre']);pc.add_argument('--case',action='append');pc.add_argument('--tier',action='append',choices=q.TIERS);pc.add_argument('--variant',choices=['original','trace']);pc.add_argument('--pilot',action='store_true')
    w=s.add_parser('worker');w.add_argument('work',type=Path);w.add_argument('kernel')
    a=s.add_parser('analyze');a.add_argument('--lane',action='append',required=True,type=Path);a.add_argument('--output',required=True,type=Path);a.add_argument('--producer-repo',type=Path)
    args=p.parse_args()
    if args.mode=='freeze':freeze(args.output.resolve(),args.case,args.tier,args.variant)
    elif args.mode=='run':run(args.inputs.resolve(),args.output.resolve(),args.backend,args.profile,args.case,args.tier,args.variant,defer_analysis=args.defer_analysis,pilot=args.pilot)
    elif args.mode=='precheck':print(json.dumps(precheck(args.inputs.resolve(),args.backend,args.case,args.tier,args.variant,pilot=args.pilot)))
    elif args.mode=='worker':worker(args.work.resolve(),args.kernel)
    else:analyze(args.lane,args.output,args.producer_repo)

"""Immutable breadth inputs and bounded serial four-backend execution receipts.

Q targets bind candidate controls before execution; they are not qualifications.
Scientific grading and actual settings/provenance remain separate records.
"""
import argparse
import ast
from bisect import bisect_left, bisect_right
from decimal import Decimal
from fractions import Fraction
import math
import json
import re
from pathlib import Path
import shutil
import sys
from time import perf_counter

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'evas/validation/paper'))
sys.path.insert(0,str(ROOT/'experiments/backends/paper'))
from precision_run import (LIMITS, source_files, execute_one, load, preflight,
                           verify_tool, effective_settings, directory_budget)
from inputs import BACKENDS, decks, save, sha
from observations import read_native
from precision_report import qualification
from precision_precheck import inspect_plan, pilot_plan, measure

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


def freeze(output,*,backend_tier_profiles=None):
    data=load_contract();profiles={p['id']:p for p in data['profiles']}
    if not set(TIER_PROFILES.values())<=profiles.keys():raise ValueError('missing candidate profiles')
    binding_source=ROOT/'experiments/backends/support/precision_binding_run.py'
    definitions=[n.value for n in ast.parse(binding_source.read_text()).body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='DEEP_BOUND' for t in n.targets)]
    if len(definitions)!=1:raise ValueError('ambiguous existing deep_bound profile source')
    prior=ast.literal_eval(definitions[0])
    profiles['deep_bound']={**profiles['deep'],'id':'deep_bound','step_units':prior['step_units']}
    mapping={b:dict(TIER_PROFILES) for b in BACKENDS}
    mapping['spectre']['Q3']='deep_bound'
    if backend_tier_profiles is not None:mapping=backend_tier_profiles
    if (set(mapping)!=set(BACKENDS) or any(set(m)!=set(TIER_PROFILES) or
        any(p not in profiles for p in m.values()) for m in mapping.values())):
        raise ValueError('backend profile binding must cover every backend and tier with known candidates')
    bindings={'schema_version':'breadth-v2','backend_tier_profiles':mapping,'profiles':profiles,
              'sources':{'deep_bound':{'base_profile':'deep','overridden_controls':['step_units'],
                  'step_units_source':str(binding_source.relative_to(ROOT)),'source_sha256':sha(binding_source)}},
              'claim':'candidate controls bound before execution; fixed Q budgets are unchanged'}
    data={**data,'profiles':list(profiles.values())}
    cards=data['cards']
    if len({c['id'] for c in cards})!=len(cards):raise ValueError('duplicate card identity')
    output.mkdir(parents=True,exist_ok=False)
    save(output/'cards.json',data);save(output/'PROFILE_BINDINGS.json',bindings);plan=[];estimates=[]
    for card in cards:
        observation=observation_plan(card,data);times=observation['times_s']
        min_step=min(profiles[p]['step_units'] for m in mapping.values() for p in m.values())
        estimated_rows=2*(len(times)+int(card['stop_s']/(card['unit_s']*min_step))+1)
        estimated_bytes=estimated_rows*(len(card['ports'])+2)*32
        if estimated_bytes>BREADTH_LIMITS['file_limit_bytes']*.8:
            raise ValueError('waveform estimate exceeds file budget: '+card['id'])
        estimates.append({'condition':card['id'],'requested_points':len(times),
                          'estimated_waveform_bytes':estimated_bytes})
        physical={**card,'stimulus':{n:{'points_s_V':v} for n,v in card['inputs'].items()}}
        bind={'top_module':card['top'],'ports':card['ports'],'parameters':card['parameters']}
        for tier in TIER_PROFILES:
            for backend in BACKENDS:
                profile_id=mapping[backend][tier];profile=profiles[profile_id]
                settings={**profile,'target_tier':tier,'candidate_status':'unqualified',
                          'stop_s':card['stop_s'],'maxstep_s':card['unit_s']*profile['step_units'],
                          'spice_maxstep_s':card['unit_s']*profile['step_units']}
                generated=decks(physical,settings,bind,times,{'records':[{'time_s':t} for t in times]})
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
    paths=set(source_files())|{Path(__file__),ROOT/'experiments/backends/support/precision_precheck.py',
                ROOT/'experiments/backends/support/precision_report.py',
                ROOT/'evas/validation/paper/precision-v2.json',binding_source}
    save(output/'SOURCE_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted(paths)})
    save(output/'MANIFEST.json',{str(p.relative_to(output)):sha(p) for p in sorted(output.rglob('*')) if p.is_file()})
    return plan


def select_plan(plan,backend,family,groups=(),cards=(),tiers=()):
    available=[r for r in plan if r['backend']==backend and r['family']==family]
    for field,requested in (('group_id',groups),('condition',cards),('tier',tiers)):
        unknown=set(requested)-{r[field] for r in available}
        if unknown:raise ValueError('unknown selection '+field+': '+', '.join(sorted(unknown)))
    selected=[r for r in plan if r['backend']==backend and r['family']==family and
              (not groups or r['group_id'] in groups) and (not cards or r['condition'] in cards) and
              (not tiers or r['tier'] in tiers)]
    if not selected:raise ValueError('selection contains no frozen slots')
    return selected


def run(inputs,output,backend,profile_path,family,*,groups=(),cards=(),tiers=(),defer_analysis=False,pilot=False):
    full_plan=select_plan(load(inputs/'PLAN.json'),backend,family,groups,cards,tiers)
    plan=pilot_plan(full_plan) if pilot else full_plan
    output.mkdir(parents=True,exist_ok=False);results=[];attempts=[]
    started=perf_counter()
    timings={'status':'interrupted','precheck_s':0,'tool_preflight_s':0}
    save(output/'STARTED.json',{'schema_version':load(inputs/'PROFILE_BINDINGS.json')['schema_version'] if (inputs/'PROFILE_BINDINGS.json').is_file() else 'breadth-v1','limits':BREADTH_LIMITS,'selected':plan,
         'input_manifest_sha256':sha(inputs/'MANIFEST.json'),'profile_sha256':sha(profile_path),
         'defer_analysis':defer_analysis,'scope':'pilot' if pilot else 'full-selection',
         'full_selection':full_plan})
    try:
        with measure(timings,'precheck_s'):
            verify(inputs)
            recipe=inspect_plan(inputs,full_plan)
            save(output/'RECIPE_CHECK.json',recipe)
            data=load(inputs/'cards.json');profile=load(profile_path)
        with measure(timings,'tool_preflight_s'):
            tool,env=preflight(backend,profile,output,LIMITS);save(output/'TOOL_IDENTITY.json',tool)
        for row in plan:
            phase_timings={'input_preparation':0,'backend_execution':0,'inline_analysis':0}
            with measure(phase_timings,'input_preparation'):
                verify(inputs);verify_tool(tool,profile,env)
                work=output/'runs'/row['label'];shutil.copytree(inputs/row['work'],work)
                save(work/'INPUT_IDENTITY.json',{'source_sha256':sha(work/'dut.va'),
                     'requested_settings_sha256':sha(work/'requested_settings.json'),'deck_sha256':sha(work/row['deck'])})
            attempt={'index':len(attempts)+1,'backend':backend,'label':row['label'],
                     'status':'invoked','stages':[],'stage_receipts_complete':False}
            attempts.append(attempt);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
            try:
                with measure(phase_timings,'backend_execution'):
                    result={**row,**execute_one(backend,tool,env,work)}
                result['phase_timings_s']=phase_timings
                attempt.update(status=result['status'],stages=result.get('stages',[]),stage_receipts_complete=True)
            except Exception as exc:
                attempt.update(status='adapter_error',reason=repr(exc),
                               stages=[load(work/(n+'.json')) for n in ('compile','simulate') if (work/(n+'.json')).is_file()])
                result={**row,'status':'execution_failed','reason':repr(exc),'abort_batch':True,
                        'phase_timings_s':phase_timings}
                if defer_analysis:deferred_analysis(result,data)
                save(work/'RESULT.json',result);results.append(result)
                raise
            if defer_analysis:
                deferred_analysis(result,data)
            elif result['status']=='waveform_available':
                try:
                    with measure(phase_timings,'inline_analysis'):
                        native=read_native(work/result['waveform'],backend)
                        result['assessment']=assess(load(work/'condition.json'),native,data)
                        save(work/'ASSESSMENT-breadth.json',result['assessment'])
                        result['effective_settings']=effective_settings(work,backend)
                        result['qualification']=qualification(work,backend,result,native)
                        result['native_observation_evidence']=native_observation_evidence(
                            work,backend,result['qualification'],native,tool=tool,card=load(work/'condition.json'),contract=data)
                except Exception as exc:
                    result['analysis_error']=repr(exc)
                    result['qualification']={'status':'evidence_insufficient','issues':[repr(exc)]}
                    result['native_observation_evidence']={'status':'unknown','reason':'analysis incomplete'}
                q=result['qualification'];provenance=result['native_observation_evidence']
                if 'assessment' not in result:
                    result['assessment']={'analysis_error':result['analysis_error'],'tiers':{
                        tier['id']:{'status':'evidence_insufficient','numerical':{'status':'unknown'},
                                    'evidence':{'status':'evidence_insufficient','issues':[result['analysis_error']]}}
                        for tier in data['tiers']}}
                    save(work/'ASSESSMENT-breadth.json',result['assessment'])
                result['runtime_control_evidence']=runtime_control_evidence(backend,result.get('effective_settings',{}))
                qualified=q['status']=='qualified' and provenance['status']=='qualified' and result['runtime_control_evidence']['status']=='qualified'
                result['qualified_tiers']={tier['id']:{
                    'status':a['status'] if qualified or a['status']!='pass' else 'evidence_insufficient',
                    'settings_and_provenance':q['status'],'native_observations':provenance['status'],
                    'runtime_controls':result['runtime_control_evidence']['status']}
                    for tier in data['tiers']
                    for a in [result['assessment'].get('tiers',{}).get(tier['id'],{'status':'evidence_insufficient'})]}
            result['directory_budget']=directory_budget(work)
            save(work/'RESULT.json',result);results.append(result)
            checkpoint(output/'EXECUTION.json',results);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
            if result.get('abort_batch') or result['directory_budget']['status']!='within_limit':break
        timings['status']='complete' if len(results)==len(plan) else 'aborted'
    finally:
        recorded={r['label'] for r in results}
        selected={r['label'] for r in plan}
        results.extend({**r,'status':'not_run','reason':'lane did not reach this frozen slot'}
                       for r in plan if r['label'] not in recorded)
        results.extend({**r,'status':'not_run','reason':'pilot did not select this frozen slot'}
                       for r in full_plan if r['label'] not in selected)
        checkpoint(output/'EXECUTION.json',results);checkpoint(output/'ATTEMPTS.json',attempt_receipt(attempts))
        timings['cases']={r['label']:r['phase_timings_s'] for r in results if 'phase_timings_s' in r}
        timings['claim']='wall time of named phases; backend_execution includes compile/export; total excludes final receipt writes; not a speed ranking'
        with measure(timings,'artifact_sealing_s'):
            manifest={str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                 for p in sorted(output.rglob('*')) if p.is_file() and p.name!='FILE_MANIFEST.json'}
        timings['total_s']=perf_counter()-started
        save(output/'TIMINGS.json',timings)
        manifest['TIMINGS.json']={'sha256':sha(output/'TIMINGS.json'),'bytes':(output/'TIMINGS.json').stat().st_size}
        save(output/'FILE_MANIFEST.json',manifest)
    return results


def precheck(inputs,backend,family,*,groups=(),cards=(),tiers=(),pilot=False):
    """Inspect recipes without contacting a backend or creating run output."""
    verify(inputs)
    plan=select_plan(load(inputs/'PLAN.json'),backend,family,groups,cards,tiers)
    report=inspect_plan(inputs,plan)
    selected=pilot_plan(plan) if pilot else plan
    return {**report,'scope':'pilot' if pilot else 'full-selection',
            'selected_slots':len(selected),'selected_labels':[r['label'] for r in selected],
            'omitted_slots':len(plan)-len(selected)}


def deferred_analysis(result,contract):
    """Execution success is raw evidence availability, never a science pass."""
    result['analysis_status']='pending' if result['status']=='waveform_available' else 'not_available'
    result['qualification']={'status':'unknown','reason':'analysis deferred to independent local reanalysis'}
    result['qualified_tiers']={tier['id']:{'status':'unknown','settings_and_provenance':'unknown',
        'native_observations':'unknown','runtime_controls':'unknown'} for tier in contract['tiers']}


def runtime_control_evidence(backend,settings):
    """Qualify reported controls; a verified stateless solve has no step to cap."""
    issues=[];actual=settings.get('actual',{});requested=settings.get('requested',{})
    if backend not in ('evas','spectre'):
        return {'status':'unknown','issues':['installed-version maxstep/stop mapping not supplied'],
                'actual':actual,'claim':'deck controls alone do not prove runtime application'}
    for key in ('stop','maxstep'):
        value=actual.get(key);wanted=requested.get(key)
        if (type(value) not in (int,float) or type(wanted) not in (int,float) or
            not math.isfinite(value) or not math.isfinite(wanted) or value<=0 or wanted<=0 or
            not math.isclose(value,wanted,rel_tol=1e-12)):
            issues.append('missing or mismatched actual '+key)
    step='applied'
    if backend=='evas' and settings.get('max_step_applied') is not True:
        summary=settings.get('sample_origin_summary',{})
        observed=settings.get('observed_response',{})
        if (settings.get('max_step_applied') is False and summary and
            set(summary)=={'stateless_working_point'} and
            type(summary['stateless_working_point']) is int and summary['stateless_working_point']>0 and
            observed.get('accepted_steps')==0):
            step='not_applicable'
        else:
            step='unknown';issues.append('maxstep propagation application unavailable')
    return {'status':'unknown' if issues else 'qualified','issues':issues,'maxstep_application':step,
            'actual':actual,'claim':'validated API/readback controls; stateless origin does not use a propagation step'}


def native_observation_evidence(work,backend,qualified,rows,*,tool=None,card=None,contract=None):
    """Report export facts, and qualify only an independently checked origin path.

    read_native preserves raw rows but supplies no origin certificate. A requested
    strobe/trace deck and an aggregate accepted-row count do not identify every
    saved row. The paper observation protocol keeps those facts separate.
    """
    facts={'row_count':len(rows)};artifacts={}
    waveform=work/({'evas':'waveform.csv','spectre':'psf/tran.tran.tran'}.get(backend,'waveform.txt'))
    if waveform.is_file():artifacts[str(waveform.relative_to(work))]=sha(waveform)
    if backend=='evas':
        raw=work/'raw-response.json'
        if raw.is_file():artifacts['raw-response.json']=sha(raw)
        controls=qualified.get('additional_controls',{})
        origins=controls.get('origins',[])
        if qualified.get('status')=='qualified' and raw.is_file() and origins and controls.get('observation_mode'):
            return {'status':'qualified','method':'precision_report raw response/CSV equality and explicit origin validation',
                    'origins':origins,'artifacts':artifacts,'facts':facts,
                    'limit':'forced solver/history observations; not DC/transient phase or callback-order proof'}
    elif backend=='spectre':
        log=work/'spectre.log';deck=work/'tb.scs'
        if log.is_file():
            artifacts['spectre.log']=sha(log)
            counts=re.findall(r'Number of accepted tran steps\s*=\s*(\d+)',log.read_text())
            if len(counts)==1:
                facts['logged_accepted_steps']=int(counts[0])
                facts['rows_equal_accepted_steps_plus_initial']=len(rows)==int(counts[0])+1
        if deck.is_file():
            artifacts['tb.scs']=sha(deck)
            facts['all_strobe_export_requested']='strobeoutput=all' in deck.read_text()
        match=spectre_accepted_rows(work,rows,tool or {},card,contract)
        facts.update(match['facts'])
        if match['status']=='qualified':
            return {'status':'qualified','method':'fixed Spectre accepted step annotations matched uniquely to every PSF row',
                    'facts':facts,'artifacts':artifacts,
                    'limit':'accepted export timestamps; DC/transient phase, callback order and exact input identity remain separate'}

    else:
        log=work/'simulate.log';deck=work/('tb.cir' if backend=='openvaf_r_ngspice' else 'tb.gc')
        if log.is_file():
            artifacts['simulate.log']=sha(log)
            counts=re.findall(r'No\. of Data Rows\s*:\s*(\d+)',log.read_text())
            if len(counts)==1:
                facts['logged_plot_rows']=int(counts[0]);facts['rows_equal_plot_rows']=len(rows)==int(counts[0])
        if deck.is_file():
            artifacts[deck.name]=sha(deck)
            facts['native_export_requested']=('wrdata waveform.txt' in deck.read_text() and
                'linearize' not in deck.read_text()) if backend=='openvaf_r_ngspice' else 'trace alltime' in deck.read_text()
    return {'status':'unknown','reason':'installed-version per-row accepted/forced origin correspondence unavailable',
            'facts':facts,'artifacts':artifacts,
            'limit':'deck and aggregate export facts do not certify initial state, counters, phase, or interpolation error'}


def spectre_accepted_rows(work,rows,tool,card=None,contract=None):
    """Match sixteen-digit accepted-step annotations without nearest-row repair."""
    facts={};unknown={'status':'unknown','facts':facts}
    if (tool.get('version')!='sub-version  21.1.0.509.isr12' or
        tool.get('binary_sha256')!='72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f'):
        facts['origin_gap']='unreviewed Spectre binary/version';return unknown
    if not all((work/n).is_file() for n in ('spectre.log','tb.scs','requested_times.json')):
        facts['origin_gap']='missing log/deck/request identity';return unknown
    log=(work/'spectre.log').read_text();deck=(work/'tb.scs').read_text()
    if not re.search(r'^\s*precision\s*=\s*%\.17g\s*$',log,re.M):
        facts['origin_gap']='actual seventeen-digit export readback unavailable';return unknown
    if not all(token in deck for token in ('annotate=steps','annotatedigits=16','strobeoutput=all','skipcount=1','compression=no')):
        facts['origin_gap']='accepted step/export annotation recipe absent';return unknown
    counts=re.findall(r'Number of accepted tran steps\s*=\s*(\d+)',log)
    lines=[line for line in log.splitlines() if re.match(r'^\s*tran: time\s*=',line)]
    pattern=re.compile(r'^\s*tran: time\s*=\s*([+\-0-9.eE]+)\s*(fs|ps|ns|us|ms|s)\s*\([^)]*\),\s*step\s*=')
    if len(counts)!=1 or len(lines)!=int(counts[0]) or len(rows)!=len(lines)+1 or not rows or rows[0]['time']!=0:
        facts['origin_gap']='accepted annotation count differs from raw rows';return unknown
    units={'s':Fraction(1),'ms':Fraction(1,1000),'us':Fraction(1,10**6),
           'ns':Fraction(1,10**9),'ps':Fraction(1,10**12),'fs':Fraction(1,10**15)}
    intervals=[]
    for line in lines:
        match=pattern.match(line)
        if not match:
            facts['origin_gap']='malformed accepted time annotation';return unknown
        decimal=Decimal(match[1]);unit=units[match[2]]
        if not decimal.is_finite() or decimal<=0:
            facts['origin_gap']='invalid accepted time annotation';return unknown
        center=Fraction(decimal)*unit
        # %g removes trailing zeros. annotatedigits fixes sixteen significant
        # digits even for short tokens such as "2 ps". One final decimal unit
        # conservatively covers annotation rounding; PSF binary64 parsing adds
        # eight ulps. The core independently checks serialization uncertainty.
        radius=Fraction(Decimal(1).scaleb(decimal.adjusted()-15))*unit
        intervals.append((center-radius,center+radius))
    if any(a[1]>=b[0] for a,b in zip(intervals,intervals[1:])):
        facts['origin_gap']='accepted annotations cannot distinguish adjacent times';return unknown
    for index,(row,(lo,hi)) in enumerate(zip(rows[1:],intervals)):
        time=row['time'];padding=Fraction(8*math.ulp(time));value=Fraction(time)
        if not lo-padding<=value<=hi+padding:
            facts['origin_gap']='raw row differs from accepted annotation';return unknown
        for other in (index-1,index+1):
            if 0<=other<len(intervals) and intervals[other][0]-padding<=value<=intervals[other][1]+padding:
                facts['origin_gap']='raw row has ambiguous accepted annotation';return unknown
    # Use the frozen scientific time-serialization budget, also used by the
    # core for reference intervals and critical-point coverage. Matching never
    # changes raw times or removes boundary requests from numerical grading.
    try:
        stop=card['stop_s'];ulps=contract['budgets']['time_serialization_ulps']
        if not math.isfinite(stop) or stop<=0 or type(ulps) is not int or ulps<0:
            raise ValueError('invalid frozen time budget')
        padding=ulps*math.ulp(stop)
    except (TypeError,KeyError,ValueError):
        facts['origin_gap']='frozen strobe time uncertainty unavailable';return unknown
    facts.update(strobe_time_uncertainty_s=padding,strobe_time_budget_ulps=ulps,
                 strobe_time_budget_scale_s=stop)
    times=[row['time'] for row in rows];used=set()
    for requested in load(work/'requested_times.json'):
        # Bisect narrows candidates; exact binary64 differences enforce the
        # declared radius even when floating addition rounds the endpoints.
        indices=[i for i in range(bisect_left(times,requested-padding),bisect_right(times,requested+padding))
                 if abs(Fraction(times[i])-Fraction(requested))<=Fraction(padding)]
        if len(indices)!=1:
            facts['origin_gap']='requested strobe has no unique raw row';return unknown
        if indices[0] in used:
            facts['origin_gap']='distinct requested strobes collapse onto one raw row';return unknown
        used.add(indices[0])
    facts.update(matched_accepted_rows=len(intervals),initial_row_time_s=0,
                 requested_strobes_matched=len(load(work/'requested_times.json')))
    return {'status':'qualified','facts':facts}


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
    for mode in ('run','precheck'):
        p=sub.add_parser(mode);p.add_argument('inputs',type=Path)
        if mode=='run':
            p.add_argument('output',type=Path);p.add_argument('--profile',type=Path,required=True)
            p.add_argument('--defer-analysis',action='store_true',help='export raw evidence; leave scientific and settings analysis pending')
        p.add_argument('--backend',choices=BACKENDS,required=True)
        p.add_argument('--family',choices=('foundation','composition'),required=True)
        p.add_argument('--group',action='append',default=[]);p.add_argument('--card',action='append',default=[])
        p.add_argument('--tier',choices=tuple(TIER_PROFILES),action='append',default=[])
        p.add_argument('--pilot',action='store_true',help='first frozen condition per group/configuration; omitted slots remain not_run')
    a=parser.parse_args()
    if a.mode=='freeze':freeze(a.output.resolve())
    elif a.mode=='precheck':
        print(json.dumps(precheck(a.inputs.resolve(),a.backend,a.family,groups=a.group,cards=a.card,tiers=a.tier,pilot=a.pilot)))
    else:run(a.inputs.resolve(),a.output.resolve(),a.backend,a.profile.resolve(),a.family,
             groups=a.group,cards=a.card,tiers=a.tier,defer_analysis=a.defer_analysis,pilot=a.pilot)

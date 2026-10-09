"""Bind actual EVAS response evidence to paper roles without creating missing proofs."""
from __future__ import annotations
import argparse
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
from observations import normalize_observation


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def upper(value):
    """Round a nonnegative rational upper bound outward to binary64."""
    result=float(value)
    return math.nextafter(result,math.inf) if F(result)<value else result


def bind(path):
    p=Path(path).resolve()
    return {'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size}


def input_curve_bound(card,request):
    """Exact sup of two continuous affine PWLs on the actual executed domain."""
    domain=F(request['stop'])
    maxima={}
    def value(points,t,reference=False):
        # Existing oracle.pwl holds the reference endpoint; actual Rust source
        # must cover the executed domain and is never extended by this adapter.
        if reference and t>=points[-1][0]:return points[-1][1]
        for (a,u),(b,v) in zip(points,points[1:]):
            if a<=t<=b:return u+(v-u)*(t-a)/(b-a)
        raise ValueError('input curve coverage insufficient')
    for name,stimulus in card['stimulus'].items():
        if stimulus.get('kind')!='pwl':return None,{'reason':'unsupported non-PWL stimulus','input':name}
        ideal=[(F(str(t))/10**6,F(str(v))) for t,v in stimulus['points_T_V']]
        actual=[(F(t),F(v)) for t,v in request['inputs'][name]]
        if any(len(p)<2 or any(a[0]>=b[0] for a,b in zip(p,p[1:])) or p[0][0]>0 for p in (ideal,actual)) or actual[-1][0]<domain:
            return None,{'reason':'noncontinuous/nonmonotone or insufficient actual-domain coverage','input':name}
        knots=sorted({F(0),domain,*[t for t,_ in ideal if 0<=t<=domain],*[t for t,_ in actual if 0<=t<=domain]})
        bound=max(abs(value(ideal,t,reference=True)-value(actual,t)) for t in knots)
        maxima[name]={'bound_V':upper(bound),'exact_numerator':bound.numerator,'exact_denominator':bound.denominator,'union_knots':len(knots)}
    return max((b['bound_V'] for b in maxima.values()),default=0),{'inputs':maxima,'domain_s':[0,request['stop']],'reference_endpoint_semantics':'oracle.pwl endpoint hold; no actual-source extension'}


WORKER_DEPENDENCIES=tuple('experiments/backends/paper/'+name+'.py' for name in
                          ('runner','inputs','process','settings_readback','observations'))+(
    'experiments/archive/dvs2-starter-pilot/analyze.py','experiments/archive/dvs2-starter-pilot/suite.py')
BUILD_METADATA=('evas/pyproject.toml','evas/rust_core/Cargo.toml','evas/rust_core/Cargo.lock',
                'evas/rust_core/ir/Cargo.toml','evas/rust_core/ir/Cargo.lock',
                'evas/rust_core/build.rs','evas/rust_core/ir/build.rs',
                'evas/rust_core/rust-toolchain','evas/rust_core/rust-toolchain.toml',
                'evas/rust_core/.cargo/config','evas/rust_core/.cargo/config.toml',
                'evas/rust_core/ir/.cargo/config','evas/rust_core/ir/.cargo/config.toml')


def production_dependency(name):
    """Production scopes are defined independently of supplied manifest entries."""
    return (name in WORKER_DEPENDENCIES or name in BUILD_METADATA
            or name.startswith('evas/src/') and name.endswith('.py')
            or any(name.startswith(prefix) for prefix in ('evas/rust_core/src/','evas/rust_core/ir/src/')) and name.endswith('.rs'))


def production_dependencies(repo):
    """Enumerate the complete current production closure from the fixed audit repo."""
    repo=Path(repo)
    expected=set(WORKER_DEPENDENCIES)
    for directory,suffix in (('evas/src','.py'),('evas/rust_core/src','.rs'),('evas/rust_core/ir/src','.rs')):
        found={str(path.relative_to(repo)) for path in (repo/directory).rglob('*'+suffix) if path.is_file()}
        if not found:raise ValueError('audited production source directory missing: '+directory)
        expected.update(found)
    expected.update(name for name in BUILD_METADATA if (repo/name).is_file())
    mandatory=('evas/pyproject.toml','evas/rust_core/Cargo.toml','evas/rust_core/Cargo.lock','evas/rust_core/ir/Cargo.toml')
    if any(not (repo/name).is_file() for name in (*WORKER_DEPENDENCIES,*mandatory)):
        raise ValueError('audited production dependency missing')
    return {name:sha(repo/name) for name in sorted(expected)}


def producer_identity(sources,repo):
    expected=production_dependencies(repo)
    supplied={name for name in sources if production_dependency(name)}
    missing=sorted(set(expected)-supplied);extra=sorted(supplied-set(expected))
    changed=sorted(name for name,digest in expected.items() if name in supplied and sources[name]!=digest)
    return {'verified':not (missing or extra or changed),'required_source_count':len(expected),
            'missing_dependencies':missing,'unexpected_dependencies':extra,'changed_dependencies':changed,
            'audited_production_sources':expected}


def execution_identity(lane,work,card,*,build_record=None,source_manifest=None,tool_profile=None,producer_repo=None):
    """Verify existing receipts; never create a source/build/execution receipt."""
    if any(p is None for p in (lane,build_record,source_manifest,tool_profile)):
        return {'verified':False,'basis':'missing explicit actual lane/build/source manifest/tool profile identity chain'}
    lane=Path(lane).resolve();work=Path(work).resolve()
    manifest=json.loads((lane/'FILE_MANIFEST.json').read_text())
    def bound(path):
        path=Path(path).resolve()
        try:relative=str(path.relative_to(lane))
        except ValueError:raise ValueError('execution artifact is outside lane')
        entry=manifest.get(relative)
        if not isinstance(entry,dict) or entry.get('sha256')!=sha(path) or entry.get('bytes')!=path.stat().st_size:
            raise ValueError('execution manifest identity mismatch: '+relative)
        return json.loads(path.read_text())
    tool=bound(lane/'TOOL_IDENTITY.json');record=bound(lane/('final-record-'+card['id']+'.json'))
    started=bound(work/'STARTED.json');program=bound(work/'program.json');worker=bound(work/'worker-result.json')
    actual_request=bound(work/'request.json')
    for name in ('raw-response.json','observation.json','condition.json','breakpoint_requests.json',actual_request['requested_times']):
        bound(work/name)
    source_entry=manifest.get(str((work/'dut.va').relative_to(lane)),{})
    if source_entry.get('sha256')!=sha(work/'dut.va') or source_entry.get('bytes')!=(work/'dut.va').stat().st_size:
        raise ValueError('execution source manifest mismatch')
    if (record.get('backend')!='evas' or record.get('condition')!=card['id'] or record.get('status')!='waveform_available'
        or record.get('source_sha256')!=sha(work/'dut.va') or record.get('condition_identity')!=canonical_sha(card)
        or started.get('condition')!=card['id'] or started.get('source_sha256')!=sha(work/'dut.va')
        or started.get('deck_sha256')!=sha(work/'request.json') or started.get('tool_identity_sha256')!=sha(lane/'TOOL_IDENTITY.json')
        or worker.get('status')!='waveform_available'):
        raise ValueError('actual source/execution identity mismatch')
    observation=record.get('observation',{})
    if observation.get('sha256')!=sha(work/'observation.json') or (lane/observation.get('path','')).resolve()!=work/'observation.json':
        raise ValueError('actual normalized execution binding mismatch')
    def successful(stage):
        return stage.get('status')=='completed' and stage.get('returncode')==0 and stage.get('timeout') is False and stage.get('cleanup',{}).get('complete') is True
    stages=record.get('stages',[])
    if not stages or not all(successful(stage) and tool.get('kernel') in stage.get('argv',[]) for stage in stages) or not successful(tool.get('probe',{})):
        raise ValueError('actual execution did not complete with identified kernel')
    build=json.loads(Path(build_record).read_text());sources=json.loads(Path(source_manifest).read_text());profile=json.loads(Path(tool_profile).read_text())
    if (not successful(build.get('stage',{})) or build.get('kernel_sha256')!=tool.get('kernel_sha256')
        or not build.get('kernel_sha256') or build.get('source_manifest_sha256')!=sha(source_manifest)
        or build.get('cargo_lock_sha256')!=sources.get('evas/rust_core/Cargo.lock')
        or not build.get('source_revision') or profile.get('build_record_sha256')!=sha(build_record)
        or canonical_sha(profile)!=tool.get('profile_identity') or profile.get('backend')!='evas'
        or profile.get('kernel')!=tool.get('kernel') or profile.get('kernel_sha256')!=tool.get('kernel_sha256')):
        raise ValueError('actual source/build/tool chain mismatch')
    compiler=build.get('compiler_identity',{})
    if not all(compiler.get(name,{}).get('actual_binary_sha256') for name in ('cargo','rustc')):
        raise ValueError('missing actual compiler identity')
    repo=Path(producer_repo) if producer_repo else Path(__file__).resolve().parents[3]
    producer=producer_identity(sources,repo)
    compatible=producer['verified']
    return {'verified':compatible,'basis':'actual source/build/kernel/profile/launch/raw identity chain; native producer files match audited implementation' if compatible else 'producer source differs from audited implementation',
            'source_revision':build['source_revision'],'kernel_sha256':tool['kernel_sha256'],
            'stateless_program':all(program.get(key)==[] for key in ('states','events','operators')),
            'artifacts':{name:bind(path) for name,path in {'lane_manifest':lane/'FILE_MANIFEST.json','tool':lane/'TOOL_IDENTITY.json',
                'final_record':lane/('final-record-'+card['id']+'.json'),'build_record':build_record,'source_manifest':source_manifest,'tool_profile':tool_profile}.items()},
            'producer_identity':producer}


def derive(card, request, requested_times, response, previous, review, *, core_sha, source_sha, breakpoints=None, execution=None):
    """Return role facts; containment validates transport, not the solver proof.

    Source review is independent and explicit. Native query evaluation is reported
    using audited noninterpolated producer semantics and actual execution identity.
    """
    expected_inputs={n:[[t*1e-6,v] for t,v in stimulus['points_T_V']] for n,stimulus in card['stimulus'].items()}
    if request['inputs']!=expected_inputs or request['stop']!=card['stop_T']*1e-6:
        raise ValueError('actual stimulus/stop differs from frozen card')
    nodes=response['nodes']; times=response['transient']['times']; solutions=response['solutions']
    if times!=requested_times or len(times)!=len(solutions):
        raise ValueError('response does not preserve actual request times')
    if any(isinstance(t,bool) or not isinstance(t,(int,float)) or not math.isfinite(t) for t in times):
        raise ValueError('invalid actual timestamps')
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for solution in solutions for v in solution['voltages']):
        raise ValueError('invalid actual voltages')
    if len(set(nodes))!=len(nodes) or not set(card['observables'])<=set(nodes):
        raise ValueError('missing or duplicate actual nodes')
    rows=[dict(time=t,**dict(zip(nodes,s['voltages'],strict=True))) for t,s in zip(times,solutions,strict=True)]
    if previous['rows']!=rows or previous.get('condition')!=card['id'] or previous.get('backend')!='evas':
        raise ValueError('raw/normalized identity mismatch')
    roles={r:{'status':'unknown','basis':'missing actual evidence'} for r in
           ('source','time','voltage','inputs','native_initial','native_counters','native_phase')}
    matches=[r for r in review.get('records',[]) if r.get('condition')==card['id']]
    if review.get('schema_version')!=1 or review.get('cards_sha256',review.get('core-v1.json_file_sha'))!=core_sha:
        raise ValueError('source review core identity mismatch')
    if len(matches)!=1:
        raise ValueError('source review must contain exactly one condition record')
    record=matches[0]
    if record.get('source_sha256')!=source_sha or record.get('card_sha256')!=canonical_sha(card):
        raise ValueError('source review card/source identity mismatch')
    if record.get('status')=='reviewed' and ((isinstance(record.get('basis'),str) and record['basis'].strip()) or (isinstance(record.get('basis'),list) and record['basis'] and all(isinstance(x,str) and x.strip() for x in record['basis']))):
        roles['source']={'status':'established','basis':record['basis'],'limits':record.get('limits')}
    else:
        roles['source']={'status':record.get('status','unknown'),'basis':'external source review is not reviewed with a nonempty basis'}
    nominal=[F(str(t)) for t in requested_times]
    errors=[abs(F(t)-n) for t,n in zip(times,nominal,strict=True)]
    # Include independent decimal card obligations, rather than just comparing
    # a request echo with itself. Every named anchor/center must have a real row.
    named=[a['t_T'] for a in card.get('anchors',[])]+[w['center_T'] for w in card['observation_windows']]
    for value in named:
        requested=float(value)*1e-6
        if requested not in times:
            raise ValueError('missing named nominal request row')
        errors.append(abs(F(requested)-F(str(value))/10**6))
    stop_roundoff=abs(F(request['stop'])-F(str(card['stop_T']))/10**6)
    errors.append(stop_roundoff)
    if not times or times[-1]!=request['stop']:
        raise ValueError('actual response endpoint differs from executed stop')
    time_error=upper(max(errors,default=F(0)))
    roles['time']={'status':'established','basis':'every raw timestamp equals its binary64 request; exact rational decimal-to-binary64 bounds include card anchors and centers','bound_s':time_error,'actual_stop_s':request['stop'],'decimal_stop_fraction':[F(str(card['stop_T'])).numerator,F(str(card['stop_T'])).denominator*10**6],'stop_roundoff_s':upper(stop_roundoff)}
    evidence=response.get('observation_evidence')
    voltage_error=None; origins=['unknown']*len(rows)
    if evidence is not None:
        if evidence.get('schema_version')!=1 or evidence.get('nodes')!=nodes:
            raise ValueError('invalid observation evidence schema/node identity')
        controls=evidence['effective_controls']
        for key in ('absolute_V','relative','stop_s','max_step_s'):
            value=controls.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<0 or (key!='relative' and value==0):
                raise ValueError('invalid actual effective controls')
        if type(controls.get('max_step_applied')) is not bool:
            raise ValueError('invalid actual max_step application flag')
        bounds=evidence['voltage_bounds_V']; actual_origins=evidence['sample_origins']
        if len(bounds)!=len(rows) or len(actual_origins)!=len(rows):
            raise ValueError('evidence row count mismatch')
        radii=[]; missing=[]
        for i,(intervals,solution) in enumerate(zip(bounds,solutions,strict=True)):
            if intervals is None:
                missing.append(i);continue
            if len(intervals)!=len(nodes):
                raise ValueError('bound node count mismatch')
            for node,interval,value in zip(nodes,intervals,solution['voltages'],strict=True):
                if len(interval)!=2 or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) for x in interval):
                    raise ValueError('nonfinite or invalid interval')
                lo,hi=interval
                if not lo<=value<=hi:
                    raise ValueError('interval order/representative containment mismatch')
                if node in card['observables']:
                    radii.extend((F(value)-F(lo),F(hi)-F(value)))
        if not missing:
            voltage_error=upper(max(radii,default=F(0)))
            roles['voltage']={'status':'established','basis':'existing solver certificates exported as outward binary64 interval hulls; maximum radius around unchanged returned representative','bound_V':voltage_error,'limits':'certificate is for actual binary64 IR and PWL inputs; transport containment is not independent certificate verification'}
        else:
            roles['voltage']={'status':'unknown','basis':'solver did not export a certificate for all rows','missing_rows':missing}
        known={'accepted_controller_frame','certified_causal_frame','implicit_history_evaluation','stateless_working_point','unknown'}
        if any(o not in known for o in actual_origins):
            raise ValueError('invalid actual sample origin')
        identity_ok=bool(execution and execution.get('verified') is True and roles['source']['status']=='established')
        point_origins={'accepted_controller_frame','certified_causal_frame','stateless_working_point'}
        stateless_ok=identity_ok and execution.get('stateless_program') is True and response['transient'].get('events')==[]
        origins=['accepted' if (identity_ok and bounds[i] is not None and (o in point_origins and (o!='stateless_working_point' or stateless_ok)
                  or o=='implicit_history_evaluation' and times[i]==0 and evidence.get('initial_settled') is True)) else 'unknown'
                 for i,o in enumerate(actual_origins)]
        native=bool(origins) and all(o=='accepted' for o in origins)
        if native:
            for role in ('native_counters','native_phase'):
                roles[role]={'status':'established','basis':'unmodified certified native point observations from audited controller/causal/stateless producers and bound actual execution identity; no interpolation, rounding or modulo repair'}
        initial=evidence.get('initial_settled') is True and times and times[0]==0 and origins[0]=='accepted'
        # initial_settled alone is after initialization, but a t=0 callback may
        # already have occurred. The original contract requires before callback.
        events=response['transient'].get('events',[])
        def positive_event(e):
            return (isinstance(e,dict) and isinstance(e.get('time'),(int,float)) and e['time']>0
                    and e.get('observation_time_bounds',[e['time'],e['time']])[0]>0
                    and all(t.get('time_bounds',[e['time'],e['time']])[0]>0 for t in e.get('fired_triggers',[])))
        if initial and all(positive_event(e) for e in events):
            roles['native_initial']={'status':'established','basis':'actual initial_settled at raw t=0 accepted frame and every exported callback time strictly positive'}
        else:
            roles['native_initial']={'status':'unknown','basis':'initial_settled does not by itself prove a row before the first sample/cross callback'}
    input_error,input_details=input_curve_bound(card,request)
    roles['inputs']={'status':'established' if input_error is not None else 'unknown',
        'basis':'Fraction exact maximum on union of decimal-card and binary64-request knots and actual executed-domain endpoints; absolute affine difference reaches its maximum at an endpoint',
        'bound_V':input_error,'details':input_details,
        'limits':'continuous mathematical PWL curves, matching original-knot exact_source semantics; representative floating interpolation error is handled separately by output certificate; this is not an ideal-input output-error proof'}
    cohort=None
    if card['observation_windows']:
        cohort_records=[];unresolved=[]
        request_records=breakpoints.get('records',[]) if isinstance(breakpoints,dict) else []
        for center in sorted({window['center_T']*1e-6 for window in card['observation_windows']}):
            candidates=[r for r in request_records if r.get('time_s')==center]
            indices=[i for i,t in enumerate(times) if t==center]
            if (len(candidates)==1 and len(indices)==1 and isinstance(candidates[0].get('request_id'),str)
                and candidates[0]['request_id'] and origins[indices[0]]=='accepted'):
                cohort_records.append({'nominal_time_s':center,'row_index':indices[0],'request_id':candidates[0]['request_id']})
            else:unresolved.append(center)
        cohort={'serialization_error_s':time_error,'records':cohort_records}
        roles['boundary_cohort']={'status':'unknown' if unresolved else 'established',
            'basis':'exact frozen breakpoint request IDs map one-to-one to unchanged raw native center rows; all columns share this single committed response/event history',
            'unresolved_centers_s':unresolved,'records':cohort_records}
    required=['source','time','voltage','inputs','native_initial']
    if any(n in ('count','na','nb') for n in card['observables']):required.append('native_counters')
    if card['id'] in ('CP-02','CO-VCO-01'):required.append('native_phase')
    if card['observation_windows']:required.append('boundary_cohort')
    return rows,origins,{'roles':roles,'required_roles':required,'missing_roles':[r for r in required if roles[r]['status']!='established'],
                        'time_error_s':time_error,'voltage_error_V':voltage_error,'input_error_V':input_error,
                        'effective_controls':evidence.get('effective_controls') if evidence else None,
                        'actual_sample_origins':evidence.get('sample_origins') if evidence else None,'boundary_cohort':cohort,'execution_identity':execution}


def adapt(core, condition, work, source_review, output, *, lane=None, build_record=None, source_manifest=None, tool_profile=None, producer_repo=None):
    core=Path(core);work=Path(work);source_review=Path(source_review);output=Path(output)
    if output.exists():raise ValueError('output directory must be new')
    if output.resolve().is_relative_to(work.resolve()):raise ValueError('output must be outside actual run directory')
    data=json.loads(core.read_text());card=next(c for c in data['cards'] if c['id']==condition)
    request=json.loads((work/'request.json').read_text())
    paths={'core':core,'condition':work/'condition.json','source_review':source_review,'source':work/'dut.va','request':work/'request.json',
           'times':work/request['requested_times'],'raw':work/'raw-response.json','normalized':work/'observation.json'}
    if (work/'breakpoint_requests.json').is_file():paths['breakpoints']=work/'breakpoint_requests.json'
    # Identity is the actual consumed bytes. This creates no execution receipt.
    identities={name:bind(path) for name,path in paths.items()}
    loaded={name:json.loads(path.read_text()) for name,path in paths.items() if name not in ('core','source')}
    if loaded['condition']!=card:
        raise ValueError('actual condition does not equal frozen card')
    if (work/'dut.va').read_text()!=card['source']:
        raise ValueError('actual source does not equal frozen card source')
    execution=execution_identity(lane,work,card,build_record=build_record,source_manifest=source_manifest,tool_profile=tool_profile,producer_repo=producer_repo)
    rows,origins,report=derive(card,request,loaded['times'],loaded['raw'],loaded['normalized'],loaded['source_review'],
                             core_sha=sha(core),source_sha=sha(work/'dut.va'),breakpoints=loaded.get('breakpoints'),execution=execution)
    report.update(schema_version=1,condition=condition,backend='evas',identities=identities,
                  claim='new actual-evidence derivation; preserves previous raw/normalized rows and leaves missing qualifications unknown')
    output.mkdir(parents=True)
    snapshot=output/'analysis_adapter.py'
    snapshot.write_bytes(Path(__file__).read_bytes())
    report['analysis_adapter']={'path':str(snapshot.resolve()),'sha256':sha(snapshot)}
    report_path=output/'evidence.json';report_path.write_text(json.dumps(report,separators=(',',':'),allow_nan=False)+'\n')
    certificates={role:{'method':fact['basis'],'artifact_path':str(report_path.resolve()),'sha256':sha(report_path)}
                  for role,fact in report['roles'].items() if fact['status']=='established'}
    q={key:report[key] for key in ('time_error_s','voltage_error_V','input_error_V')}
    q.update(qualified=not report['missing_roles'],source_validated=report['roles']['source']['status']=='established',
             native_initial=report['roles']['native_initial']['status']=='established',input_bounds_qualified=report['roles']['inputs']['status']=='established',
             exact_time_qualified=all(o=='accepted' for o in origins),qualification_evidence=certificates)
    if report['boundary_cohort'] is not None:q['boundary_cohort']=report['boundary_cohort']
    normalized=normalize_observation(card,'evas',rows,origins,q,contract=data['shared_contract'])
    (output/'observation.json').write_text(json.dumps(normalized,separators=(',',':'),allow_nan=False)+'\n')
    return report,normalized


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('core',type=Path);parser.add_argument('condition');parser.add_argument('work',type=Path)
    parser.add_argument('source_review',type=Path);parser.add_argument('output',type=Path)
    for name in ('lane','build-record','source-manifest','tool-profile','producer-repo'):parser.add_argument('--'+name,type=Path)
    args=parser.parse_args();adapt(args.core,args.condition,args.work,args.source_review,args.output,lane=args.lane,
        build_record=args.build_record,source_manifest=args.source_manifest,tool_profile=args.tool_profile,producer_repo=args.producer_repo)

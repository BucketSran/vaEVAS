"""Assess qualified normalized samples. No simulator invocation or score table."""
import hashlib
import json
import math
import re
import sys
from pathlib import Path
try:
    from .oracle import values, error_bound, pwl
except ImportError:
    from oracle import values, error_bound, pwl

HERE=Path(__file__).resolve().parent
BATCH=json.loads((HERE/'core-v1.json').read_text())
CARDS={c['id']:c for c in BATCH['cards']}
T=BATCH['units']['T_s']
DEPENDENCY_FILES=('criteria.py','oracle.py','core-v1.json')
LOADED_FILES={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in DEPENDENCY_FILES}
RUNTIME={'python':sys.version,'math_sha256':hashlib.sha256(Path(math.__file__).read_bytes()).hexdigest()}
COUNTERS={'EV-SH-01':{'count':[2,4,6,8]},'EV-HC-01':{'count':[1.375,3.375]},'EV-HC-02':{'count':[2.75,5.375]},'TM-01':{'count':[2,6]},'SI-01':{'na':[2,4,6],'nb':[3,6]},'CO-SH-01':{'count':[2,3,4,6,8]},'CO-HC-01':{'count':[1.375,3.375]}}


def identity():
    files={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in DEPENDENCY_FILES}
    if files!=LOADED_FILES:raise ValueError('Checker dependency changed after import; reload under a new identity')
    dependency={'files':files,'runtime':RUNTIME}
    return {'version':'paper-criteria-v1',**dependency,'sha256':hashlib.sha256(json.dumps(dependency,sort_keys=True).encode()).hexdigest()}


def prop(name,status,**details):return dict(name=name,status=status,**details)


def finite_nonnegative(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0


def verified_evidence(record):
    if not isinstance(record,dict) or not record.get('method') or not isinstance(record.get('artifact_path'),str):return False
    try:
        artifact=Path(record['artifact_path'])
        return artifact.is_file() and hashlib.sha256(artifact.read_bytes()).hexdigest()==record.get('sha256')
    except OSError:
        return False


def decision(error,uncertainty,budget):
    if error+uncertainty <= budget:return 'P'
    if max(0,error-uncertainty)>budget:return 'F'
    return 'I'


def aggregate(properties):
    states={p['status'] for p in properties}
    return 'F' if 'F' in states else 'I' if 'I' in states else 'P'


def event_limits(card, port):
    """Bind callback windows to frozen source guards and actual PWL slopes."""
    limits=[]
    guards=re.findall(r"cross\(V\((\w+)\)-([0-9.]+),([+-]1),([^,]+),([^)]+)\)",card['source'])
    for event in card['event_contract']:
        if event['kind']=='wrap':continue
        if 'instance' in event and event['instance']!={'na':'A','nb':'B'}.get(port):continue
        for nominal in event['nominal_T']:
            window=list(event['window_T']);slope=0;channel=None
            if event['kind']=='cross':
                matched=[g for g in guards if ('channel' not in event or g[0]==event['channel']) and ('direction' not in event or int(g[2])==event['direction'])]
                if len(matched)!=1:raise ValueError('Ambiguous frozen cross guard')
                channel,threshold,direction,time_tol,expr_tol=matched[0]
                points=card['stimulus'][channel]['points_T_V']
                segment=next(((a,va,b,vb) for (a,va),(b,vb) in zip(points,points[1:]) if a<nominal<b),None)
                if segment is None:raise ValueError('Cross root lacks a unique PWL segment')
                a,va,b,vb=segment;slope=(vb-va)/(b-a)
                if abs(pwl(points,nominal)-float(threshold))>1e-12 or (slope>0)!=(int(direction)>0):raise ValueError('Frozen cross root or direction disagrees with stimulus')
                width=min(float(time_tol)/T,float(expr_tol)/abs(slope))
                if abs(window[0])>1e-15 or abs(window[1]-width)>1e-15:raise ValueError('Frozen cross window disagrees with source/stimulus')
                window=[0,width]
            limits.append({'nominal_T':nominal,'window_T':window,'slope_V_per_T':abs(slope),'channel':channel,'kind':event['kind']})
    return sorted(limits,key=lambda e:e['nominal_T'])


def boundary_rows(card, rows, qualification):
    """Return only attested requested-center records, never nearest ordinary rows."""
    centers={w['center_T'] for w in card['observation_windows'] if w['include_exact_center']}
    if not centers:return {},[]
    cohort=qualification.get('boundary_cohort',{})
    evidence=qualification.get('qualification_evidence',{}).get('boundary_cohort')
    precision=cohort.get('serialization_error_s') if isinstance(cohort,dict) else None
    if not verified_evidence(evidence) or not finite_nonnegative(precision) or precision>qualification['time_error_s']:
        return {},[{'nominal_T':c,'status':'I','reason':'Missing requested-center source or bounded serialization evidence'} for c in sorted(centers)]
    records=cohort.get('records',[])
    if not isinstance(records,list):records=[]
    found={};missing=[]
    for center in sorted(centers):
        nominal=center*T;roundoff=4*math.ulp(nominal)
        candidates=[r for r in records if isinstance(r,dict) and isinstance(r.get('nominal_time_s'),(int,float)) and not isinstance(r['nominal_time_s'],bool) and math.isfinite(r['nominal_time_s']) and abs(r['nominal_time_s']-nominal)<=roundoff]
        if len(candidates)==1:
            record=candidates[0];i=record.get('row_index');request=record.get('request_id')
            if isinstance(i,int) and not isinstance(i,bool) and 0<=i<len(rows) and isinstance(request,str) and request and abs(rows[i]['time_s']-nominal)<=precision+roundoff:
                found[center]=(i,dict(record,serialization_error_s=precision));continue
        missing.append({'nominal_T':center,'status':'I','reason':'Requested nominal center has no uniquely sourced row within serialization precision'})
    return found,missing


def bound_status(lower,upper,budget):
    return 'F' if lower>budget else 'P' if upper<=budget else 'I'


def assess(case_id, rows, qualification, execution_state='completed'):
    if not isinstance(case_id,str) or case_id not in CARDS:raise ValueError('Unknown condition: '+str(case_id))
    card=CARDS[case_id]
    answer={'condition_id':case_id,'execution_state':execution_state,'status':'I','properties':[],
            'checker_identity':identity(),'claim_limit':'Maximum error on qualified observed records; unobserved between-record short pulses remain outside this claim.'}
    if execution_state in ('T','U','X'):
        answer['status']=execution_state;return answer
    if execution_state!='completed':raise ValueError('execution_state must be completed, T, U or X')
    props=answer['properties']
    q=qualification
    required=set(card['observables'])
    numeric=('time_error_s','voltage_error_V','input_error_V')
    if (not q.get('qualified') or not q.get('source_validated') or not q.get('input_bounds_qualified') or not q.get('native_initial') or q.get('time_unit')!='s' or q.get('voltage_unit')!='V'
        or any(not finite_nonnegative(q.get(k)) for k in numeric)):
        props.append(prop('observation','I',reason='Missing source/units/uncertainty qualification'));return answer
    needed=['source','time','voltage','inputs','native_initial']
    if case_id in COUNTERS:needed.append('native_counters')
    if case_id in ('CP-02','CO-VCO-01'):needed.append('native_phase')
    evidence=q.get('qualification_evidence',{})
    if not isinstance(evidence,dict):
        props.append(prop('observation','I',reason='Qualification evidence must map roles to records'));return answer
    for role in needed:
        record=evidence.get(role,{})
        if not verified_evidence(record):
            props.append(prop('observation','I',reason='Missing or unverifiable qualification evidence for '+role));return answer
    answer['qualification_evidence']=evidence
    if (q['time_error_s']>1e-11 or q['voltage_error_V']>5e-5 or q['input_error_V']>1e-5):
        props.append(prop('observation','I',reason='Uncertainty exceeds the predeclared observation contract'));return answer
    if len(rows)<2 or any(not required|{'time_s'} <= r.keys() or any(not isinstance(r[k],(float,int)) or isinstance(r[k],bool) or not math.isfinite(r[k]) for k in required|{'time_s'}) for r in rows):
        props.append(prop('observation','I',reason='Missing/nonfinite samples or columns'));return answer
    times=[r['time_s']/T for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])) or abs(times[0])>1e-12 or abs(times[-1]-card['stop_T'])>1e-10:
        props.append(prop('observation','I',reason='Nonmonotone or truncated time domain'));return answer
    gap_ok=all((b-a)*T<=2e-10+1e-20 for a,b in zip(times,times[1:]))
    local_ok=True
    for w in card['observation_windows']:
        local=[x for x in times if w['start_T']-1e-12<=x<=w['end_T']+1e-12]
        local_ok &= bool(local) and local[0]<=w['start_T']+2e-5 and local[-1]>=w['end_T']-2e-5 and all((b-a)*T<=w['max_gap_s']+1e-20 for a,b in zip(local,local[1:]))
    if not gap_ok or not local_ok:
        props.append(prop('observation','I',reason='Required ordinary/dense windows not covered'));return answer
    props.append(prop('observation','P',rows=len(rows)))
    # Source-column incompatibility invalidates the observation before DUT verdicts.
    for port,stim in card['stimulus'].items():
        maximum=0;maximum_excess=-math.inf
        for x,row in zip(times,rows):
            target=stim['value_V'] if stim['kind']=='dc' else pwl(stim['points_T_V'],x)
            error=abs(row[port]-target)
            budget=q['input_error_V']+q['voltage_error_V']+error_bound(card,port,x,q['time_error_s']/T,0,0)
            maximum=max(maximum,error);maximum_excess=max(maximum_excess,error-budget)
        props.append(prop('input_consistency:'+port,'I' if maximum_excess>0 else 'P',max_observed_error=maximum,max_budget_excess=maximum_excess,units='V',scope='Observation/source compatibility, not DUT behavior'))
    if any(p['status']=='I' for p in props):return answer
    centers,missing=boundary_rows(card,rows,q)
    if card['observation_windows']:
        props.append(prop('boundary_cohort','I' if missing else 'P',missing=missing,rule='Attested requested nominal centers within evidenced serialization precision'))
    if missing:answer['missing_boundary_observations']=missing
    events={}; event_bounds={}; max_event_error=0; counter_values={}; terr=q['time_error_s']/T; verr=q['voltage_error_V']
    for port, nominal in COUNTERS.get(case_id,{}).items():
        if not q.get('native_counters'):
            props.append(prop('events','I',reason='Counter samples require native, noninterpolated records'));answer['status']=aggregate(props);return answer
        nums=[round(r[port]) for r in rows]
        marker_error=max(abs(r[port]-n) for r,n in zip(rows,nums))
        marker_status=decision(marker_error,verr,.001)
        props.append(prop('counter_voltage:'+port,marker_status,max_observed_error=marker_error,uncertainty=verr,budget=.001,units='V'))
        if marker_status!='P':
            answer['status']=aggregate(props);return answer
        if nums[0]!=0 or nums[-1]!=len(nominal) or any(b-a not in (0,1) for a,b in zip(nums,nums[1:])):
            props.append(prop('events','F',port=port,reason='Invalid callback count or order'));answer['status']='F';return answer
        indices=[i for i in range(1,len(rows)) if nums[i]!=nums[i-1]]
        if len(indices)!=len(nominal):
            props.append(prop('events','F',port=port,reason='Missing callback'));answer['status']='F';return answer
        inferred=[];bounds=[]
        limits=event_limits(card,port)
        if [e['nominal_T'] for e in limits]!=nominal:raise ValueError('Counter schedule disagrees with frozen card')
        native_brackets=[];native_pairs=[];legal_windows=[]
        for j,(i,nom,limit) in enumerate(zip(indices,nominal,limits)):
            lo,hi=times[i-1]-terr,times[i]+terr
            native_brackets.append([lo,hi]);native_pairs.append([times[i-1],times[i]])
            root_error=q['input_error_V']/limit['slope_V_per_T'] if limit['kind']=='cross' else 0
            legal=(nom+limit['window_T'][0]-root_error,nom+limit['window_T'][1]+root_error)
            legal_windows.append(list(legal))
            if hi<legal[0] or lo>legal[1]:
                props.append(prop('event_time','F',port=port,index=j,observed_T=[lo,hi],legal_T=list(legal)));answer['status']='F';return answer
            lo,hi=max(lo,legal[0]),min(hi,legal[1]);inferred.append((lo+hi)/2);bounds.append([lo,hi]);max_event_error=max(max_event_error,(hi-lo)/2)
        events[port]=inferred;event_bounds[port]=bounds;counter_values[port]=nums
        props.append(prop('event_history','P',port=port,intervals_T=bounds,native_brackets_T=native_brackets,native_sample_pairs_T=native_pairs,legal_windows_T=legal_windows,rule='Exists one compatible legal native-counter history shared by every dependent port; not a measured bound proving every possible actual callback time legal'))
    boundary=[]
    for port,nominals in COUNTERS.get(case_id,{}).items():
        for j,nominal in enumerate(nominals):
            if nominal not in centers:continue
            i,source=centers[nominal]
            lo,hi=event_bounds[port][j]
            relation='post-event' if hi<times[i]-terr else 'pre-event' if lo>times[i]+terr else 'unresolved tie'
            boundary.append({'cohort_source':source,'counter_port':port,'nominal_T':nominal,'sample_time_s':rows[i]['time_s'],'raw_values':{k:rows[i][k] for k in card['observables']},'latent_event_interval_T':[lo,hi],'observed_callback_stage':counter_values[port][i],'relation':relation,'status':'I' if relation=='unresolved tie' else 'P','time_uncertainty_s':q['time_error_s']})
    if boundary:answer['event_boundary_observations']=boundary
    errors={}; uncertainties={}; budgets={};lower_bounds={};upper_bounds={}
    for i,(x,row) in enumerate(zip(times,rows)):
        cv={k:v[i] for k,v in counter_values.items()}
        expected=values(card,x,events,cv)
        for port,target in expected.items():
            if port in COUNTERS.get(case_id,{}) or port in card['stimulus']:continue
            diff=abs(row[port]-target)
            wrapped=port=='phase' and case_id in ('CP-02','CO-VCO-01')
            if wrapped:
                diff=abs((row[port]-target+.5)%1-.5)
            if port in card['stimulus']:budget=q['input_error_V']
            elif port=='phase':budget=.001
            elif port=='out' and case_id in ('TM-01','CO-SH-01','CO-HC-01','CP-02','CO-VCO-01'):budget=.003
            else:budget=.001
            uncertainty=verr+error_bound(card,port,x,terr,max_event_error,q['input_error_V'])
            errors[port]=max(errors.get(port,0),diff)
            uncertainties[port]=max(uncertainties.get(port,0),uncertainty)
            budgets[port]=budget
            lower_bounds[port]=max(lower_bounds.get(port,0),max(0,diff-uncertainty))
            upper_bounds[port]=max(upper_bounds.get(port,0),diff+uncertainty)
    for port in errors:
        props.append(prop(('input_consistency:' if port in card['stimulus'] else 'voltage:')+port,bound_status(lower_bounds[port],upper_bounds[port],budgets[port]),max_error_lower_bound=lower_bounds[port],max_error_upper_bound=upper_bounds[port],max_observed_error=errors[port],uncertainty=uncertainties[port],budget=budgets[port],units='cycle' if port=='phase' else 'V'))
    if case_id in ('CP-02','CO-VCO-01'):
        if not q.get('native_phase'):
            props.append(prop('wrap_observation','I',reason='Wrapping requires qualified native phase records'));answer['status']=aggregate(props);return answer
        phase=[r['phase'] for r in rows]
        range_status='F' if any(v < -verr or v>1+verr for v in phase) else 'P'
        props.append(prop('modulo_range',range_status))
        roots=card['event_contract'][0]['nominal_T']
        ordinary_error=0; ordinary_uncertainty=0;ordinary_lower=0;ordinary_upper=0
        for x,row in zip(times,rows):
            if all(abs(x-root)>.0001 for root in roots):
                target=values(card,x,{},{} )['phase']
                error=abs(row['phase']-target);uncertainty=verr+error_bound(card,'phase',x,terr,0,q['input_error_V'])
                ordinary_error=max(ordinary_error,error);ordinary_uncertainty=max(ordinary_uncertainty,uncertainty)
                ordinary_lower=max(ordinary_lower,max(0,error-uncertainty));ordinary_upper=max(ordinary_upper,error+uncertainty)
        props.append(prop('phase_absolute_outside_wrap_windows',bound_status(ordinary_lower,ordinary_upper,.001),max_error_lower_bound=ordinary_lower,max_error_upper_bound=ordinary_upper,max_observed_error=ordinary_error,uncertainty=ordinary_uncertainty,budget=.001,units='cycle'))
        drops=[i for i in range(1,len(rows)) if phase[i]-phase[i-1]<-.5]
        roots=card['event_contract'][0]['nominal_T']
        status='P'; intervals=[]
        if len(drops)!=len(roots):status='F'
        else:
            for i,root in zip(drops,roots):
                lo,hi=times[i-1]-terr,times[i]+terr;intervals.append([lo,hi])
                if hi<root-.0001 or lo>root+.0001:status='F'
                elif lo<root-.0001 or hi>root+.0001:status='I'
        props.append(prop('wrap_count_and_windows',status,count=len(drops),expected_count=len(roots),intervals_T=intervals))
        endpoint=[]
        for level,root in zip(card['event_contract'][0]['unwrapped_integer_levels'],roots):
            if root not in centers:continue
            i,source=centers[root];r=rows[i]
            endpoint.append({'cohort_source':source,'nominal_T':root,'unwrapped_integer_level':level,'sample_time_s':r['time_s'],'raw_phase':r['phase'],'scalar_endpoint_error':abs(r['phase']),'circular_error':min(abs(r['phase']),abs(1-r['phase'])),'time_uncertainty_s':q['time_error_s'],'status':'I','reason':'Finite time uncertainty straddles modulo endpoint; raw discrepancy retained.'})
        answer['exact_boundary_observations']=endpoint
        answer['endpoint_semantics_status']='I'
        answer['claim_limit']+=' Exact modulo endpoint semantics remain separately I at finite observation-time uncertainty.'
    answer['required_properties']=[p['name'] for p in props]
    answer['separate_diagnostics']=(['event_boundary_observations'] if boundary else [])+(['exact_boundary_observations'] if case_id in ('CP-02','CO-VCO-01') else [])
    answer['status']=aggregate(props)
    return answer


def assess_observation(observation, execution_state='completed'):
    """Bridge the experiment-owned normalized observation envelope without claiming qualification."""
    q=dict(observation.get('qualification',{}))
    metadata=observation.get('metadata',{})
    evidence=q.get('qualification_evidence',metadata.get('qualification_evidence',{}))
    if isinstance(evidence,list):
        evidence={r['role']:r for r in evidence if isinstance(r,dict) and 'role' in r}
    q['qualification_evidence']=evidence
    rows=[dict(r,time_s=r.get('time')) for r in observation.get('rows',[])]
    case=observation.get('condition_id',observation.get('condition'))
    if not isinstance(case,str):raise ValueError('Observation requires condition_id or condition string')
    origins=metadata.get('sample_origins',[])
    if not origins or origins[0]!='accepted':q['native_initial']=False
    if len(origins)!=len(rows) or any(x!='accepted' for x in origins):
        # Output interpolation can be qualified, but callback and modulo jumps need
        # native brackets. Do not infer native status from a CSV format or backend name.
        q['native_counters']=False;q['native_phase']=False
    return assess(case,rows,q,execution_state)


def freeze_checker(destination):
    """Create an immutable local identity manifest; an existing different file is an error."""
    target=Path(destination)
    manifest=identity()
    text=json.dumps(manifest,sort_keys=True,indent=2)+'\n'
    if target.exists():
        if target.read_text()!=text:raise ValueError('Refusing to replace a different checker freeze')
    else:
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('x') as stream:stream.write(text)
    return manifest

"""One reference, three external accuracy targets; v1 remains immutable.

Assessment never reads a requested backend tolerance to set a passing threshold.
Observations must come from one native/forced run, with export provenance checked
by the backend adapter. No interpolation, window deletion or per-point fitting.
"""
from bisect import bisect_left
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path

from precision_reference import FirstOrder, pwl_range, slope_bound, outward


def load_contract(path=None):
    path=Path(path) if path else Path(__file__).with_name('precision-v2.json')
    data=json.loads(path.read_text());source=path.parent/data['model_set']['path']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=data['model_set']['sha256']:
        raise ValueError('frozen model set drift')
    old=json.loads(source.read_text());data['cards']=old['cards']
    if len(data['cards'])!=data['denominator']:raise ValueError('denominator mismatch')
    return data


def shape(card):
    pts=card['inputs']['u']
    if all(v==pts[0][1] for _,v in pts):return 'constant'
    return 'small' if card['scale_V']<1 else 'ramp'


def critical_points(card):
    points=[{'id':'start','time_s':0.},{'id':'stop','time_s':card['stop_s']}]
    for name,pts in card['inputs'].items():
        points.extend({'id':f'input:{name}:{i}','time_s':t} for i,(t,_) in enumerate(pts))
    for i,t in enumerate(card.get('events_s',[]),1):
        for name,s in (('nominal',t),('earliest',t-card['event_early_s']),('latest',t+card['event_late_s'])):
            points.append({'id':f'event:{i}:{name}','time_s':s})
    return points


def observation_plan(card,contract):
    config=contract['observation'];stop=card['stop_s']
    critical=critical_points(card)
    # Set union only coalesces exactly equal float values. Every obligation keeps
    # its identity, even when several obligations share the same instant.
    step=Fraction(card['unit_s'])*Fraction(config['global_request_units'])
    times={float(i*step) for i in range(math.ceil(Fraction(stop)/step)+1)}
    for p in list(critical):
        t=p['time_s'];times.add(t)
        for side,delta in (('left',-config['padding_s']),('right',config['padding_s'])):
            q=t+delta
            if 0<=q<=stop:
                times.add(q);critical.append({'id':p['id']+':'+side,'time_s':q})
    if card['family']=='sample_hold':
        interval=config[shape(card)+'_interval_s']
        for t in card['events_s']:
            a=Fraction(t)-Fraction(card['event_early_s'])-Fraction(config['padding_s'])
            b=Fraction(t)+Fraction(card['event_late_s'])+Fraction(config['padding_s'])
            n=math.ceil((b-a)/Fraction(interval))
            times.update(float(a+(b-a)*i/n) for i in range(n+1))
    ordered=sorted(t for t in times if 0<=t<=stop)
    return {'id':config['id'],'target_tier':config['target_tier'],'times_s':ordered,
            'critical':critical,'claim':'requests only; qualify actual native records separately'}


def error_bounds(value,lo,hi,uncertainty):
    return max(0.,lo-value-uncertainty,value-hi-uncertainty), max(abs(value-lo),abs(value-hi))+uncertainty


def _uncertainty(value,scale,ulps):return ulps*math.ulp(max(abs(value),scale))


def rows_digest(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def event_evidence(path,rows):
    """Read a reviewed independent timing analysis, bound to this exact trace.

    Hashes establish identity, not scientific validity. The adapter/reviewer
    must establish that the linked artifact measures actual callback times,
    independently of requested times, predicted roots and the sampled output.
    No current backend gets this qualification from self-reported root records.
    """
    path=Path(path);data=json.loads(path.read_text())
    if data.get('waveform_rows_sha256')!=rows_digest(rows):raise ValueError('event evidence belongs to another waveform')
    if data.get('method')!='independent_callback_trace':raise ValueError('unqualified event timing method')
    source=(path.parent/data['artifact']).resolve()
    if not source.is_relative_to(path.parent.resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=data['artifact_sha256']:
        raise ValueError('event timing artifact drift')
    events={}
    for entry in data['events']:
        k=entry['index'];lo,hi=map(Fraction,entry['time_bounds_s'])
        if type(k) is not int or k<1 or k in events or lo>hi:raise ValueError('invalid event timing interval/index')
        events[k]=(outward(lo,False),outward(hi,True))
    return events


def assess(card,rows,contract,*,event_evidence_path=None):
    budgets=contract['budgets'];obs=contract['observation']
    result={'schema_version':2,'condition':card['id'],'reference':'represented PWL and first-order ODE; independent bounded arithmetic',
            'claim':'finite native/forced observations including named boundaries; not all-time proof','tiers':{}}
    required=['time',*card['inputs'],*card['outputs']]
    def unavailable(reason):
        result.update(behavior={'status':'unknown'},observation_issues=[reason])
        result['tiers']={q['id']:{'status':'evidence_insufficient','reasons':[reason]} for q in contract['tiers']}
        return result
    if len(rows)<3 or any(any(type(r.get(k)) not in (float,int) or not math.isfinite(r[k]) for k in required) for r in rows):
        return unavailable('missing or nonfinite observations')
    times=[r['time'] for r in rows]
    if any(b<=a for a,b in zip(times,times[1:])):return unavailable('timestamps are not strictly increasing')
    ut=_uncertainty(card['stop_s'],card['stop_s'],budgets['time_serialization_ulps'])
    def uv(v,scale=card['scale_V']):return _uncertainty(v,scale,budgets['voltage_serialization_ulps'])
    issues=[];confirmed={}
    if event_evidence_path is not None:
        try:
            confirmed=event_evidence(event_evidence_path,rows)
            if any(k>card.get('expected_events',0) for k in confirmed):
                raise ValueError('independent trace contains unexpected event index')
        except (ValueError,KeyError,OSError,TypeError) as exc:
            confirmed={};issues.append('invalid independent event evidence: '+str(exc))
    if abs(times[0])>ut or abs(times[-1]-card['stop_s'])>ut:issues.append('incomplete start/stop coverage')
    gap=max(b-a for a,b in zip(times,times[1:]))
    if gap>card['unit_s']*budgets['global_gap_units']+2*ut:issues.append('observation gap exceeds frozen limit')
    distance=budgets['boundary_distance_s']
    for point in critical_points(card):
        t=point['time_s'];i=bisect_left(times,t)
        near=times[max(0,i-2):i+3]
        if not near or min(abs(q-t) for q in near)>distance+ut:
            issues.append('missing boundary: '+point['id'])
        if 0<t<card['stop_s']:
            if not any(t-distance-ut<=q<t-ut for q in near) or not any(t+ut<q<=t+distance+ut for q in near):
                issues.append('missing boundary sides: '+point['id'])
    input_errors={};ref_uncertainty=0.
    for name,pts in card['inputs'].items():
        scale=1. if name=='clk' else card['scale_V'];slope=slope_bound(pts);lower=upper=0.
        for row in rows:
            lo,hi,ref_u=pwl_range(pts,row['time'],row['time'])
            u=uv(row[name],scale)+slope*ut
            low,up=error_bounds(row[name],lo,hi,u)
            lower=max(lower,low);upper=max(upper,up);ref_uncertainty=max(ref_uncertainty,ref_u)
        input_errors[name]={'lower_V':lower,'upper_V':upper,'scale_V':scale}
    if any('bench_ref' in r for r in rows):
        if any(type(r.get('bench_ref')) not in (int,float) or not math.isfinite(r['bench_ref']) for r in rows):
            issues.append('invalid ground alias')
        else:
            input_errors['bench_ref']={'lower_V':max(max(0.,abs(r['bench_ref'])-uv(r['bench_ref'])) for r in rows),
                                      'upper_V':max(abs(r['bench_ref'])+uv(r['bench_ref']) for r in rows),'scale_V':card['scale_V']}
    behavior={'status':'pass','issues':[]};lower=upper=drift_low=drift_up=resolution=bracket_width=0.;witness=None;events=[]
    def accumulate(row,lo,hi,ref_u):
        nonlocal lower,upper,resolution,witness,ref_uncertainty
        u=uv(row['y']);low,up=error_bounds(row['y'],lo,hi,u)
        lower=max(lower,low)
        if up>upper:upper=up;witness={'time_s':row['time'],'actual_V':row['y'],'reference_V':[lo,hi]}
        resolution=max(resolution,hi-lo+u);ref_uncertainty=max(ref_uncertainty,ref_u)
    if card['family']=='first_order':
        reference=FirstOrder(card)
        time_u=2*card['scale_V']/card['tau_s']*ut
        for row in rows:
            lo,hi=reference.bounds(row['time'])
            accumulate(row,lo-time_u,hi+time_u,hi-lo)
    else:
        counts=[round(r['count']) for r in rows]
        if any(abs(r['count']-n)>budgets['count_V'] for r,n in zip(rows,counts)):
            behavior['issues'].append('counter is not an integer-valued state')
        nmax=card['expected_events']
        if counts[0]!=0 or counts[-1]!=nmax or any(b-a not in (0,1) for a,b in zip(counts,counts[1:])) or any(n<0 or n>nmax for n in counts):
            behavior['issues'].append('initial/final count, missing, repeated, or reversed event')
        if behavior['issues']:
            behavior['status']='behavior_error'
        else:
            groups=[[] for _ in range(nmax+1)];transitions={}
            for i,(row,n) in enumerate(zip(rows,counts)):
                groups[n].append(row)
                if i and n!=counts[i-1]:transitions[n]=(times[i-1]-ut,times[i]+ut)
            for row in groups[0]:accumulate(row,card['initial_V'],card['initial_V'],0.)
            for k,group in enumerate(groups):
                if not group:
                    behavior['issues'].append('missing holding stage');behavior['status']='behavior_error';continue
                u=2*max(uv(r['y']) for r in group)
                drift=max(r['y'] for r in group)-min(r['y'] for r in group)
                drift_low=max(drift_low,max(0.,drift-u));drift_up=max(drift_up,drift+u)
                if k==0:continue
                a,b=transitions[k];native_bracket=[a,b];nominal=card['events_s'][k-1]
                if k in confirmed:
                    ca,cb=confirmed[k]
                    if a<=ca<=cb<=b:a,b=ca,cb
                    else:issues.append(f'event {k} independent time conflicts with native counter interval')
                legal_lo=nominal-card['event_early_s'];legal_hi=nominal+card['event_late_s']
                root_u=0.
                if card['clock']=='cross':
                    # The observed clock error provides an explicit conservative
                    # uncertainty in the root of this fixed monotone PWL ramp.
                    root_u=input_errors['clk']['upper_V']/card['clock_slope_V_s']
                    legal_hi=nominal+min(card['event_late_s'],card['cross_expression_tolerance_V']/card['clock_slope_V_s'])
                if b<legal_lo-root_u or a>legal_hi+root_u:
                    timing='behavior_error';behavior['status']='behavior_error'
                    behavior['issues'].append(f'event {k} outside legal time window')
                elif a>=legal_lo+root_u and b<=legal_hi-root_u:
                    timing='pass'
                else:
                    timing='evidence_insufficient';issues.append(f'event {k} bracket not wholly inside legal window')
                bracket_width=max(bracket_width,b-a)
                # Do not clip to the legal window, even in an inconclusive run.
                lo,hi,ref_u=pwl_range(card['inputs']['u'],a,b)
                stage_low=stage_up=0.
                for row in group:
                    low,up=error_bounds(row['y'],lo,hi,uv(row['y']))
                    stage_low=max(stage_low,low);stage_up=max(stage_up,up)
                    accumulate(row,lo,hi,ref_u)
                events.append({'index':k,'counter_bracket_s':native_bracket,'qualified_callback_s':[a,b],
                               'independent_event_evidence_used':k in confirmed and [a,b]!=native_bracket,'legal_s':[legal_lo,legal_hi],
                               'clock_root_uncertainty_s':root_u,'timing_status':timing,
                               'sample_reference_range_V':[lo,hi],'error_lower_V':stage_low,'error_upper_V':stage_up,
                               'hold_drift_upper_V':drift+u,'observations':len(group)})
    result.update(behavior=behavior,observation_issues=issues,row_count=len(rows),extent_s=[times[0],times[-1]],
                  max_gap_s=gap,time_serialization_bound_s=ut,input_errors=input_errors,
                  error_lower_V=lower,error_upper_V=upper,hold_drift_lower_V=drift_low,hold_drift_upper_V=drift_up,
                  observation_uncertainty_V=resolution,reference_uncertainty_V=ref_uncertainty,
                  max_callback_bracket_s=bracket_width,event_records=events,worst=witness)
    for index,tier in enumerate(contract['tiers']):
        B=(budgets['absolute_V']+budgets['relative']*card['scale_V'])*tier['factor']
        reasons=list(issues)
        input_bad=input_unknown=False
        for name,err in input_errors.items():
            limit=(budgets['absolute_V']+budgets['relative']*err['scale_V'])*tier['factor']*obs['input_fraction']
            if err['lower_V']>limit:input_bad=True;reasons.append('input outside budget: '+name)
            elif err['upper_V']>limit:input_unknown=True;reasons.append('input error overlaps budget: '+name)
        if ref_uncertainty>B*obs['reference_fraction']:reasons.append('reference uncertainty exceeds tier limit')
        if resolution>B*obs['observation_fraction']:reasons.append('observation uncertainty exceeds tier limit')
        if card['family']=='sample_hold' and bracket_width>obs['bracket_limits_s'][shape(card)][index]:
            reasons.append('callback bracket exceeds tier limit')
        if behavior['status']=='behavior_error':status='behavior_error';reasons+=behavior['issues']
        elif input_bad:status='input_mismatch'
        elif lower>B or drift_low>B:status='numerical_error';reasons.append('confirmed output or holding error exceeds tier budget')
        elif reasons or input_unknown or upper>B or drift_up>B:
            status='evidence_insufficient'
            if upper>B or drift_up>B:reasons.append('output error overlaps tier budget')
        else:status='pass'
        result['tiers'][tier['id']]={'status':status,'voltage_budget_V':B,'reasons':reasons}
    return result

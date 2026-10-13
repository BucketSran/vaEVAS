"""Versioned SH-X root-window assessment; precision_v2 remains immutable.

The assessment body is a deliberate fork of precision_v2.assess. Shared helpers,
voltage targets, full callback intervals and all non-timing gates remain unchanged.
Only the cross window uses independent represented-input roots and the existing
serialization allowance. Strict semantic timing is reported separately.
"""
from bisect import bisect_left
import math

from precision_v2 import (load_contract, critical_points, error_bounds, _uncertainty,
                          event_evidence, shape)
from precision_reference import FirstOrder, pwl_range, slope_bound, outward
from root_windows import reference_roots, timing


def assess(card,rows,contract,*,event_evidence_path=None,committed_callback_boxes=None):
    """Assess qualified committed boxes supplied by an external producer adapter.

    This function validates structure and waveform compatibility, not producer
    identity. The caller must bind every supplied box to original raw records,
    compiled source and the externally verified kernel. It is not an independent
    Spectre trace. The historical event_evidence_path protocol remains available.
    """
    roots=reference_roots(card)
    if card['id']!='SH-X-RAMP':
        raise ValueError('root-v3 sample-hold assessment only qualifies SH-X-RAMP')
    frozen=load_contract()
    if any(contract.get(key)!=frozen[key] for key in ('budgets','observation','tiers')):
        raise ValueError('root-v3 requires unchanged frozen budgets, observations and tiers')
    supplied={}
    if committed_callback_boxes is not None:
        if event_evidence_path is not None:
            raise ValueError('choose one callback evidence protocol')
        if (type(committed_callback_boxes) is not dict or
            any(type(k) is not int for k in committed_callback_boxes) or
            set(committed_callback_boxes)!=set(range(1,card['expected_events']+1))):
            raise ValueError('committed callback inventory must contain every event exactly once')
        for k,box in committed_callback_boxes.items():
            if (type(box) not in (list,tuple) or len(box)!=2 or
                any(type(v) not in (float,int) or not 0<=v<=card['stop_s'] or
                    not math.isfinite(v) for v in box) or
                not 0<=box[0]<=box[1]<=card['stop_s']):
                raise ValueError('invalid complete committed callback box')
            supplied[k]=tuple(box)
    budgets=contract['budgets'];obs=contract['observation']
    result={'schema_version':3,'reference_version':'root-window-v3','condition':card['id'],'reference':'exact represented-input PWL roots; unchanged bounded sample-hold reference',
            'claim':'finite native/forced observations including named boundaries; not all-time proof','tiers':{},
            'strict_semantic_timing':'unresolved','serialized_resolution_timing':'evidence_insufficient'}
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
    issues=[];confirmed=supplied
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
                a,b=transitions[k];native_bracket=[a,b]
                if k in confirmed:
                    ca,cb=confirmed[k]
                    if a<=ca<=cb<=b:a,b=ca,cb
                    else:
                        method='committed callback' if committed_callback_boxes is not None else 'independent time'
                        issues.append(f'event {k} {method} conflicts with native counter interval')
                root=roots[k-1]
                legal_lo=outward(root.exact,False)
                legal_hi=outward(root.exact+root.late,True)
                # Input fidelity remains graded separately by the frozen logic.
                # S only describes exported time resolution, not an early VA tolerance.
                root_u=input_errors['clk']['upper_V']/card['clock_slope_V_s']
                root_timing=timing(root,[a,b],card['stop_s'],budgets['time_serialization_ulps'])
                event_status=root_timing['serialized_resolution_timing']
                if event_status=='behavior_error':
                    behavior['status']='behavior_error'
                    behavior['issues'].append(f'event {k} outside represented-input root window')
                elif event_status!='pass':
                    issues.append(f'event {k} bracket not wholly inside serialized root window')
                bracket_width=max(bracket_width,b-a)
                # Do not clip to the legal window, even in an inconclusive run.
                lo,hi,ref_u=pwl_range(card['inputs']['u'],a,b)
                stage_low=stage_up=0.
                for row in group:
                    low,up=error_bounds(row['y'],lo,hi,uv(row['y']))
                    stage_low=max(stage_low,low);stage_up=max(stage_up,up)
                    accumulate(row,lo,hi,ref_u)
                events.append({'index':k,'counter_bracket_s':native_bracket,'qualified_callback_s':[a,b],
                               'independent_event_evidence_used':event_evidence_path is not None and k in confirmed and [a,b]!=native_bracket,
                               'committed_callback_evidence_used':committed_callback_boxes is not None and k in confirmed and [a,b]!=native_bracket,
                               'callback_evidence_method':('externally_qualified_committed_callback' if committed_callback_boxes is not None
                                   else 'independent_callback_trace' if event_evidence_path is not None else 'native_counter_bracket'),
                               'legal_s':[legal_lo,legal_hi],
                               'clock_root_uncertainty_s':root_u,'timing_status':event_status,
                               **root_timing,
                               'sample_reference_range_V':[lo,hi],'error_lower_V':stage_low,'error_upper_V':stage_up,
                               'hold_drift_upper_V':drift+u,'observations':len(group)})
    if len(events)==card['expected_events']:
        for field,unknown in [('strict_semantic_timing','unresolved'),
                              ('serialized_resolution_timing','evidence_insufficient')]:
            values=[event[field] for event in events]
            result[field]=('behavior_error' if 'behavior_error' in values else
                           'pass' if all(value=='pass' for value in values) else unknown)
    result.update(behavior=behavior,observation_issues=issues,row_count=len(rows),extent_s=[times[0],times[-1]],
                  max_gap_s=gap,time_serialization_bound_s=ut,input_errors=input_errors,
                  error_lower_V=lower,error_upper_V=upper,hold_drift_lower_V=drift_low,hold_drift_upper_V=drift_up,
                  observation_uncertainty_V=resolution,reference_uncertainty_V=ref_uncertainty,
                  max_callback_bracket_s=bracket_width,event_records=events,worst=witness,
                  timing_claim='serialized resolution acceptance does not prove strict no-early VA semantics')
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

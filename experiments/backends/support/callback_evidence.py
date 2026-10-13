"""Qualify completed EVAS callback records without changing frozen Q budgets.

Caller verifies the lane manifest and supplies the independently reviewed producer
identity. This module never grants that identity, edits raw records, synthesizes
waveform rows, clips callback boxes, or guesses events by nearest nominal time.
The supported scope has direct discrete counters, including sampled-integral
consumers. Integral/filter voltages still use the original reference and checker;
a callback certificate does not qualify their continuous history by itself.
"""
from copy import deepcopy
from fractions import Fraction as F
import hashlib
import math

SUPPORTED = {'F07-base', 'EC01-v1', 'EC02-v1', 'EC03-v1', 'EC04-v1',
             'EC07-v1', 'EC10-v1', 'EC20-v1'}


def finite(x):return type(x) in (int,float) and math.isfinite(x)


def _origin_label(origin):
    return f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"


def _box(box, time, stop):
    if (not isinstance(box,(list,tuple)) or len(box)!=2 or
        not all(finite(v) for v in box) or not finite(time) or
        not 0<=box[0]<=time<=box[1]<=stop):
        raise ValueError('invalid complete callback box')
    return box


def _counter_state(program, name):
    node=program['nodes'].index(name);ground=program['nodes'].index('0')
    matches=[]
    for c in program['contributions']:
        rhs=c['rhs'];sign=1 if (c['positive'],c['negative'])==(node,ground) else -1 if (c['positive'],c['negative'])==(ground,node) else 0
        if not sign:continue
        if rhs.get('op')=='state' and sign==1:matches.append(rhs['state'])
        elif (rhs.get('op')=='multiply' and rhs['left']==dict(op='affine',constant=float(sign),terms=[])
              and rhs['right'].get('op')=='state'):matches.append(rhs['right']['state'])
        else:raise ValueError('counter is not a direct state contribution')
    if len(matches)!=1:raise ValueError('ambiguous counter contribution')
    return matches[0]


def _fixed_clock(trigger, occurrence, box):
    # This proves the scheduled physical moment from the reviewed EVAS fixed
    # timer producer, not from the frozen expected answer or printed time.
    # Keep its complete observation box; never replace it by this point.
    if (trigger.get('kind')!='timer' or trigger.get('enabled') is not True or
        not finite(trigger.get('start')) or not finite(trigger.get('period')) or
        trigger['start']<=0 or trigger['period']<0):return None
    if trigger['period']==0 and occurrence:
        raise ValueError('one-shot fixed timer repeated')
    tick=F(trigger['start'])+occurrence*F(trigger['period'])
    if not F(box[0])<=tick<=F(box[1]):
        raise ValueError('physical fixed clock is outside complete callback box')
    return tick


def callbacks(card, program, response, rows, *, producer_qualified=False):
    """Return complete boxes only after identity, state and waveform checks.

    producer_qualified must come from external source/kernel/manifest review,
    never from a field in the response. Missing optional point bounds are valid
    only under that reviewed EventRecord producer contract.
    """
    try:
        if not producer_qualified or card['id'] not in SUPPORTED:
            raise ValueError('unreviewed producer or unsupported adapter scope')
        if program['schema_version']!=response['schema_version'] or program['nodes']!=response['nodes']:
            raise ValueError('program/response identity mismatch')
        if response['observation_evidence']['initial_settled'] is not True:
            raise ValueError('initial state was not settled')
        if not rows:raise ValueError('missing waveform')
        channels=card['counter_channels']
        if not channels:raise ValueError('missing direct persistent counters')
        states={name:_counter_state(program,name) for name in channels}
        if len(set(states.values()))!=len(states):raise ValueError('counter states are aliased')
        actual=response['transient']['events'];expected=card['events']
        if len(actual)!=len(expected):raise ValueError('missing or extra committed callback')
        previous=[s['initial'] for s in program['states']]
        bounds={};history=[];occurrences={};previous_clock=None
        for i,(record,e) in enumerate(zip(actual,expected,strict=True)):
            index=record['event']
            if type(index) is not int or not 0<=index<len(program['events']):raise ValueError('invalid compiled event index')
            compiled=program['events'][index]
            name=e['counter'];state=states[name]
            if (record['origin']!=_origin_label(compiled['origin']) or
                compiled['origin']['instance']!=program['states'][state]['instance']):
                raise ValueError('event origin or counter instance mismatch')
            before,after=record['before'],record['after']
            if before!=previous or len(after)!=len(previous) or not all(finite(v) for v in before+after):
                raise ValueError('broken accepted state chain')
            if (after[state]!=before[state]+1 or e['index']!=after[state] or
                any(after[other]!=before[other] for channel,other in states.items() if channel!=name)):
                raise ValueError('wrong counter update or frozen event order')
            trigger=compiled['trigger']
            box=_box(record.get('observation_time_bounds',[record['time'],record['time']]),record['time'],card['stop_s'])
            if trigger['kind']=='or':
                fired=record['fired_triggers']
                if record['kind']!='or' or len(fired)!=1:raise ValueError('missing or ambiguous OR leaf')
                leaf=fired[0]['trigger']
                if type(leaf) is not int or not 0<=leaf<len(trigger['triggers']):raise ValueError('invalid OR leaf')
                trigger=trigger['triggers'][leaf]
                if fired[0]['kind']!=trigger['kind']:raise ValueError('OR leaf kind mismatch')
                leaf_box=_box(fired[0]['time_bounds'],record['time'],card['stop_s'])
                if not box[0]<=leaf_box[0]<=leaf_box[1]<=box[1]:
                    raise ValueError('OR leaf is outside complete callback box')
                guard=fired[0].get('guard_value')
            else:
                if record['kind']!=trigger['kind']:raise ValueError('record/trigger kind mismatch')
                guard=record.get('guard_value')
            if trigger['kind']!=e['kind']:raise ValueError('wrong frozen event kind')
            if e['kind']=='cross':
                if not finite(guard) or abs(guard)>trigger['expression_tolerance']:
                    raise ValueError('unproved crossing guard')
                dependencies=[]
                def nodes(x):
                    if x.get('op')=='affine':dependencies.extend(t['node'] for t in x['terms'] if t['coefficient'] and program['nodes'][t['node']]!='0')
                    for key in ('left','right'):
                        if key in x:nodes(x[key])
                nodes(trigger['guard'])
                if set(dependencies)!={program['nodes'].index(e['input'])} or trigger['direction']!=(1 if e['slope_V_s']>0 else -1):
                    raise ValueError('cross input or direction mismatch')
            early=F(e['nominal_s'])-F(e['early_s']);late=F(e['nominal_s'])+F(e['late_s'])
            if e['kind']=='cross':late=min(late,F(e['nominal_s'])+F(e['expression_tolerance_V'])/abs(F(e['slope_V_s'])))
            if F(box[0])<early or F(box[1])>late:raise ValueError('complete callback box exceeds legal window')
            occurrence=occurrences.get(index,0)
            clock=_fixed_clock(trigger,occurrence,box)
            occurrences[index]=occurrence+1
            if history and history[-1]['box_s'][1]>=box[0]:
                if previous_clock is None or clock is None or previous_clock>=clock:
                    raise ValueError('strict callback order is unproved')
            previous_clock=clock
            bounds[e['id']]=list(box);history.append(dict(event_id=e['id'],counter=name,box_s=list(box),before=before[state],after=after[state],
                physical_clock_fraction=None if clock is None else [clock.numerator,clock.denominator]))
            previous=after
        ut=16*math.ulp(card['stop_s'])
        for name,state in states.items():
            if previous[state]!=channels[name]['final']:
                raise ValueError('wrong final counter')
            for row in rows:
                if not finite(row.get('time')) or not finite(row.get(name)):raise ValueError('invalid waveform counter')
                possible={channels[name]['initial']}
                for item in history:
                    if item['counter']!=name:continue
                    lo,hi=item['box_s']
                    if row['time']>hi+ut:possible={item['after']}
                    elif row['time']>=lo-ut:possible.add(item['after'])
                if not any(abs(row[name]-value)<=1e-9 for value in possible):
                    raise ValueError('waveform counter contradicts committed history')
        return dict(status='qualified',event_bounds_s=bounds,history=history,
                    claim='complete accepted callback boxes; no whole-trajectory proof')
    except (ValueError,KeyError,TypeError,IndexError,OverflowError) as exc:
        return dict(status='unknown',reason=str(exc))


def reanalyze(science, card, program, response, rows, contract, *, producer_qualified=False):
    """Keep old assessment beside a new assessment using proved actual boxes.

    The original reference and all B, B/10 and B/100 limits are reused. Only the
    old waveform-bracket issues supplanted by the complete callback certificate
    can be removed. Numerical errors and unrelated observation gaps survive.
    """
    old=science.assess(card,rows,contract)
    proof=callbacks(card,program,response,rows,producer_qualified=producer_qualified)
    result=dict(original_assessment=old,callback_evidence=proof)
    if proof['status']!='qualified':return result
    if not all(key in old.get('behavior',{}) for key in ('errors','issues')):
        result['reanalyze_status']='original waveform assessment is incomplete'
        return result
    reference=science._reference(card)
    def actual_reference(c,t,unused):return reference(c,t,deepcopy(proof['event_bounds_s']))
    new=science.assess(card,rows,contract,reference=actual_reference)
    # These issues concern only the broad bracket replaced by this certificate.
    resolved={'full callback bracket does not fit legal window: '+e['id'] for e in card['events']}
    if card.get('order_evidence_required'):
        # callbacks() proved frozen physical order by disjoint complete boxes
        # or the independently reviewed fixed-clock producer. Boxes stay intact.
        resolved.update({'independent callback order evidence unavailable',
                         'cross-channel callback order is unresolved'})
    if new['behavior']['errors']:return result
    def keep(issues):return [x for x in issues if x not in resolved]
    new['behavior']['issues']=keep(new['behavior']['issues'])
    new['behavior']['status']='unknown' if new['behavior']['issues'] else 'pass'
    new['event_bounds_s']=deepcopy(proof['event_bounds_s'])
    new['observation_issues']=keep(new['observation_issues'])
    new['evidence']=dict(status='evidence_insufficient' if new['observation_issues'] else 'complete',issues=new['observation_issues'])
    for tier in new['tiers'].values():
        tier['evidence']['issues']=keep(tier['evidence']['issues'])
        tier['evidence']['status']='evidence_insufficient' if tier['evidence']['issues'] else 'complete'
        tier['behavior']=deepcopy(new['behavior'])
        tier['status']=('numerical_error' if tier['numerical']['status']=='numerical_error' else
                        'evidence_insufficient' if tier['evidence']['issues'] else tier['numerical']['status'])
    result['new_assessment']=new
    return result

"""Initial/cross OR keeps one source event and explicit initial leaf provenance.

All states below are supplied by the caller's source-derived execution. An
initial OR batch is removed only after validating its complete state/provenance.
"""
import copy
import math
from initial_advisory_contract import check_advisories_before_initial_removal
from dataclasses import asdict


def check_initial_union_batch(result,program,before,after,count,zero_timer=None):
    wire=program if isinstance(program,dict) else asdict(program)
    records=result['transient']['events']
    assert [s['initial'] for s in wire['states']]==before
    assert result['transient']['state_names']==[s['instance']+':'+s['name'] for s in wire['states']]
    assert len(before)==len(after)
    assert all(type(v) in (int,float) and math.isfinite(v) for v in before+after)
    expected=[]
    for index,event in enumerate(wire['events']):
        trigger=event['trigger']
        if trigger['kind']=='or':
            initial=[i for i,leaf in enumerate(trigger['triggers']) if leaf['kind']=='initial_step']
            if initial:
                assert len(initial)==1
                assert all(leaf['kind'] in ('initial_step','cross') for leaf in trigger['triggers'])
                expected.append((index,event,initial[0]))
    expected.sort(key=lambda item:(item[1]['expanded_statement_ordinal'],item[0]))
    assert len(expected)==count
    actual=[r for r in records if r['kind']=='or' and any(f['kind']=='initial_step' for f in r.get('fired_triggers',[]))]
    assert len(actual)==count and actual==records[:count]
    assert len([r for r in records if r['time']==0])==count+(zero_timer is not None)
    for record,(index,event,leaf) in zip(actual,expected,strict=True):
        origin=event['origin'];assert not origin.get('expansion')
        assert record['event']==index and type(record['event']) is int
        assert record['origin']==f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"
        assert record['time']==0 and record.get('observation_time_bounds',[0,0])==[0,0]
        assert record['fired_triggers']==[dict(trigger=leaf,kind='initial_step')]
        assert 'guard_value' not in record
        assert record['before']==before and record['after']==after
    final=after
    if zero_timer is not None:
        ordinal,timer_before,timer_after=zero_timer
        candidates=[(i,e) for i,e in enumerate(wire['events'])
                    if e['expanded_statement_ordinal']==ordinal and e['trigger']['kind']=='timer']
        assert len(candidates)==1
        index,event=candidates[0];trigger=event['trigger'];origin=event['origin']
        assert trigger['start']==0 and trigger['period']==0 and trigger.get('enabled',True)
        record=records[count]
        assert record['kind']=='timer' and record['event']==index and record['time']==0
        assert record['origin']==f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"
        assert record.get('observation_time_bounds',[0,0])==[0,0]
        assert 'guard_value' not in record and not record.get('fired_triggers')
        assert timer_before==after and record['before']==timer_before and record['after']==timer_after
        final=timer_after
    for time,state in zip(result['transient']['times'],result['transient']['states'],strict=True):
        if time==0:assert state==final
    check_advisories_before_initial_removal(result,wire,count)
    view=copy.deepcopy(result)
    view['_checked_initial_records']=copy.deepcopy(records[:count])
    view['transient']['events']=view['transient']['events'][count:]
    for advice in view.get('portability_advisories',{}).get('records',[]):advice['event_record']-=count
    return view

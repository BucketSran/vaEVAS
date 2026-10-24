"""Explicit test-only IR33 initial-record migration, events.md batch snapshots.

Callers supply source-derived declaration seeds, joint t0 result and initial
count. Native output is never used to construct these expected values.
"""
import copy
import math


def check_initial_record_batch(result, program, before, after, count):
    wire = program.to_dict() if hasattr(program, 'to_dict') else program
    events = result['transient']['events']
    declared = [state['initial'] for state in wire['states']]
    assert declared == before, ('declaration seeds', declared, before)
    assert len(after) == len(before) == len(result['transient']['state_names'])
    assert all(type(v) in (int,float) and math.isfinite(v) for v in before + after)
    expected = [(i,event) for i,event in enumerate(wire['events'])
                if event['trigger']['kind'] == 'initial_step']
    assert len(expected) == count, ('source initial count', len(expected), count)
    expected.sort(key=lambda pair:(pair[1]['expanded_statement_ordinal'],pair[0]))
    actual = [(i,event) for i,event in enumerate(events) if event['kind']=='initial_step']
    assert len(actual) == count, ('record initial count', len(actual), count)
    assert [i for i,_ in actual] == list(range(count)), 'initial prefix order'
    zero_timers=[(i,event) for i,event in enumerate(wire['events'])
                 if event['trigger']['kind']=='timer'
                 and event['trigger']['start']==0 and event['trigger'].get('enabled',True)]
    expected_zero=expected+zero_timers
    expected_zero.sort(key=lambda pair:(pair[1]['expanded_statement_ordinal'],pair[0]))
    assert [e['event'] for e in events if e['time']==0]==[i for i,_ in expected_zero], 'complete t0 source batch'
    for time,state in zip(result['transient']['times'],result['transient']['states']):
        if time==0:
            assert state==after, ('joint t0 observation',state,after)
    # Every t0 record has the wire source identity and exact zero bounds.
    # Record/advisory agreement alone cannot certify this independent duty.
    zero_records=[record for record in events if record['time']==0]
    for record,(index,event) in zip(zero_records,expected_zero):
        origin=event['origin']
        label=f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"
        assert not origin.get('expansion'), 'these source fixtures have no macro t0 expansion'
        assert type(record['event']) is int and record['event']==index
        assert record['kind']==event['trigger']['kind'] and record['origin']==label
        assert record['time']==0 and record.get('observation_time_bounds',[0,0])==[0,0]
        assert 'guard_value' not in record and not record.get('fired_triggers')
        assert record['before']==before and record['after']==after, ('joint t0 state',record,before,after)
    # Validate original indices before constructing the legacy runtime view.
    # Never silently drop an advisory pointing at an unexpected initial record.
    for advice in result.get('portability_advisories',{}).get('records',[]):
        index=advice['event_record'];assert type(index) is int and count<=index<len(events)
        event=events[index];requested=wire['events'][event['event']]['trigger']
        assert advice['event']==event['event'] and advice['origin']==event['origin']
        kind=advice['code'].removesuffix('_observation_boundary')
        assert kind in ('timer','cross')
        leaves=requested.get('triggers',[requested]);trigger=advice['trigger']
        assert type(trigger) is int and 0<=trigger<len(leaves)
        assert leaves[trigger]['kind'] in (kind,'held_timer' if kind=='timer' else kind)
        assert event['kind']==kind or any(f['trigger']==trigger and f['kind']==kind for f in event.get('fired_triggers',[]))
        expected_bounds=event.get('observation_time_bounds',[event['time'],event['time']])
        if event['kind']=='or':
            expected_bounds=next(f for f in event['fired_triggers'] if f['trigger']==trigger)['time_bounds']
        key='time_bounds_s' if result['portability_advisories']['schema_version']==2 else 'root_time_bounds_s'
        assert advice[key]==expected_bounds
        if advice.get('query_source','output_times')=='output_times':
            assert result['transient']['times'][advice['query_index']]==advice['query_time_s']
    view=copy.deepcopy(result)
    view['_checked_initial_records']=copy.deepcopy(events[:count])
    view['transient']['events']=view['transient']['events'][count:]
    for advice in view.get('portability_advisories',{}).get('records',[]):
        advice['event_record']-=count
    return view

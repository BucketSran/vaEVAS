"""Test-only source-derived t0 occurrence snapshots for one analog process.

Expected tuples are (source statement ordinal, record kind, before, after).
They are supplied by the caller's worked source execution, never DUT output.
"""
import copy
from dataclasses import asdict
import math
from initial_advisory_contract import check_advisories_before_initial_removal


def check_initial_source_sequence(result, program, declaration, expected):
    wire = program if isinstance(program, dict) else asdict(program)
    events = result['transient']['events']
    assert [state['initial'] for state in wire['states']] == declaration
    assert len(result['transient']['state_names']) == len(declaration)
    by_ordinal = {e['expanded_statement_ordinal']: (i,e) for i,e in enumerate(wire['events'])}
    assert len(by_ordinal) == len(wire['events']), 'one process, unique source statements'
    initial = [(i,e) for i,e in enumerate(wire['events']) if e['trigger']['kind']=='initial_step']
    initial_count=len(initial)
    assert initial_count>0 and expected[0][1]=='initial_step'
    assert sum(e['kind']=='initial_step' for e in events)==initial_count
    assert [entry[1] for entry in expected[:initial_count]]==['initial_step']*initial_count
    assert sum(entry[1]=='initial_step' for entry in expected)==initial_count
    zero = [e for e in events if e['time']==0]
    assert len(zero)==len(expected)
    assert events[:len(zero)]==zero, 'complete t0 prefix'
    previous=declaration
    for record,entry in zip(zero,expected,strict=True):
        ordinal,kind,before,after=entry[:4]
        index,event=by_ordinal[ordinal]
        assert event['trigger']['kind'] in (kind, 'held_timer' if kind=='timer' else kind)
        assert before==previous and len(before)==len(after)==len(declaration)
        assert all(type(v) in (int,float) and math.isfinite(v) for v in before+after)
        origin=event['origin']
        assert not origin.get('expansion')
        assert type(record['event']) is int and record['event']==index
        assert record['origin']==f"{origin['source']}:{origin['line']}:{origin['column']} ({origin['instance']})"
        assert record['kind']==kind and record['time']==0
        assert record.get('observation_time_bounds',[0,0])==[0,0]
        assert 'guard_value' not in record
        if kind=='or':
            # Caller supplies leaf ids from the source OR, all exact t0 timers.
            leaves=entry[4]
            assert len(leaves)==len(set(leaves))
            requested=event['trigger']['triggers']
            assert all(requested[i]['kind'] in ('timer','held_timer') for i in leaves)
            fired=record.get('fired_triggers',[])
            assert [f['trigger'] for f in fired]==leaves
            for f in fired:
                assert f['kind']=='timer' and f.get('time_bounds',[0,0])==[0,0]
                assert 'guard_value' not in f
        else:
            assert not record.get('fired_triggers')
        assert record['before']==before and record['after']==after
        previous=after
    for t,state in zip(result['transient']['times'],result['transient']['states'],strict=True):
        if t==0:assert state==previous
    # Validate advisory referents before removing only the checked initial record.
    check_advisories_before_initial_removal(result,wire,initial_count)
    view=copy.deepcopy(result)
    view['_checked_initial_records']=copy.deepcopy(events[:initial_count])
    view['transient']['events']=view['transient']['events'][initial_count:]
    for advice in view.get('portability_advisories',{}).get('records',[]):advice['event_record']-=initial_count
    return view

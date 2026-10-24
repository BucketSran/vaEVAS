"""Read-only advisory referents checked before test-only initial-record removal.

This shared test checker binds notices to source trigger kinds, the committed
certificate, and the actual observation grid. It never calls EVAS validation.
"""
import math


def check_advisories_before_initial_removal(result,wire,count):
    advice=result.get('portability_advisories')
    if advice is None:return
    assert type(advice['schema_version']) is int and advice['schema_version'] in (1,2)
    records=result['transient']['events']
    for item in advice.get('records',[]):
        index=item['event_record']
        assert type(index) is int and count<=index<len(records)
        event=records[index]
        assert type(event['event']) is int and 0<=event['event']<len(wire['events'])
        assert type(item['event']) is int and item['event']==event['event']
        assert item['origin']==event['origin']
        kind={'timer_observation_boundary':'timer','cross_observation_boundary':'cross'}.get(item['code'])
        assert kind is not None, 'known source observation-boundary code'
        requested=wire['events'][event['event']]['trigger']
        leaves=requested.get('triggers',[requested])
        trigger=item['trigger']
        assert type(trigger) is int and 0<=trigger<len(leaves)
        assert leaves[trigger]['kind'] in (('timer','held_timer') if kind=='timer' else ('cross',))
        if event['kind']==kind:
            assert trigger==0
            expected=event.get('observation_time_bounds',[event['time'],event['time']])
        else:
            assert event['kind']=='or'
            fired=[f for f in event.get('fired_triggers',[]) if f['trigger']==trigger and f['kind']==kind]
            assert len(fired)==1
            expected=fired[0].get('time_bounds')
        key='time_bounds_s' if advice['schema_version']==2 else 'root_time_bounds_s'
        bounds=item[key]
        assert isinstance(bounds,list) and len(bounds)==2
        assert all(type(v) in (int,float) and math.isfinite(v) for v in bounds)
        assert bounds==expected and 0<=bounds[0]<=bounds[1]
        source=item.get('query_source','output_times')
        assert source in ('output_times','strobetimes')
        grid=(result['transient']['times'] if source=='output_times'
              else result.get('strobe_evidence',{}).get('times',[]))
        query=item['query_index'];time=item['query_time_s']
        assert type(query) is int and 0<=query<len(grid)
        assert type(time) in (int,float) and math.isfinite(time)
        assert grid[query]==time, 'advisory matches its actual observation query'

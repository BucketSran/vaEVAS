"""Validate the kernel's public response before returning simulation results."""
import math

from .errors import KernelError
from .ir import SCHEMA_VERSION, OrTrigger, Display, Conditional


def _invalid(message):
    raise KernelError(dict(kind='invalid_response', message=message))


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _vector(value, length):
    return isinstance(value, list) and len(value) == length and all(_finite(v) for v in value)


def _index(value):
    return type(value) is int and value >= 0


def _bounds(value):
    return _vector(value, 2) and value[0] <= value[1]


def _observation_evidence(response, solutions, output_times):
    if 'observation_evidence' not in response:
        return  # Old kernels remain supported; missing evidence stays missing.
    evidence=response['observation_evidence']
    if (output_times is None or not isinstance(evidence,dict)
            or type(evidence.get('schema_version')) is not int or evidence['schema_version']!=1
            or evidence.get('nodes')!=response['nodes']):
        _invalid('invalid observation evidence identity')
    controls=evidence.get('effective_controls')
    if (not isinstance(controls,dict)
            or any(not _finite(controls.get(k)) or controls[k]<=0 for k in ('absolute_V','stop_s','max_step_s'))
            or not _finite(controls.get('relative')) or controls['relative']<0
            or type(controls.get('max_step_applied')) is not bool
            or output_times and output_times[-1]>controls['stop_s']):
        _invalid('invalid observation effective controls')
    origins=evidence.get('sample_origins')
    kinds={'stateless_working_point','accepted_controller_frame','certified_causal_frame','implicit_history_evaluation','unknown'}
    if (not isinstance(origins,list) or len(origins)!=len(solutions)
            or any(not isinstance(origin,str) or origin not in kinds for origin in origins)):
        _invalid('invalid observation sample origins')
    if ('initial_settled' in evidence and evidence['initial_settled'] is not None
            and (evidence['initial_settled'] is not True or not output_times or output_times[0]!=0)):
        _invalid('invalid initial settlement evidence')
    bounds=evidence.get('voltage_bounds_V')
    if not isinstance(bounds,list) or len(bounds)!=len(solutions):
        _invalid('invalid observation voltage bounds rows')
    for row,solution in zip(bounds,solutions):
        if row is None:
            continue
        if (not isinstance(row,list) or len(row)!=len(response['nodes'])
                or any(not _bounds(interval) or not interval[0]<=value<=interval[1]
                       for interval,value in zip(row,solution['voltages']))):
            _invalid('invalid observation voltage bounds or representative containment')


def _portability_advisories_v1(response, program, output_times):
    if 'portability_advisories' not in response:
        return
    advice=response['portability_advisories']
    if (output_times is None or not isinstance(advice,dict)
            or type(advice.get('schema_version')) is not int or advice['schema_version']!=1
            or type(advice.get('record_limit')) is not int or advice['record_limit']!=128
            or not _index(advice.get('dropped_records'))
            or type(advice.get('truncated')) is not bool
            or advice['truncated']!=(advice['dropped_records']>0)):
        _invalid('invalid portability advisory identity or budget')
    records=advice.get('records')
    if (not isinstance(records,list) or not 0<len(records)<=advice['record_limit']
            or advice['dropped_records'] and len(records)!=advice['record_limit']):
        _invalid('invalid portability advisory records')
    events=response['transient']['events']
    seen=set()
    for record in records:
        if (not isinstance(record,dict) or record.get('code')!='cross_observation_boundary'
                or record.get('nonblocking') is not True
                or not isinstance(record.get('message'),str) or not record['message']
                or any(not _index(record.get(k)) for k in ('event_record','event','trigger','query_index'))
                or record['event_record']>=len(events) or record['query_index']>=len(output_times)
                or not _finite(record.get('query_time_s'))
                or record['query_time_s']!=output_times[record['query_index']]
                or not _bounds(record.get('root_time_bounds_s'))):
            _invalid('invalid portability advisory record')
        event=events[record['event_record']]
        requested=program.events[event['event']].trigger
        leaves=requested.triggers if isinstance(requested,OrTrigger) else (requested,)
        if record['trigger']>=len(leaves) or leaves[record['trigger']].kind!='cross':
            _invalid('portability advisory trigger does not match a requested cross')
        bounds=record['root_time_bounds_s']
        if event['kind']=='cross' and record['trigger']==0:
            expected=event.get('observation_time_bounds',[event['time'],event['time']])
        else:
            leaf=next((f for f in event.get('fired_triggers',[])
                       if f['trigger']==record['trigger'] and f.get('kind')=='cross'),None)
            expected=leaf.get('time_bounds') if leaf else None
        lo,hi=bounds
        identity=(record['event_record'],record['trigger'],record['query_index'])
        if (record['event']!=event['event'] or record.get('origin')!=event['origin']
                or bounds!=expected or lo<0 or hi>math.nextafter(lo,math.inf)
                or not math.nextafter(lo,-math.inf)<=record['query_time_s']<=math.nextafter(hi,math.inf)
                or identity in seen):
            _invalid('portability advisory does not match a nearby committed cross certificate')
        seen.add(identity)


def _portability_advisories(response, program, output_times):
    advice=response.get('portability_advisories')
    if 'portability_advisories' not in response:
        return
    if isinstance(advice,dict) and type(advice.get('schema_version')) is int and advice['schema_version']==1:
        return _portability_advisories_v1(response,program,output_times)
    if (output_times is None or not isinstance(advice,dict)
            or type(advice.get('schema_version')) is not int or advice['schema_version']!=2
            or type(advice.get('record_limit')) is not int or advice['record_limit']!=128
            or not _index(advice.get('dropped_records'))
            or type(advice.get('truncated')) is not bool
            or advice['truncated']!=(advice['dropped_records']>0)):
        _invalid('invalid portability advisory identity or budget')
    records=advice.get('records');models=advice.get('model_records')
    if (not isinstance(records,list) or not isinstance(models,list)
            or not 0<len(records)+len(models)<=128
            or advice['dropped_records'] and len(records)+len(models)!=128):
        _invalid('invalid portability advisory records')
    grids={'output_times':output_times,
           'strobetimes':response.get('strobe_evidence',{}).get('times',[])}
    events=response['transient']['events'];seen=set()
    for record in records:
        if (not isinstance(record,dict)
                or record.get('code') not in ('cross_observation_boundary','timer_observation_boundary')
                or record.get('query_source') not in ('output_times','strobetimes')
                or record.get('nonblocking') is not True
                or not isinstance(record.get('message'),str) or not record['message']
                or any(not _index(record.get(k)) for k in ('event_record','event','trigger','query_index'))
                or record['event_record']>=len(events)
                or not _finite(record.get('query_time_s')) or not _bounds(record.get('time_bounds_s'))):
            _invalid('invalid portability advisory record')
        times=grids[record['query_source']]
        if record['query_index']>=len(times) or record['query_time_s']!=times[record['query_index']]:
            _invalid('portability advisory does not match its observation grid')
        kind='cross' if record['code']=='cross_observation_boundary' else 'timer'
        event=events[record['event_record']]
        requested=program.events[event['event']].trigger
        leaves=requested.triggers if isinstance(requested,OrTrigger) else (requested,)
        allowed_kinds=('timer','held_timer') if kind=='timer' else ('cross',)
        if record['trigger']>=len(leaves) or leaves[record['trigger']].kind not in allowed_kinds:
            _invalid('portability advisory trigger does not match the request')
        if event['kind']==kind and record['trigger']==0:
            expected=event.get('observation_time_bounds',[event['time'],event['time']])
        else:
            leaf=next((f for f in event.get('fired_triggers',[])
                       if f['trigger']==record['trigger'] and f.get('kind')==kind),None)
            expected=leaf.get('time_bounds') if leaf else None
        lo,hi=record['time_bounds_s']
        identity=(record['event_record'],record['trigger'],record['query_source'],record['query_index'])
        if (record['event']!=event['event'] or record.get('origin')!=event['origin']
                or record['time_bounds_s']!=expected or lo<0
                or kind=='cross' and hi>math.nextafter(lo,math.inf)
                or not math.nextafter(lo,-math.inf)<=record['query_time_s']<=math.nextafter(hi,math.inf)
                or identity in seen):
            _invalid('portability advisory does not match a nearby committed certificate')
        seen.add(identity)
    operators=set()
    for record in models:
        if (not isinstance(record,dict)
                or set(record)!={'code','nonblocking','message','operator','origin'}
                or record.get('code')!='modulo_phase_sensitive' or record.get('nonblocking') is not True
                or not isinstance(record.get('message'),str) or not record['message']
                or not _index(record.get('operator')) or record['operator']>=len(program.operators)):
            _invalid('invalid model portability advisory')
        op=program.operators[record['operator']];origin=op.origin
        expected=f'{origin.source}:{origin.line}:{origin.column} ({origin.instance})'
        if op.kind!='idt_mod' or record['origin']!=expected or record['operator'] in operators:
            _invalid('model portability advisory does not match an idtmod call site')
        operators.add(record['operator'])


def validate_response(response, program, count, output_times=None, *, strobetimes=None):
    if (not isinstance(response, dict) or type(response.get('schema_version')) is not int
            or response['schema_version'] != SCHEMA_VERSION
            or response.get('nodes') != list(program.nodes)
            or not isinstance(response.get('engine'), str)):
        _invalid('kernel response identity mismatch')
    solutions = response.get('solutions')
    if not isinstance(solutions, list) or len(solutions) != count:
        _invalid('kernel solution count mismatch')
    diagnostics = ('max_residual_v', 'max_residual_ratio', 'max_scaled_residual_ratio',
                   'max_voltage_correction_v', 'max_voltage_correction_ratio')
    for row in solutions:
        if (not isinstance(row, dict) or not _vector(row.get('voltages'), len(program.nodes))
                or not {'max_residual_v', 'max_residual_ratio'} <= row.keys()):
            _invalid('kernel solution must contain finite voltages and residuals with the requested shape')
        if any(not _finite(row[key]) or row[key] < 0 for key in diagnostics if key in row):
            _invalid('kernel residual/correction diagnostics must be finite and nonnegative')
    _observation_evidence(response, solutions, output_times)
    strobe = response.get('strobe_evidence')
    if strobetimes and strobe is None:
        _invalid('kernel did not acknowledge forced solve points')
    if strobe is not None:
        points = strobe.get('times') if isinstance(strobe, dict) else None
        kinds = {'stateless_working_point', 'accepted_controller_frame', 'implicit_history_evaluation'}
        if (output_times is None or not isinstance(strobe, dict)
                or type(strobe.get('schema_version')) is not int or strobe['schema_version'] != 1
                or not isinstance(points, list) or not points or len(points) > 100_000
                or not _vector(points, len(points)) or any(t < 0 for t in points)
                or any(a >= b for a,b in zip(points,points[1:]))
                or strobetimes is not None and points != strobetimes
                or not isinstance(strobe.get('sample_origins'), list)
                or len(strobe['sample_origins']) != len(points)
                or any(not isinstance(k,str) or k not in kinds for k in strobe['sample_origins'])
                or not isinstance(strobe.get('voltages_V'), list)
                or len(strobe['voltages_V']) != len(points)
                or any(not _vector(row, len(response['nodes'])) for row in strobe['voltages_V'])):
            _invalid('invalid strobe execution evidence')
    if output_times is None:
        if 'transient' in response:
            _invalid('static response unexpectedly contains a transient trace')
        _portability_advisories(response, program, output_times)
        return response
    trace = response.get('transient')
    if (not isinstance(trace, dict) or not _vector(trace.get('times'), count)
            or trace['times'] != output_times
            or trace.get('state_names') != [f'{s.instance}:{s.name}' for s in program.states]):
        _invalid('transient response identity mismatch')
    states = trace.get('states')
    if not isinstance(states, list) or len(states) != count or any(not _vector(row, len(program.states)) for row in states):
        _invalid('transient state rows must contain finite values with the requested shape')
    if any(not _index(trace.get(key)) for key in ('accepted_steps', 'discarded_trials')):
        _invalid('transient step counters must be nonnegative integers')
    events = trace.get('events')
    if not isinstance(events, list):
        _invalid('transient events must be an array')
    for event in events:
        if (not isinstance(event, dict) or not _finite(event.get('time'))
                or not _index(event.get('event')) or event['event'] >= len(program.events)
                or not isinstance(event.get('origin'), str) or not isinstance(event.get('kind'), str)
                or not _vector(event.get('before'), len(program.states))
                or not _vector(event.get('after'), len(program.states))):
            _invalid('invalid transient event record')
        if ('guard_value' in event and not _finite(event['guard_value'])
                or 'observation_time_bounds' in event and not _bounds(event['observation_time_bounds'])):
            _invalid('invalid transient event bounds or guard value')
        fired = event.get('fired_triggers', [])
        if not isinstance(fired, list):
            _invalid('fired_triggers must be an array')
        trigger = program.events[event['event']].trigger
        leaves = trigger.triggers if isinstance(trigger, OrTrigger) else (trigger,)
        for leaf in fired:
            if (not isinstance(leaf, dict) or not _index(leaf.get('trigger'))
                    or leaf['trigger'] >= len(leaves)
                    or 'time_bounds' in leaf and not _bounds(leaf['time_bounds'])):
                _invalid('invalid fired trigger record')
            kind = leaves[leaf['trigger']].kind
            if kind in ('held_timer',):
                kind = 'timer'
            if (leaf.get('kind', kind) != kind
                    or kind == 'cross' and not _finite(leaf.get('guard_value'))
                    or kind == 'timer' and 'guard_value' in leaf):
                _invalid('fired trigger type or guard value does not match the request')
    def contains_display(body):
        return any(isinstance(statement, Display) or isinstance(statement, Conditional)
                   and (contains_display(statement.then_body) or contains_display(statement.else_body))
                   for statement in body)
    if any(contains_display(event.body) for event in program.events) and 'display_records' not in trace:
        _invalid('transient response omitted requested display records')
    display_records = trace.get('display_records', [])
    if not isinstance(display_records, list):
        _invalid('display records must be an array')
    for record in display_records:
        if (not isinstance(record, dict) or not _finite(record.get('time'))
                or not _index(record.get('event')) or record['event'] >= len(program.events)
                or not isinstance(record.get('origin'), str) or not record['origin']
                or not isinstance(record.get('text'), str)
                or not any(event['event'] == record['event'] and event['time'] == record['time'] for event in events)):
            _invalid('invalid or uncommitted display record')
    _portability_advisories(response, program, output_times)
    return response

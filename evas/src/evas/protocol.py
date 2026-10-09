"""Validate the kernel's public response before returning simulation results."""
import math

from .errors import KernelError
from .ir import SCHEMA_VERSION, OrTrigger


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
            and (type(evidence['initial_settled']) is not bool or not output_times or output_times[0]!=0)):
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


def validate_response(response, program, count, output_times=None):
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
    if output_times is None:
        if 'transient' in response:
            _invalid('static response unexpectedly contains a transient trace')
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
            if kind == 'held_timer':
                kind = 'timer'
            if (leaf.get('kind', kind) != kind
                    or kind == 'cross' and not _finite(leaf.get('guard_value'))
                    or kind == 'timer' and 'guard_value' in leaf):
                _invalid('fired trigger type or guard value does not match the request')
    return response

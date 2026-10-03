"""Validate the kernel's public response before returning simulation results."""
import math

from .errors import KernelError
from .ir import SCHEMA_VERSION


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
        for leaf in fired:
            if (not isinstance(leaf, dict) or not _index(leaf.get('trigger'))
                    or not _finite(leaf.get('guard_value'))
                    or 'time_bounds' in leaf and not _bounds(leaf['time_bounds'])):
                _invalid('invalid fired trigger record')
    return response

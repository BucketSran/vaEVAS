"""Small continuation policy for an existing scope and its sole runtime record.

The caller is a trusted execution/project adapter. Receipt hashes bind content;
they do not authenticate a host or establish native-agent metering coverage.
That adapter owns readiness and purpose classification of the actual command.
Plan text, a purpose string and a successful admission are not project acceptance.
Native accounting uses active-agent seconds. An explicitly authorized bounded
mode charges whole command allocations in command-deadline seconds instead.
Only the referenced runtime file and its lock are written, never scope/queue.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile


DEFAULTS = {'total_agent_s': 14400, 'closeout_fraction': .25,
            'stagnation_s': 1800, 'initial_exploration_s': 3600, 'renewal_s': 1800}
NATIVE_MODE = 'native_agent_active_seconds'
BOUNDED_MODE = 'bounded_command_seconds'
# This reviewed Harness adds three guardian seconds, polls surviving descendants
# at 0.05 seconds, and permits two seconds for owner cleanup/reaping.
HARNESS_GUARD_CONTRACTS = {
    'd0833e133f10d95e4433c993afa5580e2da194dd13514d2cff7997dfb43daf6b': 5.05}


def command_guard_allowance(harness_process_sha256):
    try:
        return HARNESS_GUARD_CONTRACTS[harness_process_sha256]
    except (KeyError, TypeError) as error:
        raise PolicyError('unreviewed Harness guardian lifetime; bounded dispatch denied') from error


def accounting_mode(state):
    return state.get('accounting', {}).get('mode', NATIVE_MODE)


class PolicyError(ValueError):
    """No execution permission was acquired; reconcile or repair the facts."""


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise PolicyError(f'{name} must be a nonempty string')
    return value


def _number(value, name):
    if (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
        raise PolicyError(f'{name} must be a finite nonnegative number')
    return value


def _load(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise PolicyError(f'{path}: expected an object')
    return value


def _binding(scope_path):
    scope_path = Path(scope_path).resolve()
    scope = _load(scope_path)
    continuation = scope['current']['continuation']
    ref = continuation['runtime']
    if ref.get('schema_version') != 1:
        raise PolicyError('unsupported runtime reference schema')
    path = (scope_path.parent / _text(ref.get('path'), 'runtime.path')).resolve()
    queue_name = scope['current'].get('remaining_closure_ledger')
    queue_path = (scope_path.parent / queue_name).resolve() if queue_name else None
    if path in (scope_path, queue_path):
        raise PolicyError('runtime cannot overwrite scope or business queue')
    return scope_path, scope, continuation, path


@contextmanager
def _locked(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def _write(path, state):
    handle, name = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
    try:
        with os.fdopen(handle, 'w') as stream:
            json.dump(state, stream, ensure_ascii=False, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def initialize_runtime(scope_path, *, task_id, authority_ref, config=None,
                       prior_consumed_s=None):
    """Create the pre-bound runtime. None historical usage remains unknown.

    Passing zero explicitly asserts a newly authorized, previously unused window.
    Initialization never rewrites a scope or silently reinitializes existing work.
    """
    _, _, _, path = _binding(scope_path)
    settings = dict(DEFAULTS)
    if config:
        if set(config) - set(DEFAULTS):
            raise PolicyError('unknown policy configuration')
        settings.update(config)
    for key, value in settings.items():
        _number(value, key)
    if settings['closeout_fraction'] > 1 or any(
            settings[key] <= 0 for key in settings if key != 'closeout_fraction'):
        raise PolicyError('invalid policy limits')
    if prior_consumed_s is not None:
        _number(prior_consumed_s, 'prior_consumed_s')
    state = {'schema_version': 1, 'task_id': _text(task_id, 'task_id'),
             'authority_ref': _text(authority_ref, 'authority_ref'),
             'config': settings, 'prior_consumed_s': prior_consumed_s,
             'routes': {}, 'actions': {}, 'attempts': {}, 'events': {}, 'progress': {}}
    with _locked(path):
        if path.exists():
            raise PolicyError('runtime already exists; recover the same task')
        _write(path, state)
    return state


def read_runtime(scope_path):
    """Read an atomic snapshot; absent/corrupt records are never empty budgets."""
    _, _, _, path = _binding(scope_path)
    return _validate_state(_load(path))


def _validate_state(state):
    if type(state.get('schema_version')) is not int or state['schema_version'] != 1:
        raise PolicyError('unsupported runtime schema')
    _text(state.get('task_id'), 'task_id')
    _text(state.get('authority_ref'), 'authority_ref')
    if state.get('prior_consumed_s') is not None:
        _number(state['prior_consumed_s'], 'prior_consumed_s')
    if 'prior_consumed_s' not in state:
        raise PolicyError('missing historical usage is unknown, never zero')
    if accounting_mode(state) not in (NATIVE_MODE, BOUNDED_MODE):
        raise PolicyError('unsupported accounting mode')
    if accounting_mode(state) == BOUNDED_MODE:
        account = state['accounting']
        if (account.get('unit') != 'command_deadline_seconds' or
                account.get('native_history', {}).get('prior_consumed_s') !=
                state['prior_consumed_s'] or _number(account.get('total_command_s'),
                                                     'total_command_s') <= 0):
            raise PolicyError('inconsistent bounded-command accounting')
        _text(account.get('authority_ref'), 'bounded authority_ref')
    settings = state.get('config')
    if not isinstance(settings, dict) or set(settings) != set(DEFAULTS):
        raise PolicyError('invalid policy configuration')
    for key, value in settings.items():
        _number(value, key)
    if settings['closeout_fraction'] > 1 or any(
            settings[key] <= 0 for key in settings if key != 'closeout_fraction'):
        raise PolicyError('invalid policy limits')
    for key in ('routes', 'actions', 'attempts', 'events', 'progress'):
        if not isinstance(state.get(key), dict):
            raise PolicyError(f'{key} must be an object')
    for key in ('reviews', 'review_units', 'goal_checkpoints'):
        if key in state and not isinstance(state[key], dict):
            raise PolicyError(f'{key} must be an object')
    for attempt_id, attempt in state['attempts'].items():
        _number(attempt['allocation_s'], 'allocation_s')
        _number(attempt['consumed_s'], 'consumed_s')
        bounded = accounting_mode(state) == BOUNDED_MODE
        if bounded and (attempt.get('accounting_mode') != BOUNDED_MODE or
                attempt['active_intervals'] or
                attempt['consumed_s'] != (attempt['allocation_s'] if attempt['settled'] else 0) or
                not 0 < _number(attempt.get('command_timeout_s'), 'command_timeout_s') <=
                attempt['allocation_s']):
            raise PolicyError('inconsistent bounded-command execution state')
        if bounded and 'guard_allowance_s' in attempt:
            guard = command_guard_allowance(attempt.get('harness_process_sha256'))
            if (attempt['guard_allowance_s'] != guard or
                    attempt['allocation_s'] + 1e-9 < attempt['command_timeout_s'] + guard):
                raise PolicyError('command allocation does not cover its reviewed guardian boundary')
        if (attempt['route_id'] not in state['routes'] or
                state['actions'][attempt['action_id']]['attempt_id'] != attempt_id or
                attempt['status'] not in ('reserved', 'running', 'completed', 'failed',
                                          'cancelled', 'unknown') or
                type(attempt['settled']) is not bool or
                type(attempt['metering_unknown']) is not bool or
                (not bounded and
                 _seconds(attempt['active_intervals']) != attempt['consumed_s'])):
            raise PolicyError('inconsistent execution state')
    return state


def evaluate(runtime, project_snapshot, *, now=None):
    """Use adapter-owned goal/runnable facts; never infer project acceptance."""
    _validate_state(runtime)
    if any(type(project_snapshot.get(key)) is not bool for key in ('goal_complete', 'runnable')):
        raise PolicyError('project adapter must provide boolean goal_complete and runnable')
    ready_ids = project_snapshot.get('runnable_route_ids', [])
    if not isinstance(ready_ids, list) or any(not isinstance(rid, str) or not rid for rid in ready_ids):
        raise PolicyError('runnable_route_ids must be a list of stable route IDs')
    if project_snapshot.get('paused') is True:
        _text(project_snapshot.get('pause_ref'), 'pause_ref')
        return {'decision': 'paused', 'reason': 'explicit human pause'}
    budget = _budget(runtime)
    routes = {rid: _route_status(runtime, rid) for rid in runtime['routes']}
    common = {'budget': budget, 'routes': routes}
    if budget['consumed_s'] is None:
        return dict(common, decision='unknown', reason='active usage is unknown')
    pending = [a for a in runtime['attempts'].values() if not a['settled']]
    if any(a['status'] in ('reserved', 'unknown') for a in pending):
        return dict(common, decision='unknown', reason='reconcile existing execution first')
    blocked = {rid for rid, item in routes.items() if item['decision'] == 'replan_required'}
    active = {a['route_id'] for a in pending}
    ready = set(project_snapshot.get('runnable_route_ids', [])) - blocked - active
    if not pending and project_snapshot.get('goal_complete') is True:
        return dict(common, decision='complete', reason='project adapter closed acceptance')
    if ready and budget['available_s'] > 0:
        return dict(common, decision='continue', reason='independent authorized route is ready')
    if not pending and budget['available_s'] <= 0:
        return dict(common, decision='budget_exhausted', reason='only closeout or user decision remains')
    if blocked and not ready and len(blocked) == len(routes):
        return dict(common, decision='replan_required', reason='affected routes require replan')
    if pending:
        now_s = _time(now) if isinstance(now, str) else (now or datetime.now(timezone.utc)).timestamp()
        if any(a['status'] == 'running' and _time(a['deadline_utc']) <= now_s for a in pending):
            return dict(common, decision='unknown', reason='execution deadline expired; reconcile first')
        return dict(common, decision='running', reason='observe existing execution')
    if budget['available_s'] <= 0:
        return dict(common, decision='budget_exhausted', reason='only closeout or user decision remains')
    return dict(common, decision='continue' if project_snapshot.get('runnable') is True else 'wait',
                reason='project adapter supplied remaining-work facts')


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def _budget(state):
    attempts = list(state['attempts'].values())
    bounded = accounting_mode(state) == BOUNDED_MODE
    legacy_pending = bounded and any(not a['settled'] and 'guard_allowance_s' not in a
                                     for a in attempts)
    consumed = 0 if bounded else state['prior_consumed_s']
    if consumed is None or legacy_pending or any(a.get('metering_unknown') or a['status'] == 'unknown'
                               for a in attempts):
        known = False
    else:
        known = True
    consumed = (consumed or 0) + _charged_seconds(state, attempts)
    reserved = sum(max(0, a['allocation_s'] - a['consumed_s'])
                   for a in attempts if not a['settled'])
    closeout_attempts = [a for a in attempts if a['purpose'] == 'closeout']
    closeout = _charged_seconds(state, closeout_attempts) + sum(
        max(0, a['allocation_s'] - a['consumed_s'])
        for a in closeout_attempts if not a['settled'])
    total = state['accounting']['total_command_s'] if bounded else state['config']['total_agent_s']
    reserve = max(0, total *
                  state['config']['closeout_fraction'] - closeout)
    return {'mode': accounting_mode(state),
            'unit': 'command_deadline_seconds' if bounded else 'agent_active_seconds',
            'consumed_s': consumed if known else None,
            'known_consumed_s': consumed, 'reserved_s': reserved,
            'pre_guard_fix_settled_attempt_ids': ([aid for aid, a in state['attempts'].items()
                if a['settled'] and 'guard_allowance_s' not in a] if bounded else []),
            'unallocated_closeout_s': reserve,
            'available_s': max(0, total -
                               consumed - reserved - reserve) if known else None}


def _plan(value):
    if not isinstance(value, dict) or set(value) != {'hypothesis', 'experiment', 'criterion'}:
        raise PolicyError('plan requires hypothesis, experiment and criterion')
    for key, entry in value.items():
        _text(entry, key)
    return copy.deepcopy(value)


def plan_digest(plan):
    """Stable plan identity for an independently produced replan receipt."""
    return _digest(_plan(plan))


def _time(value):
    value = _text(value, 'timestamp')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise PolicyError('invalid ISO8601 timestamp') from error
    if result.tzinfo is None:
        raise PolicyError('timestamp requires timezone')
    return result.timestamp()


def _union(intervals):
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _seconds(intervals):
    return sum(end - start for start, end in _union(intervals))


def _actor_seconds(attempts):
    actors = {}
    for attempt in attempts:
        actors.setdefault(attempt['actor'], []).extend(attempt['active_intervals'])
    return sum(_seconds(intervals) for intervals in actors.values())


def _charged_seconds(state, attempts):
    if accounting_mode(state) == BOUNDED_MODE:
        return sum(a['consumed_s'] for a in attempts)
    return _actor_seconds(attempts)


def _activate_bounded(state, request, continuation):
    _authorize(continuation)
    if accounting_mode(state) != NATIVE_MODE or 'accounting' in state:
        raise PolicyError('accounting mode is already fixed; activation cannot reset a budget')
    authority = _text(request.get('authority_ref'), 'bounded authority_ref')
    if any(state[key] for key in ('attempts', 'actions', 'routes', 'progress')) or (
            state['prior_consumed_s'] not in (None, 0)):
        raise PolicyError('nonempty native accounting cannot migrate to a fresh command budget')
    total = _number(request.get('total_command_s'), 'total_command_s')
    if total <= 0 or total > state['config']['total_agent_s']:
        raise PolicyError('bounded total must fit the existing authorized numeric ceiling')
    state['accounting'] = {'mode': BOUNDED_MODE, 'unit': 'command_deadline_seconds',
        'total_command_s': total, 'authority_ref': authority,
        'activated_at_utc': datetime.now(timezone.utc).isoformat(),
        'native_history': {'mode': NATIVE_MODE, 'prior_consumed_s': state['prior_consumed_s'],
                           'authority_ref': state['authority_ref']}}
    return {'decision': 'bounded_execution_activated', 'mode': BOUNDED_MODE,
            'unit': 'command_deadline_seconds'}


def _route_status(state, route_id):
    route = state['routes'][route_id]
    attempts = [a for a in state['attempts'].values() if a['route_id'] == route_id]
    intervals = [row for a in attempts for row in a['active_intervals']]
    bounded = accounting_mode(state) == BOUNDED_MODE
    active = _charged_seconds(state, attempts) if bounded else _seconds(intervals)
    anchor = route['observation_anchor_s']
    if route.get('progress_at_s') is not None:
        if bounded:
            prior = sum(a['consumed_s'] for a in attempts
                        if a.get('observed_at_s', math.inf) <= route['progress_at_s'])
        else:
            before = [[start, min(end, route['progress_at_s'])]
                      for start, end in intervals if start < route['progress_at_s']]
            prior = _seconds(before)
        anchor = max(anchor, prior)
    observed = max(0, active - anchor)
    exploration = _charged_seconds(state, [a for a in attempts if a['purpose'] == 'exploration'])
    reason = route['required_reason']
    if not reason and observed >= state['config']['stagnation_s']:
        reason = 'stagnation'
    if not reason and exploration >= route['exploration_limit_s']:
        reason = 'exploration_exhausted'
    return {'decision': 'replan_required' if reason else 'continue', 'reason': reason,
            'mode': accounting_mode(state),
            'unit': 'command_deadline_seconds' if bounded else 'agent_active_seconds',
            'charged_s': active,
            **({'command_charged_s': active, 'observation_command_s': observed} if bounded else
               {'active_union_s': active, 'observation_active_s': observed}),
            'exploration_consumed_s': exploration,
            'exploration_limit_s': route['exploration_limit_s']}


def _receipt(request, scope_path):
    ref = request.get('receipt')
    if not isinstance(ref, dict):
        raise PolicyError('receipt requires a path and sha256')
    path = scope_path.parent / _text(ref.get('path'), 'receipt.path')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise PolicyError('receipt content hash differs')
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise PolicyError('receipt must contain an object')
    return value, copy.deepcopy(ref)


def _verified_ref(scope_path, ref):
    if not isinstance(ref, dict):
        raise PolicyError('evidence requires a path and sha256')
    raw = (Path(scope_path).parent / _text(ref.get('path'), 'evidence.path')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise PolicyError('evidence content hash differs')
    return raw


def review_key(contract):
    """Identify one declared review scope, including dependencies and evidence."""
    if (not isinstance(contract, dict) or not {'unit_id', 'axis', 'author', 'inputs'} <= set(contract)
            or set(contract) - {'unit_id', 'axis', 'author', 'inputs', 'previous_review'}):
        raise PolicyError('review contract requires unit_id, axis, author and inputs')
    for key in ('unit_id', 'axis', 'author'):
        _text(contract[key], key)
    if contract.get('previous_review') is not None:
        _text(contract['previous_review'], 'previous_review')
    refs = contract['inputs']
    if not isinstance(refs, list) or not refs:
        raise PolicyError('review requires frozen inputs')
    paths = []
    for ref in refs:
        if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
            raise PolicyError('review inputs require path and sha256')
        paths.append(_text(ref['path'], 'review input path'))
        digest = _text(ref['sha256'], 'review input sha256')
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise PolicyError('invalid review input digest')
    if len(paths) != len(set(paths)):
        raise PolicyError('duplicate review input path')
    return _digest(contract)


def validate_review_contract(scope_path, contract):
    review_key(contract)
    for ref in contract['inputs']:
        _verified_ref(scope_path, ref)
    return copy.deepcopy(contract)


def _review_unit(contract):
    return _digest([contract['unit_id'], contract['axis']])


def review_reuse(scope_path, contract):
    """Reuse the latest complete review only while every declared input matches.

    The adapter must declare transitive dependencies and acceptance evidence;
    a path list cannot discover missing dependencies or authenticate its author.
    """
    state = read_runtime(scope_path)
    key = review_key(contract)
    unit = state.get('review_units', {}).get(_review_unit(contract), {})
    row = state.get('reviews', {}).get(unit.get('latest'))
    if not row or row['key'] != key or row['status'] not in ('approved', 'changes_requested'):
        return None
    try:
        validate_review_contract(scope_path, contract)
        _verified_ref(scope_path, row['receipt'])
        _verified_ref(scope_path, row['result'])
        _verified_ref(scope_path, row['execution_receipt'])
        for finding in row['findings']:
            _verified_ref(scope_path, finding['evidence'])
    except (OSError, ValueError, KeyError):
        return None
    return {'decision': 'review_reused', 'status': row['status'], 'review_key': key,
            'findings': copy.deepcopy(row['findings']), 'receipt': row['receipt']}


def _review(state, request, scope_path):
    receipt, ref = _receipt(request, scope_path)
    if receipt.get('kind') != 'review':
        raise PolicyError('review receipt required')
    attempt = _bound_receipt(state, receipt)
    contract = receipt.get('contract')
    key = review_key(contract)
    if key != receipt['input_digest'] or attempt['actor'] == contract['author']:
        raise PolicyError('review must bind frozen inputs and an independent executor')
    if not attempt['settled']:
        raise PolicyError('review requires settled execution; reconcile first')
    # One execution can yield one result. Late files cannot upgrade a timeout or
    # incomplete result; an authorized retry uses a new action and its allocation.
    records = state.setdefault('reviews', {})
    aid = receipt['attempt_id']
    if aid in records:
        return {'decision': 'review_recorded', 'status': records[aid]['status'],
                'review_key': records[aid]['key']}
    execution = json.loads(_verified_ref(scope_path, attempt['receipt']))
    unit = state.setdefault('review_units', {}).setdefault(_review_unit(contract),
                                                          {'open_findings': {}})
    findings = []
    status, error = 'incomplete', None
    if execution.get('execution') == 'timeout':
        status = 'timed_out'
    elif (attempt['status'] == 'completed' and execution.get('execution') == 'ok'
          and execution.get('returncode') == 0 and execution.get('cleanup_confirmed') is True
          and receipt.get('outcome') == 'completed'):
        try:
            if contract.get('previous_review') != unit.get('latest_complete'):
                raise PolicyError('review predecessor changed; recollect the current open findings')
            validate_review_contract(scope_path, contract)
            output = json.loads(_verified_ref(scope_path, receipt.get('result')))
            if output.get('review_key') != key or output.get('reviewer') != attempt['actor']:
                raise PolicyError('review output identity differs')
            findings = output.get('findings')
            if not isinstance(findings, list):
                raise PolicyError('review findings must be explicit')
            seen = set()
            for row in findings:
                fid = _text(row.get('id'), 'finding id')
                if fid in seen or row.get('status') not in ('open', 'resolved'):
                    raise PolicyError('duplicate or invalid finding')
                seen.add(fid)
                _text(row.get('detail'), 'finding detail')
                _verified_ref(scope_path, row.get('evidence'))
                if row['evidence'] not in contract['inputs']:
                    raise PolicyError('finding evidence must belong to the frozen review inputs')
                old = unit['open_findings'].get(fid)
                if row['status'] == 'resolved' and (old is None or
                        old['evidence']['sha256'] == row['evidence']['sha256']):
                    raise PolicyError('resolution requires an open finding and changed evidence')
            if set(unit['open_findings']) - seen:
                raise PolicyError('unresolved findings cannot silently disappear')
            status = 'changes_requested' if any(row['status'] == 'open' for row in findings) else 'approved'
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            status, findings, error = 'incomplete', [], str(exc)
    row = {'key': key, 'contract': copy.deepcopy(contract), 'status': status,
           'receipt': ref, 'execution_receipt': attempt['receipt'],
           'result': receipt.get('result'), 'findings': findings, 'error': error}
    records[aid] = row
    unit['latest'] = aid
    if status in ('approved', 'changes_requested'):
        unit['open_findings'] = {item['id']: item for item in findings if item['status'] == 'open'}
        unit['latest_complete'] = aid
    return {'decision': 'review_recorded', 'status': status, 'review_key': key,
            'error': error}


def _goal_checkpoint(state, request, scope_path):
    """Consume project-owned comparison facts; CI green alone has no goal credit."""
    receipt, ref = _receipt(request, scope_path)
    if receipt.get('kind') != 'goal_checkpoint':
        raise PolicyError('goal checkpoint receipt required')
    attempt = _bound_receipt(state, receipt)
    if not attempt['settled']:
        raise PolicyError('checkpoint requires settled execution')
    _validator(receipt, attempt['actor'])
    _verified_ref(scope_path, receipt.get('evidence'))
    comparison = _text(receipt.get('comparison_id'), 'comparison_id')
    metric = _text(receipt.get('metric'), 'metric')
    facts = receipt.get('assessment', {})
    for field in ('complete', 'comparable', 'checkpoint_due'):
        if type(facts.get(field)) is not bool:
            raise PolicyError('checkpoint must explicitly report completeness, comparability and due state')
    for field in ('before', 'after', 'target', 'expected_min_gain'):
        _number(facts.get(field), field)
    if (facts['target'] <= 0 or facts['before'] > facts['target'] or facts['after'] > facts['target']
            or facts['expected_min_gain'] <= 0):
        raise PolicyError('invalid project goal comparison')
    key = _digest([receipt['route_id'], metric, comparison])
    records = state.setdefault('goal_checkpoints', {})
    if key in records:
        if records[key]['assessment'] != facts or records[key]['evidence'] != receipt['evidence']:
            raise PolicyError('goal comparison identity reused for different facts')
        return {'decision': 'duplicate_goal_checkpoint'}
    route = state['routes'][receipt['route_id']]
    if receipt.get('plan_digest') != route['plan_digest']:
        raise PolicyError('goal checkpoint must bind the current route plan')
    comparable = facts['complete'] and facts['comparable'] and facts['checkpoint_due']
    gain = facts['after'] - facts['before']
    reason = ('goal_regression' if gain < 0 else 'goal_no_growth') if (
        comparable and gain < facts['expected_min_gain'] and facts['after'] < facts['target']) else None
    records[key] = {'receipt': ref, 'assessment': facts, 'evidence': receipt['evidence'],
                    'route_id': receipt['route_id'], 'metric': metric,
                    'net_gain': gain if comparable else None, 'replan_reason': reason}
    if reason:
        route['required_reason'] = route['required_reason'] or reason
    elif comparable and gain >= facts['expected_min_gain']:
        route['progress_at_s'] = max(attempt['observed_at_s'], route.get('progress_at_s') or 0)
    return {'decision': 'replan_required' if reason else 'goal_checkpoint_recorded',
            'net_gain': gain if comparable else None, 'reason': reason}


def _bound_receipt(state, receipt):
    if receipt.get('task_id') != state['task_id']:
        raise PolicyError('receipt task identity differs')
    action = state['actions'].get(receipt.get('action_id'))
    if action is None or any(action[key] != receipt.get(key)
                             for key in ('route_id', 'attempt_id', 'input_digest')):
        raise PolicyError('receipt action, route, attempt or source identity differs')
    return state['attempts'][action['attempt_id']]


def _reconcile(state, request, scope_path):
    receipt, ref = _receipt(request, scope_path)
    if receipt.get('kind') != 'execution':
        raise PolicyError('execution receipt required')
    attempt = _bound_receipt(state, receipt)
    execution = _text(receipt.get('execution_id'), 'execution_id')
    if attempt['execution_id'] not in (None, execution):
        raise PolicyError('execution identity changed; do not redispatch')
    status = receipt.get('status')
    if status not in ('running', 'completed', 'failed', 'cancelled', 'unknown'):
        raise PolicyError('unknown execution status')
    if attempt['settled'] and status != attempt['status']:
        raise PolicyError('settled execution cannot return to a different status')
    if accounting_mode(state) == BOUNDED_MODE:
        return _reconcile_bounded(attempt, receipt, ref, status)
    if attempt['settled'] and receipt.get('metering_complete') is not True:
        raise PolicyError('settled metering cannot be downgraded by a late notification')
    observed = _time(receipt.get('observed_at_utc'))
    if observed < attempt.get('observed_at_s', 0):
        raise PolicyError('stale execution observation')
    if status == 'running':
        deadline = _time(receipt.get('deadline_utc'))
        if deadline <= observed:
            raise PolicyError('running execution has no future deadline')
        attempt['deadline_utc'] = receipt['deadline_utc']
    rows = receipt.get('active_intervals')
    if not isinstance(rows, list):
        raise PolicyError('active_intervals must be a list; absent metering is unknown')
    intervals = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 2:
            raise PolicyError('active interval requires start and end')
        start, end = map(_time, row)
        if end < start or end > observed:
            raise PolicyError('invalid or future active interval')
        intervals.append([start, end])
    combined = _union(attempt['active_intervals'] + intervals)
    consumed = _seconds(combined)
    if attempt['settled'] and consumed != attempt['consumed_s']:
        raise PolicyError('settled receipt cannot add new consumption')
    attempt.update(execution_id=execution, status=status, observed_at_s=observed,
                   active_intervals=combined, consumed_s=consumed,
                   metering_unknown=receipt.get('metering_complete') is not True,
                   receipt=ref)
    attempt['settled'] = (status in ('completed', 'failed', 'cancelled') and
                          not attempt['metering_unknown'])
    return {'decision': 'collected' if status in ('completed', 'failed', 'cancelled')
            else 'observe' if status == 'running' else 'unknown',
            'attempt_id': receipt['attempt_id'], 'settled': attempt['settled']}


def _reconcile_bounded(attempt, receipt, ref, status):
    if (receipt.get('accounting_mode') != BOUNDED_MODE or
            receipt.get('budget_unit') != 'command_deadline_seconds' or
            any(receipt.get(key) != attempt[key] for key in
                ('intent_digest', 'command_timeout_s')) or
            receipt.get('deadline_utc') != attempt['command_deadline_utc'] or
            receipt.get('active_intervals') != [] or
            receipt.get('metering_complete') is not False or
            receipt.get('agent_meter_receipt') is not None or
            receipt.get('meter_source_kind') is not None):
        raise PolicyError('bounded receipt must bind its command deadline without native metering')
    if 'guard_allowance_s' in attempt:
        if any(receipt.get(key) != attempt[key] for key in
               ('guard_allowance_s', 'harness_process_sha256')):
            raise PolicyError('bounded receipt changed its reviewed guardian boundary')
    elif not attempt['settled']:
        attempt.update(status='unknown', receipt=ref)
        return {'decision': 'unknown', 'attempt_id': receipt['attempt_id'], 'settled': False}
    observed = _time(receipt.get('observed_at_utc'))
    if observed < attempt.get('observed_at_s', 0):
        raise PolicyError('stale execution observation')
    terminal = status in ('completed', 'failed', 'cancelled')
    if terminal and receipt.get('cleanup_confirmed') is not True:
        raise PolicyError('completed command requires confirmed Harness cleanup')
    if status == 'running' and _time(receipt['deadline_utc']) <= observed:
        raise PolicyError('running execution has no future deadline')
    attempt.update(status=status, observed_at_s=observed, receipt=ref,
                   deadline_utc=receipt['deadline_utc'], metering_unknown=False,
                   consumed_s=attempt['allocation_s'] if terminal else 0, settled=terminal)
    return {'decision': 'collected' if terminal else 'observe' if status == 'running' else 'unknown',
            'attempt_id': receipt['attempt_id'], 'settled': terminal}


def _validator(receipt, author, *, independent=False):
    validator = receipt.get('validator', {})
    kind = validator.get('kind')
    if (validator.get('accepted') is not True or validator.get('author') != author or
            kind not in ('project_check', 'independent_review')):
        raise PolicyError('applicable project validation or independent review required')
    identity = _text(validator.get('identity'), 'validator.identity')
    if (independent or kind == 'independent_review') and (
            kind != 'independent_review' or identity == author):
        raise PolicyError('an author cannot independently approve their own evidence')


def _progress(state, request, scope_path):
    receipt, ref = _receipt(request, scope_path)
    if receipt.get('kind') != 'progress':
        raise PolicyError('progress receipt required')
    attempt = _bound_receipt(state, receipt)
    if attempt['status'] not in ('completed', 'failed', 'cancelled'):
        raise PolicyError('progress requires an observed execution result')
    _validator(receipt, attempt['actor'])
    if receipt.get('category') not in ('acceptance', 'exploration', 'verification'):
        raise PolicyError('unknown progress category')
    _text(receipt.get('changes_decision'), 'changes_decision')
    _text(receipt.get('progress_id'), 'progress_id')
    at = _time(receipt.get('at_utc'))
    if at > attempt['observed_at_s']:
        raise PolicyError('progress cannot postdate the observed evidence')
    # Evidence can be arbitrary bytes; content/identity is checked, not its meaning.
    evidence = receipt.get('evidence', {})
    raw = (scope_path.parent / _text(evidence.get('path'), 'evidence.path')).read_bytes()
    if hashlib.sha256(raw).hexdigest() != evidence.get('sha256'):
        raise PolicyError('progress evidence hash differs')
    key = _progress_identity(receipt)
    if key in state['progress']:
        return {'decision': 'duplicate_progress'}
    # Earlier records included category in their key. Recover evidence identity
    # from their bound receipt, rather than treating those records as new work.
    for previous in state['progress'].values():
        identity = previous.get('evidence_identity')
        if identity is None:
            old_receipt, _ = _receipt({'receipt': previous['receipt']}, scope_path)
            identity = _progress_identity(old_receipt)
        if identity == key:
            return {'decision': 'duplicate_progress'}
    if any(row['progress_id'] == receipt['progress_id'] for row in state['progress'].values()):
        raise PolicyError('progress identity reused for different evidence')
    state['progress'][key] = {'receipt': ref, 'progress_id': receipt['progress_id'],
                              'evidence_identity': key, 'category': receipt['category']}
    route = state['routes'][receipt['route_id']]
    # Checks establish correctness. Only a project goal comparison or new
    # discriminating exploration evidence may advance the observation anchor.
    if receipt['category'] == 'exploration':
        route['progress_at_s'] = max(at, route.get('progress_at_s') or at)
    if receipt.get('premise_refuted') is True:
        route['required_reason'] = 'premise_refuted'
    return {'decision': 'progress_recorded'}


def _progress_identity(receipt):
    return _digest([receipt['route_id'], receipt['input_digest'],
                    receipt['evidence']['sha256']])


def _replan(state, request, scope_path, continuation):
    _authorize(continuation)
    route_id = _text(request.get('route_id'), 'route_id')
    route = state['routes'][route_id]
    status = _route_status(state, route_id)
    if not status['reason']:
        raise PolicyError('route has no replan trigger')
    if any(a['route_id'] == route_id and not a['settled'] for a in state['attempts'].values()):
        raise PolicyError('reconcile existing attempts before replacing their plan')
    if _budget(state)['available_s'] is None:
        raise PolicyError('unknown usage prevents reactivation')
    plan = _plan(request.get('plan'))
    receipt, ref = _receipt(request, scope_path)
    if (receipt.get('kind') != 'replan' or receipt.get('task_id') != state['task_id'] or
            receipt.get('route_id') != route_id or
            receipt.get('previous_plan_digest') != route['plan_digest'] or
            receipt.get('new_plan_digest') != plan_digest(plan) or
            receipt.get('trigger') != status['reason']):
        raise PolicyError('replan review does not bind the affected plan and trigger')
    _bound_receipt(state, receipt)
    _validator(receipt, _text(request.get('author'), 'author'), independent=True)
    _text(receipt.get('addresses_trigger'), 'addresses_trigger')
    _text(receipt.get('next_check'), 'next_check')
    if status['reason'] != 'exploration_exhausted' and all(
            plan[key] == route['plan'][key] for key in ('experiment', 'criterion')):
        raise PolicyError('renaming a hypothesis does not change the discriminating experiment')
    renewal = _number(request.get('renewal_s', 0), 'renewal_s')
    if renewal:
        if (route['renewals_used'] or renewal > state['config']['renewal_s'] or
                renewal > _budget(state)['available_s']):
            raise PolicyError('one regular renewal within the existing total is allowed')
        route['exploration_limit_s'] += renewal
        route['renewals_used'] += 1
    if (status['reason'] == 'exploration_exhausted' and not renewal):
        raise PolicyError('exhausted route requires authorized renewal or closeout')
    route.update(plan=plan, plan_digest=plan_digest(plan), required_reason=None,
                 observation_anchor_s=status['charged_s'], replan_receipt=ref)
    return {'decision': 'replanned', 'route_id': route_id}


def _authorize(continuation):
    if continuation.get('status', 'active') not in ('active', 'waiting', 'paused'):
        raise PolicyError('unknown continuation authority state')
    if continuation.get('status') == 'paused':
        raise PolicyError('explicit human pause prevents new execution')
    deadline = continuation.get('deadline_utc')
    if deadline is not None and datetime.now(timezone.utc).timestamp() >= _time(deadline):
        raise PolicyError('current authorized execution window ended')


def _admit(state, request, scope, continuation, scope_path):
    _authorize(continuation)
    if request.get('ready') is not True:
        raise PolicyError('project adapter has not confirmed dependencies ready')
    action_id = _text(request.get('action_id'), 'action_id')
    if action_id in state['actions']:
        return {'decision': 'reconcile_required', 'action_id': action_id,
                'attempt_id': state['actions'][action_id]['attempt_id']}
    attempt_id = _text(request.get('attempt_id'), 'attempt_id')
    if attempt_id in state['attempts']:
        raise PolicyError('attempt identity already belongs to another action')
    route_id = _text(request.get('route_id'), 'route_id')
    actor = _text(request.get('actor'), 'actor')
    source = _text(request.get('input_digest'), 'input_digest')
    plan = _plan(request.get('plan'))
    # Scope/queue adapter: validate references only, never project verdicts.
    rows = _load(scope_path.parent / scope['current']['remaining_closure_ledger'])['cases']
    known_ids = {row['case_id'] for row in rows}
    case_ids = request.get('case_ids')
    if (not isinstance(case_ids, list) or not case_ids or
            any(not isinstance(cid, str) for cid in case_ids) or
            len(set(case_ids)) != len(case_ids) or not set(case_ids) <= known_ids):
        raise PolicyError('action must reference IDs from the existing project queue')
    allocation = _number(request.get('allocation_s'), 'allocation_s')
    purpose = request.get('purpose', 'exploration')
    if allocation <= 0 or purpose not in ('exploration', 'work', 'closeout'):
        raise PolicyError('positive allocation and known purpose required')
    command = {}
    if accounting_mode(state) == BOUNDED_MODE:
        timeout = _number(request.get('command_timeout_s'), 'command_timeout_s')
        harness_sha = request.get('harness_process_sha256')
        guard = command_guard_allowance(harness_sha)
        deadline = request.get('command_deadline_utc')
        remaining = _time(deadline) - datetime.now(timezone.utc).timestamp()
        digest = _text(request.get('intent_digest'), 'intent_digest')
        if (timeout <= 0 or allocation + 1e-9 < timeout + guard or
                request.get('guard_allowance_s') != guard or
                not 0 < remaining <= timeout + .1 or len(digest) != 64 or
                any(char not in '0123456789abcdef' for char in digest)):
            raise PolicyError('command allocation must cover timeout, guardian and cleanup allowance')
        command = {'accounting_mode': BOUNDED_MODE, 'command_timeout_s': timeout,
                   'command_deadline_utc': deadline, 'intent_digest': digest,
                   'guard_allowance_s': guard, 'harness_process_sha256': harness_sha}
    budget = _budget(state)
    available = budget['available_s']
    if available is None:
        raise PolicyError('active usage is unknown; no fresh allocation')
    if purpose == 'closeout':
        available += budget['unallocated_closeout_s']
    if allocation > available:
        raise PolicyError('allocation would consume protected or unavailable budget')
    # Existing case references provide stable work ownership. Descriptions,
    # input revisions and actor/route names cannot create another exploration
    # allowance. A different experiment for that work needs the same route's
    # reviewed replan. Actions only reference the original queue, not a copy.
    for action in state['actions'].values():
        if not set(case_ids).intersection(action['case_ids']):
            continue
        old = state['attempts'][action['attempt_id']]
        if old['purpose'] == 'closeout':
            continue
        if purpose != 'closeout' and action['route_id'] != route_id:
            raise PolicyError('reuse the stable route for existing case work; reviewed replan required')
        if purpose == 'closeout' and all(
                plan[key] == old['plan'][key] for key in ('experiment', 'criterion')):
            raise PolicyError('existing exploration cannot acquire closeout budget by relabeling')
    route = state['routes'].get(route_id)
    if route is None:
        route = {'plan': plan, 'plan_digest': _digest(plan), 'renewals_used': 0,
                 'exploration_limit_s': state['config']['initial_exploration_s'],
                 'observation_anchor_s': 0, 'required_reason': None}
        state['routes'][route_id] = route
    elif route['plan_digest'] != _digest(plan):
        raise PolicyError('plan changes require a reviewed replan on the same route')
    if _route_status(state, route_id)['decision'] == 'replan_required':
        raise PolicyError('route requires replan before another action')
    exploration_attempts = [a for a in state['attempts'].values()
                            if a['route_id'] == route_id and a['purpose'] == 'exploration']
    allocated = _charged_seconds(state, exploration_attempts) + sum(
        max(0, a['allocation_s'] - a['consumed_s'])
        for a in exploration_attempts if not a['settled'])
    if purpose == 'exploration' and allocated + allocation > route['exploration_limit_s']:
        raise PolicyError('route exploration allocation exhausted')
    state['actions'][action_id] = {'route_id': route_id, 'attempt_id': attempt_id,
                                  'case_ids': case_ids, 'input_digest': source}
    state['attempts'][attempt_id] = {
        'route_id': route_id, 'action_id': action_id, 'actor': actor,
        'purpose': purpose, 'plan': plan, 'input_digest': source,
        'allocation_s': allocation, 'consumed_s': 0,
        'status': 'reserved', 'settled': False, 'metering_unknown': False,
        'execution_id': _text(request.get('execution_id', attempt_id), 'execution_id'),
        'execution_ref': (None if request.get('execution_ref') is None else
                          _text(request['execution_ref'], 'execution_ref')),
        'active_intervals': [], **command}
    return {'decision': 'admitted', 'action_id': action_id, 'attempt_id': attempt_id,
            'execution_id': state['attempts'][attempt_id]['execution_id']}


def update_runtime(scope_path, request):
    """Atomically apply an adapter request. Repeated event IDs are idempotent."""
    scope_path, scope, continuation, path = _binding(scope_path)
    with _locked(path):
        state = _validate_state(_load(path))
        if request.get('task_id') != state['task_id']:
            raise PolicyError('request task identity differs from runtime')
        event_id = _text(request.get('event_id'), 'event_id')
        digest = _digest(request)
        previous = state['events'].get(event_id)
        if previous:
            if previous['request_digest'] != digest:
                raise PolicyError('event ID reused for a different request')
            return dict(previous['result'], replayed=True)
        if request.get('operation') == 'activate_bounded_execution':
            result = _activate_bounded(state, request, continuation)
        elif request.get('operation') == 'admit':
            result = _admit(state, request, scope, continuation, scope_path)
        elif request.get('operation') == 'reconcile':
            result = _reconcile(state, request, scope_path)
        elif request.get('operation') == 'progress':
            result = _progress(state, request, scope_path)
        elif request.get('operation') == 'review':
            result = _review(state, request, scope_path)
        elif request.get('operation') == 'goal_checkpoint':
            result = _goal_checkpoint(state, request, scope_path)
        elif request.get('operation') == 'replan':
            result = _replan(state, request, scope_path, continuation)
        else:
            raise PolicyError('unsupported operation')
        state['events'][event_id] = {'request_digest': digest, 'result': result}
        _write(path, state)
        return dict(result, replayed=False)

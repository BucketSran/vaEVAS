"""Bind one existing action to the maintained Harness process runner.

The runtime referenced by scope is the only budget/attempt record. Harness owns
process creation, deadlines, logs and cleanup. Native mode needs a trusted agent
meter. Explicit bounded mode charges whole command allocations, never agent time.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import threading
import time

import task_continuation_policy as policy


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ref(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def _context(admission):
    return {key: admission[key] for key in (
        'task_id', 'route_id', 'action_id', 'attempt_id', 'execution_id', 'actor',
        'input_digest')}


def _intent_digest(intent):
    return hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _meter_report(ref, context, controlled_test):
    path = Path(ref['path'])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref.get('sha256'):
        raise ValueError('agent meter receipt hash differs')
    report = json.loads(raw)
    if report.get('kind') != 'agent_active_meter' or report.get('binding') != context:
        raise ValueError('agent meter receipt does not bind this execution')
    source = report.get('source_kind')
    if source == 'controlled_test':
        if not controlled_test:
            raise ValueError('controlled test metering requires explicit test mode')
    elif source != 'native_agent_active':
        raise ValueError('a trusted native active-agent meter is required')
    if not isinstance(report.get('active_intervals'), list):
        raise ValueError('meter must report active intervals explicitly')
    return report


def _harness(root=None):
    root = Path(root).resolve() if root else (
        Path(__file__).resolve().parents[1].parent.parent / 'circuits/circuit-harness')
    if not (root / 'circuit_harness/execution/runtime/process.py').is_file():
        raise ImportError('maintained external Harness checkout is unavailable')
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    process = importlib.import_module('circuit_harness.execution.runtime.process')
    journal = importlib.import_module('circuit_harness.execution.runtime.journal')
    for module in (process, journal):
        if not Path(module.__file__).resolve().is_relative_to(root):
            raise ValueError('a different Harness installation is already imported')
    return process, journal


@contextmanager
def _owner(directory, lock_name='.continuation-owner.lock'):
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / lock_name).open('a') as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)


def _collect(scope_path, path, receipt, *, started, controlled_test):
    if receipt.get('controlled_test') is not (controlled_test is True):
        raise ValueError('receipt test mode differs from the authorized execution intent')
    meter_ref = receipt.get('agent_meter_receipt')
    if meter_ref is not None:
        meter = _meter_report(meter_ref, _context(receipt), controlled_test=controlled_test)
        if (receipt.get('active_intervals') != meter['active_intervals'] or
                receipt.get('meter_source_kind') != meter['source_kind'] or
                receipt.get('metering_complete') != (meter.get('metering_complete') is True)):
            raise ValueError('execution metering differs from the bound agent meter receipt')
    elif receipt.get('metering_complete') is True or receipt.get('active_intervals'):
        raise ValueError('complete metering requires a bound agent meter receipt')
    ref = _ref(path)
    result = policy.update_runtime(scope_path, {
        'event_id': 'execution:' + receipt['execution_id'] + ':' + ref['sha256'],
        'operation': 'reconcile', 'task_id': receipt['task_id'], 'receipt': ref})
    return {**result, 'started': started, 'execution': receipt,
            'native_agent_metering': (receipt.get('meter_source_kind') == 'native_agent_active'
                                     and receipt.get('metering_complete') is True),
            'receipt': ref}


def _receipt(context, intent, result, meter=None, meter_ref=None):
    receipt = {'kind': 'execution', **context,
            'controlled_test': intent['controlled_test'],
            'status': ('unknown' if result['cleanup_confirmed'] is not True
                       else 'completed' if result['execution'] == 'ok' and result['returncode'] == 0
                       else 'cancelled' if result['execution'] == 'cancelled' else 'failed'),
            'observed_at_utc': _now(), 'deadline_utc': intent['deadline_utc'],
            'active_intervals': meter['active_intervals'] if meter else [],
            'metering_complete': meter.get('metering_complete') is True if meter else False,
            'meter_source_kind': meter.get('source_kind') if meter else None,
            'agent_meter_receipt': meter_ref,
            'process_wall_s': result['elapsed_s'],
            **{key: result[key] for key in ('execution', 'returncode', 'cleanup_confirmed',
                                           'stdout', 'stderr')}}
    if intent.get('accounting_mode') == policy.BOUNDED_MODE:
        receipt.update(accounting_mode=policy.BOUNDED_MODE,
                       budget_unit='command_deadline_seconds',
                       command_timeout_s=intent['timeout_s'], intent_digest=_intent_digest(intent))
        if 'guard_allowance_s' in intent:
            receipt.update(guard_allowance_s=intent['guard_allowance_s'],
                           harness_process_sha256=intent['harness_process_sha256'])
    return receipt


def execute_action(scope_path, admission, argv, *, directory, cwd=None, timeout_s=90,
                   agent_meter=None, controlled_test=False, harness_root=None,
                   cancel=None, max_output_bytes=16 * 1024 * 1024):
    """Dispatch once through Harness.

    A trusted meter supplies preflight(context) and collect(context) receipt refs.
    A ref contains path and sha256. Its JSON binds the execution and reports
    active_intervals, metering_complete and source_kind. This module supplies no
    native provider and never derives agent intervals from its process timer.
    """
    admission = dict(admission)
    admission.setdefault('execution_id', admission['attempt_id'])
    directory = Path(directory).resolve()
    admission['execution_ref'] = str(directory)
    runtime = policy.read_runtime(scope_path)
    mode = policy.accounting_mode(runtime)
    bounded = mode == policy.BOUNDED_MODE
    if bounded and (controlled_test or agent_meter is not None):
        raise ValueError('bounded command mode does not accept controlled-test or native agent meters')
    if admission.get('task_id') != runtime['task_id']:
        raise ValueError('admission task identity differs from the runtime')
    if (type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or
            timeout_s <= 0):
        raise ValueError('command deadline must be a finite positive number')
    if not bounded and timeout_s > 90:
        raise ValueError('one narrow command must have a deadline within 90 seconds')
    existing = runtime['actions'].get(admission['action_id'])
    if existing:
        attempt = runtime['attempts'][existing['attempt_id']]
        expected = {**attempt, 'task_id': runtime['task_id'],
                    'attempt_id': existing['attempt_id']}
        if (_context(admission) != _context(expected) or
                admission.get('case_ids') != existing['case_ids'] or any(
                    admission.get(key, 'exploration' if key == 'purpose' else None) != attempt[key]
                    for key in ('allocation_s', 'purpose', 'plan'))):
            raise ValueError('existing action cannot be reused with a different admission binding')
        intent_path = directory / 'execution.intent.json'
        if intent_path.exists():
            intent = json.loads(intent_path.read_text())
            if (intent['argv'] != argv or
                    intent['cwd'] != (str(Path(cwd).resolve()) if cwd else str(directory)) or
                    intent['timeout_s'] != timeout_s or
                    intent['max_output_bytes'] != max_output_bytes):
                raise ValueError('existing action cannot be reused for a different command')
        return recover_action(scope_path, existing['attempt_id'], directory=directory,
                              harness_root=harness_root, controlled_test=controlled_test)
    if agent_meter is None and not bounded:
        return {'decision': 'metering_unavailable', 'started': False,
                'reason': 'native active-agent metering provider is unavailable',
                'native_agent_metering': False}
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError('argv must be a nonempty list of strings')
    context = _context(admission)
    preflight_ref = None
    if not bounded:
        preflight_ref = agent_meter.preflight(context)
        preflight = _meter_report(preflight_ref, context, controlled_test)
        if (preflight.get('available') is not True or
                preflight.get('metering_complete') is not True):
            return {'decision': 'metering_unavailable', 'started': False,
                    'reason': 'agent meter reports no coverage', 'native_agent_metering': False}
    try:
        process, journal = _harness(harness_root)
        harness_sha = hashlib.sha256(Path(process.__file__).read_bytes()).hexdigest()
        guard = None
        if bounded:
            if getattr(process, '_SOURCE_SHA256', None) != harness_sha:
                raise ValueError('loaded Harness code differs from its current source identity')
            guard = policy.command_guard_allowance(harness_sha)
    except (ImportError, ValueError) as error:
        return {'decision': 'execution_unavailable', 'started': False,
                'reason': str(error), 'native_agent_metering': False}
    with _owner(directory) as owned:
        if not owned:
            return {'decision': 'execution_busy', 'started': False}
        intent_path = directory / 'execution.intent.json'
        if intent_path.exists():
            raise ValueError('output directory already belongs to an execution')
        deadline_monotonic = time.monotonic() + timeout_s
        intent = {'binding': context, 'argv': argv,
                  'cwd': str(Path(cwd).resolve()) if cwd else str(directory),
                  'controlled_test': controlled_test is True, 'timeout_s': timeout_s,
                  'accounting_mode': mode, 'allocation_s': admission['allocation_s'],
                  'deadline_monotonic': deadline_monotonic,
                  'max_output_bytes': max_output_bytes,
                  'deadline_utc': (datetime.now(timezone.utc) +
                                   timedelta(seconds=timeout_s)).isoformat(),
                  'meter_preflight': preflight_ref,
                  'harness_process_sha256': harness_sha}
        if bounded:
            intent['guard_allowance_s'] = guard
            admission.update(command_timeout_s=timeout_s,
                             command_deadline_utc=intent['deadline_utc'],
                             guard_allowance_s=guard, harness_process_sha256=harness_sha,
                             intent_digest=_intent_digest(intent))
        decision = policy.update_runtime(scope_path, admission)
        if decision['decision'] != 'admitted' or decision.get('replayed'):
            return {**decision, 'started': False}
        journal.atomic_json(intent_path, intent)
        wrapped = [sys.executable, '-B', '-c',
                   'import os,sys;os.chdir(sys.argv[1]);'
                   'os.execvpe(sys.argv[2],sys.argv[2:],os.environ)', intent['cwd'], *argv]
        result = process.run_process(
            wrapped, directory=directory, stage='check', deadline=deadline_monotonic,
            cancel=cancel or threading.Event(),
            journal=journal.Journal(directory, call_id=context['execution_id']),
            max_output_bytes=max_output_bytes)
        meter_ref, meter = None, None
        if not bounded:
            try:
                meter_ref = agent_meter.collect(context)
                meter = _meter_report(meter_ref, context, controlled_test)
                if meter.get('available') is not True:
                    raise ValueError('agent meter has lost execution coverage')
            except Exception as error:
                # The command already finished. Keep its durable result and reservation.
                result['meter_error'] = type(error).__name__ + ': ' + str(error)
                meter_ref, meter = None, None
        receipt = _receipt(context, intent, result, meter, meter_ref)
        if result.get('meter_error'):
            receipt['meter_error'] = result['meter_error']
        path = directory / 'execution.receipt.json'
        journal.atomic_json(path, receipt)
        return _collect(scope_path, path, receipt, started=True, controlled_test=controlled_test)


def execute_review(scope_path, admission, argv, *, review_contract, directory, result_path,
                   cwd=None, timeout_s=90, agent_meter=None, controlled_test=False,
                   harness_root=None, cancel=None, max_output_bytes=16 * 1024 * 1024):
    """Bind a frozen review to execute_action and the same runtime registry.

    The caller supplies a reviewer command and its JSON output path. Harness
    controls that local process group; this does not cancel remote inference.
    Results are recorded once, so late output cannot upgrade a settled review.
    """
    admission = dict(admission)
    admission.setdefault('execution_id', admission['attempt_id'])
    review_contract = copy.deepcopy(review_contract)
    key = policy.review_key(review_contract)
    if admission['input_digest'] != key or admission['actor'] == review_contract['author']:
        raise ValueError('review requires its frozen input identity and an independent actor')
    if not isinstance(argv, list) or not argv or any(not isinstance(a, str) for a in argv):
        raise ValueError('argv must be a nonempty list of strings')
    argv = list(argv)
    directory, result_path = Path(directory).resolve(), Path(result_path).resolve()
    runtime = policy.read_runtime(scope_path)
    if admission['task_id'] != runtime['task_id']:
        raise ValueError('admission task identity differs from the runtime')
    existing = runtime['actions'].get(admission['action_id'])
    intent = {'binding': _context(admission), 'contract': review_contract, 'argv': argv,
              'result_path': str(result_path), 'timeout_s': timeout_s,
              'cwd': str(Path(cwd).resolve()) if cwd else str(directory),
              'controlled_test': controlled_test is True, 'max_output_bytes': max_output_bytes}
    with _owner(directory, '.continuation-review.lock') as owned:
        if not owned:
            return {'decision': 'execution_busy', 'started': False}
        intent_path = directory / 'review.intent.json'
        if intent_path.exists():
            if json.loads(intent_path.read_text()) != intent:
                raise ValueError('existing action cannot change its review contract or output command')
        elif existing:
            raise ValueError('existing action has no bound review intent')
        if not existing:
            policy.validate_review_contract(scope_path, review_contract)
            reused = policy.review_reuse(scope_path, review_contract)
            if reused is not None:
                return {**reused, 'started': False}
            if result_path.exists():
                raise ValueError('review result path already exists before dispatch')
        try:
            _, journal = _harness(harness_root)
        except (ImportError, ValueError) as error:
            return {'decision': 'execution_unavailable', 'started': False,
                    'reason': str(error), 'native_agent_metering': False}
        if not intent_path.exists():
            journal.atomic_json(intent_path, intent)
        # Existing actions always recover their execution before any cache lookup
        # or current-input check. They can still need cleanup or reconciliation.
        execution = execute_action(scope_path, admission, argv, directory=directory,
            cwd=cwd, timeout_s=timeout_s, agent_meter=agent_meter,
            controlled_test=controlled_test, harness_root=harness_root,
            cancel=cancel, max_output_bytes=max_output_bytes)
        if 'execution' not in execution or execution.get('settled') is not True:
            return execution
        receipt_path = directory / 'review.receipt.json'
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get('contract') != review_contract or any(
                    receipt.get(name) != admission[name] for name in
                    ('task_id', 'action_id', 'attempt_id', 'route_id', 'input_digest'))):
                raise ValueError('review receipt differs from its bound execution intent')
            if receipt.get('result') is not None and receipt['result'].get('path') != str(result_path):
                raise ValueError('review receipt output differs from its bound execution intent')
        else:
            observed = execution['execution']
            outcome = ('timed_out' if observed.get('execution') == 'timeout' else
                       'completed' if observed.get('status') == 'completed'
                       and observed.get('execution') == 'ok' and observed.get('returncode') == 0
                       and observed.get('cleanup_confirmed') is True else 'incomplete')
            try:
                policy.validate_review_contract(scope_path, review_contract)
            except (OSError, ValueError):
                outcome = 'incomplete'
            try:
                result_ref = _ref(result_path)
            except OSError:
                result_ref = None
            receipt = {'kind': 'review', **{name: admission[name] for name in
                ('task_id', 'action_id', 'attempt_id', 'route_id', 'input_digest')},
                'contract': review_contract, 'outcome': outcome, 'result': result_ref}
            journal.atomic_json(receipt_path, receipt)
        ref = _ref(receipt_path)
        recorded = policy.update_runtime(scope_path, {
            'event_id': 'review:' + admission['attempt_id'] + ':' + ref['sha256'],
            'operation': 'review', 'task_id': admission['task_id'], 'receipt': ref})
        # The durable row records what was reviewed then. Recovery still needs
        # current applicability before returning an approval to the caller.
        if recorded['status'] in ('approved', 'changes_requested') and policy.review_reuse(
                scope_path, review_contract) is None:
            recorded = {**recorded, 'historical_status': recorded['status'],
                        'status': 'incomplete', 'error': 'review evidence is no longer applicable'}
        return {**execution, **recorded, 'review_receipt': ref}


def recover_action(scope_path, attempt_id, *, directory=None, harness_root=None,
                   controlled_test=False):
    """Observe existing Harness facts; never start or restart an existing attempt."""
    runtime = policy.read_runtime(scope_path)
    attempt = runtime['attempts'][attempt_id]
    recorded = attempt.get('execution_ref')
    if not recorded:
        return {'decision': 'unknown', 'started': False,
                'reason': 'the existing attempt has no bound execution output reference'}
    directory = Path(directory or recorded).resolve()
    if directory != Path(recorded).resolve():
        raise ValueError('recovery directory differs from the recorded execution reference')
    try:
        _, journal = _harness(harness_root)
    except (ImportError, ValueError) as error:
        return {'decision': 'execution_unavailable', 'started': False,
                'reason': str(error), 'native_agent_metering': False}
    with _owner(directory) as owned:
        intent_path = directory / 'execution.intent.json'
        if not intent_path.exists():
            return {'decision': 'unknown', 'started': False,
                    'reason': 'admission exists but no durable Harness intent was found'}
        intent = json.loads(intent_path.read_text())
        mode = policy.accounting_mode(runtime)
        if intent.get('accounting_mode', policy.NATIVE_MODE) != mode:
            raise ValueError('execution intent accounting mode differs from its runtime')
        if mode == policy.BOUNDED_MODE and (
                intent['timeout_s'] != attempt['command_timeout_s'] or
                intent['deadline_utc'] != attempt['command_deadline_utc'] or
                _intent_digest(intent) != attempt['intent_digest']):
            raise ValueError('bounded command intent or deadline differs from its admission')
        if mode == policy.BOUNDED_MODE and 'guard_allowance_s' in attempt and any(
                intent.get(key) != attempt[key] for key in
                ('guard_allowance_s', 'harness_process_sha256')):
            raise ValueError('bounded command guardian allowance differs from its admission')
        if intent.get('controlled_test') is not (controlled_test is True):
            raise ValueError('recovery requires the original explicit test mode')
        context = intent['binding']
        expected = {**attempt, 'task_id': runtime['task_id'], 'attempt_id': attempt_id}
        if context != _context(expected):
            raise ValueError('execution output does not bind the runtime attempt')
        path = directory / 'execution.receipt.json'
        if path.exists():
            receipt = json.loads(path.read_text())
            if any(receipt.get(key) != value for key, value in context.items()):
                raise ValueError('execution receipt identity differs from intent')
            return _collect(scope_path, path, receipt, started=False, controlled_test=controlled_test)
        events, torn = journal.read_events(directory / 'events.jsonl')
        events = [row for row in events if row.get('call_id') == context['execution_id']
                  and row.get('stage') == 'check']
        finished = [row for row in events if row['event'] == 'process_finished']
        if finished and not torn and owned:
            receipt = _receipt(context, intent, finished[-1])
            journal.atomic_json(path, receipt)
            return _collect(scope_path, path, receipt, started=False, controlled_test=controlled_test)
        running = (not owned and not torn and not finished and
                   any(row['event'] == 'process_started' for row in events) and
                   datetime.fromisoformat(intent['deadline_utc']) > datetime.now(timezone.utc))
        return {'decision': 'running' if running else 'unknown', 'started': False,
                'attempt_id': attempt_id, 'execution_id': context['execution_id'],
                'reason': 'live output owner and Harness start event with future deadline'
                          if running else 'completion or active execution is unconfirmed'}

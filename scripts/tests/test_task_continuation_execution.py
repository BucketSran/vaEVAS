"""Real Harness command tests; controlled meters never claim native coverage."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest


SCRIPTS = Path(__file__).resolve().parents[1]
SCRIPT = SCRIPTS / 'task_continuation_execution.py'
HARNESS = Path(os.environ.get('CONTINUATION_TEST_HARNESS',
    str(SCRIPTS.parent.parent.parent / 'circuits/circuit-harness')))
HAS_HARNESS = (HARNESS / 'circuit_harness/execution/runtime/process.py').is_file()
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
policy = importlib.import_module('task_continuation_policy')


class ControlledAgentMeter:
    """A declared ten-second test interval, independent of process wall time."""
    def __init__(self, root, seconds=10):
        self.root = Path(root)
        self.seconds = seconds

    def report(self, context, *, complete):
        value = {'kind': 'agent_active_meter', 'source_kind': 'controlled_test',
                 'available': True, 'binding': context, 'metering_complete': True,
                 'active_intervals': [['2026-01-01T00:00:00Z',
                                       '2026-01-01T00:%02d:%02dZ' % divmod(self.seconds, 60)]]
                                     if complete else [],
                 'basis': 'deterministic test clock; no native host coverage'}
        raw = json.dumps(value, sort_keys=True).encode()
        path = self.root / ('meter-' + hashlib.sha256(raw).hexdigest() + '.json')
        path.write_bytes(raw)
        return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}

    def preflight(self, context):
        return self.report(context, complete=False)

    def collect(self, context):
        return self.report(context, complete=True)


class ExecutionAdapterTests(unittest.TestCase):
    def setUp(self):
        evidence = os.environ.get('CONTINUATION_EXECUTION_EVIDENCE')
        if evidence:
            Path(evidence).mkdir(parents=True, exist_ok=True)
            self.root = Path(tempfile.mkdtemp(prefix=self._testMethodName + '-', dir=evidence))
        else:
            temp = tempfile.TemporaryDirectory()
            self.addCleanup(temp.cleanup)
            self.root = Path(temp.name)
        self.scope = self.root / 'scope.json'
        self.scope.write_text(json.dumps({'current': {
            'remaining_closure_ledger': 'cases400.json',
            'continuation': {'status': 'active', 'runtime': {
                'schema_version': 1, 'path': 'runtime.json'}}}}))
        (self.root / 'cases400.json').write_text(json.dumps({'cases': [
            {'case_id': '019', 'revised_result': 'REJECTED',
             'next_action': 'inspect original input'}]}))
        policy.initialize_runtime(self.scope, task_id='task', authority_ref='human-message',
                                  prior_consumed_s=0)
        spec = importlib.util.spec_from_file_location('continuation_execution', SCRIPT)
        self.execution = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.execution)
        self.marker = self.root / 'started.txt'
        self.argv = [sys.executable, '-B', '-c',
                     'from pathlib import Path;import sys;'
                     'p=Path(sys.argv[1]);'
                     'p.open("a").write("started\\n")', str(self.marker)]
        self.admission = {
            'event_id': 'admit:attempt-019', 'operation': 'admit', 'task_id': 'task',
            'route_id': 'original-019', 'action_id': 'original-019-inspect',
            'attempt_id': 'attempt-019', 'execution_id': 'execution-019',
            'actor': 'worker-019', 'case_ids': ['019'], 'ready': True,
            'purpose': 'exploration', 'input_digest': 'source-v1', 'allocation_s': 60,
            'plan': {'hypothesis': 'input stage differs', 'experiment': 'inspect fixed input',
                     'criterion': 'compare intermediate values'}}
        self.meter = ControlledAgentMeter(self.root)

    def run_action(self, **changes):
        arguments = dict(directory=self.root / 'command', cwd=self.root,
                         timeout_s=5, agent_meter=self.meter, controlled_test=True,
                         harness_root=HARNESS)
        arguments.update(changes)
        return self.execution.execute_action(self.scope, self.admission, self.argv, **arguments)

    def activate_command_mode(self, total=120, **config):
        scope = json.loads(self.scope.read_text())
        scope['current']['continuation']['runtime']['path'] = 'bounded-runtime.json'
        self.scope.write_text(json.dumps(scope))
        policy.initialize_runtime(self.scope, task_id='task', authority_ref='original-authority',
                                  prior_consumed_s=None, config=config)
        return policy.update_runtime(self.scope, {'operation': 'activate_bounded_execution',
            'event_id': 'activate-command-budget', 'task_id': 'task',
            'authority_ref': 'human-bounded-command-authorization', 'total_command_s': total})

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_tiny_reservation_cannot_ignore_guardian_and_cleanup_allowance(self):
        self.activate_command_mode()
        self.admission['allocation_s'] = .1
        with self.assertRaises(policy.PolicyError):
            self.run_action(agent_meter=None, controlled_test=False, timeout_s=.1)
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_production_command_runs_without_native_meter_and_charges_whole_allocation(self):
        self.activate_command_mode(total=12)
        self.admission['allocation_s'] = 9
        result = self.run_action(agent_meter=None, controlled_test=False, timeout_s=3)
        self.assertEqual(result['decision'], 'collected', result)
        self.assertTrue(result['settled'])
        self.assertEqual(result['execution']['accounting_mode'], 'bounded_command_seconds')
        self.assertEqual(result['execution']['active_intervals'], [])
        self.assertFalse(result['execution']['metering_complete'])
        self.assertFalse(result['native_agent_metering'])
        self.assertEqual(result['execution']['status'], 'completed')
        state = policy.read_runtime(self.scope)
        self.assertIsNone(state['prior_consumed_s'])
        self.assertEqual(state['attempts']['attempt-019']['consumed_s'], 9)
        self.assertEqual(self.execution.recover_action(
            self.scope, 'attempt-019', harness_root=HARNESS)['decision'], 'collected')
        self.assertEqual(self.marker.read_text(), 'started\n')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_150_second_deadline_runs_immediate_command(self):
        self.activate_command_mode(total=240)
        self.admission['allocation_s'] = 155.05
        result = self.run_action(agent_meter=None, controlled_test=False, timeout_s=150)
        self.assertEqual(result['decision'], 'collected', result)
        self.assertTrue(result['settled'])
        self.assertTrue(result['execution']['cleanup_confirmed'])
        self.assertEqual(result['execution']['command_timeout_s'], 150)
        self.assertEqual(result['execution']['guard_allowance_s'], 5.05)
        self.assertFalse(result['native_agent_metering'])
        self.assertEqual(self.marker.read_text(), 'started\n')
        state = policy.read_runtime(self.scope)
        attempt = state['attempts']['attempt-019']
        self.assertEqual(attempt['command_timeout_s'], 150)
        self.assertEqual(attempt['allocation_s'], 155.05)
        self.assertEqual(attempt['consumed_s'], 155.05)
        self.assertEqual(attempt['active_intervals'], [])

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_150_second_deadline_refuses_short_reservation_or_total_budget(self):
        self.activate_command_mode(total=240)
        for allocation, reason in ((150, 'timeout, guardian and cleanup'),
                                   (181, 'protected or unavailable budget')):
            with self.subTest(allocation=allocation):
                self.admission['allocation_s'] = allocation
                before = policy.read_runtime(self.scope)
                with self.assertRaisesRegex(policy.PolicyError, reason):
                    self.run_action(agent_meter=None, controlled_test=False, timeout_s=150)
                self.assertEqual(policy.read_runtime(self.scope), before)
                self.assertFalse(self.marker.exists())
                self.assertFalse((self.root / 'command' / 'execution.intent.json').exists())
                self.assertFalse((self.root / 'command' / 'events.jsonl').exists())

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_replay_preserves_original_150_second_deadline_and_parameters(self):
        self.activate_command_mode(total=240)
        self.admission['allocation_s'] = 155.05
        self.run_action(agent_meter=None, controlled_test=False, timeout_s=150)
        intent_path = self.root / 'command' / 'execution.intent.json'
        original = intent_path.read_bytes()
        intent = json.loads(original)
        replay = self.run_action(agent_meter=None, controlled_test=False, timeout_s=150)
        self.assertEqual(replay['decision'], 'collected', replay)
        self.assertFalse(replay['started'])
        self.assertEqual(replay['execution']['command_timeout_s'], 150)
        self.assertEqual(replay['execution']['deadline_utc'], intent['deadline_utc'])
        for changes in ({'timeout_s': 90}, {'timeout_s': 120},
                        {'timeout_s': 150, 'cwd': self.root / 'other-cwd'},
                        {'timeout_s': 150, 'max_output_bytes': 1024}):
            with self.subTest(changes=changes), self.assertRaisesRegex(
                    ValueError, 'different command'):
                self.run_action(agent_meter=None, controlled_test=False, **changes)
        self.assertEqual(intent_path.read_bytes(), original)
        attempt = policy.read_runtime(self.scope)['attempts']['attempt-019']
        self.assertEqual(attempt['command_timeout_s'], 150)
        self.assertEqual(attempt['command_deadline_utc'], intent['deadline_utc'])
        self.assertEqual(attempt['consumed_s'], 155.05)
        self.assertEqual(self.marker.read_text(), 'started\n')

    def test_bounded_invalid_deadlines_refuse_before_dispatch(self):
        self.activate_command_mode(total=240)
        self.admission['allocation_s'] = 155.05
        before = policy.read_runtime(self.scope)
        for timeout in (float('nan'), float('inf'), float('-inf'), -1, 0,
                        True, False, '150', None):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.run_action(agent_meter=None, controlled_test=False, timeout_s=timeout)
        self.assertEqual(policy.read_runtime(self.scope), before)
        self.assertFalse(self.marker.exists())
        self.assertFalse((self.root / 'command').exists())

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_replay_rejects_boolean_timeout_equal_to_original_one_second_deadline(self):
        self.activate_command_mode(total=12)
        self.admission['allocation_s'] = 6.05
        first = self.run_action(agent_meter=None, controlled_test=False, timeout_s=1)
        self.assertEqual(first['execution']['status'], 'completed', first)
        intent_path = self.root / 'command' / 'execution.intent.json'
        original = intent_path.read_bytes()
        before = policy.read_runtime(self.scope)
        with self.assertRaisesRegex(ValueError, 'finite positive number'):
            self.run_action(agent_meter=None, controlled_test=False, timeout_s=True)
        self.assertEqual(policy.read_runtime(self.scope), before)
        self.assertEqual(intent_path.read_bytes(), original)
        self.assertEqual(self.marker.read_text(), 'started\n')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_native_default_deadline_stays_90_seconds_and_rejects_longer_deadlines(self):
        for timeout in (90.01, 120, 150):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                self.run_action(timeout_s=timeout)
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})
        result = self.execution.execute_action(
            self.scope, self.admission, self.argv, directory=self.root / 'command',
            cwd=self.root, agent_meter=self.meter, controlled_test=True,
            harness_root=HARNESS)
        self.assertEqual(result['decision'], 'collected', result)
        intent = json.loads((self.root / 'command' / 'execution.intent.json').read_text())
        self.assertEqual(intent['timeout_s'], 90)
        self.assertEqual(self.marker.read_text(), 'started\n')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_limits_and_controlled_meter_refuse_before_any_process_starts(self):
        self.activate_command_mode(total=12)
        for allocation in (10, 2):
            self.admission['allocation_s'] = allocation
            with self.subTest(allocation=allocation), self.assertRaises(policy.PolicyError):
                self.run_action(agent_meter=None, controlled_test=False, timeout_s=3)
        self.admission['allocation_s'] = 3
        with self.assertRaisesRegex(ValueError, 'controlled-test'):
            self.run_action()
        unavailable = self.run_action(agent_meter=None, controlled_test=False, timeout_s=3,
                                      harness_root=self.root / 'missing-Harness')
        self.assertEqual(unavailable['decision'], 'execution_unavailable')
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_same_actor_parallel_commands_share_one_summed_budget(self):
        self.activate_command_mode(total=24)
        barrier = threading.Barrier(3)
        outcomes, errors = [], []
        def execute(index):
            admission = dict(self.admission, event_id=f'bounded-{index}', allocation_s=9,
                             action_id=f'bounded-{index}', attempt_id=f'bounded-{index}',
                             execution_id=f'bounded-{index}')
            try:
                barrier.wait(timeout=3)
                outcomes.append(self.execution.execute_action(self.scope, admission, self.argv,
                    directory=self.root / f'parallel-{index}', cwd=self.root, timeout_s=2,
                    harness_root=HARNESS))
            except BaseException as error:
                errors.append(error)
        workers = [threading.Thread(target=execute, args=(index,)) for index in range(3)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=5)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(outcomes), 2, outcomes)
        self.assertEqual(len(errors), 1, errors)
        self.assertIsInstance(errors[0], policy.PolicyError)
        self.assertEqual(self.marker.read_text(), 'started\nstarted\n')
        state = policy.read_runtime(self.scope)
        self.assertEqual({attempt['actor'] for attempt in state['attempts'].values()}, {'worker-019'})
        budget = policy.evaluate(state, {'goal_complete': False, 'runnable': True})['budget']
        self.assertEqual(budget['consumed_s'], 18)
        self.assertEqual(budget['available_s'], 0)

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_owner_loss_retains_full_guard_reservation_and_guardian_stops_late_work(self):
        self.activate_command_mode()
        self.admission['allocation_s'] = 6
        late = self.root / 'must-not-run-after-guardian.txt'
        self.argv = [sys.executable, '-B', '-c',
            'import time,sys;from pathlib import Path;from datetime import datetime,timezone;'
            'time.sleep(.5);Path(sys.argv[1]).write_text(datetime.now(timezone.utc).isoformat());'
            'time.sleep(3);Path(sys.argv[2]).write_text("too late")', str(self.marker), str(late)]
        payload = self.root / 'owner-loss.json'
        payload.write_text(json.dumps({'scope': str(self.scope), 'admission': self.admission,
            'argv': self.argv, 'directory': str(self.root / 'command'), 'root': str(self.root)}))
        runner = self.root / 'owner-loss.py'
        runner.write_text('import json,os,sys\nfrom pathlib import Path\n'
            f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
            'import task_continuation_execution as a\n'
            '_,j=a._harness()\nold=j.Journal.emit\n'
            'def stop(self,event,**fields):\n'
            '    old(self,event,**fields)\n'
            '    if event=="process_started": os._exit(79)\n'
            'j.Journal.emit=stop\np=json.loads(Path(sys.argv[1]).read_text())\n'
            'a.execute_action(p["scope"],p["admission"],p["argv"],\n'
            '    directory=p["directory"],cwd=p["root"],timeout_s=.1)\n')
        owner = subprocess.run([sys.executable, '-B', str(runner), str(payload)],
                               capture_output=True, text=True, timeout=3)
        self.assertEqual(owner.returncode, 79, owner.stderr)
        try:
            time.sleep(4)
            self.assertTrue(self.marker.exists())
            self.assertFalse(late.exists(), 'guardian must stop work beyond its real lifetime')
            intent = json.loads((self.root / 'command/execution.intent.json').read_text())
            self.assertGreater(self.marker.read_text(), intent['deadline_utc'])
            self.assertEqual(intent['guard_allowance_s'], 5.05)
            self.assertEqual(self.run_action(agent_meter=None, controlled_test=False,
                                             timeout_s=.1)['decision'], 'unknown')
            state = policy.read_runtime(self.scope)
            self.assertEqual(state['attempts']['attempt-019']['allocation_s'], 6)
            self.assertFalse(state['attempts']['attempt-019']['settled'])
            budget = policy.evaluate(state, {'goal_complete': False, 'runnable': True})['budget']
            self.assertEqual(budget['reserved_s'], 6)
            (self.root / 'owner-loss-result.json').write_text(json.dumps({
                'owner_returncode': owner.returncode, 'declared_timeout_s': .1,
                'guard_allowance_s': 5.05, 'reserved_s': budget['reserved_s'],
                'early_marker_after_declared_deadline': True, 'late_marker_exists': late.exists(),
                'harness_process_sha256': intent['harness_process_sha256']}))
        finally:
            events = (self.root / 'command/events.jsonl').read_text().splitlines()
            for event in map(json.loads, events):
                if event['event'] == 'process_started':
                    try:
                        import signal
                        os.killpg(event['group_pid'], signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_failure_timeout_and_cancellation_charge_each_whole_allocation(self):
        self.activate_command_mode()
        for kind in ('failure', 'timeout', 'cancelled'):
            admission = dict(self.admission, event_id=kind, action_id=kind,
                             attempt_id=kind, execution_id=kind, allocation_s=6)
            argv = [sys.executable, '-B', '-c', 'raise SystemExit(4)' if kind == 'failure'
                    else 'import time;time.sleep(1)']
            cancel = threading.Event()
            if kind == 'cancelled':
                cancel.set()
            result = self.execution.execute_action(self.scope, admission, argv,
                directory=self.root / kind, cwd=self.root, timeout_s=.1,
                cancel=cancel, harness_root=HARNESS)
            self.assertEqual(result['decision'], 'collected', result)
            self.assertTrue(result['settled'])
            self.assertEqual(result['execution']['status'], 'cancelled' if kind == 'cancelled' else 'failed')
            self.assertEqual(policy.read_runtime(self.scope)['attempts'][kind]['consumed_s'], 6)
        self.assertEqual(policy.evaluate(policy.read_runtime(self.scope),
            {'goal_complete': False, 'runnable': True})['budget']['consumed_s'], 18)

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_bounded_crash_recovery_collects_journal_or_receipt_without_rerun_or_double_charge(self):
        self.activate_command_mode()
        for point in ('before-receipt', 'after-receipt'):
            admission = dict(self.admission, event_id=point, action_id=point,
                             attempt_id=point, execution_id=point, allocation_s=8)
            payload = self.root / (point + '.json')
            payload.write_text(json.dumps({'scope': str(self.scope), 'admission': admission,
                'argv': self.argv, 'directory': str(self.root / point), 'root': str(self.root)}))
            runner = self.root / (point + '.py')
            runner.write_text(
                'import json,os,sys\nfrom pathlib import Path\n'
                f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
                'import task_continuation_execution as adapter\n'
                'p=json.loads(Path(sys.argv[1]).read_text())\n'
                + ('_,journal=adapter._harness()\nwrite=journal.atomic_json\n'
                   'def stop(path,value):\n'
                   '    if path.name=="execution.receipt.json": os._exit(79)\n'
                   '    return write(path,value)\njournal.atomic_json=stop\n'
                   if point == 'before-receipt' else
                   'update=adapter.policy.update_runtime\n'
                   'def stop(scope,request):\n'
                   '    if request["operation"]=="reconcile": os._exit(79)\n'
                   '    return update(scope,request)\nadapter.policy.update_runtime=stop\n')
                + 'adapter.execute_action(p["scope"],p["admission"],p["argv"],\n'
                  '    directory=p["directory"],cwd=p["root"],timeout_s=2)\n')
            crash = subprocess.run([sys.executable, '-B', str(runner), str(payload)],
                                   capture_output=True, text=True, timeout=8)
            self.assertEqual(crash.returncode, 79, crash.stderr)
            for _ in range(2):
                result = self.execution.recover_action(self.scope, point, harness_root=HARNESS)
                self.assertEqual(result['decision'], 'collected')
                self.assertTrue(result['settled'])
            self.assertEqual(policy.read_runtime(self.scope)['attempts'][point]['consumed_s'], 8)
        self.assertEqual(self.marker.read_text(), 'started\nstarted\n')

    def test_missing_native_agent_meter_refuses_before_marker_process_starts(self):
        before = (self.scope.read_bytes(), (self.root / 'cases400.json').read_bytes())
        result = self.execution.execute_action(
            self.scope, self.admission, self.argv, directory=self.root / 'command',
            cwd=self.root, timeout_s=5)
        self.assertEqual(result['decision'], 'metering_unavailable')
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})
        self.assertEqual(before, (self.scope.read_bytes(),
                                 (self.root / 'cases400.json').read_bytes()))

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_historical_313_with_87_actions_dispatches_original_id_exactly_once(self):
        fixture = json.loads((SCRIPTS / 'tests/fixtures/continuation-wave21-313.json').read_text())
        scope = fixture['scope']
        scope['workspace']['root'] = str(self.root)
        scope['current']['remaining_closure_ledger'] = 'cases400.json'
        scope['current']['continuation'] = {'status': 'active', 'runtime': {
            'schema_version': 1, 'path': 'runtime.json'}}
        self.scope.write_text(json.dumps(scope))
        rows = [{'case_id': cid, 'revised_result': 'PASS'}
                for cid in fixture['queue']['passed_ids']] + fixture['queue']['remaining']
        queue_path = self.root / 'cases400.json'
        queue_path.write_text(json.dumps({'cases': rows}))
        before = (self.scope.read_bytes(), queue_path.read_bytes())
        self.assertEqual(sum(row['revised_result'] == 'PASS' for row in rows), 313)
        self.assertEqual(len([row for row in rows if row['revised_result'] != 'PASS']), 87)
        session = scope['workspace']['main_thread']
        stop = subprocess.run([
            sys.executable, '-B', str(SCRIPTS / 'check_task_continuation.py'),
            '--scope', str(self.scope), '--session-id', session], input=json.dumps({
                'hook_event_name': 'Stop', 'session_id': session, 'cwd': str(self.root),
                'stop_hook_active': False,
                'last_assistant_message': '313 accepted, no jobs running; stopping.'}),
            capture_output=True, text=True, timeout=5)
        (self.root / 'stop-cli-result.json').write_text(stop.stdout)
        self.assertEqual(stop.returncode, 0, stop.stderr)
        self.assertEqual(json.loads(stop.stdout)['decision'], 'block')
        first = self.run_action()
        self.assertEqual(first['decision'], 'collected', first)
        self.assertEqual(first['execution']['returncode'], 0)
        self.assertEqual(first['execution']['status'], 'completed')
        self.assertTrue(first['execution']['cleanup_confirmed'])
        self.assertFalse(first['native_agent_metering'])
        second = self.run_action()
        self.assertEqual(second['decision'], 'collected')
        self.assertFalse(second['started'])
        self.assertEqual(self.marker.read_text(), 'started\n')
        runtime = policy.read_runtime(self.scope)
        self.assertEqual(runtime['attempts']['attempt-019']['consumed_s'], 10)
        self.assertNotEqual(first['execution']['process_wall_s'], 10)
        self.assertEqual(before, (self.scope.read_bytes(), queue_path.read_bytes()))

    def test_controlled_test_meter_is_rejected_by_default_production_call(self):
        with self.assertRaisesRegex(ValueError, 'explicit test mode'):
            self.run_action(controlled_test=False)
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    def test_incomplete_meter_preflight_never_starts_the_marker(self):
        meter = self.meter
        class IncompleteMeter:
            def preflight(self, context):
                ref = meter.preflight(context)
                path = Path(ref['path'])
                value = json.loads(path.read_text())
                value['metering_complete'] = False
                path.write_text(json.dumps(value))
                return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        result = self.run_action(agent_meter=IncompleteMeter())
        self.assertEqual(result['decision'], 'metering_unavailable')
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    def test_missing_harness_never_starts_a_fallback_process(self):
        result = self.execution.execute_action(
            self.scope, self.admission, self.argv, directory=self.root / 'command',
            agent_meter=self.meter, controlled_test=True,
            harness_root=self.root / 'missing-harness')
        self.assertEqual(result['decision'], 'execution_unavailable')
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_no_quota_and_stagnation_refusals_leave_marker_process_unstarted(self):
        policy.update_runtime(self.scope, dict(self.admission,
            event_id='reserved-all', action_id='earlier-work', attempt_id='earlier-attempt',
            purpose='work', allocation_s=10800))
        with self.assertRaises(policy.PolicyError):
            self.run_action()
        self.assertFalse(self.marker.exists())

        scope = json.loads(self.scope.read_text())
        scope['current']['continuation']['runtime']['path'] = 'stagnation-runtime.json'
        self.scope.write_text(json.dumps(scope))
        policy.initialize_runtime(self.scope, task_id='task', authority_ref='human-message',
                                  prior_consumed_s=0)
        self.admission['allocation_s'] = 3600
        self.meter = ControlledAgentMeter(self.root, seconds=1800)
        self.assertEqual(self.run_action()['decision'], 'collected')
        self.marker = self.root / 'must-not-start.txt'
        self.argv[-1] = str(self.marker)
        self.admission.update(event_id='next-after-stagnation', action_id='next-action',
                              attempt_id='next-attempt', execution_id='next-execution')
        with self.assertRaisesRegex(policy.PolicyError, 'requires replan'):
            self.run_action(directory=self.root / 'rejected-command')
        self.assertFalse(self.marker.exists())

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_live_harness_owner_is_running_and_same_attempt_is_not_dispatched_twice(self):
        self.argv = [sys.executable, '-B', '-c',
                     'from pathlib import Path;import sys,time;'
                     'p=Path(sys.argv[1]);p.open("a").write("started\\n");'
                     'release=Path(sys.argv[2]);'
                     '\nwhile not release.exists(): time.sleep(.01)',
                     str(self.marker), str(self.root / 'release')]
        outcomes, errors = [], []
        def execute():
            try:
                outcomes.append(self.run_action())
            except BaseException as error:
                errors.append(error)
        worker = threading.Thread(target=execute)
        worker.start()
        try:
            until = time.monotonic() + 3
            while not self.marker.exists() and time.monotonic() < until and not errors:
                time.sleep(.01)
            self.assertTrue(self.marker.exists(), errors)
            result = self.execution.recover_action(self.scope, 'attempt-019', controlled_test=True)
            self.assertEqual(result['decision'], 'running', result)
            duplicate = self.run_action()
            self.assertEqual(duplicate['decision'], 'running')
            self.assertEqual(self.marker.read_text(), 'started\n')
        finally:
            (self.root / 'release').touch()
            worker.join(timeout=6)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(outcomes[0]['decision'], 'collected')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_unknown_admitted_attempt_never_dispatches_a_second_process(self):
        policy.update_runtime(self.scope, dict(self.admission,
            execution_ref=str(self.root / 'command')))
        self.assertEqual(self.run_action()['decision'], 'unknown')
        self.assertEqual(self.run_action()['decision'], 'unknown')
        self.assertFalse(self.marker.exists())
        self.assertFalse(policy.read_runtime(self.scope)['attempts']['attempt-019']['settled'])

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_completed_command_is_collected_after_real_wrapper_crash_without_rerun(self):
        payload = self.root / 'crash-input.json'
        payload.write_text(json.dumps({'scope': str(self.scope), 'admission': self.admission,
                                      'argv': self.argv, 'root': str(self.root)}))
        runner = self.root / 'crash-wrapper.py'
        runner.write_text(
            'import json,os,sys\n'
            f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
            f'sys.path.insert(0, {str(SCRIPTS / "tests")!r})\n'
            'import task_continuation_execution as adapter\n'
            'from test_task_continuation_execution import ControlledAgentMeter\n'
            'from pathlib import Path\n'
            'p=json.loads(Path(sys.argv[1]).read_text())\n'
            'update=adapter.policy.update_runtime\n'
            'def crash_after_durable_result(scope, request):\n'
            '    if request["operation"] == "reconcile": os._exit(79)\n'
            '    return update(scope, request)\n'
            'adapter.policy.update_runtime=crash_after_durable_result\n'
            'adapter.execute_action(p["scope"],p["admission"],p["argv"],\n'
            '    directory=Path(p["root"])/"command",cwd=p["root"],timeout_s=5,\n'
            '    agent_meter=ControlledAgentMeter(p["root"]),controlled_test=True)\n')
        crash = subprocess.run([sys.executable, '-B', str(runner), str(payload)],
                               capture_output=True, text=True, timeout=10)
        (self.root / 'wrapper-crash-result.json').write_text(json.dumps({
            'returncode': crash.returncode, 'stdout': crash.stdout, 'stderr': crash.stderr}))
        self.assertEqual(crash.returncode, 79, crash.stderr)
        self.assertEqual(self.marker.read_text(), 'started\n')
        self.assertFalse(policy.read_runtime(self.scope)['attempts']['attempt-019']['settled'])
        recovered = self.execution.recover_action(self.scope, 'attempt-019', controlled_test=True)
        self.assertEqual(recovered['decision'], 'collected')
        self.assertFalse(recovered['started'])
        self.assertTrue(recovered['settled'])
        self.assertEqual(self.execution.recover_action(
            self.scope, 'attempt-019', controlled_test=True)['decision'], 'collected')
        self.assertEqual(self.marker.read_text(), 'started\n')
        self.assertEqual(policy.read_runtime(self.scope)['attempts']['attempt-019']['consumed_s'], 10)

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_renamed_stagnant_route_cannot_launch_another_command(self):
        scope = json.loads(self.scope.read_text())
        scope['current']['continuation']['runtime']['path'] = 'stagnation-runtime.json'
        self.scope.write_text(json.dumps(scope))
        policy.initialize_runtime(self.scope, task_id='task', authority_ref='human-message',
                                  prior_consumed_s=0, config={'stagnation_s': 10})
        self.run_action()
        state = policy.read_runtime(self.scope)
        self.assertEqual(policy.evaluate(state, {
            'goal_complete': False, 'runnable': True})['decision'], 'replan_required')
        renamed = dict(self.admission, event_id='renamed', route_id='renamed-route',
                       action_id='renamed-action', attempt_id='renamed-attempt',
                       execution_id='renamed-execution',
                       plan=dict(self.admission['plan'], hypothesis='same idea, new wording'))
        with self.assertRaises(policy.PolicyError):
            self.execution.execute_action(
                self.scope, renamed, self.argv, directory=self.root / 'renamed-command',
                cwd=self.root, timeout_s=5, agent_meter=self.meter, controlled_test=True,
                harness_root=HARNESS)
        self.assertEqual(self.marker.read_text(), 'started\n')
        self.assertEqual(len(policy.read_runtime(self.scope)['attempts']), 1)

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_concurrent_admission_never_starts_two_commands_against_one_remaining_allocation(self):
        queue = self.root / 'cases400.json'
        queue.write_text(json.dumps({'cases': [
            {'case_id': '019', 'revised_result': 'REJECTED'},
            {'case_id': '020', 'revised_result': 'REJECTED'}]}))
        scope = json.loads(self.scope.read_text())
        scope['current']['continuation']['runtime']['path'] = 'small-runtime.json'
        self.scope.write_text(json.dumps(scope))
        policy.initialize_runtime(self.scope, task_id='task', authority_ref='human-message',
                                  prior_consumed_s=0, config={'total_agent_s': 80})
        barrier = threading.Barrier(2)
        outcomes, errors = [], []
        def execute(index):
            admission = dict(self.admission, event_id=f'admit-{index}',
                             route_id=f'route-{index}', action_id=f'action-{index}',
                             attempt_id=f'attempt-{index}', execution_id=f'execution-{index}',
                             case_ids=[f'{19 + index:03d}'])
            try:
                barrier.wait(timeout=3)
                outcomes.append(self.execution.execute_action(
                    self.scope, admission, self.argv, directory=self.root / f'command-{index}',
                    cwd=self.root, timeout_s=5, agent_meter=self.meter, controlled_test=True,
                    harness_root=HARNESS))
            except BaseException as error:
                errors.append(error)
        workers = [threading.Thread(target=execute, args=(index,)) for index in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=6)
        self.assertTrue(all(not worker.is_alive() for worker in workers))
        self.assertEqual(len(outcomes), 1, outcomes)
        self.assertEqual(len(errors), 1, errors)
        self.assertIsInstance(errors[0], policy.PolicyError)
        self.assertIn('budget', str(errors[0]))
        self.assertEqual(self.marker.read_text(), 'started\n')
        self.assertEqual(len(policy.read_runtime(self.scope)['attempts']), 1)

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_recovery_cannot_relabel_controlled_test_meter_as_native_coverage(self):
        self.run_action()
        path = self.root / 'command/execution.receipt.json'
        receipt = json.loads(path.read_text())
        receipt['meter_source_kind'] = 'native_agent_active'
        path.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'meter receipt'):
            self.execution.recover_action(self.scope, 'attempt-019', harness_root=HARNESS,
                                          controlled_test=True)
        self.assertEqual(self.marker.read_text(), 'started\n')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_invalid_finish_meter_collects_process_result_but_preserves_unknown_usage(self):
        meter = self.meter
        class InvalidFinishMeter:
            preflight = meter.preflight
            def collect(self, context):
                return dict(meter.collect(context), sha256='invalid-meter-digest')
        result = self.run_action(agent_meter=InvalidFinishMeter())
        self.assertEqual(result['decision'], 'collected')
        self.assertFalse(result['settled'])
        self.assertEqual(result['execution']['status'], 'completed')
        self.assertFalse(result['execution']['metering_complete'])
        self.assertEqual(result['execution']['active_intervals'], [])
        self.assertEqual(self.run_action()['decision'], 'collected')
        self.assertEqual(self.marker.read_text(), 'started\n')
        attempt = policy.read_runtime(self.scope)['attempts']['attempt-019']
        self.assertEqual(attempt['allocation_s'], 60)
        self.assertEqual(attempt['consumed_s'], 0)
        self.assertTrue(attempt['metering_unknown'])

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_same_action_with_changed_binding_or_command_is_rejected(self):
        self.run_action()
        for key, replacement in {
                'task_id': 'another-task', 'route_id': 'another-route',
                'input_digest': 'different-input', 'actor': 'another-worker',
                'attempt_id': 'another-attempt', 'execution_id': 'another-execution',
                'case_ids': ['020'], 'allocation_s': 61}.items():
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.execution.execute_action(self.scope, dict(self.admission, **{key: replacement}),
                    self.argv, directory=self.root / 'command', cwd=self.root, timeout_s=5,
                    agent_meter=self.meter, controlled_test=True, harness_root=HARNESS)
        with self.assertRaisesRegex(ValueError, 'command'):
            self.execution.execute_action(self.scope, self.admission,
                self.argv + ['different-argument'], directory=self.root / 'command',
                cwd=self.root, timeout_s=5, agent_meter=self.meter, controlled_test=True,
                harness_root=HARNESS)
        with self.assertRaisesRegex(ValueError, 'command'):
            self.run_action(cwd=self.root / 'different-cwd')
        self.assertEqual(self.marker.read_text(), 'started\n')

    @unittest.skipUnless(HAS_HARNESS, 'external Harness unavailable; no fallback runner')
    def test_default_production_recovery_refuses_original_controlled_test_mode(self):
        self.run_action()
        with self.assertRaisesRegex(ValueError, 'test mode'):
            self.execution.recover_action(self.scope, 'attempt-019', harness_root=HARNESS)
        with self.assertRaisesRegex(ValueError, 'test mode'):
            self.run_action(controlled_test=False)
        self.assertEqual(self.marker.read_text(), 'started\n')


if __name__ == '__main__':
    unittest.main()

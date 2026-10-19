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

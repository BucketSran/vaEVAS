"""Replay the real accepted313/400 checkpoint through the Stop command contract."""
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'check_task_continuation.py'
FIXTURE = Path(__file__).resolve().parent / 'fixtures/continuation-wave21-313.json'
sys.path.insert(0, str(SCRIPT.parent))
initialize_runtime = importlib.import_module('task_continuation_policy').initialize_runtime
update_runtime = importlib.import_module('task_continuation_policy').update_runtime


class ContinuationChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        saved = json.loads(FIXTURE.read_text())
        self.scope = saved['scope']
        self.scope['workspace']['root'] = str(self.root)
        self.scope['current']['remaining_closure_ledger'] = str(self.root / 'cases400.json')
        self.queue = {'cases': sorted(
            [{'case_id': cid, 'revised_result': 'PASS'} for cid in saved['queue']['passed_ids']]
            + saved['queue']['remaining'], key=lambda row: row['case_id'])}
        self.session = self.scope['workspace']['main_thread']
        self.event = {'hook_event_name': 'Stop', 'session_id': self.session,
                      'cwd': str(self.root), 'stop_hook_active': False,
                      'last_assistant_message': 'Frozen checkpoint accepted; no jobs running.'}

    def invoke(self, *, scope=None, queue=None, event=None):
        scope = copy.deepcopy(self.scope if scope is None else scope)
        queue = copy.deepcopy(self.queue if queue is None else queue)
        path = self.root / 'scope.json'
        path.write_text(json.dumps(scope))
        ledger = self.root / 'cases400.json'
        ledger.write_text(json.dumps(queue))
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in [path, ledger]]
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--scope', str(path),
                                 '--session-id', self.session],
                                input=json.dumps(self.event if event is None else event),
                                text=True, capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in [path, ledger]])
        return json.loads(result.stdout)

    def test_actual_313_checkpoint_with_87_actions_cannot_stop(self):
        self.assertEqual(len(self.queue['cases']), 400)
        self.assertEqual(sum(r['revised_result'] == 'PASS' for r in self.queue['cases']), 313)
        self.assertEqual(self.scope['current']['running_original_or_full_python_jobs'], [])
        decision = self.invoke()
        self.assertEqual(decision.get('decision'), 'block', decision)
        self.assertIn('87', decision['reason'])
        self.assertIn('019', decision['reason'])

    def test_repeated_stop_is_still_blocked_without_progress(self):
        event = dict(self.event, stop_hook_active=True)
        self.assertEqual(self.invoke(event=event).get('decision'), 'block')

    def opt_in_runtime(self, prior_consumed_s):
        self.scope['current']['continuation'] = {
            'status': 'active', 'runtime': {'schema_version': 1, 'path': 'runtime.json'}}
        path = self.root / 'scope.json'
        path.write_text(json.dumps(self.scope))
        (self.root / 'cases400.json').write_text(json.dumps(self.queue))
        initialize_runtime(path, task_id='historical-313-replay',
                           authority_ref='fixture-authorized-window',
                           prior_consumed_s=prior_consumed_s)

    def test_unknown_active_usage_does_not_force_unbudgeted_continuation(self):
        self.opt_in_runtime(None)
        self.assertNotIn('decision', self.invoke())
        self.assertEqual(self.scope['current']['revised400']['passed'], 313)

    def test_exhausted_execution_window_can_report_unfinished_work(self):
        self.opt_in_runtime(14400)
        self.assertNotIn('decision', self.invoke())
        self.assertFalse(self.scope['current']['revised400'].get('target400_complete', False))

    def test_opted_in_available_budget_still_blocks_the_historical_stop(self):
        self.opt_in_runtime(0)
        self.assertEqual(self.invoke().get('decision'), 'block')

    def record_running_019(self):
        self.opt_in_runtime(0)
        path = self.root / 'scope.json'
        update_runtime(path, {
            'event_id': 'claim-019', 'operation': 'admit',
            'task_id': 'historical-313-replay', 'route_id': 'route-019',
            'action_id': 'action-019', 'attempt_id': 'attempt-019',
            'actor': 'worker', 'case_ids': ['019'], 'ready': True,
            'execution_id': 'job-019', 'input_digest': 'fixture-source',
            'allocation_s': 60, 'purpose': 'exploration',
            'plan': {'hypothesis': 'input stage', 'experiment': 'inspect fixed input',
                     'criterion': 'compare intermediate value'}})
        now = datetime.now(timezone.utc)
        receipt = self.root / 'running-019.json'
        receipt.write_text(json.dumps({
            'kind': 'execution', 'task_id': 'historical-313-replay',
            'route_id': 'route-019', 'action_id': 'action-019',
            'attempt_id': 'attempt-019', 'input_digest': 'fixture-source',
            'execution_id': 'job-019', 'status': 'running',
            'observed_at_utc': now.isoformat(),
            'deadline_utc': (now + timedelta(hours=1)).isoformat(),
            'active_intervals': [], 'metering_complete': True}))
        update_runtime(path, {
            'event_id': 'running-019', 'operation': 'reconcile',
            'task_id': 'historical-313-replay', 'receipt': {
                'path': receipt.name, 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}})

    def test_running_case_does_not_hide_86_unassigned_ready_actions(self):
        self.record_running_019()
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_only_ready_case_already_running_can_wait(self):
        self.record_running_019()
        # Keep the same 400 IDs and acceptance count; only readiness changes.
        for row in self.queue['cases']:
            if row['revised_result'] != 'PASS' and row['case_id'] != '019':
                receipt = self.root / (row['case_id'] + '-wait.json')
                receipt.write_text(json.dumps({'case_id': row['case_id'],
                                               'blocker_kind': 'external_dependency',
                                               'next_check': 'fixture dependency restored'}))
                row['continuation_block'] = {'kind': 'external_dependency', 'evidence': {
                    'path': receipt.name, 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}}
        self.assertNotIn('decision', self.invoke())

    def test_explicit_stop_probe_blocks_once_and_records_same_turn_continuation(self):
        self.scope['current']['continuation'] = {
            'status': 'paused', 'user_pause': {'message_ref': 'EVAS waits for workflow checks'},
            'native_stop_probe': {'nonce': 'fixture-probe', 'receipt': 'native-probe.jsonl'}}
        event = dict(self.event, turn_id='fixture-turn')
        self.assertEqual(self.invoke(event=event).get('decision'), 'block')
        self.assertNotIn('decision', self.invoke(event=dict(event, stop_hook_active=True)))
        rows = [json.loads(line) for line in (self.root / 'native-probe.jsonl').read_text().splitlines()]
        self.assertEqual([row['outcome'] for row in rows], ['block_once', 'same_turn_continuation'])
        self.assertEqual({row['turn_id'] for row in rows}, {'fixture-turn'})
        self.assertNotIn('decision', self.invoke(event=dict(event, turn_id='later-turn')))

    def test_stop_probe_cannot_overwrite_task_or_escape_its_evidence_directory(self):
        self.scope['current']['continuation'] = {
            'status': 'paused', 'user_pause': {'message_ref': 'human pause'},
            'native_stop_probe': {'nonce': 'fixture-probe', 'receipt': '../escape.jsonl'}}
        decision = self.invoke(event=dict(self.event, turn_id='fixture-turn'))
        self.assertEqual(decision.get('decision'), 'block')
        self.assertIn('probe receipt', decision['reason'])

    def test_other_thread_and_non_stop_events_are_unaffected(self):
        self.assertNotIn('decision', self.invoke(event=dict(self.event, session_id='another-thread')))
        self.assertNotIn('decision', self.invoke(event=dict(self.event, hook_event_name='Interrupt')))

    def test_bound_main_thread_cannot_bypass_check_by_changing_directory(self):
        decision = self.invoke(event=dict(self.event, cwd=str(self.root.parent)))
        self.assertEqual(decision.get('decision'), 'block', decision)

    def test_another_400_case_roster_cannot_replace_the_fixed_ids(self):
        self.scope['current']['revised400'].update(passed=400, target400_complete=True)
        self.scope['current']['delivery_checks'] = {'status': 'closed'}
        self.queue['acceptance_summary'] = {'target400_complete': True}
        for index, row in enumerate(self.queue['cases'], 401):
            row.update(case_id=str(index), revised_result='PASS')
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_completed_candidate_and_old_morning_deadline_do_not_finish_goal(self):
        self.scope['objective']['morning_review_at'] = '2000-01-01T00:00:00+00:00'
        self.scope['current']['rework']['status'] = 'phase complete'
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_explicit_current_deadline_can_end_the_execution_window(self):
        self.scope['current']['continuation'] = {'status': 'active',
                                                'deadline_utc': '2000-01-01T00:00:00+00:00'}
        self.assertNotIn('decision', self.invoke())

    def test_pause_requires_recorded_human_authority(self):
        self.scope['current']['continuation'] = {'status': 'paused'}
        self.assertEqual(self.invoke().get('decision'), 'block')
        self.scope['current']['continuation']['user_pause'] = {'message_ref': 'human-message-42'}
        self.assertNotIn('decision', self.invoke())

    def test_verified_full_target_can_stop_but_counter_only_cannot(self):
        self.scope['current']['revised400']['passed'] = 400
        self.assertEqual(self.invoke().get('decision'), 'block')
        for row in self.queue['cases']:
            row['revised_result'] = 'PASS'
        self.assertEqual(self.invoke().get('decision'), 'block')
        self.scope['current']['revised400']['target400_complete'] = True
        self.scope['current']['delivery_checks'] = {'status': 'closed'}
        self.queue['acceptance_summary'] = {'target400_complete': True}
        self.assertNotIn('decision', self.invoke())

    def test_all_cases_passed_does_not_skip_pending_delivery(self):
        self.scope['current']['revised400'].update(passed=400, target400_complete=True)
        self.queue['acceptance_summary'] = {'target400_complete': True}
        for row in self.queue['cases']:
            row['revised_result'] = 'PASS'
        self.scope['current']['delivery_checks'] = {'status': 'pending CI'}
        self.assertEqual(self.invoke().get('decision'), 'block')
        self.scope['current']['delivery_checks'] = {
            'status': 'closed candidate; final acceptance pending'}
        self.assertEqual(self.invoke().get('decision'), 'block')
        self.scope['current']['delivery_checks'] = {'status': 'closed'}
        self.scope['current']['running_original_or_full_python_jobs'] = ['ci-in-progress']
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_one_blocked_case_does_not_hide_other_ready_actions(self):
        unresolved = [r for r in self.queue['cases'] if r['revised_result'] != 'PASS']
        unresolved[0]['continuation_block'] = {'kind': 'external_dependency',
                                              'evidence': 'receipt.json'}
        (self.root / 'receipt.json').write_text('{"external_dependency":"license"}')
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_missing_action_is_a_state_error_not_permission_to_stop(self):
        for row in self.queue['cases']:
            if row['revised_result'] != 'PASS':
                row['next_action'] = ''
        decision = self.invoke()
        self.assertEqual(decision.get('decision'), 'block')
        self.assertIn('next_action', decision['reason'])

    def test_invalid_queue_is_not_silently_treated_as_complete(self):
        self.queue['cases'].pop()
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_only_all_externally_blocked_cases_allow_waiting(self):
        self.scope['current']['continuation'] = {'status': 'waiting'}
        for row in self.queue['cases']:
            if row['revised_result'] == 'PASS':
                continue
            receipt = self.root / (row['case_id'] + '.json')
            receipt.write_text(json.dumps({'case_id': row['case_id'],
                                           'blocker_kind': 'external_dependency',
                                           'next_check': 'external license restored'}))
            row['continuation_block'] = {'kind': 'external_dependency', 'evidence': {
                'path': receipt.name, 'sha256': hashlib.sha256(receipt.read_bytes()).hexdigest()}}
        self.assertNotIn('decision', self.invoke())
        (self.root / '019.json').write_text('{}')
        self.assertEqual(self.invoke().get('decision'), 'block')

    def test_generated_native_hook_runs_the_checker_not_an_advisory_stub(self):
        self.invoke()
        path = self.root / 'scope.json'
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--scope', str(path),
                              '--session-id', self.session, '--print-hook-config'],
                             capture_output=True, text=True, check=True, timeout=5)
        handler = json.loads(run.stdout)['hooks']['Stop'][0]['hooks'][0]
        self.assertEqual(handler['type'], 'command')
        result = subprocess.run(handler['command'], shell=True, cwd=self.root,
                                input=json.dumps(self.event), text=True,
                                capture_output=True, timeout=5, check=True)
        self.assertEqual(json.loads(result.stdout).get('decision'), 'block')

    def test_broken_bound_state_returns_a_native_block_instead_of_a_hook_error(self):
        self.invoke()
        path = self.root / 'scope.json'
        path.write_text('{')
        run = subprocess.run([sys.executable, '-B', str(SCRIPT), '--scope', str(path),
                              '--session-id', self.session], input=json.dumps(self.event),
                             capture_output=True, text=True, timeout=5)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout).get('decision'), 'block')


if __name__ == '__main__':
    unittest.main()

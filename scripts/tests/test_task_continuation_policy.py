"""Policy-level contracts; these tests do not establish native host coverage."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / 'task_continuation_policy.py'


class RuntimePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = self.root / 'scope.json'
        self.scope.write_text(json.dumps({'current': {
            'remaining_closure_ledger': 'cases.json',
            'continuation': {'status': 'active', 'runtime': {
                'schema_version': 1, 'path': 'runtime.json'}}}}))
        (self.root / 'cases.json').write_text(json.dumps({'cases': [
            {'case_id': '019', 'revised_result': 'REJECTED'}, {'case_id': '020'}]}))
        spec = importlib.util.spec_from_file_location('continuation_policy', SCRIPT)
        self.policy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.policy)

    def test_missing_historical_metering_does_not_grant_a_fresh_budget(self):
        before = self.scope.read_bytes()
        state = self.policy.initialize_runtime(
            self.scope, task_id='original-task', authority_ref='human-message')
        result = self.policy.evaluate(state, {'goal_complete': False, 'runnable': True})
        self.assertEqual(result['decision'], 'unknown')
        self.assertEqual(self.scope.read_bytes(), before)
        with self.assertRaises(self.policy.PolicyError):
            self.policy.update_runtime(self.scope, {
                'event_id': 'claim-1', 'operation': 'admit', 'task_id': 'original-task',
                'route_id': 'route-a', 'action_id': 'action-a', 'attempt_id': 'attempt-a',
                'actor': 'worker-a', 'case_ids': ['019'], 'ready': True,
                'input_digest': 'source-v1', 'allocation_s': 60,
                'plan': {'hypothesis': 'input stage', 'experiment': 'inspect fixed input',
                         'criterion': 'compare intermediate value'}})

    def fresh(self, **config):
        return self.policy.initialize_runtime(
            self.scope, task_id='task', authority_ref='human-message',
            prior_consumed_s=0, config=config)

    def admit(self, **changes):
        request = {'event_id': 'claim-1', 'operation': 'admit', 'task_id': 'task',
                   'route_id': 'route-a', 'action_id': 'action-a', 'attempt_id': 'attempt-a',
                   'actor': 'worker-a', 'case_ids': ['019'], 'ready': True,
                   'execution_id': 'host-job-a',
                   'purpose': 'exploration', 'input_digest': 'source-v1', 'allocation_s': 3600,
                   'plan': {'hypothesis': 'input stage', 'experiment': 'inspect fixed input',
                            'criterion': 'compare intermediate value'}}
        request.update(changes)
        return self.policy.update_runtime(self.scope, request)

    def test_admission_reserves_once_and_cannot_spend_closeout_or_pause(self):
        self.fresh(total_agent_s=4800)
        first = self.admit()
        self.assertEqual(first['decision'], 'admitted')
        self.assertFalse(first['replayed'])
        self.assertTrue(self.admit()['replayed'])
        duplicate = self.admit(event_id='same-action-new-event')
        self.assertEqual(duplicate['decision'], 'reconcile_required')
        with self.assertRaises(self.policy.PolicyError):
            self.admit(event_id='over-budget', route_id='route-b', action_id='action-b',
                       attempt_id='attempt-b', actor='worker-b', allocation_s=1)
        saved = json.loads(self.scope.read_text())
        saved['current']['continuation'].update(
            status='paused', user_pause={'message_ref': 'pause-message'})
        self.scope.write_text(json.dumps(saved))
        with self.assertRaises(self.policy.PolicyError):
            self.admit(event_id='during-pause', action_id='action-c', attempt_id='attempt-c')
        state = self.policy.read_runtime(self.scope)
        self.assertEqual(len(state['attempts']), 1)
        self.assertEqual(self.policy.evaluate(state, {
            'goal_complete': False, 'runnable': True, 'paused': True,
            'pause_ref': 'pause-message'})['decision'], 'paused')

    def receipt(self, name, **changes):
        receipt = {'kind': 'execution', 'task_id': 'task', 'route_id': 'route-a',
                   'action_id': 'action-a', 'attempt_id': 'attempt-a',
                   'input_digest': 'source-v1', 'execution_id': 'host-job-a',
                   'status': 'completed', 'observed_at_utc': '2026-01-01T00:20:00Z',
                   'deadline_utc': '2026-01-01T02:00:00Z',
                   'active_intervals': [['2026-01-01T00:00:00Z', '2026-01-01T00:20:00Z']],
                   'metering_complete': True}
        receipt.update(changes)
        path = self.root / name
        path.write_text(json.dumps(receipt))
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def reconcile(self, name='finished.json', **changes):
        return self.policy.update_runtime(self.scope, {
            'event_id': name, 'operation': 'reconcile', 'task_id': 'task',
            'receipt': self.receipt(name, **changes)})

    def test_recovery_keeps_unknown_reservation_and_collects_a_result_once(self):
        self.fresh()
        self.admit()
        self.reconcile('unknown.json', status='unknown', active_intervals=[],
                       metering_complete=False)
        unknown = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(unknown['decision'], 'unknown')
        self.assertEqual(unknown['budget']['reserved_s'], 3600)
        self.assertEqual(self.admit(event_id='recovery')['decision'], 'reconcile_required')
        first = self.reconcile()
        self.assertEqual(first['decision'], 'collected')
        self.assertTrue(self.reconcile()['replayed'])
        state = self.policy.read_runtime(self.scope)
        decision = self.policy.evaluate(state, {'goal_complete': False, 'runnable': True})
        self.assertEqual(decision['budget']['consumed_s'], 1200)
        self.assertEqual(decision['budget']['reserved_s'], 0)
        self.assertEqual(self.admit(event_id='late-recovery')['decision'], 'reconcile_required')
        with self.assertRaises(self.policy.PolicyError):
            self.reconcile('wrong-source.json', input_digest='different-source')

    def test_parallel_activity_uses_union_and_wait_does_not_reset_30_min_window(self):
        self.fresh()
        self.admit(allocation_s=1800)
        self.admit(event_id='claim-b', action_id='action-b', attempt_id='attempt-b',
                   actor='worker-b', execution_id='host-job-b', allocation_s=1800)
        self.reconcile('actor-a.json')
        self.reconcile('actor-b-wait.json', action_id='action-b', attempt_id='attempt-b',
                       execution_id='host-job-b', status='running',
                       observed_at_utc='2026-01-01T01:30:00Z')
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True}, now='2026-01-01T01:30:00Z')
        self.assertEqual(result['decision'], 'running')
        self.assertEqual(result['budget']['consumed_s'], 2400)
        self.assertEqual(result['routes']['route-a']['active_union_s'], 1200)
        self.reconcile('actor-b-done.json', action_id='action-b', attempt_id='attempt-b',
                       execution_id='host-job-b', observed_at_utc='2026-01-01T01:40:00Z',
                       active_intervals=[['2026-01-01T00:00:00Z', '2026-01-01T00:20:00Z'],
                                         ['2026-01-01T01:30:00Z', '2026-01-01T01:40:00Z']])
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['decision'], 'replan_required')
        self.assertEqual(result['budget']['consumed_s'], 3000)
        self.assertEqual(result['routes']['route-a']['observation_active_s'], 1800)
        with self.assertRaises(self.policy.PolicyError):
            self.admit(event_id='unchanged', action_id='action-c', attempt_id='attempt-c',
                       allocation_s=60)

    def test_verified_negative_progress_preserves_spend_and_requires_changed_plan(self):
        self.fresh()
        self.admit()
        self.reconcile()
        evidence = self.receipt('experiment-evidence.json')
        progress = self.receipt('progress.json', kind='progress', progress_id='fact-a',
                                category='exploration', at_utc='2026-01-01T00:20:00Z',
                                evidence=evidence, changes_decision='input hypothesis excluded',
                                premise_refuted=True, validator={
                                    'kind': 'independent_review', 'identity': 'reviewer',
                                    'author': 'worker-a', 'accepted': True})
        request = {'operation': 'progress', 'event_id': 'progress-a',
                   'task_id': 'task', 'receipt': progress}
        self.assertEqual(self.policy.update_runtime(self.scope, request)['decision'], 'progress_recorded')
        request['event_id'] = 'same-evidence-again'
        self.assertEqual(self.policy.update_runtime(self.scope, request)['decision'], 'duplicate_progress')
        state = self.policy.read_runtime(self.scope)
        result = self.policy.evaluate(state, {'goal_complete': False, 'runnable': True})
        self.assertEqual(result['decision'], 'replan_required')
        self.assertEqual(result['budget']['consumed_s'], 1200)
        old = state['routes']['route-a']['plan']
        plan = dict(old, hypothesis='calculation stage', experiment='inspect fixed intermediate state')
        review = self.receipt('replan.json', kind='replan',
                              previous_plan_digest=self.policy.plan_digest(old),
                              new_plan_digest=self.policy.plan_digest(plan),
                              trigger='premise_refuted', addresses_trigger='check remaining stage',
                              next_check='compare intermediate state', validator={
                                  'kind': 'independent_review', 'identity': 'reviewer',
                                  'author': 'worker-a', 'accepted': True})
        self.policy.update_runtime(self.scope, {
            'operation': 'replan', 'event_id': 'plan-b', 'task_id': 'task',
            'route_id': 'route-a', 'author': 'worker-a', 'plan': plan, 'receipt': review})
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['decision'], 'continue')
        self.assertEqual(result['budget']['consumed_s'], 1200)
        self.assertEqual(result['routes']['route-a']['active_union_s'], 1200)

    def test_running_route_does_not_stop_independent_ready_work(self):
        self.fresh()
        self.admit()
        self.reconcile('running.json', status='running')
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True, 'runnable_route_ids': ['route-a', 'route-b']},
            now='2026-01-01T00:21:00Z')
        self.assertEqual(result['decision'], 'continue')
        only_active = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True, 'runnable_route_ids': ['route-a']},
            now='2026-01-01T00:21:00Z')
        self.assertEqual(only_active['decision'], 'running')

    def test_concurrent_admission_cannot_allocate_the_same_remaining_budget_twice(self):
        self.fresh(total_agent_s=4800)
        worker = '''
import importlib.util, json, sys
spec=importlib.util.spec_from_file_location('policy',sys.argv[1])
policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
try:
    result=policy.update_runtime(sys.argv[2],json.loads(sys.argv[3]))
    print(result['decision'])
except policy.PolicyError:
    print('denied')
'''
        processes = []
        for suffix in ('a', 'b'):
            request = {'event_id': 'claim-' + suffix, 'operation': 'admit', 'task_id': 'task',
                       'route_id': 'route-' + suffix, 'action_id': 'action-' + suffix,
                       'attempt_id': 'attempt-' + suffix, 'actor': 'worker-' + suffix,
                       'case_ids': ['019' if suffix == 'a' else '020'],
                       'ready': True, 'input_digest': 'source-v1',
                       'allocation_s': 2700, 'plan': {'hypothesis': 'stage-' + suffix,
                       'experiment': 'fixed experiment-' + suffix, 'criterion': 'fixed value'}}
            processes.append(subprocess.Popen(
                [sys.executable, '-B', '-c', worker, str(SCRIPT), str(self.scope), json.dumps(request)],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stderr)
            outputs.append(stdout.strip())
        self.assertEqual(sorted(outputs), ['admitted', 'denied'])
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['budget']['reserved_s'], 2700)
        self.assertEqual(result['budget']['available_s'], 900)

    def test_budget_exhaustion_allows_closeout_instead_of_a_replan_loop(self):
        self.fresh(total_agent_s=2400)
        self.admit(allocation_s=1800)
        self.reconcile(observed_at_utc='2026-01-01T00:30:00Z', active_intervals=[
            ['2026-01-01T00:00:00Z', '2026-01-01T00:30:00Z']])
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['decision'], 'budget_exhausted')
        self.admit(event_id='closeout', route_id='closeout', action_id='closeout',
                   attempt_id='closeout', allocation_s=600, purpose='closeout', plan={
                       'hypothesis': 'delivery receipts remain to collect',
                       'experiment': 'collect existing delivery receipts',
                       'criterion': 'all existing deliveries accounted for'})

    def test_default_60_min_route_has_one_30_min_renewal_without_refunding_spend(self):
        self.fresh(stagnation_s=10000)
        self.admit()
        self.reconcile(observed_at_utc='2026-01-01T01:00:00Z', active_intervals=[
            ['2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z']])
        state = self.policy.read_runtime(self.scope)
        plan = state['routes']['route-a']['plan']
        self.assertEqual(self.policy.evaluate(state, {
            'goal_complete': False, 'runnable': True})['decision'], 'replan_required')
        def renew(event):
            review = self.receipt(event + '.json', kind='replan',
                previous_plan_digest=self.policy.plan_digest(plan),
                new_plan_digest=self.policy.plan_digest(plan), trigger='exploration_exhausted',
                addresses_trigger='evidence supports one bounded follow-up', next_check='fixed check',
                validator={'kind': 'independent_review', 'identity': 'reviewer',
                           'author': 'worker-a', 'accepted': True})
            return self.policy.update_runtime(self.scope, {
                'operation': 'replan', 'event_id': event, 'task_id': 'task', 'route_id': 'route-a',
                'author': 'worker-a', 'plan': plan, 'receipt': review, 'renewal_s': 1800})
        renew('renew-once')
        self.admit(event_id='claim-followup', action_id='followup', attempt_id='followup',
                   allocation_s=1800)
        self.reconcile('followup-done.json', action_id='followup', attempt_id='followup',
            observed_at_utc='2026-01-01T01:30:00Z', active_intervals=[
                ['2026-01-01T01:00:00Z', '2026-01-01T01:30:00Z']])
        with self.assertRaises(self.policy.PolicyError):
            renew('second-renewal')
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['budget']['consumed_s'], 5400)
        self.assertEqual(result['routes']['route-a']['exploration_limit_s'], 5400)

    def test_route_alias_and_expired_authority_do_not_grant_execution(self):
        self.fresh()
        self.admit()
        self.reconcile()
        with self.assertRaises(self.policy.PolicyError):
            self.admit(event_id='renamed-route', route_id='renamed-route', action_id='other-action',
                       attempt_id='other-attempt', actor='new-actor', allocation_s=60)
        before = self.policy.read_runtime(self.scope)
        with self.assertRaises(self.policy.PolicyError):
            self.admit(allocation_s=1)
        self.assertEqual(self.policy.read_runtime(self.scope), before)
        saved = json.loads(self.scope.read_text())
        saved['current']['continuation']['deadline_utc'] = '2000-01-01T00:00:00Z'
        self.scope.write_text(json.dumps(saved))
        with self.assertRaises(self.policy.PolicyError):
            self.admit(event_id='past-deadline', action_id='next-action',
                       attempt_id='next-attempt', allocation_s=60)

    def test_corrupt_runtime_is_rejected_instead_of_becoming_available_credit(self):
        self.fresh()
        path = self.root / 'runtime.json'
        state = json.loads(path.read_text())
        state['prior_consumed_s'] = -1
        path.write_text(json.dumps(state))
        with self.assertRaises(self.policy.PolicyError):
            self.policy.read_runtime(self.scope)
        with self.assertRaises(self.policy.PolicyError):
            self.admit()

    def test_replan_rejects_self_review_and_renamed_unchanged_experiment(self):
        self.fresh()
        self.admit()
        self.reconcile(observed_at_utc='2026-01-01T00:30:00Z', active_intervals=[
            ['2026-01-01T00:00:00Z', '2026-01-01T00:30:00Z']])
        state = self.policy.read_runtime(self.scope)
        old = state['routes']['route-a']['plan']
        for reviewer, plan in (
                ('worker-a', dict(old, experiment='different experiment')),
                ('reviewer', dict(old, hypothesis='renamed hypothesis'))):
            review = self.receipt(reviewer + '.json', kind='replan',
                previous_plan_digest=self.policy.plan_digest(old),
                new_plan_digest=self.policy.plan_digest(plan), trigger='stagnation',
                addresses_trigger='claimed fix', next_check='claimed check',
                validator={'kind': 'independent_review', 'identity': reviewer,
                           'author': 'worker-a', 'accepted': True})
            with self.assertRaises(self.policy.PolicyError):
                self.policy.update_runtime(self.scope, {
                    'operation': 'replan', 'event_id': reviewer, 'task_id': 'task',
                    'route_id': 'route-a', 'author': 'worker-a', 'plan': plan, 'receipt': review})
        self.assertEqual(self.policy.read_runtime(self.scope), state)

    def test_settled_result_cannot_be_downgraded_by_a_late_notification(self):
        self.fresh()
        self.admit()
        self.reconcile()
        before = self.policy.read_runtime(self.scope)
        with self.assertRaises(self.policy.PolicyError):
            self.reconcile('late-notification.json', metering_complete=False)
        self.assertEqual(self.policy.read_runtime(self.scope), before)

    def test_overlapping_same_actor_attempts_count_once_for_budget_and_route_limit(self):
        self.fresh()
        self.admit(allocation_s=1800)
        self.admit(event_id='claim-b', action_id='action-b', attempt_id='attempt-b',
                   allocation_s=1800)
        self.reconcile('done-a.json')
        self.reconcile('done-b.json', action_id='action-b', attempt_id='attempt-b')
        result = self.policy.evaluate(self.policy.read_runtime(self.scope), {
            'goal_complete': False, 'runnable': True})
        self.assertEqual(result['budget']['consumed_s'], 1200)
        self.assertEqual(result['routes']['route-a']['exploration_consumed_s'], 1200)
        self.admit(event_id='remaining-route-budget', action_id='action-c', attempt_id='attempt-c',
                   allocation_s=2400)

    def test_stalled_case_keeps_its_route_when_descriptions_source_or_case_groups_change(self):
        self.fresh()
        self.admit(case_ids=['019', '020'], allocation_s=1800)
        self.reconcile(observed_at_utc='2026-01-01T00:30:00Z', active_intervals=[
            ['2026-01-01T00:00:00Z', '2026-01-01T00:30:00Z']])
        before = self.policy.read_runtime(self.scope)
        plan = before['routes']['route-a']['plan']
        variants = [
            {'plan': dict(plan, hypothesis='renamed hypothesis')},
            {'plan': dict(plan, experiment='rewritten experiment description')},
            {'input_digest': 'source-v2'},
            {'case_ids': ['020'], 'actor': 'different-worker'},
            {'purpose': 'closeout', 'plan': dict(plan, hypothesis='renamed as closeout')}]
        for index, changes in enumerate(variants):
            with self.subTest(changes=changes), self.assertRaises(self.policy.PolicyError):
                self.admit(event_id=f'alias-{index}', route_id=f'alias-{index}',
                           action_id=f'alias-{index}', attempt_id=f'alias-{index}',
                           allocation_s=60, **changes)
        after = self.policy.read_runtime(self.scope)
        self.assertEqual(after, before)
        status = self.policy.evaluate(after, {'goal_complete': False, 'runnable': True})
        self.assertEqual(status['decision'], 'replan_required')
        self.assertEqual(status['budget']['consumed_s'], 1800)
        self.assertEqual(status['routes']['route-a']['observation_active_s'], 1800)

    def test_reclassifying_same_evidence_does_not_refresh_its_observed_progress(self):
        self.fresh()
        self.admit()
        self.reconcile()
        evidence = self.receipt('fixed-evidence.json')
        validator = {'kind': 'project_check', 'identity': 'deterministic-checker',
                     'author': 'worker-a', 'accepted': True}
        first = self.receipt('exploration-progress.json', kind='progress', progress_id='fact-a',
            category='exploration', at_utc='2026-01-01T00:20:00Z', evidence=evidence,
            changes_decision='fixed evidence determines next test', validator=validator)
        self.policy.update_runtime(self.scope, {'operation': 'progress', 'event_id': 'fact-a',
                                               'task_id': 'task', 'receipt': first})
        self.admit(event_id='followup', action_id='followup', attempt_id='followup', allocation_s=1800)
        self.reconcile('followup-result.json', action_id='followup', attempt_id='followup',
            observed_at_utc='2026-01-01T00:50:00Z', active_intervals=[
                ['2026-01-01T00:20:00Z', '2026-01-01T00:50:00Z']])
        before = self.policy.read_runtime(self.scope)
        self.assertEqual(self.policy.evaluate(before, {'goal_complete': False,
            'runnable': True})['decision'], 'replan_required')
        repeated = self.receipt('acceptance-progress.json', kind='progress', progress_id='fact-b',
            action_id='followup', attempt_id='followup', category='acceptance',
            at_utc='2026-01-01T00:50:00Z', evidence=evidence,
            changes_decision='same bytes under a different label', validator=validator)
        result = self.policy.update_runtime(self.scope, {'operation': 'progress', 'event_id': 'fact-b',
                                                        'task_id': 'task', 'receipt': repeated})
        self.assertEqual(result['decision'], 'duplicate_progress')
        after = self.policy.read_runtime(self.scope)
        self.assertEqual(after['routes'], before['routes'])
        status = self.policy.evaluate(after, {'goal_complete': False, 'runnable': True})
        self.assertEqual(status['decision'], 'replan_required')
        self.assertEqual(status['routes']['route-a']['observation_active_s'], 1800)

    def test_existing_progress_record_without_new_identity_metadata_still_deduplicates(self):
        self.fresh()
        self.admit()
        self.reconcile()
        evidence = self.receipt('fixed-legacy-evidence.json')
        validator = {'kind': 'project_check', 'identity': 'deterministic-checker',
                     'author': 'worker-a', 'accepted': True}
        first = self.receipt('old-progress.json', kind='progress', progress_id='old-fact',
            category='exploration', at_utc='2026-01-01T00:10:00Z', evidence=evidence,
            changes_decision='fixed earlier observation', validator=validator)
        self.policy.update_runtime(self.scope, {'operation': 'progress', 'event_id': 'old-fact',
                                               'task_id': 'task', 'receipt': first})
        state = self.policy.read_runtime(self.scope)
        # Prior record shape retained receipt and progress_id under an opaque key.
        state['progress'] = {'previous-category-dependent-key': {
            'receipt': first, 'progress_id': 'old-fact'}}
        (self.root / 'runtime.json').write_text(json.dumps(state))
        later = self.receipt('new-category.json', kind='progress', progress_id='new-label',
            category='acceptance', at_utc='2026-01-01T00:20:00Z', evidence=evidence,
            changes_decision='same earlier observation', validator=validator)
        result = self.policy.update_runtime(self.scope, {'operation': 'progress', 'event_id': 'new-label',
                                                        'task_id': 'task', 'receipt': later})
        self.assertEqual(result['decision'], 'duplicate_progress')
        self.assertEqual(self.policy.read_runtime(self.scope)['routes'], state['routes'])


if __name__ == '__main__':
    unittest.main()

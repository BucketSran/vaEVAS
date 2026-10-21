"""Historical zero-gain replay and incremental review result contracts."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import unittest

import test_task_continuation_policy as base


class CheckpointTests(unittest.TestCase):
    setUp = base.RuntimePolicyTests.setUp
    fresh = base.RuntimePolicyTests.fresh
    activate_bounded = base.RuntimePolicyTests.activate_bounded
    bounded_admit = base.RuntimePolicyTests.bounded_admit
    bounded_finish = base.RuntimePolicyTests.bounded_finish
    admit = base.RuntimePolicyTests.admit
    receipt = base.RuntimePolicyTests.receipt
    reconcile = base.RuntimePolicyTests.reconcile

    def prepare(self, **config):
        self.fresh(**config)
        self.activate_bounded()
        self.bounded_admit()
        self.bounded_finish()

    def checkpoint(self, name='checkpoint', **changes):
        fixture = Path(__file__).parent / 'fixtures/continuation-wave26-zero-gain.json'
        history = json.loads(fixture.read_text())
        state = self.policy.read_runtime(self.scope)
        values = dict(kind='goal_checkpoint', comparison_id='wave26', metric='revised400',
            plan_digest=state['routes']['route-a']['plan_digest'],
            assessment={'before': history['retention']['prior_pass_count'],
                'after': history['summary']['checker_passed'], 'target': 400,
                'expected_min_gain': 1, 'complete': True, 'comparable': True, 'checkpoint_due': True},
            evidence={'path': str(fixture), 'sha256': hashlib.sha256(fixture.read_bytes()).hexdigest()},
            validator={'kind': 'project_check', 'identity': 'frozen-comparison',
                       'author': 'worker-a', 'accepted': True})
        values.update(changes)
        ref = self.receipt(name+'.json', **values)
        return self.policy.update_runtime(self.scope, {'operation': 'goal_checkpoint',
            'event_id': name, 'task_id': 'task', 'receipt': ref})

    def test_green_checks_do_not_advance_observation_or_remove_zero_gain_replan(self):
        self.prepare(stagnation_s=20)
        state = self.policy.read_runtime(self.scope)
        before = self.policy.evaluate(state, {'goal_complete': False, 'runnable': True})
        evidence = self.receipt('green-tests.json')
        for category in ('acceptance', 'verification'):
            ref = self.receipt(category+'.json', kind='progress', progress_id=category,
                category=category, at_utc=datetime.fromtimestamp(
                    state['attempts']['attempt-a']['observed_at_s'], timezone.utc).isoformat(), evidence=evidence,
                changes_decision='CI is green', validator={'kind': 'project_check',
                    'identity': 'ci', 'author': 'worker-a', 'accepted': True})
            self.policy.update_runtime(self.scope, {'operation': 'progress', 'event_id': category,
                                                    'task_id': 'task', 'receipt': ref})
            observed = self.policy.evaluate(self.policy.read_runtime(self.scope),
                                             {'goal_complete': False, 'runnable': True})
            self.assertEqual(observed['routes'], before['routes'])
        after = self.policy.evaluate(self.policy.read_runtime(self.scope),
                                     {'goal_complete': False, 'runnable': True})
        self.assertEqual(after['routes'], before['routes'])
        self.assertEqual(after['decision'], 'replan_required')
        self.assertEqual(self.checkpoint()['net_gain'], 0)
        self.assertEqual(self.policy.read_runtime(self.scope)['routes']['route-a']['required_reason'],
                         'goal_no_growth')

    def test_historical_317_400_checkpoint_blocks_repeat_preserves_queue_and_budget(self):
        self.prepare()
        files = {p: p.read_bytes() for p in (self.scope, self.root/'cases.json')}
        history = json.loads((Path(__file__).parent/'fixtures/continuation-wave26-zero-gain.json').read_text())
        self.assertTrue(history['ci']['all_jobs_success'])
        self.assertEqual(history['ci']['jobs'], 15)
        self.assertEqual(history['retention']['prior_pass_count'], 317)
        self.assertEqual(history['summary']['remaining_to400'], 83)
        self.assertEqual(set(history['retention']['prior_pass_ids']), set(history['summary']['pass_ids']))
        self.assertEqual(self.checkpoint()['decision'], 'replan_required')
        with self.assertRaisesRegex(self.policy.PolicyError, 'replan'):
            self.bounded_admit(event_id='repeat', action_id='repeat', attempt_id='repeat')
        state = self.policy.read_runtime(self.scope)
        self.assertEqual(state['attempts']['attempt-a']['consumed_s'], 20)
        self.assertEqual(self.checkpoint(name='duplicate')['decision'], 'duplicate_goal_checkpoint')
        for path, raw in files.items():
            self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(self.policy.evaluate(state, {'goal_complete': False,
                         'runnable': True})['decision'], 'replan_required')
        # Existing independent queue work continues through the same admission.
        self.bounded_admit(event_id='independent', action_id='independent', attempt_id='independent',
                           route_id='route-b', case_ids=['020'])
        self.assertEqual(len(self.policy.read_runtime(self.scope)['attempts']), 2)

    def test_partial_waiting_or_real_gain_does_not_trigger_goal_stagnation(self):
        self.prepare()
        facts = {'before':317, 'after':317, 'target':400, 'expected_min_gain':1,
                 'complete':True, 'comparable':True, 'checkpoint_due':True}
        for field in ('complete', 'comparable', 'checkpoint_due'):
            result = self.checkpoint(name=field, comparison_id=field,
                                     assessment=dict(facts, **{field:False}))
            self.assertIsNone(result['net_gain'])
            self.assertEqual(result['decision'], 'goal_checkpoint_recorded')
        result = self.checkpoint(name='gain', comparison_id='gain', assessment=dict(facts, after=318))
        self.assertEqual(result['net_gain'], 1)
        self.assertIsNone(self.policy.read_runtime(self.scope)['routes']['route-a']['required_reason'])

    def test_zero_gain_requires_changed_reviewed_plan_without_budget_reset(self):
        self.prepare()
        self.checkpoint()
        state = self.policy.read_runtime(self.scope)
        old = state['routes']['route-a']['plan']
        plan = dict(old, experiment='run original full-case consumer before another broad batch')
        for label, chosen in (('rename', dict(old, hypothesis='new name')), ('changed', plan)):
            ref = self.receipt(label+'.json', kind='replan',
                previous_plan_digest=self.policy.plan_digest(old), new_plan_digest=self.policy.plan_digest(chosen),
                trigger='goal_no_growth', addresses_trigger='original consumer checks actual score gain',
                next_check='frozen full-case result', validator={'kind':'independent_review',
                    'identity':'reviewer', 'author':'worker-a', 'accepted':True})
            request = {'operation':'replan', 'event_id':label, 'task_id':'task', 'route_id':'route-a',
                       'author':'worker-a', 'plan':chosen, 'receipt':ref}
            if label == 'rename':
                with self.assertRaises(self.policy.PolicyError):
                    self.policy.update_runtime(self.scope, request)
            else:
                self.assertEqual(self.policy.update_runtime(self.scope, request)['decision'], 'replanned')
        self.assertEqual(self.checkpoint(name='old-replay')['decision'], 'duplicate_goal_checkpoint')
        self.assertEqual(self.policy.read_runtime(self.scope)['attempts']['attempt-a']['consumed_s'], 20)
        self.bounded_admit(event_id='new-plan', action_id='next', attempt_id='next', plan=plan)

    def review(self, name, contract, findings, **execution):
        key = self.policy.review_key(contract)
        self.bounded_admit(event_id=name, action_id=name, attempt_id=name,
                           input_digest=key, execution_id=name)
        self.bounded_finish(name+'-execution.json', attempt_id=name, input_digest=key,
                            execution='ok', returncode=0, **execution)
        output = self.root/(name+'-output.json')
        output.write_text(json.dumps({'review_key':key, 'reviewer':'worker-a', 'findings':findings}))
        ref = self.receipt(name+'-review.json', kind='review', action_id=name, attempt_id=name,
            input_digest=key, contract=contract, outcome='completed',
            result={'path':str(output), 'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
        return self.policy.update_runtime(self.scope, {'operation':'review', 'event_id':name+'-collect',
                                                       'task_id':'task', 'receipt':ref})

    def contract(self, text='original'):
        path = self.root/(text+'.txt')
        path.write_text(text)
        return {'unit_id':'module', 'axis':'spec', 'author':'implementer',
                'inputs':[{'path':str(path), 'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}

    def test_review_reuses_only_exact_inputs_and_preserves_open_findings(self):
        self.fresh()
        self.activate_bounded(total_command_s=240)
        old = self.contract()
        finding = {'id':'SPEC-1', 'status':'open', 'detail':'missing direct consumer', 'evidence':old['inputs'][0]}
        self.assertEqual(self.review('r1',old,[finding])['status'], 'changes_requested')
        self.assertEqual(self.policy.review_reuse(self.scope,old)['status'], 'changes_requested')
        changed = dict(self.contract('changed'), previous_review='r1')
        self.assertIsNone(self.policy.review_reuse(self.scope,changed))
        self.assertEqual(self.review('r2',changed,[])['status'], 'incomplete')
        self.assertEqual(self.review('r3',changed,[dict(finding,status='resolved',
                              evidence=changed['inputs'][0])])['status'], 'approved')
        self.assertEqual(self.policy.review_reuse(self.scope,changed)['status'], 'approved')
        Path(changed['inputs'][0]['path']).write_text('mutated dependency')
        self.assertIsNone(self.policy.review_reuse(self.scope,changed))

    def test_stale_parallel_review_cannot_drop_new_finding(self):
        self.fresh()
        self.activate_bounded(total_command_s=240)
        contract = self.contract()
        self.review('r1',contract,[{'id':'new-finding', 'status':'open', 'detail':'actual flaw',
                                   'evidence':contract['inputs'][0]}])
        self.assertEqual(self.review('stale',contract,[])['status'], 'incomplete')
        unit = next(iter(self.policy.read_runtime(self.scope)['review_units'].values()))
        self.assertIn('new-finding', unit['open_findings'])

    def test_renaming_evidence_does_not_close_a_finding(self):
        self.fresh()
        self.activate_bounded(total_command_s=240)
        contract = self.contract()
        finding = {'id':'SPEC-1', 'status':'open', 'detail':'missing consumer',
                   'evidence':contract['inputs'][0]}
        self.review('r1', contract, [finding])
        path = self.root/'renamed.txt'
        path.write_bytes(Path(finding['evidence']['path']).read_bytes())
        evidence = dict(finding['evidence'], path=str(path))
        changed = dict(contract, inputs=[evidence], previous_review='r1')
        self.assertEqual(self.review('renamed', changed,
            [dict(finding, status='resolved', evidence=evidence)])['status'], 'incomplete')

    def test_real_gain_recovers_legacy_null_progress_without_resetting_budget(self):
        self.prepare()
        state = self.policy.read_runtime(self.scope)
        state['routes']['route-a']['progress_at_s'] = None
        (self.root/'runtime.json').write_text(json.dumps(state))
        result = self.checkpoint(assessment={'before':317, 'after':318, 'target':400,
            'expected_min_gain':1, 'complete':True, 'comparable':True, 'checkpoint_due':True})
        self.assertEqual(result['net_gain'], 1)
        self.assertEqual(self.policy.read_runtime(self.scope)['attempts']['attempt-a']['consumed_s'], 20)


if __name__ == '__main__':
    unittest.main()

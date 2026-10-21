"""Real review commands reuse the maintained execution and budget boundaries."""
import hashlib
import json
import sys
import unittest

import test_task_continuation_execution as execution_tests


policy = execution_tests.policy


@unittest.skipUnless(execution_tests.HAS_HARNESS, 'external Harness unavailable; no fallback runner')
class ReviewExecutionTests(unittest.TestCase):
    activate_command_mode = execution_tests.ExecutionAdapterTests.activate_command_mode

    def setUp(self):
        execution_tests.ExecutionAdapterTests.setUp(self)
        self.activate_command_mode()
        self.input = self.root / 'frozen-review-input.txt'
        self.input.write_text('fixed diff and validation evidence\n')
        self.contract = {'unit_id': 'unit-019', 'axis': 'correctness', 'author': 'author-019',
                         'inputs': [{'path': str(self.input),
                                     'sha256': hashlib.sha256(self.input.read_bytes()).hexdigest()}]}
        self.admission.update(input_digest=policy.review_key(self.contract), allocation_s=8)
        self.result_path = self.root / 'review-result.json'
        worker = self.root / 'review-worker.py'
        worker.write_text(
            'import json,sys,time\n'
            'from pathlib import Path\n'
            'marker,result,key,reviewer,mode,input_path=sys.argv[1:]\n'
            'with Path(marker).open("a") as stream: stream.write("started\\n")\n'
            'if mode != "missing":\n'
            '    Path(result).write_text(json.dumps({"review_key":key,\n'
            '        "reviewer":reviewer,"findings":[],"status":"approved"}))\n'
            'if mode == "malformed": Path(result).write_text("{")\n'
            'if mode == "mutate": Path(input_path).write_text("changed input\\n")\n'
            'if mode == "timeout": time.sleep(60)\n')
        self.argv = [sys.executable, '-B', str(worker), str(self.marker),
                     str(self.result_path), self.admission['input_digest'],
                     self.admission['actor'], 'success', str(self.input)]

    def run_review(self, **changes):
        arguments = dict(review_contract=self.contract, directory=self.root / 'command',
                         result_path=self.result_path, cwd=self.root, timeout_s=2,
                         harness_root=execution_tests.HARNESS)
        arguments.update(changes)
        return self.execution.execute_review(self.scope, self.admission, self.argv, **arguments)

    def test_success_and_replay_dispatch_once_and_keep_one_charge(self):
        first = self.run_review()
        self.assertEqual(first['status'], 'approved', first)
        self.assertTrue(first['started'])
        replay = self.run_review()
        self.assertEqual(replay['status'], 'approved', replay)
        self.assertFalse(replay['started'])
        self.assertNotEqual(replay['decision'], 'review_reused')
        self.assertTrue(replay['execution']['cleanup_confirmed'])
        self.assertEqual(self.marker.read_text(), 'started\n')
        state = policy.read_runtime(self.scope)
        self.assertEqual(len(state['attempts']), 1)
        self.assertEqual(state['attempts']['attempt-019']['consumed_s'], 8)

    def next_action(self, suffix):
        self.admission = dict(self.admission, event_id='admit:' + suffix,
                              action_id='action-' + suffix, attempt_id='attempt-' + suffix,
                              execution_id='execution-' + suffix)

    def test_cached_new_action_dispatches_nothing_and_consumes_no_new_allocation(self):
        self.assertEqual(self.run_review()['status'], 'approved')
        before = policy.read_runtime(self.scope)
        self.next_action('cached')
        cached = self.run_review(directory=self.root / 'cached-command',
                                 result_path=self.root / 'unused-result.json')
        self.assertEqual(cached['decision'], 'review_reused', cached)
        self.assertEqual(cached['status'], 'approved')
        self.assertFalse(cached['started'])
        self.assertEqual(policy.read_runtime(self.scope), before)
        self.assertEqual(self.marker.read_text(), 'started\n')

    def test_approved_recovery_rechecks_input_and_result_without_redispatch(self):
        self.assertEqual(self.run_review()['status'], 'approved')
        before = policy.read_runtime(self.scope)
        for path in (self.input, self.result_path):
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_text('changed after completed review')
                recovered = self.run_review()
                self.assertEqual(recovered['status'], 'incomplete')
                self.assertEqual(recovered['historical_status'], 'approved')
                self.assertFalse(recovered['started'])
                self.assertIsNone(policy.review_reuse(self.scope, self.contract))
                self.assertEqual(policy.read_runtime(self.scope), before)
                self.assertEqual(self.marker.read_text(), 'started\n')
                path.write_bytes(original)
        self.assertEqual(self.run_review()['status'], 'approved')

    def test_timeout_with_prewritten_approval_stays_timed_out_and_keeps_charge(self):
        self.argv[-2] = 'timeout'
        first = self.run_review(timeout_s=.2)
        self.assertEqual(first['status'], 'timed_out', first)
        self.assertEqual(first['execution']['execution'], 'timeout')
        self.assertTrue(first['execution']['cleanup_confirmed'])
        self.assertEqual(json.loads(self.result_path.read_text())['status'], 'approved')
        self.result_path.write_text(json.dumps({'review_key': self.admission['input_digest'],
            'reviewer': self.admission['actor'], 'findings': []}))
        replay = self.run_review(timeout_s=.2)
        self.assertEqual(replay['status'], 'timed_out', replay)
        self.assertEqual(self.marker.read_text(), 'started\n')
        self.assertEqual(policy.read_runtime(self.scope)['attempts']['attempt-019']['consumed_s'], 8)
        self.assertIsNone(policy.review_reuse(self.scope, self.contract))

    def test_missing_result_is_incomplete_and_new_action_uses_the_original_budget(self):
        self.argv[-2] = 'missing'
        first = self.run_review()
        self.assertEqual(first['status'], 'incomplete', first)
        self.assertFalse(self.result_path.exists())
        # A late result never promotes this settled execution to approval.
        self.result_path.write_text(json.dumps({'review_key': self.admission['input_digest'],
            'reviewer': self.admission['actor'], 'findings': []}))
        self.assertEqual(self.run_review()['status'], 'incomplete')
        self.next_action('retry')
        retry_output = self.root / 'retry-result.json'
        self.argv[4], self.argv[-2] = str(retry_output), 'success'
        retry = self.run_review(directory=self.root / 'retry-command', result_path=retry_output)
        self.assertEqual(retry['status'], 'approved', retry)
        self.assertEqual(self.marker.read_text(), 'started\nstarted\n')
        state = policy.read_runtime(self.scope)
        self.assertEqual(sum(a['consumed_s'] for a in state['attempts'].values()), 16)
        self.assertEqual(state['accounting']['total_command_s'], 120)

    def test_changed_input_during_command_is_incomplete_even_after_bytes_are_restored(self):
        self.argv[-2] = 'mutate'
        first = self.run_review()
        self.assertEqual(first['status'], 'incomplete', first)
        self.assertEqual(first['execution']['status'], 'completed')
        self.input.write_text('fixed diff and validation evidence\n')
        self.assertEqual(self.run_review()['status'], 'incomplete')
        self.assertEqual(self.marker.read_text(), 'started\n')

    def test_malformed_json_result_is_recorded_as_incomplete(self):
        self.argv[-2] = 'malformed'
        result = self.run_review()
        self.assertEqual(result['status'], 'incomplete', result)
        self.assertTrue(result['settled'])
        self.assertEqual(policy.read_runtime(self.scope)['attempts']['attempt-019']['consumed_s'], 8)

    def test_same_action_rejects_changed_contract_output_and_command(self):
        self.assertEqual(self.run_review()['status'], 'approved')
        original = self.admission
        changed = dict(self.contract, axis='standards')
        self.admission = dict(original, input_digest=policy.review_key(changed))
        with self.assertRaisesRegex(ValueError, 'contract or output'):
            self.run_review(review_contract=changed)
        self.admission = original
        with self.assertRaisesRegex(ValueError, 'contract or output'):
            self.run_review(result_path=self.root / 'different-result.json')
        self.argv.append('changed argument')
        with self.assertRaisesRegex(ValueError, 'contract or output'):
            self.run_review()
        self.assertEqual(self.marker.read_text(), 'started\n')

    def test_preexisting_result_rejects_dispatch_without_charging(self):
        self.result_path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.run_review()
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    def test_independence_and_frozen_input_digest_are_required_before_dispatch(self):
        original = self.admission
        for field in ({'actor': self.contract['author']}, {'input_digest': 'unbound-input'}):
            with self.subTest(field=field):
                self.admission = dict(original, **field)
                with self.assertRaisesRegex(ValueError, 'independent actor'):
                    self.run_review()
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})

    def test_input_changed_before_dispatch_never_starts_or_charges(self):
        self.input.write_text('different bytes\n')
        with self.assertRaises(ValueError):
            self.run_review()
        self.assertFalse(self.marker.exists())
        self.assertEqual(policy.read_runtime(self.scope)['attempts'], {})


if __name__ == '__main__':
    unittest.main()

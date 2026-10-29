"""A registered non-passing observation must not silently vanish while the baseline stays unchanged.

The real collector (run_regression.TimedResult) observes a small unittest whose second subtest runs only when a
simulated DUT returns it. No EVAS kernel or simulation runs.
"""
import copy
import importlib.util
import io
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('vanished_gate', ROOT / 'regression_gate.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
_spec = importlib.util.spec_from_file_location('vanished_runner', ROOT / 'run_regression.py')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)

REVIEW = {'status': 'approved', 'reviewer': 'fixture-independent-reviewer', 'reference': 'fixture-review:vanish',
          'semantic_status': 'not-EVAS'}
SUBJECT = {'key': '7' * 64, 'report_schema_version': 3, 'evidence_schema_version': 3, 'input_count': 6,
           'environment': {'fixture': 'unit-only', 'shard': '0-of-1'},
           'comparison_subject': {'schema_version': 1, 'report_schema_version': 3, 'evidence_schema_version': 3,
                                  'files_sha256': '6' * 64, 'input_count': 4, 'environment': {'fixture': 'unit-only'},
                                  'excluded_baseline_paths': list(gate.COMPARISON_BASELINE_PATHS)}}
DUT = {'subtests': ('fixed-pass', 'returned-obligation'), 'returned': 2, 'method': None}


def collected_case():
    """The observed unittest, built per call so discovery never collects it as a test of this module."""

    class Collected(unittest.TestCase):
        """Behaviour comes from DUT, a stand-in for what an actual DUT returns."""

        def test_returned_cases(self):
            for case in DUT['subtests']:
                with self.subTest(case=case):
                    self.assertEqual(1, DUT['returned'] if case == 'returned-obligation' else 1)

        def test_method_level(self):
            if DUT['method'] == 'fail':
                self.fail('method-level failure')

    return Collected


def collect(subtests=('fixed-pass', 'returned-obligation'), returned=2, method=None, methods=None):
    """One complete schema-3 report observed by the real TimedResult."""
    DUT.update(subtests=subtests, returned=returned, method=method)
    names = methods or ['test_returned_cases', 'test_method_level']
    result = runner.TimedResult(unittest.runner._WritelnDecorator(io.StringIO()), True, 0,
                                journal=io.StringIO(), reason_policies=[])
    case = collected_case()
    unittest.TestSuite(case(name) for name in names).run(result)
    ids = [row['id'] for row in result.timings]
    observed = [c for row in result.timings for c in row['conditions']]
    return dict(schema_version=3, complete=True, collection_complete=True, successful=result.wasSuccessful(),
                tests_run=result.testsRun, failures=sum(c['outcome'] == 'failed' for c in observed),
                errors=sum(c['outcome'] == 'error' for c in observed), skipped=0, expected_failures=0,
                unexpected_successes=0, tests=result.timings, fixtures=[], setup_skipped_test_ids=[],
                discovered_test_ids=ids, selected_test_ids=ids, assignment=[ids], shard_count=1, shard_index=0,
                metadata=dict(criteria_id='1' * 64, language_profile='2' * 64, collector_sha256='3' * 64,
                              runtime_profile={'backend': 'fixture-no-kernel'}, invocation={'pattern': 'test*.py'}),
                source_identity={'dut_files': [['evas/src/dut_fixture.py', '4' * 64]], 'kernel_sha256': None,
                                 'execution_identity': copy.deepcopy(SUBJECT)})


def propose(report):
    return gate.propose_baseline(report, {'raw_report': 'fixture-raw-source', 'source_commit': '5' * 40}, REVIEW)


class VanishedNonpassTests(unittest.TestCase):
    def setUp(self):
        self.old = collect()
        self.assertTrue(gate.validate_report(self.old)['valid'])
        self.trusted = propose(self.old)

    def outcomes(self, report):
        return {(row['id'].rsplit('.', 1)[-1], c.get('kind'), (c.get('params') or {}).get('case')): c['outcome']
                for row in report['tests'] for c in row['conditions']}

    def test_dropped_failing_subtest_needs_a_reviewed_refresh(self):
        # The review's counterexample: the DUT no longer returns the failing case; the kept pass is identical.
        new = collect(subtests=('fixed-pass',))
        self.assertTrue(gate.validate_report(new)['valid'])
        self.assertTrue(gate.compare_report(new, self.trusted)['merge_allowed'])
        self.assertFalse(gate._passed_observations(new) - gate._passed_observations(self.old))
        result = gate.validate_baseline_transition(new, self.trusted, self.trusted)
        self.assertFalse(result['merge_allowed'], result)
        self.assertTrue(result['transition']['refresh_required'])
        self.assertEqual([row['owner'] for row in result['transition']['vanished_nonpassing_observations']],
                         [self.old['tests'][0]['id']])
        self.assertIn('vanished nonpassing observations require a reviewed refreshed baseline',
                      ' '.join(result['differences']))

    def test_a_reviewed_refresh_retains_the_shrunken_observations(self):
        new = collect(subtests=('fixed-pass',))
        result = gate.validate_baseline_transition(new, self.trusted, propose(new))
        self.assertTrue(result['merge_allowed'], result)
        self.assertTrue(result['transition']['proposal_evaluated'])

    def test_same_failure_with_another_message_is_a_changed_nonpass(self):
        new = collect(returned=3)
        self.assertEqual(self.outcomes(new), self.outcomes(self.old))
        comparison = gate.compare_report(new, self.trusted)
        self.assertFalse(comparison['merge_allowed'])
        self.assertIn('new or changed nonpassing condition', ' '.join(comparison['differences']))

    def test_removed_failing_method_is_a_method_manifest_change(self):
        old = collect(method='fail')
        trusted = propose(old)
        new = collect(methods=['test_returned_cases'])
        comparison = gate.compare_report(new, trusted)
        self.assertFalse(comparison['merge_allowed'])
        self.assertIn('method manifest changed', comparison['differences'])

    def test_failing_method_that_now_passes_is_an_improvement_needing_refresh(self):
        old = collect(method='fail')
        trusted = propose(old)
        new = collect()
        self.assertTrue(gate.compare_report(new, trusted)['merge_allowed'])
        result = gate.validate_baseline_transition(new, trusted, trusted)
        self.assertFalse(result['merge_allowed'])
        self.assertIn('newly passed observations require a reviewed refreshed baseline', ' '.join(result['differences']))
        self.assertTrue(gate.validate_baseline_transition(new, trusted, propose(new))['merge_allowed'])

    def test_identical_observations_reuse_the_trusted_baseline(self):
        result = gate.validate_baseline_transition(collect(), self.trusted, self.trusted)
        self.assertTrue(result['merge_allowed'], result)
        self.assertTrue(result['transition']['reused_trusted_baseline'])


if __name__ == '__main__':
    unittest.main()

"""Synthetic controls for registering an E1 that ran on another DUT (D1) than the registration run (D0).

No fixture is a real execution. The #282 rehearsal on actual CI bytes is recorded outside the repository.
"""
import copy
import unittest

import regression_registration_fixtures as fx

api = fx.api
D0 = 'D0'
D1 = 'D1'


def add_obligation(e1, identity, outcome):
    """Append one unpaired E1 condition and keep the raw counters and method outcome consistent."""
    e1['tests'][0]['conditions'].append(fx.condition(identity, outcome, criteria='C1'))
    if outcome == 'failed':
        e1['failures'] += 1
    elif outcome == 'error':
        e1['errors'] += 1
        e1['tests'][0]['outcome'] = 'error'


def dut(report):
    subject = fx.gate.execution_subject(report)
    return dict(manifest_sha256=subject['dut_files_sha256'], kernel_sha256=subject['kernel_sha256'])


def rebind_evidence(auth):
    auth['independent_review']['evidence_sha256'] = api.digest(auth['e1'])


class SplitDutRegistrationTests(unittest.TestCase):
    def accept(self, fixture):
        result = fx.evaluate(fixture)
        self.assertTrue(result['merge_allowed'], result)
        return result

    def reject(self, fixture, message):
        result = fx.evaluate(fixture)
        self.assertFalse(result['merge_allowed'], result)
        self.assertIn(message, ' '.join(result['differences']), result)
        return result

    def test_e1_on_another_dut_with_preserved_and_new_passes_registers(self):
        # The #282 shape: E1 ran on D1, every old obligation is preserved, every new one passes.
        f = fx.make_fixture(e1_dut=D1, alter_e1=lambda e1: add_obligation(e1, 'C1:new pass', 'passed'))
        self.assertNotEqual(dut(f['current']), dut(f['e1']))
        self.assertEqual({item['classification'] for item in f['auth']['obligation_mapping']}, {'preserved'})
        result = self.accept(f)
        self.assertFalse(result['semantic_qualification'])
        merged = fx.make_fixture(e1_dut=D1, merged=True)
        self.accept(merged)

    def test_dut_identities_are_recorded_in_the_result(self):
        f = fx.make_fixture(e1_dut=D1)
        self.assertEqual(self.accept(f)['registration_dut'],
                         dict(current=dut(f['current']), e1=dut(f['e1']), changed=True))
        same = fx.make_fixture()
        self.assertEqual(self.accept(same)['registration_dut'],
                         dict(current=dut(same['current']), e1=dut(same['current']), changed=False))

    def test_changed_outcome_labelled_preserved_is_rejected_on_another_dut(self):
        def relabel(auth):
            item = next(x for x in auth['obligation_mapping'] if x['classification'] != 'preserved')
            item.update(classification='preserved', attribution=None)
            auth['independent_review']['mapping_sha256'] = api.digest(auth['obligation_mapping'])
        self.reject(fx.make_fixture(e1_dut=D1, correction=True, alter_auth=relabel),
                    'preserved obligation changed outcome')

    def test_false_pass_attribution_needs_e1_on_d0(self):
        self.reject(fx.make_fixture(e1_dut=D1, correction=True),
                    'false-pass attribution needs E1 on the authorized D0')
        # Regression control: on D0 the same correction registers as before.
        self.accept(fx.make_fixture(correction=True))

    def test_new_nonpassing_obligation_on_another_dut_is_rejected(self):
        for outcome in ('failed', 'error'):
            with self.subTest(outcome=outcome):
                self.reject(fx.make_fixture(e1_dut=D1, alter_e1=lambda e1: add_obligation(e1, 'C1:new', outcome)),
                            'new obligation on another DUT must pass: synthetic.Case.test_one:')
                # Regression control: on D0 a new matchable failure registers as before.
                self.accept(fx.make_fixture(alter_e1=lambda e1: add_obligation(e1, 'C1:new', outcome)))

    def test_new_skip_stays_rejected_on_another_dut(self):
        def skip(e1):
            e1['tests'][0]['conditions'].append(dict(fx.condition('C1:new skip', 'passed', criteria='C1'),
                                                     outcome='skipped', reason=dict(kind='skip', message='skip')))
            e1['skipped'] = 1
        self.reject(fx.make_fixture(e1_dut=D1, alter_e1=skip), 'new skip/xfail/unexpected-success observation')

    def test_registration_run_must_be_on_the_authorized_d0(self):
        for field in ('dut_files', 'kernel_sha256'):
            with self.subTest(field=field):
                f = fx.make_fixture(e1_dut=D1)
                current = copy.deepcopy(f['current'])
                if field == 'dut_files':
                    current['source_identity']['dut_files'][0][1] = fx.h('different registration-run DUT')
                else:
                    current['source_identity']['kernel_sha256'] = fx.h('different registration-run binary')
                f['current_bytes'] = fx.raw(current)
                self.reject(f, 'actual DUT/kernel against authorized D0')

    def test_environment_outside_dut_identity_must_stay_equal(self):
        def drift(e1):
            identity = e1['source_identity']['execution_identity']
            identity['environment']['hidden-profile-flag'] = True
            identity['comparison_subject']['environment']['hidden-profile-flag'] = True
        self.reject(fx.make_fixture(e1_dut=D1, alter_e1=drift), 'actual environment profile')

    def test_each_run_environment_kernel_is_its_own_dut_kernel(self):
        def e1_kernel(e1):
            identity = e1['source_identity']['execution_identity']
            for environment in (identity['environment'], identity['comparison_subject']['environment']):
                environment['kernel_sha256'] = fx.h('kernel that E1 did not record as its DUT')
        self.reject(fx.make_fixture(e1_dut=D1, alter_e1=e1_kernel), 'E1 environment kernel against its own DUT')
        f = fx.make_fixture(e1_dut=D1)
        current = copy.deepcopy(f['current'])
        identity = current['source_identity']['execution_identity']
        for environment in (identity['environment'], identity['comparison_subject']['environment']):
            environment['kernel_sha256'] = fx.h('kernel other than D0')
        f['current_bytes'] = fx.raw(current)
        self.reject(f, 'registration run environment kernel against D0')


class UnbackedD1ClaimTests(unittest.TestCase):
    """Regression controls: a D1 claim that E1's own evidence does not back keeps the D0 rule."""
    reject = SplitDutRegistrationTests.reject

    def test_declared_e1_subject_that_e1_did_not_run_keeps_the_d0_rule(self):
        def declare(auth):
            auth['e1']['execution_subject']['dut_files_sha256'] = fx.h('declared but not run')
            rebind_evidence(auth)
        self.reject(fx.make_fixture(e1_dut=D1, alter_auth=declare), 'retrievable binary differs from D0')

    def test_kernel_role_other_than_the_e1_kernel_keeps_the_d0_rule(self):
        def other(blobs):
            blobs['kernel_binary'] = b'SYNTHETIC NONEXECUTABLE OTHER BINARY FIXTURE'
        self.reject(fx.make_fixture(e1_dut=D1, alter_blobs=other), 'retrievable binary differs from D0')
        def d0_bytes(blobs):
            blobs['kernel_binary'] = b'SYNTHETIC NONEXECUTABLE D0 BINARY FIXTURE'
        self.reject(fx.make_fixture(e1_dut=D1, alter_blobs=d0_bytes), 'actual DUT/kernel against authorized D0')

    def test_e1_dut_manifest_unlike_its_snapshot_keeps_the_d0_rule(self):
        def hide(e1):
            e1['source_identity']['dut_files'][0][1] = fx.h('D2 not in the E1 snapshot')
        self.reject(fx.make_fixture(e1_dut=D1, alter_e1=hide), 'retrievable binary differs from D0')

    def test_same_actual_dut_with_a_wrong_authorized_d0_is_rejected_with_another_message(self):
        # Scope of the compatibility claim: it holds when the authorized DUT pairs are equal. Here both runs use
        # the same DUT, but current_dut names another kernel. Both versions reject; only the message differs.
        def wrong_current(auth):
            auth['current_dut']['kernel_sha256'] = fx.h('incorrect authorized current kernel')
        f = fx.make_fixture(opaque_count=0, alter_auth=wrong_current)
        self.assertEqual(dut(f['current']), dut(f['e1']))
        self.reject(f, 'actual DUT/kernel against authorized D0')


class AfterRegistrationAdmissionTests(unittest.TestCase):
    """Regression controls: once registered, a later run of the same criteria must repeat E1 exactly."""

    def test_later_run_must_equal_the_registered_entry(self):
        f = fx.make_fixture(e1_dut=D1)
        registered = f['head']
        same = copy.deepcopy(f['e1'])
        self.assertTrue(fx.gate.compare_report(same, registered)['merge_allowed'])
        self.assertTrue(fx.gate.validate_baseline_transition(same, registered, registered)['merge_allowed'])
        regressed = copy.deepcopy(f['e1'])
        passed = regressed['tests'][0]['conditions'][1]
        self.assertEqual(passed['outcome'], 'passed')
        passed.update(outcome='failed', reason=dict(kind='assertion', exception_type='builtins.AssertionError',
                                                    message='later regression', site=passed['site'],
                                                    context_complete=True, attribution='unreviewed-observation'))
        regressed['failures'] += 1
        comparison = fx.gate.compare_report(regressed, registered)
        self.assertFalse(comparison['merge_allowed'])
        self.assertIn('previously passed condition missing or changed', ' '.join(comparison['differences']))
        improved = copy.deepcopy(f['e1'])
        failed = improved['tests'][0]['conditions'][0]
        self.assertEqual(failed['outcome'], 'failed')
        failed['outcome'] = 'passed'
        failed.pop('reason')
        improved.update(failures=0, successful=True)
        improved['tests'][0]['outcome'] = 'passed'
        transition = fx.gate.validate_baseline_transition(improved, registered, registered)
        self.assertFalse(transition['merge_allowed'])
        self.assertIn('newly passed observations require a reviewed refreshed baseline', ' '.join(transition['differences']))

    def test_later_run_cannot_drop_a_registered_failure(self):
        # The review's F1 shape on a D1 context: a later run on a D2 no longer observes a registered failure.
        f = fx.make_fixture(e1_dut=D1, opaque_count=0)
        registered = f['head']
        later, _, _, _ = fx.report(criteria='C1', collector='I1', opaque_count=0, dut='D2')
        later['tests'][0]['conditions'].pop(0)
        later['tests'][0]['outcome'] = 'passed'
        later.update(failures=0, successful=True)
        self.assertTrue(fx.gate.compare_report(later, registered)['merge_allowed'])
        transition = fx.gate.validate_baseline_transition(later, registered, registered)
        self.assertFalse(transition['merge_allowed'])
        self.assertIn('vanished nonpassing observations require a reviewed refreshed baseline',
                      ' '.join(transition['differences']))


if __name__ == '__main__':
    unittest.main()

"""Synthetic plumbing controls; these fixtures do not attest scientific execution."""
import copy
import json
import unittest
import regression_registration_fixtures as fx
api = fx.api


class ContextRegistrationTests(unittest.TestCase):
    def reject(self, fixture, message=None):
        result = fx.evaluate(fixture)
        self.assertFalse(result['merge_allowed'], result)
        if message:
            self.assertIn(message, ' '.join(result['differences']), result)
        return result

    def test_red_old_transition_denies_append_green_narrow_registration_accepts(self):
        f = fx.make_fixture()
        old = fx.gate.validate_baseline_transition(f['current'], f['baseline'], f['head'])
        self.assertFalse(old['merge_allowed'])
        result = fx.evaluate(f)
        self.assertTrue(result['merge_allowed'], result)
        self.assertFalse(result['semantic_qualification'])
        self.assertEqual(result['opaque_passes'], 58)
        self.assertTrue(result['current_transition']['merge_allowed'])

    def test_subjects_differ_while_actual_D0_manifest_and_binary_match(self):
        f = fx.make_fixture()
        a, b = fx.gate.execution_subject(f['current']), fx.gate.execution_subject(f['e1'])
        self.assertNotEqual(a, b)
        self.assertEqual(a['dut_files_sha256'], b['dut_files_sha256'])
        self.assertEqual(a['kernel_sha256'], b['kernel_sha256'])
        self.assertTrue(fx.evaluate(f)['merge_allowed'])

    def test_criteria_only_and_collector_only_each_allowed(self):
        for criteria, collector in [('C1', 'I0'), ('C0', 'I1')]:
            with self.subTest(criteria=criteria, collector=collector):
                result = fx.evaluate(fx.make_fixture(new_criteria=criteria, new_collector=collector))
                self.assertTrue(result['merge_allowed'], result)

    def test_registration_finds_the_current_context_across_a_runner_host_change(self):
        def host(platform, image):
            return dict(platform=platform, machine='x86_64', variables={'ImageVersion': image},
                        execution_toolchain=dict(platform=platform, machine='x86_64',
                                                 variables={'ImageVersion': image}))
        old = host('Linux-6.17.0-1022-azure-x86_64-with-glibc2.39', '20261023.334.3')
        new = host('Linux-7.0.0-1017-azure-x86_64-with-glibc2.39', '20261026.354.1')
        def registered_on_old_host(baseline):
            for entry in baseline['contexts']:
                for target in (entry['context'], entry['observations']['metadata']):
                    target['runtime_profile'] = copy.deepcopy(old)
        result = fx.evaluate(fx.make_fixture(runtime=new, alter_baseline=registered_on_old_host))
        self.assertTrue(result['merge_allowed'], result)
        self.assertEqual(result['trusted_comparison']['host_runtime_difference']['actual']['runtime_profile'],
                         dict(platform=new['platform'], ImageVersion='20261026.354.1'))
        other = host('Linux-7.0.0-1017-azure-x86_64-with-glibc2.39', '20261027.360.1')
        self.reject(fx.make_fixture(runtime=new, e1_runtime=other, alter_baseline=registered_on_old_host),
                    'fixed runtime_profile')

    def test_old_compare_rejection_stops_before_head_or_authority_or_E1(self):
        f = fx.make_fixture()
        current = copy.deepcopy(f['current'])
        current['tests'][0]['conditions'][0]['reason']['message'] = 'changed original failure'
        f['current_bytes'] = fx.raw(current)
        f['store'].files[('HEAD', api.BASELINE)] = b'INVALID HEAD JSON'
        f['e1_bytes'] = b'INVALID E1 JSON'
        result = self.reject(f)
        self.assertFalse(result['head_evaluated'])
        self.assertFalse(result['authorization_evaluated'])
        # Pure API receives data; loader tests enforce no HEAD access before comparison.

    def test_ordinary_current_transition_still_requires_new_pass_retention(self):
        f = fx.make_fixture()
        current = copy.deepcopy(f['current'])
        current['tests'][0]['conditions'].append(fx.condition('new ordinary pass', 'passed'))
        f['current_bytes'] = fx.raw(current)
        self.assertTrue(fx.gate.compare_report(current, f['baseline'])['merge_allowed'])
        self.reject(f, 'ordinary current-context transition rejected')

    def test_existing_contexts_must_all_be_canonically_identical_and_ordered(self):
        for mode in ('remove', 'change', 'reorder'):
            f = fx.make_fixture()
            head = copy.deepcopy(f['head'])
            if mode == 'remove':
                head['contexts'].pop(1)
            elif mode == 'change':
                head['contexts'][1]['source_identity']['injected'] = True
            else:
                head['contexts'][:2] = reversed(head['contexts'][:2])
            f['store'].files[('HEAD', api.BASELINE)] = fx.raw(head)
            with self.subTest(mode=mode):
                self.reject(f)

    def test_multiple_append_and_no_append_rejected(self):
        for delta in (-1, 1):
            f = fx.make_fixture()
            head = copy.deepcopy(f['head'])
            if delta == -1:
                head['contexts'].pop()
            else:
                head['contexts'].append(copy.deepcopy(f['entry']))
            f['store'].files[('HEAD', api.BASELINE)] = fx.raw(head)
            self.reject(f, 'exactly one context append')

    def test_current_report_DUT_manifest_or_binary_change_cannot_register_D0(self):
        for field in ('dut_files', 'kernel_sha256'):
            f = fx.make_fixture()
            current = copy.deepcopy(f['current'])
            if field == 'dut_files':
                current['source_identity'][field][0][1] = fx.h('different actual DUT')
            else:
                current['source_identity'][field] = fx.h('different actual binary')
            f['current_bytes'] = fx.raw(current)
            self.reject(f, 'actual DUT/kernel against authorized D0')

    def test_E1_changed_DUT_manifest_or_binary_rejected_even_if_authorized_entry(self):
        for field in ('dut_files', 'kernel_sha256'):
            def alter(e1):
                if field == 'dut_files':
                    e1['source_identity'][field][0][1] = fx.h('D1 hidden in E1')
                else:
                    e1['source_identity'][field] = fx.h('wrong E1 binary')
            with self.subTest(field=field):
                self.reject(fx.make_fixture(alter_e1=alter), 'actual DUT/kernel against authorized D0')

    def test_language_runtime_and_invocation_drift_rejected(self):
        for field in ('language_profile', 'runtime_profile', 'invocation'):
            def alter(e1):
                e1['metadata'][field] = fx.h('new language') if field == 'language_profile' else {'drift': True}
            with self.subTest(field=field):
                self.reject(fx.make_fixture(alter_e1=alter), 'fixed ' + field)

    def test_actual_environment_drift_not_hidden_by_same_metadata(self):
        def alter(e1):
            identity = e1['source_identity']['execution_identity']
            identity['environment']['hidden-profile-flag'] = True
            identity['comparison_subject']['environment']['hidden-profile-flag'] = True
        self.reject(fx.make_fixture(alter_e1=alter), 'actual environment profile')

    def test_raw_bytes_and_canonical_report_are_separate_bindings(self):
        f = fx.make_fixture()
        f['e1_bytes'] += b'\n'
        self.reject(f, 'E1 raw bytes')
        f = fx.make_fixture(alter_auth=lambda a: a['e1'].update(canonical_report_sha256='1' * 64))
        self.reject(f, 'E1 canonical report')

    def test_entry_and_new_source_or_review_tampering_rejected(self):
        for key in ('canonical_report_sha256', 'source_identity', 'review'):
            f = fx.make_fixture()
            head = copy.deepcopy(f['head'])
            if key == 'canonical_report_sha256':
                head['contexts'][-1][key] = '1' * 64
            else:
                head['contexts'][-1][key]['tampered'] = True
            f['store'].files[('HEAD', api.BASELINE)] = fx.raw(head)
            self.reject(f, 'expected one exact authorization')

    def test_authorized_entry_must_keep_every_pass_and_projection_field(self):
        def drop_pass(entry):
            entry['observations']['tests'][0]['conditions'].pop(1)
        self.reject(fx.make_fixture(alter_entry=drop_pass), 'complete projected E1 observations')

    def test_unknown_entry_field_or_schema_not_upgraded(self):
        for field, value in [('surprise', True), ('observation_encoding', 'future-v99'),
                             ('semantic_qualification', True)]:
            with self.subTest(field=field):
                self.reject(fx.make_fixture(alter_entry=lambda e: e.update({field: value})))

    def test_unknown_authorization_schema_extra_fields_or_self_hash_rejected(self):
        for changes in ({'schema_version': 2}, {'schema_version': True}, {'self_sha256': '1' * 64}):
            self.reject(fx.make_fixture(alter_auth=lambda a: a.update(changes)))

    def test_unknown_E1_metadata_not_silently_projected_away(self):
        self.reject(fx.make_fixture(alter_e1=lambda r: r['metadata'].update(unknown_profile=True)), 'E1 metadata schema')

    def test_all_observed_nonpasses_must_be_matchable(self):
        def alter(e1):
            e1['tests'][0]['conditions'][0]['identity_complete'] = False
        self.reject(fx.make_fixture(alter_e1=alter), 'nonpassing identity not fully matchable')

    def test_missing_raw_subject_old_raw_is_never_filled_in(self):
        f = fx.make_fixture()
        e1 = copy.deepcopy(f['e1'])
        e1['source_identity'].pop('execution_identity')
        f['e1_bytes'] = fx.raw(e1)
        self.reject(f)
        self.assertNotIn('execution_identity', json.loads(f['e1_bytes'])['source_identity'])

    def test_old_baseline_canonical_digest_blocks_replay(self):
        f = fx.make_fixture()
        prior_registered = copy.deepcopy(f['head'])
        f['store'].files[(fx.BASE, api.BASELINE)] = fx.raw(prior_registered)
        replay_head = copy.deepcopy(prior_registered)
        replay_head['contexts'].append(copy.deepcopy(f['entry']))
        f['store'].files[('HEAD', api.BASELINE)] = fx.raw(replay_head)
        self.reject(f, 'authorized old baseline')

    def test_unrelated_tracked_change_and_head_review_changes_are_blocked(self):
        f = fx.make_fixture()
        f['store'].changed.append('scripts/unrelated.py')
        self.reject(f, 'only fixed baseline path')
        f = fx.make_fixture()
        review = copy.deepcopy(f['review'])
        review['original_receipt']['decision'] = 'rewritten old receipt'
        f['store'].files[('HEAD', api.REVIEW)] = fx.raw(review)
        self.reject(f, 'head review/receipt/governance fields')

    def test_head_fake_authorization_is_not_trusted(self):
        f = fx.make_fixture()
        empty = copy.deepcopy(f['review'])
        empty[api.GOVERNANCE] = []
        f['store'].files[(fx.BASE, api.REVIEW)] = fx.raw(empty)
        self.reject(f, 'head review/receipt/governance fields')

    def test_authorization_not_exact_entry_digest_cannot_match(self):
        self.reject(fx.make_fixture(alter_auth=lambda a: a.update(new_entry_canonical_sha256='2' * 64)),
                    'expected one exact authorization')

    def test_duplicate_trusted_authorization_rejected(self):
        f = fx.make_fixture()
        review = copy.deepcopy(f['review'])
        review[api.GOVERNANCE].append(copy.deepcopy(review[api.GOVERNANCE][0]))
        for revision in (fx.BASE, 'HEAD'):
            f['store'].files[(revision, api.REVIEW)] = fx.raw(review)
        self.reject(f, 'expected one exact authorization')

    def test_missing_old_method_or_obligation_mapping_rejected(self):
        self.reject(fx.make_fixture(alter_auth=lambda a: a['obligation_mapping'].pop()), 'old obligations omitted')
        def alter(e1):
            for key in ('discovered_test_ids', 'selected_test_ids'):
                e1[key] = ['synthetic.Case.renamed']
            e1['assignment'] = [['synthetic.Case.renamed']]
            e1['tests'][0]['id'] = 'synthetic.Case.renamed'
        self.reject(fx.make_fixture(alter_e1=alter), 'old method ID obligation lost')

    def test_false_pass_requires_named_manual_attribution_not_auto_exemption(self):
        f = fx.make_fixture(correction=True)
        self.assertTrue(fx.evaluate(f)['merge_allowed'])
        def remove(auth):
            item = next(x for x in auth['obligation_mapping'] if x['classification'] != 'preserved')
            item['attribution'] = None
        self.reject(fx.make_fixture(correction=True, alter_auth=remove), 'false-pass attribution schema')
        def relabel(auth):
            item = next(x for x in auth['obligation_mapping'] if x['classification'] != 'preserved')
            item['classification'] = 'preserved'
            item['attribution'] = None
        self.reject(fx.make_fixture(correction=True, alter_auth=relabel), 'preserved obligation changed outcome')

    def test_mapping_must_bind_exact_old_and_new_conditions(self):
        for field in ('old_signature_sha256', 'new_signature_sha256'):
            def alter(auth):
                auth['obligation_mapping'][0][field] = '2' * 64
            self.reject(fx.make_fixture(alter_auth=alter), 'obligation signature')

    def test_new_skip_or_xfail_not_hidden_in_registration(self):
        def alter(e1):
            c = fx.condition('new-xfail', 'expected_failure', criteria='C1')
            e1['tests'][0]['conditions'].append(c)
            e1['expected_failures'] = 1
        self.reject(fx.make_fixture(alter_e1=alter), 'new skip/xfail')

    def test_missing_or_changed_artifact_bytes_and_binary_rejected(self):
        for role in ('kernel_binary', 'snapshot_manifest', 'dut_build', 'stdout', 'stderr', 'shard_reports'):
            f = fx.make_fixture()
            f['blobs'][role] += b'corruption'
            self.reject(f, 'artifact bytes: ' + role)

    def test_review_binds_entry_evidence_and_mapping_but_not_human_authentication(self):
        for field in ('entry_sha256', 'evidence_sha256', 'mapping_sha256'):
            def alter(auth):
                auth['independent_review'][field] = '2' * 64
            self.reject(fx.make_fixture(alter_auth=alter), 'manual review exact')
        f = fx.make_fixture()
        self.assertIn('does not authenticate', fx.evaluate(f)['human_review_status'])

    def test_merged_two_shard_raw_and_original_captures_are_verified(self):
        f = fx.make_fixture(merged=True)
        result = fx.evaluate(f)
        self.assertTrue(result['merge_allowed'], result)
        self.assertEqual(result['opaque_passes'], 58)

    def test_even_authorized_capture_cannot_drop_original_shard_bytes(self):
        def alter(blobs):
            shards = json.loads(blobs['shard_reports'])
            shards.pop()
            blobs['shard_reports'] = fx.raw(shards)
        self.reject(fx.make_fixture(merged=True, alter_blobs=alter), 'shard raw bytes missing')

    def test_even_authorized_shard_cannot_hide_different_DUT_manifest(self):
        def alter(blobs):
            shards = json.loads(blobs['shard_reports'])
            report = json.loads(shards[1])
            report['source_identity']['dut_files'][0][1] = fx.h('hidden D1 shard')
            shards[1] = fx.raw(report).decode()
            blobs['shard_reports'] = fx.raw(shards)
            capture = json.loads(blobs['artifact_manifest'])
            capture['shard_report_sha256'] = [api.raw_digest(x.encode()) for x in shards]
            blobs['artifact_manifest'] = fx.raw(capture)
        self.reject(fx.make_fixture(merged=True, alter_blobs=alter), 'shard public scientific source')

    def test_authorized_artifact_schema_and_snapshot_modes_remain_strict(self):
        for mode in ('version', 'symlink', 'changed-input', 'collector'):
            def alter(blobs):
                if mode == 'collector':
                    collector = json.loads(blobs['collector_manifest'])
                    collector['runner'] = fx.h('wrong collector source')
                    blobs['collector_manifest'] = fx.raw(collector)
                    return
                snapshot = json.loads(blobs['snapshot_manifest'])
                if mode == 'version':
                    snapshot['schema_version'] = 99
                elif mode == 'symlink':
                    snapshot['entries'][0][1] = '120000'
                else:
                    snapshot['entries'][0][3] = fx.h('changed tracked input')
                blobs['snapshot_manifest'] = fx.raw(snapshot)
            with self.subTest(mode=mode):
                self.reject(fx.make_fixture(alter_blobs=alter))

    def test_authorized_recipe_and_capture_output_mismatch_rejected(self):
        def wrong_recipe(blobs):
            value = json.loads(blobs['composition_recipe'])
            value['criteria_id'] = fx.h('wrong criteria')
            blobs['composition_recipe'] = fx.raw(value)
        self.reject(fx.make_fixture(alter_blobs=wrong_recipe), 'composition recipe')
        def wrong_stdout(blobs):
            blobs['stdout'] += b'new output'
        self.reject(fx.make_fixture(alter_blobs=wrong_stdout), 'captured stdout')

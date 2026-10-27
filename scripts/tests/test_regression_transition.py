"""Small report fixtures. The separate pilot uses an actual DUT and Git commits."""
import copy
import importlib.util
from pathlib import Path
import unittest
D=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('transition_gate', D.parent/'regression_gate.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def report(outcome='failed'):
    cond=dict(id='A',phase='test',kind='subtest',site={'module':'test_fixed','line':10,'source_sha256':'a'*64},identity_complete=True,outcome=outcome)
    if outcome!='passed':cond['reason']=dict(kind='assertion',exception_type='builtins.AssertionError',message='A differs',site=cond['site'])
    return dict(schema_version=3,complete=True,collection_complete=True,successful=outcome=='passed',tests_run=1,failures=int(outcome=='failed'),errors=0,skipped=0,expected_failures=0,unexpected_successes=0,tests=[dict(id='fixed.Case.test_A',outcome=outcome,seconds=0.1,conditions=[cond])],fixtures=[],setup_skipped_test_ids=[],discovered_test_ids=['fixed.Case.test_A'],selected_test_ids=['fixed.Case.test_A'],assignment=[['fixed.Case.test_A']],shard_count=1,shard_index=0,metadata=dict(criteria_id='1'*64,language_profile='2'*64,collector_sha256='3'*64,runtime_profile={'backend':'fixture-no-kernel'},invocation={'pattern':'test*.py'}),source_identity={'dut_files':[['evas/src/dut_fixture.py','4'*64]],'kernel_sha256':None,'execution_identity':{'key':'7'*64,'report_schema_version':3,'evidence_schema_version':3,'input_count':6,'environment':{'fixture':'unit-only','shard':'0-of-1'},'comparison_subject':{'schema_version':1,'report_schema_version':3,'evidence_schema_version':3,'files_sha256':'6'*64,'input_count':4,'environment':{'fixture':'unit-only'},'excluded_baseline_paths':['evas/validation/baselines/regression-v1.json','evas/validation/baselines/regression-v1.review.json']}}})
REVIEW={'status':'approved','reviewer':'fixture-independent-reviewer','reference':'fixture-review:001','semantic_status':'not-EVAS'}

def propose(r):return gate.propose_baseline(r,{'raw_report':'fixture-raw-source','source_commit':'5'*40},REVIEW)

class TransitionTests(unittest.TestCase):
    def test_improvement_cannot_merge_with_stale_baseline(self):
        old=report();fixed=report('passed');trusted=propose(old)
        self.assertTrue(gate.compare_report(fixed,trusted)['merge_allowed'])
        self.assertFalse(gate.validate_baseline_transition(fixed,trusted,trusted)['merge_allowed'])


class RetentionBehavior(unittest.TestCase):
    def setUp(self):
        self.old=report();self.fixed=report('passed');self.trusted=propose(self.old)
    def evaluate(self,current=None,head=None):
        return gate.validate_baseline_transition(current or self.fixed,self.trusted,head if head is not None else propose(self.fixed))
    def test_unchanged_legacy_baseline_without_subject_can_be_reused(self):
        legacy=copy.deepcopy(self.trusted);legacy['contexts'][0].pop('execution_subject')
        r=gate.validate_baseline_transition(self.old,legacy,legacy)
        self.assertTrue(r['merge_allowed']);self.assertFalse(r['raw_successful']);self.assertFalse(r['transition']['proposal_evaluated'])
    def test_reviewed_complete_improvement_is_accepted(self):
        r=self.evaluate();self.assertTrue(r['merge_allowed']);self.assertTrue(r['transition']['refresh_required'])
        self.assertFalse(r['semantic_qualification'])
    def test_same_A_recurrence_against_updated_trusted_is_refused(self):
        updated=propose(self.fixed)
        r=gate.validate_baseline_transition(self.old,updated,self.trusted)
        self.assertFalse(r['merge_allowed']);self.assertFalse(r['transition']['proposal_evaluated'])
    def test_old_trusted_comparison_runs_before_head_is_inspected(self):
        current=report();current['tests'][0]['conditions'][0]['id']='B'
        class PoisonHead(dict):
            def items(self):raise AssertionError('head must not be inspected')
        r=gate.validate_baseline_transition(current,self.trusted,PoisonHead())
        self.assertFalse(r['merge_allowed']);self.assertFalse(r['transition']['proposal_evaluated'])
    def test_head_self_adds_B_waiver_cannot_waive_current_A_to_B(self):
        current=report();current['tests'][0]['conditions'][0]['id']='B'
        r=gate.validate_baseline_transition(current,self.trusted,propose(current))
        self.assertTrue(gate.compare_report(current,propose(current))['merge_allowed'])
        self.assertFalse(r['merge_allowed'])
    def test_passed_observation_cannot_be_removed_from_proposal(self):
        current=copy.deepcopy(self.fixed)
        p=copy.deepcopy(current['tests'][0]['conditions'][0]);p['id']='P';current['tests'][0]['conditions'].append(p)
        head=propose(current);head['contexts'][0]['observations']['tests'][0]['conditions'].pop(0)
        self.assertTrue(gate.compare_report(current,head)['merge_allowed'])
        self.assertFalse(self.evaluate(current,head)['merge_allowed'])
    def test_preexisting_pass_cannot_be_lost_in_refresh(self):
        old=copy.deepcopy(self.old);p=copy.deepcopy(self.fixed['tests'][0]['conditions'][0]);p['id']='P';old['tests'][0]['conditions'].append(p)
        fixed=copy.deepcopy(old);fixed['tests'][0]['conditions'][0]=copy.deepcopy(self.fixed['tests'][0]['conditions'][0]);fixed.update(successful=True,failures=0);fixed['tests'][0]['outcome']='passed'
        head=propose(fixed);head['contexts'][0]['observations']['tests'][0]['conditions'].pop()
        self.assertFalse(gate.validate_baseline_transition(fixed,propose(old),head)['merge_allowed'])
    def test_extra_head_failure_exemption_is_rejected_even_when_current_is_unchanged(self):
        head=copy.deepcopy(self.trusted);c=copy.deepcopy(head['contexts'][0]['observations']['tests'][0]['conditions'][0]);c['id']='B';head['contexts'][0]['observations']['tests'][0]['conditions'].append(c);head['contexts'][0]['observations']['failures']=2
        self.assertFalse(gate.validate_baseline_transition(self.old,self.trusted,head)['merge_allowed'])
    def test_review_fields_are_required(self):
        for field in ['status','reviewer','reference']:
            head=propose(self.fixed);head['contexts'][0]['review'].pop(field)
            self.assertFalse(self.evaluate(head=head)['merge_allowed'])
    def test_unknown_and_incomplete_report_are_refused(self):
        for field,value in [('schema_version',99),('complete',False),('collection_complete',False)]:
            current=copy.deepcopy(self.fixed);current[field]=value
            self.assertFalse(self.evaluate(current=current)['merge_allowed'])
        current=copy.deepcopy(self.fixed);current['tests'][0]['conditions'][0]['identity_complete']=False
        self.assertFalse(self.evaluate(current=current)['merge_allowed'])
    def test_actual_metadata_drift_is_rejected_before_proposal(self):
        for key in gate.CONTEXT_KEYS:
            current=copy.deepcopy(self.fixed);current['metadata'][key]='f'*64 if key in gate.CONTEXT_KEYS[:3] else {'changed':True}
            r=self.evaluate(current=current)
            self.assertFalse(r['merge_allowed']);self.assertFalse(r['transition']['proposal_evaluated'])
    def test_proposal_context_or_subject_drift_is_rejected(self):
        for field,value in [('dut_files_sha256','f'*64),('kernel_sha256','f'*64),('schema_version',99)]:
            head=propose(self.fixed);head['contexts'][0]['execution_subject'][field]=value
            self.assertFalse(self.evaluate(head=head)['merge_allowed'])
        head=propose(self.fixed);head['contexts'][0]['context']['criteria_id']='f'*64
        self.assertFalse(self.evaluate(head=head)['merge_allowed'])
    def test_subject_is_from_actual_raw_not_caller_source_identity(self):
        head=gate.propose_baseline(self.fixed,{'dut_files':[['evas/src/invented.py','f'*64]]},REVIEW)
        self.assertEqual(head['contexts'][0]['execution_subject'],gate.execution_subject(self.fixed))
    def test_missing_or_duplicate_selected_DUT_identity_cannot_refresh(self):
        head=propose(self.fixed)
        for files in [[],[['evas/src/dut_fixture.py','4'*64]]*2,[['evas/validation/baselines/ignored.json','4'*64]]]:
            current=copy.deepcopy(self.fixed);current['source_identity']['dut_files']=files
            self.assertFalse(self.evaluate(current,head)['merge_allowed'])
    def test_prior_raw_same_science_is_valid_without_a_full_raw_hash_fixed_point(self):
        source=copy.deepcopy(self.fixed);source['source_identity']['execution_identity']['key']='a'*64
        source['tests'][0]['seconds']=0.12
        head=propose(source)
        current=copy.deepcopy(self.fixed);current['source_identity']['execution_identity']['key']='b'*64;current['tests'][0]['seconds']=0.45
        self.assertNotEqual(head['contexts'][0]['canonical_report_sha256'],__import__('hashlib').sha256(gate._json(current).encode()).hexdigest())
        self.assertTrue(self.evaluate(current,head)['merge_allowed'])
    def test_actual_DUT_change_rejects_a_prior_science_proposal(self):
        head=propose(self.fixed);current=copy.deepcopy(self.fixed);current['source_identity']['dut_files'][0][1]='f'*64
        self.assertFalse(self.evaluate(current,head)['merge_allowed'])
    def test_unrelated_context_cannot_be_removed_or_changed(self):
        other=copy.deepcopy(self.old);other['metadata']['criteria_id']='f'*64
        trusted=copy.deepcopy(self.trusted);trusted['contexts']+=propose(other)['contexts']
        head=propose(self.fixed)
        self.assertFalse(gate.validate_baseline_transition(self.fixed,trusted,head)['merge_allowed'])
        head['contexts']+=copy.deepcopy(trusted['contexts'][1:])
        self.assertTrue(gate.validate_baseline_transition(self.fixed,trusted,head)['merge_allowed'])


class CompleteInputSubjectBehavior(unittest.TestCase):
    def test_legacy_raw_cannot_backfill_a_new_pass_subject(self):
        old=report();fixed=report('passed');fixed['source_identity'].pop('execution_identity')
        head=propose(fixed)
        self.assertNotIn('execution_subject',head['contexts'][0])
        self.assertFalse(gate.validate_baseline_transition(fixed,propose(old),head)['merge_allowed'])
    def test_other_input_digest_or_mode_change_is_not_the_same_science(self):
        fixed=report('passed');head=propose(fixed);trusted=propose(report())
        for field,value in [('files_sha256','f'*64),('input_count',5),('environment',{'fixture':'changed-tool'})]:
            current=copy.deepcopy(fixed);current['source_identity']['execution_identity']['comparison_subject'][field]=value
            self.assertFalse(gate.validate_baseline_transition(current,trusted,head)['merge_allowed'])
    def test_exclusion_expansion_unknown_field_or_missing_field_is_rejected(self):
        fixed=report('passed');head=propose(fixed);trusted=propose(report())
        for mutate in [lambda s:s['excluded_baseline_paths'].append('config/extra.json'),lambda s:s.update(extra='unknown'),lambda s:s.pop('files_sha256'),lambda s:s.update(schema_version=99),lambda s:s['environment'].update(shard='0-of-1')]:
            current=copy.deepcopy(fixed);mutate(current['source_identity']['execution_identity']['comparison_subject'])
            self.assertFalse(gate.validate_baseline_transition(current,trusted,head)['merge_allowed'])
    def test_merged_part_subjects_must_agree_and_all_be_present(self):
        r=report('passed');subject=copy.deepcopy(r['source_identity']['execution_identity']['comparison_subject'])
        r.update(merged=True,shard_index=None,shard_count=2,assignment=[r['discovered_test_ids'],[]],parts=[{'shard_index':i,'complete':True,'collection_complete':True,'selected_test_ids':r['discovered_test_ids'] if i==0 else [],'source_identity':{'execution_identity':copy.deepcopy(r['source_identity']['execution_identity'])}} for i in range(2)])
        actual=gate.execution_subject(r)
        self.assertEqual(actual['comparison_subject'],subject)
        r['parts'][1]['source_identity']['execution_identity']['comparison_subject']['files_sha256']='f'*64
        with self.assertRaises(ValueError):gate.execution_subject(r)
        r['parts'][1]['source_identity']['execution_identity'].pop('comparison_subject')
        with self.assertRaises(ValueError):gate.execution_subject(r)


class ActualIdentityConsistency(unittest.TestCase):
    def test_subject_environment_cannot_disagree_with_its_actual_execution_identity(self):
        fixed=report('passed');head=propose(fixed)
        fixed['source_identity']['execution_identity']['environment']['tool']='actually-different'
        self.assertFalse(gate.validate_baseline_transition(fixed,propose(report()),head)['merge_allowed'])


class ActualManifestShapeCompatibility(unittest.TestCase):
    def test_grouped_manifest_order_is_preserved_without_legacy_subject(self):
        import hashlib
        # The collector emits src then rust_core, each internally sorted.
        # The full327-row historical compatibility receipt remains task evidence.
        shape={'dut_files':[['evas/src/dut_fixture.py','4'*64],
                            ['evas/rust_core/src/lib.rs','5'*64]]}
        self.assertNotEqual(shape['dut_files'], sorted(shape['dut_files']))
        current=report('passed');current['source_identity']['dut_files']=shape['dut_files']
        # Synthetic unit comparison_subject stays explicitly separate from old raw.
        subject=gate.execution_subject(current)
        self.assertEqual(subject['dut_files_sha256'],hashlib.sha256(gate._json(shape['dut_files']).encode()).hexdigest())
        reordered=copy.deepcopy(current);reordered['source_identity']['dut_files']=sorted(shape['dut_files'])
        self.assertNotEqual(subject['dut_files_sha256'],gate.execution_subject(reordered)['dut_files_sha256'])
        legacy_shape_only=copy.deepcopy(current);legacy_shape_only['source_identity'].pop('execution_identity')
        self.assertNotIn('execution_subject',propose(legacy_shape_only)['contexts'][0])


class OpaquePassedCompatibility(unittest.TestCase):
    def old_and_fixed(self):
        old=report();p=copy.deepcopy(report('passed')['tests'][0]['conditions'][0]);p.update(id='P',identity_complete=False)
        old['tests'][0]['conditions'].append(p)
        fixed=copy.deepcopy(old);fixed.update(successful=True,failures=0);fixed['tests'][0]['outcome']='passed';fixed['tests'][0]['conditions'][0]=copy.deepcopy(report('passed')['tests'][0]['conditions'][0])
        return old,fixed
    def test_existing_opaque_pass_can_reuse_unchanged_legacy_baseline(self):
        old,_=self.old_and_fixed();baseline=propose(old);baseline['contexts'][0].pop('execution_subject')
        result=gate.validate_baseline_transition(old,baseline,baseline)
        self.assertTrue(result['merge_allowed']);self.assertFalse(result['semantic_qualification'])
    def test_existing_opaque_pass_is_retained_false_during_other_improvement(self):
        old,fixed=self.old_and_fixed();head=propose(fixed)
        result=gate.validate_baseline_transition(fixed,propose(old),head)
        self.assertTrue(result['merge_allowed']);self.assertFalse(result['semantic_qualification'])
        self.assertFalse(head['contexts'][0]['observations']['tests'][0]['conditions'][1]['identity_complete'])
    def test_opaque_pass_cannot_disappear_fail_or_be_promoted_by_proposal(self):
        old,fixed=self.old_and_fixed();trusted=propose(old)
        missing=copy.deepcopy(old);missing['tests'][0]['conditions'].pop()
        self.assertFalse(gate.validate_baseline_transition(missing,trusted,trusted)['merge_allowed'])
        failing=copy.deepcopy(old);c=failing['tests'][0]['conditions'][1];c['outcome']='failed';c['reason']=copy.deepcopy(old['tests'][0]['conditions'][0]['reason']);failing['failures']=2
        self.assertFalse(gate.validate_baseline_transition(failing,trusted,propose(failing))['merge_allowed'])
        head=propose(fixed);head['contexts'][0]['observations']['tests'][0]['conditions'][1]['identity_complete']=True
        self.assertFalse(gate.validate_baseline_transition(fixed,trusted,head)['merge_allowed'])
    def test_new_pass_can_be_opaque_if_false_flag_and_all_inputs_are_retained(self):
        fixed=report('passed');fixed['tests'][0]['conditions'][0]['identity_complete']=False
        head=propose(fixed);result=gate.validate_baseline_transition(fixed,propose(report()),head)
        self.assertTrue(result['merge_allowed']);self.assertFalse(result['semantic_qualification'])
        again=report();again['tests'][0]['conditions'][0]['identity_complete']=False
        self.assertFalse(gate.validate_baseline_transition(again,head,propose(again))['merge_allowed'])
    def test_unknown_nonpass_is_still_not_waivable(self):
        unknown=report();unknown['tests'][0]['conditions'][0]['identity_complete']=False
        self.assertFalse(gate.validate_baseline_transition(unknown,propose(report()),propose(unknown))['merge_allowed'])


class MissingHeadDataBehavior(unittest.TestCase):
    def test_missing_head_data_cannot_be_treated_as_verified_unchanged_baseline(self):
        old=report();trusted=propose(old)
        self.assertFalse(gate.validate_baseline_transition(old,trusted,None)['merge_allowed'])


OLD_PLATFORM='Linux-6.17.0-1022-azure-x86_64-with-glibc2.39';NEW_PLATFORM='Linux-7.0.0-1017-azure-x86_64-with-glibc2.39'
def on_host(r,platform,image):
    r=copy.deepcopy(r);variables={'PATH':'/usr/bin','ImageVersion':image}
    r['metadata']['runtime_profile']=dict(platform=platform,machine='x86_64',variables=variables,
        execution_toolchain=dict(platform=platform,machine='x86_64',variables={'ImageVersion':image}))
    return r
NEW_HOST={'runtime_profile':{'platform':NEW_PLATFORM,'ImageVersion':'20261026.354.1'},
          'execution_toolchain':{'platform':NEW_PLATFORM,'ImageVersion':'20261026.354.1'}}


class RunnerHostRefresh(unittest.TestCase):
    """A new pass seen on another runner host refreshes the registered context."""
    def setUp(self):
        self.trusted=propose(on_host(report(),OLD_PLATFORM,'20261023.334.3'))
        self.fixed=on_host(report('passed'),NEW_PLATFORM,'20261026.354.1')
    def refresh(self,observed_host=NEW_HOST,run='fixture-run:40000000001'):
        head=propose(self.fixed);entry=head['contexts'][0];registered=self.trusted['contexts'][0]['context']
        entry['context']=copy.deepcopy(registered);entry['observations']['metadata']=copy.deepcopy(registered)
        entry['source_identity']=dict(entry['source_identity'],observed_run=run,observed_host=copy.deepcopy(observed_host))
        return head
    def test_refresh_keeps_registered_context_and_records_actual_host(self):
        r=gate.validate_baseline_transition(self.fixed,self.trusted,self.refresh())
        self.assertTrue(r['merge_allowed'],r);self.assertTrue(r['transition']['refresh_required'])
        self.assertEqual(r['host_runtime_difference']['actual'],NEW_HOST)
    def test_refresh_without_actual_host_or_run_is_refused(self):
        wrong=copy.deepcopy(NEW_HOST);wrong['runtime_profile']['ImageVersion']='20261023.334.3'
        for head in [self.refresh(observed_host=None),self.refresh(observed_host=wrong),self.refresh(run=' ')]:
            r=gate.validate_baseline_transition(self.fixed,self.trusted,head)
            self.assertFalse(r['merge_allowed']);self.assertIn('actual runner host and run',' '.join(r['differences']))
    def test_refresh_cannot_move_the_registered_context_to_the_new_host(self):
        r=gate.validate_baseline_transition(self.fixed,self.trusted,propose(self.fixed))
        self.assertFalse(r['merge_allowed']);self.assertIn('exactly one current context',' '.join(r['differences']))

if __name__=='__main__':unittest.main()

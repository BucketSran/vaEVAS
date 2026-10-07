"""Evidence boundary tests. These fixtures do not claim simulator execution."""
import copy
import gzip
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('audit_formal', Path(__file__).with_name('audit_formal.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FormalAuditTests(unittest.TestCase):
    def storage(self):
        raw = b'complete synthetic PSF bytes\n' * 30
        stored = gzip.compress(raw, mtime=0)
        receipt = dict(version='gzip-lossless-psf-v1', encoding='gzip', roundtrip_verified=True,
                       raw_path='psf/tran.tran.tran', gzip_path='psf/tran.tran.tran.gz',
                       raw_bytes=len(raw), raw_sha256=audit.digest(raw), gzip_bytes=len(stored),
                       gzip_sha256=audit.digest(stored), compression_elapsed_s=.05)
        return raw, stored, receipt

    def test_full_gzip_roundtrip(self):
        raw, stored, receipt = self.storage()
        self.assertEqual(audit.decode_waveform(stored,receipt),raw)

    def test_stored_and_raw_corruption_are_rejected(self):
        raw, stored, receipt = self.storage()
        with self.assertRaisesRegex(ValueError,'gzip identity'):
            audit.decode_waveform(stored[:-1]+b'x',receipt)
        wrong = copy.deepcopy(receipt)
        wrong['raw_sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError,'raw PSF identity'):
            audit.decode_waveform(stored,wrong)

    def test_decompression_overrun_and_path_relocation_rejected(self):
        raw, stored, receipt = self.storage()
        wrong = copy.deepcopy(receipt); wrong['raw_bytes'] -= 1
        with self.assertRaisesRegex(ValueError,'byte count'):
            audit.decode_waveform(stored,wrong)
        for path in ('../../leak.gz','other.gz','/absolute.gz'):
            wrong = copy.deepcopy(receipt); wrong['gzip_path'] = path
            with self.assertRaises(ValueError):audit.decode_waveform(stored,wrong)

    def completed(self):
        records = [dict(phase=phase,role=role,status='completed',passed=True)
                   for phase,role in audit.ORDER]
        return dict(status='completed',warmups=records[:2],records=records[2:])

    def test_two_warmups_and_five_pairs_required(self):
        paired=self.completed()
        self.assertEqual(len(audit.verify_attempt_order(paired)),12)
        for group,index in (('warmups',0),('records',3),('records',9)):
            wrong=copy.deepcopy(paired);wrong[group].pop(index)
            with self.assertRaises(ValueError):audit.verify_attempt_order(wrong)
        wrong=copy.deepcopy(paired);wrong['records'][0],wrong['records'][1]=wrong['records'][1],wrong['records'][0]
        with self.assertRaises(ValueError):audit.verify_attempt_order(wrong)

    def test_early_failures_preserve_prefix_and_do_not_reduce_completed_denominator(self):
        paired=self.completed();paired['status']='submission_failure'
        paired['records']=paired['records'][:2];paired['records'][-1].update(passed=False)
        self.assertEqual(len(audit.verify_attempt_order(paired)),4)
        wrong=copy.deepcopy(paired);wrong['status']='completed'
        with self.assertRaises(ValueError):audit.verify_attempt_order(wrong)
        wrong=copy.deepcopy(paired);wrong['warmups'][0]['passed']=False
        with self.assertRaises(ValueError):audit.verify_attempt_order(wrong)

    def test_missing_report_and_infrastructure_are_never_semantic_rejection(self):
        self.assertEqual(audit.classify_attempt(None),'infrastructure_failure')
        self.assertEqual(audit.classify_attempt({'status':'infrastructure_error'}, {'passed':False}),
                         'infrastructure_failure')
        self.assertEqual(audit.classify_attempt({'status':'graded','passed':False}, {'passed':False}),
                         'semantic_failure')

    def test_correct_function_can_fail_performance(self):
        paired=self.completed();paired['comparison']={'passed':False}
        self.assertEqual(audit.classify_attempt({'status':'graded','passed':False},{'passed':True},paired),
                         'performance_failure')

    def test_matrix_plan_omissions_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);matrix=root/'matrix.json';plan=root/'plan.json'
            matrix.write_text(json.dumps([{'prepared':str(root/'a')}]));plan.write_text('[]')
            with self.assertRaisesRegex(ValueError,'matrix/plan inventory'):
                audit.audit_matrix(matrix,plan,root)

    def test_changed_case_value_refuses_reuse(self):
        with self.assertRaisesRegex(ValueError,'case values differ'):
            audit.require_same_case({'stop':1.},{'stop':1.0000001})

    def test_solver_invocation_must_preserve_native_log_psf_and_single_thread(self):
        argv=['spectre','-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1']
        audit.validate_argv(argv)
        for wrong in (argv[:-1],argv[:-1]+['+mt=4'],argv[:6]+['psfbin']+argv[7:]):
            with self.assertRaisesRegex(ValueError,'solver invocation'):
                audit.validate_argv(wrong)

    def test_compact_receipt_retains_fixed_identity_without_artifact_duplication(self):
        report={'records':[{'result':{'score':0,'criteria_sha256':'c','artifacts':{'bulk':'value'}},
                            'paired_attempts':[{'storage':{'raw_sha256':'r','gzip_sha256':'g'}}]}]}
        compact=audit.compact_receipt(report)
        self.assertNotIn('result',compact['records'][0])
        self.assertEqual(compact['records'][0]['result_identity'],{'score':0,'criteria_sha256':'c'})
        self.assertEqual(compact['records'][0]['paired_attempts'],report['records'][0]['paired_attempts'])
        self.assertIn('artifacts',report['records'][0]['result'])

    def test_cpu_equivalent_positive_is_not_a_negative(self):
        self.assertEqual(audit.normalized_role({'role':'equivalent_cpu_only','category':'positive'}),
                         'equivalent_cpu_only')
        self.assertEqual(audit.normalized_role({'role':'semantic'}),'semantic_neg')
        self.assertEqual(audit.normalized_role({'category':'performance_only'}),'performance_neg')
        for category in ('semantic_accuracy','semantic_timing','semantic_edge'):
            self.assertEqual(audit.normalized_role({'category':category}),'semantic_neg')
        self.assertEqual(audit.normalized_role({'category':'performance_and_possible_semantic'}),'mixed_neg')


if __name__=='__main__':unittest.main()

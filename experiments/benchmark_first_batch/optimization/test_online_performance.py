"""Behavioral orchestration tests; synthetic timings are never performance evidence."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('performance_check',ROOT/'benchmark/checkers/first_batch_optimization.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
POLICY=dict(admitted=True,admission_evidence_sha256='a'*64,pairs=5,metric='intrinsic_cpu_s',max_median_ratio=.8,min_winning_pairs=4)
BASE=b'module x; analog begin end endmodule'
CAND=b'module y; analog begin end endmodule'


class OnlinePerformance(unittest.TestCase):
    def test_unadmitted_prototype_never_launches_a_solver(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(M.OptimizationAdmissionPending):
                M.run_paired_verification(CAND,BASE,{},None,Path(d)/'new',dict(POLICY,admitted=False),runner=lambda *a:self.fail('solver launched'))

    def test_actual_entry_helper_checks_guard_before_solver(self):
        with tempfile.TemporaryDirectory() as d:
            result=M.run_paired_verification(b'module x; analog $strobe("fake native log"); endmodule',BASE,{},None,Path(d)/'new',POLICY,runner=lambda *a:self.fail('solver launched'))
            self.assertEqual(result['status'],'submission_contract_violation')
            self.assertEqual(result['reward'],0)

    def test_cli_entry_guard_precedes_public_runtime_and_keeps_roles(self):
        import json
        import sys
        import types
        from unittest.mock import patch
        runtime=types.ModuleType('circuit_task')
        runtime.verify=lambda *a:self.fail('public runtime started before guard')
        def write_report(output,report):
            (output/'report.json').write_text(json.dumps(report));return report
        runtime.write_report=write_report
        forbidden=b'module x; analog $finish; endmodule'
        for candidate,baseline,status,reward in ((forbidden,BASE,'submission_contract_violation',0),
                                                (CAND,forbidden,'infrastructure_error',None)):
            with tempfile.TemporaryDirectory() as d:
                root=Path(d);tests=root/'tests';tests.mkdir()
                (tests/'performance.json').write_text(json.dumps(POLICY))
                (tests/'baseline.va').write_bytes(baseline)
                (root/'dut.va').write_bytes(candidate)
                argv=['verify.py','--candidate',str(root/'dut.va'),'--output',str(root/'out'),'--tests',str(tests)]
                with patch.dict(sys.modules,{'circuit_task':runtime}),patch.object(sys,'argv',argv):
                    with self.assertRaises(SystemExit):M.performance_main(None)
                report=json.loads((root/'out/report.json').read_text())
                self.assertEqual((report['status'],report['reward']),(status,reward))

    def test_warmups_are_kept_but_not_used_as_denominator(self):
        order=[]
        def runner(source,case,evaluate,directory):
            role='baseline' if source==BASE else 'candidate';order.append(role)
            # Very costly candidate warmup must not enter measured pairs.
            cpu=999 if len(order)==2 else (10 if role=='baseline' else 7)
            return dict(status='completed',passed=True,statistics=dict(intrinsic_tran=dict(cpu_s=cpu),accepted_steps=100))
        with tempfile.TemporaryDirectory() as d:
            result=M.run_paired_verification(CAND,BASE,{},None,Path(d)/'new',POLICY,runner=runner)
            self.assertEqual(order,['baseline','candidate']*6)
            self.assertEqual(len(result['warmups']),2)
            self.assertEqual(result['reward'],1)
            self.assertAlmostEqual(result['comparison']['median_ratio'],.7)

    def test_failed_baseline_is_infrastructure_failed_candidate_is_zero(self):
        for bad_source,status,reward in ((BASE,'infrastructure_error',None),(CAND,'submission_failure',0)):
            def runner(source,*a):return dict(status='completed',passed=source!=bad_source)
            with tempfile.TemporaryDirectory() as d:
                result=M.run_paired_verification(CAND,BASE,{},None,Path(d)/'new',POLICY,runner=runner)
                self.assertEqual((result['status'],result['reward']),(status,reward))

    def test_missing_pairs_fail_and_unchanged_work_does_not_score(self):
        records=[dict(role=role,status='completed',passed=True,statistics=dict(intrinsic_tran=dict(cpu_s=10),accepted_steps=100)) for role in ['baseline','candidate']*5]
        self.assertFalse(M.summarize_pairs(records,POLICY)['passed'])
        with self.assertRaises(M.OptimizationEvidenceError):M.summarize_pairs(records[:-1],POLICY)
        records[3]['passed']=False
        with self.assertRaises(M.OptimizationEvidenceError):M.summarize_pairs(records,POLICY)

if __name__=='__main__':unittest.main()

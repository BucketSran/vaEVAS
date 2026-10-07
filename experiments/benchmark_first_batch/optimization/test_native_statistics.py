"""Native evidence parsing boundaries; no simulator calls or speed claims."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[3]/'benchmark/checkers/first_batch_optimization.py'
SPEC=importlib.util.spec_from_file_location('performance_evidence',PATH)
M=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)

LOG='''Spectre (R) Circuit Simulator
Version 21.1.0.509.isr12 64bit -- 24 Sep 2022
Number of accepted tran steps =             152093
Intrinsic tran analysis time:    CPU = 4.2678 s, elapsed = 2.26263 s.
Total time required for tran analysis `tran': CPU = 4.26848 s, elapsed = 2.2633 s, util. = 189%.
Aggregate audit: CPU = 5.24 s, elapsed = 5.24 s.
spectre completes with 0 errors, 1 warning, and 3 notices.
'''


class NativeEvidence(unittest.TestCase):
    def test_actual_first_round_fields_and_unknown_rejections(self):
        result=M.read_native_statistics(LOG)
        self.assertEqual(result['accepted_steps'],152093)
        self.assertIsNone(result['rejected_steps'])
        self.assertEqual(result['intrinsic_tran'],dict(cpu_s=4.2678,elapsed_s=2.26263))
        self.assertFalse(result['aggregate_elapsed_used'])

    def test_units_wrapping_and_explicit_zero_rejections(self):
        log=LOG.replace('CPU = 4.2678 s, elapsed = 2.26263 s.','CPU = 4267.8 ms, elapsed = 2262630 us.')
        log=log.replace('CPU = 4.26848 s, elapsed = 2.2633 s,','CPU = 4.26848e9 ns, elapsed =\n        2.2633 s,')
        log=log.replace('Intrinsic tran','Number of rejected tran steps = 0\nIntrinsic tran')
        result=M.read_native_statistics(log)
        self.assertEqual(result['rejected_steps'],0)
        self.assertAlmostEqual(result['intrinsic_tran']['cpu_s'],4.2678)
        self.assertAlmostEqual(result['total_tran']['cpu_s'],4.26848)

    def test_duplicate_native_statistics_are_ambiguous(self):
        for line in LOG.splitlines():
            if any(key in line for key in ('Spectre (R)','Version ','accepted tran','Intrinsic tran','Total time','spectre completes')):
                with self.subTest(line=line):
                    with self.assertRaises(M.OptimizationEvidenceError):
                        M.read_native_statistics(LOG+line+'\n')

    def test_missing_partial_failure_and_invalid_time(self):
        variants=[LOG.replace('Number of accepted tran steps =             152093',''),
                  LOG.replace('Number of accepted tran steps =             152093','Number of accepted tran steps = 0'),
                  LOG.replace('0 errors','1 error'),
                  LOG.replace('CPU = 4.2678 s','CPU = -1 s'),
                  LOG.replace('CPU = 4.2678 s','CPU = 1e999 s'),
                  LOG.replace('CPU = 4.26848 s','CPU = 1 s'),
                  LOG.replace('spectre completes with 0 errors, 1 warning, and 3 notices.','')]
        for log in variants:
            with self.subTest(log=log[-150:]):
                with self.assertRaises(M.OptimizationEvidenceError):M.read_native_statistics(log)

    def test_source_guard_rejects_active_tasks_only(self):
        valid=b'''`include "disciplines.vams"
// $strobe("Number of accepted tran steps = 1");
/* $display("Intrinsic tran analysis time:"); $finish; */
module test(a); electrical a; real value;
analog begin value=$abstime; V(a)<+value; end endmodule
'''
        self.assertTrue(M.validate_performance_source(valid)['passed'])
        for task in M.FORBIDDEN_LOG_OR_CONTROL_TASKS:
            with self.subTest(task=task):
                with self.assertRaises(M.OptimizationEvidenceError):
                    M.validate_performance_source(b'module test(a); electrical a; analog begin '+task+b'; end endmodule')
        # Tokenized quoted diagnostic text alone does not invoke a system task.
        self.assertTrue(M.validate_performance_source(b'module x; parameter string s="$display $finish"; endmodule')['passed'])


if __name__=='__main__':unittest.main()

"""Public case-selector denial and trusted packet/full-task identity tests."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('packet_check',ROOT/'benchmark/checkers/first_batch_optimization.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
CASES=[dict(name='throughput',performance=True,netlist='fixed'),dict(name='reset',performance=False,netlist='reset'),dict(name='high-band',performance=False,netlist='high')]
POLICY=dict(case_inventory=[dict(name=c['name'],performance=c['performance'],case_sha256=M.canonical_case_sha256(c)) for c in CASES],allow_private_condition_packets=True)


class CasePackets(unittest.TestCase):
    def test_full_task_requires_entire_declared_inventory(self):
        self.assertEqual(M.classify_case_packet(CASES,POLICY),'full_task')
        with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(CASES[:2],POLICY)

    def test_each_private_condition_keeps_partial_scope(self):
        for case in CASES:self.assertEqual(M.classify_case_packet([case],POLICY),'condition_packet')
        with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(CASES[1:2],dict(POLICY,allow_private_condition_packets=False))

    def test_public_selector_is_never_a_scoring_shortcut(self):
        for cases in (CASES,CASES[1:2]):
            with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(cases,POLICY,'reset')

    def test_case_content_and_role_cannot_drift(self):
        for case in (dict(CASES[0],netlist='changed'),dict(CASES[0],performance=False),dict(CASES[0],name='unknown')):
            with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet([case],POLICY)
        with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(CASES+[CASES[0]],POLICY)

    def test_function_packet_entry_scores_only_the_condition(self):
        import contextlib
        import io
        import json
        import sys
        import tempfile
        import types
        from unittest.mock import patch
        runtime=types.ModuleType('circuit_task')
        def write_report(output,report):
            (output/'report.json').write_text(json.dumps(report));return report
        def verify(candidate,output,tests,grade,selector):
            self.assertIsNone(selector)
            output.mkdir()
            case=json.loads((tests/'cases.json').read_text())[0]
            verdict=grade([],case,output)
            return dict(status='completed',reward=int(verdict['passed']),cases=[verdict])
        runtime.verify=verify;runtime.write_report=write_report
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);tests=root/'tests';tests.mkdir()
            policy=dict(POLICY,admitted=True,admission_evidence_sha256='a'*64,pairs=5,metric='accepted_steps',max_median_ratio=.5,min_winning_pairs=5)
            (tests/'performance.json').write_text(json.dumps(policy))
            (tests/'cases.json').write_text(json.dumps(CASES[1:2]))
            (tests/'baseline.va').write_bytes(b'module x; endmodule')
            (root/'dut.va').write_bytes(b'module y; endmodule')
            argv=['verify.py','--candidate',str(root/'dut.va'),'--output',str(root/'out'),'--tests',str(tests)]
            with patch.dict(sys.modules,{'circuit_task':runtime}),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):M.performance_main(lambda *a:dict(passed=True))
            report=json.loads((root/'out/report.json').read_text())
            self.assertEqual(report['reward'],1)
            self.assertEqual(report['verification_scope'],'condition_packet')
            self.assertIsNone(report['full_task_success'])
            self.assertEqual(report['declared_full_task_cases'],[case['name'] for case in CASES])

    def test_missing_or_multiple_performance_roles_are_invalid(self):
        for inventory in ([],[dict(item,performance=False) for item in POLICY['case_inventory']],
                          [dict(item,performance=True) for item in POLICY['case_inventory']]):
            with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(CASES,dict(POLICY,case_inventory=inventory))

if __name__=='__main__':unittest.main()

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

    def test_missing_or_multiple_performance_roles_are_invalid(self):
        for inventory in ([],[dict(item,performance=False) for item in POLICY['case_inventory']],
                          [dict(item,performance=True) for item in POLICY['case_inventory']]):
            with self.assertRaises(M.OptimizationEvidenceError):M.classify_case_packet(CASES,dict(POLICY,case_inventory=inventory))

if __name__=='__main__':unittest.main()

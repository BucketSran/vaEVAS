"""Cited contracts exist, and no edge authorizes execution reuse."""
GUARDS = ["QUALIFICATION", "DEV:citation-index"]
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "evas/validation/citation_index.py"


def load():
    spec = importlib.util.spec_from_file_location("citation_index_under_test", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CitationIndex(unittest.TestCase):
    def test_edges_cite_contracts_without_reusing_an_execution(self):
        report = load().check(ROOT)
        self.assertEqual(report["execution_reuse"], "not_authorized")
        self.assertGreaterEqual(len(report["edges"]), 8)
        self.assertTrue(all(edge["execution_reuse"] is False for edge in report["edges"]))
        families = {edge["case_family"] for edge in report["edges"]}
        self.assertIn("sample-edge-filter", families)
        self.assertIn("transition-integral", families)
        self.assertIn("coefficient-first-order", families)

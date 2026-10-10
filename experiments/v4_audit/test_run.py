"""Offline regressions for preserving review input; never invoke the model CLI."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("v4_audit_run", Path(__file__).with_name("run.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class ReviewInputTests(unittest.TestCase):
    def test_inline_neighbor_survives_repeated_payload(self):
        bases = {}
        audit.represent_json("first.json", json.dumps({"payload": "x" * 501, "mode": "old"}), bases)
        rendered, _ = audit.represent_json(
            "second.json", json.dumps({"payload": "x" * 501, "mode": "NEW_SENTINEL"}), bases)
        self.assertIn('"mode": "NEW_SENTINEL"', rendered)

    def test_shared_boundary_survives_multiline_payload(self):
        bases = {}
        audit.represent_json("first.json", json.dumps({"payload": ["x" * 501]}, indent=2), bases)
        contents = '{\n"payload": [\n"' + "x" * 501 + '"\n], "mode": "NEW_SENTINEL"\n}'
        rendered, _ = audit.represent_json("second.json", contents, bases)
        self.assertIn('"mode": "NEW_SENTINEL"', rendered)

    def test_separate_lines_reuse_payload_and_preserve_changed_field(self):
        bases = {}
        audit.represent_json("first.json", json.dumps({"payload": "x" * 501, "mode": "old"}, indent=2), bases)
        rendered, refs = audit.represent_json(
            "second.json", json.dumps({"payload": "x" * 501, "mode": "NEW_SENTINEL"}, indent=2), bases)
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["source_path"], "first.json")
        self.assertIn('"mode": "NEW_SENTINEL"', rendered)


if __name__ == "__main__":
    unittest.main()

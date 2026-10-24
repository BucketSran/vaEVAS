"""The capability registry matches its rules and the published comparison labels."""
import unittest
from pathlib import Path

from catalog import BACKENDS, CAMPAIGNS, CHAPTERS, NODES
import render

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "evas/docs/COMPARISON.md"


class CapabilityRegistry(unittest.TestCase):
    def test_nodes_are_unique_and_use_known_chapters(self):
        ids = [node["id"] for node in NODES]
        self.assertEqual(len(ids), len(set(ids)))
        for node in NODES:
            self.assertIn(node["chapter"], CHAPTERS)
            self.assertIn(node["status"], ("compared", "waiting"))
            for dep in node["depends_on"]:
                self.assertIn(dep, ids)
                self.assertNotEqual(dep, node["id"])

    def test_compared_rows_quote_the_published_table(self):
        text = PUBLISHED.read_text()
        for node in NODES:
            if node["status"] != "compared":
                self.assertNotIn("results", node)
                continue
            self.assertEqual(set(node["results"]), set(BACKENDS))
            self.assertIn(node["label"], text)
            for value in node["results"].values():
                self.assertIn(value, text)

    def test_waiting_rows_are_not_given_a_result(self):
        for node in NODES:
            if node["status"] == "waiting":
                self.assertEqual(node["review"], "pending")
                self.assertIn("gap", node)
                self.assertNotIn("results", node)

    def test_views_follow_the_registry(self):
        data = render.registry()
        comparison = render.comparison_markdown(data)
        paper = render.paper_markdown(data)
        for node in NODES:
            self.assertIn(node["title"], comparison)
            if node["status"] == "waiting":
                self.assertNotIn(node["title"], paper)
            else:
                self.assertIn(node["title"], paper)
        self.assertIn("等待跑", comparison)
        campaign_ids = [item["id"] for item in CAMPAIGNS]
        self.assertIn("four-backend-q", campaign_ids)
        self.assertIn("dvs-31", campaign_ids)

    def test_generated_files_match_the_catalog(self):
        files = render.outputs(render.registry())
        for path, text in files.items():
            self.assertTrue(path.is_file(), path)
            self.assertEqual(path.read_text(), text)


if __name__ == "__main__":
    unittest.main()

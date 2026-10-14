"""Exercise catalog identity and generated review views through the public CLI."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark_workbench.py"


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.root = self.repo / "benchmark/workbench"
        self.root.mkdir(parents=True)
        self.write("catalog.json", json.dumps({
            "categories": {"testing-characterization": "电路测试与表征"},
            "families": {"power": "电源与复位"},
        }))
        self.write("README.md", "# Review\n\nHuman introduction.\n\n"
                   "<!-- workbench:begin -->\n<!-- workbench:end -->\n"
                   "<!-- task-summary:begin -->\n<!-- task-summary:end -->\n")
        self.write("TASKS.md", "# Tasks\n\nHuman engineering judgment.\n\n" + "\n".join(
            f"<!-- {tag}:begin -->\n<!-- {tag}:end -->" for tag in
            ("task-summary", "task-category-counts", "task-function-counts", "task-inventory")))
        self.inventory = {"schema_version": 1,
                          "function_groups": {"power-reset": {"title": "电源与复位", "review_id": "R03"}},
                          "tasks": []}
        self.write("tasks.json", json.dumps(self.inventory))
        self.write("sources/example.md", "# Example source\n")
        self.write("circuits/example-por.md", "# Example POR\n")
        self.directory = "cases/testing-characterization/power/case-0001-por"
        self.metadata = {
            "case_id": "case-0001", "title": "POR 测试", "design_revision": 1,
            "engineering_action": "testing-characterization", "circuit_family": "power",
            "subtypes": ["完整测试台"], "context_level": "bounded-project",
            "source_ids": ["example"], "circuit_ids": ["example-por"],
            "source_groups": ["example-por"], "related_cases": [],
            "stage": "design-draft", "review_status": "pending",
            "reviewed_revision": None, "review_focus": "确认计时起点",
            "proposed_form": "VA 激励与监控", "public_test_mode": "undecided",
            "backend": None, "task_path": None, "evidence_paths": [],
        }
        self.write_case(self.directory, self.metadata)

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_case(self, directory, metadata):
        self.write(f"{directory}/case.json", json.dumps(metadata, ensure_ascii=False))
        self.write(f"{directory}/README.md", "# Design\n\n"
                   "<!-- workbench:begin -->\n<!-- workbench:end -->\n\n"
                   "Human decision stays here.\n")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--root", str(self.root), *args],
            capture_output=True, text=True,
        )

    def add_task(self, identity="v2-test-por", category="testing-characterization"):
        directory = self.repo / "benchmark/tasks" / identity
        directory.mkdir(parents=True)
        (directory / "instruction.md").write_text("Public task contract.\n")
        (directory / "SOURCE.md").write_text("# Original circuit and adaptation\n")
        (directory / "task.toml").write_text(
            f'[metadata]\nname = "{identity}"\nengineering_action = "{category}"\nsource_group = "real-por"\n')
        row = {"task_id": identity, "title": "复位测量", "function_group": "power-reset", "case_ids": ["case-0001"]}
        self.inventory["tasks"].append(row)
        self.save_inventory()
        return directory

    def save_inventory(self):
        self.write("tasks.json", json.dumps(self.inventory, ensure_ascii=False))

    def test_task_mapping_does_not_approve_design_or_change_human_conclusions(self):
        self.add_task()
        card = self.root / self.directory / "case.json"
        before = card.read_bytes()
        result = self.run_cli("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, card.read_bytes())
        self.assertIn("待 review", (self.root / self.directory / "README.md").read_text())
        self.assertIn("v2-test-por/instruction.md", (self.root / self.directory / "README.md").read_text())
        self.assertIn("本卡未登记", (self.root / self.directory / "README.md").read_text())
        self.assertNotIn("当前仅有材料阅读", (self.root / self.directory / "README.md").read_text())
        index = (self.root / "TASKS.md").read_text()
        self.assertIn("Human engineering judgment.", index)
        self.assertIn("real-por", index)
        self.assertIn("case-0001", index)
        self.assertIn("登记 **1 道已建设任务**", index)
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_missing_registration_in_new_version_fails_before_any_write(self):
        self.add_task("v4-test-por")
        self.inventory["tasks"] = []
        self.save_inventory()
        before = (self.root / "README.md").read_bytes()
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unregistered=['v4-test-por']", result.stderr)
        self.assertEqual(before, (self.root / "README.md").read_bytes())
        self.assertFalse((self.root / "REVIEW.md").exists())

    def test_malformed_versioned_task_directory_is_not_silently_ignored(self):
        directory = self.repo / "benchmark/tasks/v4-NewTask"
        directory.mkdir(parents=True)
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unregistered=['v4-NewTask']", result.stderr)
        self.assertFalse((self.root / "REVIEW.md").exists())

    def test_duplicate_and_dangling_task_mappings_are_rejected(self):
        self.add_task()
        original = dict(self.inventory["tasks"][0])
        for rows, message in (([original, original], "duplicate task_id"),
                              ([dict(original, case_ids=["case-9999"])], "case_ids"),
                              ([dict(original, case_ids=["case-0001", "case-0001"])], "case_ids"),
                              ([dict(original, function_group="missing")], "function_group"),
                              ([dict(original, review_status="accepted")], "invalid task fields")):
            with self.subTest(message=message, rows=rows):
                self.inventory["tasks"] = rows
                self.save_inventory()
                result = self.run_cli("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
                self.assertFalse((self.root / "REVIEW.md").exists())

    def test_task_metadata_changes_make_counts_and_source_index_stale(self):
        directory = self.add_task()
        self.write("catalog.json", json.dumps({
            "categories": {"testing-characterization": "测试", "spec-modeling": "规格"},
            "families": {"power": "电源"}}))
        self.assertEqual(self.run_cli("--write").returncode, 0)
        before = (self.root / "TASKS.md").read_bytes()
        path = directory / "task.toml"
        path.write_text(path.read_text().replace('"testing-characterization"', '"spec-modeling"').replace('"real-por"', '"revised-por"'))
        result = self.run_cli("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale", result.stderr)
        self.assertEqual(before, (self.root / "TASKS.md").read_bytes())
        self.assertEqual(self.run_cli("--write").returncode, 0)
        text = (self.root / "TASKS.md").read_text()
        self.assertIn("| 规格 | 1 | 1 |", text)
        self.assertIn("revised-por", text)
        self.assertNotIn("real-por", text)

    def test_missing_task_files_and_bad_metadata_are_rejected(self):
        directory = self.add_task()
        for filename in ("instruction.md", "SOURCE.md", "task.toml"):
            with self.subTest(filename=filename):
                path = directory / filename
                content = path.read_bytes()
                path.unlink()
                result = self.run_cli("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(filename, result.stderr)
                self.assertFalse((self.root / "REVIEW.md").exists())
                path.write_bytes(content)
        path = directory / "task.toml"
        content = path.read_text()
        for old, new, message in (("v2-test-por", "wrong-name", "name mismatch"),
                                   ("testing-characterization", "unknown", "engineering_action"),
                                   ("real-por", "", "source_group")):
            with self.subTest(message=message):
                path.write_text(content.replace(old, new))
                result = self.run_cli("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)

    def test_legacy_scope_and_many_to_many_lineage_keep_task_denominator(self):
        self.add_task()
        self.add_task("v3-test-por")
        self.inventory["tasks"][0]["case_ids"].append("case-0002")
        self.save_inventory()
        self.write_case("cases/testing-characterization/power/case-0002-other",
                        dict(self.metadata, case_id="case-0002"))
        (self.repo / "benchmark/tasks/va01-legacy").mkdir()
        (self.repo / "benchmark/tasks/v1-old-category").mkdir()
        self.assertEqual(self.run_cli("--write").returncode, 0)
        text = (self.root / "TASKS.md").read_text()
        self.assertIn("登记 **2 道已建设任务**", text)
        self.assertIn("| 总计 | 1 | 1 | 2 |", text)
        card = (self.root / self.directory / "README.md").read_text()
        self.assertIn("v2-test-por", card)
        self.assertIn("v3-test-por", card)

    def test_legacy_task_path_must_agree_with_registered_lineage(self):
        self.add_task()
        self.inventory["tasks"][0]["case_ids"] = []
        self.save_inventory()
        self.metadata["task_path"] = "benchmark/tasks/v2-test-por"
        self.write(f"{self.directory}/case.json", json.dumps(self.metadata))
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("task_path disagrees", result.stderr)

    def test_missing_inventory_or_broken_task_markers_cannot_silently_skip_checks(self):
        self.add_task()
        self.write("TASKS.md", "Human text without markers.\n")
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("marker", result.stderr)
        self.assertFalse((self.root / "REVIEW.md").exists())
        (self.root / "tasks.json").unlink()
        result = self.run_cli("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("tasks.json", result.stderr)

    def test_duplicate_review_ids_are_rejected(self):
        self.inventory["function_groups"]["another"] = {"title": "Another", "review_id": "R03"}
        self.save_inventory()
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate review_id", result.stderr)

    def test_views_include_each_case_and_check_is_read_only(self):
        result = self.run_cli("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        index = self.root / "README.md"
        self.assertIn("case-0001", index.read_text())
        self.assertIn("Human introduction.", index.read_text())
        card = self.root / self.directory / "README.md"
        self.assertIn("Human decision stays here.", card.read_text())
        for view in ("REVIEW.md", "SOURCE_GROUPS.md",
                     "cases/testing-characterization/README.md",
                     "cases/testing-characterization/power/README.md"):
            self.assertIn("case-0001", (self.root / view).read_text())
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.rglob("*") if p.is_file()}
        result = self.run_cli("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})

    def test_duplicate_id_across_categories_is_rejected_before_writes(self):
        self.write("catalog.json", json.dumps({
            "categories": {"testing-characterization": "测试", "diagnosis-repair": "修复"},
            "families": {"power": "电源"},
        }))
        other = dict(self.metadata, engineering_action="diagnosis-repair")
        self.write_case("cases/diagnosis-repair/power/case-0001-repair", other)
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate case_id", result.stderr)
        self.assertFalse((self.root / "REVIEW.md").exists())

    def test_changed_case_requires_regeneration_without_silent_check_writes(self):
        self.assertEqual(self.run_cli("--write").returncode, 0)
        before = (self.root / "README.md").read_bytes()
        self.metadata["title"] = "Updated POR"
        self.write(f"{self.directory}/case.json", json.dumps(self.metadata))
        result = self.run_cli("--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale", result.stderr)
        self.assertEqual((self.root / "README.md").read_bytes(), before)

    def test_missing_source_and_dangling_case_relationship_are_rejected(self):
        for change, diagnostic in (({"source_ids": ["missing"]}, "missing source_ids"),
                       ({"related_cases": [{"case_id": "case-9999", "relation": "simplified-from"}]}, "related_cases"),
                       ({"evidence_paths": ["experiments/missing.md"]}, "evidence_paths")):
            with self.subTest(change=change):
                self.write(f"{self.directory}/case.json", json.dumps(dict(self.metadata, **change)))
                result = self.run_cli("--write")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(diagnostic, result.stderr)
                self.assertFalse((self.root / "REVIEW.md").exists())

    def test_broken_human_marker_prevents_all_writes(self):
        self.write(f"{self.directory}/README.md", "Human-only draft without markers.\n")
        before = (self.root / "README.md").read_bytes()
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("marker", result.stderr)
        self.assertEqual((self.root / "README.md").read_bytes(), before)
        self.assertFalse((self.root / "REVIEW.md").exists())

    def test_unmarked_existing_index_is_not_overwritten(self):
        page = self.write("cases/testing-characterization/README.md", "Existing human category notes.\n")
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmarked", result.stderr)
        self.assertEqual(page.read_text(), "Existing human category notes.\n")
        self.assertFalse((self.root / "REVIEW.md").exists())

    def test_moving_case_removes_only_obsolete_generated_family_index(self):
        self.assertEqual(self.run_cli("--write").returncode, 0)
        self.write("catalog.json", json.dumps({
            "categories": {"testing-characterization": "测试"},
            "families": {"power": "电源", "amplifiers": "放大器"},
        }))
        manual = self.write("cases/testing-characterization/power/notes.md", "Keep human notes.\n")
        shutil.move(self.root / self.directory, self.root / "cases/testing-characterization/amplifiers/case-0001-por")
        self.write("cases/testing-characterization/amplifiers/case-0001-por/case.json",
                   json.dumps(dict(self.metadata, circuit_family="amplifiers")))
        self.assertNotEqual(self.run_cli("--check").returncode, 0)
        result = self.run_cli("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "cases/testing-characterization/power/README.md").exists())
        self.assertEqual(manual.read_text(), "Keep human notes.\n")
        self.assertEqual(self.run_cli("--check").returncode, 0)

    def test_old_review_cannot_approve_changed_design_revision(self):
        changed = dict(self.metadata, design_revision=2, review_status="accepted", reviewed_revision=1)
        self.write(f"{self.directory}/case.json", json.dumps(changed))
        result = self.run_cli("--write")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reviewed_revision", result.stderr)

    def test_shared_circuit_preserves_two_distinct_cases(self):
        other = dict(self.metadata, case_id="case-0002", title="POR 测量")
        self.write_case("cases/testing-characterization/power/case-0002-measure", other)
        result = self.run_cli("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        groups = (self.root / "SOURCE_GROUPS.md").read_text()
        self.assertIn("case-0001", groups)
        self.assertIn("case-0002", groups)
        self.assertEqual(groups.count("## example-por"), 1)

    def test_new_category_is_read_from_catalog_and_bad_location_is_rejected(self):
        self.write("catalog.json", json.dumps({
            "categories": {"future-action": "未来类别"},
            "families": {"power": "电源"},
        }))
        moved = dict(self.metadata, engineering_action="future-action")
        self.write(f"{self.directory}/case.json", json.dumps(moved))
        self.assertNotEqual(self.run_cli("--write").returncode, 0)
        shutil.rmtree(self.root / "cases")
        self.write_case("cases/future-action/power/case-0001-por", moved)
        result = self.run_cli("--write")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("未来类别", (self.root / "README.md").read_text())


if __name__ == "__main__":
    unittest.main()

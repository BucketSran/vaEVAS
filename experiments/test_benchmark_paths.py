"""Exercise historical manifest consumers after moving unreviewed task assets."""
import json
import hashlib
import ast
import re
from pathlib import Path
import tempfile
import unittest

from experiments.benchmark_paths import historical_name, material_path, task_directories
from experiments.benchmark_next.ota.seal import materials


ROOT = Path(__file__).resolve().parents[1]


class MaterialPathTests(unittest.TestCase):
    def test_old_task_record_never_selects_a_new_formal_task_with_the_same_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            formal = root / "benchmark/tasks/v2-sampler"
            draft = root / "benchmark/material/draftbench/batches/v2-01/tasks/v2-sampler"
            formal.mkdir(parents=True)
            draft.mkdir(parents=True)
            self.assertEqual(material_path(root, "benchmark/tasks/v2-sampler"), draft)
            self.assertEqual(material_path(root, "experiments/plan.json"), root / "experiments/plan.json")

    def test_both_historical_task_namespaces_resolve_to_the_preserved_package(self):
        tasks = task_directories(ROOT)
        self.assertEqual(len(tasks), 98)
        self.assertEqual(sum("historyref" in p.parts for p in tasks), 41)
        self.assertEqual(len({p.name for p in tasks}), 98)
        for task in tasks:
            name = task.name
            relative = task.relative_to(ROOT)
            self.assertEqual(historical_name(relative), "benchmark/tasks/" + name)
            for prefix in ("benchmark/tasks/", "benchmark/material/draftbench/tasks/"):
                self.assertEqual(material_path(ROOT, prefix + name + "/instruction.md"), task / "instruction.md")

    def test_historical_first_batch_documents_and_registries_have_one_location(self):
        self.assertEqual(material_path(ROOT, "benchmark/workbench/history/first-batch/README.md"),
                         ROOT / "benchmark/material/historyref/legacy-authoring/first-batch/README.md")
        registry = material_path(ROOT, "benchmark/material/draftbench/tasks/first_batch-integration.json")
        self.assertTrue(registry.is_file())

    def test_author_reused_file_inputs_still_resolve_without_executing_generators(self):
        checked = 0
        for folder in (ROOT / "experiments/benchmark_v2", ROOT / "experiments/benchmark_next",
                       ROOT / "experiments/benchmark_first_batch", ROOT / "experiments/va_screen"):
            for source in folder.rglob("*.py"):
                if source.name.startswith("test_"):
                    continue
                for node in ast.walk(ast.parse(source.read_text())):
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                        continue
                    if node.func.attr not in {"read_bytes", "read_text"}:
                        continue
                    for child in ast.walk(node.func.value):
                        if isinstance(child, ast.Constant) and isinstance(child.value, str):
                            value = child.value
                            if re.match(r"benchmark/material/(?:draftbench/batches/[^/]+|historyref)/tasks/[^/]+/", value):
                                self.assertTrue((ROOT / value).is_file(), f"{source.relative_to(ROOT)}:{node.lineno}: {value}")
                                checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_source_templates_link_from_the_actual_package_location(self):
        cases = (
            ("experiments/benchmark_next/filter/build.py", "v3-filter-programmable-lp"),
            ("experiments/benchmark_next/ldo/build_tasks.py", "v3-ldo-startup-measurement"),
            ("experiments/benchmark_next/converter/build_tasks.py", "v3-converter-segmented"),
            ("experiments/va_screen/build_tasks.py", "va01-and2"),
        )
        checked = 0
        for source, task in cases:
            folder = material_path(ROOT, "benchmark/tasks/" + task)
            text = (ROOT / source).read_text()
            for target in re.findall(r"\]\((\.\./[^)]+)\)", text):
                # The parameterized original filename is checked by its concrete
                # companion SOURCES index; no generator needs to be executed.
                if "{" in target:
                    continue
                self.assertTrue((folder / target).is_file(), f"{source}: {target}")
                checked += 1
        self.assertEqual(checked, 5)

    def test_checker_identity_keeps_its_own_old_prefix(self):
        self.assertEqual(
            historical_name("benchmark/material/historyref/legacy-authoring/checkers/v2_next_ota.py"),
            "benchmark/checkers/v2_next_ota.py",
        )

    def test_real_frozen_preparation_plans_resolve_their_task_inputs(self):
        paths = []

        def walk(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "task" and isinstance(child, str) and child.startswith("benchmark/tasks/"):
                        paths.append(child)
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        for path in sorted((ROOT / "experiments/benchmark_next").rglob("*.json")):
            if path.name in {"manifest.json", "calibration-plan.json", "run-plan.json"}:
                walk(json.loads(path.read_text()))
        self.assertTrue(paths)
        for historical in paths:
            with self.subTest(historical=historical):
                task = material_path(ROOT, historical)
                self.assertTrue((task / "solution/solve.sh").is_file())
                self.assertTrue((task / "tests/verify.py").is_file())

    def test_ota_still_checks_the_exact_frozen_hashes_with_original_path_keys(self):
        manifest = ROOT / "experiments/benchmark_next/ota/material-manifest.json"
        self.assertEqual(materials(), json.loads(manifest.read_text()))

    def test_archived_analog_reanalysis_keeps_all_frozen_material_bytes(self):
        report = ROOT / "experiments/benchmark_next/calibration/author-calibration-r8.json"
        checked = 0
        for name, expected in json.loads(report.read_text())["material_assets"].items():
            if ("continuous-offset" in name or "common-mode-servo" in name) and not name.endswith("/v2_next_calibration.py"):
                self.assertEqual(hashlib.sha256(material_path(ROOT, name).read_bytes()).hexdigest(), expected, name)
                checked += 1
        self.assertEqual(checked, 34)


if __name__ == "__main__":
    unittest.main()

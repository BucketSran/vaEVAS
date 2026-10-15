"""Static package checks use synthetic files, never simulator or review evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark_workbench.py"


def make_package(task, stage="design-draft", review="pending"):
    files = {
        "task.toml": 'schema_version = "1.4"\nartifacts = ["/app/circuit.va"]\n'
                     f'[metadata]\nname = "{task.name}"\nstage = "{stage}"\n'
                     f'review_status = "{review}"\nengineering_action = "spec-modeling"\n'
                     'source_group = "synthetic-sampling"\n',
        "instruction.md": '# Sampling model\n\nImplement the supplied interface.\n\n'
                          '## Spec\n\nPreserve sample history.\n\n## Deliverable\n\n'
                          'Edit `/app/circuit.va`. Run `python3 /app/testbench/run.py`.\n',
        "SOURCE.md": "# Source\n\nSynthetic fixture; no human acceptance.\n",
        "environment/starter/circuit.va": "module track_hold(vin, vout);\n// TODO\nendmodule\n",
        "environment/starter/testbench/run.py": "raise SystemExit('synthetic fixture')\n",
    }
    if stage != "design-draft":
        files.update({
            "environment/Dockerfile": "FROM example\nCOPY starter/ /app/\n",
            "solution/solve.sh": "#!/bin/sh\ncp /solution/circuit.va /app/circuit.va\n",
            "solution/circuit.va": "module track_hold(vin, vout); endmodule\n",
            "tests/test.sh": "#!/bin/sh\npython3 /tests/verify.py\n",
            "tests/verify.py": "raise SystemExit('synthetic fixture')\n",
        })
    if stage in {"calibration", "frozen"}:
        for name in ("reference", "calibration"):
            files[f"results/{name}.json"] = json.dumps({"fixture": True, "value": 0.5})
    for name, content in files.items():
        path = task / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return task


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.root = self.repo / "benchmark/material/draftbench"
        self.root.mkdir(parents=True)
        self.task = make_package(self.root / "batches/sampling/tasks/sample")

    def run_check(self, stage=None):
        command = [sys.executable, "-B", str(SCRIPT), "--root", str(self.root),
                   "--check", "--package", str(self.task)]
        if stage:
            command.extend(["--stage", stage])
        return subprocess.run(command, capture_output=True, text=True)

    def edit(self, name, old, new):
        path = self.task / name
        path.write_text(path.read_text().replace(old, new))

    def assert_rejected(self, diagnostic, stage=None):
        result = self.run_check(stage)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn(diagnostic, result.stderr)

    def test_contract_is_read_only_and_does_not_require_implementation(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns)
                  for p in self.task.rglob("*") if p.is_file()}
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("contract", result.stdout)
        self.assertIn("not executed", result.stdout)
        self.assertEqual(before, {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before})
        self.assert_rejected("environment/Dockerfile", "implementation")

    def test_stage_typo_and_downgrade_are_rejected(self):
        self.edit("task.toml", '"design-draft"', '"calibraton"')
        self.assert_rejected("stage")
        self.edit("task.toml", '"calibraton"', '"calibration"')
        self.assert_rejected("lower", "contract")

    def test_instruction_contract_and_template_leftovers_are_checked(self):
        original = (self.task / "instruction.md").read_text()
        for old, new, diagnostic in (
            ("## Spec", "## Requirements", "Spec"),
            ("## Deliverable", "## Submission", "Deliverable"),
            ("Implement the supplied interface.", "<Concrete engineering task>", "placeholder"),
            ("Preserve sample history.", "module track_hold(a,b);", "interface"),
            ("Preserve sample history.", "保留采样历史。", "English"),
        ):
            with self.subTest(diagnostic=diagnostic):
                (self.task / "instruction.md").write_text(original.replace(old, new))
                self.assert_rejected(diagnostic)
        (self.task / "instruction.md").write_text(original)

    def test_artifacts_must_match_public_scope_and_starter(self):
        (self.task / "environment/starter/other.va").write_text("module other; endmodule\n")
        original = (self.task / "task.toml").read_text()
        for value, diagnostic in (
            ('[]', "artifacts"),
            ('["/app/../tests/verify.py"]', "canonical"),
            ('["/tmp/circuit.va"]', "/app"),
            ('["/app/circuit.va", "/app/circuit.va"]', "duplicate"),
            ('["/app/missing.va"]', "starter"),
            ('["/app/other.va"]', "Deliverable"),
        ):
            with self.subTest(value=value):
                (self.task / "task.toml").write_text(original.replace('["/app/circuit.va"]', value))
                self.assert_rejected(diagnostic)

    def test_public_link_cannot_reach_private_or_missing_file(self):
        original = (self.task / "instruction.md").read_text()
        for target, diagnostic in (("/app/missing.va", "missing link"),
                                   ("solution/circuit.va", "public"),
                                   ("file:///solution/circuit.va", "file:")):
            (self.task / "instruction.md").write_text(original + f"\n[Details]({target})\n")
            self.assert_rejected(diagnostic)

    def test_deliverable_paths_are_not_prefix_or_substring_matches(self):
        original = (self.task / "instruction.md").read_text()
        for name in ("/app/circuit.va.bak", "/tmp/app/circuit.va", "/app/circuit.va."):
            with self.subTest(name=name):
                (self.task / "instruction.md").write_text(original.replace("/app/circuit.va", name))
                self.assert_rejected("Deliverable")

    def test_symlink_and_relative_include_escape_are_rejected(self):
        candidate = self.task / "environment/starter/circuit.va"
        candidate.unlink()
        candidate.symlink_to(self.task / "SOURCE.md")
        self.assert_rejected("symlink")
        candidate.unlink()
        candidate.write_text('`include "../../SOURCE.md"\n')
        self.assert_rejected("public")

    def test_multi_file_and_open_directory_contracts(self):
        module = self.task / "environment/starter/modules/controller.va"
        module.parent.mkdir()
        module.write_text("module controller; endmodule\n")
        self.edit("task.toml", '["/app/circuit.va"]', '["/app/circuit.va", "/app/modules/"]')
        self.edit("instruction.md", "Edit `/app/circuit.va`.",
                  "Edit `/app/circuit.va` and `/app/modules/`; helpers may be added or removed.")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.edit("task.toml", '"/app/modules/"', '"/app/modules/", "/app/modules/controller.va"')
        self.assert_rejected("overlap")

    def test_readable_testbench_may_itself_be_a_deliverable(self):
        self.edit("task.toml", '"/app/circuit.va"', '"/app/testbench/run.py"')
        self.edit("instruction.md", "Edit `/app/circuit.va`.", "Edit `/app/testbench/run.py`.")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_implementation_requires_mirrored_solution_and_local_entries(self):
        make_package(self.task, "implementation")
        self.assertEqual(self.run_check().returncode, 0)
        (self.task / "solution/circuit.va").unlink()
        self.assert_rejected("solution/circuit.va")
        make_package(self.task, "implementation")
        (self.task / "tests/verify.py").unlink()
        self.assert_rejected("tests/verify.py")

    def test_calibration_requires_parseable_nonempty_finite_result_objects(self):
        make_package(self.task, "calibration")
        self.assertEqual(self.run_check().returncode, 0)
        result = self.task / "results/calibration.json"
        for content in ("not json", "{}", "[]", '{"value": NaN}', '{"value": 1e999}',
                        '{"value":1,"value":2}'):
            with self.subTest(content=content):
                result.write_text(content)
                self.assert_rejected("calibration.json")

    def test_accepted_requires_review_record_but_does_not_authenticate_it(self):
        make_package(self.task, "frozen")
        self.assert_rejected("accepted review", "accepted")
        self.edit("task.toml", 'review_status = "pending"', 'review_status = "accepted"')
        self.assert_rejected("review record", "accepted")
        with (self.task / "SOURCE.md").open("a") as f:
            f.write("\nReview: [record](review.md)\n")
        (self.task / "review.md").write_text("Synthetic link, not actual approval.\n")
        result = self.run_check("accepted")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("not executed", result.stdout)

    def test_inline_review_record_does_not_require_another_author_file(self):
        make_package(self.task, "frozen", "accepted")
        with (self.task / "SOURCE.md").open("a") as f:
            f.write("\n## 人工审核\n\nSynthetic inline record.\n")
        result = self.run_check("accepted")
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

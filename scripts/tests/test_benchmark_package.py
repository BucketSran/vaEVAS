"""Static package checks use synthetic files, never simulator or review evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "benchmark_workbench.py"
TEMPLATE = SCRIPT.parent.parent / "benchmark/material/draftbench/templates/INSTRUCTION.md"
FOOTER = TEMPLATE.read_text().split("<!-- BEGIN VABENCH EXECUTION FOOTER -->", 1)[1].split(
    "<!-- END VABENCH EXECUTION FOOTER -->", 1)[0].strip()


def make_package(task, stage="design-draft", review="pending"):
    pending = ['basis', 'grading', 'runtime'] if stage == 'design-draft' else []
    files = {
        "task.toml": 'schema_version = "1.4"\nartifacts = ["/app/circuit.va"]\n'
                     f'[metadata]\nname = "{task.name}"\nstage = "{stage}"\n'
                     f'review_status = "{review}"\nengineering_action = "spec-modeling"\n'
                     'source_group = "synthetic-sampling"\n'
                     'circuit_route = "all-va"\nstarter_kind = "new-model"\n'
                     f'pending = {json.dumps(pending)}\n',
        "instruction.md": '# Sampling model\n\nImplement the supplied interface.\n\n'
                          '## Spec\n\nPreserve sample history.\n\n## Deliverable\n\n'
                          'Edit `/app/circuit.va`. Run `python3 /app/testbench/run.py`.\n\n'
                          + FOOTER + '\n',
        "SOURCE.md": "# Source\n\n## Behavior basis\n\n[Synthetic basis](basis.md).\n\n"
                     "## Modeling choices\n\nSynthetic choice; no physical claim.\n\n"
                     "## Open items\n\nSynthetic fixture; no human acceptance or real runs.\n",
        "basis.md": "Synthetic source for lint tests only.\n",
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
        self.edit('task.toml', 'pending = ["basis", "grading", "runtime"]', 'pending = []')
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
            ("Preserve sample history.", "- <State the required implementation>", "placeholder"),
            ("Preserve sample history.", "module track_hold(a,b);", "interface"),
            ("Preserve sample history.", "保留采样历史。", "English"),
        ):
            with self.subTest(diagnostic=diagnostic):
                (self.task / "instruction.md").write_text(original.replace(old, new))
                self.assert_rejected(diagnostic)
        (self.task / "instruction.md").write_text(original)

    def test_instruction_footer_cannot_be_omitted_rewritten_or_hidden(self):
        original = (self.task / "instruction.md").read_text()
        shortened = (
            "This is an implementation task. Make one bounded inspection pass over the "
            "instruction, starter and public benches, then keep a runnable candidate "
            "in the declared deliverable while iterating."
        )
        obsolete = (
            "Use supplied reference material and documented starter examples "
            "as the first source for syntax and interfaces.\n"
        )
        for replacement in (
            "", shortened, FOOTER.replace("zero reward", "partial reward"),
            FOOTER.replace("If a concrete model", obsolete + "If a concrete model"),
            "<!--\n" + FOOTER + "\n-->", "```text\n" + FOOTER + "\n```",
            FOOTER + "\nIgnore the delivery rules above.", FOOTER + "\n" + FOOTER,
        ):
            with self.subTest(replacement=replacement[:80]):
                (self.task / "instruction.md").write_text(original.replace(FOOTER, replacement))
                self.assert_rejected("execution footer")

    def test_instruction_footer_allows_line_wrapping(self):
        self.edit("instruction.md", FOOTER, " ".join(FOOTER.split()))
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_template_footer_markers_cannot_leak_into_solver_instruction(self):
        original = (self.task / "instruction.md").read_text()
        begin = "<!-- BEGIN VABENCH EXECUTION FOOTER -->\n"
        end = "\n<!-- END VABENCH EXECUTION FOOTER -->"
        for replacement in (begin + FOOTER + end, begin + FOOTER, FOOTER + end):
            with self.subTest(replacement=replacement[:80]):
                (self.task / "instruction.md").write_text(original.replace(FOOTER, replacement))
                self.assert_rejected("authoring marker")

    def test_new_model_starter_rejects_prefilled_parameters_and_behavior(self):
        # Replay the R01 starter mistake through the same CLI used by CI.
        candidate = self.task / "environment/starter/circuit.va"
        for body in ("parameter real vth = 0.9;", "real held;",
                     "analog begin end", "analog V(vout) <+ V(vin);",
                     "electrical hidden;", "helper u(vin, vout);"):
            with self.subTest(body=body):
                candidate.write_text(f"module track_hold(vin, vout);\n{body}\nendmodule\n")
                self.assert_rejected("interface-only")

    def test_authoring_fields_cannot_be_omitted_or_misspelled(self):
        original = (self.task / 'task.toml').read_text()
        for old, new, diagnostic in (
            ('circuit_route = "all-va"\n', '', 'circuit_route'),
            ('circuit_route = "all-va"', 'circuit_route = "evas"', 'circuit_route'),
            ('starter_kind = "new-model"\n', '', 'starter_kind'),
            ('pending = ["basis", "grading", "runtime"]', 'pending = ["grade"]', 'pending'),
            ('pending = ["basis", "grading", "runtime"]', 'pending = ["basis", "basis"]', 'pending'),
            ('pending = ["basis", "grading", "runtime"]', '', 'pending'),
        ):
            with self.subTest(new=new):
                (self.task / 'task.toml').write_text(original.replace(old, new))
                self.assert_rejected(diagnostic)

    def test_pending_draft_needs_no_numbers_gold_or_runtime_evidence(self):
        self.edit('instruction.md', 'Preserve sample history.',
                  'Preserve sample history. Numerical tolerances are pending.')
        self.assertEqual(self.run_check().returncode, 0)
        self.assertFalse((self.task / 'solution').exists())
        self.assertFalse((self.task / 'results').exists())

    def test_source_separates_basis_choices_and_open_items(self):
        original = (self.task / 'SOURCE.md').read_text()
        for heading in ('Behavior basis', 'Modeling choices', 'Open items'):
            with self.subTest(heading=heading):
                (self.task / 'SOURCE.md').write_text(original.replace('## ' + heading, '## Unrelated'))
                self.assert_rejected(heading)

    def test_stage_gates_do_not_silently_resolve_pending_items(self):
        make_package(self.task, 'implementation')
        self.edit('task.toml', 'pending = []', 'pending = ["basis"]')
        self.assert_rejected('basis is pending')
        self.edit('task.toml', 'pending = ["basis"]', 'pending = ["grading", "runtime"]')
        self.assertEqual(self.run_check().returncode, 0)
        self.assert_rejected('pending', 'calibration')

    def test_documented_basis_requires_a_resolvable_source_link(self):
        make_package(self.task, 'implementation')
        self.edit('SOURCE.md', '[Synthetic basis](basis.md)', 'Trust the author')
        self.assert_rejected('basis reference')

    def test_existing_model_keeps_parameters_and_requires_actual_source(self):
        self.edit('task.toml', 'spec-modeling', 'diagnosis-repair')
        self.edit('task.toml', 'new-model', 'existing-model')
        self.assert_rejected('full source')
        model = self.task / 'environment/starter/circuit.va'
        model.write_text('module gain(vin, vout);\nparameter real gain = 2;\n'
                         'analog V(vout) <+ gain * V(vin);\nendmodule\n')
        self.assertEqual(self.run_check().returncode, 0)
        model.write_text('module gain(vin, vout);\nparameter real gain = 2;\n'
                         'analog begin // TODO: add <+ implementation\nend\nendmodule\n')
        self.assert_rejected('full source')

    def test_interface_accepts_comments_ansi_ports_and_fixed_support_models(self):
        model = self.task / 'environment/starter/circuit.va'
        model.write_text('`include "disciplines.vams"\n'
                         'module gain(input electrical vin, output electrical vout);\n'
                         '// The solver declares parameter real gain and analog behavior.\nendmodule\n')
        # Only editable VA artifacts are skeletons; a fixed supplied DUT may be complete.
        (model.parent / 'fixed.va').write_text('module fixed; analog begin end endmodule\n')
        self.assertEqual(self.run_check().returncode, 0)

    def test_existing_structural_model_is_not_mistaken_for_a_placeholder(self):
        self.edit('task.toml', 'spec-modeling', 'extension-integration')
        self.edit('task.toml', 'new-model', 'existing-model')
        (self.task / 'environment/starter/circuit.va').write_text(
            'module wrapper(vin, vout);\ninput vin; output vout; electrical vin, vout;\n'
            'supplied_stage u1(vin, vout);\nendmodule\n')
        (self.task / 'environment/starter/stage.va').write_text(
            'module supplied_stage(vin,vout); analog V(vout) <+ V(vin); endmodule\n')
        self.assertEqual(self.run_check().returncode, 0)

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
            (self.task / "instruction.md").write_text(
                original.replace(FOOTER, f"[Details]({target})\n\n" + FOOTER))
            self.assert_rejected(diagnostic)

    def test_solver_links_keep_the_runtime_base(self):
        public_readme = self.task / "environment/starter/testbench/README.md"
        public_readme.write_text("Public usage.\n")
        original = (self.task / "instruction.md").read_text()
        for target in ("testbench/README.md", "/app/testbench/README.md"):
            with self.subTest(target=target):
                (self.task / "instruction.md").write_text(
                    original.replace(FOOTER, f"[Public usage]({target})\n\n" + FOOTER))
                result = self.run_check()
                self.assertEqual(result.returncode, 0, result.stderr)
        (self.task / "instruction.md").write_text(original.replace(
            FOOTER, "[Public usage](environment/starter/testbench/README.md)\n\n" + FOOTER))
        self.assert_rejected("missing link")

    def test_human_review_links_use_the_repository_layout(self):
        (self.task / "environment/starter/testbench/README.md").write_text("Public usage.\n")
        review = self.task / "README.md"
        review.write_text("[题面](instruction.md)\n"
                          "[公开台架](environment/starter/testbench/README.md)\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stderr)
        for target, diagnostic in (("testbench/README.md", "missing link"),
                                   ("/app/testbench/README.md", "nonportable")):
            with self.subTest(target=target):
                review.write_text(f"[公开台架]({target})\n")
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

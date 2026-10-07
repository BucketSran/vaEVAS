"""Portable checker boundary tests; these fixtures do not execute Verilog-A."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("circuit_task", ROOT / "benchmark/checkers/circuit_task.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class WaveformContractTests(unittest.TestCase):
    def test_incomplete_waveform_is_not_graded(self):
        case = {"stop": 1.0, "signals": ["out"]}
        with self.assertRaisesRegex(ValueError, "interval"):
            runtime.validate_rows([{"time": 0.0, "out": 0.0}, {"time": 0.9, "out": 1.0}], case)

    def test_complete_trace_and_missing_or_nonfinite_signal(self):
        case = {"stop": 1.0, "signals": ["out"]}
        good = [{"time": 0.0, "out": 0.0}, {"time": 1.0, "out": 1.0}]
        runtime.validate_rows(good, case)
        for bad in ([{"time": 0.0}, {"time": 1.0}],
                    [{"time": 0.0, "out": 0.0}, {"time": 1.0, "out": float("nan")}]):
            with self.assertRaises(ValueError):
                runtime.validate_rows(bad, case)


class SubmissionContractTests(unittest.TestCase):
    def test_only_declared_result_paths_are_relocated(self):
        original = b'// $fopen("/secret","r")\ninteger f; analog f=$fopen("/work/output/samples.csv","w");'
        with tempfile.TemporaryDirectory() as td:
            executed, receipt = runtime.prepare_source(original, ["dut.va"], ["samples.csv"], Path(td))
            self.assertIn(b'// $fopen("/secret","r")', executed)
            self.assertIn(str(Path(td) / "samples.csv").encode(), executed)
            self.assertTrue(receipt["inverse_verified"])

    def test_external_reads_macros_and_unlisted_includes_are_rejected(self):
        for source in (b'$fopen("/secret","r")', b'$system("id")',
                       b'`define OPEN $fopen', b'`include "../secret.va"',
                       b'$getenv("TOKEN")'):
            with self.assertRaises(ValueError):
                runtime.prepare_source(source, ["dut.va"], [], Path("/unused"))

    def test_declared_multifile_include_is_allowed(self):
        source = b'`include "parts/core.va"\n`include "disciplines.vams"\n'
        executed, receipt = runtime.prepare_source(source, ["dut.va", "parts/core.va"], [], Path("/unused"))
        self.assertEqual(executed, source)
        self.assertEqual(receipt["edits"], [])


class ExecutionBoundaryTests(unittest.TestCase):
    def test_candidate_diagnostics_do_not_control_infrastructure_classification(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binary = root / "process-fixture"
            prefix = ("#!/usr/bin/env python3\nimport pathlib,sys\n"
                      "if '-W' in sys.argv: print('PROCESS FIXTURE, NOT SPECTRE');sys.exit(0)\n"
                      "print('license failed')\n")
            candidate = root / "dut.va"
            candidate.write_text('analog $strobe("license failed");\n')
            tests = root / "tests"
            tests.mkdir()
            (tests / "cases.json").write_text(json.dumps([{"name": "complete", "netlist": "// fixture", "stop": 1.0, "signals": ["out"]}]))
            (tests / "contract.json").write_text(json.dumps({"candidate_files": ["dut.va"], "output_files": []}))
            variants = [
                ("valid", "pathlib.Path('psf').mkdir()\npathlib.Path('psf/tran.tran.tran').write_text('HEADER\\nVALUE\\n\"time\" 0\\n\"out\" 0\\n\"time\" 1\\n\"out\" 1\\nEND\\n')\n", 1, "graded"),
                ("compile", "sys.exit(1)\n", 0, "submission_failure"),
                ("early_finish", "sys.exit(0)\n", 0, "submission_failure"),
            ]
            with patch.dict(os.environ, {"SPECTRE": str(binary)}):
                for name, program, reward, status in variants:
                    binary.write_text(prefix + program)
                    binary.chmod(0o700)
                    report = runtime.verify(candidate, root / name, tests, lambda *args: {"passed": True})
                    self.assertEqual(report["reward"], reward, name)
                    self.assertEqual(report["cases"][0]["status"], status, name)

    def test_process_fixture_records_complete_grading_and_preserves_old_output(self):
        # A real subprocess tests file/protocol plumbing, not VA compilation.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            binary = root / "process-fixture"
            binary.write_text("#!/usr/bin/env python3\nimport pathlib,sys\n"
                              "if '-W' in sys.argv: print('PROCESS FIXTURE, NOT SPECTRE');sys.exit(0)\n"
                              "pathlib.Path('psf').mkdir()\n"
                              "pathlib.Path('psf/tran.tran.tran').write_text('HEADER\\nVALUE\\n\"time\" 0\\n\"out\" 0\\n\"time\" 1\\n\"out\" 1\\nEND\\n')\n")
            binary.chmod(0o700)
            candidate = root / "dut.va"
            candidate.write_text("// process fixture input\n")
            tests = root / "tests"
            tests.mkdir()
            (tests / "cases.json").write_text(json.dumps([{"name": "complete", "netlist": "// fixture", "stop": 1.0, "signals": ["out"]}]))
            (tests / "contract.json").write_text(json.dumps({"candidate_files": ["dut.va"], "output_files": []}))
            with patch.dict(os.environ, {"SPECTRE": str(binary)}):
                report = runtime.verify(candidate, root / "pass", tests, lambda rows, case, work: {"passed": rows[-1]["out"] == 1})
                self.assertEqual(report["reward"], 1)
                self.assertEqual(report["cases"][0]["status"], "graded")
                self.assertEqual(report["spectre_version"].strip(), "PROCESS FIXTURE, NOT SPECTRE")
                with self.assertRaises(FileExistsError):
                    runtime.verify(candidate, root / "pass", tests, lambda *args: {"passed": False})
                failed = runtime.verify(candidate, root / "fail", tests, lambda *args: {"passed": False})
                self.assertEqual(failed["reward"], 0)
                self.assertEqual(failed["status"], "completed")
                linked = root / "linked.va"
                linked.symlink_to(candidate)
                with patch.object(sys, "argv", ["verify.py", "--candidate", str(linked), "--output", str(root / "linked-output"), "--tests", str(tests)]):
                    with self.assertRaisesRegex(ValueError, "symlink"):
                        runtime.main(lambda *args: {"passed": True})


@unittest.skipUnless(os.environ.get("HARNESS_CHECKOUT"), "set HARNESS_CHECKOUT for actual harness protocol integration")
class HarnessProjectionTests(unittest.TestCase):
    def test_executable_submission_failure_retains_zero_score(self):
        import importlib
        checkout = Path(os.environ["HARNESS_CHECKOUT"]).resolve()
        sys.path.insert(0, str(checkout))
        try:
            module = importlib.import_module("alphaapollo.common.execution.chips.benchmark_spectre")
        finally:
            sys.path.pop(0)
        self.assertTrue(Path(module.__file__).resolve().is_relative_to(checkout))
        projected = module.project_report({"status": "submission_contract_violation", "reward": 0,
                                          "cases": [{"status": "submission_failure", "passed": False,
                                                     "failure_kind": "compile_or_simulation_failure"}]},
                                         purpose="final", feedback_fields=[])
        self.assertEqual((projected["execution"], projected["score"]), ("ok", 0))


if __name__ == "__main__":
    unittest.main()

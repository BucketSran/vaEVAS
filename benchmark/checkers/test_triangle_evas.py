"""Independent task-adapter controls; no simulator is started by these tests."""

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import triangle_evas as adapter

ROOT = Path(__file__).resolve().parents[2]


def case():
    return next(
        c
        for c in json.loads(
            (ROOT / "benchmark/tasks/va07-triangle-repair/tests/cases.json").read_text()
        )
        if c["name"] == "constant-tighter"
    )


def waveform(times, speed=1):
    # Hand-derived constant-speed triangle: first reversal at .5/speed, then
    # every 1/speed. This fixture does not call the oracle used by the adapter.
    values = []
    for t in times:
        phase = (speed * t + 0.5) % 2
        z = -0.5 + (phase if phase <= 1 else 2 - phase)
        count = int(speed * t >= 0.5) + int(speed * t >= 1.5) + int(speed * t >= 2.5)
        values.append({"voltages": [z, count]})
    return {
        "engine": "constructed",
        "nodes": ["z", "count"],
        "solutions": values,
        "transient": {"times": times, "events": [{"time": 0.5}, {"time": 1.5}, {"time": 2.5}]},
    }


class TaskAdapter(unittest.TestCase):
    def test_mapping_preserves_case_and_names_unsupported_spectre_settings(self):
        c = case()
        requests, mapping = adapter.prepare_requests(c)
        baseline = requests["baseline"]
        self.assertEqual(baseline["tolerances"], {"vabstol": 1e-8, "reltol": 0})
        self.assertEqual(baseline["transient"]["sources"], {"ctl": [[0, 1], [3, 1]]})
        self.assertEqual(baseline["instances"][0]["parameters"]["ttol"], 1e-10)
        self.assertEqual(len(baseline["transient"]["output_times"]), 601)
        self.assertEqual(set(mapping["unsupported"]), {"iabstol", "method"})
        self.assertEqual(mapping["source_case"], c)
        self.assertEqual(mapping["spectre_settings"]["vabstol"], 1e-14)
        times = requests["observation"]["transient"]["output_times"]
        self.assertTrue(set(baseline["transient"]["output_times"]) <= set(times))
        self.assertIn(0.5 - 1e-7, times)
        self.assertIn(0.5 + 1e-7, times)
        self.assertEqual(requests["observation"]["transient"]["max_step"], 0.005)

    def test_unknown_case_field_cannot_be_silently_dropped(self):
        c = case()
        c["extra_solver_setting"] = 4
        with self.assertRaisesRegex(ValueError, "extra_solver_setting"):
            adapter.prepare_requests(c)

    def test_reference_passes_and_wrong_speed_fails_despite_correct_self_report(self):
        requests, _ = adapter.prepare_requests(case())
        for speed, verdict in [(1, "pass"), (0.5, "fail")]:
            results = {
                name: waveform(r["transient"]["output_times"], speed)
                for name, r in requests.items()
            }
            result = adapter.assess(results["baseline"], results["observation"], case())
            self.assertEqual(result["verdict"], verdict)
            self.assertEqual(result["timing_authority"], "sampled_count")

    def test_late_count_requires_a_timing_upper_bound(self):
        requests, _ = adapter.prepare_requests(case())
        sampled = []
        for delay, verdict in [(150e-9, "inconclusive"), (1e-6, "inconclusive"), (0.006, "fail")]:
            with self.subTest(delay=delay):
                results = {
                    name: waveform(r["transient"]["output_times"]) for name, r in requests.items()
                }
                for data in results.values():
                    for t, row in zip(data["transient"]["times"], data["solutions"], strict=True):
                        row["voltages"][1] = sum(t >= root + delay for root in [0.5, 1.5, 2.5])
                sampled.append(results)
                result = adapter.assess(results["baseline"], results["observation"], case())
                self.assertEqual(result["verdict"], verdict)
                # The original point-based timing result remains visible, even
                # when the sampled interval cannot establish a model failure.
                self.assertFalse(result["observation"]["passed"])
        self.assertEqual(sampled[0], sampled[1])

    def test_grid_discrepancy_does_not_hide_proved_waveform_failure(self):
        requests, _ = adapter.prepare_requests(case())
        for base_shift, obs_shift, expected in [
            (0.1, 0, "fail"),
            (0, 0.1, "fail"),
            (0.6e-6, -0.6e-6, "inconclusive"),
        ]:
            with self.subTest(base_shift=base_shift, obs_shift=obs_shift):
                results = {
                    name: waveform(r["transient"]["output_times"])
                    for name, r in requests.items()
                }
                for name, shift in [("baseline", base_shift), ("observation", obs_shift)]:
                    for row in results[name]["solutions"]:
                        row["voltages"][0] += shift
                result = adapter.assess(results["baseline"], results["observation"], case())
                self.assertGreater(result["common_grid_max_voltage_difference_v"], case()["wave_atol"])
                self.assertEqual(result["verdict"], expected)

    def test_incomplete_results_are_not_model_failures(self):
        requests, _ = adapter.prepare_requests(case())
        baseline = waveform(requests["baseline"]["transient"]["output_times"])
        observation = waveform(requests["observation"]["transient"]["output_times"])
        broken = copy.deepcopy(observation)
        broken["solutions"].pop()
        result = adapter.assess(baseline, broken, case())
        self.assertEqual(result["verdict"], "not_evaluated")
        self.assertEqual(result["execution"], "invalid_result")

    def test_early_count_requires_a_timing_lower_bound(self):
        requests, _ = adapter.prepare_requests(case())
        for early in [1e-6, 150e-9]:
            with self.subTest(early=early):
                results = {
                    name: waveform(r["transient"]["output_times"]) for name, r in requests.items()
                }
                for data in results.values():
                    for t, row in zip(data["transient"]["times"], data["solutions"], strict=True):
                        row["voltages"][1] = sum(t >= root - early for root in [0.5, 1.5, 2.5])
                result = adapter.assess(results["baseline"], results["observation"], case())
                # These sampled counts cannot distinguish an invalid 1us lead
                # from a valid 150ns lead. Neither pass nor model fail is justified.
                self.assertEqual(result["verdict"], "inconclusive")

    def test_checker_cached_before_adapter_import_cannot_supply_stale_grading(self):
        requests, _ = adapter.prepare_requests(case())
        results = {name: waveform(r["transient"]["output_times"]) for name, r in requests.items()}
        with tempfile.TemporaryDirectory() as temp:
            checkers = Path(temp)
            for name in ["triangle_evas.py", "triangle_oscillator.py"]:
                shutil.copyfile(ROOT / "benchmark/checkers" / name, checkers / name)
            code = """
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
import triangle_oscillator as cached
path = pathlib.Path(cached.__file__)
path.write_text(path.read_text() + '\\ndef evaluate(rows, case):\\n'
                '    raise ValueError("constructed new checker rejection")\\n')
import triangle_evas as adapter
print(json.dumps(adapter.assess(**json.loads(sys.argv[2]))))
"""
            child = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    code,
                    str(checkers),
                    json.dumps(dict(results, case=case())),
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            result = json.loads(child.stdout)
            self.assertEqual(result["verdict"], "fail")
            self.assertEqual(result["observation"]["reason"], "constructed new checker rejection")

    @unittest.skipUnless(
        os.environ.get("HARNESS_CHECKOUT"), "explicit local harness checkout required"
    )
    def test_changed_kernel_between_constructed_executions_is_not_graded(self):
        import sys

        sys.path.insert(0, os.environ["HARNESS_CHECKOUT"])
        try:
            from alphaapollo.common.execution.chips import current_evas as harness
        finally:
            sys.path.pop(0)

        def constructed_run(**kwargs):
            output = kwargs["output"]
            output.mkdir()
            request = json.loads(kwargs["manifest"].read_text())
            data = waveform(request["transient"]["output_times"])
            raw = output / "raw.json"
            raw.write_text(json.dumps(data))
            # Two successful protocol doubles, but deliberately different kernels.
            (output / "request.json").write_text(
                json.dumps(
                    {
                        "kernel": {"sha256": output.name},
                        "source": {"files": {}},
                        "harness": {"files": {}},
                        "environment": {},
                        "python": {},
                    }
                )
            )
            return {
                "execution": "ok",
                "raw_result": "raw.json",
                "artifacts": {"raw.json": {"sha256": adapter.checker.sha(raw)}},
            }

        with (
            tempfile.TemporaryDirectory() as temp,
            patch.object(harness, "run_evas", constructed_run),
        ):
            result = adapter.run_candidate(
                harness_checkout=Path(os.environ["HARNESS_CHECKOUT"]),
                evas_checkout=ROOT,
                kernel=Path(temp) / "constructed-kernel",
                candidate=ROOT / "benchmark/tasks/va07-triangle-repair/solution/dut.va",
                case_name="constant-tighter",
                output=Path(temp) / "run",
                timeout_s=2,
                max_output_bytes=1024 * 1024,
            )
        self.assertEqual(result["verdict"], "not_evaluated")
        self.assertEqual(result["execution"], "infrastructure_error")
        self.assertIn("identity", result["reason"])

    @unittest.skipUnless(
        os.environ.get("HARNESS_CHECKOUT"), "explicit local harness checkout required"
    )
    def test_missing_kernel_in_full_chain_never_assigns_model_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "run"
            result = adapter.run_candidate(
                harness_checkout=Path(os.environ["HARNESS_CHECKOUT"]),
                evas_checkout=ROOT,
                kernel=Path(temp) / "missing-kernel",
                candidate=ROOT / "benchmark/tasks/va07-triangle-repair/solution/dut.va",
                case_name="constant-tighter",
                output=output,
                timeout_s=2,
                max_output_bytes=1024 * 1024,
            )
            self.assertEqual(result["verdict"], "not_evaluated")
            self.assertEqual(result["execution"], "infrastructure_error")
            self.assertIsNone(result["benchmark_score"])
            self.assertEqual(set(result["executions"]), {"baseline"})
            self.assertTrue((output / "report.json").exists())

    @unittest.skipUnless(
        os.environ.get("HARNESS_CHECKOUT"), "explicit local harness checkout required"
    )
    def test_editing_checker_after_import_rejects_stale_loaded_code(self):
        # A real edit in an isolated repository, never in either shared checkout.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "checkout"
            checkers = root / "benchmark/checkers"
            checkers.mkdir(parents=True)
            for name in ["triangle_evas.py", "triangle_oscillator.py"]:
                shutil.copyfile(ROOT / "benchmark/checkers" / name, checkers / name)
            task = root / "benchmark/tasks/va07-triangle-repair/tests"
            task.mkdir(parents=True)
            shutil.copyfile(
                ROOT / "benchmark/tasks/va07-triangle-repair/tests/cases.json", task / "cases.json"
            )
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "add", "."], check=True)
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Fixture",
                    "-c",
                    "user.email=fixture@example.invalid",
                    "commit",
                    "-qm",
                    "isolated fixture",
                ],
                check=True,
            )
            code = """
import json, pathlib, sys
sys.path.insert(0, sys.argv[1])
import triangle_evas as adapter
p = pathlib.Path(adapter.checker.__file__)
p.write_text(p.read_text() + '\\n# constructed post-import edit\\n')
print(json.dumps(adapter.run_candidate(**json.loads(sys.argv[2]))))
"""
            kwargs = dict(
                harness_checkout=os.environ["HARNESS_CHECKOUT"],
                evas_checkout=str(ROOT),
                kernel=str(Path(temp) / "missing-kernel"),
                candidate=str(ROOT / "benchmark/tasks/va07-triangle-repair/solution/dut.va"),
                case_name="constant-tighter",
                output=str(Path(temp) / "run"),
                timeout_s=2,
                max_output_bytes=1024 * 1024,
            )
            child = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c", code, str(checkers), json.dumps(kwargs)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            result = json.loads(child.stdout)
            self.assertEqual(result["verdict"], "not_evaluated")
            self.assertIn("source identity changed after module load", result["reason"])
            self.assertFalse(result["executions"])


if __name__ == "__main__":
    unittest.main()

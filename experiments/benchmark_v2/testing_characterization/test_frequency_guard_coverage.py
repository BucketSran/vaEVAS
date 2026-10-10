"""A complete divider period must survive the report guard before disable."""
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
TASK = ROOT / "benchmark/tasks/v2-test-clock-frequency"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrequencyGuardCoverage(unittest.TestCase):
    def test_current_fixture_retains_observable_complete_divider_period(self):
        case = json.loads((TASK / "tests/cases.json").read_text())[2]
        line = next(line for line in case["netlist"].splitlines() if line.startswith("Ven "))
        tokens = re.search(r"wave=\[([^]]+)\]", line).group(1).split()
        def seconds(token):
            return float(token[:-1]) * 1e-9 if token.endswith("n") else float(token)
        points = [(seconds(tokens[i]), float(tokens[i + 1])) for i in range(0, len(tokens), 2)]
        threshold = case["threshold"]
        falls = [ta + (threshold - va) * (tb - ta) / (vb - va)
                 for (ta, va), (tb, vb) in zip(points, points[1:]) if va > threshold >= vb]
        # Independent observed boundary: second rising div_clk edge from the
        # original Spectre archive, not a reference-meter state or generated value.
        second_divider_rise = 118.442174995e-9
        self.assertGreater(falls[0] - second_divider_rise, 2 * case["guard"])
        self.assertLess(falls[0], 131.4e-9)  # Still leaves a disabled interval.
        self.assertIn("divide_ratio=7", case["netlist"])

    def test_literal_fourteen_period_ratio_rejects_cap_without_checker_change(self):
        checker = load("frequency_coverage_checker", ROOT / "benchmark/checkers/v2_testing.py")
        # Independent literal trace: 100 MHz DCO rises at 5,15,... ns; divided
        # clock rises at 5 and145 ns. The measured ratio is 140/10 = 14.
        rows = []
        for i in range(19001):
            ns = i / 100
            rows.append(dict(time=ns * 1e-9, enable=.9, reset=0.,
                             dco_clk=.9 if int(ns // 5) % 2 else 0.,
                             div_clk=.9 if 5 <= ns < 75 or ns >= 145 else 0.,
                             freq_mhz=100. if ns >= 15 else 0.,
                             divider_ratio=14. if ns >= 145 else 0.,
                             valid=1. if ns >= 145 else 0.))
        case = dict(kind="frequency", stop=190e-9, threshold=.45, guard=80e-12,
                    atol=.01, tolerances={"freq_mhz":.8,"divider_ratio":.03})
        good = checker.evaluate(rows, case)
        self.assertTrue(good["passed"], good)
        capped = [{**row, "divider_ratio":min(row["divider_ratio"], 13.8)} for row in rows]
        bad = checker.evaluate(capped, case)
        self.assertFalse(bad["passed"], bad)
        self.assertTrue(any(f.get("node") == "divider_ratio" for f in bad["failures"]))

    def test_frequency_generator_matches_delivered_cases_without_public_writes(self):
        builder = load("frequency_coverage_builder", HERE / "build_tasks.py")
        captured = []
        builder.package = lambda *args, **kwargs: captured.append((args, kwargs))
        builder.frequency_task()
        args, kwargs = captured[0]
        self.assertEqual(args[0], "clock-frequency")
        self.assertEqual(args[7], json.loads((TASK / "tests/cases.json").read_text()))
        self.assertEqual(kwargs["public_cases"], json.loads((TASK / "environment/public/cases.json").read_text()))
        self.assertEqual(len(args[7]), 3)
        self.assertEqual(len(args[6]), 3)  # Keep the five registered variants.


if __name__ == "__main__":
    unittest.main()

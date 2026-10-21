"""Compare a selected rational value with a constant without general fractions."""
import unittest

from evas import CompileError, KernelError, solve
from test_positive_clamped_divisor import CLAMPED_SOURCE
from test_rational_predicate_closure import KERNEL, compile_model, outside_source_only_scope

GUARDS = ["LANG"]

SELECTED_SOURCE = (CLAMPED_SOURCE
    .replace("real denominator, numerator, result;", "real denominator, numerator, result, selected;")
    .replace("result = clip(numerator / denominator);", "begin selected = clip(numerator / denominator); result = (selected > 0.5) ? 0.9 : 0.0; end"))


class SelectedQuotientComparisonContracts(unittest.TestCase):
    def assert_outputs(self, samples, expected, *, source=SELECTED_SOURCE, parameters=None):
        response = solve(compile_model(source, parameters), ["n", "d", "en", "ref"], samples, kernel=KERNEL)
        output = response["nodes"].index("y")
        for sample, answer in zip(response["solutions"], expected, strict=True):
            self.assertAlmostEqual(sample["voltages"][output], answer, places=10)

    def test_clipped_quotient_threshold_and_saturation_boundaries(self):
        self.assert_outputs([[-.1, 0, 1, 0], [0, 0, 1, 0], [.0625, 0, 1, 0], [.09375, 0, 1, 0], [.25, 0, 1, 0]],
                            [0, 0, 0, .9, .9], parameters={"floor": .125})

    def test_reverse_comparison_and_output_amplification(self):
        source = SELECTED_SOURCE.replace("(selected > 0.5) ? 0.9 : 0.0", "(0.5 < selected) ? 900000.0 : 0.0")
        self.assert_outputs([[.0625, 0, 1, 0], [.09375, 0, 1, 0]], [0, 900000],
                            source=source, parameters={"floor": .125})

    def test_source_order_keeps_comparison_before_alias_overwrite(self):
        source = SELECTED_SOURCE.replace("? 0.9 : 0.0; end", "? 0.9 : 0.0; selected = 0.0; end")
        self.assert_outputs([[.09375, 0, 1, 0]], [.9], source=source, parameters={"floor": .125})

    def test_each_selected_arm_uses_its_own_positive_guard(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);",
                                         "selected = (V(d) >= 0.125) ? numerator / V(d) : 0.0;")
        self.assert_outputs([[.09375, .125, 1, 0], [.09375, 0, 1, 0]], [.9, 0], source=source)

    def test_a_sibling_positive_guard_cannot_prove_another_arm(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);",
                                         "selected = (V(d) >= 0.125) ? 0.0 : numerator / V(d);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_unused_runtime_arm_still_needs_a_divisor_proof(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);",
                                         "selected = (V(ref) > 0.5) ? numerator / denominator : numerator / V(d);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_nonlinear_selected_arm_stays_rejected(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);",
                                         "selected = (V(ref) > 0.5) ? numerator / denominator : V(n) * V(ref);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_missing_source_value_does_not_become_a_proven_leaf(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);", "if (V(ref) > 0.5) selected = numerator / denominator;")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_general_rational_sum_remains_rejected(self):
        source = SELECTED_SOURCE.replace("selected > 0.5", "selected + numerator / denominator > 0.5")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_selected_original_quotient_value_keeps_overflow_rejection(self):
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);",
                                         "selected = (V(d) >= 0.125) ? numerator / V(d) : 0.0;")
        source = source.replace("(selected > 0.5) ? 0.9 : 0.0", "(selected > 0.5) ? selected : 0.0")
        program = compile_model(source)
        with self.assertRaisesRegex(KernelError, "nonfinite_arithmetic"):
            solve(program, ["n", "d", "en", "ref"], [[1e308, .125, 1, 0]], kernel=KERNEL)

    def test_shared_alias_tree_obeys_expanded_ir_budget(self):
        expansion = "selected = clip(numerator / denominator);\n" + "\n".join(
            "selected = (V(ref) > 0.5) ? selected : selected;" for _ in range(16))
        source = SELECTED_SOURCE.replace("selected = clip(numerator / denominator);", expansion)
        with self.assertRaises(CompileError) as caught:
            compile_model(outside_source_only_scope(source))
        self.assertEqual(caught.exception.diagnostic["code"], "resource_budget")

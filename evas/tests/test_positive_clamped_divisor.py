"""A source clamp can prove every selected denominator arm positive."""
import unittest

from evas import CompileError, KernelError, solve
from test_rational_predicate_closure import SOURCE, KERNEL, compile_model, outside_source_only_scope

GUARDS = ["LANG"]

CLAMPED_SOURCE = (SOURCE
    .replace("parameter real lower = 0.6;", "parameter real lower = 0.6; parameter real floor = 0.05;")
    .replace("denominator = V(d);", "denominator = V(d); if (denominator < floor) denominator = floor;")
    .replace("if ((V(en) > 0.5) && (denominator >= lower))", "if (V(en) > 0.5)"))


class PositiveClampedDivisorContracts(unittest.TestCase):
    def assert_outputs(self, samples, expected, *, source=CLAMPED_SOURCE, parameters=None):
        response = solve(compile_model(source, parameters), ["n", "d", "en", "ref"], samples, kernel=KERNEL)
        output = response["nodes"].index("y")
        for sample, answer in zip(response["solutions"], expected, strict=True):
            self.assertAlmostEqual(sample["voltages"][output], answer, places=12)

    def test_clamp_proves_divisor_positive_at_negative_zero_and_boundary(self):
        self.assert_outputs([[.025, -.2, 1, 0], [.025, 0, 1, 0], [.025, .05, 1, 0], [.025, .1, 1, 0]],
                            [.5, .5, .5, .25])

    def test_clamp_parameter_override_and_saturation_boundaries(self):
        self.assert_outputs([[-.1, 0, 1, 0], [0, 0, 1, 0], [.0625, 0, 1, 0], [.125, 0, 1, 0], [.25, 0, 1, 0]],
                            [0, 0, .5, 1, 1], parameters={"floor": .125})

    def test_piecewise_affine_difference_numerator(self):
        source = CLAMPED_SOURCE.replace("numerator = V(n);", "numerator = V(n) - V(ref);")
        self.assert_outputs([[.3125, 0, 1, .25], [.25, 0, 1, .25]], [.5, 0],
                            source=source, parameters={"floor": .125})

    def test_second_select_keeps_its_own_positive_arms(self):
        source = CLAMPED_SOURCE.replace("numerator = V(n);", "if (V(ref) > 0.5) denominator = 0.125; numerator = V(n);")
        self.assert_outputs([[.0625, 0, 1, 1], [.025, 0, 1, 0]], [.5, .5], source=source)

    def test_nonpositive_clamp_floor_does_not_prove_positive_divisor(self):
        for floor in [0, -.05]:
            with self.subTest(floor=floor), self.assertRaises(CompileError):
                compile_model(outside_source_only_scope(CLAMPED_SOURCE), {"floor": floor})

    def test_true_arm_cannot_borrow_false_arm_lower_bound(self):
        source = CLAMPED_SOURCE.replace("denominator = floor;", "denominator = -floor;")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_swapped_clamp_arms_do_not_prove_a_lower_bound(self):
        source = CLAMPED_SOURCE.replace("denominator = floor;", "denominator = denominator; else denominator = floor;")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_false_arm_cannot_borrow_true_arm_constant(self):
        source = CLAMPED_SOURCE.replace("denominator = floor;", "denominator = floor; else denominator = -denominator;")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_nonlinear_numerator_stays_rejected(self):
        source = CLAMPED_SOURCE.replace("numerator = V(n);", "numerator = V(n) * V(ref);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_unclamped_alias_does_not_inherit_the_positive_selected_value(self):
        source = CLAMPED_SOURCE.replace("result = clip(numerator / denominator);", "result = clip(numerator / V(d));")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_selected_quotient_overflow_is_still_rejected(self):
        source = CLAMPED_SOURCE.replace("clip(numerator / denominator)",
                                        "(numerator / denominator > 0.125) ? numerator / denominator : 0.0")
        program = compile_model(source)
        with self.assertRaisesRegex(KernelError, "nonfinite_arithmetic"):
            solve(program, ["n", "d", "en", "ref"], [[1e308, 0, 1, 0]], kernel=KERNEL)

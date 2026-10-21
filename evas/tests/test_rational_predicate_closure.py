"""Positive branch domains permit affine guards around a rational value.

Expected voltages come directly from clamp(n/d, 0, 1), with division evaluated
only on the source branch whose bound makes its denominator positive.
"""
from pathlib import Path
import unittest

from evas import CompileError, Instance, KernelError, compile_sources, solve

GUARDS = ["LANG"]
KERNEL = Path(__file__).resolve().parents[1] / "rust_core/target/debug/evas-kernel"


SOURCE = '''`include "disciplines.vams"
module positive_clip(n,d,en,ref,y);
input n,d,en,ref; output y;
electrical n,d,en,ref,y;
parameter real lower = 0.6;
real denominator, numerator, result;
analog function real clip;
    input x; real x;
    begin
        if (x < 0.0) clip = 0.0;
        else if (x > 1.0) clip = 1.0;
        else clip = x;
    end
endfunction
analog begin
    denominator = V(d);
    numerator = V(n);
    if ((V(en) > 0.5) && (denominator >= lower))
        result = clip(numerator / denominator);
    else result = -0.125;
    V(y) <+ result;
end
endmodule
'''


def outside_source_only_scope(source):
    """Keep the earlier helper rejection contract on a real state program."""
    return source.replace("analog begin", "real source_scope_witness; analog begin @(initial_step) source_scope_witness = 0;", 1)


def compile_model(source=SOURCE, parameters=None):
    return compile_sources({"positive-domain.va": source}, [
        Instance("dut", "positive_clip", {"n": "n", "d": "d", "en": "en", "ref": "ref", "y": "y"}, parameters or {})
    ])


class RationalPredicateClosureContracts(unittest.TestCase):
    def assert_outputs(self, samples, expected, *, source=SOURCE, parameters=None):
        samples = [row + [0] if len(row) == 3 else row for row in samples]
        response = solve(compile_model(source, parameters), ["n", "d", "en", "ref"], samples, kernel=KERNEL)
        output = response["nodes"].index("y")
        actual = [sample["voltages"][output] for sample in response["solutions"]]
        for observed, answer in zip(actual, expected, strict=True):
            self.assertAlmostEqual(observed, answer, places=12)

    def test_bound_alias_and_clamp_boundaries(self):
        self.assert_outputs(
            [[-.3, .6, 1], [0, .6, 1], [.3, .6, 1], [.6, .6, 1], [.9, .6, 1]],
            [0, 0, .5, 1, 1])

    def test_nonselected_branch_protects_zero_negative_and_small_denominator(self):
        self.assert_outputs(
            [[.3, 0, 1], [.3, -1, 1], [.3, .59, 1], [.3, .8, 0]],
            [-.125, -.125, -.125, -.125])

    def test_bound_is_taken_from_bound_parameter_not_its_default(self):
        self.assert_outputs([[.05, .1, 1], [.3, .5, 1], [.05, .09, 1]],
                            [.5, .6, -.125], parameters={"lower": .1})

    def test_strict_guard_and_reversed_operands_keep_boundary(self):
        source = SOURCE.replace("denominator >= lower", "lower < denominator")
        self.assert_outputs([[.3, .6, 1], [.35, .7, 1]], [-.125, .5], source=source)

    def test_constant_threshold_and_reversed_quotient_comparison(self):
        for comparison in ["numerator / denominator > 0.125", "0.125 < numerator / denominator"]:
            with self.subTest(comparison=comparison):
                source = SOURCE.replace("clip(numerator / denominator)", "(" + comparison + ") ? 0.9 : 0.0")
                self.assert_outputs([[.03125, .5, 1], [.0625, .5, 1], [.125, .5, 1]],
                                    [0, 0, .9], source=source, parameters={"lower": .1})

    def test_negative_denominator_domain_stays_rejected(self):
        source = SOURCE.replace("denominator >= lower", "denominator <= -lower")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_preserved_affine_difference_numerator(self):
        source = SOURCE.replace("numerator = V(n);", "numerator = V(n) - V(ref);")
        self.assert_outputs([[0, .5, 1, .25], [.25, .5, 1, .25], [.5, .5, 1, .25], [.75, .5, 1, .25]],
                            [0, 0, .5, 1], source=source, parameters={"lower": .1})

    def test_selected_quotient_overflow_keeps_existing_runtime_rejection(self):
        source = SOURCE.replace("clip(numerator / denominator)",
                                "(numerator / denominator > 0.125) ? numerator / denominator : 0.0")
        program = compile_model(source, {"lower": .1})
        with self.assertRaisesRegex(KernelError, "nonfinite_arithmetic"):
            solve(program, ["n", "d", "en", "ref"], [[1e308, .1, 1, 0]], kernel=KERNEL)

    def test_selected_quotient_derivative_nonfinite_keeps_runtime_rejection(self):
        program = compile_model(parameters={"lower": 1e-301})
        with self.assertRaisesRegex(KernelError, "nonfinite_arithmetic"):
            solve(program, ["n", "d", "en", "ref"], [[5e-301, 1e-300, 1, 0]], kernel=KERNEL)

    def test_wrong_branch_does_not_inherit_positive_fact(self):
        source = SOURCE.replace("denominator >= lower", "denominator < lower")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_zero_or_negative_lower_parameter_does_not_prove_positive_domain(self):
        for lower in [0, -.1]:
            with self.subTest(lower=lower), self.assertRaises(CompileError):
                compile_model(outside_source_only_scope(SOURCE), {"lower": lower})

    def test_unrelated_positive_voltage_does_not_prove_denominator_positive(self):
        source = SOURCE.replace("denominator >= lower", "V(en) >= lower")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_overwritten_alias_loses_its_previous_positive_domain(self):
        source = SOURCE.replace("result = clip(numerator / denominator);", "begin denominator = -denominator; result = clip(numerator / denominator); end")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_nonlinear_numerator_remains_outside_affine_guard_scope(self):
        source = SOURCE.replace("numerator = V(n);", "numerator = V(n) * V(n);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

    def test_branch_positive_fact_does_not_escape_to_later_expression(self):
        source = SOURCE.replace("V(y) <+ result;", "V(y) <+ clip(numerator / denominator);")
        with self.assertRaises(CompileError):
            compile_model(outside_source_only_scope(source))

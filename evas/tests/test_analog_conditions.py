"""Ordinary analog real assignment and if/else contracts.

These are development regressions for the v1-main gap.  The expected values are
the hand piecewise formula for a sequential local real, not EVAS output.
"""

import unittest

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, execute, instance, model


def limiter_source():
    return model("""
        y = 1.5*V(u,r)+0.125;
        if (y > 0.875) y = 0.875;
        if (y < -0.75) y = -0.75;
        V(yout,r)<+y;
    """, declarations="real y;", ports="u,yout,r",
       directions="input u; output yout; inout r;")


class OrdinaryAnalogConditionContracts(unittest.TestCase):
    def test_v1_limiter_formula_and_boundaries(self):
        samples = [[-1.0], [-7/12], [0.0], [0.5], [2.0]]
        rows = execute(limiter_source(), [instance(connections=dict(u="u", yout="yout", r="0"))],
                       ["u"], samples)
        expected = [-0.75, -0.75, 0.125, 0.875, 0.875]
        for row, value in zip(rows, expected):
            self.assertAlmostEqual(row["yout"], value, places=12)

    def test_stateless_transient_replays_input_driven_select(self):
        program = compile_sources({"test.va": limiter_source()},
                                  [instance(connections=dict(u="u", yout="yout", r="0"))])
        result = transient(program, {"u": [[0, -1.0], [1, 1.0]]},
                           [0.0, 0.5, 1.0], stop=1.0, max_step=0.25, kernel=KERNEL)
        rows = [dict(zip(result["nodes"], solution["voltages"])) for solution in result["solutions"]]
        self.assertEqual(result["transient"]["states"], [[], [], []])
        self.assertEqual([row["yout"] for row in rows], [-0.75, 0.125, 0.875])

    def test_sequential_assignment_is_not_contribution_accumulation(self):
        source = model("""
            tmp = V(u,r);
            tmp = tmp + 1;
            V(y,r)<+tmp;
            V(y,r)<+2;
        """, declarations="real tmp;")
        row = execute(source, samples=[[0.25]])[0]
        self.assertAlmostEqual(row["y"], 3.25, places=12)

    def test_independent_contributions_still_accumulate_when_reordered(self):
        a = model("tmp=V(u,r); if (tmp>.5) tmp=1; V(y,r)<+tmp; V(y,r)<+2;",
                  declarations="real tmp;")
        b = model("tmp=V(u,r); if (tmp>.5) tmp=1; V(y,r)<+2; V(y,r)<+tmp;",
                  declarations="real tmp;")
        for source in (a, b):
            rows = execute(source, samples=[[0.25], [0.75]])
            self.assertEqual([row["y"] for row in rows], [2.25, 3.0])

    def test_cancellation_predicate_uses_exact_binary64_affine_sign(self):
        from fractions import Fraction
        source = model("""
            tmp = 0;
            if (V(u,r)+1e16 > 1e16) tmp = 1; else tmp = 0;
            V(y,r)<+tmp;
        """, declarations="real tmp;")
        rows = execute(source, samples=[[1.0], [0.0], [-1.0]])
        expected = [
            1.0 if Fraction(u) + Fraction(1e16) > Fraction(1e16) else 0.0
            for u in [1.0, 0.0, -1.0]
        ]
        self.assertEqual([row["y"] for row in rows], expected)

    def test_neighboring_threshold_and_equality_keep_exact_relation_semantics(self):
        from fractions import Fraction
        threshold = float(1.0 + 2.0**-52)
        source = model("""
            tmp = 0;
            if (V(u,r) >= 1.0000000000000002) tmp = tmp + 1;
            if (V(u,r) <= 1.0000000000000002) tmp = tmp + 2;
            V(y,r)<+tmp;
        """, declarations="real tmp;")
        samples = [[1.0], [threshold], [float(1.0 + 2.0**-51)]]
        rows = execute(source, samples=samples)
        expected = []
        for [u] in samples:
            value = 0.0
            if Fraction(u) >= Fraction(threshold):
                value += 1.0
            if Fraction(u) <= Fraction(threshold):
                value += 2.0
            expected.append(value)
        self.assertEqual([row["y"] for row in rows], expected)

    def test_nested_select_only_evaluates_selected_condition_path(self):
        from fractions import Fraction
        source = model("""
            tmp = 0;
            if (V(sel,r) > 0) begin
                if (V(u,r)+1e16 > 1e16) tmp = 1; else tmp = 2;
            end else begin
                tmp = 3;
            end
            V(y,r)<+tmp;
        """, declarations="real tmp;", ports="u,sel,y,r",
           directions="input u; input sel; output y; inout r;")
        samples = [[1.0, 1.0], [-1.0, 1.0], [1.0, -1.0]]
        rows = execute(
            source,
            [instance(connections=dict(u="u", sel="sel", y="y", r="0"))],
            ["u", "sel"],
            samples,
        )
        expected = []
        for u, sel in samples:
            if Fraction(sel) > 0:
                expected.append(
                    1.0 if Fraction(u) + Fraction(1e16) > Fraction(1e16) else 2.0
                )
            else:
                expected.append(3.0)
        self.assertEqual([row["y"] for row in rows], expected)

    def test_raw_ir_uncertified_condition_is_rejected_instead_of_rounded(self):
        program = compile_sources(
            {"test.va": limiter_source()},
            [instance(connections=dict(u="u", yout="yout", r="0"))],
        ).to_dict()
        def find_select(expr):
            if expr.get("op") == "select":
                return expr
            for value in expr.values():
                if isinstance(value, dict) and "op" in value:
                    found = find_select(value)
                    if found:
                        return found
            return None
        select = find_select(program["contributions"][0]["rhs"])
        square = {
            "op": "multiply",
            "left": {
                "op": "affine", "constant": 0,
                "terms": [{"node": program["nodes"].index("u"), "coefficient": 1}],
            },
            "right": {
                "op": "affine", "constant": 0,
                "terms": [{"node": program["nodes"].index("u"), "coefficient": 1}],
            },
        }
        select["left"] = {
            "op": "add", "left": square,
            "right": {"op": "affine", "constant": 1e16, "terms": []},
        }
        select["right"] = {"op": "affine", "constant": 1e16, "terms": []}
        with self.assertRaisesRegex(KernelError, "condition_precision|unsupported_condition"):
            solve(
                type("ProgramLike", (), {
                    "to_dict": lambda self: program,
                    "nodes": tuple(program["nodes"]),
                })(),
                ["u"], [[0.5]], kernel=KERNEL,
            )

    def test_rejects_unsupported_feedback_predicate(self):
        source = model("tmp=V(y,r); if (tmp>.5) tmp=1; V(y,r)<+tmp;",
                       declarations="real tmp;")
        with self.assertRaisesRegex(CompileError, "ordinary analog if"):
            execute(source)

    def test_rejects_dynamic_local_assignment(self):
        source = model("tmp=idt(V(u,r),0); V(y,r)<+tmp;", declarations="real tmp;")
        with self.assertRaisesRegex(CompileError, "ordinary analog local assignments"):
            compile_sources({"bad.va": source}, [instance()])

    def test_raw_ir_select_predicate_must_be_driven(self):
        program = compile_sources(
            {"test.va": limiter_source()},
            [instance(connections=dict(u="u", yout="yout", r="0"))],
        ).to_dict()
        def find_select(expr):
            if expr.get("op") == "select":
                return expr
            for value in expr.values():
                if isinstance(value, dict) and "op" in value:
                    found = find_select(value)
                    if found:
                        return found
            return None
        select = find_select(program["contributions"][0]["rhs"])
        self.assertIsNotNone(select)
        select["left"] = {"op": "affine", "constant": 0,
                          "terms": [{"node": program["nodes"].index("yout"), "coefficient": 1}]}
        with self.assertRaisesRegex(KernelError, "unsupported_condition"):
            solve(
                type("ProgramLike", (), {
                    "to_dict": lambda self: program,
                    "nodes": tuple(program["nodes"]),
                })(),
                ["u"], [[0.5]], kernel=KERNEL,
            )


if __name__ == "__main__":
    unittest.main()

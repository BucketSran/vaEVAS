"""Transient entry contracts for state-free polynomial voltage equations."""

from decimal import Decimal, getcontext
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model


getcontext().prec = 90


def exact_float(value):
    return Decimal.from_float(float(value))


def decimal_cubic_root(u, cubic, scale):
    """High-precision monotonic root for exact binary64 inputs/parameters."""
    u = exact_float(u)
    cubic = exact_float(cubic)
    scale = exact_float(scale)
    coefficient = cubic / (scale * scale)
    lo = min(Decimal(-1), u)
    hi = max(Decimal(1), u)

    def f(y):
        return y + coefficient * y * y * y - u

    while f(lo) > 0:
        lo *= 2
    while f(hi) < 0:
        hi *= 2
    for _ in range(260):
        mid = (lo + hi) / 2
        if f(mid) <= 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def cubic_root(u, cubic, scale):
    """Independent monotonic bisection for y + c*y^3/s^2 = u."""
    lo = min(-1.0, u)
    hi = max(1.0, u)

    def f(y):
        return y + cubic * y**3 / (scale * scale) - u

    while f(lo) > 0:
        lo *= 2.0
    while f(hi) < 0:
        hi *= 2.0
    for _ in range(180):
        mid = (lo + hi) / 2.0
        if f(mid) <= 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


class NonlinearTransientContracts(unittest.TestCase):
    def compile_cubic(self, cubic=0.5, scale=1.0):
        source = model(
            "V(y,r)<+V(u,r)-c*pow(V(y,r),3)/(s*s);",
            "parameter real c=.5; parameter real s=1;",
        )
        return compile_sources(
            {"nonlinear.va": source},
            [
                instance(
                    connections=dict(u="u", y="y", r="r"),
                    parameters=dict(c=cubic, s=scale),
                )
            ],
        )

    def test_state_free_polynomial_transient_solves_each_output_time(self):
        program = self.compile_cubic(cubic=0.5, scale=2.0)
        times = [0.0, 0.5, 1.25, 2.0, 3.0, 4.0]
        roots = [-1.5, -0.25, 0.0, 0.75, 2.0, -1.5]
        reference = 0.125
        u_values = [reference + q + 0.5 * q**3 / 4.0 for q in roots]
        result = transient(
            program,
            {
                "u": list(map(list, zip(times, u_values))),
                "r": [[0.0, reference], [4.0, reference]],
            },
            times,
            stop=4.0,
            max_step=4.0,
            kernel=KERNEL,
        )
        rows = [dict(zip(result["nodes"], s["voltages"])) for s in result["solutions"]]
        self.assertEqual(result["transient"]["events"], [])
        self.assertEqual(result["transient"]["states"], [[] for _ in times])
        self.assertEqual(result["transient"]["accepted_steps"], len(times) - 1)
        for row, q in zip(rows, roots):
            self.assertAlmostEqual(row["y"] - row["r"], q, delta=4e-10)

    def test_transient_answers_match_independent_cubic_roots_under_tolerances(self):
        program = self.compile_cubic(cubic=2.0, scale=0.5)
        times = [0.0, 0.3, 0.9, 1.7, 2.0]
        u_values = [-0.6, -0.1, 0.25, 1.2, -0.6]
        result = transient(
            program,
            {"u": list(map(list, zip(times, u_values))), "r": [[0.0, 0.0], [2.0, 0.0]]},
            times,
            stop=2.0,
            max_step=2.0,
            kernel=KERNEL,
            vabstol=1e-11,
            reltol=1e-11,
        )
        rows = [dict(zip(result["nodes"], s["voltages"])) for s in result["solutions"]]
        for row, u in zip(rows, u_values):
            expected = cubic_root(u, 2.0, 0.5)
            self.assertAlmostEqual(row["y"], expected, delta=2e-8)
            residual = row["y"] + 2.0 * row["y"] ** 3 / 0.25 - u
            self.assertLess(abs(residual), 3e-10)

    def test_decimal_root_precision_and_grid_variation_use_voltage_budget(self):
        cubic = 0.5
        scale = 2.0
        abstol = 1e-10
        reltol = 1e-10
        program = self.compile_cubic(cubic=cubic, scale=scale)
        roots = [-1.75, -0.3, 0.05, 0.9, 1.4]
        u_values = [q + cubic * q**3 / (scale * scale) for q in roots]
        dense_times = [0.0, 0.2, 0.7, 1.3, 2.0]
        sparse_times = [0.0, 0.7, 2.0]
        sources = {
            "u": list(map(list, zip(dense_times, u_values))),
            "r": [[0.0, 0.0], [dense_times[-1], 0.0]],
        }

        def run(times):
            result = transient(
                program,
                sources,
                times,
                stop=dense_times[-1],
                max_step=dense_times[-1],
                kernel=KERNEL,
                vabstol=abstol,
                reltol=reltol,
            )
            return [dict(zip(result["nodes"], s["voltages"])) for s in result["solutions"]]

        dense = run(dense_times)
        sparse = run(sparse_times)
        for row, u in zip(dense, u_values):
            expected = decimal_cubic_root(u, cubic, scale)
            observed = exact_float(row["y"])
            rhs = exact_float(u)
            coefficient = exact_float(cubic) / (exact_float(scale) * exact_float(scale))
            lhs = observed
            physical_rhs = rhs - coefficient * observed * observed * observed
            budget = exact_float(abstol) + exact_float(reltol) * max(abs(lhs), abs(physical_rhs))
            self.assertLessEqual(abs(observed - expected), budget)
        for dense_index, sparse_row in zip([0, 2, 4], sparse):
            budget = abstol + reltol * max(abs(sparse_row["y"]), abs(dense[dense_index]["y"]))
            self.assertLessEqual(abs(sparse_row["y"] - dense[dense_index]["y"]), budget)

    def test_polynomial_transient_with_events_remains_explicitly_unsupported(self):
        source = model(
            "@(initial_step) held=0; @(timer(0,1,1p)) held=held+1; "
            "V(y,r)<+V(u,r)-pow(V(y,r),3)+held;",
            "integer held;",
        )
        program = compile_sources({"event_nonlinear.va": source}, [instance()])
        with self.assertRaises(KernelError) as error:
            transient(
                program,
                {"u": [[0.0, 0.0], [1.0, 1.0]]},
                [0.0, 1.0],
                stop=1.0,
                max_step=1.0,
                kernel=KERNEL,
            )
        self.assertEqual(error.exception.detail["kind"], "unsupported_transient")
        self.assertIn("polynomial transient equations", error.exception.detail["message"])

    def test_nonconvergence_reports_output_index_without_committing_later_points(self):
        source = model("V(y,r)<+V(y,r)-(pow(V(y,r),3)-2*V(y,r)+2);")
        program = compile_sources({"bad_transient.va": source}, [instance()])
        with self.assertRaises(KernelError) as error:
            transient(
                program,
                {"u": [[0.0, 0.0], [1.0, 0.0]]},
                [0.0, 0.5, 1.0],
                stop=1.0,
                max_step=1.0,
                kernel=KERNEL,
            )
        self.assertEqual(error.exception.detail["kind"], "nonconvergence")
        self.assertEqual(error.exception.detail["sample"], 0)

    def test_nonconvergence_after_success_reports_later_output_index(self):
        source = model(
            "V(y,r)<+bias+gain*V(u,r)-c*pow(V(y,r),3);",
            "parameter real bias=0; parameter real gain=0; parameter real c=0;",
        )
        program = compile_sources(
            {"late_bad_transient.va": source},
            [
                instance("clamp", parameters=dict(bias=0.0, gain=0.0, c=0.0)),
                instance("cubic", parameters=dict(bias=0.0, gain=1.0, c=1.0)),
            ],
        )
        with self.assertRaises(KernelError) as error:
            transient(
                program,
                {"u": [[0.0, 0.0], [1.0, 1.0]]},
                [0.0, 1.0],
                stop=1.0,
                max_step=1.0,
                kernel=KERNEL,
            )
        self.assertEqual(error.exception.detail["kind"], "nonconvergence")
        self.assertEqual(error.exception.detail["sample"], 1)


if __name__ == "__main__":
    unittest.main()

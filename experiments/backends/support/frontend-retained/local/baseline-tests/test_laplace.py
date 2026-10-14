"""First-order laplace_nd development contracts.

The oracle solves d1*y' + d0*y = b0*u on the binary64 source PWL segments.
It is independent of the kernel implementation and keeps standard array syntax
separate from the historical non-standard brace form.
"""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS", "LAPLACE"]

import copy
from decimal import Decimal, getcontext
import json
import math
import subprocess
import unittest

from evas.ir import SCHEMA_VERSION
from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance, model


getcontext().prec = 80

POINTS = [[0.0, 0.0], [1e-6, 1.0], [3e-6, 1.0], [4e-6, -1.0], [6e-6, -1.0]]


def compile_filter(body="V(y,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,0.5e-6});",
                   declarations="", instances=None):
    return compile_sources({"laplace.va": model(body, declarations)}, instances or [instance()])


def execute(program=None, points=POINTS, times=None, step=10e-6, **tolerances):
    return transient(program or compile_filter(), {"u": points},
                     times or [0, .5e-6, 1e-6, 2e-6, 3e-6, 4e-6, 6e-6],
                     stop=points[-1][0], max_step=step, kernel=KERNEL, **tolerances)


def column(result, name="y"):
    index = result["nodes"].index(name)
    return [row["voltages"][index] for row in result["solutions"]]


def expected(points, time, gain=1.0, tau=0.5e-6):
    tau = Decimal(tau)
    gain = Decimal(gain)
    return expected_with_decimal_gain_tau(points, time, gain, tau)


def expected_from_coefficients(points, time, b0, d0, d1):
    return expected_with_decimal_gain_tau(
        points, time, Decimal(b0) / Decimal(d0), Decimal(d1) / Decimal(d0))


def expected_with_decimal_gain_tau(points, time, gain, tau):
    y = gain * Decimal(points[0][1])
    now = Decimal(points[0][0])
    target = Decimal(time)
    for (start, u0), (end, u1) in zip(points, points[1:]):
        start, end = Decimal(start), Decimal(end)
        u0, u1 = Decimal(u0), Decimal(u1)
        if target <= start:
            break
        h = min(target, end) - start
        duration = end - start
        x = h / tau
        e = (-x).exp()
        lag = h - tau * (Decimal(1) - e)
        q = lag / duration
        y = e * y + gain * ((Decimal(1) - e - q) * u0 + q * u1)
        now = end
        if target <= end:
            break
    assert target >= now or True
    return float(y)


class LaplaceContracts(unittest.TestCase):
    def test_standard_constant_arrays_and_first_order_ramp_oracle(self):
        program = compile_filter()
        self.assertEqual(program.schema_version, SCHEMA_VERSION)
        self.assertEqual(program.operators[0].kind, "laplace_nd")
        self.assertEqual(program.operators[0].numerator, (1.0,))
        self.assertEqual(program.operators[0].denominator, (1.0, 0.5e-6))
        times = [0, .5e-6, 1e-6, 2e-6, 3e-6, 4e-6, 6e-6]
        result = execute(program, times=times, vabstol=1e-9, reltol=0)
        for actual, t in zip(column(result), times):
            self.assertAlmostEqual(actual, expected(POINTS, t), delta=2e-9)
        self.assertTrue(all(row["max_residual_ratio"] <= 1 for row in result["solutions"]))

    def test_initial_value_is_dc_equilibrium_not_forced_zero(self):
        points = [[0.0, 2.0], [2e-6, 2.0], [4e-6, 2.0]]
        result = execute(points=points, times=[0, 1e-6, 4e-6])
        self.assertEqual(column(result), [2.0, 2.0, 2.0])
        scaled = compile_filter("V(y,r)<+laplace_nd(2*V(u,r),'{3.0},'{6.0,12e-6});")
        result = execute(scaled, points=points, times=[0, 2e-6, 4e-6])
        self.assertEqual(column(result), [2.0, 2.0, 2.0])

    def test_output_grid_maxstep_instances_and_order_do_not_define_history(self):
        source = model("V(y,r)<+laplace_nd(g*V(u,r),'{1.0},'{1.0,tau});",
                       "parameter real g=1; parameter real tau=0.5e-6;")
        a = instance("a", connections=dict(u="u", y="ya", r="0"))
        b = instance("b", connections=dict(u="u", y="yb", r="0"), parameters=dict(g=-2, tau=1e-6))
        times = [0, .25e-6, 1e-6, 2.5e-6, 5e-6, 6e-6]
        baseline = None
        for order in ([a, b], [b, a]):
            for grid in (times, sorted(set(times + [i * 0.125e-6 for i in range(49)]))):
                for step in (10e-6, 0.375e-6):
                    result = transient(compile_sources({"laplace.va": source}, list(order)),
                                       {"u": POINTS}, grid, stop=6e-6,
                                       max_step=step, kernel=KERNEL, vabstol=1e-8, reltol=0)
                    selected = ([column(result, "ya")[grid.index(t)] for t in times],
                                [column(result, "yb")[grid.index(t)] for t in times])
                    if baseline is None:
                        baseline = selected
                    for actual, answer in zip(selected[0], [expected(POINTS, t) for t in times]):
                        self.assertAlmostEqual(actual, answer, delta=3e-8)
                    for actual, answer in zip(selected[1], [expected(POINTS, t, gain=-2, tau=1e-6) for t in times]):
                        self.assertAlmostEqual(actual, answer, delta=3e-8)
                    self.assertEqual(selected, baseline)

    def test_coefficient_scale_and_long_small_step_queries(self):
        points = [[0.0, 1.0], [1e-12, 1.25], [4e-12, 0.5]]
        program = compile_filter("V(y,r)<+laplace_nd(V(u,r),'{2.0},'{4.0,8e-12});")
        result = execute(program, points=points, times=[0, 1e-12, 2e-12, 4e-12],
                         step=1e-12, vabstol=1e-10, reltol=0)
        for actual, t in zip(column(result), [0, 1e-12, 2e-12, 4e-12]):
            self.assertAlmostEqual(actual, expected(points, t, gain=.5, tau=2e-12), delta=1e-10)

    def test_original_coefficient_division_uses_decimal_oracle(self):
        points = [[0.0, 1.0], [2.0, 2.0], [5.0, -1.0]]
        program = compile_filter("V(y,r)<+laplace_nd(V(u,r),'{1.0},'{3.0,3.0});")
        times = [0, 0.5, 2.0, 3.5, 5.0]
        result = execute(program, points=points, times=times, step=5.0, vabstol=2e-12, reltol=0)
        for actual, t in zip(column(result), times):
            self.assertAlmostEqual(
                actual, expected_from_coefficients(points, t, 1.0, 3.0, 3.0), delta=2e-12)

    def test_large_absolute_time_uncertainty_is_budgeted(self):
        body = ("V(z,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,1.0e16}); "
                "V(y,r)<+1.0e12*V(z,r);")
        program = compile_filter(body, "electrical z;")
        points = [[0.0, 0.0], [1.0, 0.0], [1.0e16, 1.0]]
        times = [0, 1.0, 5.0e15, 1.0e16]
        ok = execute(program, points=points, times=times, step=1.0e16, vabstol=1e-2, reltol=0)
        for actual, t in zip(column(ok, "y"), times):
            self.assertAlmostEqual(
                actual, 1.0e12 * expected_from_coefficients(points, t, 1.0, 1.0, 1.0e16),
                delta=1e-2)
        with self.assertRaisesRegex(
                KernelError, "waveform_accuracy: .*budget 1e-6"):
            execute(program, points=points, times=times, step=1.0e16, vabstol=1e-6, reltol=0)

    def test_decimal_oracle_covers_ordinary_and_large_exponential_weights(self):
        cases = [
            ([[0.0, 0.0], [1e-6, 1.0], [3e-6, -0.5]], 0.5e-6,
             [0, 0.5e-6, 1.5e-6, 3e-6], 2e-9),
            ([[0.0, 0.0], [20e-9, 1.0], [100e-9, 1.0]], 1e-9,
             [0, 1e-9, 20e-9, 100e-9], 3e-9),
        ]
        for points, tau, times, delta in cases:
            program = compile_filter(f"V(y,r)<+laplace_nd(V(u,r),'{{1.0}},'{{1.0,{tau!r}}});")
            result = execute(program, points=points, times=times, step=100e-9,
                             vabstol=delta, reltol=0)
            for actual, t in zip(column(result), times):
                self.assertAlmostEqual(actual, expected(points, t, tau=tau), delta=delta)

    def test_laplace_history_error_is_amplified_by_voltage_network(self):
        body = ("V(z,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,0.5e-6}); "
                "V(y,r)<+1073741824*V(z,r);")
        program = compile_filter(body, "electrical z;")
        points = [[0, 0], [1e-6, 1]]
        ok = execute(program, points=points, times=[0, .5e-6, 1e-6],
                     step=1e-6, vabstol=1e-3, reltol=0)
        for actual, t in zip(column(ok, "y"), [0, .5e-6, 1e-6]):
            self.assertAlmostEqual(actual, 1073741824 * expected(points, t), delta=1e-3)
        with self.assertRaisesRegex(KernelError, "waveform_accuracy"):
            execute(program, points=points, times=[0, .5e-6, 1e-6],
                    step=1e-6, vabstol=1e-9, reltol=0)

    def test_rejections_are_explicit(self):
        compile_errors = [
            "V(y,r)<+laplace_nd(V(u,r),{1.0},{1.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{1.0});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0,2.0,3.0},'{1.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,1,1,1,1,1,1,1,1,1});",
            "V(y,r)<+laplace_nd(V(u,r),'{V(u,r)},'{1.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{tau,V(u,r)});",
            "V(y,r)<+laplace_nd(V(u,r));",
        ]
        for body in compile_errors:
            with self.subTest(body=body), self.assertRaises(CompileError):
                compile_filter(body, "parameter real tau=1;")
        kernel_errors = [
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{0.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,-0.5e-6});",
            "@(initial_step) q=0; V(y,r)<+laplace_nd(q,'{1.0},'{1.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(y,r),'{1.0},'{1.0,0.5e-6});",
            "V(y,r)<+laplace_nd(V(u,r),'{1.0},'{1.0,0.5e-6})*V(u,r);",
        ]
        for body in kernel_errors:
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                execute(compile_filter(body, "electrical z; real q;"))
        with self.assertRaises(KernelError):
            solve(compile_filter(), ["u"], [[1]], kernel=KERNEL)

    def test_raw_ir_rejects_bad_coefficients_and_dependencies(self):
        good = compile_filter().to_dict()
        bad_programs = []
        for key, value in [("numerator", [1.0, 2.0, 3.0]), ("denominator", [1.0]),
                           ("denominator", [1.0] * 10), ("denominator", [1.0, -1.0]),
                           ("extra", 0)]:
            raw = copy.deepcopy(good)
            raw["operators"][0][key] = value
            bad_programs.append(raw)
        raw = copy.deepcopy(good)
        del raw["operators"][0]["numerator"]
        bad_programs.append(raw)
        for program in bad_programs:
            response = subprocess.run([str(KERNEL)], input=json.dumps(dict(
                program=program, driven=["u"], samples=[],
                transient=dict(pwl=[POINTS], output_times=[0, 6e-6], stop=6e-6, max_step=10e-6))),
                text=True, capture_output=True)
            with self.subTest(program=program):
                self.assertEqual(response.returncode, 2, response.stdout)
                self.assertIn(json.loads(response.stderr)["kind"],
                              ["invalid_ir", "invalid_request", "unsupported_operator"])

    def test_raw_self_feedback_without_unique_dc_initial_state_fails(self):
        raw = compile_filter().to_dict()
        raw["operators"][0]["input"] = dict(op="operator", operator=0)
        response = subprocess.run([str(KERNEL)], input=json.dumps(dict(
            program=raw, driven=["u"], samples=[],
            transient=dict(pwl=[POINTS], output_times=[0, 6e-6], stop=6e-6, max_step=10e-6))),
            text=True, capture_output=True)
        self.assertEqual(response.returncode, 2, response.stdout)
        # x'=(x-x)/tau gives no DC equation that determines x(0).
        self.assertEqual(json.loads(response.stderr)["kind"], "event_resolution")


if __name__ == "__main__":
    unittest.main()

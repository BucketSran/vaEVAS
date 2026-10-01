"""Continuous dynamic contracts with hand-derived public-interface answers.

These tests pin the next EVAS continuous-time scope: affine integral feedback,
direct PWL derivatives, and proper higher-order ``laplace_nd`` filters.  The
expected values come from closed forms or exact PWL areas, not from the kernel's
state-space machinery.
"""

from fractions import Fraction
import itertools
import math
import unittest

from evas import CompileError, KernelError, Instance, compile_sources, transient
from test_affine import KERNEL, instance, model


def compile_model(body, declarations="", *, ports="u,y,r", directions="input u; output y; inout r;", instances=None):
    default_connections = {name: ("0" if name == "r" else name) for name in ports.split(",")}
    return compile_sources(
        {"continuous.va": model(body, declarations, ports=ports, directions=directions)},
        instances or [instance(connections=default_connections)],
    )


def run(program, sources=None, times=None, *, stop=None, max_step=None, **tolerances):
    times = times or [0.0, 0.25, 0.5, 1.0, 2.0]
    stop = times[-1] if stop is None else stop
    max_step = stop if max_step is None else max_step
    return transient(
        program,
        sources or {"u": [[0.0, 0.0], [stop, 0.0]]},
        times,
        stop=stop,
        max_step=max_step,
        kernel=KERNEL,
        **tolerances,
    )


def values(result, node="y"):
    index = result["nodes"].index(node)
    return [row["voltages"][index] for row in result["solutions"]]


def rows(result):
    return [dict(zip(result["nodes"], row["voltages"])) for row in result["solutions"]]


def assert_close(test, actual, expected, *, delta=2e-9):
    test.assertTrue(math.isfinite(actual), actual)
    test.assertAlmostEqual(actual, expected, delta=delta)


class AffineIntegralFeedbackContracts(unittest.TestCase):
    def test_first_order_integral_feedback_has_closed_form(self):
        program = compile_model("V(y,r)<+idt(1-V(y,r),0);")
        times = [0.0, 0.125, 0.5, 1.0, 2.0, 4.0]
        for step in (4.0, 0.125):
            with self.subTest(step=step):
                result = run(program, times=times, stop=4.0, max_step=step, vabstol=1e-10, reltol=0.0)
                for time, actual in zip(times, values(result)):
                    assert_close(self, actual, 1.0 - math.exp(-time), delta=2e-9)

    def test_two_integrators_can_form_a_coupled_oscillator(self):
        source = """
            V(s,r)<+idt(V(c,r),0);
            V(c,r)<+idt(-V(s,r),1);
            V(y,r)<+V(s,r);
            V(q,r)<+V(c,r);
        """
        program = compile_model(
            source,
            "electrical s,c;",
            ports="u,y,q,r",
            directions="input u; output y,q; inout r;",
            instances=[Instance("dut", "m", dict(u="u", y="y", q="q", r="0"))],
        )
        times = [0.0, 0.25, 0.5, 1.0, math.pi / 2, math.pi]
        result = run(program, {"u": [[0.0, 0.0], [math.pi, 0.0]]}, times, stop=math.pi, max_step=math.pi)
        for time, row in zip(times, rows(result)):
            assert_close(self, row["y"], math.sin(time), delta=3e-8)
            assert_close(self, row["q"], math.cos(time), delta=3e-8)

    def test_same_branch_integral_feedback_is_order_invariant(self):
        pieces = ["V(y,r)<+.25;", "V(y,r)<+idt(1-V(y,r),0);"]
        times = [0.0, 0.25, 0.5, 1.0, 2.0]
        baseline = None
        for order in itertools.permutations(pieces):
            program = compile_model("".join(order))
            result = run(program, times=times, stop=2.0, max_step=2.0)
            actual = values(result)
            expected = [0.25 + 0.75 * (1.0 - math.exp(-time)) for time in times]
            for observed, answer in zip(actual, expected):
                assert_close(self, observed, answer, delta=2e-9)
            if baseline is None:
                baseline = actual
            self.assertEqual(actual, baseline)

    def test_internal_voltage_relay_can_drive_integral_feedback(self):
        program = compile_model("V(z,r)<+V(u,r); V(y,r)<+idt(V(z,r),0);", "electrical z;")
        points = [[0.0, 0.0], [2.0, 2.0]]
        times = [0.0, 0.5, 1.0, 2.0]
        result = run(program, {"u": points}, times, stop=2.0, max_step=2.0)
        for time, actual in zip(times, values(result)):
            expected = Fraction.from_float(time) ** 2 / 2
            assert_close(self, actual, float(expected), delta=2e-9)

    def test_nested_integrals_of_constant_source_have_quadratic_answer(self):
        program = compile_model("V(y,r)<+idt(idt(V(u,r),0),0);")
        points = [[0.0, 1.0], [3.0, 1.0]]
        times = [0.0, 0.25, 1.0, 2.0, 3.0]
        result = run(program, {"u": points}, times, stop=3.0, max_step=3.0)
        for time, actual in zip(times, values(result)):
            expected = Fraction.from_float(time) ** 2 / 2
            assert_close(self, actual, float(expected), delta=2e-9)

    def test_internal_voltage_integral_chain_has_quadratic_answer(self):
        program = compile_model("V(z,r)<+idt(V(u,r),0); V(y,r)<+idt(V(z,r),0);", "electrical z;")
        points = [[0.0, 1.0], [3.0, 1.0]]
        times = [0.0, 0.25, 1.0, 2.0, 3.0]
        result = run(program, {"u": points}, times, stop=3.0, max_step=3.0)
        for time, row in zip(times, rows(result)):
            assert_close(self, row["dut:z"], time, delta=2e-9)
            expected = Fraction.from_float(time) ** 2 / 2
            assert_close(self, row["y"], float(expected), delta=2e-9)

    def test_canceled_internal_voltage_inputs_still_select_joint_network(self):
        expressions = ["V(z,r)-V(z,r)", "0*V(z,r)", "V(z,z)"]
        points = [[0.0, 1.0], [3.0, 1.0]]
        times = [0.0, 0.5, 1.0, 3.0]
        for expression in expressions:
            with self.subTest(expression=expression):
                program = compile_model(f"V(z,r)<+V(u,r); V(y,r)<+idt({expression},0);", "electrical z;")
                result = run(program, {"u": points}, times, stop=3.0, max_step=3.0)
                for row in rows(result):
                    assert_close(self, row["dut:z"], 1.0, delta=2e-9)
                    assert_close(self, row["y"], 0.0, delta=2e-9)

    def test_canceled_internal_voltage_with_event_state_has_zero_integral(self):
        expressions = ["V(z,r)-V(z,r)", "0*V(z,r)", "V(z,z)"]
        for expression in expressions:
            with self.subTest(expression=expression):
                body = (
                    "@(initial_step) q=0; @(timer(1,0,1e-12)) q=1; "
                    f"V(z,r)<+V(u,r)+0*q; V(y,r)<+idt({expression},0);"
                )
                program = compile_model(body, "real q; electrical z;")
                result = run(program, {"u": [[0.0, 1.0], [3.0, 1.0]]}, [0.0, 1.0, 3.0], stop=3.0, max_step=3.0)
                for value in values(result):
                    assert_close(self, value, 0.0, delta=1e-10)

    def test_output_grid_and_max_step_do_not_define_integral_history(self):
        program = compile_model("V(y,r)<+idt(1-V(y,r),0);")
        sparse = [0.0, 0.5, 1.0, 2.0]
        dense = [index / 16 for index in range(33)]
        baseline = values(run(program, times=sparse, stop=2.0, max_step=2.0, vabstol=1e-10, reltol=0.0))
        for times, step in ((sparse, 2.0), (dense, 0.125), (dense, 2.0)):
            result = run(program, times=times, stop=2.0, max_step=step, vabstol=1e-10, reltol=0.0)
            selected = [values(result)[times.index(time)] for time in sparse]
            for observed, answer in zip(selected, baseline):
                self.assertAlmostEqual(observed, answer, delta=2e-9)


class ContinuousInitializationContracts(unittest.TestCase):
    def test_ddt_identity_filter_preserves_dc_in_equivalent_encodings(self):
        bodies = [
            ("V(y,r)<+ddt(V(u,r));", ""),
            ("V(y,r)<+laplace_nd(ddt(V(u,r)),'{1,1},'{1,1});", ""),
            ("V(y,r)<+laplace_nd(ddt(V(u,r)),'{1,2,1},'{1,2,1});", ""),
            ("V(d,r)<+ddt(V(u,r)); V(y,r)<+laplace_nd(V(d,r),'{1,1},'{1,1});", "electrical d;"),
        ]
        times = [0.0, 2.0 ** -20, 0.5, 1.0]
        # H(s)=1 must preserve both the zero DC derivative and the nonzero
        # right-side transient derivative. Nonzero u(0) is not a derivative.
        for slope in (-1.0, 1.0):
            for body, declarations in bodies:
                with self.subTest(slope=slope, body=body):
                    result = run(compile_model(body, declarations),
                                 {"u": [[0.0, 2.0], [1.0, 2.0 + slope]]}, times,
                                 stop=1.0, max_step=1.0, vabstol=1e-10, reltol=0.0)
                    for actual, expected in zip(values(result), [0.0, slope, slope, slope]):
                        assert_close(self, actual, expected, delta=1e-10)
                    if declarations:
                        for row in rows(result):
                            assert_close(self, row["y"], row["dut:d"], delta=1e-10)

    def test_ddt_feedthrough_uses_nonzero_joint_dc_equilibrium(self):
        times = [0.0, 2.0 ** -20, 0.5, 1.0]
        # H(s)=(1+s)/(1+2s), input=2+ddt(u). The DC output is 2;
        # for t>0, the added derivative step gives m*(1-.5*exp(-t/2)).
        program = compile_model("V(y,r)<+laplace_nd(2+ddt(V(u,r)),'{1,1},'{1,2});")
        for slope in (-1.0, 1.0):
            with self.subTest(slope=slope):
                result = run(program, {"u": [[0.0, 2.0], [1.0, 2.0 + slope]]}, times,
                             stop=1.0, max_step=1.0, vabstol=1e-10, reltol=0.0)
                expected = [2.0 if t == 0.0 else 2.0 + slope * (1.0 - 0.5 * math.exp(-t / 2.0))
                            for t in times]
                for actual, answer in zip(values(result), expected):
                    assert_close(self, actual, answer, delta=1e-10)

    def test_ddt_identity_feedback_keeps_contribution_order_and_dc(self):
        pieces = ["V(y,r)<+1;", "V(y,r)<+laplace_nd(2+ddt(V(u,r))+.5*V(y,r),'{1,1},'{1,1});"]
        # y=1+2+d+.5*y => y=6+2*d, with d(DC)=0 and d(t>0)=m.
        for slope in (-1.0, 1.0):
            for order in itertools.permutations(pieces):
                with self.subTest(slope=slope, order=order):
                    result = run(compile_model("".join(order)),
                                 {"u": [[0.0, 2.0], [1.0, 2.0 + slope]]}, [0.0, 0.5, 1.0],
                                 stop=1.0, max_step=1.0, vabstol=1e-10, reltol=0.0)
                    for actual, answer in zip(values(result), [6.0, 6.0 + 2.0 * slope, 6.0 + 2.0 * slope]):
                        assert_close(self, actual, answer, delta=1e-10)

    def test_ddt_integral_feedback_preserves_explicit_initial_state(self):
        program = compile_model("V(y,r)<+idt(ddt(V(u,r))-V(y,r),3);")
        times = [0.0, 0.25, 0.5, 1.0]
        result = run(program, {"u": [[0.0, 2.0], [1.0, 3.0]]}, times,
                     stop=1.0, max_step=1.0, vabstol=1e-10, reltol=0.0)
        for time, actual in zip(times, values(result)):
            assert_close(self, actual, 1.0 + 2.0 * math.exp(-time), delta=1e-10)

    def test_ddt_filter_observations_preserve_dc_and_corner_sides(self):
        program = compile_model("V(y,r)<+laplace_nd(ddt(V(u,r)),'{1,1},'{1,1});")
        sources = {"u": [[0.0, 2.0], [0.5, 2.5], [1.0, 2.0]]}
        for times, step in (([0.0, 0.25, 0.5, 1.0], 1.0),
                            ([0.0, 0.125, 0.25, 0.5, 0.75, 1.0], 0.125),
                            ([0.25, 0.5, 1.0], 1.0)):
            with self.subTest(times=times, step=step):
                result = run(program, sources, times, stop=1.0, max_step=step,
                             vabstol=1e-10, reltol=0.0)
                expected = [0.0 if t == 0.0 else (1.0 if t < 0.5 else -1.0) for t in times]
                for actual, answer in zip(values(result), expected):
                    assert_close(self, actual, answer, delta=1e-10)


class DerivativeContracts(unittest.TestCase):
    def test_ddt_of_direct_pwl_uses_documented_side_convention(self):
        program = compile_model("V(y,r)<+ddt(V(u,r));")
        points = [[0.0, 0.0], [1.0, 2.0], [3.0, -2.0], [4.0, -2.0]]
        times = [0.0, 0.5, 1.0, 2.0, 3.0, 4.0]
        # Initial DC derivative is zero; interior and knot samples use the
        # right derivative, except the final stop point which uses the left.
        expected = [0.0, 2.0, -2.0, -2.0, 0.0, 0.0]
        result = run(program, {"u": points}, times, stop=4.0, max_step=4.0)
        for actual, answer in zip(values(result), expected):
            assert_close(self, actual, answer, delta=1e-12)

    def test_ddt_rejects_event_state_impulses_and_discontinuous_guard_use(self):
        cases = [
            ("state", "@(initial_step) q=0; @(timer(1,0,1e-12)) q=1; V(y,r)<+ddt(q);", "real q;"),
            ("canceled_state", "@(initial_step) q=0; @(timer(1,0,1e-12)) q=1; V(y,r)<+ddt(q-q);", "real q;"),
        ]
        for name, body, declarations in cases:
            with self.subTest(name=name):
                program = compile_model(body, declarations)
                with self.assertRaisesRegex(KernelError, "unsupported_operator"):
                    run(program, {"u": [[0.0, 0.0], [2.0, 2.0]]}, [0.0, 1.0, 2.0], stop=2.0, max_step=2.0)

        program = compile_model(
            "@(initial_step) n=0; @(cross(ddt(V(u,r))-.5,1,1e-12,1e-9)) n=n+1; V(y,r)<+n;",
            "integer n;",
        )
        with self.assertRaisesRegex(KernelError, "unsupported_cross"):
            run(program, {"u": [[0.0, 0.0], [2.0, 2.0]]}, [0.0, 2.0], stop=2.0, max_step=2.0)


class HigherOrderLaplaceContracts(unittest.TestCase):
    def run_filter(self, numerator, denominator, *, body_input="V(u,r)", times=None):
        num = ",".join(repr(float(v)) for v in numerator)
        den = ",".join(repr(float(v)) for v in denominator)
        program = compile_model(f"V(y,r)<+laplace_nd({body_input},'{{{num}}},'{{{den}}});")
        times = times or [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
        return run(program, {"u": [[0.0, 0.0], [4.0, 4.0]]}, times, stop=4.0, max_step=4.0)

    def test_second_order_lowpass_ramp_closed_form(self):
        times = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
        result = self.run_filter([1], [1, 2, 1], times=times)
        for time, actual in zip(times, values(result)):
            expected = time - 2.0 + (time + 2.0) * math.exp(-time)
            assert_close(self, actual, expected, delta=3e-8)

    def test_third_order_lowpass_ramp_closed_form(self):
        times = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
        result = self.run_filter([1], [1, 3, 3, 1], times=times)
        for time, actual in zip(times, values(result)):
            expected = time - 3.0 + (3.0 + 2.0 * time + 0.5 * time * time) * math.exp(-time)
            assert_close(self, actual, expected, delta=3e-8)

    def test_full_numerator_terms_are_preserved(self):
        times = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
        result = self.run_filter([1, 1], [1, 2, 1], times=times)
        for time, actual in zip(times, values(result)):
            expected = time - 1.0 + math.exp(-time)
            assert_close(self, actual, expected, delta=3e-8)

    def test_equal_order_feedthrough_filter_keeps_derivative_terms(self):
        times = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0]
        result = self.run_filter([0, 0, 1], [1, 2, 1], times=times)
        for time, actual in zip(times, values(result)):
            expected = time * math.exp(-time)
            assert_close(self, actual, expected, delta=3e-8)

    def test_laplace_dc_feedback_uses_joint_equilibrium(self):
        program = compile_model("V(y,r)<+laplace_nd(1-.5*V(y,r),'{1},'{1,2,1});")
        result = run(program, times=[0.0, 0.5, 2.0, 4.0], stop=4.0, max_step=4.0)
        for actual in values(result):
            assert_close(self, actual, 2.0 / 3.0, delta=2e-9)

    def test_high_order_output_grid_and_max_step_are_invariant(self):
        program = compile_model("V(y,r)<+laplace_nd(V(u,r),'{1},'{1,2,1});")
        sources = {"u": [[0.0, 0.0], [4.0, 4.0]]}
        sparse = [0.0, 0.5, 1.0, 2.0, 4.0]
        dense = [index / 16 for index in range(65)]
        baseline = values(run(program, sources, sparse, stop=4.0, max_step=4.0, vabstol=1e-10, reltol=0.0))
        for times, step in ((sparse, 4.0), (dense, 0.125), (dense, 4.0)):
            result = run(program, sources, times, stop=4.0, max_step=step, vabstol=1e-10, reltol=0.0)
            selected = [values(result)[times.index(time)] for time in sparse]
            for observed, answer in zip(selected, baseline):
                self.assertAlmostEqual(observed, answer, delta=2e-8)

    def test_rescaled_two_pole_ramp_uses_normalized_time(self):
        normalized_times = [0.0, 0.25, 1.0, 2.0, 4.0]
        for tau in (1.0, 1e-3, 1e-6):
            with self.subTest(tau=tau):
                points = [[0.0, 0.0], [4.0 * tau, 4.0]]
                times = [x * tau for x in normalized_times]
                result = run(
                    compile_model(
                        "V(y,r)<+laplace_nd(V(u,r),'{1},'{"
                        + f"1.0,{2.0 * tau!r},{tau * tau!r}"
                        + "});"
                    ),
                    {"u": points},
                    times,
                    stop=4.0 * tau,
                    max_step=4.0 * tau,
                )
                for x, actual in zip(normalized_times, values(result)):
                    expected = x - 2.0 + (x + 2.0) * math.exp(-x)
                    assert_close(self, actual, expected, delta=5e-8)


class AccuracyAndBoundaryContracts(unittest.TestCase):
    def test_tight_voltage_budget_rejects_amplified_history_uncertainty(self):
        # A large but solvable gain tests propagated history error rather than
        # the linear solver's separate near-singular pivot boundary.
        program = compile_model("V(z,r)<+idt(V(u,r),0); V(y,r)<+1e8*V(z,r);", "electrical z;")
        sources = {"u": [[0.0, 0.0], [3.0, 1.0]]}
        exact = 1e8 / 6.0
        with self.assertRaises(KernelError) as error:
            run(program, sources, [1.0], stop=3.0, max_step=3.0, vabstol=1e-12, reltol=0.0)
        self.assertEqual(error.exception.detail["kind"], "waveform_accuracy")
        accepted = run(program, sources, [1.0], stop=3.0, max_step=3.0, vabstol=1e-6, reltol=0.0)
        self.assertAlmostEqual(values(accepted)[0], exact, delta=1e-6)

    def test_state_and_reset_feedback_boundaries_are_explicit_rejections(self):
        cases = [
            ("reset_feedback", "@(initial_step) q=0; @(timer(1,0,1e-12)) q=V(y,r); V(y,r)<+idt(1,0,q);"),
        ]
        for name, body in cases:
            with self.subTest(name=name):
                program = compile_model(body, "real q;")
                with self.assertRaisesRegex(KernelError, "unsupported"):
                    run(program, times=[0.0, 0.5, 1.0, 2.0], stop=2.0, max_step=2.0)

    def test_operator_feedback_inside_event_state_remains_out_of_scope(self):
        source = "@(initial_step) q=0; @(timer(1,0,1e-12)) q=idt(V(u,r),0); V(y,r)<+q;"
        with self.assertRaises(CompileError):
            compile_model(source, "real q;")


if __name__ == "__main__":
    unittest.main()

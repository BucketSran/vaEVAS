"""Independent chain-rule answers through the public compiler/Rust interface."""
import unittest

from evas import CompileError, KernelError, Instance, compile_sources, transient
from test_affine import model, KERNEL

from test_continuous_dynamics import compile_model, run, values, assert_close


class PolynomialDerivativeContracts(unittest.TestCase):
    def test_quadratic_time_derivative_preserves_dc(self):
        program = compile_model("V(y,r)<+ddt(3*$abstime*$abstime+2*$abstime+7);")
        times = [0., .125, .5, 1., 2.]
        result = run(program, times=times)
        for actual, answer in zip(values(result), [0., 2.75, 5., 8., 14.]):
            assert_close(self, actual, answer)

    def test_squared_voltage_derivative_has_physical_knot_sides(self):
        program = compile_model("V(y,r)<+ddt(V(u,r)*V(u,r));")
        times = [0., .25, .5, .75, 1.]
        source = {"u": [[0., 2.], [.5, 3.], [1., 2.]]}
        for step in (1., .125):
            result = run(program, source, times, max_step=step)
            for actual, answer in zip(values(result), [0., 10., -12., -10., -8.]):
                assert_close(self, actual, answer)

    def test_chain_rule_combines_time_voltage_products_and_powers(self):
        program = compile_model("V(y,r)<+ddt($abstime*pow(V(u,r),3));")
        # u=2+t: d(t*u^3)=u^3+3*t*u^2.
        result = run(program, {"u": [[0., 2.], [1., 3.]]}, [0., .25, .5, 1.])
        for actual, answer in zip(values(result), [0., 15.1875, 25., 54.]):
            assert_close(self, actual, answer)

    def test_absolute_time_is_instance_independent_with_strobes(self):
        source = model("V(y,r)<+$abstime; V(d,r)<+ddt($abstime*$abstime);",
                       "electrical d;", ports="u,y,r")
        program = compile_sources({"time.va": source}, [
            Instance("first", "m", dict(u="u", y="y1", r="0")),
            Instance("second", "m", dict(u="u", y="y2", r="0")),
        ])
        result = transient(program, {"u": [[0., 9.], [1., -3.]]}, [0., .25, .75, 1.],
                           stop=1., max_step=1., strobetimes=[.125, .5, .875], kernel=KERNEL)
        samples = list(zip([0., .25, .75, 1.], [r["voltages"] for r in result["solutions"]]))
        samples += list(zip(result["strobe_evidence"]["times"], result["strobe_evidence"]["voltages_V"]))
        for time, voltages in samples:
            output = dict(zip(result["nodes"], voltages))
            for node in ("y1", "y2"):
                assert_close(self, output[node], time)
            for node in ("first:d", "second:d"):
                assert_close(self, output[node], 2 * time)

    def test_noncontinuous_and_unreduced_internal_inputs_stay_rejected(self):
        for body, declarations in (
            ("@(initial_step) q=0; @(timer(0.5)) q=1; V(y,r)<+ddt(q*q);", "real q;"),
            ("V(z,r)<+V(u,r); V(y,r)<+ddt(V(z,r)*V(z,r));", "electrical z;"),
            ("V(y,r)<+ddt(ddt(V(u,r))*V(u,r));", ""),
            ("V(y,r)<+ddt((V(u,r)>0)?V(u,r):0);", ""),
        ):
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                run(compile_model(body, declarations))

    def test_unrelated_events_preserve_derivative_history(self):
        program = compile_model(
            "@(initial_step) q=0; @(timer(0.5)) q=q+1; V(y,r)<+ddt(V(u,r)*V(u,r));", "real q;")
        result = run(program, {"u": [[0., 2.], [1., 3.]]}, [0., .25, .75, 1.])
        for actual, answer in zip(values(result), [0., 4.5, 5.5, 6.]):
            assert_close(self, actual, answer)

    def test_polynomial_integral_operand_keeps_nonzero_initial_value(self):
        program = compile_model("V(y,r)<+ddt(pow(idt(2,3),3));")
        result = run(program, times=[0., .25, .5, 1.])
        for actual, answer in zip(values(result), [0., 73.5, 96., 150.]):
            assert_close(self, actual, answer)

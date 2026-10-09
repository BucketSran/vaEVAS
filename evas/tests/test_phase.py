"""Restricted idtmod/sin phase contracts for D2-style voltage-domain models."""

# Guarded conditions/capabilities: see docs/development/PROCESS.md and docs/development/TRACEABILITY.md
GUARDS = ["DYNAMICS"]

import math
import subprocess
import json
import unittest
from decimal import Decimal, getcontext
from fractions import Fraction as F

from evas.ir import SCHEMA_VERSION
from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance



def decimal_sin(value):
    getcontext().prec = 80
    x = value if isinstance(value, Decimal) else Decimal.from_float(value)
    pi = Decimal("3.14159265358979323846264338327950288419716939937510582097494459230781640628620899")
    two_pi = 2 * pi
    while x > pi:
        x -= two_pi
    while x < -pi:
        x += two_pi
    term = x
    total = x
    n = 1
    while True:
        term *= -x * x / Decimal((2 * n) * (2 * n + 1))
        total += term
        if abs(term) < Decimal("1e-70"):
            return total
        n += 1


def source(body, ports="f,out,total,phase,r", declarations=""):
    return f"""`include "disciplines.vams"
`include "constants.vams"
module m({ports});
input f; output out,total,phase; inout r;
electrical {ports};
{declarations}
analog begin
{body}
end
endmodule"""


def compile_phase(body, declarations="real total_phase, phase_v;"):
    return compile_sources({"phase.va": source(body, declarations=declarations)}, [instance(connections={
        "f": "f", "out": "out", "total": "total", "phase": "phase", "r": "0"})])


def run_phase(points, times, body=None, declarations="real total_phase, phase_v;", **tolerances):
    body = body or """
total_phase = idt(V(f,r), 0.125);
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(total,r)<+total_phase;
V(phase,r)<+phase_v;
V(out,r)<+0.8*sin(2*`M_PI*phase_v);
"""
    return transient(compile_phase(body, declarations), {"f": points}, times, stop=points[-1][0],
                     max_step=points[-1][0] or 1, kernel=KERNEL, **tolerances)


def voltages(result, node):
    index = result["nodes"].index(node)
    return [row["voltages"][index] for row in result["solutions"]]


def integral(points, time, ic=F(1, 8)):
    total = ic
    t = F(time)
    for (s, a), (e, b) in zip(points, points[1:]):
        s, a, e, b = map(F, (s, a, e, b))
        if t <= s:
            break
        end = min(t, e)
        u_end = a + (b - a) * (end - s) / (e - s)
        total += (a + u_end) * (end - s) / 2
    return total


def wrapped(x):
    return x - math.floor(x)


def floor_fraction(value):
    return value.numerator // value.denominator


def rational_wrapped(raw, modulus=1.0, offset=0.0):
    raw = F(raw)
    modulus = F(modulus)
    offset = F(offset)
    turn = floor_fraction((raw - offset) / modulus)
    return raw - turn * modulus


def rational_constant_raw(time, freq, ic=0.125):
    return F(ic) + F(freq) * F(time)


def is_exact_wrap_boundary(raw, modulus=1.0, offset=0.0):
    return (F(raw) - F(offset)) % F(modulus) == 0


class PhaseContracts(unittest.TestCase):
    def test_constant_phase_accumulates_wraps_and_sine_uses_constants_macro(self):
        points = [(0, 0.25), (4, 0.25)]
        times = [0, 1, 2, 3, 4]
        result = run_phase(points, times, vabstol=1e-12, reltol=0)
        for t, total, phase, out in zip(times, voltages(result, "total"),
                                       voltages(result, "phase"), voltages(result, "out")):
            exact = integral(points, t)
            self.assertEqual(F(total), exact)
            self.assertEqual(F(phase), F(wrapped(float(exact))))
            self.assertAlmostEqual(out, .8 * math.sin(2 * math.pi * float(exact)), delta=2e-15)

    def test_chirp_and_negative_frequency_have_independent_oracles(self):
        for points, times in [
            ([(0, 0.25), (2, 1.25)], [0, .5, 1, 1.5, 2]),
            ([(0, -0.25), (2, -0.25)], [0, .5, 1, 1.5, 2]),
        ]:
            result = run_phase(points, times, vabstol=1e-12, reltol=0)
            for t, total, phase, out in zip(times, voltages(result, "total"),
                                           voltages(result, "phase"), voltages(result, "out")):
                exact = integral(points, t)
                self.assertEqual(F(total), exact)
                self.assertEqual(F(phase), F(wrapped(float(exact))))
                self.assertAlmostEqual(out, .8 * math.sin(2 * math.pi * float(exact)), delta=2e-15)

    def test_direct_sin_input_is_input_only_and_sampling_invariant(self):
        body = "V(out,r)<+sin(V(f,r)); V(total,r)<+0; V(phase,r)<+0;"
        points = [(0, 0), (2, math.pi)]
        sparse = run_phase(points, [0, 1, 2], body, declarations="", vabstol=1e-12, reltol=0)
        dense = run_phase(points, [0, .5, 1, 1.5, 2], body, declarations="", vabstol=1e-12, reltol=0)
        self.assertEqual(voltages(sparse, "out"), [0, 1, math.sin(math.pi)])
        self.assertEqual([voltages(dense, "out")[i] for i in [0, 2, 4]], voltages(sparse, "out"))

    def test_direct_sin_matches_decimal_reference_for_binary64_inputs(self):
        body = "V(out,r)<+sin(V(f,r)); V(total,r)<+0; V(phase,r)<+0;"
        values = [0.1, -0.7, 1.23456789012345, 3.0]
        points = [(float(i), v) for i, v in enumerate(values)]
        result = run_phase(points, [p[0] for p in points], body, declarations="", vabstol=1e-12, reltol=0)
        for observed, source_value in zip(voltages(result, "out"), values):
            expected = decimal_sin(source_value)
            self.assertLessEqual(abs(Decimal.from_float(observed) - expected), Decimal("1e-12"))

    def test_repeated_phase_alias_affine_coefficients_match_decimal_reference(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+sin(2*phase_v + phase_v);
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        result = run_phase([(0, 0), (1, 0)], [0, 1], body,
                           declarations="real phase_v;", vabstol=1e-12, reltol=0)
        expected = decimal_sin(Decimal(3) / Decimal(8))
        for observed in voltages(result, "out"):
            self.assertLessEqual(abs(Decimal.from_float(observed) - expected), Decimal("1e-12"))

    def test_repeated_phase_alias_cancellation_keeps_coefficient_roundoff_budget(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+sin(1e16*phase_v + phase_v - (1e16-2)*phase_v);
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        exact = decimal_sin(Decimal(3) / Decimal(8))
        rounded_coeff = decimal_sin(Decimal(1) / Decimal(4))
        self.assertGreater(abs(exact - rounded_coeff), Decimal("0.1"))
        with self.assertRaises(KernelError) as error:
            run_phase([(0, 0), (1, 0)], [0, 1], body,
                      declarations="real phase_v;", vabstol=1e-12, reltol=0)
        self.assertEqual(error.exception.detail["kind"], "waveform_accuracy")

    def test_sin_rejects_second_operator_hidden_by_exact_cancellation(self):
        body = """
phase_p = idtmod(V(f,r), 0.125, 1, 0);
phase_q = idtmod(V(f,r), 0.25, 1, 0);
V(out,r)<+sin(phase_p + phase_q - phase_q);
V(total,r)<+0;
V(phase,r)<+phase_p;
"""
        with self.assertRaises(KernelError) as error:
            run_phase([(0, 0), (1, 0)], [0], body,
                      declarations="real phase_p, phase_q;", vabstol=1e-12, reltol=0)
        self.assertEqual(error.exception.detail["kind"], "unsupported_operator")

    def test_sin_rejects_second_operator_hidden_by_zero_multiplier(self):
        body = """
phase_p = idtmod(V(f,r), 0.125, 1, 0);
phase_q = idtmod(V(f,r), 0.25, 1, 0);
V(out,r)<+sin(phase_p + 0*phase_q);
V(total,r)<+0;
V(phase,r)<+phase_p;
"""
        with self.assertRaises(KernelError) as error:
            run_phase([(0, 0), (1, 0)], [0], body,
                      declarations="real phase_p, phase_q;", vabstol=1e-12, reltol=0)
        self.assertEqual(error.exception.detail["kind"], "unsupported_operator")

    def test_direct_sin_is_transient_operator_not_static_nonlinear_solve(self):
        program = compile_phase("V(out,r)<+sin(V(f,r)); V(total,r)<+0; V(phase,r)<+0;", declarations="")
        with self.assertRaises(KernelError) as error:
            solve(program, ["f"], [[0]], kernel=KERNEL)
        self.assertEqual(error.exception.detail["kind"], "unsupported_analysis")
        self.assertIn("transient", error.exception.detail["message"])

    def test_sine_of_wrapped_phase_uses_two_side_certificate_at_wrap(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+0.8*sin(2*`M_PI*phase_v);
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        result = run_phase([(0, .5), (4, .5)], [1.75], body,
                           declarations="real phase_v;", vabstol=1e-9, reltol=0)
        self.assertLessEqual(abs(voltages(result, "out")[0]), 1e-12)

    def test_wrapped_phase_voltage_certifies_binary64_side_and_exact_boundary(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+0;
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        times = [1.7499999999999998, 1.75, 1.7500000000000002]
        sparse = run_phase([(0, .5), (4, .5)], times, body,
                           declarations="real phase_v;", vabstol=1e-12, reltol=0)
        dense = run_phase([(0, .5), (4, .5)], [0, *times, 4], body,
                          declarations="real phase_v;", vabstol=1e-12, reltol=0)
        budget = F(1, 10**12)
        for observed, t in zip(voltages(sparse, "phase"), times):
            raw = rational_constant_raw(t, .5)
            exact = rational_wrapped(raw)
            if is_exact_wrap_boundary(raw):
                self.assertEqual(F(observed), F(0))
            else:
                self.assertLessEqual(abs(F(observed) - exact), budget)
        self.assertEqual([voltages(dense, "phase")[i] for i in [1, 2, 3]],
                         voltages(sparse, "phase"))

    def test_wrapped_phase_voltage_certifies_negative_frequency_and_offset_boundary(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+0;
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        neg_times = [.24999999999999997, .25, .25000000000000006]
        result = run_phase([(0, -.5), (1, -.5)], neg_times,
                           body, declarations="real phase_v;", vabstol=1e-12, reltol=0)
        budget = F(1, 10**12)
        for observed, t in zip(voltages(result, "phase"), neg_times):
            raw = rational_constant_raw(t, -.5)
            exact = rational_wrapped(raw)
            if is_exact_wrap_boundary(raw):
                self.assertEqual(F(observed), F(0))
            else:
                self.assertLessEqual(abs(F(observed) - exact), budget)

        offset_body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0.25);
V(out,r)<+0;
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        offset_times = [.2499999999999999, .25, .2500000000000001]
        offset = run_phase([(0, .5), (1, .5)], offset_times,
                           offset_body, declarations="real phase_v;", vabstol=1e-12, reltol=0)
        for observed, t in zip(voltages(offset, "phase"), offset_times):
            raw = rational_constant_raw(t, .5)
            exact = rational_wrapped(raw, offset=.25)
            if is_exact_wrap_boundary(raw, offset=.25):
                self.assertEqual(F(observed), F(.25))
            else:
                self.assertLessEqual(abs(F(observed) - exact), budget)

        time=.24999999999999997
        result=run_phase([(0, .5), (1, .5)], [time], offset_body,
                         declarations="real phase_v;", vabstol=1e-12, reltol=0)
        actual=voltages(result,"phase")[0]
        self.assertLess(actual,1.25)
        self.assertLessEqual(abs(F(actual)-rational_wrapped(rational_constant_raw(time,.5),offset=.25)),budget)

    def test_wrapped_phase_voltage_certifies_binary64_coefficient_boundary(self):
        body = """
phase_v = idtmod(V(f,r)/3, 0.125, 1, 0);
V(out,r)<+0;
V(total,r)<+0;
V(phase,r)<+phase_v;
"""
        time=1.7499999999999998
        result=run_phase([(0,1.5),(4,1.5)],[time],body,
                         declarations="real phase_v;",vabstol=1e-5,reltol=0)
        # The compiler stores binary64 1/3; retain that distinct reference.
        exact=rational_wrapped(F(.125)+F(1.5)*F(1/3)*F(time))
        actual=voltages(result,"phase")[0]
        self.assertGreater(actual,.99)
        self.assertLess(actual,1)
        self.assertLessEqual(abs(F(actual)-exact),F(1,2**52))
        # A mathematically known side still cannot evade voltage rounding.
        with self.assertRaises(KernelError) as error:
            run_phase([(0,1.5),(4,1.5)],[time],body,
                      declarations="real phase_v;",vabstol=1e-20,reltol=0)
        self.assertEqual(error.exception.detail["kind"],"waveform_accuracy")

    def test_exact_binary_wrapped_output_meets_strict_voltage_budget(self):
        body = """
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(total,r)<+0;
V(phase,r)<+phase_v;
V(out,r)<+0;
"""
        times=[0,3.5000000000000004]
        result=run_phase([(0,.25),(4,.25)],times,body,
                         declarations="real phase_v;",vabstol=1e-16,reltol=0)
        self.assertEqual([F(x) for x in voltages(result,"phase")],
                         [rational_wrapped(rational_constant_raw(t,.25)) for t in times])

    def test_unsupported_phase_forms_are_explicitly_rejected(self):
        for body in [
            "phase_v = idtmod(V(f,r),0); V(out,r)<+phase_v; V(total,r)<+0; V(phase,r)<+0;",
            "phase_v = idtmod(V(f,r),0,0,0); V(out,r)<+phase_v; V(total,r)<+0; V(phase,r)<+0;",
            "@(initial_step) q=0; V(out,r)<+sin(q); V(total,r)<+0; V(phase,r)<+0;",
        ]:
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                declarations = "real phase_v; real q;" if "q" in body else "real phase_v;"
                run_phase([(0, 0), (1, 0)], [0, 1], body, declarations=declarations)

    def test_raw_ir_rejects_missing_or_extra_phase_operator_fields(self):
        program = compile_phase("""
phase_v = idtmod(V(f,r), 0.125, 1, 0);
V(out,r)<+sin(2*`M_PI*phase_v); V(total,r)<+0; V(phase,r)<+phase_v;
""", declarations="real phase_v;").to_dict()
        mutations = []
        bad = json.loads(json.dumps(program))
        del bad["operators"][0]["modulus"]
        mutations.append(bad)
        bad = json.loads(json.dumps(program))
        bad["operators"][0]["reset"] = 0
        mutations.append(bad)
        bad = json.loads(json.dumps(program))
        bad["operators"][1]["input"] = {"op": "operator", "operator": 99}
        mutations.append(bad)
        for mutated in mutations:
            response = subprocess.run([str(KERNEL)], input=json.dumps(dict(
                program=mutated, driven=["f"], samples=[],
                transient=dict(pwl=[[(0, 0.25), (1, 0.25)]], output_times=[0, 1], stop=1, max_step=1))),
                text=True, capture_output=True)
            with self.subTest(mutated=mutated):
                self.assertEqual(response.returncode, 2, response.stdout)
                self.assertIn(json.loads(response.stderr)["kind"],
                              ["invalid_request", "invalid_ir", "unsupported_operator"])


if __name__ == "__main__":
    unittest.main()

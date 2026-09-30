"""Restricted idtmod/sin phase contracts for D2-style voltage-domain models."""
import math
import subprocess
import json
import unittest
from decimal import Decimal, getcontext
from fractions import Fraction as F

from evas import CompileError, KernelError, compile_sources, solve, transient
from test_affine import KERNEL, instance



def decimal_sin(value):
    getcontext().prec = 80
    x = Decimal.from_float(value)
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
    return f"""`include "constants.vams"
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
total_phase = idt(V(f,r), .125);
phase_v = idtmod(V(f,r), .125, 1, 0);
V(total,r)<+total_phase;
V(phase,r)<+phase_v;
V(out,r)<+.8*sin(2*`M_PI*phase_v);
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

    def test_direct_sin_is_transient_operator_not_static_nonlinear_solve(self):
        program = compile_phase("V(out,r)<+sin(V(f,r)); V(total,r)<+0; V(phase,r)<+0;", declarations="")
        with self.assertRaises(KernelError) as error:
            solve(program, ["f"], [[0]], kernel=KERNEL)
        self.assertEqual(error.exception.detail["kind"], "unsupported_analysis")
        self.assertIn("transient", error.exception.detail["message"])

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
phase_v = idtmod(V(f,r), .125, 1, 0);
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

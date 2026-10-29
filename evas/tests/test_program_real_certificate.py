"""Program reals in the waveform certificate: values selected by a voltage condition.

A real assigned under a voltage-dependent if or ?: and then contributed is a rounded program value
(ADR-006). While a PWL input ramps, the input at an output row is an interval, so the rounded
value has several possible binary64 values and no finite interval derivative; the kernel must
still certify the answer or refuse it for its real accuracy reason. The models are the minimal
probes of #287 R2 (comment 6484013758) and the discriminating models R1-R4 of its requirement card.

The expected answers are not EVAS output. At each binary64 output row the PWL input is an exact
Fraction, every program-real assignment and arithmetic operation rounds to nearest with ties to
even (Python float of a Fraction), and contributions and contribution-level selections are exact.
Each nominal answer must lie within vabstol + reltol*|target| of that value and the enclosure the
kernel reports must contain it. Rows at an exact discontinuous switch are not scored (the two
one-sided values differ beyond the budget there).
"""
GUARDS = ["ANALOG", "LANG"]

from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

STOP = 2e-9
RAMP = [[0, 0.4], [0.5e-9, 0.4], [1.5e-9, 0.1], [2e-9, 0.1]]
SHORT = [[0, 0.4], [0.5e-9, 0.4], [1.5e-9, 0.3], [2e-9, 0.3]]
CROSS = [[0, 0.4], [0.5e-9, 0.4], [1.5e-9, -0.4], [2e-9, -0.4]]
OFFGRID = [[0, 0.4], [0.5e-9, 0.4], [1.53e-9, -0.4], [2e-9, -0.4]]
FLAT = [[0, 0.4], [2e-9, 0.4]]
LOW = [[0, 0.1], [2e-9, 0.1]]
N = [[0, 0.2], [2e-9, 0.2]]
VABSTOL, RELTOL = 1e-12, 1e-10
QUARTER, HALF = F(1, 4), F(1, 2)
CLAMP = "den = V(d); if (abs(den) < 0.25) den = (den > 0.0) ? 0.25 : -0.25; "


def rn(value):
    return F(float(value))


def symmetric(d):
    den = rn(d)
    if abs(den) < QUARTER:
        den = QUARTER if den > 0 else -QUARTER
    return den


def floor_quarter(d):
    den = rn(d)
    return QUARTER if den < QUARTER else den


# name: (analog body, V(d) wave, exact y(d, n), discontinuous switch threshold of d or None)
TRIGGERS = {
    "a-offgrid-zero": (CLAMP + "V(y) <+ V(n) / den;", OFFGRID, lambda d, n: n / symmetric(d), F(0)),
    "b-exact-zero-on-grid": (CLAMP + "V(y) <+ V(n) / den;", CROSS, lambda d, n: n / symmetric(d), F(0)),
    "c-never-zero-inside-clamp": (CLAMP + "V(y) <+ V(n) / den;", RAMP, lambda d, n: n / symmetric(d), None),
    "f-clamp-multiply": (CLAMP + "V(y) <+ V(n) * den;", RAMP, lambda d, n: n * symmetric(d), None),
    "h-clamp-read": (CLAMP + "V(y) <+ den;", RAMP, lambda d, n: symmetric(d), None),
    "i-clamp-add": (CLAMP + "V(y) <+ V(n) + den;", RAMP, lambda d, n: n + symmetric(d), None),
    "j-one-ternary-divide": ("den = (abs(V(d)) < 0.25) ? ((V(d) > 0.0) ? 0.25 : -0.25) : V(d);"
                             " V(y) <+ V(n) / den;", RAMP, lambda d, n: n / symmetric(d), None),
    "k-literal-branch-divide": ("den = V(d); if (den < 0.25) den = 0.25; V(y) <+ V(n) / den;", RAMP,
                                lambda d, n: n / floor_quarter(d), None),
    "p4-both-arms-voltage": ("den = (V(d) < 0.25) ? 0.5*V(d) : V(d); V(y) <+ den;", RAMP,
                             lambda d, n: rn(HALF * rn(d)) if rn(d) < QUARTER else rn(d), QUARTER),
    "p7-clamp-on-sum": ("den = V(d) + V(n); if (den < 0.45) den = 0.45; V(y) <+ den;", RAMP,
                        lambda d, n: max(rn(rn(d) + rn(n)), rn(F(0.45))), None),
}
CONTROLS = {
    "d-var-no-clamp": ("den = V(d); V(y) <+ V(n) / den;", FLAT, lambda d, n: n / rn(d), None),
    "e-direct-divide": ("V(y) <+ V(n) / V(d);", FLAT, lambda d, n: n / d, None),
    "g-clamp-divide-constant": (CLAMP + "V(y) <+ V(n) / den;", FLAT, lambda d, n: n / symmetric(d), None),
    "p1-direct-ternary": ("V(y) <+ (V(d) < 0.25) ? 0.25 : V(d);", RAMP, lambda d, n: max(d, QUARTER), None),
    "p2-max": ("V(y) <+ max(V(d), 0.25);", RAMP, lambda d, n: max(d, QUARTER), None),
    "p3-if-else-contribution": ("if (V(d) < 0.25) V(y) <+ 0.25; else V(y) <+ V(d);", RAMP,
                                lambda d, n: max(d, QUARTER), None),
    "p5-constant-arm-from-start": ("den = V(d); if (den < 0.25) den = 0.25; V(y) <+ den;", LOW,
                                   lambda d, n: floor_quarter(d), None),
    "p6-constant-arm-divide-no-switch": ("den = V(d); if (den < 0.25) den = 0.25; V(y) <+ V(n) / den;", LOW,
                                         lambda d, n: n / floor_quarter(d), None),
    "x-control-clamp-on-sum-never-taken": ("den = V(d) + V(n); if (den < 0.45) den = 0.45; V(y) <+ den;", FLAT,
                                           lambda d, n: max(rn(rn(d) + rn(n)), rn(F(0.45))), None),
}
DISCRIMINATING = {
    "R1-ramp-no-flip-branched": (CLAMP + "V(y) <+ den;", SHORT, lambda d, n: symmetric(d), None),
    "R2-ramp-unbranched-read": ("den = V(d); V(y) <+ den;", RAMP, lambda d, n: rn(d), None),
    "R3-ramp-unbranched-divide": ("den = V(d); V(y) <+ V(n) / den;", SHORT, lambda d, n: n / rn(d), None),
    "R4-direct-both-arms": ("V(y) <+ (V(d) < 0.25) ? 0.5*V(d) : V(d);", RAMP,
                            lambda d, n: HALF * d if d < QUARTER else d, QUARTER),
}
CONSTANT_INPUT = {"d-var-no-clamp", "e-direct-divide", "g-clamp-divide-constant", "p5-constant-arm-from-start",
                  "p6-constant-arm-divide-no-switch", "x-control-clamp-on-sum-never-taken"}


def rows(wave):
    """The SCS output grid: k*binary64(10 ps) below stop, stop and every knot."""
    return sorted({k * 1e-11 for k in range(201) if k * 1e-11 < STOP} | {STOP} | {t for t, _ in wave})


def program(body):
    source = (f'`include "disciplines.vams"\nmodule m(n, d, y); input n, d; output y;'
              f' electrical n, d, y; real den, q; analog begin {body} end endmodule')
    return compile_sources({"program-real.va": source}, [Instance("dut", "m", dict(n="n", d="d", y="y"))])


def pwl(points, time):
    """Exact value of a PWL wave at a binary64 time."""
    t = F(time)
    knots = [(F(a), F(b)) for a, b in points]
    for (t0, v0), (t1, v1) in zip(knots, knots[1:]):
        if t0 <= t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return knots[-1][1]


def run(body, wave, **options):
    p = program(body)
    options = dict(dict(vabstol=VABSTOL, reltol=RELTOL), **options)
    times = rows(wave)
    result = transient(p, {"n": N, "d": wave}, times, stop=STOP, max_step=1e-11, kernel=KERNEL, **options)
    return p, times, result


class ProgramRealWaveformCertificate(unittest.TestCase):
    def scored(self, name, case):
        """Run one model; check every scored row and return {time: (y, target)}."""
        body, wave, expected, switch = case
        p, times, result = run(body, wave)
        y = p.nodes.index("y")
        bounds = result["observation_evidence"]["voltage_bounds_V"]
        self.assertEqual(len(result["solutions"]), len(times))
        values = {}
        for time, row, box in zip(times, result["solutions"], bounds):
            d = pwl(wave, time)
            if switch is not None and abs(d - switch) < F(1, 10**12):
                continue
            target = expected(d, pwl(N, time))
            actual = F(row["voltages"][y])
            budget = F(VABSTOL) + F(RELTOL) * abs(target)
            self.assertLessEqual(abs(actual - target), budget, (name, time, float(actual), float(target)))
            self.assertLessEqual(F(box[y][0]), target, (name, time, box[y]))
            self.assertLessEqual(target, F(box[y][1]), (name, time, box[y]))
            values[time] = (row["voltages"][y], target)
        return values

    def test_program_real_selected_by_voltage_condition_minimal_models(self):
        for name, case in TRIGGERS.items():
            with self.subTest(model=name):
                self.scored(name, case)

    def test_program_real_minimal_controls_unchanged(self):
        for name, case in CONTROLS.items():
            with self.subTest(model=name):
                values = self.scored(name, case)
                if name in CONSTANT_INPUT:
                    # Inputs are knots here, so the answer is the nearest double of the target.
                    for actual, target in values.values():
                        self.assertEqual(actual, float(target), name)

    def test_program_real_ramp_without_flip(self):
        # R1 has a condition that never flips on its ramp; R2 and R3 have none.
        for name, case in DISCRIMINATING.items():
            if name.startswith(("R1", "R2", "R3")):
                with self.subTest(model=name):
                    self.scored(name, case)

    def test_program_real_variable_and_direct_forms_agree(self):
        for variable, direct in [(TRIGGERS["p4-both-arms-voltage"], DISCRIMINATING["R4-direct-both-arms"]),
                                 (TRIGGERS["h-clamp-read"], CONTROLS["p1-direct-ternary"])]:
            with self.subTest(body=variable[0]):
                a = self.scored("variable", variable)
                b = self.scored("direct", direct)
                for time in a.keys() & b.keys():
                    budget = F(VABSTOL) + F(RELTOL) * abs(a[time][1])
                    self.assertLessEqual(abs(F(a[time][0]) - F(b[time][0])), 2 * budget, time)

    def test_clamped_divider_never_reports_zero_denominator(self):
        cases = {name: (TRIGGERS[name], symmetric) for name in ("a-offgrid-zero", "b-exact-zero-on-grid",
                                                                "c-never-zero-inside-clamp", "j-one-ternary-divide")}
        cases["k-literal-branch-divide"] = (TRIGGERS["k-literal-branch-divide"], floor_quarter)
        cases["program-real-division"] = (("den = V(d); if (den < 0.25) den = 0.25; q = V(n) / den; V(y) <+ q;",
                                           RAMP, lambda d, n: rn(rn(n) / floor_quarter(d)), None), floor_quarter)
        for name, (case, denominator) in cases.items():
            with self.subTest(model=name):
                self.scored(name, case)
                # The selected denominator is at least 1/4 in magnitude at every row.
                wave = case[1]
                self.assertGreaterEqual(min(abs(denominator(pwl(wave, t))) for t in rows(wave)), QUARTER)

    def test_input_uncertainty_beyond_the_budget_is_refused_at_the_output(self):
        # Each relation's own residual fits 1e-5 V, but 1000*(den-0.396)
        # amplifies the 1 uV input band of the rounded value to about 1 mV.
        body = "den = (V(d) < 0.25) ? 0.5*V(d) : V(d); V(y) <+ 1000*(den - 0.396);"
        with self.assertRaisesRegex(KernelError, "waveform_accuracy.*same-time forward error at y"):
            run(body, SHORT, source_errors={"d": 1e-6}, vabstol=1e-5, reltol=0)
        p, times, result = run(body, SHORT, source_errors={"d": 1e-6}, vabstol=1e-2, reltol=0)
        y = p.nodes.index("y")
        for time, row in zip(times, result["solutions"]):
            exact = 1000 * (rn(pwl(SHORT, time)) - F(0.396))
            self.assertLessEqual(abs(F(row["voltages"][y]) - exact), F(1e-2))

    def test_a_rounded_value_read_back_by_its_own_relation_is_not_answered(self):
        # den = V(y) and V(y) <+ den: every value solves the same-time equation.
        with self.assertRaises(KernelError):
            run("den = V(y); V(y) <+ den;", RAMP)


if __name__ == "__main__":
    unittest.main()

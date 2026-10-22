"""Issue #226: a variable-start timer that fires at t=0 must seed transition.

Model and request come from the 2026-10-14 Spectre characterization
``n18-dynamic-zero-v1`` (cases ``fixed_zero``, ``fixed_independent``,
``held_zero``, ``held_without_fixed`` and ``held_independent``). ``start`` is
a variable that equals 0, so ``@(timer(start,0,0.001)) a=1`` fires at t=0.

Independent answer (hand derivation, not EVAS output): the t=0 event sets
a=1 before the first output, so the transition input q+a is 1 from t=0. A
transition whose input never changes after initialization stays at its
initial value, so y(t)=1 for every t. z=a=1 and w=0.75, or
w=0.75+t^2/2 for the ``idt(V(u),0.75)`` variant with u(t)=t.

Spectre 21.1.0.509.isr12 (raw PSF of all five cases, analysis budget 1 uV)
agrees: y=z=1 at all 14 requested times, w as above (max deviation 7e-15 V).

Contract: either these answers within ``BUDGET`` or an honest refusal
(``unsupported`` or ``numerical`` diagnostic category). Main ``a4d2b875``
returns neither for the variable-start cases: y=0,0,0,0.25,0.75,1,1 at
TIMES, without a diagnostic, while the literal ``timer(0,...)`` cases already
give y=1. The three variable-start tests are marked as expected failures for
#226; remove the decorators when the issue is fixed (an unexpected success
fails the regression run).
"""
GUARDS = ["TIMER", "TRANSITION", "EVENT-ORDER", "DYNAMICS", "DEV:silent-error-regression"]

from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

TIMES = [0., .0625, .125, .25, .5, .75, 1.]
BUDGET = 1e-9
REFUSAL_CATEGORIES = ("unsupported", "numerical")

# Event blocks of the Spectre cases; the remaining source is shared.
FIXED_NEIGHBOUR = "@(timer(0,0,0)) q=q; "
VARIABLE_START = "@(timer(start,0,0.001)) a=1; "
LITERAL_START = "@(timer(0,0,0.001)) a=1; "
CONSTANT_W = "0.75"
INTEGRAL_W = "idt(V(u,r),0.75)"


def source(events, w):
    return ('`include "disciplines.vams"\n'
            'module m(u,y,z,w,r); input u; output y,z,w; inout r; electrical u,y,z,w,r; '
            'real q,a,start; analog begin @(initial_step) begin q=0; a=0; start=0; end '
            f'{events}V(y,r)<+transition(q+a,0.125,0.5,0.5); V(z,r)<+a; V(w,r)<+{w}; '
            'end endmodule')


def expected_w(w):
    if w == CONSTANT_W:
        return lambda t: F(3, 4)
    return lambda t: F(3, 4) + F(t) ** 2 / 2


class VariableStartZeroTimer(unittest.TestCase):
    def assert_seeded_or_refused(self, events, w):
        program = compile_sources({"dut.va": source(events, w)}, [Instance(
            "dut", "m", dict(u="u", y="y", z="z", w="w", r="0"), {})])
        try:
            result = transient(program, {"u": [[0., 0.], [1., 1.]]}, TIMES, stop=1.,
                               max_step=0.015625, vabstol=BUDGET, reltol=0, kernel=KERNEL)
        except KernelError as refusal:
            self.assertIn(refusal.diagnostic["category"], REFUSAL_CATEGORIES, refusal.detail)
            return
        self.assertEqual(len(result["solutions"]), len(TIMES))
        index = {node: result["nodes"].index(node) for node in "yzw"}
        w_answer = expected_w(w)
        for t, row in zip(TIMES, result["solutions"], strict=True):
            values = row["voltages"]
            self.assertAlmostEqual(values[index["y"]], 1., delta=BUDGET, msg=("y", t))
            self.assertAlmostEqual(values[index["z"]], 1., delta=BUDGET, msg=("z", t))
            self.assertAlmostEqual(values[index["w"]], float(w_answer(t)), delta=BUDGET,
                                   msg=("w", t))

    def test_literal_zero_start_seeds_transition(self):
        # Spectre cases fixed_zero and fixed_independent; main already agrees.
        for w in (CONSTANT_W, INTEGRAL_W):
            with self.subTest(w=w):
                self.assert_seeded_or_refused(FIXED_NEIGHBOUR + LITERAL_START, w)

    @unittest.expectedFailure  # Issue #226: silent wrong y on main.
    def test_variable_zero_start_beside_fixed_zero_timer(self):
        # Spectre case held_zero.
        self.assert_seeded_or_refused(FIXED_NEIGHBOUR + VARIABLE_START, CONSTANT_W)

    @unittest.expectedFailure  # Issue #226: silent wrong y on main.
    def test_variable_zero_start_alone(self):
        # Spectre case held_without_fixed.
        self.assert_seeded_or_refused(VARIABLE_START, CONSTANT_W)

    @unittest.expectedFailure  # Issue #226: silent wrong y on main.
    def test_variable_zero_start_beside_independent_integral(self):
        # Spectre case held_independent.
        self.assert_seeded_or_refused(FIXED_NEIGHBOUR + VARIABLE_START, INTEGRAL_W)


if __name__ == "__main__":
    unittest.main()

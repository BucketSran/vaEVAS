"""Issue #227: an unrelated timer at the transition ramp end must not move history.

Model and independent answer come from ``answers`` in
``evas/tests/test_exact_transition_deadlines.py`` on branch
``codex/evas-night-source-transition`` (N06 exact deadlines). Only the
three-tick contract is ported here.

The first timer at ``start`` changes q from q0 to q1, so y is a clipped ramp
of width ``width``. The second timer at ``tick`` only increments ``count``;
y, its first-order filter f and its integral z must not depend on ``tick``.
Independent answers: clipped ramp and its exact area with ``Fraction``; the
filtered ramp step/ramp solution in 80-digit ``Decimal``.

Contract: y and f within ``VOLTAGE_BUDGET`` (the requested vabstol), z within
``AREA_BUDGET``, or an honest refusal. On main ``a4d2b875`` the ticks
2.2 us and 2.3 us match to about 7e-17 V. Tick 2.25 us equals the ramp end
(2 us + 0.25 us): f(2.25 us) is -0.2135 instead of +0.0708 (error 0.284 V)
and z(2.25 us) is 8.75e-7 instead of 1e-6, without a diagnostic. That tick
is an expected failure for #227; remove the decorator when it is fixed.
"""
GUARDS = ["TIMER", "TRANSITION", "LAPLACE", "DYNAMICS", "EVENT-ORDER",
          "DEV:silent-error-regression"]

from decimal import Decimal, localcontext
from fractions import Fraction as F
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

SOURCE = '''`include "disciplines.vams"
module edge(y,f,z,n);
 output y,f,z,n; electrical y,f,z,n;
 parameter real start=2e-6, width=2.5e-7, tick=2.25e-6;
 parameter real q0=0.5, q1=-0.5, tau=2e-7;
 real q; integer count;
 analog begin
  @(initial_step) begin q=q0; count=0; end
  @(timer(start,0,1e-13)) begin q=q1; count=count+1; end
  @(timer(tick,0,1e-13)) count=count+1;
  V(y)<+transition(q,0,width,width);
  V(f)<+laplace_nd(V(y),'{1},'{1,tau});
  V(z)<+idt(V(y),0);
  V(n)<+count;
 end
endmodule
'''
START, TIMER_TOLERANCE = 2e-6, 1e-13
TIMES = [0., 2e-6, 2.2e-6, 2.25e-6, 2.3e-6, 2.4e-6, 2.5e-6, 2.6e-6, 2.8e-6]
VOLTAGE_BUDGET = 1e-9
# Same area budget as the branch's nearby-retarget control (z is about 1e-6 V*s).
AREA_BUDGET = 2e-14
REFUSAL_CATEGORIES = ("unsupported", "numerical")


def answers(t, start=2e-6, width=2.5e-7, q0=.5, q1=-.5, tau=2e-7):
    """Clipped ramp, its exact area, and the first-order step/ramp solution."""
    t, a, b, p, q = map(F, (t, start, width, q0, q1))
    h = max(F(0), t-a)
    edge = p + (q-p)*min(h/b, 1)
    area = p*t + (q-p)*(min(h, b)**2/(2*b) + max(F(0), h-b))
    with localcontext() as ctx:
        ctx.prec = 80
        decimal = lambda x: Decimal(x.numerator)/Decimal(x.denominator)
        hd, bd, pd, qd, td = map(decimal, (h, b, p, q, F(tau)))
        ramp_time = min(hd, bd)
        ramp_end = pd+(qd-pd)/bd*(ramp_time-td*(1-(-ramp_time/td).exp()))
        filtered = ramp_end if hd <= bd else qd+(ramp_end-qd)*(-(hd-bd)/td).exp()
    return float(edge), float(filtered), float(area)


class UnrelatedTimerAtRampEnd(unittest.TestCase):
    def assert_answers_or_refused(self, tick):
        program = compile_sources({"edge.va": SOURCE}, [Instance(
            "dut", "edge", {node: node for node in "yfzn"}, {"tick": tick})])
        try:
            result = transient(program, {}, TIMES, stop=TIMES[-1], max_step=3.125e-8,
                               vabstol=VOLTAGE_BUDGET, reltol=0, kernel=KERNEL)
        except KernelError as refusal:
            self.assertIn(refusal.diagnostic["category"], REFUSAL_CATEGORIES, refusal.detail)
            return
        events = result["transient"]["events"]
        self.assertEqual(len(events), 2)
        for event, nominal in zip(events, (START, tick), strict=True):
            self.assertGreaterEqual(F(event["time"]), F(nominal))
            self.assertLessEqual(F(event["time"]) - F(nominal), F(TIMER_TOLERANCE))
        self.assertEqual(len(result["solutions"]), len(TIMES))
        index = {node: result["nodes"].index(node) for node in "yfzn"}
        for t, row in zip(TIMES, result["solutions"], strict=True):
            values = row["voltages"]
            y, f, z = answers(t)
            self.assertAlmostEqual(values[index["y"]], y, delta=VOLTAGE_BUDGET, msg=("y", t))
            self.assertAlmostEqual(values[index["f"]], f, delta=VOLTAGE_BUDGET, msg=("f", t))
            self.assertAlmostEqual(values[index["z"]], z, delta=AREA_BUDGET, msg=("z", t))
            if t not in (START, tick):
                # Away from the two event instants the count is unambiguous.
                self.assertEqual(values[index["n"]], int(t > START) + int(t > tick), msg=("n", t))

    def test_tick_inside_ramp_keeps_independent_history(self):
        self.assert_answers_or_refused(2.2e-6)

    def test_tick_after_ramp_keeps_independent_history(self):
        self.assert_answers_or_refused(2.3e-6)

    @unittest.expectedFailure  # Issue #227: silent wrong f and z on main.
    def test_tick_at_ramp_end_keeps_independent_history(self):
        self.assert_answers_or_refused(2.25e-6)


if __name__ == "__main__":
    unittest.main()

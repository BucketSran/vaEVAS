"""Same-time feedback through program reals: the real-arithmetic same-time equation.

A rounded program value that feeds the equation it is computed from at the same time point
(an event sample q=f(V(y)) with V(y) <+ q) is the root of that equation in real arithmetic,
stored as the binary64 rounding of the root (decision 22, D-R2-1 option A, a clarification of
ADR-006). An event equation that is not jointly affine is refused before a local proof can
select one of its roots: y = y*y has the two real roots 0 and 1. y = y + 1 has no real root
and stays refused.

The expected values are exact rational roots computed here, not EVAS output. Rows and the
stored value are scored within the EVAS default budget, 1e-12 V + 1e-10*|y|; the row at the
event instant is not scored.
"""
GUARDS = ["EVENT-ORDER", "ANALOG"]

from fractions import Fraction as Q
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

STEP = 0.0625


def budget(target):
    return Q(1e-12) + Q(1e-10) * abs(target)


def run(body, stop):
    p = compile_sources({'feedback.va': model(body, 'real q;')}, [instance()])
    times = [k * STEP for k in range(int(stop / STEP) + 1)]
    result = transient(p, {'u': [[0, 0], [stop, 0]]}, times, stop=stop, max_step=STEP, kernel=KERNEL)
    return p, times, result


class SameTimeProgramRealEquation(unittest.TestCase):
    def test_nonlinear_event_feedback_with_two_real_roots_is_refused(self):
        with self.assertRaisesRegex(KernelError, 'unsupported_transient: same-time feedback through a '
                                                 'program real is nonlinear'):
            run('@(initial_step) q=0.1; @(timer(0.25)) q=V(y,r)*V(y,r); V(y,r)<+q;', 0.5)

    def test_event_feedback_without_a_real_root_is_refused(self):
        with self.assertRaises(KernelError):
            run('@(initial_step) q=0; @(timer(0.5)) q=V(y,r)+1; V(y,r)<+q;', 1.0)

    def test_affine_event_feedback_answers_the_real_root(self):
        # (body, stop, event time, y before, real root of the same-time equation after)
        cases = [('@(initial_step) q=0; @(timer(0.5)) q=0.5*V(y,r)+1; V(y,r)<+q;', 1.0, 0.5, Q(0), Q(2)),
                 ('@(initial_step) q=0.1; @(timer(0.25)) q=0.5*V(y,r)+0.05; V(y,r)<+q;', 0.5, 0.25,
                  Q(0.1), Q(0.1)),
                 # q -> RN(1 - q/2) has no binary64 fixed point next to 2/3.
                 ('@(initial_step) q=0; @(timer(0.5)) q=-0.5*V(y,r)+1; V(y,r)<+q;', 1.0, 0.5, Q(0), Q(2, 3)),
                 # Not contractive: y = 2*y + 1 has the single root -1.
                 ('@(initial_step) q=0; @(timer(0.5)) q=2*V(y,r)+1; V(y,r)<+q;', 1.0, 0.5, Q(0), Q(-1))]
        for body, stop, event, before, root in cases:
            with self.subTest(body=body):
                p, times, result = run(body, stop)
                y = p.nodes.index('y')
                for time, row in zip(times, result['solutions']):
                    if time == event:
                        continue
                    target = before if time < event else root
                    self.assertLessEqual(abs(Q(row['voltages'][y]) - target), budget(target), time)
                stored = Q(result['transient']['states'][-1][0])
                self.assertLessEqual(abs(stored - root), budget(root))


if __name__ == '__main__':
    unittest.main()

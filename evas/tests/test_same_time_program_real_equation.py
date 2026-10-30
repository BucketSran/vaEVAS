"""Same-time feedback through program reals: the real-arithmetic same-time equation.

A rounded program value that feeds the equation it is computed from at the same time point
(an event sample q=f(V(y)) with V(y) <+ q) is the root of that equation in real arithmetic,
stored as the binary64 rounding of the root (decision 22, D-R2-1 option A, a clarification of
ADR-006), even where the rounded map has no binary64 fixed point or another one. An event
equation that is not jointly affine is refused before a local proof can select one of its
roots: y = y*y has the two real roots 0 and 1. y = y + 1 has no real root and stays refused.

Decision 22 is implemented where every unknown of the activation is defined by exactly one
grounded relation. A same-time cycle through a program real across a relation to a driven
node instead of ground, or between two unknown nodes, and an event cycle that is not jointly
affine, are refused as a capability limit even where the exact system has one solution; the
refusal does not claim that it has none or several.

The expected values are exact rational roots computed here, not EVAS output. Rows are scored
within the EVAS default budget, 1e-12 V + 1e-10*|y|, and the row at the event instant is not
scored; stored values and the members of a cycle are the rounding of the root bit for bit.
"""
GUARDS = ["EVENT-ORDER", "ANALOG"]

from fractions import Fraction as Q
import unittest

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

STEP = 0.0625
CAPABILITY = (r'^unsupported_transient: same-time feedback through a program real at .+ through '
              r'a relation (between two unknown nodes|to a driven node instead of ground) is not '
              r'implemented \(capability limit\)$')
NONAFFINE_EVENT = (r'^unsupported_transient: certification of same-time feedback through a program '
                   r'real at .+ that is not jointly affine is not implemented in an event '
                   r'activation \(capability limit\)$')


def budget(target):
    return Q(1e-12) + Q(1e-10) * abs(target)


def run(body, stop):
    p = compile_sources({'feedback.va': model(body, 'real q;')}, [instance()])
    times = [k * STEP for k in range(int(stop / STEP) + 1)]
    result = transient(p, {'u': [[0, 0], [stop, 0]]}, times, stop=stop, max_step=STEP, kernel=KERNEL)
    return p, times, result


class SameTimeProgramRealEquation(unittest.TestCase):
    def refusal(self, body, declarations):
        # The review r1 shape: module m(u,y), u driven at 0, default budget.
        source = ('`include "disciplines.vams"\nmodule m(u,y); input u; output y; electrical u,y; '
                  f'{declarations} analog begin {body} end endmodule')
        p = compile_sources({'deck.va': source}, [Instance('M', 'm', dict(u='u', y='y'))])
        with self.assertRaises(KernelError) as caught:
            transient(p, {'u': [[0, 0], [1, 0]]}, [0, .75, 1], stop=1, max_step=.25, kernel=KERNEL)
        return str(caught.exception)

    def test_nonlinear_event_feedback_with_two_real_roots_is_refused(self):
        with self.assertRaisesRegex(KernelError, NONAFFINE_EVENT):
            run('@(initial_step) q=0.1; @(timer(0.25)) q=V(y,r)*V(y,r); V(y,r)<+q;', 0.5)

    def test_ungrounded_same_time_cycle_is_a_capability_limit(self):
        # Each exact system has exactly one solution: det 21/32 for the coupled pair, root
        # (-2/21, 34/21) of the relative voltages; 3/2 for the scalar one, root 2/3. A refusal
        # stating no solution or several, or only a numeric symptom, would be wrong.
        a, b, c, d = Q(-1, 8), Q(-3, 8), Q(-1, 8), Q(3, 8)
        self.assertEqual((1 - a) * (1 - d) - b * c, Q(21, 32))
        coupled = ('@(initial_step) begin q=0; h=0; end @(timer(0.5)) begin '
                   'q=-0.125*V(y,{r})-0.375*V(z,{r})+0.5; h=-0.125*V(y,{r})+0.375*V(z,{r})+1; end '
                   'V(y,{r})<+q; V(z,{r})<+h;')
        scalar = '@(initial_step) q=0; @(timer(0.5)) q=-0.5*V(y,{r})+1; V(y,{r})<+q;'
        driven, unknown = 'to a driven node instead of ground', 'between two unknown nodes'
        cases = [(coupled.format(r='u'), 'real q,h; electrical z;', driven),
                 (coupled.format(r='r') + ' V(r)<+0.125;', 'real q,h; electrical z,r;', unknown),
                 (scalar.format(r='u'), 'real q;', driven),
                 (scalar.format(r='r') + ' V(r)<+0.125;', 'real q; electrical r;', unknown)]
        for body, declarations, structure in cases:
            with self.subTest(body=body):
                message = self.refusal(body, declarations)
                self.assertRegex(message, CAPABILITY)
                self.assertIn(structure, message)

    def test_nonaffine_event_same_time_cycle_with_one_root(self):
        # F(y) = y + y^3/4 - 1 has F'(y) = 1 + 3y^2/4 > 0 and F(0) < 0 < F(1): one root, but
        # an event cycle that is not jointly affine is not certified (capability limit).
        for cube in ('pow(V(y),3)', 'V(y)*V(y)*V(y)'):
            with self.subTest(cube=cube):
                body = f'@(initial_step) q=0; @(timer(0.5)) q=1-0.25*{cube}; V(y)<+q;'
                self.assertRegex(self.refusal(body, 'real q;'), NONAFFINE_EVENT)

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

    def test_stored_values_are_the_roundings_of_the_exact_roots(self):
        # Decision 22 stores RN of the exact root bit for bit (float(Fraction) rounds once,
        # ties to even), also where the rounded map has no binary64 fixed point
        # (q -> RN(1 - q/2) next to 2/3) or another one: in the coupled system below the
        # rounded map has the fixed point s = -0.09523809523809534, the root is -2/21.
        p, times, result = run('@(initial_step) q=0; @(timer(0.5)) q=-0.5*V(y,r)+1; V(y,r)<+q;', 1.0)
        self.assertEqual(result['transient']['states'][-1], [float(Q(2, 3))])
        self.assertEqual(result['solutions'][-1]['voltages'][p.nodes.index('y')], float(Q(2, 3)))
        a, b, c, d, f, g = Q(-1, 8), Q(-3, 8), Q(-1, 8), Q(3, 8), Q(1, 2), Q(1)
        det = (1 - a) * (1 - d) - b * c
        s, h = ((1 - d) * f + b * g) / det, (c * f + (1 - a) * g) / det
        self.assertEqual((s, h), (Q(-2, 21), Q(34, 21)))
        source = model(f'''@(initial_step) begin s=0; h=0; end
            @(timer(0.5)) begin s={float(a)!r}*V(y,r)+{float(b)!r}*V(z,r)+{float(f)!r};
            h={float(c)!r}*V(y,r)+{float(d)!r}*V(z,r)+{float(g)!r}; end
            V(y,r)<+s; V(z,r)<+h;''', 'real s,h; electrical z;')
        coupled = compile_sources({'coupled.va': source}, [instance()])
        result = transient(coupled, {'u': [[0, 0], [1, 0]]}, [0, 1], stop=1, max_step=1, kernel=KERNEL)
        self.assertEqual(result['transient']['states'][-1], [float(s), float(h)])
        # Ordinary feedback through a selected program real: y = u - y^3/4 with the exact
        # source value u = 4/3 at t = 1, an irrational root bracketed here until its ends
        # round alike.
        def rounded_root(u):
            lo, hi = Q(1), Q(3, 2)
            while float(lo) != float(hi):
                middle = (lo + hi) / 2
                if middle + middle ** 3 / 4 - u > 0:
                    hi = middle
                else:
                    lo = middle
            return float(lo)
        source = model('tmp=V(u,r)-0.25*pow(V(y,r),3); if(V(u,r)>-2) begin end V(y,r)<+tmp;', 'real tmp;')
        ordinary = compile_sources({'cubic.va': source}, [instance()])
        result = transient(ordinary, {'u': [[0, 1], [3, 2]]}, [1, 3], stop=3, max_step=3, kernel=KERNEL)
        y = ordinary.nodes.index('y')
        self.assertEqual([row['voltages'][y] for row in result['solutions']],
                         [rounded_root(Q(4, 3)), rounded_root(Q(2))])


if __name__ == '__main__':
    unittest.main()

"""Final-point initialization of independent continuous history beside transitions.

Constructor-only initialization (N18c): a continuous subproblem that the causal
projection proves free of transition dependency is freshly built from the final
initial state, while source transitions keep their point/right seeds, Ready
plans and future cuts. Uncertified mixed graphs stay rejected.
"""
GUARDS = ['DYNAMICS', 'TIMED-OPERATOR', 'COMPOSE', 'EVENT-ORDER', 'TIMER']
import math
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

RAMP = [[0., 0.], [1., 1.]]
TIMES = [0., 0.5, 0.5625, 0.625, 1.]
# The dut always exposes u (input), y and t (outputs) and r (inout); extra
# internal nodes such as z stay private to the instance.


def simulate(body, decl='', sources=None, times=TIMES, stop=1., max_step=0.0625, **kw):
    source = model(body, decl,
                   ports='u,y,t,r', directions='input u; output y,t; inout r;')
    p = compile_sources({'independent-initial.va': source},
                        [instance(connections=dict(u='u', y='y', t='t', r='0'))])
    return transient(p, {'u': sources if sources is not None else RAMP}, times,
                     stop=stop, max_step=max_step, vabstol=1e-9, reltol=0.,
                     kernel=KERNEL, **kw)


def column(r, name):
    return [row['voltages'][r['nodes'].index(name)] for row in r['solutions']]


class IndependentInitialHistory(unittest.TestCase):
    def test_linear_continuous_state_beside_a_source_selected_transition(self):
        body = ('V(y,r)<+idt(1-V(y,r),0.75);'
                'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);')
        r = simulate(body)
        for time, v in zip(TIMES, column(r, 'y')):
            self.assertAlmostEqual(v, 1-0.25*math.exp(-time), places=8)
        for time, v in zip(TIMES, column(r, 't')):
            self.assertAlmostEqual(v, min(1., max(0., (time-0.5)/0.125)), places=8)

    def test_nonlinear_continuous_state_beside_a_source_selected_transition(self):
        # dC/dt=(1-C)/(1+u^2) with u=t and C(0)=1/2 separates to
        # C=1-(1/2)*exp(-atan(t)).
        body = ('V(y,r)<+idt((1-V(y,r))/(1+V(u,r)*V(u,r)),0.5);'
                'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);')
        r = simulate(body)
        for time, v in zip(TIMES, column(r, 'y')):
            self.assertAlmostEqual(v, 1-0.5*math.exp(-math.atan(time)), places=8)
        for time, v in zip(TIMES, column(r, 't')):
            self.assertAlmostEqual(v, min(1., max(0., (time-0.5)/0.125)), places=8)

    def test_point_and_right_targets_differ_at_zero_and_future_cuts_stay_visible(self):
        # At t=0 the point target of u>0 is 0 while the right target is 1.
        times = [0., 0.1, 0.25, 0.5, 1.]
        body = 'V(t,r)<+transition(V(u,r)>0,0,0.25,0.25);V(y,r)<+idt(1-V(y,r),0.75);'
        r = simulate(body, times=times)
        self.assertEqual(column(r, 't')[0], 0.)
        for time, v in zip(times, column(r, 't')):
            self.assertAlmostEqual(v, min(4.*time, 1.), places=8)
        for time, v in zip(times, column(r, 'y')):
            self.assertAlmostEqual(v, 1-0.25*math.exp(-time), places=8)
        # A later source cut must still retarget the Ready transition plan.
        steps = [[0., 0.], [0.4, 0.], [0.5, 1.], [1., 1.]]
        cut = 'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);V(y,r)<+idt(1-V(y,r),0.75);'
        times2 = [0., 0.4, 0.45, 0.5, 0.6, 0.7]
        s = simulate(cut, sources=steps, times=times2)
        for time, v in zip(times2, column(s, 't')):
            self.assertAlmostEqual(v, min(1., max(0., (time-0.45)/0.125)), places=8)
        # A crossing the binary64 clock cannot prove as a singleton stays a
        # rejection instead of being snapped onto a representable neighbor.
        steep = [[0., 0.], [0.4, 0.], [0.4000000000000001, 1.], [1., 1.]]
        with self.assertRaises(KernelError) as caught:
            simulate(cut, sources=steep, times=times2)
        self.assertEqual(caught.exception.detail['kind'], 'condition_precision')

    def test_zero_held_callback_reparameterizes_the_continuous_history(self):
        # q changes 0->1 in the zero-time transaction; the independent C'=q-C
        # must be built from the final q (1-exp(-t)), not the pre-closure zero
        # trajectory, and the transition must seed from final q=1 (flat 1,
        # instead of ramping up from the pre-closure q=0).
        continuous = 'V(y,r)<+idt(q-V(y,r),0.0);'
        timed = 'V(t,r)<+transition(q,0,0.25);'
        times = [0., 0.25, 0.5, 1.]
        for order in [continuous + timed, timed + continuous]:
            with self.subTest(order=order[:14]):
                body = '@(timer(0,5,0)) q=1;' + order
                r = simulate(body, 'integer q;', times=times)
                for time, v in zip(times, column(r, 'y')):
                    self.assertAlmostEqual(v, 1-math.exp(-time), places=8)
                self.assertEqual(column(r, 't'), [1., 1., 1., 1.])
                self.assertEqual([e['time'] for e in r['transient']['events']], [0.])

    def test_hidden_zero_and_explicit_transition_feedback_stay_rejected(self):
        base = 'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);'
        for extra, kind in [
                ('V(z,r)<+idt(1-V(z,r)+V(t,r),0.75);', 'unsupported_operator'),
                ('V(z,r)<+idt(1-V(z,r),0.75)+0*V(t,r);', 'unsupported_operator'),
                ('V(z,r)<+idt(1-V(z,r),0.75);V(z,r)<+(V(u,r)>2?V(t,r):0);', 'unsupported_initial_history')]:
            with self.subTest(extra=extra), self.assertRaises(KernelError) as caught:
                simulate(base + extra + 'V(y,r)<+V(z,r);', 'electrical z;')
            self.assertEqual(caught.exception.detail['kind'], kind)

    def test_uncertified_history_families_and_math_over_transition_stay_rejected(self):
        for decl, body in [
            ('electrical z;',
             'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);V(z,r)<+absdelay(V(u,r),0.1);V(y,r)<+V(z,r);'),
            ('integer n;',
             '@(timer(0.25,0,0)) n=1;'
             'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);V(y,r)<+exp(transition(n,0,0.125));'),
            ('electrical z;',
             'V(t,r)<+transition(V(u,r)>0.5,0,0.125,0.125);V(z,r)<+slew(V(u,r),1.0,-1.0);V(y,r)<+V(z,r);'),
        ]:
            with self.subTest(body=body), self.assertRaises(KernelError) as caught:
                simulate(body, decl)
            self.assertEqual(caught.exception.detail['kind'], 'unsupported_initial_history')


if __name__ == '__main__':
    unittest.main()

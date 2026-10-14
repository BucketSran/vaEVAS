"""Analytical controls for selected integral flow and continuous state retention."""
GUARDS = ["ANALOG", "DYNAMICS", "EVENT-CONDITIONS"]
import math
import unittest
from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


def simulate(body, times, *, max_step=1):
    text = model(body)
    p = compile_sources({'selected.va': text}, [instance()])
    return transient(p, {'u': [[0, 0], [1, 1]]}, times,
                     stop=1, max_step=max_step, kernel=KERNEL)


def values(result):
    y = result['nodes'].index('y')
    return [s['voltages'][y] for s in result['solutions']]


class SelectedIntegral(unittest.TestCase):
    def test_finite_rate_switch_preserves_integral_and_schedules_breakpoint(self):
        body = 'V(y,r)<+idt(V(u,r)<0.5 ? 2 : -1,0.25);'
        sparse = simulate(body, [0, .25, .5, .75, 1])
        dense = simulate(body, [i/40 for i in range(41)])
        expected = [.25, .75, 1.25, 1, .75]
        for got, want in zip(values(sparse), expected):
            self.assertAlmostEqual(got, want, places=10)
        self.assertAlmostEqual(values(sparse)[-1], values(dense)[-1], places=11)
        self.assertGreaterEqual(sparse['transient']['accepted_steps'], 2)

    def test_selected_feedback_retains_memory_at_source_boundary(self):
        body = 'V(y,r)<+idt(V(u,r)<0.5 ? (1-V(y,r))*2 : -V(y,r),0);'
        result = simulate(body, [0, .25, .5, .75, 1])
        expected = [0, 1-math.exp(-.5), 1-math.exp(-1),
                    (1-math.exp(-1))*math.exp(-.25),
                    (1-math.exp(-1))*math.exp(-.5)]
        for got, want in zip(values(result), expected):
            self.assertAlmostEqual(got, want, places=9)

    def test_held_predicate_event_changes_rate_without_reset(self):
        text = model('''@(initial_step) q=0;
            @(cross(V(u,r)-0.5,+1)) q=1;
            V(y,r)<+idt(q<0.5 ? (1-V(y,r))*2 : -V(y,r),0);''').replace('analog begin', 'real q; analog begin')
        p = compile_sources({'held.va': text}, [instance()])
        r = transient(p, {'u':[[0,0],[1,1]]}, [0,.25,.5,.75,1], stop=1,max_step=1,kernel=KERNEL)
        self.assertAlmostEqual(values(r)[-1], (1-math.exp(-1))*math.exp(-.5), places=8)

    def test_reciprocal_source_integral_has_analytic_arctangent_history(self):
        result=simulate('V(y,r)<+idt(1/(1+V(u,r)*V(u,r)),0);',[0,.25,.5,1])
        for got,t in zip(values(result),[0,.25,.5,1]):
            self.assertAlmostEqual(got,math.atan(t),places=8)

    def test_selected_rational_feedback_and_dynamic_inner_bound(self):
        result=simulate('$bound_step((1+V(u,r)*V(u,r))/32); V(y,r)<+idt(V(u,r)<0.5 ? -V(y,r)/(1+V(u,r)*V(u,r)) : -2*V(y,r)/(1+V(u,r)*V(u,r)),1);',[0,.5,1])
        expected=math.exp(-math.atan(.5)-2*(math.atan(1)-math.atan(.5)))
        self.assertAlmostEqual(values(result)[-1],expected,places=8)
        self.assertGreaterEqual(result['transient']['accepted_steps'],16)

    def test_exponential_forcing_has_independent_integral(self):
        result = simulate('V(y,r)<+idt(exp(-V(u,r)),0);', [0,.25,.5,1])
        for got,t in zip(values(result), [0,.25,.5,1]):
            self.assertAlmostEqual(got, 1-math.exp(-t), places=8)

    def test_negative_exponential_tail_uses_certified_absolute_bound(self):
        result = simulate('V(y,r)<+idt(exp(-600-V(u,r)),0);', [0,1])
        expected = math.exp(-600)*(1-math.exp(-1))
        self.assertLess(abs(values(result)[-1]-expected), 1e-220)

    def test_held_exponential_forcing_restart_preserves_integral(self):
        text = model("""@(initial_step) q=0;
            @(cross(V(u,r)-0.5,+1)) q=0.5;
            V(y,r)<+idt(exp(-(V(u,r)-q)),0);""").replace('analog begin', 'real q; analog begin')
        p = compile_sources({'held-exp.va':text}, [instance()])
        r = transient(p, {'u':[[0,0],[1,1]]}, [0,.25,.5,.75,1], stop=1,max_step=1,kernel=KERNEL)
        self.assertAlmostEqual(values(r)[-1], 2*(1-math.exp(-.5)), places=8)

    def test_source_switch_and_held_event_share_uncertain_boundary(self):
        text = model("""@(initial_step) q=0;
            @(cross(V(u,r)-0.3,+1)) q=0.3;
            kick=exp(-(V(u,r)-q));
            V(y,r)<+idt(V(u,r)>0.3 ? kick : 0,0);""").replace('analog begin', 'real q,kick; analog begin')
        p = compile_sources({'source-held.va':text}, [instance()])
        for max_step in [.01,.17]:
            r = transient(p, {'u':[[0,0],[1,1]]}, [0,.3,.5,1], stop=1,max_step=max_step,kernel=KERNEL)
            for got,t in zip(values(r),[0,.3,.5,1]):
                self.assertAlmostEqual(got, 0 if t<=.3 else 1-math.exp(-(t-.3)), places=8)

    def test_held_transition_selector_rebinds_target_at_event(self):
        text = model("""@(initial_step) q=0;
            @(cross(V(u,r)-0.5,+1)) q=1;
            V(y,r)<+transition(q>0.5 ? 2 : 0,0,0.1,0.1);""").replace('analog begin', 'real q; analog begin')
        p = compile_sources({'held-transition.va':text}, [instance()])
        r = transient(p, {'u':[[0,0],[1,1]]}, [0,.25,.5,.75,1], stop=1,max_step=1,kernel=KERNEL)
        self.assertAlmostEqual(values(r)[0],0,places=10)
        self.assertAlmostEqual(values(r)[-1],2,places=10)

    def test_zero_variable_denominator_rejects_uncertified_history(self):
        with self.assertRaisesRegex(Exception,'denominator|nonfinite|trajectory|tube|accuracy'):
            simulate('V(y,r)<+idt(1/(V(u,r)-0.5),0);',[0,1])

    def test_internal_predicate_has_explicit_rejection(self):
        with self.assertRaisesRegex(Exception, 'predicate|conditional|source|internal'):
            simulate('V(y,r)<+idt(V(y,r)<0.5 ? 1 : 0,0);', [0,1])


if __name__ == '__main__':
    unittest.main()

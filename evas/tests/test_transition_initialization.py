"""Final held closure supplies the initial transition/filter DC value.

Independent initialization obligations derived from actual N18 observations:
runs/evas-night-20261014/remote/n18-initialization-v1/ANALYSIS-v1.json
in the daily checkout. These tests do not revise historical checker scores.
Fraction answers follow constant DC, integral IC, and a later linear ramp.
"""
GUARDS = ['TRANSITION', 'DYNAMICS', 'COMPOSE', 'EVENT-ORDER']

from fractions import Fraction as Q
import math
import unittest

from evas import Instance, compile_sources, transient
from test_affine import KERNEL

TIMES = [0., .0625, .125, .1875, .25, .375, .5, .625, .6875, .75, 1.]
BUDGET = 1e-8


def execute(body, declarations=''):
    source = ('`include "disciplines.vams"\n'
              'module m(u,y,z,r); input u; output y,z; inout r; '
              'electrical u,y,z,r; ' + declarations + ' analog begin '
              + body + ' end endmodule')
    p = compile_sources({'initialization.va': source},
                        [Instance('dut', 'm', dict(u='u', y='y', z='z', r='0'))])
    return transient(p, {'u': [[0., 0.], [1., 1.]]}, TIMES,
                     stop=1., max_step=1., vabstol=BUDGET, reltol=0.,
                     kernel=KERNEL, timeout=30)


def assert_exact_node(test, result, node, oracle):
    """Require both point accuracy and containment of the independent answer."""
    test.assertEqual(len(result['solutions']), len(TIMES))
    evidence = result['observation_evidence']
    test.assertEqual(evidence['nodes'], result['nodes'])
    bounds = evidence['voltage_bounds_V']
    test.assertEqual(len(bounds), len(TIMES))
    index = result['nodes'].index(node)
    for t, row, intervals in zip(TIMES, result['solutions'], bounds, strict=True):
        with test.subTest(node=node, time=t):
            test.assertEqual(len(row['voltages']), len(result['nodes']))
            value = row['voltages'][index]
            test.assertTrue(math.isfinite(value))
            expected = Q(oracle(Q(t)))
            test.assertLessEqual(abs(Q(value)-expected), Q(BUDGET))
            test.assertLessEqual(row['max_residual_ratio'], 1)
            test.assertIsNotNone(intervals)
            test.assertEqual(len(intervals), len(result['nodes']))
            interval = intervals[index]
            test.assertIsNotNone(interval)
            test.assertEqual(len(interval), 2)
            test.assertTrue(all(math.isfinite(v) for v in interval))
            lo, hi = map(Q, interval)
            test.assertLessEqual(lo, min(Q(value), expected))
            test.assertLessEqual(max(Q(value), expected), hi)
            test.assertLessEqual(max(Q(value)-lo, hi-Q(value)), Q(BUDGET))


class TransitionInitialization(unittest.TestCase):
    def test_noop_timer_preserves_independent_histories(self):
        prefix='@(initial_step) q=1; @(timer(0,0,0)) q=q; '
        for expr, oracle in [
            ('idt(V(u,r),0.75)', lambda t: Q(3,4)+t*t/2),
            ("laplace_nd(V(u,r),'{1},'{1,0.25})", None),
            ('sin(V(u,r))', None),
        ]:
            r=execute(prefix+'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+'+expr+';', 'real q;')
            assert_exact_node(self,r,'y',lambda t: 1)
            if oracle: assert_exact_node(self,r,'z',oracle)
            else:
                col=r['nodes'].index('z')
                for t,row in zip(TIMES,r['solutions'],strict=True):
                    answer=math.sin(t) if expr.startswith('sin') else t-.25+.25*math.exp(-4*t)
                    self.assertLessEqual(abs(row['voltages'][col]-answer),BUDGET)
            events=r['transient']['events']
            self.assertEqual(len(events),1)
            self.assertEqual(events[0]['before'],events[0]['after'])

    def test_equal_constant_timer_seed_preserves_independent_integral(self):
        r=execute('@(initial_step) q=1; @(timer(0,0,0)) q=1; '
                  'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+idt(V(u,r),0.75);','real q;')
        assert_exact_node(self,r,'y',lambda t: 1)
        assert_exact_node(self,r,'z',lambda t: Q(3,4)+t*t/2)
        self.assertEqual(len(r['transient']['events']),1)

    def test_noop_timer_allows_unrelated_internal_read_once(self):
        r=execute('@(initial_step) begin q=1; a=0; end '
                  '@(timer(0,0,0)) begin q=q; a=V(z,r); $strobe("a=%g",a); end '
                  'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+2;', 'real q,a;')
        assert_exact_node(self,r,'y',lambda t: 1)
        assert_exact_node(self,r,'z',lambda t: 2)
        self.assertEqual(r['transient']['states'],[[1.,2.]]*len(TIMES))
        self.assertEqual(len(r['transient']['events']),1)
        self.assertEqual(len(r['transient']['display_records']),1)

    def test_equal_constant_seed_allows_unrelated_internal_read(self):
        r=execute('@(initial_step) begin q=1; a=0; end '
                  '@(timer(0,0,0)) begin q=1; a=V(z,r); end '
                  'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+2;','real q,a;')
        assert_exact_node(self,r,'y',lambda t: 1)
        self.assertEqual(r['transient']['states'],[[1.,2.]]*len(TIMES))
        self.assertEqual(len(r['transient']['events']),1)

    def test_final_seed_precedes_first_circuit_solve(self):
        # With the obsolete q=1 seed, e=e+1 is singular. Closing timer(0)
        # first gives q=0 and the unique final DC solution e=1.
        for initial in [0, 1]:
            r = execute(f'@(initial_step) q={initial}; @(timer(0,0,0)) q=0; '
                        'V(e,r)<+transition(q,0.125,0.5,0.5)*V(e,r)+1; '
                        'V(y,r)<+V(e,r); V(z,r)<+q;', 'real q; electrical e;')
            assert_exact_node(self, r, 'y', lambda t: 1)
            assert_exact_node(self, r, 'z', lambda t: 0)

    def test_held_timer_zero_disable_seeds_final_zero(self):
        r = execute('@(initial_step) q=1; @(timer(0,0,0)) q=0; '
                    'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+q;',
                    'real q;')
        assert_exact_node(self, r, 'z', lambda t: 0)
        assert_exact_node(self, r, 'y', lambda t: 0)

    def test_held_timer_zero_enable_seeds_final_one(self):
        r = execute('@(initial_step) q=0; @(timer(0,0,0)) q=1; '
                    'V(y,r)<+transition(q,0.125,0.5,0.5); V(z,r)<+q;',
                    'real q;')
        assert_exact_node(self, r, 'z', lambda t: 1)
        assert_exact_node(self, r, 'y', lambda t: 1)

    def test_filter_normal_and_forward_use_final_parent_dc_seed(self):
        # N18 directly covers disable in both orders. Enable is an adjacent
        # analytical obligation, not an additional executed Spectre case.
        parent = 'V(e,r)<+transition(q,0.125,0.5,0.5); '
        child = "V(z,r)<+laplace_nd(V(e,r),'{1},'{1,0.25}); "
        for initial, final in [(1, 0), (0, 1)]:
            for forward in [False, True]:
                with self.subTest(initial=initial, final=final, forward=forward):
                    r = execute(f'@(initial_step) q={initial}; @(timer(0,0,0)) q={final}; '
                                + (child+parent if forward else parent+child)
                                + 'V(y,r)<+V(e,r);', 'real q; electrical e;')
                    # Constant final input is already the filter DC solution;
                    # a filter transient here reveals an inconsistent seed.
                    assert_exact_node(self, r, 'z', lambda t: final)
                    assert_exact_node(self, r, 'y', lambda t: final)

    def test_affine_final_seed_preserves_integral_ic(self):
        # This held-only encoding is adjacent to N18's source-predicate case.
        # q=2 gives e=9/2 from t=0; idt starts at 3/4, not its input DC value.
        r = execute('@(initial_step) q=1; @(timer(0,0,0)) q=2; '
                    'V(z,r)<+idt(V(e,r),0.75); '
                    'V(e,r)<+transition(2*q+0.5,0.125,0.5,0.5); '
                    'V(y,r)<+V(e,r);', 'real q; electrical e;')
        assert_exact_node(self, r, 'z', lambda t: Q(3, 4)+Q(9, 2)*t)
        assert_exact_node(self, r, 'y', lambda t: Q(9, 2))

    def test_forward_integral_preserves_ic_and_consumes_later_parent_history(self):
        parent = 'V(e,r)<+transition(q,0.125,0.125,0.125); '
        child = 'V(z,r)<+idt(2*V(e,r)+0.5,0.75); '
        def answer(t):
            dt=max(Q(0),t-Q(5,8))
            ramp_area=dt*dt/(2*Q(1,8)) if dt<=Q(1,8) else dt-Q(1,16)
            return Q(3,4)+Q(5,2)*t+2*ramp_area
        for forward in [False, True]:
            r = execute('@(initial_step) q=0; @(timer(0,0,0)) q=1; '
                        '@(timer(0.5,0,0)) q=2; '
                        +(child+parent if forward else parent+child)
                        +'V(y,r)<+V(e,r);', 'real q; electrical e;')
            assert_exact_node(self, r, 'z', answer)
            assert_exact_node(self, r, 'y', lambda t:
                1+min(Q(1),max(Q(0),(t-Q(5,8))/Q(1,8))))

    def test_shared_initial_count_closes_once_and_later_edge_is_preserved(self):
        # Explicit encoded count is an observable output, not callback tracing.
        r = execute('@(initial_step or timer(0,0.5,0)) n=n+1; '
                    '@(timer(0,0,0)) begin n=n+1; latched=n; end '
                    'V(y,r)<+transition(n,0.125,0.125,0.125); '
                    'V(z,r)<+10.0*n+latched;', 'integer n,latched;')
        assert_exact_node(self, r, 'z', lambda t: 10*(2+t//Q(1, 2))+2)
        assert_exact_node(self, r, 'y', lambda t:
                          2+min(Q(1), max(Q(0), (t-Q(5, 8))/Q(1, 8))))


if __name__ == '__main__':
    unittest.main()

"""Physical sampled sqrt domains; independent answers precede implementation.

The first Cross consumer addresses original074's mathematical admission gate.
MATH170 still requires ln and held-delay qualification beyond this contract.
"""
GUARDS = ['EVENT-CONDITIONS', 'COMPOSE', 'TRANSITION']
from fractions import Fraction as F
import os
from pathlib import Path
import unittest

from evas import Instance, KernelError, compile_sources, transient

ROOT = Path(__file__).resolve().parents[2]
KERNEL = Path(os.environ.get('EVAS_KERNEL', os.environ.get('EVAS_TEST_KERNEL',
    str(ROOT / 'evas/rust_core/target/debug/evas-kernel'))))


def clock(stop):
    points = [[0, 0]]
    for k in range(5):
        for time, value in [(k/2+.125, 0), (k/2+.375, 1), (k/2+.5, 1)]:
            if time < stop:
                points.append([time, value])
    points.append([stop, points[-1][1]])
    return points


def run(body, times, *, timer=False, stop=1, u=None, errors=None, gain=1, direct=False, vabstol=1e-10):
    # direct=True drives y from q itself instead of a transition: the fixed
    # timer plus algebraic consumer is the shape that accepts uncertain sources.
    trigger = 'timer(0.25,0.5,1e-12)' if timer else 'cross(V(clk)-0.5,+1,1e-12,1e-12)'
    consumer = 'q' if direct else 'transition(q,0,0.0625,0.0625)'
    source = '''`include "disciplines.vams"
module sampled_math(u,v,clk,y);input u,v,clk;output y;electrical u,v,clk,y;
real q,s,x;integer n;
analog begin
@(initial_step)begin q=0;s=0;x=0;n=0;end
@('''+trigger+''')begin '''+body+''' end
V(y)<+'''+str(gain)+'''*'''+consumer+''';
end endmodule'''
    p = compile_sources({'sampled-math-domain.va': source}, [Instance(
        'M', 'sampled_math', dict(u='u', v='v', clk='clk', y='y'))])
    return transient(p, dict(u=u or [[0, 1], [stop, 1]],
                            v=[[0, 4], [stop, 4]], clk=clock(stop)), times,
                     stop=stop, max_step=.125, vabstol=vabstol, reltol=0,
                     source_errors=errors, kernel=KERNEL)


class GroupMathSampledDomain(unittest.TestCase):
    def check_half_edge(self, result, times):
        y = result['nodes'].index('y')
        boxes = result['observation_evidence']['voltage_bounds_V']
        for time, row, box in zip(times, result['solutions'], boxes):
            expected = min(F(1, 2), max(F(0), (F(time)-F(1, 4))*8))
            self.assertLessEqual(abs(F(row['voltages'][y])-expected), F(1, 10**10))
            self.assertLessEqual(F(box[y][0]), expected)
            self.assertLessEqual(expected, F(box[y][1]))

    def test_cross_sqrt_ratio_reaches_physical_transition_with_exact_edges(self):
        times = [0, .25, .28125, .3125, .5, .75, 1]
        result = run('q=sqrt(V(u)/V(v));', times)
        self.check_half_edge(result, times)
        dense_times = sorted(set(times+[k/64 for k in range(65)]))
        dense = run('q=sqrt(V(u)/V(v));', dense_times)
        self.assertEqual(result['transient']['events'], dense['transient']['events'])
        for time, row in zip(times, result['solutions']):
            self.assertEqual(row, dense['solutions'][dense_times.index(time)])

    def test_fixed_timer_uses_same_domain_contract_and_real_transition(self):
        times = [0, .25, .28125, .3125, .5, 1]
        self.check_half_edge(run('q=sqrt(V(u)/V(v));', times, timer=True), times)

    def test_four_sample_rms_uses_completed_sum_before_reset(self):
        # Samples at1/4,3/4,5/4,7/4 are1,0,0,0. RMS is1/2, only afterfourth.
        body = 'x=V(u);s=s+x*x;n=n+1;if(n>=4)begin q=sqrt(s/4);s=0;n=0;end'
        times = [0, .375, .875, 1.375, 1.75, 1.78125, 1.8125, 2.25]
        result = run(body, times, stop=2.25, u=[[0, 1], [.375, 1], [.5, 0], [2.25, 0]])
        y = result['nodes'].index('y')
        for row, expected in zip(result['solutions'], [0, 0, 0, 0, 0, F(1, 4), F(1, 2), F(1, 2)]):
            self.assertLessEqual(abs(F(row['voltages'][y])-expected), F(1, 10**10))

    def test_selected_negative_sqrt_is_not_hidden_by_later_clamp(self):
        with self.assertRaisesRegex(KernelError, 'event_domain.*nonnegative'):
            run('q=sqrt(-V(u));if(q<0)q=0;', [0, 1])

    def test_nonpoint_input_domain_is_not_replaced_by_nominal_sample(self):
        # The nominal sample 0.25 is valid but its box [-0.25, 0.75] is not.
        # Fixed timer with an algebraic consumer is the uncertain-source shape
        # that reaches the sampled domain rule; the kernel must refuse it.
        with self.assertRaisesRegex(KernelError, 'event_domain.*nonnegative'):
            run('q=sqrt(V(u));', [0, 1], u=[[0, .25], [1, .25]], errors={'u': .5},
                timer=True, direct=True, vabstol=1)
        # Independent enclosure for a box inside the domain: the true input set
        # is [1/4 - e, 1/4 + e] with e the binary64 value of 0.1.
        result = run('q=sqrt(V(u));', [0, 1], u=[[0, .25], [1, .25]], errors={'u': .1},
                     timer=True, direct=True, vabstol=1)
        y = result['nodes'].index('y')
        low, high = result['observation_evidence']['voltage_bounds_V'][-1][y]
        self.assertLessEqual(F(low) ** 2, F(1, 4) - F(.1))
        self.assertGreaterEqual(F(high) ** 2, F(1, 4) + F(.1))
        self.assertLess(high - low, .25)
        # The cross/transition shape has no time-shape bound for uncertain
        # sources yet; it is refused by that specific gate, never by nominal.
        with self.assertRaisesRegex(KernelError, 'unsupported_source_uncertainty'):
            run('q=sqrt(V(u));', [0, 1], u=[[0, .25], [1, .25]], errors={'u': .5})

    def test_cross_ln_ratio_reaches_physical_transition(self):
        # ln(V(v)/V(u)) = ln(4) is held from the first edge at 1/4.
        times = [0, .25, .3125, .5, 1]
        result = run('q=0.25*ln(V(v)/V(u));', times)
        y = result['nodes'].index('y')
        boxes = result['observation_evidence']['voltage_bounds_V']
        import math
        target = .25*math.log(4)
        for time, row, box in zip(times, result['solutions'], boxes):
            expected = min(1., max(0., (time-.25)*16))*target
            self.assertLessEqual(abs(row['voltages'][y]-expected), 1e-10)
            self.assertLessEqual(box[y][0], expected+1e-15)
            self.assertLessEqual(expected-1e-15, box[y][1])

    def test_ln_requires_strictly_positive_argument(self):
        # V(u)-1 is exactly zero: a zero argument is outside the ln domain.
        with self.assertRaisesRegex(KernelError, 'event_domain.*ln.*positive'):
            run('q=ln(V(u)-1);', [0, 1])
        with self.assertRaisesRegex(KernelError, 'event_domain.*ln.*positive'):
            run('q=ln(-V(u));if(q<0)q=0;', [0, 1])

    def test_other_sampled_math_functions_remain_rejected(self):
        # Only sqrt and ln gained a certified physical sampled contract.
        from evas import CompileError
        for body in ('q=exp(V(u));', 'q=cos(V(u));', 'q=tanh(V(u));'):
            with self.subTest(body=body), self.assertRaises((CompileError, KernelError)):
                run(body, [0, 1])

    def test_sampled_math_needs_a_sample_in_an_assignment_value(self):
        from evas import CompileError
        # A held value never sampled in this event, a predicate, and a node
        # this module itself drives keep the original compile refusal.
        for body in ('q=sqrt(s);', 'if(sqrt(V(u))>0.5) q=1;', 'q=ln(V(y)+1);'):
            with self.subTest(body=body), self.assertRaisesRegex(CompileError, 'nonconstant mathematical'):
                run(body, [0, 1])
        # A state assigned from a sample earlier in the same event qualifies.
        result = run('x=V(u)*V(u); q=sqrt(x);', [0, .25, .3125, .5, 1], u=[[0, .25], [1, .25]])
        y = result['nodes'].index('y')
        self.assertAlmostEqual(result['solutions'][-1]['voltages'][y], .25, places=12)

    def test_uncertain_math_result_survives_transition_and_future_amplification(self):
        # sqrt(1/4 +- 1e-4) keeps a ~1e-4 band; gain 1000 makes it ~0.1, far
        # above the 1e-3 budget. The band must survive and be refused.
        with self.assertRaisesRegex(KernelError, 'event_accuracy.*at y'):
            run('q=sqrt(V(u));', [0, .5, 1], u=[[0, .25], [1, .25]], errors={'u': .0001},
                gain=1000, timer=True, direct=True, vabstol=1e-3)
        # Without amplification the same band fits and is reported, not erased.
        result = run('q=sqrt(V(u));', [0, .5, 1], u=[[0, .25], [1, .25]], errors={'u': .0001},
                     timer=True, direct=True, vabstol=1e-3)
        y = result['nodes'].index('y')
        low, high = result['observation_evidence']['voltage_bounds_V'][-1][y]
        self.assertLessEqual(F(low) ** 2, F(1, 4) - F(.0001))
        self.assertGreaterEqual(F(high) ** 2, F(1, 4) + F(.0001))
        # The transition consumer has no uncertain-source time-shape bound yet:
        # that exact gate refuses it before any nominal value could be used.
        with self.assertRaisesRegex(KernelError, 'unsupported_source_uncertainty'):
            run('q=sqrt(V(u));', [0, .5, 1],
                u=[[0, .25], [1, .25]], errors={'u': .0001}, gain=1000)

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

The original safety contract permitted honest refusal. The repaired cases
require these answers within ``BUDGET``. Main ``a4d2b875``
returns neither for the variable-start cases: y=0,0,0,0.25,0.75,1,1 at
TIMES, without a diagnostic, while the literal ``timer(0,...)`` cases already
give y=1. The repaired slice requires successful output, including the independent integral.
"""
GUARDS = ["TIMER", "TRANSITION", "EVENT-ORDER", "DYNAMICS", "DEV:silent-error-regression"]

from fractions import Fraction as F
import unittest
from initial_named_batches_contract import check_named_initial_batches

from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL

TIMES = [0., .0625, .125, .25, .5, .75, 1.]
BUDGET = 1e-9

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
    def assert_seeded(self, events, w, *, program_source=None):
        program = compile_sources({"dut.va": program_source or source(events, w)}, [Instance(
            "dut", "m", dict(u="u", y="y", z="z", w="w", r="0"), {})])
        result = transient(program, {"u": [[0., 0.], [1., 1.]]}, TIMES, stop=1.,
                           max_step=0.015625, vabstol=BUDGET, reltol=0, kernel=KERNEL)
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
                self.assert_seeded(FIXED_NEIGHBOUR + LITERAL_START, w)

    def test_variable_zero_start_beside_fixed_zero_timer(self):
        # Spectre case held_zero.
        self.assert_seeded(FIXED_NEIGHBOUR + VARIABLE_START, CONSTANT_W)

    def test_variable_zero_start_alone(self):
        # Spectre case held_without_fixed.
        self.assert_seeded(VARIABLE_START, CONSTANT_W)

    def test_variable_zero_start_beside_independent_integral(self):
        # Spectre case held_independent.
        self.assert_seeded(FIXED_NEIGHBOUR + VARIABLE_START, INTEGRAL_W)

    def test_initial_stage_moves_start_to_zero_and_enables_or_leaf(self):
        events = '@(timer(start,0,0.001,en) or timer(0.5,0,0)) a=1; '
        text = source(events, INTEGRAL_W).replace(
            'real q,a,start;', 'real q,a,start; integer en;').replace(
            'start=0; end', 'start=0.125; en=0; start=0; en=1; end')
        self.assert_seeded(events, INTEGRAL_W, program_source=text)

    def closure(self, events, *, initial='s=0; en=1; n=0; b=0.5; p=0.5;',
                initial_values=None, zero_steps=None):
        # Analytic references below use exact dyadic clocks and a unit-slope
        # source integral. They do not use EVAS event traces as their oracle.
        text = ('`include "disciplines.vams"\n'
                'module m(u,y,z,w); input u; output y,z,w; electrical u,y,z,w; '
                'real s,b,p; integer en,n; analog begin '
                f'@(initial_step) begin {initial} end {events}'
                'V(y)<+transition(n,0,0.125,0.125); V(z)<+n; '
                'V(w)<+idt(V(u),0.75); end endmodule')
        program = compile_sources({'closure.va': text}, [Instance(
            'dut', 'm', dict(u='u', y='y', z='z', w='w'), {})])
        times = sorted(set(TIMES + [.5625, .8125]))
        result = transient(program, {'u': [[0., 0.], [1., 1.]]}, times, stop=1.,
                           max_step=0.015625, vabstol=BUDGET, reltol=0, kernel=KERNEL)
        columns = {node: [row['voltages'][result['nodes'].index(node)]
                          for row in result['solutions']] for node in 'yzw'}
        for t, w in zip(times, columns['w']):
            self.assertAlmostEqual(w, float(F(3, 4) + F(t)**2/2), delta=BUDGET)
        if zero_steps is not None:
            result=check_named_initial_batches(result,program,
                initial_values or dict(s=0,en=1,n=0,b=.5,p=.5),zero_steps)
        return result, times, columns

    def test_enable_and_self_disable_consume_original_zero_once(self):
        for start in ('0', 's'):
            with self.subTest(start=start):
                result, _, v = self.closure(
                    f'@(timer({start},0.25,0.001,en)) begin n=n+1; en=0; end ',
                    zero_steps=[(1,'timer',dict(n=1,en=0))])
                self.assertEqual(v['y'], [1.] * len(v['y']))
                self.assertEqual(v['z'], [1.] * len(v['z']))
                self.assertEqual([e['time'] for e in result['transient']['events']], [0.])

    def test_changed_start_replaces_future_and_keeps_initial_seed(self):
        result, times, v = self.closure(
            '@(timer(s,0,0.001,en)) begin n=n+1; if(n==1) s=0.5; else en=0; end ',
            zero_steps=[(1,'timer',dict(n=1,s=.5))])
        for t, y, z in zip(times, v['y'], v['z']):
            self.assertAlmostEqual(y, 1+min(1., max(0., 8*(t-.5))), delta=BUDGET)
            self.assertEqual(z, 1+int(t >= .5))
        self.assertEqual([e['time'] for e in result['transient']['events']], [0., .5])

    def test_other_future_timer_is_replaced_in_either_declaration_order(self):
        first = '@(timer(s,0,0.001)) begin n=1; b=0.75; end '
        second = '@(timer(b,0,0.001)) n=2; '
        for events in (first+second, second+first):
            with self.subTest(events=events):
                result, times, v = self.closure(events,
                    zero_steps=[(1 if events==first+second else 2,"timer",dict(n=1,b=.75))])
                for t, y, z in zip(times, v['y'], v['z']):
                    self.assertAlmostEqual(y, 1+min(1., max(0., 8*(t-.75))), delta=BUDGET)
                    self.assertEqual(z, 1+int(t >= .75))
                self.assertEqual([e['time'] for e in result['transient']['events']], [0., .75])

    def test_period_change_keeps_consumed_zero_and_subsequent_ticks(self):
        result, times, v = self.closure(
            '@(timer(s,p,0.001)) begin n=n+1; p=0.25; end ',
            zero_steps=[(1,'timer',dict(n=1,p=.25))])
        for t, z in zip(times, v['z']):
            self.assertEqual(z, 1+int(F(t)//F(1, 4)))
        self.assertEqual([e['time'] for e in result['transient']['events']], [0., .25, .5, .75, 1.])

    def test_one_shot_becomes_dense_periodic_without_losing_zero_or_future_ticks(self):
        result, times, v = self.closure(
            '@(timer(s,p,0.001)) begin n=n+1; p=0.015625; end ',
            initial='s=0; en=1; n=0; b=0.5; p=0;',
            initial_values=dict(s=0,en=1,n=0,b=.5,p=0),
            zero_steps=[(1,'timer',dict(n=1,p=.015625))])
        self.assertEqual([e['time'] for e in result['transient']['events']],
                         [i/64 for i in range(65)])
        for t, z in zip(times, v['z']):
            self.assertEqual(z, 1+int(F(t)//F(1, 64)))

    def test_unneeded_cold_proof_preserves_large_future_or_calendar(self):
        # The future OR body executes once, not 128 times. Neither it nor
        # the held timer changes the seed, so no new cold calendar is needed.
        future = ' or '.join(['timer(0.25,0,0)']*128)
        for start in ('0.125', '0'):
            with self.subTest(start=start):
                result, _, v = self.closure(
                    '@(timer(s,0,0.001)) n=n; @('+future+') n=n; ',
                    initial=f's={start}; en=1; n=0; b=0.5; p=0;',
                    initial_values=dict(s=float(start),en=1,n=0,b=.5,p=0),
                    zero_steps=[] if start=='0.125' else [(1,'timer',{})])
                self.assertEqual(v['y'], [0.]*len(v['y']))
                self.assertEqual(v['z'], [0.]*len(v['z']))
                self.assertEqual([e['time'] for e in result['transient']['events']],
                                 [float(start),.25])

    def test_duplicate_or_zero_runs_body_once(self):
        result, _, v = self.closure('@(timer(s,0,0.001) or timer(0,0,0)) n=n+1; ',
            zero_steps=[(1,'or',dict(n=1),[0,1])])
        self.assertEqual(v['y'], [1.] * len(v['y']))
        self.assertEqual(v['z'], [1.] * len(v['z']))
        self.assertEqual(len(result['transient']['events']), 1)
        self.assertEqual(len(result['transient']['events'][0]['fired_triggers']), 2)

    def test_new_unconsumed_zero_timer_is_not_silently_lost(self):
        # A newly created same-time occurrence needs a separate causal closure
        # contract. Both a changed and an invariant transition seed expose it.
        for body in ('b=0; n=1;', 'b=0;'):
            with self.subTest(body=body), self.assertRaises(KernelError) as caught:
                self.closure('@(timer(s,0,0.001)) begin '+body+' end '
                             '@(timer(b,0,0.001)) n=n+1; ')
            self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
            self.assertIn('unconsumed held timer', caught.exception.detail['message'])


if __name__ == "__main__":
    unittest.main()

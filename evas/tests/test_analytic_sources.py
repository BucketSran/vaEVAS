"""Physical source and root sampling contracts through the public SCS API.

The rational Taylor oracle does not call EVAS source or interval arithmetic.
These controls cover explicit source parameters, not vendor defaults.
"""
GUARDS = ["LANG", "ANALOG", "EVENT-ORDER", "COMPOSE"]

from fractions import Fraction as Q
import math
import os
from pathlib import Path
import tempfile
import unittest

from evas import KernelError
from evas.scs import simulate_scs


KERNEL = Path(os.environ.get(
    'EVAS_TEST_KERNEL', Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel'))
PI_LO = Q('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679')
PI_HI = PI_LO + Q(1, 10**100)
PASS = '''`include "disciplines.vams"
module probe(x,clk,y); input x,clk; output y; electrical x,clk,y;
analog begin V(y)<+V(x); end endmodule
'''
HELD = '''`include "disciplines.vams"
module probe(x,clk,y); input x,clk; output y; electrical x,clk,y; real h;
analog begin
  @(initial_step) h=0;
  @(cross(V(clk)-0.5,+1)) h=V(x);
  V(y)<+h;
end endmodule
'''
DECK = '''simulator lang=spectre
global 0
ahdl_include "probe.va"
VX (x 0) vsource type=sine sinedc=0.5 ampl=0.25 freq=1 sinephase=0
VC (clk 0) vsource type=pwl wave=[0 0 1 3]
XD (x clk y) probe
tran tran stop=1 maxstep=0.125
save x clk y
'''


def source_box(turns):
    turns = Q(turns)
    exact = {Q(0): Q(1, 2), Q(1, 4): Q(3, 4), Q(1, 2): Q(1, 2),
             Q(3, 4): Q(1, 4), Q(1): Q(1, 2)}
    if turns in exact:
        return exact[turns], exact[turns]
    x = 2 * PI_LO * turns
    assert abs(x) < 8
    value = sum((-1)**k * x**(2*k+1) / math.factorial(2*k+1) for k in range(41))
    error = abs(x)**83 / math.factorial(83) + 2 * abs(turns) * (PI_HI-PI_LO)
    return Q(1, 2)+(value-error)/4, Q(1, 2)+(value+error)/4


class AnalyticSourceContracts(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.directory = Path(folder.name)

    def simulate(self, model=PASS, deck=DECK):
        (self.directory/'probe.va').write_text(model)
        (self.directory/'source.scs').write_text(deck)
        return simulate_scs(self.directory/'source.scs', kernel=KERNEL, timeout=120)

    def assert_box(self, result, sample, name, expected):
        lower, upper = expected
        saved = result['saved']
        nominal = saved['values'][sample][saved['nodes'].index(name)]
        bounds = result['observation_evidence']['voltage_bounds_V'][sample][result['nodes'].index(name)]
        self.assertLessEqual(Q(bounds[0]), lower, (name, sample, bounds))
        self.assertGreaterEqual(Q(bounds[1]), upper, (name, sample, bounds))
        self.assertLess(abs(nominal-float((lower+upper)/2)), 1e-12)

    def test_explicit_source_saved_bounds_polarity_and_passive_queries(self):
        result = self.simulate()
        self.assertGreaterEqual(len(result['saved']['times']), 9)
        for i, time in enumerate(result['saved']['times']):
            for node in ['x', 'y']:
                self.assert_box(result, i, node, source_box(Q(time)))
        dense = self.simulate(deck=DECK.replace('maxstep=0.125', 'maxstep=0.0625'))
        rows = dict(zip(dense['saved']['times'], dense['saved']['values']))
        boxes = dict(zip(dense['saved']['times'], dense['observation_evidence']['voltage_bounds_V']))
        for i, time in enumerate(result['saved']['times']):
            self.assertEqual(result['saved']['values'][i], rows[time])
            self.assertEqual(result['observation_evidence']['voltage_bounds_V'][i], boxes[time])
        reverse = self.simulate(deck=DECK.replace('VX (x 0)', 'VX (0 x)'))
        self.assertEqual(reverse['saved']['values'][0][0], -.5)
        phase = self.simulate(deck=DECK.replace('sinephase=0', 'sinephase=90'))
        self.assert_box(phase, 0, 'x', (Q(3, 4), Q(3, 4)))

    def test_nonbinary_physical_root_sample_and_timer(self):
        result = self.simulate(HELD)
        self.assertEqual(len(result['transient']['events']), 1)
        lo, hi = result['transient']['events'][0]['observation_time_bounds']
        self.assertLess(Q(lo), Q(1, 6))
        self.assertGreater(Q(hi), Q(1, 6))
        for i, time in enumerate(result['saved']['times']):
            if Q(time) > Q(1, 6):
                self.assert_box(result, i, 'y', source_box(Q(1, 6)))
        dense = self.simulate(HELD, DECK.replace('maxstep=0.125', 'maxstep=0.0625'))
        self.assertEqual(result['transient']['events'], dense['transient']['events'])
        rows = dict(zip(dense['saved']['times'], dense['saved']['values']))
        for time, values in zip(result['saved']['times'], result['saved']['values']):
            self.assertEqual(values, rows[time])
        timer = self.simulate(HELD.replace('@(cross(V(clk)-0.5,+1))', '@(timer(0.125,0))'))
        for i, time in enumerate(timer['saved']['times']):
            if time > .125:
                self.assert_box(timer, i, 'y', source_box(Q(1, 8)))

    def test_unsupported_parameter_and_original_role_combinations(self):
        cases = [
            (PASS, DECK.replace('sinephase=0', 'sinephase=90 phase=0'), 'separate source contract'),
            (PASS, DECK.replace('sinephase=0', 'delay=0'), 'no delay or modulation'),
            (PASS, DECK.replace('freq=1', 'freq=0'), 'positive frequency'),
            (PASS, DECK.replace('freq=1', 'freq=100'), 'Taylor domain'),
            (HELD.replace('V(clk)-0.5', 'V(x)-0.5'), DECK, 'sine cross guards'),
            (HELD.replace('V(clk)-0.5', 'V(clk)-0.5+0*V(x)'), DECK, 'sine cross guards'),
            (HELD.replace('h=V(x);', 'if (0) h=sqrt(V(x)); else h=V(x);'), DECK, 'hidden arm'),
            (HELD.replace('h=0;', 'h=V(x);'), DECK, 'initialization'),
        ]
        for model, deck, message in cases:
            with self.subTest(message=message, model=model):
                with self.assertRaisesRegex(Exception, message):
                    self.simulate(model, deck)

        # A cross-triggered held state cannot borrow the fixed-Timer
        # sampled-Transition profile; retain this role-specific rejection.
        with self.assertRaises(KernelError) as caught:
            self.simulate(HELD.replace('V(y)<+h;', 'V(y)<+transition(h,0,0.001);'), DECK)
        self.assertEqual(caught.exception.detail['kind'], 'unsupported_analytic_source_consumer')
        self.assertEqual(caught.exception.detail['message'],
                         'sampled Transition profile requires independent fixed Timer leaves')


if __name__ == '__main__':
    unittest.main()

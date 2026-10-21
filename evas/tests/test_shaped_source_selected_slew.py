"""A slew whose target is selected by a shaped (rounded) pulse uses the exact
physical curve for its cuts, like a selected Transition. Other slew inputs keep
the source-uncertainty refusal."""
from fractions import Fraction as Q
from pathlib import Path
import tempfile
import unittest

from evas import KernelError
from evas.scs import simulate_scs
from test_affine import KERNEL

VA = '''`include "disciplines.vams"
module gate(clk, out);
input clk; output out; electrical clk, out;
analog begin
 V(out) <+ slew(TARGET, 0.9/SLEWp, -0.9/SLEWp);
end
endmodule
'''
DECK = '''simulator lang=spectre
global 0
ahdl_include "gate.va"
Vclk (clk 0) vsource type=pulse val0=0 val1=0.9 period=10n delay=DELAYn rise=50p fall=50p width=5n
XDUT (clk out) gate
tran tran stop=STOPn maxstep=100p
save clk out
'''


def run(target, root, delay=1, slew=300, stop=25):
    (root / 'gate.va').write_text(VA.replace('TARGET', target).replace('SLEW', str(slew)))
    (root / 'tb.scs').write_text(DECK.replace('DELAY', str(delay)).replace('STOP', str(stop)))
    return simulate_scs(root / 'tb.scs', kernel=KERNEL)


class ShapedSelectedSlew(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def check(self, delay, slew, stop):
        result = run('(V(clk) > 0.45) ? 0.9 : 0.0', self.root, delay, slew, stop)
        saved = result['saved']
        out = saved['nodes'].index('out')
        rate = Q(9, 10) / (slew * Q(1e-12))
        edges = []
        for k in range(3):
            start = delay * Q(1e-9) + k * Q(10e-9)
            edges += [(start + Q(50e-12) / 2, True),
                      (start + Q(50e-12) + Q(5e-9) + Q(50e-12) / 2, False)]
        ramps = 0
        for time, row in zip(saved['times'], saved['values']):
            t = Q(time)
            past = [e for e in edges if e[0] <= t]
            if not past:
                expected = Q(0)
            elif past[-1][1]:
                expected = min(Q(9, 10), rate * (t - past[-1][0]))
            else:
                expected = max(Q(0), Q(9, 10) - rate * (t - past[-1][0]))
            ramps += 0 < expected < Q(9, 10)
            self.assertLessEqual(abs(Q(row[out]) - expected), Q(1e-9), time)
        return ramps

    def test_selected_slew_follows_exact_pulse_crossings(self):
        self.assertGreater(self.check(1, 300, 25), 4)

    def test_fast_edge_after_late_rounded_crossing_uses_exact_cut(self):
        # Near 121 ns one binary64 time step is about 2.6e-23 s; at 0.9/20p
        # V/s its window alone exceeds the 1e-12 V voltage tolerance.
        self.check(121, 20, 128)

    def test_shaped_source_value_leaves_still_refuse(self):
        for target in ['V(clk)', '(V(clk) > 0.45) ? V(clk) : 0.0',
                       '(V(clk) > 0.45) ? 0.9 + 0*V(clk) : 0.0']:
            with self.subTest(target=target):
                with self.assertRaises(KernelError) as caught:
                    run(target, self.root)
                self.assertEqual(caught.exception.detail['kind'],
                                 'unsupported_source_uncertainty')


if __name__ == '__main__':
    unittest.main()

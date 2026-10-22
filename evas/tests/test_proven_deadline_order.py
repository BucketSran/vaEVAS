"""Independent transition deadlines whose exact order is proven inside one ULP."""
GUARDS = ['CROSS', 'TRANSITION', 'EVENT-ORDER']
import os
from pathlib import Path
from fractions import Fraction as Q
import unittest
from evas import KernelError, compile_sources, transient
from test_affine import model, instance, KERNEL as DEFAULT_KERNEL
KERNEL = Path(os.environ.get('EVAS_DEADLINE_KERNEL', DEFAULT_KERNEL))

# The cross root is exactly 1/3. With (rise, delay) = (0.7, 0.8), y ends at
# 1/3+0.1+0.7 and z starts at 1/3+0.8. In binary64 these sums differ by less
# than one ULP at 1.13: the deadline enclosures overlap, and only the exact
# rationals prove that y ends first. With (0.2, 0.3) z starts first instead.
TAU = Q(1, 3)
STOP = 1.5


def times(rise, delay):
    start_z = TAU + Q(delay)
    return sorted({0., 0.3, 0.4, 0.5, 0.8, float(TAU + Q(0.1) + Q(rise)) - 0.01,
                   float(start_z), float(start_z) + 0.01, float(start_z + Q(0.05)), 1.4, STOP})


def body(rise, delay, extra=''):
    return ('@(initial_step) begin q=0; p=0; w=0; end '
            '@(cross(V(u,r)-1,1,1e-9,1e-9)) begin q=1; p=1; end '
            + extra +
            f'V(y,r)<+transition(q,0.1,{rise}); V(z,r)<+transition(p,{delay},0.05); V(o,r)<+w;')


def run(rise=0.7, delay=0.8, extra=''):
    source = model(body(rise, delay, extra), 'real q,p,w; electrical z,o;')
    p = compile_sources({'order.va': source}, [instance()])
    result = transient(p, {'u': [[0., 0.], [STOP, 3 * STOP]]}, times(rise, delay),
                       stop=STOP, max_step=0.05, kernel=KERNEL)
    return p, result


def ramp(t, start, width):
    return min(Q(1), max(Q(0), (t - start) / width))


class ProvenDeadlineOrder(unittest.TestCase):
    def test_reference_order_is_proven_but_below_one_ulp(self):
        for rise, delay, end_first in [(0.7, 0.8, True), (0.2, 0.3, False)]:
            end_y = TAU + Q(0.1) + Q(rise)
            start_z = TAU + Q(delay)
            self.assertEqual(end_y < start_z, end_first)
            self.assertEqual(float(end_y), float(start_z))

    def test_independent_end_then_start_follow_the_fraction_reference(self):
        p, result = run()
        y = p.nodes.index('y')
        z = p.nodes.index('dut:z')
        grid = times(0.7, 0.8)
        self.assertEqual(len(result['solutions']), len(grid))
        for t, row in zip(grid, result['solutions']):
            time = Q(t)
            row = row['voltages']
            self.assertLessEqual(abs(Q(row[y]) - ramp(time, TAU + Q(0.1), Q(0.7))), Q(1e-10))
            self.assertLessEqual(abs(Q(row[z]) - ramp(time, TAU + Q(0.8), Q(0.05))), Q(1e-10))

    def assert_refused(self, **kwargs):
        with self.assertRaises(KernelError) as caught:
            run(**kwargs)
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
        self.assertIn('ordering of operator deadlines', caught.exception.detail['message'])

    def test_an_earlier_pending_activation_keeps_the_refusal(self):
        # z's new ramp could induce an event before y ends; the rule does
        # not admit a start that precedes the other deadline.
        self.assert_refused(rise=0.2, delay=0.3)

    def test_observer_inside_the_shared_window_keeps_the_refusal(self):
        # A timer at the shared binary64 representative lies inside both
        # enclosures. Its write does not touch y or z, but the rule refuses
        # any event inside the window instead of proving that.
        at = float(TAU + Q(0.8))
        self.assert_refused(extra=f'@(timer({at!r})) w=1; ')


if __name__ == '__main__':
    unittest.main()

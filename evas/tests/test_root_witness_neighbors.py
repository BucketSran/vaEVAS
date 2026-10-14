"""Public safety contract for a narrow pulse ending at a held-state timer.

The second source predicate root lies one float beyond the prediction horizon.
Both source directions and both timer sides use the original voltage budget.
Explicit precision refusal is allowed; this does not assert support recovery.
"""
GUARDS = ["DYNAMICS"]
from fractions import Fraction as F
import math
import unittest
from evas import Instance, KernelError, compile_sources, transient
from test_affine import KERNEL


def exact_pulse(horizon):
    r, h = F(1, 3), F(horizon)
    return F(0) if h <= r else F(10**10) * (h-r+(h**3-r**3)/3)


def assert_enclosure(test, bounds, value, answer):
    lo, hi = map(F, bounds)
    test.assertLessEqual(lo, answer)
    test.assertLessEqual(answer, hi)
    test.assertLessEqual(abs(F(value)-answer), F(1e-9)+F(1e-6)*abs(answer))


class RootWitnessNeighbors(unittest.TestCase):
    def test_neighbor_root_outside_horizon_cannot_erase_pulse(self):
        # These decimals are exact binary64 model data. r=1/3 is not.
        before = 1./3
        after = math.nextafter(before, math.inf)
        cutoff = math.nextafter(after, math.inf)
        self.assertLess(F(before), F(1, 3))
        self.assertGreater(F(after), F(1, 3))
        for direction in (1, -1):
            for horizon in (before, after):
                with self.subTest(direction=direction, horizon=horizon):
                    a, b = ('>', '<') if direction == 1 else ('<', '>')
                    source = f'''`include "disciplines.vams"
module m(u,y,z); input u; output y,z; electrical u,y,z; real q;
analog begin
 @(initial_step) q=0; @(timer({horizon!r},1,0)) q=1;
 V(z)<+q;
 V(y)<+idt(1e10*(1+V(u)*V(u))*(3*V(u){a}{direction}?
   (V(u){b}{direction*cutoff!r}*(1-q)?1:0):0),0);
end endmodule'''
                    program = compile_sources({'pulse.va': source},
                        [Instance('dut','m',dict(u='u',y='y',z='z'))])
                    try:
                        response = transient(program, {'u': [[0.,0.],[1.,float(direction)]]},
                            [0.,horizon,1.], stop=1., max_step=.125,
                            vabstol=1e-9, reltol=1e-6, kernel=KERNEL)
                    except KernelError as exc:
                        self.assertIn(exc.diagnostic['kind'],
                                      ('condition_precision','waveform_accuracy','event_resolution'))
                        continue
                    y, z = response['nodes'].index('y'), response['nodes'].index('z')
                    self.assertEqual(response['solutions'][-1]['voltages'][z], 1.)
                    answer = exact_pulse(horizon)
                    for index in (1, 2):
                        assert_enclosure(self,
                            response['observation_evidence']['voltage_bounds_V'][index][y],
                            response['solutions'][index]['voltages'][y], answer)

    def test_exact_oracle_detects_erased_pulse(self):
        answer = exact_pulse(math.nextafter(1./3, math.inf))
        self.assertGreater(answer, F(1e-9))
        with self.assertRaises(AssertionError):
            assert_enclosure(self, [0.,0.], 0., answer)
        value = float(answer)
        assert_enclosure(self, [math.nextafter(value,-math.inf),
                                math.nextafter(value,math.inf)], value, answer)


if __name__ == '__main__':
    unittest.main()

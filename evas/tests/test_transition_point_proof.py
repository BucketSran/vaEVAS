"""Physical point values from rational PWL roots, with unchanged error budgets."""

GUARDS = ["TRANSITION", "TIMED-OPERATOR", "CROSS"]

from fractions import Fraction as F
from math import ulp
import unittest

from evas import KernelError, transient
from test_transition import compile_transition, KERNEL
from test_transition_accuracy import execute


class TransitionPointProof(unittest.TestCase):
    def test_nonbinary_pwl_root_removes_representative_start_displacement(self):
        # Place the physical cross just above a binary64 time. The upper
        # representative shifts the old falling ramp by more than 1e-12 V.
        center, lo, hi = 65.11e-9, 65e-9, 65.22e-9
        sample, stop = 65.12e-9, 65.3e-9
        wanted = F(center) + F(ulp(center))/100
        threshold = float(F(.9)*(wanted-F(lo))/(F(hi)-F(lo)))
        root = F(lo)+(F(hi)-F(lo))*F(threshold)/F(.9)
        exact = max(F(0), F(.9)*(root+F(1e-11)-F(sample))/F(1e-11))
        body = (f'@(initial_step) a=0.9; '
                f'@(cross(V(u,r)-{threshold!r},+1,1p,1u)) a=0; '
                'V(y,r)<+transition(a,0,10p,10p);')
        program = compile_transition(body, 'real a;')
        for times in [[0, sample], [0, 65.115e-9, sample]]:
            result = transient(program, {'u':[[0,0],[lo,0],[hi,.9],[stop,.9]]}, times,
                               stop=stop, max_step=stop, kernel=KERNEL,
                               vabstol=1e-12, reltol=0)
            actual = result['solutions'][-1]['voltages'][result['nodes'].index('y')]
            self.assertEqual(actual, float(exact))
            self.assertLessEqual(abs(F(actual)-exact), F(1e-12))

    def test_correctly_rounded_point_still_rejects_unrepresentable_voltage(self):
        # Correctly rounding 1/3 cannot meet this absolute voltage budget.
        body = ('@(initial_step) a=0; @(timer(1,0,0.001)) a=1; '
                'V(y,r)<+transition(a,0,3,3);')
        with self.assertRaisesRegex(KernelError, 'waveform_accuracy'):
            execute(body, [0,2,4], 4, atol=1e-18, declarations='real a;')

"""Independent nearest-cell controls for ADR-006, preserving true source bands."""
GUARDS = ['LANG', 'EVENT-CONDITIONS', 'TIMER', 'COMPOSE']
import math
import unittest
from fractions import Fraction as Q
from evas import KernelError
from test_event_conditions import source, execute, states
from test_affine import model
from test_timer import run_timer

class ProgramRNCells(unittest.TestCase):
    def test_exact_midpoint_tie_and_adjacent_cell(self):
        hi=math.nextafter(1.,math.inf)
        self.assertEqual((Q(1)+Q(hi))/2,Q(1)+Q(1,2**53))
        for end,want in [(hi,3),(math.nextafter(hi,math.inf),2)]:
            text=source('if(V(u,r)>1)q=2;else q=3;',trigger='timer(0.5,0,0.001)')
            result=execute(text,points=[[0,1],[1,end]], initial_records=([0], [0], 1))
            self.assertEqual(states(result),[0,want,want])

    def test_true_band_inside_cell_is_singleton(self):
        text=source('if(V(u,r)>1)q=2;else q=3;',trigger='timer(0.5,0,0.001)')
        self.assertEqual(states(execute(text,points=[[0,1],[1,1]],source_errors={'u':2**-55}, initial_records=([0], [0], 1))),[0,3,3])

    def test_true_band_straddling_adjacent_cell_must_refuse(self):
        text=source('if(V(u,r)>1)q=2;else q=3;',trigger='timer(0.5,0,0.001)')
        hi=math.nextafter(1.,math.inf)
        # Exact interpolation is the RN midpoint; the irreducible band
        # contains values strictly below and above it, so both 1 and hi occur.
        with self.assertRaisesRegex(KernelError,'event_condition'):
            execute(text,points=[[0,1],[1,hi]],source_errors={'u':2**-55}, initial_records=([0], [0], 1))

    def test_state_addition_halfway_and_first_above_halfway(self):
        for exponent in [-80,0,80]:
            unit=2.**exponent
            halfway=2.**(exponent-53)
            for delta,want in [(halfway,0.),(math.nextafter(halfway,math.inf),1e16*2**-52)]:
                with self.subTest(exponent=exponent,delta=delta):
                    # RN of this sum is independently supplied by binary64
                    # arithmetic; exact Fraction proves its side of halfway.
                    if want:self.assertGreater(Q(delta),Q(halfway))
                    else:self.assertEqual(Q(delta),Q(halfway))
                    text=model(f'''@(initial_step)s=0;@(timer(0.5,0,0.01))begin
                        s={unit!r};s=s+{delta!r};s=s-{unit!r};end
                        V(y,r)<+1e16*s/{unit!r};''','real s;')
                    result=run_timer(text,stop=1,times=[0,1], initial_records=([0], [0], 1))
                    self.assertAlmostEqual(result['solutions'][-1]['voltages'][result['nodes'].index('y')],want,delta=1e-12)

    def test_amplified_sample_domain_keeps_cross_cell_uncertainty(self):
        text=source('if(V(u,r)>0)q=V(u,r)-0.5;else q=0;',rhs='1e16*q')
        # Same physical nominal, two irreducible domains. The smaller domain
        # has singleton RN image .5; the larger includes its predecessor.
        self.assertEqual(states(execute(text,points=[[0,.5],[1,.5]],source_errors={'u':2**-56}, initial_records=([0], [0], 1))),[0.,0.,0.])
        # This detector requires refusal; exact diagnostic classification is
        # retained separately in the receipt (fixed-v11: singular_jacobian).
        with self.assertRaises(KernelError):
            execute(text,points=[[0,.5],[1,.5]],source_errors={'u':2**-54}, initial_records=([0], [0], 1))

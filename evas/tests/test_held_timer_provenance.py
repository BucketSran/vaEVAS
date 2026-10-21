"""Held timer phase uses mathematical time proofs, retaining numerical bounds."""
import os
from fractions import Fraction
from pathlib import Path
import unittest

from evas import KernelError, compile_sources, transient
from test_affine import instance, model

GUARDS = ['TIMER', 'EVENT-ORDER', 'TIMED-OPERATOR', 'COMPOSE']
KERNEL = Path(os.environ.get('EVAS_HELD_PROOF_KERNEL', str(
    Path(__file__).resolve().parents[1] / 'rust_core/target/debug/evas-kernel')))


def clock(update, *, initial='q=0;half=0.1;due=0.1;', declarations='integer q;real half,due;'):
    return compile_sources({'held-proof.va':model(
        '@(initial_step)begin '+initial+'end @(timer(due))begin q=1-q;'+update+
        'end V(y,r)<+transition(q,0,0.01,0.01);', declarations)}, [instance()])


def run(program, times=(0,.25,.3,.35), **options):
    return transient(program, {'u':[[0,0],[1,1]]}, list(times),
                     stop=.4,max_step=.05,kernel=KERNEL,**options)


def output(result):
    return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]


class HeldTimerProvenance(unittest.TestCase):
    def test_point_start_state_and_held_offset_preserve_query_phase(self):
        # The exact third timer is 3*binary64(.1), strictly after binary64(.3).
        self.assertGreater(3*Fraction(.1),Fraction(.3))
        for update in ('due=due+half;', 'due=half+due;', 'due=due+0.1;', 'due=$abstime+half;',
                       'due=$abstime+0.1;'):
            with self.subTest(update=update):
                self.assertEqual(output(run(clock(update))),[0,0,0,1])

    def test_point_offset_changes_follow_selected_assignment_order(self):
        before=clock('if(q==1)half=0.125;else half=0.1;due=due+half;')
        after=clock('due=due+half;if(q==1)half=0.125;else half=0.1;')
        self.assertEqual(output(run(before,times=(0,.15,.215,.245))),[0,1,1,0])
        self.assertEqual(output(run(after,times=(0,.15,.215,.245))),[0,1,0,0])

    def test_exact_nonbinary_division_offset_preserves_physical_phase(self):
        # Exact point held inputs prove .5/3=1/6 even though its enclosure
        # is nonpoint. The query is still compared with the rational time,
        # never with an arbitrary endpoint of that enclosure.
        program=clock('due=$abstime+0.5/f;',initial='q=0;half=0;due=0.1;f=3;',
                      declarations='integer q;real half,due,f;')
        exact = Fraction(.1)+Fraction(1,6)
        boundary = float(exact)
        times = (0, boundary, .35)
        actual = output(run(program, times=times))
        value = 1 if Fraction(boundary) <= exact else max(
            Fraction(0), 1-(Fraction(boundary)-exact)/Fraction(.01))
        self.assertLessEqual(abs(Fraction(actual[1])-value), Fraction(1e-12))
        self.assertEqual(actual[0], 0)
        self.assertEqual(actual[2], 0)

    def test_future_amplification_keeps_inherited_arithmetic_error(self):
        for gain in (1,10**12):
            program=compile_sources({'future-error.va':model(
                '@(initial_step)begin n=0;x=0;p=0;half=0.1;due=0.1;end '
                '@(timer(due))begin n=n+1;if(n==1)x=0.45*V(u,r);'
                'if(n==3)p=x;due=due+half;end '
                'V(y,r)<+transition(n,0,0.01,0.01)+'+str(gain)+'*p;',
                'integer n;real x,p,half,due;')},[instance()])
            args=dict(stop=.4,max_step=.05,kernel=KERNEL,vabstol=1e-8,reltol=0)
            if gain==1:
                result=transient(program,{'u':[[0,.16],[1,.16]]},[0,.15,.25,.35],**args)
                self.assertAlmostEqual(output(result)[-1],3.072,places=12)
            else:
                with self.assertRaises(KernelError) as caught:
                    transient(program,{'u':[[0,.16],[1,.16]]},[0,.15,.25,.35],**args)
                self.assertEqual(caught.exception.detail['kind'],'waveform_accuracy')
                self.assertIn('forward error',caught.exception.detail['message'])

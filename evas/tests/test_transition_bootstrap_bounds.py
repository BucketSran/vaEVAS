"""Cold held Transition retains independently checked zero-event real error."""
GUARDS = ["LANG", "COMPOSE", "TRANSITION", "EVENT-ORDER"]
import unittest
from fractions import Fraction as Q
from evas import compile_sources, transient, CompileError, KernelError
from test_affine import KERNEL, instance, model


def program(sigma=.01, gain=1):
    return compile_sources({'cold.va':model('''@(initial_step)begin n=0;out=0;end
        @(timer(0,1))begin n=n+1;if(n%8==1)out=V(u,r)-sigma;else out=V(u,r)+sigma;end
        V(y,r)<+GAIN*(transition(out,0,0.1,0.1)-0.61);'''.replace('GAIN',str(gain)),
        f'parameter real sigma={sigma};integer n;real out;')},[instance()])


class TransitionBootstrapBounds(unittest.TestCase):
    def test_nonpoint_cold_seed_and_later_target_enclose_original_real_values(self):
        for sigma in [.01,.037]:
            with self.subTest(sigma=sigma):
                p=program(sigma)
                r=transient(p,{'u':[[0,.62],[2,.62]]},[0,.5,1.5],stop=1.5,max_step=.1,
                            vabstol=1e-12,reltol=0,kernel=KERNEL)
                y=r['nodes'].index('y')
                boxes=r['observation_evidence']['voltage_bounds_V']
                for box, want in zip(boxes,[Q(.62)-Q(sigma)-Q(.61),Q(.62)-Q(sigma)-Q(.61),Q(.62)+Q(sigma)-Q(.61)]):
                    self.assertIsNotNone(box)
                    lo,hi=map(Q,box[y]);self.assertLessEqual(lo,want);self.assertGreaterEqual(hi,want)
                self.assertLess(boxes[0][y][0],boxes[0][y][1])

    def test_initial_voltage_budget_rejects_amplified_seed_error(self):
        with self.assertRaises(KernelError):
            transient(program(gain=1099511627776),{'u':[[0,.62],[2,.62]]},[0,.5],
                      stop=.5,max_step=.1,vabstol=1e-12,reltol=0,kernel=KERNEL)

    def test_bounded_cold_seed_retains_passive_initial_display_records(self):
        from test_initial_display_transition import source,INITIAL,compile_pair,execute,displays
        import copy
        text=source('@(timer(0,0,0)) a=V(u,r)+0.125;',
                    INITIAL+'\n@(timer(0,0,0)) $display("timer=%d",n);')
        p=compile_pair(text);original=copy.deepcopy(p.to_dict());r=execute(p,value=2**-60)
        self.assertEqual(p.to_dict(),original)
        self.assertEqual(displays(r),[(0,'before=0'),(0,'after=3'),(0,'timer=3')])
        y=r['nodes'].index('y');want=Q(.125)+Q(2**-60)
        for box in r['observation_evidence']['voltage_bounds_V']:
            self.assertIsNotNone(box);lo,hi=map(Q,box[y]);self.assertLessEqual(lo,want);self.assertGreaterEqual(hi,want)

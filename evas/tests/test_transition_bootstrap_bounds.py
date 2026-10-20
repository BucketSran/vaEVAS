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


def mixed_program(*, native=False, target='out', gain=1):
    bit='(n&1)' if native else 'c'
    return compile_sources({'mixed-cold.va':model(f'''
        @(initial_step)begin n=0;c=0;out=0;end
        @(timer(0,1))begin
            n=n+1;c=1-c;
            if(n%8==1)out=V(u,r)-0.01;else out=V(u,r)+0.01;
        end
        V(y,r)<+{gain}*(transition({target},0,0.1,0.1)-0.61);
        V(z,r)<+transition({bit}?0.9:0.0,0,0.1,0.1);
    ''','integer n,c;real out;',ports='u,y,z,r',
        directions='input u;output y,z;inout r;')},
        [instance(connections=dict(u='u',y='y',z='z',r='0'))])


class TransitionBootstrapBounds(unittest.TestCase):
    def test_bare_real_and_typed_integer_targets_keep_separate_cold_boxes(self):
        for native in [False,True]:
            with self.subTest(native=native):
                p=mixed_program(native=native)
                r=transient(p,{'u':[[0,.62],[2,.62]]},[0,.05,.5,1.5],
                            stop=1.5,max_step=.1,vabstol=1e-12,reltol=0,kernel=KERNEL)
                y,z=r['nodes'].index('y'),r['nodes'].index('z')
                boxes=r['observation_evidence']['voltage_bounds_V']
                expected=[Q(.62)-Q(.01)-Q(.61)]*3+[Q(.62)+Q(.01)-Q(.61)]
                for box,want in zip(boxes,expected):
                    lo,hi=map(Q,box[y]);self.assertLessEqual(lo,want);self.assertGreaterEqual(hi,want)
                self.assertLess(boxes[0][y][0],boxes[0][y][1])
                self.assertEqual([row['voltages'][z] for row in r['solutions']],[.9,.9,.9,0])

    def test_mixed_cold_seed_error_still_reaches_the_voltage_budget(self):
        for native in [False,True]:
            with self.subTest(native=native),self.assertRaisesRegex(KernelError,'accuracy|forward error'):
                transient(mixed_program(native=native,gain=1099511627776),
                          {'u':[[0,.62],[2,.62]]},[0,.5],stop=.5,max_step=.1,
                          vabstol=1e-12,reltol=0,kernel=KERNEL)

    def test_mixed_integer_target_does_not_admit_a_nonbare_real_seed(self):
        for native in [False,True]:
            for target in ['out+0.0','1?out:out']:
                with self.subTest(native=native,target=target),self.assertRaisesRegex(KernelError,'unsupported_initial_history'):
                    transient(mixed_program(native=native,target=target),
                              {'u':[[0,.62],[2,.62]]},[0,.5],stop=.5,max_step=.1,
                              vabstol=1e-12,reltol=0,kernel=KERNEL)

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

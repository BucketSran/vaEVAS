"""Fixed rational composition contract; no simulator-generated golden values."""
from fractions import Fraction as F
import unittest

from evas import compile_sources, transient
from test_affine import KERNEL, instance, model


SOURCE = model('''
    @(initial_step) begin n=0; c=0; q=0; end
    @(timer(1,2,1e-8)) n=n+1;
    @(timer(1,2,1e-8)) q=V(z,r);
    @(cross(V(u,r),-1,1e-8,1e-9)) c=c+1;
    V(y,r)<+transition(n,.25,.5,.5);
    V(z,r)<+gain*(n+c+absdelay(V(u,r),.5)+slew(V(u,r),1,-2));
    V(h,r)<+q;
''', 'integer n,c; real q; parameter real gain=1;',
    ports='u,y,z,h,r', directions='input u; output y,z,h; inout r;')


def input_value(t):
    return 2*t if t <= 2 else (12-4*t if t <= 4 else F(-4))


def exact(t, gain):
    ticks = [F(k) for k in [1,3,5,7] if k <= t]
    n, c = len(ticks), int(t >= 3)
    tr = sum(max(F(0), min(F(1), 2*(t-k-F(1,4)))) for k in ticks)
    limited = t if t <= F(12,5) else max(F(-4), F(36,5)-2*t)
    z = gain*(n+c+input_value(max(F(0), t-F(1,2)))+limited)
    # At timer/cross coincidences q reads the jointly updated voltage.
    sampled = {1: F(3), 3: F(31,5), 5: F(-14,5), 7: F(-3)}
    q = gain*sampled[int(ticks[-1])] if ticks else F(0)
    return (tr, z, q), (F(n), F(c), q)


class TimedComposition(unittest.TestCase):
    def test_two_instances_orders_grids_and_steps_share_atomic_semantics(self):
        instances = [instance(name, connections=dict(u='u', y=f'{name}_y',
                    z=f'{name}_z', h=f'{name}_h', r='0'), parameters=dict(gain=gain))
                     for name, gain in [('a',1), ('b',2)]]
        sparse = list(map(F, [0,1,1.25,1.5,2,3,3.25,3.5,4,5,6,7,8]))
        dense = [F(k,8) for k in range(65)]
        for order in [instances, instances[::-1]]:
            program = compile_sources({'composition.va': SOURCE}, order)
            for times in [sparse, dense]:
                for step in [8, .125]:
                    with self.subTest(order=[i.name for i in order], grid=len(times), step=step):
                        result = transient(program, {'u': [[0,0],[2,4],[4,-4],[8,-4]]},
                                           list(map(float,times)), stop=8, max_step=step,
                                           kernel=KERNEL, vabstol=1e-12, reltol=1e-10)
                        self.assertEqual(len(result['transient']['events']), 18)
                        for name, gain in [('a',1), ('b',2)]:
                            nodes = [result['nodes'].index(f'{name}_{p}') for p in ['y','z','h']]
                            states = [result['transient']['state_names'].index(f'{name}:{p}')
                                      for p in ['n','c','q']]
                            for k,t in enumerate(times):
                                voltages, memory = exact(t,F(gain))
                                for j,answer in zip(nodes,voltages):
                                    self.assertLessEqual(abs(F(result['solutions'][k]['voltages'][j])-answer),F(2e-12))
                                for j,answer in zip(states,memory):
                                    self.assertLessEqual(abs(F(result['transient']['states'][k][j])-answer),F(2e-12))

"""Two-delay contracts with an exact-rational oracle on supplied binary64 inputs."""
from fractions import Fraction as F
import math
import unittest
from evas import CompileError, KernelError, compile_sources, transient
from test_affine import KERNEL, instance, model

GUARDS = ['ABSDELAY', 'TIMED-OPERATOR']


def run(body, points, times, *, d1=1, d2=2, stop=8, step=8, atol=1e-12,
        declarations='', instances=None):
    source = model(body, 'parameter real d1=1,d2=2; '+declarations)
    program = compile_sources({'cascade.va': source}, instances or [
        instance(parameters={'d1':d1,'d2':d2})])
    return transient(program, {'u': points}, times, stop=stop, max_step=step,
                     kernel=KERNEL, vabstol=atol, reltol=0)


def values(result, name='y'):
    return [row['voltages'][result['nodes'].index(name)] for row in result['solutions']]


def answer(points, t, d1, d2):
    q = max(F(t)-F(d1)-F(d2), F(0))
    for (a,x),(b,y) in zip(points, points[1:]):
        if q <= F(b):
            return F(x)+(F(y)-F(x))*(q-F(a))/(F(b)-F(a))
    return F(points[-1][1])


class CascadeContracts(unittest.TestCase):
    def test_two_fixed_delays_use_physical_history(self):
        points = [[0,0],[2,2],[8,2]]
        times = [0,1,2,3,4,5,8]
        body = 'V(y,r)<+absdelay(absdelay(V(u,r),d1),d2);'
        program = compile_sources({'identity.va':model(body,'parameter real d1=1,d2=2;')},[instance()]).to_dict()
        self.assertEqual(len(program['operators']),2)
        self.assertNotEqual(program['operators'][0]['origin'],program['operators'][1]['origin'])
        result = run(body, points, times)
        self.assertEqual(values(result), [0,0,0,0,1,2,2])

    def test_nonzero_initial_and_equivalent_internal_voltage_encodings(self):
        times = [0,1,2,3,4,5,8]
        points = [[0,-1],[2,1],[8,1]]
        bodies = [
            ('V(y,r)<+absdelay(absdelay(V(u,r),d1),d2);', ''),
            ('V(z,r)<+absdelay(V(u,r),d1); V(y,r)<+absdelay(V(z,r),d2);', 'electrical z;'),
            ('V(y,r)<+absdelay(V(z,r),d2); V(z,r)<+absdelay(V(u,r),d1);', 'electrical z;'),
        ]
        for body, declarations in bodies:
            with self.subTest(body=body):
                result = run(body, points, times, declarations=declarations)
                self.assertEqual(values(result), [-1,-1,-1,-1,0,1,1])

    def test_nonbinary_delays_keep_exact_parameter_time_and_query_refinement(self):
        points = [[0,0],[2,2],[3,2]]
        total = float(F(.1)+F(.2))
        times = sorted(set([0,.1,.2,math.nextafter(total,-math.inf),total,
                            math.nextafter(total,math.inf),1,2.3,3]))
        dense = sorted(set(times + [i/32 for i in range(97)]))
        body = 'V(y,r)<+absdelay(absdelay(V(u,r),d1),d2);'
        baseline = None
        for grid, step in [(times,3),(dense,3),(times,.125)]:
            result = run(body,points,grid,d1=.1,d2=.2,stop=3,step=step)
            common = [values(result)[grid.index(t)] for t in times]
            for actual,t in zip(common,times):
                self.assertLessEqual(abs(F(actual)-answer(points,t,.1,.2)),F(1e-12))
            if baseline is None:
                baseline = common
            self.assertEqual(common,baseline)
        internal = run('V(y,r)<+absdelay(V(z,r),d2); V(z,r)<+absdelay(V(u,r),d1);',
                       points,times,d1=.1,d2=.2,stop=3,step=3,declarations='electrical z;')
        self.assertEqual(values(internal),baseline)

    def test_two_instances_and_per_call_parameters_remain_separate(self):
        points = [[0,0],[2,2],[8,2]]
        times = [0,1,2,3,4,5,8]
        a = instance('a', connections={'u':'u','y':'a','r':'0'},parameters={'d1':1,'d2':2})
        b = instance('b', connections={'u':'u','y':'b','r':'0'},parameters={'d1':0,'d2':1})
        body = 'V(y,r)<+absdelay(absdelay(V(u,r),d1),d2);'
        for order in [[a,b],[b,a]]:
            result = run(body,points,times,instances=order)
            for node,d1,d2 in [('a',1,2),('b',0,1)]:
                self.assertEqual(values(result,node),[float(answer(points,t,d1,d2)) for t in times])

    def test_amplified_error_must_reach_original_node_budget(self):
        points = [[0,0],[3,1]]
        body = 'V(y,r)<+1073741824*absdelay(absdelay(V(u,r),d1),d2);'
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(body,points,[0,1,2,3],d1=.1,d2=.2,stop=3,step=3,atol=1e-10)
        # The pre-frozen loose control also refuses: the conservative tube's
        # final node enclosure is 1.1920928955078125e-6 > 1e-6. Keep that limit;
        # do not enlarge the budget after observing the result.
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run(body,points,[0,1,2,3],d1=.1,d2=.2,stop=3,step=3,atol=1e-6)

    def test_displaced_corners_cannot_be_accepted_as_nominal_history(self):
        a = float(2**54)
        points = [[0,0],[a,0],[a+4,1],[a+8,1]]
        with self.assertRaisesRegex(KernelError,'waveform_accuracy'):
            run('V(y,r)<+absdelay(absdelay(V(u,r),d1),d2);',points,
                [0,a,a+4,a+8],d1=3,d2=3,stop=a+8,step=a+8)
        self.assertEqual(answer(points,a+8,3,3),F(1,2))

    def test_unsupported_dependencies_and_hidden_cancellation_remain_rejected(self):
        bodies = [
            ('V(y,r)<+absdelay(absdelay(absdelay(V(u,r),1),1),1);',''),
            ('V(y,r)<+absdelay(slew(V(u,r),1,-1),1);',''),
            ('V(z,r)<+absdelay(V(u,r),1); V(y,r)<+absdelay(2*V(z,r),1);','electrical z;'),
            ('V(z,r)<+absdelay(V(u,r),1); V(y,r)<+absdelay(V(z,r)+0.1,1);','electrical z;'),
            ('V(z,r)<+absdelay(V(u,r),1); V(y,r)<+absdelay(V(z,r)+0*q,1);','electrical z; real q;'),
            ('V(z,r)<+slew(V(u,r),1,-1); V(y,r)<+absdelay(0*V(z,r)+V(u,r),1);','electrical z;'),
            ('V(z,r)<+absdelay(V(y,r),1); V(y,r)<+absdelay(V(z,r),1);','electrical z;'),
            ('V(y,r)<+absdelay(absdelay(V(u,r),1),V(u,r));',''),
            ('@(initial_step) n=0; V(y,r)<+absdelay(absdelay(V(u,r),1),1); @(cross(V(y,r)-0.5,1)) n=n+1;','integer n;'),
        ]
        for body,declarations in bodies:
            with self.subTest(body=body), self.assertRaises((CompileError,KernelError)):
                run(body,[[0,0],[2,2],[8,2]],[0,8],declarations=declarations)

    def test_cross_instance_internal_history_remains_rejected(self):
        source = model('V(y,r)<+absdelay(V(u,r),1);')
        program = compile_sources({'first.va':source.replace('module m','module first'),
                                   'second.va':source.replace('module m','module second')},
            [instance('a',module='first',connections={'u':'u','y':'d','r':'0'}),
             instance('b',module='second',connections={'u':'d','y':'y','r':'0'})])
        with self.assertRaisesRegex(KernelError,'same-instance'):
            transient(program,{'u':[[0,0],[2,2],[8,2]]},[0,8],stop=8,max_step=8,
                      kernel=KERNEL,vabstol=1e-12,reltol=0)

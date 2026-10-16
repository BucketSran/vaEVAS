"""Physical time is sampled by events, with no artificial integral history."""
GUARDS = ["LANG", "CROSS", "EVENT-ORDER"]

import unittest
from fractions import Fraction as Q
from evas import compile_sources, transient, KernelError
from test_affine import KERNEL, model, instance


class EventTime(unittest.TestCase):
    def test_timer_samples_physical_time_and_holds_it(self):
        p = compile_sources({'time.va': model('''@(initial_step) q=-1;
            @(timer(0.25,0.5)) q=$abstime; V(y,r)<+q;''', 'real q;')}, [instance()])
        r = transient(p, {'u': [[0,0],[1,0]]}, [0,.25,.5,.75,1],
                      stop=1,max_step=.4,kernel=KERNEL)
        self.assertEqual([s['voltages'][r['nodes'].index('y')] for s in r['solutions']],
                         [-1,.25,.25,.75,.75])

    def test_time_difference_after_cross_is_grid_independent(self):
        p = compile_sources({'time.va': model('''@(initial_step) q=0;
            @(cross(V(u,r)-0.5,+1)) q=$abstime;
            V(y,r)<+$abstime-q;''', 'real q;')}, [instance()])
        baseline = None
        trigger = next(event.trigger for event in p.events if event.trigger.kind=='cross')
        for original in [[0,.5,1], [0,.1,.4,.5,.7,1]]:
            seed=transient(p, {'u': [[0,0],[1,1]]}, original, stop=1,max_step=.3,kernel=KERNEL)
            event, = seed['transient']['events']
            te = Q(event['time'])
            self.assertGreater(te, Q(.5))
            self.assertLessEqual(te-Q(.5), Q(trigger.time_tolerance))
            self.assertLessEqual(te-Q(.5), Q(trigger.expression_tolerance))
            self.assertEqual(event['after'], [event['time']])
            times = sorted(set(original+[event['time']]))
            result=transient(p, {'u': [[0,0],[1,1]]}, times, stop=1,max_step=.3,kernel=KERNEL)
            for t,row,state in zip(times,result['solutions'],result['transient']['states']):
                held = te if Q(t) >= te else Q(0)
                self.assertEqual(state, [float(held)])
                self.assertEqual(row['voltages'][result['nodes'].index('y')], float(Q(t)-held))
            self.assertEqual(result['transient']['events'], seed['transient']['events'])
            if baseline is not None:
                self.assertEqual(result['transient']['events'], baseline)
            baseline = result['transient']['events']

    def test_caller_cannot_override_absolute_time(self):
        p=compile_sources({'time.va':model('V(y,r)<+$abstime;')}, [instance()])
        with self.assertRaises(KernelError) as raised:
            transient(p, {'u':[[0,0],[1,0]], '$abstime':[[0,3],[1,3]]}, [0,1],
                      stop=1,max_step=.1,kernel=KERNEL)
        self.assertEqual(raised.exception.detail['kind'], 'invalid_inputs')

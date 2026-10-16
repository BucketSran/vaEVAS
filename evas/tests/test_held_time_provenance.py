"""Optional exact time values preserve phase without narrowing state enclosures."""
GUARDS=['TIMER','CROSS','EVENT-ORDER','COMPOSE']
from fractions import Fraction as F
import math
import os
from pathlib import Path
import unittest
from evas import KernelError,compile_sources,transient
from test_affine import model,instance,KERNEL as DEFAULT_KERNEL
KERNEL=Path(os.environ.get('EVAS_HELD_TIME_KERNEL',DEFAULT_KERNEL))


def around(exact, *, stop=0.75):
    near=float(exact)
    return [0.,0.3,math.nextafter(near,-math.inf),near,math.nextafter(near,math.inf),0.6,stop]


def execute(action='due=$abstime+0.1;', *, source=None, points=None, times=None, forced=False):
    source=source or model('@(initial_step)begin due=100;q=0;end '
        '@(cross(V(u,r)-1,1,1e-9,1e-9))begin '+action+'end '
        '@(timer(due,0,1e-9))q=q+1;@(timer(0.6,0,1e-9))q=q+1;V(y,r)<+q;',
        'real due,q;')
    p=compile_sources({'held-time.va':source},[instance()])
    times=times or around(F(1,3)+F(.1))
    return transient(p,{'u':points or [[0.,0.],[1.,3.]]},times,stop=.75,max_step=.05,
                     strobetimes=times if forced else [],kernel=KERNEL)


def output(result):
    return [row['voltages'][result['nodes'].index('y')] for row in result['solutions']]


class HeldTimeProvenance(unittest.TestCase):
    def callback_deadline(self, result):
        cross = next(e for e in result['transient']['events'] if e['kind']=='cross')
        te = F(cross['time'])
        self.assertGreater(te, F(1,3))
        self.assertLessEqual(te-F(1,3), F(1e-9))
        self.assertGreater(3*te-1, 0)
        self.assertLessEqual(3*te-1, F(1e-9))
        return te+F(.1)

    def assert_deadline_outputs(self, result, deadline):
        expected = [int(F(t)>=deadline)+int(F(t)>=F(.6))
                    for t in result['transient']['times']]
        self.assertEqual(output(result), expected)
        timer = next(e for e in result['transient']['events'] if e['event']==1)
        self.assertGreaterEqual(F(timer['time']), deadline)
        self.assertLessEqual(F(timer['time'])-deadline, F(1e-9))
        # $abstime was sampled at the same certified te. The stored value may
        # round, but its independent exact sum is at most one ULP away.
        cross = next(e for e in result['transient']['events'] if e['kind']=='cross')
        self.assertLessEqual(abs(F(cross['after'][0])-deadline), F(math.ulp(float(deadline))))

    def test_source_root_delay_neighbours_and_later_callback(self):
        # Keep every original tau+.1 query, then also straddle the true te+.1.
        original = around(F(1,3)+F(.1))
        seed = execute(times=original)
        deadline = self.callback_deadline(seed)
        times = sorted(set(original+around(deadline)))
        plain=execute(times=times);forced=execute(times=times,forced=True)
        self.assert_deadline_outputs(plain, deadline)
        self.assertEqual(plain['solutions'],forced['solutions'])
        self.assertEqual(plain['transient']['events'],forced['transient']['events'])
        self.assertEqual(seed['transient']['events'], plain['transient']['events'])
        dense=execute(times=sorted(set(times+[.1,.2,.4,.5,.7])))
        for time,row in zip(times,plain['solutions']):
            self.assertEqual(row,dense['solutions'][dense['transient']['times'].index(time)])
        self.assertEqual(plain['transient']['events'],dense['transient']['events'])

    def test_selected_sequential_copy_uses_new_local_time_value(self):
        for action in ['due=$abstime;due=due+0.1;',
                       'due=$abstime+0.1;if(V(u,r)<0)due=V(u,r);']:
            with self.subTest(action=action):
                original = around(F(1,3)+F(.1))
                seed = execute(action, times=original)
                deadline = self.callback_deadline(seed)
                result = execute(action, times=sorted(set(original+around(deadline))))
                self.assert_deadline_outputs(result, deadline)
                self.assertEqual(result['transient']['events'], seed['transient']['events'])

    def test_unknown_or_dynamic_rewrite_drops_old_proof(self):
        # The first original source remains genuinely ambiguous at a query.
        with self.assertRaises(KernelError) as caught:
            execute('due=$abstime+0.1;due=V(u,r)/3+0.1;')
        self.assertEqual(caught.exception.detail['kind'],'event_resolution')
        self.assertIn('physical event phase',caught.exception.detail['message'])
        # The other original source has an interval deadline, but every
        # original query is outside it. Losing optional identity is not a
        # reason to throw away an otherwise adequate numerical certificate.
        action = 'due=$abstime+0.1;due=$abstime+0.1*V(u,r);'
        result = execute(action)
        cross = next(e for e in result['transient']['events'] if e['kind']=='cross')
        te = F(cross['time'])
        exact = te+F(.1)*(3*te)
        timer = next(e for e in result['transient']['events'] if e['event']==1)
        lo,hi = timer['observation_time_bounds']
        self.assertLess(lo,hi)
        self.assertLessEqual(F(lo),exact)
        self.assertLessEqual(exact,F(hi))
        self.assertEqual(output(result),
            [int(F(t)>=exact)+int(F(t)>=F(.6)) for t in result['transient']['times']])
        # A new query inside the actual unproven interval must still fail;
        # retaining the earlier $abstime+.1 identity would incorrectly pass.
        self.assertLess(F(lo), exact)
        for _ in range(2):
            with self.assertRaises(KernelError) as caught:
                execute(action, times=sorted(set(around(F(1,3)+F(.1))+[lo])))
            self.assertEqual(caught.exception.detail['kind'],'event_resolution')
            self.assertIn('physical event phase',caught.exception.detail['message'])
        self.assertEqual(execute(action)['transient']['events'],result['transient']['events'])

    def test_complete_identity_curve_qualifies_without_abstime_name(self):
        source=model('@(initial_step)begin due=100;q=0;end @(timer(0.3,0,1e-9))due=V(u,r)+0.1;@(timer(due,0,1e-9))q=q+1;@(timer(0.6,0,1e-9))q=q+1;V(y,r)<+q;','real due,q;')
        exact=F(.3)+F(.1); times=around(exact)
        r=execute(source=source,points=[[0.,0.],[1.,1.]],times=times)
        self.assertEqual(output(r),[int(F(t)>=exact)+int(F(t)>=F(.6))for t in times])
        for points in [[[0.,0.],[.3,.3],[1.,.75]],[[0.,0.],[.15,.14],[.3,.3],[1.,1.]]]:
            with self.subTest(points=points),self.assertRaises(KernelError)as caught:
                execute(source=source,points=points,times=times)
            self.assertEqual(caught.exception.detail['kind'],'event_resolution')
            self.assertIn('physical event phase',caught.exception.detail['message'])

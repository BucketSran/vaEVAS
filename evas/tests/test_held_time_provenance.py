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
    def test_source_root_delay_neighbours_and_later_callback(self):
        exact=F(1,3)+F(.1);times=around(exact)
        expected=[int(F(t)>=exact)+int(F(t)>=F(.6))for t in times]
        plain=execute(times=times);forced=execute(times=times,forced=True)
        self.assertEqual(output(plain),expected)
        self.assertEqual(plain['solutions'],forced['solutions'])
        self.assertEqual(plain['transient']['events'],forced['transient']['events'])
        dense=execute(times=sorted(set(times+[.1,.2,.4,.5,.7])))
        for time,row in zip(times,plain['solutions']):
            self.assertEqual(row,dense['solutions'][dense['transient']['times'].index(time)])
        self.assertEqual(plain['transient']['events'],dense['transient']['events'])

    def test_selected_sequential_copy_uses_new_local_time_value(self):
        exact=F(1,3)+F(.1)
        r=execute('due=$abstime;due=due+0.1;')
        self.assertEqual(output(r),[int(F(t)>=exact)+int(F(t)>=F(.6))for t in around(exact)])
        r=execute('due=$abstime+0.1;if(V(u,r)<0)due=V(u,r);')
        self.assertEqual(output(r),[int(F(t)>=exact)+int(F(t)>=F(.6))for t in around(exact)])

    def test_unknown_or_dynamic_rewrite_drops_old_proof(self):
        for action in ['due=$abstime+0.1;due=V(u,r)/3+0.1;',
                       'due=$abstime+0.1;due=$abstime+0.1*V(u,r);']:
            with self.subTest(action=action), self.assertRaises(KernelError) as caught:
                execute(action)
            self.assertEqual(caught.exception.detail['kind'],'event_resolution')
            self.assertIn('physical event phase',caught.exception.detail['message'])

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

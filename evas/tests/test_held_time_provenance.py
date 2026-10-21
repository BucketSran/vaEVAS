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

    def test_exact_source_offset_rewrite_replaces_old_time_proof(self):
        # Original source is u(t)=3*t and r is ground. The cross root is
        # exactly tau=1/3; u(tau)=1, hence the offset is binary64(.1)*1.
        exact = F(1, 3) + F(.1)
        times = around(exact)
        expected = [int(F(t) >= exact) + int(F(t) >= F(.6)) for t in times]
        for previous in ['0.1', '0.2']:
            action = 'due=$abstime+'+previous+';due=$abstime+0.1*V(u,r);'
            with self.subTest(previous=previous):
                plain = execute(action, times=times)
                forced = execute(action, times=times, forced=True)
                dense_times = sorted(set(times + [.1, .2, .4, .5, .7]))
                dense = execute(action, times=dense_times)
                self.assertEqual(output(plain), expected)
                self.assertEqual(plain['solutions'], forced['solutions'])
                self.assertEqual(plain['transient']['events'], forced['transient']['events'])
                self.assertEqual(plain['transient']['events'], dense['transient']['events'])
                y = plain['nodes'].index('y')
                bounds = plain['observation_evidence']['voltage_bounds_V']
                for time, row, want, boxes in zip(times, plain['solutions'], expected, bounds):
                    self.assertEqual(row, dense['solutions'][dense['transient']['times'].index(time)])
                    self.assertLessEqual(F(boxes[y][0]), F(want))
                    self.assertLessEqual(F(want), F(boxes[y][1]))
                # A stale .2 proof would schedule at tau+binary64(.2), so
                # both the neighbour outputs and original timer root catch it.
                events = plain['transient']['events']
                self.assertEqual(len(events), 3)
                timer = next(event for event in events if event['event'] == 1)
                self.assertIn('observation_time_bounds', timer)
                lo, hi = timer['observation_time_bounds']
                self.assertLessEqual(F(lo), exact)
                self.assertLessEqual(exact, F(hi))
                self.assertLess(F(hi), F(1, 3)+F(.2))

    def test_nonidentity_source_rewrite_drops_old_time_proof(self):
        # The source curve is 3*t, not the full identity curve. Its numeric
        # coincidence with time does not grant structural time provenance.
        with self.assertRaises(KernelError) as caught:
            execute('due=$abstime+0.1;due=V(u,r)/3+0.1;')
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
        self.assertIn('physical event phase', caught.exception.detail['message'])

    def test_unknown_internal_rewrite_drops_old_time_proof(self):
        # y is an unproved calculated voltage for the scalar Context. The old
        # due proof must be removed even though its nominal output is zero.
        with self.assertRaises(KernelError) as caught:
            execute('due=$abstime+0.2;due=$abstime+0.1*V(y,r);')
        self.assertEqual(caught.exception.detail['kind'], 'event_resolution')
        # With q=0, the rewritten nominal due is the current nonpoint cross
        # boundary. The uncertified internal read drops the old tau+.2 proof;
        # scheduling must reject this overlap before a later phase check.
        self.assertEqual(caught.exception.detail['message'],
                         'dynamic timer window overlaps the accepted boundary')

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

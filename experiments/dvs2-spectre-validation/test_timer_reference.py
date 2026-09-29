"""Synthetic controls, independent of EVAS and Spectre execution."""
from fractions import Fraction as Q
import unittest

import timer_reference as t


def fixture():
    case=dict(stop=4.0,ttol=0.1,maxstep=2.0,rate=1.0,reverse=False,pairs=[],
              inputs={'clock':[[0,0],[4,4]],'data':[[0,0.25],[4,8.25]]})
    p=t.probe('p',1.0,2.0); case['probes']=[p]
    # Hand anchors: events at 1.05 and 3.05, both within 0.1 of 1 and 3.
    rows=[dict(time=x,clock=x,data=0.25+2*x,count_p=n,stamp_p=h,sample_p=s)
          for x,n,h,s in [(0,0,-1,-3),(1.05,1,1.05,2.35),
                          (2,1,1.05,2.35),(3.05,2,3.05,6.35),(4,2,3.05,6.35)]]
    return case,p,rows


class TimerReferenceTests(unittest.TestCase):
    def check_history(self,rows,case,p):
        return t.history(rows,case,p,'count_p','stamp_p','sample_p')

    def test_independent_legal_shift_and_all_observations(self):
        c,p,rows=fixture()
        self.assertEqual(self.check_history(rows,c,p)['events_observed'],2)
        self.assertEqual(t.inspect(rows,c)['summary'],{'finite_consistent':1})

    def test_missing_duplicate_and_fractional_counts(self):
        for value in [0,2,1.2]:
            c,p,rows=fixture(); rows[2]['count_p']=value
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.check_history(rows,c,p)

    def test_wrong_phase_and_future_stamp(self):
        for stamp in [1.2,1.08]:
            c,p,rows=fixture(); rows[1]['stamp_p']=stamp
            rows[1]['sample_p']=0.25+2*stamp
            with self.subTest(stamp=stamp),self.assertRaises(ValueError):
                self.check_history(rows,c,p)

    def test_individually_legal_stamps_without_common_history_fail(self):
        c,p,rows=fixture(); rows[2]['stamp_p']=1.06; rows[2]['sample_p']=2.37
        with self.assertRaisesRegex(ValueError,'common event time'):
            self.check_history(rows,c,p)

    def test_sample_must_share_event_time_with_stamp(self):
        c,p,rows=fixture(); rows[1]['sample_p']=2.37
        with self.assertRaises(ValueError): self.check_history(rows,c,p)

    def test_initial_sentinel_and_missed_intermediate_history(self):
        c,p,rows=fixture(); rows[0]['sample_p']=0
        with self.assertRaises(ValueError): self.check_history(rows,c,p)
        c,p,rows=fixture()
        with self.assertRaises(ValueError): self.check_history([rows[0],*rows[3:]],c,p)

    def test_stop_window_is_not_clipped(self):
        c,p,rows=fixture(); c['stop']=1.0
        rows=[rows[0],dict(time=1,clock=1,data=2.25,count_p=0,stamp_p=-1,sample_p=-3)]
        self.assertEqual(self.check_history(rows,c,p)['pending_at_stop'],1)
        c['stop']=1.2; rows[-1]['time']=1.2
        with self.assertRaises(ValueError): self.check_history(rows,c,p)

    def test_timer_zero_accepts_post_initial_step_and_left_right_exports(self):
        c,p,rows=fixture(); p.update(start=0.0,period=0.0,initial=7)
        rows=[dict(time=0,count_p=7,stamp_p=-1,sample_p=-3),
              dict(time=0,count_p=8,stamp_p=0,sample_p=0.25),
              dict(time=4,count_p=8,stamp_p=0,sample_p=0.25)]
        self.assertEqual(self.check_history(rows,c,p)['events_observed'],1)

    def test_invalid_observations_do_not_pass(self):
        for mutation in [lambda rs:rs[1].pop('stamp_p'),
                         lambda rs:rs[1].update(stamp_p=float('nan')),
                         lambda rs:rs.pop(),lambda rs:rs[1].update(clock=3)]:
            c,p,rows=fixture(); mutation(rows)
            with self.assertRaises(ValueError): t.inspect(rows,c)

    def test_long_schedule_and_single_shot_variants(self):
        cases=t.specifications()
        self.assertEqual(len(cases),12)
        for c in cases:
            if c['family']=='long':
                events=t.nominal(c['probes'][0],c)
                self.assertEqual(len(events),2000)
                self.assertEqual(events[-1],Q(0.13e-6)+1999*Q(7e-9))
        c,p,_=fixture()
        for period in [0,-2]:
            p['period']=period; self.assertEqual(t.nominal(p,c),[Q(1)])
        p['enable']=0; self.assertEqual(t.nominal(p,c),[])

    def test_simultaneous_state_read_is_classified_not_assumed(self):
        c=dict(stop=2,ttol=0.1,maxstep=2,rate=1,reverse=False,probes=[],
               inputs={'clock':[[0,0],[2,2]],'data':[[0,0.25],[2,4.25]]},
               pairs=[dict(id='same',kind='timer',start=1,receive=1,expected_read=0)])
        for value,status in [(0,'candidate_consistent'),(1,'candidate_differs'),(2,'finite_inconsistent')]:
            rows=[dict(time=0,clock=0,data=0.25,count_same=0,stamp_same=-1,
                       received_same=0,rstamp_same=-1,sample_same=-1),
                  dict(time=2,clock=2,data=4.25,count_same=1,stamp_same=1,
                       received_same=1,rstamp_same=1,sample_same=value)]
            self.assertEqual(t.inspect(rows,c)['records'][0]['status'],status)

    def test_cross_window_is_one_sided(self):
        c,p,rows=fixture(); rows[1].update(time=0.95,stamp_p=0.95,sample_p=2.15)
        rows[2].update(stamp_p=0.95,sample_p=2.15)
        self.assertEqual(self.check_history(rows,c,p)['status'],'finite_consistent')
        with self.assertRaises(ValueError):
            t.history(rows,c,p,'count_p','stamp_p','sample_p',cross=True)

    def test_isolation_retains_every_original_probe_and_parameter(self):
        followup=t.isolation_specifications()
        self.assertEqual(len(followup),12)
        for c in t.specifications():
            if c['family']!='ordinary': continue
            group=[x for x in followup if x['id'].startswith(c['id']+'-')]
            self.assertEqual([p for x in group for p in x['probes']],c['probes'])
            self.assertEqual(sorted((p for x in group for p in x['pairs']),key=lambda x:x['id']),
                             sorted(c['pairs'],key=lambda x:x['id']))
            for x in group:
                for key in ['stop','ttol','maxstep','output_times','reverse']:
                    self.assertEqual(x[key],c[key])

    def test_pwl_endpoint_hold_preserves_raw_timestamp_and_strict_gates(self):
        import math
        c=next(c for c in t.specifications() if c['id']=='endpoint-at-coarse')
        c['maxstep']=2*c['stop']
        rows=[dict(time=0,clock=0,data=0.25,count_endpoint=0,stamp_endpoint=-1,sample_endpoint=-3),
              dict(time=math.nextafter(c['stop'],math.inf),clock=16,data=32.25,
                   count_endpoint=1,stamp_endpoint=16,sample_endpoint=32.25)]
        exported=rows[-1]['time']
        self.assertEqual(t.inspect(rows,c)['records'][0]['status'],'finite_consistent')
        self.assertEqual(rows[-1]['time'],exported)
        rows[-1]['clock']+=1e-4
        with self.assertRaisesRegex(ValueError,'input mismatch'): t.inspect(rows,c)
        rows[-1]['clock']=16; rows[-1]['time']=c['stop']+1e-17
        with self.assertRaisesRegex(ValueError,'incomplete time coverage'): t.inspect(rows,c)


if __name__=='__main__': unittest.main()

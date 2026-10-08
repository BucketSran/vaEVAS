"""Independent worked PWL/area fixtures and deliberate observable faults."""
import copy
import json
import math
from pathlib import Path
import unittest

from checker import inspect

ROOT=Path(__file__).parent
IDS=('T1','T2','C1','C2','M1','H1','N1')


def card(ident):return json.loads((ROOT/ident/'case.json').read_text())


def linear(t,knots):
    if t<=knots[0][0]:return knots[0][1]
    for (a,v),(b,w) in zip(knots,knots[1:]):
        if t<=b:return v+(w-v)*(t-a)/(b-a)
    return knots[-1][1]


def worked_rows(c,shift=0.0):
    """Worked solutions, without importing the checker's reference function."""
    ident=c['id'];U=c['criteria']['unit_s'];delta=shift/U
    stamps={e['stamp_node']:e['nominal_time_s']/U+delta for e in c['criteria']['events']}
    rows=[]
    for time in c['times']:
        t=time/U
        h1=stamps.get('h1',-1);h2=stamps.get('h2',-1);h3=stamps.get('h3',-1)
        hit=lambda x:x>=0 and t>=x
        v=dict(y=0.,z=0.,q=0.,n=0.,m=0.,s=0.,h1=h1 if hit(h1) else -1.,
               h2=h2 if hit(h2) else -1.,h3=h3 if hit(h3) else -1.)
        if ident in ('T1','M1'):
            v.update(n=float(hit(h1)),m=float(hit(h2)),q=float(hit(h1) and not hit(h2)))
            v['y']=linear(t,[(0,0),(h1+.25,0),(h1+1.25,1),(h2+.25,1),(h2+2.25,0),(10,0)])
            if ident=='M1':v['z']=linear(t,[(0,0),(h1,0),(h2,h2-h1),(10,h2-h1)])
        elif ident=='T2':
            v.update(n=float(hit(h1)),m=float(hit(h2)),q=float(hit(h1) and not hit(h2)))
            height=h2-h1
            v['y']=linear(t,[(0,0),(h1+2,0),(h2+2,height),(h2+2+height,0),(8,0)])
        elif ident=='C1':
            v['n']=float(hit(h1));v['s']=v['q']=h1/2 if hit(h1) else 0
            v['y']=linear(t,[(0,0),(h1+.25,0),(h1+1.25,h1/2),(6,h1/2)])
        elif ident=='C2':
            sample=(h2-h1)/10
            v.update(n=float(hit(h1)),m=float(hit(h2)),q=float(hit(h1) and not hit(h2)),s=sample if hit(h2) else 0)
            v['y']=linear(t,[(0,0),(h1,0),(h2,sample),(h2+20*sample,0),(18,0)])
        elif ident=='H1':
            v.update(n=float(hit(h2)),q=float(not hit(h3)),s=4 if hit(h1) else 6,y=float(hit(h2)))
        elif ident=='N1':
            v.update(n=float(hit(h1)),m=float(hit(h2)),q=float(hit(h3)),s=h2 if hit(h2) else 0)
            v['y']=v['n']+10*v['m']+100*v['q']
        rows.append(dict(time=time,voltages=v))
    return rows


class CheckerCalibration(unittest.TestCase):
    def assert_rejected(self,c,rows,reason):
        result=inspect(c,rows)
        self.assertEqual(result['status'],'F',result)
        self.assertTrue(any(reason in f for f in result['failures']),result)

    def test_seven_independent_worked_positive_fixtures(self):
        for ident in IDS:
            with self.subTest(ident=ident):
                c=card(ident);result=inspect(c,worked_rows(c))
                self.assertEqual(result['status'],'P',result)

    def test_one_permitted_event_shift_is_shared_by_all_consumers(self):
        c=card('M1');result=inspect(c,worked_rows(c,shift=5e-13))
        self.assertEqual(result['status'],'P',result)
        self.assertTrue(all(e['nominal_displacement_s']>0 for e in result['events']))

    def test_downstream_edge_cannot_choose_another_event_time(self):
        c=card('M1');rows=worked_rows(c)
        for row in rows:
            if 2.3e-6<row['time']<3.2e-6:row['voltages']['y']-=4e-6
        self.assert_rejected(c,rows,'output y')

    def test_integral_area_cannot_choose_another_event_time(self):
        c=card('M1');rows=worked_rows(c)
        for row in rows:
            if row['time']>2.1e-6:row['voltages']['z']+=4e-6
        self.assert_rejected(c,rows,'output z')

    def test_cross_sample_is_not_an_independently_fitted_target(self):
        c=card('C1');rows=worked_rows(c)
        for row in rows:
            if row['time']>1.5e-6:row['voltages']['s']+=2e-6
        self.assert_rejected(c,rows,'output s')

    def test_interruption_sample_is_checked_against_retained_edge(self):
        c=card('C2');rows=worked_rows(c)
        for row in rows:
            if row['time']>6.1e-6:row['voltages']['s']=.5
        self.assert_rejected(c,rows,'output s')

    def test_dropped_pulse_fails_even_with_correct_final_zero(self):
        c=card('T2');rows=worked_rows(c)
        for row in rows:row['voltages']['y']=0
        self.assert_rejected(c,rows,'output y')

    def test_cancelled_held_root_cannot_still_increment(self):
        c=card('H1');rows=worked_rows(c)
        for row in rows:
            if row['time']>=7e-6:row['voltages']['m']=1
        self.assert_rejected(c,rows,'wrong final source count')

    def test_old_rescheduled_root_is_not_hidden_by_final_count(self):
        c=card('H1');rows=worked_rows(c)
        for row in rows:
            if 4.1e-6<row['time']<5.9e-6:
                row['voltages']['n']=0;row['voltages']['y']=0
        self.assert_rejected(c,rows,'output n')

    def test_near_sources_must_each_be_observed(self):
        c=card('N1');rows=worked_rows(c)
        for row in rows:
            if row['time']>2.1e-6:row['voltages']['m']=0
        self.assert_rejected(c,rows,'wrong final source count')

    def test_stamp_outside_window_fails(self):
        c=card('T1');rows=worked_rows(c)
        rows[-1]['voltages']['h1']+=.01
        self.assert_rejected(c,rows,'outside nominal window')

    def test_stamp_must_remain_held(self):
        c=card('T1');rows=worked_rows(c)
        rows[len(rows)//2]['voltages']['h1']+=.01
        self.assert_rejected(c,rows,'unique held event phase')

    def test_shared_boundary_can_use_the_common_pre_event_state(self):
        c=card('T1');rows=worked_rows(c)
        row=next(r for r in rows if r['time']==2e-6)
        row['voltages'].update(n=0,q=0,h1=-1)
        self.assertEqual(inspect(c,rows)['status'],'P')

    def test_boundary_consumers_cannot_choose_conflicting_phases(self):
        c=card('T1');rows=worked_rows(c)
        row=next(r for r in rows if r['time']==2e-6)
        row['voltages']['n']=0
        self.assert_rejected(c,rows,'inconsistent shared event phase')

    def test_boundary_rows_cannot_refit_the_event_time_independently(self):
        c=card('T1');rows=worked_rows(c)
        template=next(r for r in rows if r['time']==2e-6)
        early=copy.deepcopy(template);early['time']=2e-6-5e-14
        late=copy.deepcopy(template);late['time']=2e-6+5e-14
        late['voltages'].update(n=0,q=0,h1=-1)
        rows.extend([early,late]);rows.sort(key=lambda row:row['time'])
        self.assert_rejected(c,rows,'no single event time')

    def test_missing_common_point_fails(self):
        c=card('T1');rows=worked_rows(c);del rows[len(rows)//2]
        self.assert_rejected(c,rows,'missing')

    def test_missing_output_and_nonfinite_fail(self):
        c=card('T1');rows=worked_rows(c);del rows[0]['voltages']['z']
        self.assert_rejected(c,rows,'missing normalized')
        rows=worked_rows(c);rows[-1]['voltages']['z']=math.nan
        self.assert_rejected(c,rows,'nonfinite')

    def test_incomplete_run_and_rejection_are_not_success(self):
        c=card('T1');self.assert_rejected(c,worked_rows(c)[:-3],'cover')
        self.assert_rejected(c,[],'no complete successful waveform')

    def test_decimal_export_last_bit_is_not_exact_stop_failure(self):
        c=card('T1');rows=worked_rows(c)
        rows[-1]['time']=math.nextafter(rows[-1]['time'],-math.inf)
        tokens=[dict(time=str(row['time']),voltages={k:str(v) for k,v in row['voltages'].items()}) for row in rows]
        result=inspect(c,rows,tokens)
        self.assertEqual(result['status'],'P',result)


if __name__=='__main__':unittest.main()

"""Independent event waveform calibration from hand-worked output knots.

Input points are the frozen experiment specification. Output knots are explicit
analytic answers from the case cards; no production reference, history builder,
root finder, or simulator supplies them. Time below is measured in microseconds.
"""
from fractions import Fraction as Q
import math
import unittest
from unittest.mock import patch
from run_suite import conditions
from check_results import check

CASES = {c['id']:c for c in conditions()}
# vin=.8-.1*t; reset rises through .5 at 2.15; edge duration .025.
SAMPLED = [('0','.1'),('.5','.1'),('.525','.75'),('1.5','.75'),('1.525','.65'),
           ('2.15','.65'),('2.175','.1'),('3.5','.1'),('3.525','.45'),('4','.45')]
RESET_HIGH = [('0','.1'),('1.5','.1'),('1.525','.65'),('2.15','.65'),('2.175','.1'),
              ('3.5','.1'),('3.525','.45'),('4','.45')]
NO_RESET = [('0','.1'),('.5','.1'),('.525','.75'),('1.5','.75'),('1.525','.65'),
            ('2.5','.65'),('2.525','.55'),('3.5','.55'),('3.525','.45'),('4','.45')]
# Independent second instance: vin=.2+.1*t, initial .3, edge duration .04.
SECOND = [('0','.3'),('.75','.3'),('.79','.275'),('1.75','.275'),('1.79','.375'),
          ('2.75','.375'),('2.79','.475'),('3.75','.475'),('3.79','.575'),('4','.575')]


def output_knots(name):
    if name.startswith('e1-'):
        delta = Q(37,1000000) if name=='e1-shifted' else Q(0)
        # Independent integer counters scaled by .1, each with a .01 edge.
        return {
            'up':[(Q(0),Q(0)),(Q('.5')+delta,Q(0)),(Q('.51')+delta,Q('.1')),
                  (Q('2.5')+delta,Q('.1')),(Q('2.51')+delta,Q('.2')),(Q(3),Q('.2'))],
            'down':[(Q(0),Q(0)),(Q('1.5')+delta,Q(0)),(Q('1.51')+delta,Q('.1')),(Q(3),Q('.1'))],
        }
    convert = lambda table:[(Q(t),Q(v)) for t,v in table]
    if name.startswith('e2-'):
        return {'vout':convert(RESET_HIGH if name=='e2-reset-high' else SAMPLED)}
    return {'outa':convert(NO_RESET if name=='c1-no-reset-a' else SAMPLED), 'outb':convert(SECOND)}


def interpolate(points, x):
    for (a,u),(b,v) in zip(points,points[1:]):
        if x<=b:
            return u+(v-u)*(x-a)/(b-a)
    return points[-1][1]


def rational_rows(name):
    case=CASES[name]
    tables={n:[(Q(str(t)),Q(str(v))) for t,v in points] for n,points in case['inputs'].items()}
    tables.update(output_knots(name))
    return [dict(time=float(Q(i,1000000000)), **{n:float(interpolate(points,Q(i,1000)))
            for n,points in tables.items()}) for i in range(int(case['stop_x']*1000)+1)]


class IndependentEventReview(unittest.TestCase):
    def test_hand_worked_positive_controls(self):
        for name in CASES:
            if name.startswith(('e1-','e2-','c1-')):
                with self.subTest(name=name):
                    self.assertEqual(check(rational_rows(name),CASES[name])['status'],'observations_within_targets')

    def test_fixture_has_no_production_oracle_dependency(self):
        with patch('check_results.reference',side_effect=AssertionError('shared oracle')), \
             patch('check_results.histories',side_effect=AssertionError('shared history')), \
             patch('check_results.v1.pwl',side_effect=AssertionError('shared PWL')):
            self.assertEqual(len(rational_rows('e2-low')),4001)
            self.assertEqual(rational_rows('e2-low')[1000]['vout'],.75)
            self.assertEqual(rational_rows('c1-main')[1000]['outb'],.275)

    def test_missing_first_sample_is_rejected(self):
        data=rational_rows('e2-low')
        for row in data:
            if row['time']<1.5e-6:row['vout']=.1
        self.assertEqual(check(data,CASES['e2-low'])['status'],'observed_violation')

    def test_missing_duplicate_and_wrong_direction_counts_are_rejected(self):
        for fault in ['missing','duplicate','wrong_direction']:
            with self.subTest(fault=fault):
                data=rational_rows('e1-aligned')
                for row in data:
                    if fault=='missing' and row['time']>=2.51e-6:row['up']=.1
                    elif fault=='duplicate' and row['time']>=.51e-6:row['up']+=.1
                    elif fault=='wrong_direction':row['up'],row['down']=row['down'],row['up']
                self.assertEqual(check(data,CASES['e1-aligned'])['status'],'observed_violation')

    def test_high_initial_clock_does_not_justify_initial_sample(self):
        data=rational_rows('e2-clock-high')
        for row in data:
            if row['time']<.5e-6:row['vout']=.8
        self.assertEqual(check(data,CASES['e2-clock-high'])['status'],'observed_violation')

    def test_reset_priority_and_extra_release_sample_are_rejected(self):
        for fault in ['sample_during_reset','sample_on_release']:
            with self.subTest(fault=fault):
                data=rational_rows('e2-low')
                for row in data:
                    if fault=='sample_during_reset' and 2.525e-6<=row['time']<3.5e-6:row['vout']=.55
                    if fault=='sample_on_release' and 2.9e-6<=row['time']<3.5e-6:row['vout']=.515
                self.assertEqual(check(data,CASES['e2-low'])['status'],'observed_violation')

    def test_instance_crosstalk_and_extra_effective_update_are_rejected(self):
        data=rational_rows('c1-main')
        for row in data:row['outa'],row['outb']=row['outb'],row['outa']
        self.assertEqual(check(data,CASES['c1-main'])['status'],'observed_violation')
        data=rational_rows('e2-low')
        for row in data:
            if .6e-6<=row['time']<1.5e-6:row['vout']=.9
        self.assertEqual(check(data,CASES['e2-low'])['status'],'observed_violation')

    def test_tolerance_margins_on_plateaus(self):
        for magnitude,expected in [(.0009,'observations_within_targets'),(.0011,'observed_violation')]:
            for sign in [-1,1]:
                with self.subTest(offset=sign*magnitude):
                    data=rational_rows('e2-low')
                    for row in data:row['vout']+=sign*magnitude
                    self.assertEqual(check(data,CASES['e2-low'])['status'],expected)

    def test_invalid_observations_stay_invalid(self):
        for fault in ['missing_output','missing_input','nan','infinity','duplicate_time','wrong_time_unit','missing_tail']:
            with self.subTest(fault=fault):
                data=rational_rows('e2-low')
                if fault=='missing_output':data[100].pop('vout')
                elif fault=='missing_input':data[100].pop('vin')
                elif fault=='nan':data[100]['vout']=math.nan
                elif fault=='infinity':data[100]['vin']=math.inf
                elif fault=='duplicate_time':data[100]['time']=data[99]['time']
                elif fault=='wrong_time_unit':
                    for row in data:row['time']*=1000000
                else:data.pop()
                self.assertEqual(check(data,CASES['e2-low'])['status'],'observation_invalid')


if __name__=='__main__':unittest.main()

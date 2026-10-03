"""Calibration controls for the separate cross comparison (no simulator calls)."""
import copy
from fractions import Fraction as Q
import unittest

from cross_reference import STOP, cases, check, pwl


def observations(case):
    roots=[Q(r['time']) for r in case['roots']]
    rows=[]
    for t in case['output_times']:
        n=sum(Q(t) >= root for root in roots)
        stamp=roots[n-1]*Q(3)/Q(STOP) if n else 0
        rows.append(dict(time=t,u=float(pwl(case['inputs']['u'],Q(t))),
                         clock=float(Q(t)*Q(3)/Q(STOP)),y=n,stamp=float(stamp)))
    return rows


class CrossReferenceCalibration(unittest.TestCase):
    def test_hand_anchors_and_nominal_observations(self):
        specs=cases()
        self.assertEqual(len(specs),8)
        self.assertEqual([len(c['roots']) for c in specs],[3,2,3,2,2,3,3,3])
        for actual,expected in zip(specs[0]['roots'],[.5e-6,1.5e-6,2.5e-6]):
            self.assertAlmostEqual(float(Q(actual['time'])),expected,delta=1e-20)
        for case in specs:
            with self.subTest(case=case['id']):
                self.assertEqual(check(observations(case),case)['status'],'finite_observation_pass')

    def test_known_legal_delays_are_accepted(self):
        case=cases()[0]
        rows=observations(case)
        for row in rows:
            if row['y']:
                row['stamp']+=float(Q(case['roots'][row['y']-1]['width'])*Q(3)/Q(STOP)/2)
        check(rows,case)

    def test_shared_wrong_backend_results_cannot_pass(self):
        case=cases()[0]
        for fault in ['early','late','missing','double','input','changing_hold']:
            rows=observations(case)
            if fault == 'early': rows[2]['stamp']-=.01
            if fault == 'late': rows[2]['stamp']+=.01
            if fault == 'missing': rows[2]['y']=0
            if fault == 'double': rows[2]['y']=2
            if fault == 'input': rows[2]['u']+=.01
            if fault == 'changing_hold': rows[3]['stamp']+=.001
            # Identical faulty observations for both backends still fail.
            for backend in ['evas','spectre']:
                with self.subTest(fault=fault,backend=backend),self.assertRaises(ValueError):
                    check(copy.deepcopy(rows),case)

    def test_invalid_observations_are_rejected(self):
        case=cases()[0]
        for fault in ['empty','truncated','nan','reordered','missing_signal']:
            rows=observations(case)
            if fault == 'empty': rows=[]
            if fault == 'truncated': rows.pop()
            if fault == 'nan': rows[2]['stamp']=float('nan')
            if fault == 'reordered': rows[2],rows[3]=rows[3],rows[2]
            if fault == 'missing_signal': rows[2].pop('clock')
            with self.subTest(fault=fault),self.assertRaises(ValueError):
                check(rows,case)

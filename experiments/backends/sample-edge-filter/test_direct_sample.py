"""Independent calibration of the direct-sample finite engineering checks."""
import math
import unittest
from direct_sample import assess, check_events

BUDGETS=dict(absolute_V=1e-8,relative=1e-6,input_absolute_V=1e-10,input_relative=1e-8,
             count_V=1e-6,global_gap_units=.0625,time_serialization_ulps=16,
             voltage_serialization_ulps=8,boundary_distance_s=2.1e-12)


def fixture(scale=1.):
    t=math.sqrt(2);times=sorted({i/32 for i in range(97)}|{t-1e-12,t+1e-12})
    case=dict(scale=scale,scale_V=2*abs(scale),root=t,stop=3,ttol_s=1e-3,expr_tol=1e-3)
    # Hand-constructed ideal sample plus observable native before/after counter.
    rows=[dict(time=x,clk=x,u=scale*x,y=scale*math.sqrt(2) if x>t else 0.,count=int(x>t)) for x in times]
    return case,rows


class Calibration(unittest.TestCase):
    def test_explicit_event_representative_is_separate_and_legal(self):
        case,_=fixture()
        check_events(case,[dict(kind='cross',time=case['root']+1e-10)],BUDGETS)
        for events in ([],[dict(kind='cross',time=1.3)],[dict(kind='cross',time=1.5)],
                       [dict(kind='cross',time=float('nan'))]):
            with self.assertRaises(ValueError):check_events(case,events,BUDGETS)

    def test_positive_negative_and_small_answers(self):
        for scale in (1.,-1.,.001):
            case,rows=fixture(scale)
            self.assertEqual(assess(case,rows,BUDGETS)['status'],'pass')

    def test_voltage_bias_and_hold_drift_fail(self):
        case,rows=fixture()
        for row in rows:
            if row['count']:row['y']+=1e-4
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'numerical_error')
        case,rows=fixture();rows[-1]['y']+=1e-4
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'numerical_error')

    def test_missing_repeated_or_fractional_events_fail(self):
        for value in (0,2,.5):
            case,rows=fixture();rows[-1]['count']=value
            self.assertEqual(assess(case,rows,BUDGETS)['status'],'behavior_error')

    def test_early_event_and_wrong_input_fail(self):
        case,rows=fixture()
        for row in rows:
            if row['time']>1.3:row.update(count=1,y=math.sqrt(2))
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'behavior_error')
        case,rows=fixture();rows[5]['u']+=1e-4
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'input_mismatch')

    def test_missing_boundary_and_nonfinite_are_inconclusive(self):
        case,rows=fixture()
        rows=[r for r in rows if abs(r['time']-math.sqrt(2))>1e-6]
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'evidence_insufficient')
        case,rows=fixture();rows[5]['y']=float('nan')
        self.assertEqual(assess(case,rows,BUDGETS)['status'],'evidence_insufficient')


if __name__=='__main__':unittest.main()

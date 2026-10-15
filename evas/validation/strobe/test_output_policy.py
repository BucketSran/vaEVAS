import copy
import math
import unittest
from output_policy import check


class OutputPolicyCalibration(unittest.TestCase):
    def test_exact_forced_terminal_and_window_contract(self):
        rows=[dict(time=t,u=0.,y=0.) for t in [0.,.125,.625,1.]]
        check(rows[1:],policy='strobeonly',forced=[.125,.625])
        for invalid in (rows[1:-1],rows,rows[1:]+[rows[-1]],
                        [dict(time=math.nextafter(.125,math.inf),u=0.,y=0.),*rows[2:]]):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                check(invalid,policy='strobeonly',forced=[.125,.625])

    def test_period_window_outside_rows_and_wrong_analytic_value(self):
        rows=[dict(time=0.,u=0.,y=0.),dict(time=.325,u=.6,y=1.8),
              dict(time=.575,u=0.,y=0.),dict(time=1.,u=0.,y=0.)]
        args=dict(policy='strobeonly',forced=[.325,.575],window=[.2,.8],ordinary_times=[0.,.25,.375,.4375,.5,.75,1.])
        check(rows,**args)
        for change in ('outside','inside','voltage','nan'):
            invalid=copy.deepcopy(rows)
            if change=='outside': invalid=invalid[1:]
            if change=='inside': invalid.insert(2,dict(time=.375,u=1.,y=3.))
            if change=='voltage': invalid[1]['y']=0.
            if change=='nan': invalid[1]['u']=math.nan
            with self.subTest(change=change),self.assertRaises(ValueError):
                check(invalid,**args)

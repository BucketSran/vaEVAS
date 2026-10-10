import copy
import unittest
from timer_composition import INTEGRAL, integral_value, assess, sef


class TimerIntegralCalibration(unittest.TestCase):
    def test_rectangle_areas(self):
        self.assertAlmostEqual(integral_value(1e-6),.3)
        self.assertAlmostEqual(integral_value(2e-6),1.05)
        self.assertAlmostEqual(integral_value(2.5e-6),1.10)

    def test_accept_and_reject_history_errors(self):
        # Analytic data includes both sides of all timer/PWL boundaries.
        ts={i*sef.T/32 for i in range(273)}
        for k in range(1,9):ts.update(k*sef.T+d for d in (-2e-12,0,2e-12))
        rows=[]
        for t in sorted(ts):
            n=min(8,int(t/sef.T))
            rows.append(dict(time=t,u=float(sef.pwl(sef.INPUT,min(8.5,t/sef.T))),
                             y=.25 if n==0 else float(sef.pwl(sef.INPUT,n)),count=n,i=integral_value(t)))
        self.assertEqual(assess(INTEGRAL,rows)['status'],'pass')
        for mutation in ('reset','slope','missing_event','tail','nan'):
            bad=copy.deepcopy(rows)
            if mutation=='tail':bad=bad[:-5]
            elif mutation=='nan':bad[-1]['i']=float('nan')
            else:
                for r in bad:
                    if mutation=='reset':r['i']=.05+r['y']*(r['time']/sef.T-r['count'])
                    if mutation=='slope':r['i']=.05+.25*r['time']/sef.T
                    if mutation=='missing_event':r['count']=0
            with self.subTest(mutation=mutation):self.assertNotEqual(assess(INTEGRAL,bad)['status'],'pass')


if __name__=='__main__':unittest.main()

import copy
import math
import unittest
from contract import CASES,INPUT,CLOCK,RESET,T,callbacks,initial,times,pwl,edge_value,filter_value,assess


def analytical_rows(case):
    rows=[]
    for t in times(case,True):
        x=t/T
        row=dict(time=t,**{n:float(pwl(points,min(8.5,x))) for n,points in [('u',INPUT),('clk',CLOCK),('rst',RESET)]})
        for p in case['instances']:
            events=[(e,q) for e,q in callbacks(p) if float(e)*T<=t]
            row.update({p['name']+'n':len(events),p['name']+'h':float(events[-1][1] if events else initial(p)),p['name']+'e':edge_value(p,x),p['name']+'f':filter_value(p,x)})
        rows.append(row)
    return rows


class ContractCalibration(unittest.TestCase):
    def test_closed_form_ramp_anchor(self):
        # First timer sample changes .25 to .75; ramp .5 us, tau .5 us.
        p=CASES[0]['instances'][0]
        self.assertAlmostEqual(edge_value(p,1.375),.5,places=14)
        self.assertAlmostEqual(filter_value(p,1.625),.25+.5*math.exp(-1),places=14)

    def test_accepts_independent_analytical_histories(self):
        for c in CASES:
            with self.subTest(case=c['id']):
                report=assess(c,analytical_rows(c));self.assertEqual(report['status'],'PASS',report)

    def test_rejects_history_reset_missing_events_input_drift_and_nonfinite(self):
        c=CASES[0];correct=analytical_rows(c)
        for mutation in ['filter_reset','missing_event','wrong_input','nonfinite','input_nan','time_nan','missing_port','missing_tail','time_order']:
            rows=copy.deepcopy(correct)
            if mutation=='filter_reset':
                for r in rows:r['af']=r['ae']
            elif mutation=='missing_event':
                for r in rows:r['an']=0
            elif mutation=='wrong_input':rows[20]['u']+=.001
            elif mutation=='nonfinite':rows[20]['af']=math.nan
            elif mutation=='input_nan':rows[20]['u']=math.nan
            elif mutation=='time_nan':rows[20]['time']=math.nan
            elif mutation=='missing_port':del rows[20]['an']
            elif mutation=='missing_tail':rows=rows[:-30]
            else:rows[20]['time']=rows[19]['time']
            with self.subTest(mutation=mutation):self.assertEqual(assess(c,rows)['status'],'FAIL')

if __name__=='__main__':unittest.main()

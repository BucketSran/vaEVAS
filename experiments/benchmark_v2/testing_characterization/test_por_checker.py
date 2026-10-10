"""Independent POR wave seams: actual stimulus and count history must matter."""
from pathlib import Path
import importlib.util
import unittest
spec=importlib.util.spec_from_file_location('testing',Path(__file__).resolve().parents[3]/'benchmark/checkers/v2_testing.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FullPorWave(unittest.TestCase):
    def fixture(self,missing_recovery=False,slow=False,late_first=False):
        period=60e-6 if slow else 30e-6
        dip=.00305 if late_first else .00234 if slow else .0021;low=dip+.0001;rec=low+.0001;high=rec+.0001
        first=[(.00258999 if late_first else .00152)+i*period for i in range(13)]
        second=[rec+.00008+i*period for i in range(13)]
        rise=[first[5]+1e-8]+([] if missing_recovery else [second[5]+1e-8])
        fall=[first[12]+1e-8]+([] if missing_recovery else [second[12]+1e-8])
        finish=high+.001 if missing_recovery else round((fall[1]+.0001)/1e-6+.499999)*1e-6
        events=first+second+rise+fall+[.0015,dip+.00005,rec+.00006,finish]
        times={0.,.004,*[i*1e-6 for i in range(4001)]}
        for t in events+ [t+5e-6 for t in first+second]: times.update([t-1e-9,t+1e-9])
        def pulse(t,starts,ends): return 1.8*int(any(a<=t<b for a,b in zip(starts,ends)))
        rows=[]
        for t in sorted(times):
            if t<dip: avdd=3.3*min(t/.002,1)
            elif t<low: avdd=3.3-1.3*(t-dip)/.0001
            elif t<rec: avdd=2.
            elif t<high: avdd=2+1.3*(t-rec)/.0001
            else: avdd=3.3
            r=dict(time=t,avdd=avdd,power=pulse(t,[.0015,rec+.00006],[dip+.00005,.0041]),osc=pulse(t,first+second,[x+5e-6 for x in first+second]),por=pulse(t,rise,fall),done=float(t>=finish))
            for prefix in ['first','recovery']:
                active=t>=finish and (prefix=='first' or not missing_recovery)
                r.update({prefix+'_response_us':(5*period*1e6+.01) if active else 0.,prefix+'_period_us':period*1e6 if active else 0.,prefix+'_width_us':7*period*1e6 if active else 0.,prefix+'_valid':float(active),prefix+'_ok':float(active)})
            rows.append(r)
        return rows,dict(kind='por_bench',stop=.004,guard=5e-6,atol=.1,supply_atol=.03)
    def test_correct_bad_dut_measurement(self):
        for missing in [False,True]:
            rows,case=self.fixture(missing)
            result=m.evaluate(rows,case)
            self.assertTrue(result['passed'],result)
    def test_omitting_actual_undervoltage_fails(self):
        rows,case=self.fixture()
        for r in rows:
            if r['time']>=.002: r['avdd']=3.3
        self.assertFalse(m.evaluate(rows,case)['passed'])
    def test_dip_waits_for_slower_actual_completion(self):
        rows,case=self.fixture(slow=True)
        self.assertTrue(m.evaluate(rows,case)['passed'])
        # Keep all observed DUT reports, but substitute an unconditional 2.1ms dip.
        for r in rows:
            t=r['time']
            if .0021<=t<.0022: r['avdd']=3.3-1.3*(t-.0021)/.0001
            elif .0022<=t<.0023: r['avdd']=2.
            elif .0023<=t<.0024: r['avdd']=2+1.3*(t-.0023)/.0001
            elif t>=.0024: r['avdd']=3.3
        self.assertFalse(m.evaluate(rows,case)['passed'])
    def test_near_timeout_first_fall_requires_full_hold(self):
        rows,case=self.fixture(late_first=True)
        self.assertTrue(m.evaluate(rows,case)['passed'])
        for r in rows:
            t=r['time']
            if .003<=t<.0031: r['avdd']=3.3-1.3*(t-.003)/.0001
            elif .0031<=t<.0032: r['avdd']=2.
            elif .0032<=t<.0033: r['avdd']=2+1.3*(t-.0032)/.0001
            elif t>=.0033: r['avdd']=3.3
        self.assertFalse(m.evaluate(rows,case)['passed'])
    def test_success_report_cannot_hide_missing_recovery(self):
        rows,case=self.fixture(True)
        for r in rows:
            if r['done']: r['recovery_ok']=1.
        self.assertFalse(m.evaluate(rows,case)['passed'])

if __name__=='__main__': unittest.main()

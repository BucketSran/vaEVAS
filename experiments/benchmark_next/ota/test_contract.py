"""Public waveform seam tests. Literal expectations follow worked contracts."""
import sys,unittest,json,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'benchmark/checkers'))
from v2_next_ota import propagate, measured, evaluate, measure_verdict
import bisect
class ContinuousContract(unittest.TestCase):
    def test_slew_then_exponential(self):
        # target .75, y0=0, tau 20 ns, +slew .01 V/ns.
        # Linear region finishes at 55 ns at .55 V. At 75 ns one tau elapsed.
        self.assertAlmostEqual(propagate(0,.75,75e-9,20e-9,1e7,6e6),.75-.2/2.718281828459045,12)
    def test_late_band_exit_invalidates_first_entry(self):
        # Last sample exits the 3 mV band. The report must be timeout.
        values=[.5]*180; values[-1]=.51
        metric=measured(.4,.5,.4,values)
        self.assertEqual(metric['status'],2)
        self.assertEqual(metric['valid'],0)
    def test_source_truth_identity_cannot_be_changed(self):
        root=Path(__file__).resolve().parents[3]
        case=json.loads((root/'benchmark/tasks/v3-ota-data-model/tests/cases.json').read_text())[0]
        rows=[dict(time=0.,vin=.75,enable=0.,vout=0.),dict(time=case['stop'],vin=.75,enable=1.5,vout=.75)]
        case['resolution']=case['stop']
        case['truth'][100][1]+=.00001
        with self.assertRaisesRegex(ValueError,'source observation identity'):
            evaluate(rows,case,root)
    def test_measurement_rejects_disabled_between_report_checkpoints(self):
        steps=[200e-9,400e-9,600e-9,800e-9,1000e-9,1200e-9]
        levels=[.75,.8,.7,1.2,.3,1.6,.75]
        rows=[]
        for k in range(5601):
            t=k*.25e-9; ix=bisect.bisect_right(steps,t)
            active=ix>0 and t<steps[ix-1]+180e-9
            direction=0 if ix==0 else (1 if levels[ix]>levels[ix-1] else -1)
            rows.append(dict(time=t,vin=levels[ix],enable=0 if t<10e-9 else 1.5,
                             launch=int(active),vout=.75,gain=0,slew_metric=0,
                             settle=1 if ix else 0,valid=int(ix>0 and not active),
                             status=1 if ix>0 and not active else 0,direction=direction))
        times=[r['time'] for r in rows]
        def at(t,n):
            j=max(0,min(len(rows)-2,bisect.bisect_right(times,t)-1));a,b=rows[j:j+2]
            return a[n]+(b[n]-a[n])*(t-a['time'])/(b['time']-a['time'])
        case={'stop':1.4e-6}
        self.assertTrue(measure_verdict(case,at,rows)['passed'])
        rows[1200]['enable']=0  # 300 ns: far from the old 201/202/385 ns checks.
        result=measure_verdict(case,at,rows)
        self.assertFalse(result['passed'])
        self.assertEqual(result['stimulus_failure_count'],1)
        rows[1200]['enable']=1.5
        case['dut_parameters']=dict(tau=20e-9,positive=1e7,negative=6e6,gain=.98)
        # Internally consistent reports cannot legalize a fabricated vout=.75.
        self.assertFalse(measure_verdict(case,at,rows)['passed'])
if __name__=='__main__'   :unittest.main()

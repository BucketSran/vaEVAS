"""Public waveform seam: worked frequency and causality checks, no source parsing."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'benchmark/checkers'))
from v2_next_filter import phasor, response

class ContractTests(unittest.TestCase):
    def test_ctle_dc_normalization(self):
        self.assertAlmostEqual(response(0, 1000, 4000, 12000, 1.7).real, 1.7)
    def test_synchronous_measurement_recovers_signed_phase(self):
        import math
        rows=[{'time':k/100000,'u':.2*math.cos(2*math.pi*1000*k/100000+.4)} for k in range(1001)]
        got=phasor(rows,'u',1000)
        self.assertAlmostEqual(abs(got),.2,places=5)
        self.assertAlmostEqual(math.atan2(got.imag,got.real),.4,places=5)

class DynamicContractTests(unittest.TestCase):
    def test_energy_step_requires_continuous_rise(self):
        import math
        from v2_next_filter import evaluate
        rows=[{'time':k*1e-5,'i':.4,'q':0.,'en':1.,'reset':0.,
               'env':.4*math.sqrt(1-math.exp(-2*math.pi*150*k*1e-5))} for k in range(501)]
        case={'kind':'envelope','parameters':{'initval':0.,'bandwidth':150},'stop':.005}
        self.assertTrue(evaluate(rows,case,None)['passed'])
        for row in rows: row['env']=.4
        self.assertFalse(evaluate(rows,case,None)['passed'])
    def test_programmable_state_retains_zero_code_baseline(self):
        import math
        from v2_next_filter import evaluate
        rows=[{'time':k*1e-6,'u':.2,'code':0.,'reset':0.,
               'y':.2*(1-math.exp(-2*math.pi*1000*k*1e-6))} for k in range(1001)]
        case={'kind':'programmable','parameters':{'initval':0.,'base':1000},'stop':.001}
        self.assertTrue(evaluate(rows,case,None)['passed'])
        for row in rows: row['y']=.2*(1-math.exp(-1000*row['time']))
        self.assertFalse(evaluate(rows,case,None)['passed'])

class SweepContractTests(unittest.TestCase):
    def test_early_report_cannot_pass_by_holding_correct_values_later(self):
        import math
        from v2_next_filter import evaluate
        frequencies=[1000,4000,16000,8000]
        amplitudes=[.12,.12,.0001,.12]
        rows=[]
        for k in range(3996):
            t=k*2e-5;idx=min(3,int(t/.02));local=t-idx*.02;f=frequencies[idx]
            gain=1/math.sqrt(1+(f/1500)**2);phase=-math.atan(f/1500)
            report=idx if local>=.012 else idx-1
            if report<0 or report==2:rg=rp=valid=0.
            else:
                rg=1/math.sqrt(1+(frequencies[report]/1500)**2)
                rp=-math.atan(frequencies[report]/1500);valid=1.
            rows.append(dict(time=t,drive=amplitudes[idx]*math.sin(2*math.pi*f*local),
                             sense=amplitudes[idx]*gain*math.sin(2*math.pi*f*local+phase),
                             gain=rg,phase=rp,valid=valid))
        case=dict(kind='sweep',stop=.0799,step=2e-5,parameters=dict(frequencies=frequencies,amplitudes=amplitudes,slot=.02,settle=.004,window=.008,fc=1500))
        self.assertTrue(evaluate(rows,case,None)['passed'])
        for row in rows:
            if .006<row['time']<.012:row['valid']=1.
        self.assertFalse(evaluate(rows,case,None)['passed'])

if __name__=='__main__': unittest.main()

import importlib.util
from pathlib import Path
import unittest
P=Path(__file__).resolve().parents[3]/"benchmark/checkers/v2_integration.py"
spec=importlib.util.spec_from_file_location("checker",P)
checker=importlib.util.module_from_spec(spec);spec.loader.exec_module(checker)

class ContractTests(unittest.TestCase):
    def test_tdc_signed_lag_and_missing_pair(self):
        case={"kind":"tdc", "checks":[{"time":12e-9,"code":4,"valid":.9},{"time":25e-9,"code":0,"valid":0}],"code_tol":0.01}
        rows=[{"time":0,"code":0,"valid":0},{"time":12e-9,"code":4,"valid":.9},{"time":25e-9,"code":0,"valid":0}]
        self.assertTrue(checker.evaluate(rows,case,Path('.'))["passed"])
        rows[1]["code"]=-4
        self.assertFalse(checker.evaluate(rows,case,Path('.'))["passed"])
    def test_missing_waveform_never_passes(self):
        self.assertFalse(checker.evaluate([], {"kind":"tdc","checks":[{"time":1,"code":0,"valid":0}]},Path('.'))["passed"])


class SystemEdges(unittest.TestCase):
    def waveform(self,phase=0,frequency=30e6,lock=0):
        import math
        return [{'time':i*1e-9,'dco':.45+.45*math.sin(2*math.pi*frequency*i*1e-9),
                 'ref':.45+.45*math.sin(2*math.pi*10e6*i*1e-9),
                 'fb':.45+.45*math.sin(2*math.pi*10e6*(i*1e-9-phase)), 'lock':lock}
                for i in range(2001)]
    def case(self):
        return {'kind':'pll','windows':[{'window':[.2e-6,1.8e-6],'frequency':30e6,
               'frequency_tolerance':100e3,'phase_tolerance':3e-9}],
               'checks':[{'time':1e-6,'lock':0}]}
    def test_true_edges_pass_even_without_internal_lock(self):
        self.assertTrue(checker.evaluate(self.waveform(),self.case(),Path('.'))['passed'])
    def test_lock_high_cannot_hide_frequency_failure(self):
        self.assertFalse(checker.evaluate(self.waveform(frequency=25e6,lock=.9),self.case(),Path('.'))['passed'])
    def test_real_feedback_phase_required(self):
        self.assertFalse(checker.evaluate(self.waveform(phase=10e-9),self.case(),Path('.'))['passed'])
    def test_reset_lock_residue_rejected(self):
        self.assertFalse(checker.evaluate(self.waveform(lock=.9),self.case(),Path('.'))['passed'])

if __name__=="__main__":unittest.main()

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



class DividerAndQualification(unittest.TestCase):
    def trace(self, fb_frequency=10e6, lock_good=True, lose_ref=False):
        import math
        rows=[]
        for i in range(40001):
            t=i*0.5e-9
            r=.45+.45*math.sin(2*math.pi*10e6*t)
            if lose_ref and t>12e-6:r=0
            rows.append({'time':t,'dco':.45+.45*math.sin(2*math.pi*30e6*t),
                         'ref':r,'fb':.45+.45*math.sin(2*math.pi*fb_frequency*t),
                         'target':3,'rst':0,'fine_enable':.9,
                         'lock':.9 if lock_good and t>=6.701e-6 else 0})
        return rows
    def case(self):
        return {'kind':'pll','windows':[{'window':[8e-6,10e-6], 'frequency':30e6,
                'frequency_tolerance':100e3,'phase_tolerance':3e-9,'divider_n':3}],
                'lock_contract':{'pair_lsb':250e-12,'phase_limit':1e-9,'consecutive':20,
                                 'timeout':45e-9,'settle':1.5e-9}}
    def test_reference_subsequence_is_not_valid_feedback(self):
        self.assertFalse(checker.evaluate(self.trace(fb_frequency=5e6),self.case(),Path('.'))['passed'])
    def test_constant_low_lock_rejected_after_twenty_real_pairs(self):
        self.assertFalse(checker.evaluate(self.trace(lock_good=False),self.case(),Path('.'))['passed'])
    def test_real_qualified_lock_is_accepted(self):
        self.assertTrue(checker.evaluate(self.trace(),self.case(),Path('.'))['passed'])
    def test_missing_ref_pair_revokes_previous_lock(self):
        self.assertFalse(checker.evaluate(self.trace(lose_ref=True),self.case(),Path('.'))['passed'])



class ResetReadback(unittest.TestCase):
    def test_high_phase_reset_requires_zero_frame_not_only_zero_output(self):
        case={'kind':'multichannel','checks':[{'time':26e-9,'out':0},
              {'time':36e-9,'out':0},{'time':46e-9,'out':0},{'time':56e-9,'out':0}]}
        # Worked counterexample: frame was captured at 15ns, reset at 16ns
        # while its adapted clock stayed high. Clearing only out leaves old frame.
        stale=[{'time':0,'out':0},{'time':17e-9,'out':0},{'time':26e-9,'out':.08},
               {'time':36e-9,'out':.31},{'time':46e-9,'out':.57},{'time':56e-9,'out':.84}]
        cleared=[{'time':t,'out':0} for t in [0,17e-9,26e-9,36e-9,46e-9,56e-9]]
        self.assertFalse(checker.evaluate(stale,case,Path('.'))['passed'])
        self.assertTrue(checker.evaluate(cleared,case,Path('.'))['passed'])

if __name__=="__main__":unittest.main()

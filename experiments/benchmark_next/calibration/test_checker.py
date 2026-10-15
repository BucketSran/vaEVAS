import unittest, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"benchmark/material/historyref/legacy-authoring/checkers"))
from v2_next_calibration import evaluate
class OutputContract(unittest.TestCase):
 def test_equal_outputs_cannot_pass_common_mode(self):
  rows=[{"time":i*1e-6,"inp":.05,"inn":-.05,"outp":.5,"outn":.5,"enable":.9,"code":0,"rst":0} for i in range(200)]
  details=evaluate(rows,{"kind":"common-mode","windows":[[50e-6,190e-6]],"gain":2,"cm_target":.5,"cm_tolerance":.005,"diff_tolerance":.006},Path("."))
  self.assertFalse(details["passed"])
 def test_real_signal_and_common_mode_are_both_accepted(self):
  rows=[{"time":i*1e-6,"inp":.05,"inn":-.05,"outp":.6,"outn":.4,"enable":.9,"code":-3,"rst":0} for i in range(200)]
  self.assertTrue(evaluate(rows,{"kind":"common-mode","windows":[[50e-6,190e-6]],"gain":2,"cm_target":.5,"cm_tolerance":.005,"diff_tolerance":.006},Path("."))["passed"])
 def test_fractional_steady_code_is_rejected(self):
  rows=[{"time":i*1e-6,"inp":.05,"inn":-.05,"outp":.6,"outn":.4,"enable":.9,"code":-3.5,"rst":0} for i in range(200)]
  c={"kind":"common-mode","windows":[[50e-6,190e-6]],"gain":2,"cm_target":.5,"cm_tolerance":.005,"diff_tolerance":.006}
  self.assertFalse(evaluate(rows,c,Path('.'))['passed'])
 def test_integer_codes_with_finite_transitions_are_accepted(self):
  rows=[]
  for i in range(1000):
   t=i*20e-9;value=-3 if t<5e-6 else (-3+(t-5e-6)/100e-9 if t<5.1e-6 else -2)
   rows.append({"time":t,"inp":.05,"inn":-.05,"outp":.6,"outn":.4,"enable":.9,"code":value,"rst":0})
  c={"kind":"common-mode","windows":[[1e-6,19e-6]],"gain":2,"cm_target":.5,"cm_tolerance":.005,"diff_tolerance":.006}
  self.assertTrue(evaluate(rows,c,Path('.'))['passed'])
class FractionalContract(unittest.TestCase):
 def waveform(self, variant, reference_shift=0):
  # Independently chosen 35MHz DCO and alternating 3/4 edge divide.
  events=[]
  for signal,times in [('dco',[10e-9+i/35e6 for i in range(1400)]),('ref',[10e-9+reference_shift+i/10e6 for i in range(420)])]:
   for t in times:events.extend([(t-1e-11,signal,0),(t+1e-11,signal,.9),(t+1e-9,signal,.9),(t+1.01e-9,signal,0)])
  counts=[3,4] if variant==0 else [4,3]
  index=0;times=[]
  for i in range(400):
   index+=counts[i%2];times.append(10e-9+index/35e6+50e-12)
  for t in times:events.extend([(t-1e-11,'fb',0),(t+1e-11,'fb',.9),(t+1e-9,'fb',.9),(t+1.01e-9,'fb',0)])
  values={'dco':0,'ref':0,'fb':0,'lock':.9,'rst':0,'n':3,'frac':.5};rows=[]
  for t,signal,value in sorted(events):
   values[signal]=value;rows.append({'time':t,**values})
  return rows
 def test_different_legal_fractional_sequences(self):
  c={'kind':'fractional-pll','windows':[[1e-6,10e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2}
  for variant in [0,1]:self.assertTrue(evaluate(self.waveform(variant),c,Path('.'))['passed'])
 def test_stable_wrong_phase_is_rejected(self):
  c={'kind':'fractional-pll','windows':[[1e-6,10e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2}
  result=evaluate(self.waveform(0,35e-9),c,Path('.'))
  failed=[check['name'] for check in result['checks'] if not check['passed']]
  self.assertEqual(failed,['0:mean-phase-cycles'])
 def test_reset_feedback_must_clear_even_outside_lock_windows(self):
  c={'kind':'fractional-pll','windows':[[1e-6,10e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2}
  rows=self.waveform(0)
  for row in rows:
   if 100e-9<=row['time']<=200e-9:row.update(rst=.9,fb=.9,lock=0)
  result=evaluate(rows,c,Path('.'))
  self.assertEqual([check['name'] for check in result['checks'] if not check['passed']],['reset-feedback-clear'])
 def test_each_return_or_reconfiguration_withdraws_qualification(self):
  c={'kind':'fractional-pll','windows':[[1e-6,10e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2,'withdraw_windows':[[3.1e-6,3.2e-6],[6.1e-6,6.2e-6]]}
  result=evaluate(self.waveform(0),c,Path('.'))
  self.assertEqual([check['name'] for check in result['checks'] if not check['passed']],['withdraw-qualification','withdraw-qualification'])
 def test_recovery_at_14us_respects_public_15us_deadline(self):
  c={'kind':'fractional-pll','windows':[[16e-6,30e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2,'disturbance_events':[0]}
  rows=self.waveform(0)
  for row in rows:row['lock']=.9 if row['time']>=14e-6 else 0
  self.assertTrue(evaluate(rows,c,Path('.'))['passed'])
 def test_recovery_at_16us_cannot_hide_behind_later_stable_window(self):
  c={'kind':'fractional-pll','windows':[[16e-6,30e-6,3,.5]],'ratio_tolerance':.04,'frequency_tolerance':.06,'feedback_tolerance':.015,'phase_tolerance':.35,'mean_phase_tolerance':.2,'disturbance_events':[0]}
  rows=self.waveform(0)
  for row in rows:row['lock']=.9 if row['time']>=16e-6 else 0
  verdict=evaluate(rows,c,Path('.'))
  self.assertEqual([v['name'] for v in verdict['checks'] if not v['passed']],['0:recovery-deadline-qualification'])
if __name__=="__main__": unittest.main()

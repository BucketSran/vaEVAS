import importlib.util,math,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('check',Path(__file__).with_name('check.py'));c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
class Calibration(unittest.TestCase):
 def test_reverse_and_extend_do_not_restart_full_duration(self):
  self.assertEqual(c.expected('a_reverse',.625),.25);self.assertEqual(c.expected('a_extend',.625),1)
  self.assertEqual(c.expected('b_reverse',.75),.125);self.assertEqual(c.expected('b_extend',1),1)
 def test_missing_adjacent_point_stays_missing(self):
  t=.25;self.assertEqual(c.coverage([math.nextafter(t,-math.inf)],[t]),[t])
 def test_unbound_run_alias_refused(self):
  with self.assertRaisesRegex(ValueError,'canonical'):
   c.analyze(Path('collection/spectre-output/alternate-runs'))
 def test_duplicate_times_refused(self):
  with self.assertRaises(ValueError):c.coverage([0,0],[0])
 def test_zero_reference_is_a_failure(self):
  rows=[{'time':1,'voltages':{n:0 for n in c.SIGNALS}}];d=c.waveform(rows)
  self.assertTrue(d['failures']);self.assertEqual(d['maxima']['a_extend']['difference'],2)
 def test_nonfinite_waveform_refused(self):
  r={'time':0,'voltages':{n:0 for n in c.SIGNALS}};r['voltages']['a_simple']=math.nan
  with self.assertRaises(ValueError):c.waveform([r])
 def test_absent_target_changes_not_promoted_to_callback_success(self):
  d=c.state_observations([{'time':t,'voltages':{n:0 for n in c.SIGNALS}} for t in [0,1,3]])
  self.assertEqual(len(d['failures']),8);self.assertTrue(d['timer_window_verdict'].startswith('I:'));self.assertTrue(d['callback_count_verdict'].startswith('I:'))
if __name__=='__main__':unittest.main()

import importlib.util,math,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('analysis',Path(__file__).with_name('analyze.py'));a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class DiagnosticCalibration(unittest.TestCase):
 def test_exact_dyadic_root_and_left_side(self):
  root=7/4194304;q,p=a.exact(root);self.assertEqual((q,p),(1,0));q,p=a.exact(math.nextafter(root,-math.inf));self.assertGreater(p,.999);self.assertLess(q,1)
 def test_ordinary_failure_retained_despite_circular_agreement(self):
  t=math.nextafter(7/4194304,-math.inf);r={'time':t,'voltages':{'freq':.5,'phase':0.,'out':0.}}
  d=a.compare([r]);self.assertEqual([f['signal'] for f in d['ordinary_failures']],['phase']);self.assertLess(d['maxima']['phase_circular']['difference'],.001)
 def test_duplicate_and_reversed_times_refused(self):
  for times in [[0.,0.],[1.,0.]]:
   with self.assertRaises(ValueError):a.native_index([{'time':t} for t in times])
 def test_missing_anchor_not_substituted_by_adjacent_ulp(self):
  root=7/4194304;index=a.native_index([{'time':math.nextafter(root,-math.inf)}]);self.assertNotIn(root,index)
 def test_nonfinite_psf_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a';p.write_text('VALUE\n"time" 0\n"phase" nan\nEND\n')
   with self.assertRaises(ValueError):a.normalizer.normalize(p,{'voltage_nodes':['phase']})
 def test_missing_signal_refused(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'a';p.write_text('VALUE\n"time" 0\n"phase" 0\nEND\n')
   with self.assertRaises(ValueError):a.normalizer.normalize(p,{'voltage_nodes':['phase','raw']})
if __name__=='__main__':unittest.main()

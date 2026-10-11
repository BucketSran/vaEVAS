import importlib.util, pathlib, unittest, math
p=pathlib.Path(__file__).resolve().parents[3]/'benchmark/checkers/v2_next_ldo.py'
s=importlib.util.spec_from_file_location('checker',p); c=importlib.util.module_from_spec(s)
class Startup(unittest.TestCase):
 def test_ring_exit_resets_finite_settle(self):
  s.loader.exec_module(c)
  vals=[0,1.1,1.2,1.25,1.2,1.2,1.2]
  result=c.startup_metrics(vals,dict(tick=1e-6,ramp_start=0,ramp_end=1e-6,window=6e-6,target=1.2,tail=2))
  self.assertEqual(result['t90_us'],1)
  self.assertEqual(result['settle_us'],3)
  self.assertAlmostEqual(result['overshoot_mv'],50)
  self.assertEqual(result['status'],1)
 def test_failed_dut_retains_correct_peak(self):
  s.loader.exec_module(c)
  result=c.startup_metrics([0,.5,1.,1.],dict(tick=1e-6,ramp_start=0,ramp_end=1e-6,window=3e-6,target=1.2,tail=2))
  self.assertEqual(result['status'],2)
  self.assertEqual(result['t90_us'],-1)
  self.assertEqual(result['settle_us'],-1)
  self.assertEqual(result['overshoot_mv'],0)
 def test_final_single_entry_is_not_qualified(self):
  s.loader.exec_module(c)
  result=c.startup_metrics([0,1.1,1.1,1.2],dict(tick=1e-6,ramp_start=0,ramp_end=1e-6,window=3e-6,target=1.2,tail=2))
  self.assertEqual(result['status'],3)
  self.assertEqual(result['reached'],1)
  self.assertEqual(result['settled'],0)
 def test_known_first_order_crossing(self):
  s.loader.exec_module(c)
  values=[1.2*(1-math.exp(-i)) for i in range(9)]
  result=c.startup_metrics(values,dict(tick=1e-6,ramp_start=0,ramp_end=0,window=8e-6,target=1.2,tail=2))
  # Continuous roots ln(10)=2.3026 and ln(50)=3.9120 become samples 3 and 4.
  self.assertEqual(result['t90_us'],3)
  self.assertEqual(result['settle_us'],4)
  self.assertEqual(result['overshoot_mv'],0)
 def test_known_second_order_peak(self):
  s.loader.exec_module(c)
  zeta=.3;ratio=zeta/math.sqrt(1-zeta*zeta)
  values=[1.2*(1-math.exp(-ratio*math.pi*i/10)*(math.cos(math.pi*i/10)+ratio*math.sin(math.pi*i/10))) for i in range(101)]
  result=c.startup_metrics(values,dict(tick=.1e-6,ramp_start=0,ramp_end=0,window=10e-6,target=1.2,tail=2))
  self.assertAlmostEqual(result['overshoot_mv'],1200*math.exp(-ratio*math.pi),places=9)
  self.assertEqual(result['settled'],1)
if __name__=='__main__':unittest.main()

import sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'benchmark/checkers'))
from v2_next_converter import spectrum_metrics, linearity_metrics
class Contracts(unittest.TestCase):
 def test_known_coherent_power(self):
  import math
  x=[2048+600*math.sin(2*math.pi*5*n/64)+60*math.sin(2*math.pi*10*n/64) for n in range(64)]
  q=spectrum_metrics(x,5)
  self.assertAlmostEqual(q['sndr'],20,places=8)
  self.assertAlmostEqual(q['sfdr'],20,places=8)
 def test_endpoint_fit_uses_observed_levels(self):
  q=linearity_metrics([.1,.3,.55,.7])
  self.assertAlmostEqual(q['dnl'],.25)
  self.assertAlmostEqual(q['inl'],.25)

from v2_next_converter import evaluate
class WaveformSeam(unittest.TestCase):
 def waveform(self,transparent=False):
  rows=[]
  for i in range(401):
   t=i*0.05e-9
   clk=1.0 if 1<=t/1e-9<2 or 6<=t/1e-9<7 or 11<=t/1e-9<12 or 16<=t/1e-9<17 else 0.0
   control=1.0 if t>=5e-9 else 0.0
   q=control if transparent else (1.0 if t>=6e-9 else 0.0)
   rows.append(dict(time=t,clk=clk,rst=0,b0=control,aout=q))
  return rows
 def test_held_dac_accepts_captured_transfer(self):
  case=dict(kind='dac',maxstep=50e-12,guard=.5e-9,initial=0,inputs=['b0'],weights=[1],lo=0,hi=1,tolerances={'aout':.001})
  self.assertTrue(evaluate(self.waveform(),case,None)['passed'])
 def test_transparent_dac_rejected_before_capture(self):
  case=dict(kind='dac',maxstep=50e-12,guard=.5e-9,initial=0,inputs=['b0'],weights=[1],lo=0,hi=1,tolerances={'aout':.001})
  self.assertFalse(evaluate(self.waveform(True),case,None)['passed'])

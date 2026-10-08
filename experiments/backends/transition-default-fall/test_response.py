"""Transport controls independent of transition equations or solver outputs."""
import unittest
from types import SimpleNamespace
from evas.errors import KernelError
from evas.ir import SCHEMA_VERSION
from response import observations
class ResponseIdentity(unittest.TestCase):
 def setUp(self):
  self.program=SimpleNamespace(nodes=['0','out'],states=[],events=[])
  self.control={'schema_version':SCHEMA_VERSION,'engine':'transport-control','transient':{'times':[0.,.25],'state_names':[],'states':[[],[]],'events':[],'accepted_steps':0,'discarded_trials':0},'nodes':['0','out'],'solutions':[{'voltages':[0.,0.],'max_residual_v':0.,'max_residual_ratio':0.},{'voltages':[0.,.5],'max_residual_v':0.,'max_residual_ratio':0.}]}
 def test_valid_control_uses_returned_times(self):
  self.assertEqual(observations(self.control,[0.,.25],self.program)[1],dict(time=.25,voltages={'0':0.,'out':.5}))
 def test_changed_time_rejected(self):
  self.control['transient']['times'][1]=.5
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
 def test_reordered_times_rejected(self):
  self.control['transient']['times'].reverse()
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
 def test_missing_node_rejected(self):
  self.control['nodes'].pop()
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
 def test_short_voltage_row_rejected(self):
  self.control['solutions'][0]['voltages'].pop()
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
 def test_missing_solution_rejected(self):
  self.control['solutions'].pop()
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
 def test_nonfinite_voltage_rejected(self):
  self.control['solutions'][0]['voltages'][0]=float('nan')
  with self.assertRaises(KernelError):observations(self.control,[0.,.25],self.program)
if __name__=='__main__':unittest.main()

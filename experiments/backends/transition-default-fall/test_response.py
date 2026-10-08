"""Transport controls independent of transition equations or solver outputs."""
import copy,unittest
from response import observations
class ResponseIdentity(unittest.TestCase):
 def setUp(self):
  self.control={'transient':{'times':[0.,.25]},'nodes':['0','out'],'solutions':[{'voltages':[0.,0.]},{'voltages':[0.,.5]}]}
 def test_valid_control_uses_returned_times(self):
  self.assertEqual(observations(self.control,[0.,.25],['0','out'])[1],dict(time=.25,voltages={'0':0.,'out':.5}))
 def test_changed_time_rejected(self):
  self.control['transient']['times'][1]=.5
  with self.assertRaisesRegex(ValueError,'times differ'):observations(self.control,[0.,.25],['0','out'])
 def test_reordered_times_rejected(self):
  self.control['transient']['times'].reverse()
  with self.assertRaises(ValueError):observations(self.control,[0.,.25],['0','out'])
 def test_missing_node_rejected(self):
  self.control['nodes'].pop()
  with self.assertRaisesRegex(ValueError,'node columns'):observations(self.control,[0.,.25],['0','out'])
 def test_short_voltage_row_rejected(self):
  self.control['solutions'][0]['voltages'].pop()
  with self.assertRaisesRegex(ValueError,'row shape'):observations(self.control,[0.,.25],['0','out'])
 def test_missing_solution_rejected(self):
  self.control['solutions'].pop()
  with self.assertRaisesRegex(ValueError,'solution shape'):observations(self.control,[0.,.25],['0','out'])
 def test_nonfinite_voltage_rejected(self):
  self.control['solutions'][0]['voltages'][0]=float('nan')
  with self.assertRaisesRegex(ValueError,'nonfinite'):observations(self.control,[0.,.25],['0','out'])
if __name__=='__main__':unittest.main()

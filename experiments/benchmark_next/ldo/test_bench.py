"""Analytical stage timing at the public waveform/report seam."""
import importlib.util,pathlib,unittest
p=pathlib.Path(__file__).resolve().parents[3]/'benchmark/material/historyref/legacy-authoring/checkers/v2_next_ldo.py'
s=importlib.util.spec_from_file_location('ldo',p);c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
class Bench(unittest.TestCase):
 def example(self,edge):
  case=dict(kind='bench',tick=1e-6,target=1.2,band=.024,qualification=2,ramp_start=0,ramp_end=2e-6,min_window=3e-6,timeout=4e-6,startup_timeout=5e-6,stop=20e-6,guard=5e-9)
  names=['startup','line_up','line_down','load_up','load_down'];rows=[]
  times=sorted(set([i*.25e-6 for i in range(81)]+[t+edge for t in [3e-6,6e-6,9e-6,12e-6,15e-6]]))
  for t in times:
   stage=sum(t>=x+edge for x in [3e-6,6e-6,9e-6,12e-6,15e-6])
   line=1.8*min(t/2e-6,1) if stage==0 else 1.95 if stage==1 else 1.8
   load=float(stage==3)
   row=dict(time=t,vout=1.2,vin=line,line_cmd=line,load_cmd=load,load_current=.01*load,stage=float(stage),done=float(stage==5))
   for i,name in enumerate(names):
    row[name+'_peak_mv']=row[name+'_offset_mv']=0.
    row[name+'_status']=float(stage>i)
    row[name+'_recovery_us']=(2. if i==0 else 1.) if stage>i else 0.
   rows.append(row)
  return rows,case
 def test_allowed_report_edges(self):
  for edge in [1e-9,3e-9,5e-9]:
   rows,case=self.example(edge)
   result=c.evaluate(rows,case)
   self.assertTrue(result['passed'],result)
 def test_omitting_physical_load_fails(self):
  rows,case=self.example(1e-9)
  for r in rows:r['load_current']=0
  result=c.evaluate(rows,case)
  self.assertFalse(result['passed'])
 def test_small_observation_load_is_allowed(self):
  rows,case=self.example(3e-9)
  case.update(observation_currents=['VOBSOUT:p'],observation_current_atol=1e-10)
  for row in rows:row['VOBSOUT:p']=row['vout']/1e12
  self.assertTrue(c.evaluate(rows,case)['passed'])
 def test_correct_report_cannot_hide_input_load(self):
  rows,case=self.example(3e-9)
  case.update(observation_currents=['VOBSOUT:p'],observation_current_atol=1e-10)
  for row in rows:row['VOBSOUT:p']=row['vout']/1e6
  result=c.evaluate(rows,case)
  self.assertFalse(result['passed'])
  self.assertEqual(result['failures'][0]['kind'],'read-only-input-current')
if __name__=='__main__':unittest.main()

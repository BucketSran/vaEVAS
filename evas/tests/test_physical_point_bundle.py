"""A physical shaped clock drives a held mid-ramp sample beside a polynomial."""
GUARDS = ["LANG", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]
from fractions import Fraction as F
from pathlib import Path
import json, os, tempfile, unittest
from unittest.mock import patch
from evas import Instance, compile_sources, transient
from test_forcing_history_bridge import SOURCE
KERNEL=Path(__file__).resolve().parents[2]/'evas/rust_core/target/debug/evas-kernel'
class PhysicalPointBundle(unittest.TestCase):
 def run_case(self,times):
  p=compile_sources({'physical-clock-mid-sample.va':SOURCE},[Instance('dut','sample',{n:n for n in 'abcys'},{})])
  with tempfile.TemporaryDirectory() as tmp:
   log=Path(tmp)/'diagnostics.json'
   with patch.dict(os.environ,{'EVAS_DIAGNOSTICS_PATH':str(log)}):
    r=transient(p,dict(a=[[0,0],[1,1]],b=[[0,1],[1,0]],c=[[0,0],[1,.984375]]),times,stop=1,max_step=1,kernel=KERNEL,
     source_errors=dict(c=.03125),source_shapes=dict(c=[dict(time_numerator='0',time_denominator='1',value_V=0.),dict(time_numerator='1',time_denominator='1',value_V=1.)]))
   diag=json.loads(log.read_text())
  self.assertGreater(diag['counters'].get('history_point_bundle_strict_reuse',0),0)
  self.assertGreater(diag['counters'].get('shaped_range_search_compare',0),0)
  for t,row,box in zip(times,r['solutions'],r['observation_evidence']['voltage_bounds_V']):
   t=F(t)
   for name,want in dict(s=min(F(1),max(F(0),2*(t-F(1,4)))),y=t*(1-t)+min(F(1,2),max(F(0),4*(t-F(1,2))))).items():
    n=r['nodes'].index(name)
    self.assertLessEqual(abs(row['voltages'][n]-float(want)),1e-10)
    self.assertLessEqual(F(box[n][0]),want);self.assertGreaterEqual(F(box[n][1]),want)
  self.assertEqual([e['time'] for e in r['transient']['events']],[.25,.5])
  return r
 def test_real_producer_kernel_original_point_box_and_held_history(self):
  self.run_case([0,.25,.375,.5,.5625,.625,.75,1])
 def test_passive_queries_preserve_events_and_future_samples(self):
  sparse=[0,.25,.5,.75,1];dense=[i/32 for i in range(33)]
  a=self.run_case(sparse);b=self.run_case(dense)
  self.assertEqual(a['transient']['events'],b['transient']['events'])
  self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)] for t in sparse])
  self.assertEqual(a['observation_evidence']['voltage_bounds_V'],[b['observation_evidence']['voltage_bounds_V'][dense.index(t)] for t in sparse])

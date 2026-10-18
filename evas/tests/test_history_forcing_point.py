"""Synthetic DUT public test with preserved physical clock/grid; no original DUT/checker."""
GUARDS = ["LANG", "ANALOG", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]
from pathlib import Path
from fractions import Fraction as Q
import bisect,json,os,tempfile,unittest
from unittest.mock import patch
from evas import Instance,compile_sources,transient
from test_history_forcing import SOURCE
KERNEL=Path(os.environ.get('FORCING_POINT_KERNEL',os.environ['EVAS_TEST_KERNEL']))
class OwnedPhysicalPoint(unittest.TestCase):
 def test_complete_clock_grid_preserves_physical_fraction_oracle(self):
  f=json.loads((Path(__file__).parent/'fixtures/forcing-owned-clock.json').read_text());stop=f['stop']
  p=compile_sources({'synthetic_mixer.va':SOURCE},[Instance('one','mixer',dict(u='u',lo='lo',rst='rst',y='y',metric='metric'),{})])
  with tempfile.TemporaryDirectory() as tmp:
   log=Path(tmp)/'diagnostics.json'
   with patch.dict(os.environ,{'EVAS_DIAGNOSTICS_PATH':str(log)}):
    r=transient(p,dict(u=[[0,.25],[stop,.25]],lo=f['clock'],rst=[[0,0],[stop,0]]),f['output_times'],stop=stop,max_step=f['max_step'],kernel=KERNEL,source_errors=dict(lo=f['error']),source_shapes=dict(lo=f['shape']))
   c=json.loads(log.read_text())['counters']
  ts=[Q(int(x['time_numerator']),int(x['time_denominator']))for x in f['shape']];vs=[Q(x['value_V'])for x in f['shape']];i=r['nodes'].index('y')
  for time,row,box in zip(f['output_times'],r['solutions'],r['observation_evidence']['voltage_bounds_V']):
   t=Q(time);j=bisect.bisect_left(ts,t);v=vs[j]if j<len(ts)and ts[j]==t else vs[j-1]+(vs[j]-vs[j-1])*(t-ts[j-1])/(ts[j]-ts[j-1]);want=Q(3,16)if v>Q(1,2)else Q(13,16)
   self.assertAlmostEqual(row['voltages'][i],float(want),places=10);self.assertLessEqual(Q(box[i][0]),want);self.assertGreaterEqual(Q(box[i][1]),want)
  self.assertGreater(c['forcing_owned_point_success'],0);self.assertGreater(c['forcing_owned_plateau_success'],0);self.assertGreater(c['forcing_owned_enclosure_success'],0)
  print('owned_complete_synthetic_grid',c)

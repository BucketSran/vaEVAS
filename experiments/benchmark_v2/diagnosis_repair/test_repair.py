import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"benchmark/checkers"))
from v2_repair import evaluate
class SequencerContract(unittest.TestCase):
 def test_synchronous_reset_and_reentry(self):
  case={'kind':'sequencer','signals':['clk','rst','supply_ok','bias_ok','stage1','stage2','ready','progress'],'stop':8e-9,'final_stage':3,'guard':.1e-9,'maxstep':.05e-9}
  rows=[]
  # Literal states: three qualification edges, reset, three fresh edges.
  q=0
  for i in range(161):
   t=i*.05e-9; edge=int(t/1e-9)
   q=[0,1,2,3,0,1,2,3,3][edge]
   rows.append(dict(time=t,clk=.9 if t%1e-9<.5e-9 and t>=1e-9 else 0,rst=.9 if 3.5e-9<=t<4.5e-9 else 0,supply_ok=.9,bias_ok=.9,stage1=.9 if q>=1 else 0,stage2=.9 if q>=2 else 0,ready=.9 if q>=3 else 0,progress=.3*q))
  self.assertTrue(evaluate(rows,case)['passed'])
  for row in rows:
   if row['time']>=4.1e-9: row.update(stage1=.9,stage2=.9,ready=.9,progress=.9)
  self.assertFalse(evaluate(rows,case)['passed'])
class ChainContract(unittest.TestCase):
 def test_real_downstream_actions_and_requalification(self):
  rows=[]
  for i in range(721):
   t=i*.05e-9; ns=t/1e-9
   good=(1.2<=ns<15.2 or ns>=18.2)
   release=(11.2<=ns<15.2 or ns>=28.2)
   count=max(0,int(ns)-11) if 11.2<=ns<15.2 else max(0,int(ns)-28) if ns>=28.2 else 0
   rows.append(dict(time=t,vin=.7 if good else .5,clk=.9 if ns>=1 and ns%1<.4 else 0,pgood=.9*good,resetb=.9*release,enable=.9*release,activity=.1*count))
  case={'kind':'chain','stop':36e-9,'guard':.15e-9,'release_delay':10e-9,'maxstep':.05e-9}
  self.assertTrue(evaluate(rows,case)['passed'])
  for r in rows:
   if 22e-9<r['time']<28e-9:r.update(resetb=.9,enable=.9,activity=.1)
  self.assertFalse(evaluate(rows,case)['passed'])
class SingleModuleContracts(unittest.TestCase):
 def test_debounce_glitch_cancellation_and_reset(self):
  rows=[]
  for i in range(901):
   t=i*.05e-9;n=t/1e-9
   rows.append(dict(time=t,sig=.9 if 1<=n<8 or 12<=n<30 or n>=31 else 0,rst_n=0 if 26<=n<28 else .9,out=.9 if 24<=n<26 or n>=43 else 0))
  c={'kind':'debounce','stop':45e-9,'stable':12e-9,'guard':.6e-9,'maxstep':.05e-9}
  self.assertTrue(evaluate(rows,c)['passed'])
  for r in rows:
   if 1.7e-9<r['time']<7e-9:r['out']=.9
  self.assertFalse(evaluate(rows,c)['passed'])
 def test_uvlo_synchronous_hysteresis_and_supply_recovery(self):
  rows=[]
  for i in range(201):
   t=i*.05e-9;n=t/1e-9
   vin=.7 if 1.2<=n<3.2 or n>=7.2 else .6 if 3.2<=n<5.2 else .5
   high=2<=n<6 or n>=8
   rows.append(dict(time=t,clk=.9 if n>=1 and n%1<.4 else 0,rst=0,vin=vin,out=.9*high,metric=.1 if high else .9))
  c={'kind':'uvlo','stop':10e-9,'guard':.15e-9,'maxstep':.05e-9}
  self.assertTrue(evaluate(rows,c)['passed'])
  for r in rows:
   if 4.2e-9<r['time']<5.8e-9:r.update(out=0,metric=.9)
  self.assertFalse(evaluate(rows,c)['passed'])
 def test_pfd_pairing_async_reset_and_stale_timer_cancel(self):
  rows=[]
  for i in range(801):
   t=i*5e-12;n=t/1e-9
   ref=.9 if 1<=n<1.4 or 2<=n<2.4 or 3<=n<3.4 else 0
   fb=.9 if 1.2<=n<1.6 or 2.05<=n<2.45 or 3.2<=n<3.6 else 0
   up=.9 if 1<=n<1.28 or 2<=n<2.07 or 3<=n<3.28 else 0
   down=.9 if 1.2<=n<1.28 or 2.05<=n<2.07 or 3.2<=n<3.28 else 0
   rows.append(dict(time=t,ref=ref,fb=fb,rstb=0 if 2.07<=n<2.09 else .9,up=up,down=down))
  c={'kind':'pfd','stop':4e-9,'reset_delay':80e-12,'guard':20e-12,'maxstep':5e-12}
  self.assertTrue(evaluate(rows,c)['passed'])
  for r in rows:
   if 2.095e-9<r['time']<2.12e-9:r.update(up=.9,down=.9)
  self.assertFalse(evaluate(rows,c)['passed'])
 def test_old_pair_timer_cannot_clear_new_up_after_reset(self):
  # Hand-derived: first pair at .25ns has an old .33ns deadline.
  # Reset .28..30ns cancels it; new ref .31ns must remain UP until
  # new fb .50ns plus 80ps, rather than being erased at .33ns.
  rows=[]
  for i in range(1001):
   t=i*1e-12;n=t/1e-9
   rows.append(dict(time=t,ref=.9 if .2<=n<.29 or .31<=n<.7 else 0,
    fb=.9 if .25<=n<.29 or .5<=n<.7 else 0,
    rstb=0 if .28<=n<.30 else .9,
    up=.9 if .2<=n<.28 or .31<=n<.58 else 0,
    down=.9 if .25<=n<.28 or .5<=n<.58 else 0))
  c={'kind':'pfd','stop':1e-9,'reset_delay':80e-12,'guard':20e-12,'maxstep':1e-12}
  self.assertTrue(evaluate(rows,c)['passed'])
  for r in rows:
   if .34e-9<r['time']<.49e-9:r['up']=0
  verdict=evaluate(rows,c)
  self.assertFalse(verdict['passed'])
  self.assertTrue(any(v['signal']=='up' for v in verdict['violations']))
 def test_reset_on_final_qualification_sample_has_priority(self):
  rows=[]
  # Two successful samples, then rst high at the third sample: stage
  # clears instead of becoming ready, and three fresh samples follow.
  for i in range(141):
   t=i*.05e-9;n=t/1e-9;q=[0,1,2,0,1,2,3,3][int(n)]
   rows.append(dict(time=t,clk=.9 if n>=1 and n%1<.4 else 0,
    rst=.9 if 2.6<=n<3.4 else 0,supply_ok=.9,bias_ok=.9,
    stage1=.9*(q>=1),stage2=.9*(q>=2),ready=.9*(q==3),progress=.3*q))
  c={'kind':'sequencer','stop':7e-9,'final_stage':3,'guard':.12e-9,'maxstep':.05e-9}
  self.assertTrue(evaluate(rows,c)['passed'])
  for r in rows:
   if 3.2e-9<r['time']<3.8e-9:r.update(stage1=.9,stage2=.9,ready=.9,progress=.9)
  self.assertFalse(evaluate(rows,c)['passed'])
 def test_sparse_missing_and_nonfinite_are_unscored(self):
  c={'kind':'uvlo','stop':1.,'maxstep':.1}
  with self.assertRaises(ValueError):evaluate([{'time':0},{'time':.5},{'time':1}],c)
  rows=[dict(time=i*.05,clk=0,rst=0,vin=.5,out=0,metric=.9) for i in range(21)]
  rows[5]['out']=float('nan')
  with self.assertRaisesRegex(ValueError,'nonfinite'):evaluate(rows,c)
  rows[5]['out']=0;del rows[5]['vin']
  with self.assertRaisesRegex(ValueError,'missing'):evaluate(rows,c)
if __name__=='__main__': unittest.main()

import importlib.util
import unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location('checker',Path(__file__).parents[3]/'benchmark/checkers/v2_spec.py')
class ContractTests(unittest.TestCase):
 def test_edge_sample_uses_crossing_value_and_holds_high(self):
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)
  rows=[{'time':i*1e-11,'vss':.1,'vdd':1.,'clk':.1 if i<100 else 1.,'in':.1+i*.001,'out':.1+(.1995-.1)*max(0,min(1,(i-99.5)/10))} for i in range(400)]
  result=mod.evaluate(rows,{'source_id':'024','stop':3.99e-9,'signals':['vss','vdd','clk','in','out'],'params':{'tedge':1e-10},'resolution':1e-11},Path('.'))
  self.assertTrue(result['passed'])
  for row in rows[100:]:row['out']=row['in']
  self.assertFalse(mod.evaluate(rows,{'source_id':'024','stop':3.99e-9,'signals':['vss','vdd','clk','in','out'],'params':{'tedge':1e-10},'resolution':1e-11},Path('.'))['passed'])
 def test_missing_evidence_is_not_candidate_failure(self):
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)
  with self.assertRaises(ValueError):mod.evaluate([],{'source_id':'024'},Path('.'))

class IndependentLiteralTests(unittest.TestCase):
 def checker(self):
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod);return mod
 def fixture(self,source,events,initial,signals,stop=6e-9,tr=2e-11):
  rows=[]
  for i in range(int(stop/2e-12)+1):
   t=i*2e-12;row={'time':t,**initial};row.update(signals(t))
   for node in events:
    previous=initial[node]
    for when,value in events[node]:
     if t>=when:previous=previous+(value-previous)*min(1,(t-when)/tr)
    row[node]=previous
   rows.append(row)
  return rows,{'source_id':source,'signals':list(rows[0].keys()-{'time'}),'stop':stop,'resolution':2e-12,'params':{'tr':tr}}
 def test_sigma_delta_feedback_sequence(self):
  clock=lambda t: .9 if any(a<=t<a+.3e-9 for a in [1e-9,2e-9,3e-9,4e-9]) else 0.
  # Finite 20ps clock ramps put crossings at 1.01,2.01,3.01,4.01ns.
  def inputs(t):
   clk=0.
   for a in [1e-9,2e-9,3e-9,4e-9]:
    if a<=t<a+20e-12:clk=.9*(t-a)/20e-12
    elif a+20e-12<=t<a+.3e-9:clk=.9
    elif a+.3e-9<=t<a+.32e-9:clk=.9*(a+.32e-9-t)/20e-12
   return {'vclk':clk,'vin':.25 if t<1.5e-9 else .5 if t<2.5e-9 else .125 if t<3.5e-9 else .75}
  rows,case=self.fixture('055',{'bitout':[(1.01e-9,.9),(2.01e-9,0.),(4.01e-9,.9)]},{'bitout':0.},inputs)
  self.assertTrue(self.checker().evaluate(rows,case,Path('.'))['passed'])
  for row in rows:
   if row['time']>2.05e-9:row['bitout']=.9
  self.assertFalse(self.checker().evaluate(rows,case,Path('.'))['passed'])
 def test_dac_zero_code_complementary_outputs(self):
  inputs=lambda t:{'clk':0. if t<1e-9 else min(.9,.9*(t-1e-9)/20e-12),'vss':0.,'vdd':.9,**{f'd{i}':0. for i in range(10)},'cal0':0.,'cal1':0.}
  rows,case=self.fixture('002',{'vdac_p':[(1.01e-9,.3)],'vdac_n':[(1.01e-9,.6)]},{'vdac_p':.45,'vdac_n':.45},inputs)
  self.assertTrue(self.checker().evaluate(rows,case,Path('.'))['passed'])
  for row in rows:
   if row['time']>1.1e-9:row['vdac_n']=.3
  self.assertFalse(self.checker().evaluate(rows,case,Path('.'))['passed'])
 def test_resolution_defect_stays_unscored(self):
  rows=[{'time':0,'bitout':0,'vin':.2,'vclk':0},{'time':1e-9,'bitout':.9,'vin':.2,'vclk':.9}]
  with self.assertRaisesRegex(ValueError,'resolution'):self.checker().evaluate(rows,{'source_id':'055','signals':['bitout','vin','vclk'],'stop':1e-9},Path('.'))


class InitialStateTests(unittest.TestCase):
 def test_each_source_has_independent_initial_literal(self):
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)
  inputs={'clk':0.,'clk_in':0.,'clks':0.,'ck':0.,'vclk':0.,'phi1':0.,'phi2':0.,'chop_clk':0.,'rst':0.,'enable':0.,'hold':0.,'sample':0.,'vin':.45,'in':.45,'vinp':.45,'vinn':.45,'vss':.1,'vdd':1.,'vref':.8,'vrefp':.9,'vrefn':.1,'gain_sel':0.,'data':0.,'low_trip':.3,'high_trip':.6,'dcomp':0.,'dcompb':0.,'test':0.,'d':0.,'sample_reset':0.,'sample_signal':0.,'cal0':0.,'cal1':0.}
  inputs.update({f'd{i}':0. for i in range(10)});inputs.update({f'dtest{i}':0. for i in range(4)});inputs.update({f'gain_{i}':0. for i in range(3)});inputs.update({n:0. for n in ['pre_0','pre_1','post_0','post_1']})
  literal={'024':{'out':.1},'071':{'vout':.45,'metric':0.},'186':{'clkc':0.,**{f'{p}{i}':0. if i==4 else 1. for p in ['dp','dm'] for i in range(1,5)},**{f'dout{i}':0. for i in range(4)}},'047':{'out':1.},'314':{'inside_flag':0.,'state_metric':0.,'toggled':0.},'002':{'vdac_p':.55,'vdac_n':.55},'003':{'vres':.45,'d1':0.,'d0':0.},'055':{'bitout':0.},'001':{'up':0.,'down':0.,'retimed':0.},'375':{'phi1':0.,'phi2':0.,'deadtime_metric':0.,'valid':0.},'396':{'lo_i':0.,'lo_q':0.,'div_metric':0.,'quad_ok':0.},'038':{'out':.45,'metric':0.},'082':{'out':.45,'metric':0.,'gain_mon':.6176470588235294,'rssi_mon':0.},'091':{'voutp':.45,'voutn':.45,'settled':0.,'offset_residual':0.},'308':{'vout':.45,'offset_dbg':0.,'valid':0.},'370':{'vout':.45,'error_metric':.45,'settled':0.},'307':{'vout':.45,'phase_metric':.45,'valid':0.},'183':{**{f'dc{i}':1. if i==6 else 0. for i in range(7)},'cvinp':.9,'cvinn':.1,'en':1.,'enb':0.},'353':{'vout':.45,'main_dbg':.45,'pre_dbg':.45,'post_dbg':.45}}
  for sid,outputs in literal.items():
   with self.subTest(source=sid):
    rows=[{'time':i*2e-12,**inputs,**outputs} for i in range(1001)]
    result=mod.evaluate(rows,{'source_id':sid,'stop':2e-9,'signals':list(rows[0].keys()-{'time'}),'resolution':2e-12},Path('.'))
    self.assertTrue(result['passed'],result['failures'])
    node=next(iter(outputs))
    for row in rows:row[node]+=0.1
    self.assertFalse(mod.evaluate(rows,{'source_id':sid,'stop':2e-9,'signals':list(rows[0].keys()-{'time'}),'resolution':2e-12},Path('.'))['passed'])


class ReviewTransitionTests(unittest.TestCase):
 def load(self):
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod);return mod
 @staticmethod
 def ramp(t,start,a,b,width=1e-10):return a+(b-a)*max(0,min(1,(t-start)/width))
 def clock_rows(self):
  rows=[]
  for i in range(3001):
   t=i*2e-12;clk=self.ramp(t,1e-9,0,.9) if t<4e-9 else self.ramp(t,4e-9,.9,0)
   phi1=self.ramp(t,2e-9,0,.9) if t<4.05e-9 else self.ramp(t,4.05e-9,.9,0)
   metric=0
   for start,a,b in [(1.05e-9,0,.9),(2e-9,.9,0),(4.05e-9,0,.9),(5e-9,.9,0)]:
    if t>=start:metric=self.ramp(t,start,a,b)
   rows.append(dict(time=t,clk_in=clk,rst=0.,enable=.9,phi1=phi1,phi2=self.ramp(t,5e-9,0,.9),deadtime_metric=metric,valid=self.ramp(t,2e-9,0,.9)))
  return rows,dict(source_id='375',stop=6e-9,signals=list(rows[0].keys()-{'time'}),resolution=2e-12)
 def test_clock_handoff_never_exempts_short_overlap(self):
  rows,case=self.clock_rows();m=self.load()
  self.assertTrue(m.evaluate(rows,case,Path('.'))['passed'])
  for row in rows:
   if 4.06e-9<=row['time']<=4.10e-9:row['phi2']=.9
  result=m.evaluate(rows,case,Path('.'));self.assertFalse(result['passed'])
  self.assertTrue(any(x.get('kind')=='phase_overlap' for x in result['failures']))
 def pga_rows(self):
  rows=[]
  for i in range(2001):
   t=i*2e-12;vin=.85+max(0,min(.10,(t-1e-9)*1e8))
   rows.append(dict(time=t,clk=0.,rst=0.,gain_sel=0.,vin=vin,out=min(.9,vin),metric=self.ramp(t,1.5e-9,0,.9,2e-10)))
  return rows,dict(source_id='038',stop=4e-9,signals=list(rows[0].keys()-{'time'}),resolution=2e-12)
 def test_pga_clipping_metric_may_smooth_at_analog_boundary(self):
  rows,case=self.pga_rows();m=self.load()
  self.assertTrue(m.evaluate(rows,case,Path('.'))['passed'])
  for row in rows:row['metric']=0.
  self.assertFalse(m.evaluate(rows,case,Path('.'))['passed'])
 def test_pga_continuous_output_is_checked_during_metric_transition(self):
  rows,case=self.pga_rows()
  for row in rows:
   if 1.52e-9<=row['time']<=1.56e-9:row['out']=.7
  result=self.load().evaluate(rows,case,Path('.'))
  self.assertFalse(result['passed']);self.assertTrue(any(x.get('node')=='out' for x in result['failures']))


class PgaBoundaryHistoryTests(unittest.TestCase):
 load=ReviewTransitionTests.load
 ramp=staticmethod(ReviewTransitionTests.ramp)
 def test_initial_clipping_monitor_may_smooth_then_must_hold(self):
  rows=[]
  for i in range(1001):
   t=i*2e-12
   rows.append(dict(time=t,clk=0.,rst=0.,gain_sel=0.,vin=.95,out=.9,metric=self.ramp(t,0,0,.9,2e-10)))
  case=dict(source_id='038',stop=2e-9,signals=list(rows[0].keys()-{'time'}),resolution=2e-12)
  self.assertTrue(self.load().evaluate(rows,case,Path('.'))['passed'])
  for row in rows:
   if row['time']>2.3e-10:row['metric']=0.
  self.assertFalse(self.load().evaluate(rows,case,Path('.'))['passed'])
 def test_leaving_clip_region_has_its_own_metric_fall_window(self):
  rows=[]
  for i in range(2001):
   t=i*2e-12;vin=.95-max(0,min(.10,(t-1e-9)*1e8))
   metric=self.ramp(t,0,0,.9,2e-10) if t<1.5e-9 else self.ramp(t,1.5e-9,.9,0,2e-10)
   rows.append(dict(time=t,clk=0.,rst=0.,gain_sel=0.,vin=vin,out=min(.9,vin),metric=metric))
  case=dict(source_id='038',stop=4e-9,signals=list(rows[0].keys()-{'time'}),resolution=2e-12)
  self.assertTrue(self.load().evaluate(rows,case,Path('.'))['passed'])

class HystereticPulseTests(unittest.TestCase):
 def test_stretched_input_pulse_returns_low_after_one_nanosecond(self):
  # Independent PWL arithmetic: 9.84ns + (.41-.28)/(.43-.28)*7.38ns = 16.236ns.
  rows=[]
  for i in range(15001):
   t=i*2e-12;vin=.28+.15*max(0,min(1,(t-9.84e-9)/7.38e-9))
   inside=ReviewTransitionTests.ramp(t,16.236e-9,0,.9,2e-10)
   pulse=inside if t<17.236e-9 else ReviewTransitionTests.ramp(t,17.236e-9,.9,0,2e-10)
   rows.append(dict(time=t,vin=vin,rst=0.,enable=.9,low_trip=.40,high_trip=.62,inside_flag=inside,state_metric=inside,toggled=pulse))
  case=dict(source_id='314',stop=30e-9,signals=list(rows[0].keys()-{'time'}),resolution=2e-12)
  mod=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(mod)
  self.assertTrue(mod.evaluate(rows,case,Path('.'))['passed'])
  for row in rows:
   if row['time']>=17.236e-9:row['toggled']=.9
  result=mod.evaluate(rows,case,Path('.'))
  self.assertFalse(result['passed']);self.assertTrue(any(f.get('node')=='toggled' for f in result['failures']))

if __name__=='__main__':unittest.main()

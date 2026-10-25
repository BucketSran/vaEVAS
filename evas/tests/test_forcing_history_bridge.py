"""A physical mid-ramp sample remains held beside source polynomial forcing."""
GUARDS = ["LANG", "ANALOG", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]
from fractions import Fraction as F
from pathlib import Path
import copy,unittest
from evas import Instance,compile_sources,transient,KernelError
from initial_named_batches_contract import check_named_initial_batches
KERNEL=Path(__file__).resolve().parents[2]/'evas/rust_core/target/debug/evas-kernel'
SOURCE='''`include "disciplines.vams"
module sample(a,b,c,y,s); input a,b,c; output y,s; electrical a,b,c,y,s; real q,r;
analog begin
 @(initial_step) begin q=0; r=0; end
 @(cross(V(c)-0.25,+1)) q=1;
 @(cross(V(c)-0.5,+1)) r=V(s);
 V(s)<+transition(q,0,0.5,0.5);
 V(y)<+V(a)*V(b)+transition(r,0,0.125,0.125);
end endmodule
'''
INPUTS={'a':[[0,0],[1,1]],'b':[[0,1],[1,0]],'c':[[0,0],[1,1]]}
class ForcingHistoryBridge(unittest.TestCase):
 def program(self,source=SOURCE):
  return compile_sources({'independent-mid-history.va':source},[Instance('dut','sample',{n:n for n in 'abcys'},{})])
 def run_sample(self,times):
  p=self.program()
  result=transient(p,INPUTS,times,stop=1,max_step=1,kernel=KERNEL)
  result=check_named_initial_batches(result,p,dict(q=0,r=0),[])
  for t,row,box in zip(times,result['solutions'],result['observation_evidence']['voltage_bounds_V']):
   t=F(t);expected={'s':min(F(1),max(F(0),2*(t-F(1,4)))), 'y':t*(1-t)+min(F(1,2),max(F(0),4*(t-F(1,2))))}
   for name,want in expected.items():
    n=result['nodes'].index(name)
    self.assertLessEqual(abs(row['voltages'][n]-float(want)),1e-10)
    self.assertLessEqual(F.from_float(box[n][0]),want)
    self.assertGreaterEqual(F.from_float(box[n][1]),want)
  self.assertEqual([r['time']for r in result['transient']['events']],[.25,.5])
  return result
 def test_actual_mid_history_point_box_and_hold(self):
  self.run_sample([0,.25,.375,.5,.5625,.625,.75,1])
 def test_extra_queries_preserve_history_and_complete_phase_box(self):
  sparse=[0,.25,.5,.75,1];dense=[i/32 for i in range(33)]
  a=self.run_sample(sparse);b=self.run_sample(dense)
  self.assertEqual(a['transient']['events'],b['transient']['events'])
  self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)]for t in sparse])
  self.assertEqual(a['observation_evidence']['voltage_bounds_V'],[b['observation_evidence']['voltage_bounds_V'][dense.index(t)]for t in sparse])
 def test_hidden_zero_output_read_still_rejected(self):
  p=self.program().to_dict();marker=next(c['rhs']for c in p['contributions']if c['rhs']['op']=='forcing')
  marker['checked']=[*marker['checked'],dict(op='affine',constant=0,terms=[dict(node=p['nodes'].index('y'),coefficient=0)])]
  with self.assertRaises(KernelError)as e:transient(type('RawProgram',(),{'to_dict':lambda self:p})(),INPUTS,[0,1],stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.unsupported_forcing_scope')
 def test_internal_history_cross_retains_independent_calendar_rejection(self):
  p=self.program(SOURCE.replace('cross(V(c)-0.5','cross(V(s)-0.5'))
  with self.assertRaises(KernelError)as e:transient(p,INPUTS,[0,1],stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.unsupported_forcing_scope')

 def test_malformed_history_alias_indices_rejected_before_expansion(self):
  p=self.program().to_dict();alias=next(c for c in p['contributions']if p['nodes'][c['positive'] if c['negative']==0 else c['negative']]=='s')
  alias['rhs']=dict(op='affine',constant=0,terms=[dict(node=len(p['nodes'])+7,coefficient=0)])
  with self.assertRaises(KernelError)as e:transient(type('RawProgram',(),{'to_dict':lambda self:p})(),INPUTS,[0,1],stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.invalid_ir')
 def test_cyclic_history_alias_rejected(self):
  p=self.program().to_dict();n=p['nodes'].index('s');alias=next(c for c in p['contributions']if n in (c['positive'],c['negative']))
  alias['rhs']=dict(op='affine',constant=0,terms=[dict(node=n,coefficient=1)])
  with self.assertRaises(KernelError)as e:transient(type('RawProgram',(),{'to_dict':lambda self:p})(),INPUTS,[0,1],stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.unsupported_condition')
 def test_numeric_checked_history_is_not_a_source_footprint(self):
  for hidden in [False,True]:
   with self.subTest(hidden=hidden):
    p=self.program().to_dict();m=next(c['rhs']for c in p['contributions']if c['rhs']['op']=='forcing');s=p['nodes'].index('s')
    bad=dict(op='affine',constant=0,terms=[dict(node=s,coefficient=0 if hidden else 1)])
    if hidden:bad=dict(op='select',relation='gt',left=dict(op='affine',constant=1,terms=[]),right=dict(op='affine',constant=0,terms=[]),then_value=dict(op='affine',constant=0,terms=[]),else_value=bad,origin=m['origin'])
    m['checked']=[*m['checked'],bad]
    with self.assertRaises(KernelError)as e:transient(type('RawProgram',(),{'to_dict':lambda self:p})(),INPUTS,[0,1],stop=1,max_step=1,kernel=KERNEL)
    self.assertEqual(e.exception.diagnostic['code'],'kernel.unsupported_forcing_scope')
 def test_nonpoint_cold_seed_retains_explicit_initial_history_rejection(self):
  source=SOURCE.replace('@(cross(V(c)-0.25','@(timer(0,0)) q=V(a)+0.125;\n @(cross(V(c)-0.25')
  p=self.program(source);inputs=dict(INPUTS,a=[[0,2**-60],[1,2**-60]])
  with self.assertRaises(KernelError)as e:transient(p,inputs,[0,1],stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.unsupported_initial_history')
  self.assertIn('finite final point state certificates',e.exception.diagnostic['message'])

TARGET_SOURCE='''`include "disciplines.vams"
module target(a,b,c,y,s); input a,b,c; output y,s; electrical a,b,c,y,s; real q; integer n;
analog begin
 @(initial_step) begin q=0; n=-3; end
 @(cross(V(c)-0.25,+1)) begin q=1; n=-2; end
 @(cross(V(c)-0.75,+1)) begin q=0; n=3; end
 V(s)<+transition(q,0,0.5,0.5);
 V(y)<+V(a)*V(b)-(1-V(b))*transition(TARGET,0,0.125,0.125);
end endmodule
'''
def target_program(mode):
 if mode=='history':
  parent='`include "disciplines.vams"\nmodule parent(c,s); input c; output s; electrical c,s; real q; analog begin @(initial_step) q=0; @(cross(V(c)-0.25,+1)) q=1; @(cross(V(c)-0.75,+1)) q=0; V(s)<+transition(q,0,0.5,0.5); end endmodule'
  child='`include "disciplines.vams"\nmodule consumer(a,b,s,y); input a,b,s; output y; electrical a,b,s,y; analog begin V(y)<+V(a)*V(b)-(1-V(b))*transition(V(s)>0.5 ? 1:0,0,0.125,0.125); end endmodule'
  return compile_sources({'independent-parent.va':parent,'independent-consumer.va':child},[Instance('p','parent',dict(c='c',s='s'),{}),Instance('d','consumer',dict(a='a',b='b',s='s',y='y'),{})])
 target={'bare':'q','ordinary':'q>0.5 ? 1:0','typed':'(n&1) ? 1:0','native':'(n&1) ? 1:0'}[mode]
 source=TARGET_SOURCE.replace('TARGET',target)
 if mode=='native':source=source.replace('n=-3','n=-9999').replace('n=-2','n=-10000').replace('n=3','n=9999')
 return compile_sources({'independent-target-'+mode+'.va':source},[Instance('dut','target',{n:n for n in 'abcys'},{})])
TARGET_INPUTS={'a':[[0,0],[1.25,1.25]],'b':[[0,1],[1.25,-0.25]],'c':[[0,0],[1.25,1.25]]}

class ForcingTargetComposition(unittest.TestCase):
 def run_modes(self,mode,times):
  p=target_program(mode)
  if mode=='native':self.assertIn("'op': 'integer_primitive'",str(p.to_dict()['operators']))
  result=transient(p,TARGET_INPUTS,times,stop=1.25,max_step=1,kernel=KERNEL)
  initial=dict(q=0) if mode=='history' else dict(q=0,n=-9999 if mode=='native' else -3)
  result=check_named_initial_batches(result,p,initial,[])
  def ramp(t,start):return min(F(1),max(F(0),8*(t-start)))
  for t,row,box in zip(times,result['solutions'],result['observation_evidence']['voltage_bounds_V']):
   t=F(t);parent=min(F(1),max(F(0),2*(t-F(1,4))))-min(F(1),max(F(0),2*(t-F(3,4))))
   if mode in ['typed','native']:held=1-ramp(t,F(1,4))+ramp(t,F(3,4))
   elif mode=='history':held=ramp(t,F(1,2))-ramp(t,F(1))
   else:held=ramp(t,F(1,4))-ramp(t,F(3,4))
   want=t*(1-t)-t*held
   for name,value in [('s',parent),('y',want)]:
    n=result['nodes'].index(name)
    self.assertLessEqual(abs(row['voltages'][n]-float(value)),1e-10)
    self.assertLessEqual(F.from_float(box[n][0]),value)
    self.assertGreaterEqual(F.from_float(box[n][1]),value)
  self.assertEqual([e['time']for e in result['transient']['events']],[.25,.75])
  return result
 def test_bare_two_events_preserve_nonzero_residual_source_offset_and_boxes(self):
  self.run_modes('bare',[0,.25,.375,.5,.75,.8125,.875,1,1.25])
 def test_ordinary_held_select_target_uses_actual_phase_and_full_residual(self):
  self.run_modes('ordinary',[0,.25,.375,.5,.75,.8125,.875,1,1.25])
 def test_typed_signed_target_rebinds_after_two_state_changes(self):
  self.run_modes('typed',[0,.25,.375,.5,.75,.8125,.875,1,1.25])
 def test_producer_native_wide_integer_target_uses_signed_actual_epoch(self):
  self.run_modes('native',[0,.25,.375,.5,.75,.8125,.875,1,1.25])
 def test_second_layer_history_target_and_physical_coefficient_parent_reset(self):
  self.run_modes('history',[0,.25,.5,.5625,.625,.75,1,1.0625,1.125,1.25])
 def test_extra_queries_preserve_all_modes_and_common_original_boxes(self):
  sparse=[0,.25,.5,.75,1,1.25];dense=[i/32 for i in range(41)]
  for mode in ['bare','ordinary','typed','native','history']:
   with self.subTest(mode=mode):
    a=self.run_modes(mode,sparse);b=self.run_modes(mode,dense)
    self.assertEqual(a['transient']['events'],b['transient']['events'])
    self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)]for t in sparse])
    self.assertEqual(a['observation_evidence']['voltage_bounds_V'],[b['observation_evidence']['voltage_bounds_V'][dense.index(t)]for t in sparse])

class ForcingTypedRoleControls(unittest.TestCase):
 def test_each_integer_child_overflow_is_checked_before_zero_mask(self):
  raw=target_program('typed').to_dict()
  state=next(i for i,s in enumerate(raw['states'])if s['name']=='n')
  raw['states'][state]['initial']=2147483647
  o=next(o for o in raw['operators']if o['input']['op']=='select')
  origin=o['input']['origin']
  primitive=dict(op='integer_primitive',function='bit_and',origin=origin);o['input']=primitive
  primitive['args']=[dict(op='integer_primitive',function='add',args=[dict(op='integer_state',state=state),dict(op='integer_literal',value=1)],origin=origin),dict(op='integer_literal',value=0)]
  p=type('RawProgram',(),{'to_dict':lambda self:raw})()
  with self.assertRaises(KernelError)as e:transient(p,TARGET_INPUTS,[0,.375],stop=.375,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.integer_range')
 def test_raw_round_in_unselected_typed_target_arm_keeps_strict_assignment_role(self):
  p=target_program('typed').to_dict();o=next(o for o in p['operators']if o['input']['op']=='select')
  o['input']['else_value']=dict(op='integer_round',value=dict(op='affine',constant=0,terms=[]),origin=o['origin'])
  with self.assertRaises(KernelError)as e:transient(type('RawProgram',(),{'to_dict':lambda self:p})(),TARGET_INPUTS,[0,.375],stop=.375,max_step=1,kernel=KERNEL)
  self.assertEqual(e.exception.diagnostic['code'],'kernel.invalid_ir')
  self.assertIn('only allowed as the RHS root of a scalar integer assignment',str(e.exception))

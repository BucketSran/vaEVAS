"""Public source -> kernel contract for a bounded trim consuming physical history."""
GUARDS = ['LANG', 'EVENT-ORDER', 'COMPOSE', 'TIMED-OPERATOR']
import unittest
from evas import compile_sources,Instance,transient,CompileError
from test_affine import KERNEL

SOURCE='''`include "disciplines.vams"
module m(clk,temp,por,core,corr,bit0,bit1,ready,error_metric,y);
input clk,temp;output por,core,corr,bit0,bit1,ready,error_metric,y;
electrical clk,temp,por,core,corr,bit0,bit1,ready,error_metric,y;
integer count,code,ready_count;
real ready_value,err_value,ref_value,corr_value;
analog begin
 @(initial_step)begin count=0;code=0;ready_count=0;ready_value=0;end
 @(cross(V(clk)-0.5,+1))begin
  if(count<2)count=count+1;
  err_value=0.625-(V(core)+code*0.0625);
  if(V(por)<=0.5)begin code=0;ready_count=0;ready_value=0;end
  else begin
   if(err_value>0.03125 && code<15)code=code+1;
   else if(err_value < -0.03125 && code>0)code=code-1;
   err_value=0.625-(V(core)+code*0.0625);
   if(err_value<=0.03125 && err_value >= -0.03125)begin
    if(ready_count<2)ready_count=ready_count+1;
    if(ready_count>=2)ready_value=1;
   end else begin ready_count=0;ready_value=0;end
  end
 end
 V(por)<+transition((count>=2)?1:0,0,0.125,0.125);
 ref_value=0.5+0.03125*V(temp);
 if(V(por)>0.5)V(core)<+ref_value;else V(core)<+0;
 corr_value=code*0.0625;
 err_value=0.625-(V(core)+corr_value);
 V(corr)<+corr_value;
 V(error_metric)<+err_value;
 V(bit0)<+transition(code%2,0,0.125,0.125);
 V(bit1)<+transition((code/2)%2,0,0.125,0.125);
 V(ready)<+transition(ready_value,0,0.125,0.125);
 ref_value=V(core)+V(corr);
 if(ref_value>0.625)ref_value=0.625;
 if(ref_value<0)ref_value=0;
 V(y)<+ref_value;
end endmodule'''
PORTS='clk temp por core corr bit0 bit1 ready error_metric y'.split()
def build(source=SOURCE):
 return compile_sources({'history-source.va':source},[Instance('M','m',dict(zip(PORTS,PORTS)))])
def run(program,source_errors=None):
 clock=[[0,0]]
 for t in (.25,.5,.75,1.,1.25,1.5):
  clock.extend([[t-.03125,0],[t+.03125,1],[t+.0625,0]])
 clock.append([1.75,0])
 times=[0,.25,.5,.5625,.625,.75,.875,1.,1.125,1.25,1.375,1.5,1.75]
 return transient(program,{'clk':clock,'temp':[[0,.5],[1.75,.5]]},times,stop=1.75,max_step=.03125,kernel=KERNEL,source_errors=source_errors)
class HistoryConsumer(unittest.TestCase):
 def test_public_source_bounded_trim_ready_bits_and_top_clamp(self):
  p=build()
  self.assertTrue(p._native_audit.active)
  self.assertFalse(any(getattr(op.input,'op',None)=='integer_primitive' for op in p.operators))
  result=run(p)
  nodes=result['nodes']
  def values(name):return [r['voltages'][nodes.index(name)] for r in result['solutions']]
  self.assertEqual(values('corr'),[0,0,0,0,0,.0625,.0625,.125,.125,.125,.125,.125,.125])
  self.assertEqual(values('core'),[0,0,0,0,.515625,.515625,.515625,.515625,.515625,.515625,.515625,.515625,.515625])
  self.assertEqual(values('y'),[0,0,0,0,.515625,.578125,.578125,.625,.625,.625,.625,.625,.625])
  self.assertEqual(values('bit0'),[0,0,0,0,0,0,1,1,0,0,0,0,0])
  self.assertEqual(values('bit1'),[0,0,0,0,0,0,0,0,1,1,1,1,1])
  self.assertEqual(values('ready'),[0,0,0,0,0,0,0,0,0,0,1,1,1])
  self.assertEqual(values('error_metric'),[.625,.625,.625,.625,.109375,.046875,.046875,-.015625,-.015625,-.015625,-.015625,-.015625,-.015625])
  self.assertTrue(all(row['max_residual_ratio']<=1 for row in result['solutions']))
 def test_original_zero_trip_loop_is_rejected_before_scalarization(self):
  with self.assertRaises(CompileError):
   build(SOURCE.replace('integer count,code,ready_count;','integer count,code,ready_count,i;').replace('V(y)<+ref_value;','for(i=0;i<0;i=i+1)ref_value=1;V(y)<+ref_value;'))
 def test_original_discarded_bilinear_alias_is_rejected(self):
  with self.assertRaisesRegex(CompileError,'jointly affine'):
   build(SOURCE.replace('V(y)<+ref_value;','ref_value=V(por)*V(temp);V(y)<+0;'))
 def test_original_discarded_floating_read_reaches_public_kernel_rejection(self):
  p=build(SOURCE.replace('integer count,code,ready_count;','electrical hidden;integer count,code,ready_count;').replace('V(y)<+ref_value;','ref_value=V(hidden);V(y)<+0;'))
  with self.assertRaisesRegex(Exception,'acyclic|unsupported_condition'):
   run(p)

 def test_uncertain_original_clock_source_keeps_the_existing_scope_refusal(self):
  from evas.errors import KernelError
  with self.assertRaisesRegex(KernelError,'unsupported_source_uncertainty'):
   run(build(),{'clk':1e-12})

class HistoryDispatchBudget(unittest.TestCase):
 def test_dispatch_reuses_affinity_without_walking_trees(self):
  from unittest.mock import Mock,patch
  from types import SimpleNamespace
  from evas.instance_compiler import InstanceCompiler
  compilation=SimpleNamespace(native_audit=Mock(),history_consumer_candidate=False,
                              has_waveform_operators=True,nodes=("0","y"))
  compiler=SimpleNamespace(compilation=compilation)
  with patch('evas.instance_compiler._predicate_degree',side_effect=AssertionError('unpaid repeated tree walk')):
   self.assertFalse(InstanceCompiler.history_condition_candidate(compiler,False,None,{1}))
   self.assertFalse(compilation.history_consumer_candidate)
   self.assertTrue(InstanceCompiler.history_condition_candidate(compiler,True,None,{1}))
   self.assertTrue(compilation.history_consumer_candidate)

 def test_dispatch_rejects_unknown_nodes_and_absent_history_without_rescanning(self):
  from unittest.mock import Mock,patch
  from types import SimpleNamespace
  from evas.instance_compiler import InstanceCompiler
  compilation=SimpleNamespace(native_audit=Mock(),history_consumer_candidate=False,
                              has_waveform_operators=True,nodes=('0','y'))
  compiler=SimpleNamespace(compilation=compilation)
  with patch('evas.instance_compiler._predicate_degree',side_effect=AssertionError('unpaid repeated tree walk')):
   for nodes in ({999},{-1}):
    self.assertFalse(InstanceCompiler.history_condition_candidate(compiler,True,None,nodes))
   compilation.has_waveform_operators=False
   self.assertFalse(InstanceCompiler.history_condition_candidate(compiler,True,None,{1}))
   self.assertFalse(compilation.history_consumer_candidate)

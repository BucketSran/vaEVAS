"""A dominated event scratch and ordinary alias keep their source-order roles."""
GUARDS=["LANG", "EVENT-ORDER", "COMPOSE"]
import unittest
from evas import compile_sources, Instance, transient, CompileError
from test_affine import KERNEL

HEAD='`include "disciplines.vams"\nmodule m(u,y,z);input u;output y,z;electrical u,y,z;real e,q;analog begin @(initial_step)q=0;'
TAIL='e=2*V(u);V(y)<+e;V(z)<+q;end endmodule'
def build(body,tail=TAIL):
 return compile_sources({'scratch.va':HEAD+'@(timer(0.25))begin '+body+' end '+tail},[Instance('M','m',dict(u='u',y='y',z='z'))])
class EventOrdinaryScratch(unittest.TestCase):
 def test_callback_reads_its_write_and_output_uses_ordinary_alias(self):
  p=build('e=V(u)+1;q=e;')
  self.assertEqual([s.name for s in p.states],['e','q'])
  result=transient(p,{'u':[[0,.5],[1,.5]]},[0,.125,.25,.5,1],stop=1,max_step=.125,kernel=KERNEL)
  y=result['nodes'].index('y');z=result['nodes'].index('z')
  self.assertEqual([r['voltages'][y] for r in result['solutions']],[1]*5)
  self.assertEqual([r['voltages'][z] for r in result['solutions']],[0,0,1.5,1.5,1.5])
 def test_both_conditional_writes_dominate_the_later_callback_read(self):
  p=build('if(V(u)>0)e=1;else e=2;q=e;')
  self.assertEqual(len(p.states),2)
 def test_callback_old_read_is_rejected(self):
  with self.assertRaisesRegex(CompileError,'same-callback write'):
   build('q=e;e=V(u)+1;')
 def test_incomplete_callback_write_is_rejected(self):
  with self.assertRaisesRegex(CompileError,'same-callback write'):
   build('if(V(u)>0)e=1;q=e;')
 def test_unselected_else_old_read_is_rejected(self):
  with self.assertRaisesRegex(CompileError,'same-callback write'):
   build('if(V(u)>0)q=1;else q=e;e=1;')
 def test_ordinary_read_before_assignment_is_rejected(self):
  with self.assertRaisesRegex(CompileError,'not assigned before use'):
   build('e=1;q=e;',tail='V(y)<+e;e=2*V(u);V(z)<+q;end endmodule')
 def test_earlier_ordinary_writer_is_rejected(self):
  source=HEAD+'e=2*V(u);@(timer(0.25))begin e=1;q=e;end V(y)<+e;V(z)<+q;end endmodule'
  with self.assertRaisesRegex(CompileError,'follow callback'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])

 def test_initial_only_total_alias_preserves_its_initial_state(self):
  source=HEAD+'@(initial_step)e=1;e=2;V(y)<+e;V(z)<+q;end endmodule'
  program=compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
  self.assertEqual([(state.name,state.initial) for state in program.states],[('e',1.),('q',0.)])
 def test_zero_trip_original_loop_old_read_is_rejected(self):
  source=HEAD.replace('real e,q;','real e,q;integer i;')+'@(timer(0.25))begin for(i=0;i<0;i=i+1)q=e;e=1;q=e;end '+TAIL
  with self.assertRaisesRegex(CompileError,'scratch loop'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
 def test_scratch_event_trigger_is_rejected(self):
  source=HEAD+'@(cross(e-0.5,+1))begin e=1;q=e;end '+TAIL
  with self.assertRaisesRegex(CompileError,'scratch cannot drive an event trigger'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
 def test_scratch_does_not_become_an_instance_constant_setting(self):
  with self.assertRaises(CompileError):
   build('e=1;q=e;',tail='e=2*V(u);V(y)<+transition(q,0,e,e);V(z)<+q;end endmodule')

 def test_zero_trip_ordinary_loop_cannot_hide_an_undefined_scratch_read(self):
  source=HEAD.replace('real e,q;','real e,q,a;integer i;')+'@(timer(0.25))begin e=1;q=e;end for(i=0;i<0;i=i+1)a=e;'+TAIL
  with self.assertRaisesRegex(CompileError,'scratch loop'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])

 def test_scalarized_array_cannot_bypass_the_callback_old_read_check(self):
  head=HEAD.replace('real e,q;','real e[0:0],q;')
  tail=TAIL.replace('e=','e[0]=').replace('<+e;','<+e[0];')
  source=head+'@(timer(0.25))begin q=e[0];e[0]=1;end '+tail
  with self.assertRaisesRegex(CompileError,'original scalar identity without arrays'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
 def test_scalarized_array_cannot_bypass_original_writer_order(self):
  head=HEAD.replace('real e,q;','real e[0:0],q;')
  source=head+'e[0]=2*V(u);@(timer(0.25))begin e[0]=1;q=e[0];end V(y)<+e[0];V(z)<+q;end endmodule'
  with self.assertRaisesRegex(CompileError,'original scalar identity without arrays'):
   compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
 def test_dead_loop_proof_pays_for_the_original_rhs_before_lowering(self):
  counts=[]
  for terms in (8,64):
   source=HEAD.replace('real e,q;','real e,q,a;integer i;')+'@(timer(0.25))begin e=1;q=e;end for(i=0;i<0;i=i+1)a='+ '+'.join(['V(u)']*terms)+';'+TAIL
   program=compile_sources({'scratch.va':source},[Instance('M','m',dict(u='u',y='y',z='z'))])
   self.assertTrue(program._native_audit.active)
   counts.append((program._native_audit.used,program._native_audit.counts['ordinary_scratch_visit']))
  self.assertGreaterEqual(counts[1][1]-counts[0][1],56)
  self.assertGreaterEqual(counts[1][0]-counts[0][0],counts[1][1]-counts[0][1])

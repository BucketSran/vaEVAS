"""Initial node consumers retain the pre-existing held table seed contract."""
import os,unittest
from pathlib import Path
from unittest.mock import patch
from evas import compile_sources,Instance,transient,CompileError
from evas import held_power2
from test_held_power2_targets import primitive_count
from test_affine import KERNEL as DEFAULT_KERNEL
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(DEFAULT_KERNEL)))
GUARDS=['LANG','LIN','TRANSITION','COMPOSE']
LOAD='module load(ctrl,y);input ctrl;output y;electrical ctrl,y;integer q;EXTRA analog begin INITIAL V(y)<+q;end endmodule'
DRIVE='module drive(ctrl);output ctrl;electrical ctrl;integer s;analog begin @(initial_step)s=1;V(ctrl)<+transition(s%2,0,0.1,0.1);end endmodule'
def build(initial='@(initial_step)begin q=0;if(V(ctrl)>0.5)q=1;end',reverse=False,module_reverse=False,extra=''):
 load=LOAD.replace('INITIAL',initial).replace('EXTRA',extra)
 source='`include "disciplines.vams"\n'+(('\n'.join((DRIVE,load))) if module_reverse else ('\n'.join((load,DRIVE))))
 instances=[Instance('D','load',dict(ctrl='ctrl',y='y')),Instance('E','drive',dict(ctrl='ctrl'))]
 if reverse:instances.reverse()
 return compile_sources({'initial-modulo.va':source},instances)
def answers(program):
 r=transient(program,{},[0,1],stop=1,max_step=1,kernel=KERNEL)
 return [row['voltages'][r['nodes'].index('y')] for row in r['solutions']]
class InitialCompactCompatibility(unittest.TestCase):
 def test_exact_old_initial_node_contract_in_both_instance_and_module_orders(self):
  for reverse in (False,True):
   for module_reverse in (False,True):
    with self.subTest(reverse=reverse,module_reverse=module_reverse):
     p=build(reverse=reverse,module_reverse=module_reverse)
     self.assertEqual(primitive_count(p.operators),0)
     self.assertEqual(answers(p),[1,1])

 def test_direct_initial_comparison_assignment_keeps_the_same_seed(self):
  for reverse in (False,True):
   p=build('@(initial_step)q=(V(ctrl)>0.5);',reverse=reverse)
   self.assertEqual(primitive_count(p.operators),0);self.assertEqual(answers(p),[1,1])

 def test_unselected_initial_voltage_arm_still_excludes_compact(self):
  for reverse in (False,True):
   p=build('@(initial_step)begin q=1;if(0>1)q=(V(ctrl)>0.5);end',reverse=reverse)
   self.assertEqual(primitive_count(p.operators),0);self.assertEqual(answers(p),[1,1])

 def test_zero_trip_original_initial_loop_keeps_old_gate_and_role_scan(self):
  initial='@(initial_step)begin q=1;for(i=0;i<0;i=i+1)q=(V(ctrl)>0.5);end'
  # Existing initialization-loop source admission already rejects voltage
  # values. Preserve that gate; this change does not add loop mathematics.
  with self.assertRaisesRegex(CompileError,'initialization loop values'):
   build(initial,extra='integer i;')
  # Also test the original pre-elaboration loop at the representation seam.
  from evas.frontend import parse_sources
  from test_held_power2_history_compat import unit,binding
  original=held_power2.compatible_program;captured=[]
  def observe(compiler,source):
   captured.append((compiler,source));return original(compiler,source)
  with patch.object(held_power2,'compatible_program',side_effect=observe):
   compile_sources({'unit.va':unit()},[binding()])
  model=parse_sources({'load.va':'`include "disciplines.vams"\n'+LOAD.replace('EXTRA','integer i;').replace('INITIAL',initial)})['load']
  compiler,source=captured[-1]
  roots=compiler.compilation.held_power2_source_models['unit'].initial
  roots.append(model.initial[1])
  self.assertFalse(original(compiler,source))
  roots.pop();self.assertTrue(original(compiler,source))

 def test_initial_source_mutation_is_fresh_without_semantic_cache(self):
  from test_held_power2_history_compat import unit,binding
  captured=[];original=held_power2.compatible_program
  def observe(compiler,source):
   captured.append((compiler,source));return original(compiler,source)
  with patch.object(held_power2,'compatible_program',side_effect=observe):
   compile_sources({'unit.va':unit()},[binding()])
  compiler,source=captured[-1]
  from evas.frontend import parse_sources
  assignment=parse_sources({'unit.va':unit(event='@(initial_step)q=(V(a)>0.5);')})['unit'].initial[0]
  initial=compiler.compilation.held_power2_source_models['unit'].initial
  initial.append(assignment);self.assertFalse(original(compiler,source))
  initial.pop();self.assertTrue(original(compiler,source))

 def test_retained_initial_event_body_is_in_the_initial_role(self):
  from test_held_power2_history_compat import unit,binding
  from evas.frontend import parse_sources
  from evas.syntax import Event,Trigger
  captured=[];original=held_power2.compatible_program
  def observe(compiler,source):
   captured.append((compiler,source));return original(compiler,source)
  with patch.object(held_power2,'compatible_program',side_effect=observe):
   compile_sources({'unit.va':unit()},[binding()])
  assignment=parse_sources({'unit.va':unit(event='@(initial_step)q=(V(a)>0.5);')})['unit'].initial[0]
  initial_event=Event((Trigger('initial_step',(),assignment.token),),(assignment,),assignment.token)
  compiler,source=captured[-1]
  roots=compiler.compilation.held_power2_source_models['unit'].analog
  roots.append(initial_event);self.assertFalse(original(compiler,source))
  roots.pop();self.assertTrue(original(compiler,source))

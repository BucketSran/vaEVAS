"""Whole-source held representation exclusion is independent of binding order."""
import os,unittest
from pathlib import Path
from unittest.mock import patch
from evas import compile_sources,Instance,transient,CompileError
from evas import held_power2
from test_held_power2_targets import primitive_count
import test_history_consumer as history
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(history.KERNEL)))
GUARDS=['LANG','TRANSITION','EVENT-ORDER','COMPOSE']
def unit(extra='',body='',event='@(initial_step)q=3;'):
 return '`include "disciplines.vams"\nmodule unit(a,z);input a;output z;electrical a,z;integer q;real unused;'+extra+'analog begin '+event+body+' V(z)<+transition(q%2,0,0.01,0.01);end endmodule'
def binding():return Instance('B','unit',dict(a='clk',z='z'))
def combined(reverse=False,source_reverse=False,extra=''):
 sources={'history-source.va':history.SOURCE,'unit.va':unit(body=extra)}
 if source_reverse:sources=dict(reversed(list(sources.items())))
 instances=[binding(),Instance('M','m',dict(zip(history.PORTS,history.PORTS)))]
 if reverse:instances.reverse()
 return compile_sources(sources,instances)
def full_oracle(test,program):
 history.KERNEL=KERNEL
 # Reuse every existing independent numeric assertion, not only NoPrimitive.
 with patch.object(history,'build',return_value=program):
  history.HistoryConsumer.test_public_source_bounded_trim_ready_bits_and_top_clamp(test)
class HeldHistoryCompatibility(unittest.TestCase):
 def test_existing_full_source_numeric_history_contract(self):
  full_oracle(self,history.build())

 def test_all_binding_and_source_orderings_keep_complete_history_answers(self):
  for reverse in (False,True):
   for source_reverse in (False,True):
    with self.subTest(reverse=reverse,source_reverse=source_reverse):
     p=combined(reverse,source_reverse);self.assertEqual(primitive_count(p.operators),0)
     full_oracle(self,p)

 def test_hidden_alias_arm_in_other_module_is_not_dropped(self):
  for reverse in (False,True):
   p=combined(reverse,not reverse,extra='unused=(q<0)?V(a):0;')
   self.assertEqual(primitive_count(p.operators),0);full_oracle(self,p)

 def test_zero_trip_ordinary_loop_is_still_scanned_for_representation(self):
  source=unit(extra='integer i;',body='for(i=0;i<0;i=i+1)unused=V(a);')
  p=compile_sources({'unit.va':source},[binding()]);self.assertEqual(primitive_count(p.operators),0)
  r=transient(p,{'clk':[[0,0],[1,0]]},[0,1],stop=1,max_step=.25,kernel=KERNEL)
  self.assertEqual([v['voltages'][r['nodes'].index('z')] for v in r['solutions']],[1,1])

 def test_event_only_voltage_probes_keep_independent_compact_calendar(self):
  source=unit(event='@(initial_step)q=0;@(cross(V(a)-0.5,+1))if(q<3)q=q+1;')
  p=compile_sources({'unit.va':source},[binding()]);self.assertGreater(primitive_count(p.operators),0)
  r=transient(p,{'clk':[[0,0],[1,1],[1.25,1]]},[0,.75,1.25],stop=1.25,max_step=.125,kernel=KERNEL)
  self.assertEqual([v['voltages'][r['nodes'].index('z')] for v in r['solutions']],[0,1,1])

 def test_mutated_other_binding_is_fresh_and_exhaustion_stays_sticky(self):
  capture=[];original=held_power2.compatible_program
  def observe(compiler,source):
   capture.append((compiler,source));return original(compiler,source)
  with patch.object(held_power2,'compatible_program',side_effect=observe):
   p=compile_sources({'unit.va':unit()},[binding()])
  compiler,source=capture[-1];owner=p._native_audit
  model=compiler.compilation.held_power2_source_models['unit']
  from evas.frontend import parse_sources
  added=parse_sources({'other.va':unit(body='unused=V(a);')})['unit'].analog[0]
  model.analog.append(added)
  self.assertFalse(original(compiler,source))
  model.analog.pop();self.assertTrue(original(compiler,source))
  while True:
   try:p.to_dict()
   except CompileError:break
  visits=owner.counts.get('held_power2_program_expr',0)
  for _ in range(2):
   with self.assertRaises(CompileError):original(compiler,source)
   self.assertEqual(owner.counts.get('held_power2_program_expr',0),visits)
   self.assertIs(owner,p._native_audit)

 def test_no_compact_candidate_does_not_scan_original_bindings(self):
  source=unit().replace('q%2','q')
  p=compile_sources({'unit.va':source},[binding()])
  self.assertEqual(p._native_audit.counts.get('held_power2_program_dispatch',0),0)

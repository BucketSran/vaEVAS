"""Same public /% real aliases must reach existing typed held Transition consumers."""
import os,json,unittest,hashlib
from pathlib import Path
from dataclasses import is_dataclass,fields
from evas import compile_sources,Instance,transient,CompileError
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))
GUARDS=['LANG','TRANSITION','EVENT-ORDER','TIMER','COMPOSE']
def model():
 ports=['y'+str(k) for k in range(8)]
 body='@(initial_step)n=0;@(timer(1,1))if(n<=223)n=n+32;else if(n<255)n=255;'
 for k in range(8):
  rhs='n%2' if k==0 else f'(n/{2**k})%2' if k<7 else '(n>=128)'
  if k<7:rhs='('+rhs+')==1'
  body+=f'b{k}=({rhs})?1.2:0.0;V(y{k})<+transition(b{k},0,0.01,0.01);'
 return '`include "disciplines.vams"\nmodule m('+','.join(ports)+');output '+','.join(ports)+';electrical '+','.join(ports)+';integer n;real '+','.join('b'+str(k) for k in range(8))+';analog begin '+body+' end endmodule'
def program(text):return compile_sources({'eightbit-allocation.va':text},[Instance('dut','m',{'y'+str(k):'y'+str(k) for k in range(8)})])
class HeldPower2Targets(unittest.TestCase):
 def test_original_public_eightbit_real_alias_default_owner_actual_kernel(self):
  source=model();self.assertEqual(hashlib.sha256(source.encode()).hexdigest(),'fd2b6957558a3844bdbbaa36f872ac2cf1c53a8436d43a9c37160c4bc78bac93')
  p=program(source);owner=p._native_audit;before=owner.used
  r=transient(p,{},[0]+[k+.25 for k in range(1,9)],stop=8.25,max_step=.25,kernel=KERNEL)
  self.assertTrue(owner.active);self.assertLessEqual(owner.used,100000);self.assertIs(owner,p._native_audit)
  for k in range(8):
   expected=[1.2*((n//(2**k))%2) for n in [0,32,64,96,128,160,192,224,255]]
   actual=[v['voltages'][r['nodes'].index('y'+str(k))] for v in r['solutions']]
   for a,b in zip(actual,expected):self.assertAlmostEqual(a,b,places=12)
  print('power2 public owner',before,owner.used,dict(owner.counts))


def one(rhs,*,initial=0,last=255,event=None,tail='',extra=''):
 event=('@(timer(1,1))if(n<last)n=n+1;' if event is None else event)
 return '`include "disciplines.vams"\nmodule one(y);output y;electrical y;parameter integer last='+str(last)+';integer n;real b;'+extra+'analog begin @(initial_step)n='+str(initial)+';'+event+' b='+rhs+';V(y)<+transition(b,0,0.01,0.01);'+tail+'end endmodule'
def simple(text,**parameters):return compile_sources({'held-pow2.va':text},[Instance('dut','one',dict(y='y'),parameters)])
def primitive_count(value):
 from evas.ir import IntegerPrimitive
 if isinstance(value,IntegerPrimitive):return 1+sum(primitive_count(c) for c in value.args)
 if is_dataclass(value):return sum(primitive_count(getattr(value,f.name)) for f in fields(value))
 if isinstance(value,(tuple,list)):return sum(primitive_count(c) for c in value)
 return 0
class HeldPower2Boundaries(unittest.TestCase):
 def test_all_256_values_quotient_remainder_powers_including_one(self):
  ports=['y'+str(k) for k in range(16)];body='@(initial_step)n=0;@(timer(1,1))if(n<255)n=n+1;'
  for k in range(16):
   d=2**(k%8);op='/' if k<8 else '%';body+=f'b{k}=n{op}{d};V(y{k})<+transition(b{k},0,0.01,0.01);'
  source='`include "disciplines.vams"\nmodule many('+','.join(ports)+');output '+','.join(ports)+';electrical '+','.join(ports)+';integer n;real '+','.join('b'+str(k) for k in range(16))+';analog begin '+body+'end endmodule'
  p=compile_sources({'all256.va':source},[Instance('dut','many',{n:n for n in ports})]);owner=p._native_audit
  times=[0]+[k+.25 for k in range(1,256)];r=transient(p,{},times,stop=times[-1],max_step=.25,kernel=KERNEL)
  self.assertTrue(owner.active);self.assertLessEqual(owner.used,100000)
  for k in range(16):
   d=2**(k%8);want=[n//d if k<8 else n%d for n in range(256)]
   self.assertEqual([v['voltages'][r['nodes'].index('y'+str(k))] for v in r['solutions']],want)

 def test_negative_lifetime_is_old_route_and_toward_zero_not_mask(self):
  from fractions import Fraction
  for rhs,expect in [('n%2',[0,-1]),('n/2',[0,0])]:
   p=simple(one(rhs,event='@(timer(1))n=-1;'));self.assertEqual(primitive_count(p.operators),0)
   r=transient(p,{},[0,1.25],stop=1.25,max_step=.25,kernel=KERNEL)
   self.assertEqual([v['voltages'][r['nodes'].index('y')] for v in r['solutions']],expect)

 def test_negative_and_non_power_divisors_keep_original_route(self):
  from fractions import Fraction
  for op,d in [('/',-2),('%',-2),('/',3),('%',3)]:
   p=simple(one('n'+op+'('+str(d)+')',initial=3,last=3,event=''));self.assertEqual(primitive_count(p.operators),0)
   q=int(Fraction(3,d));expected=q if op=='/' else 3-q*d
   r=transient(p,{},[0,.25],stop=.25,max_step=.25,kernel=KERNEL)
   self.assertEqual(r['solutions'][0]['voltages'][r['nodes'].index('y')],expected)

 def test_type_zero_overflow_and_unselected_overflow_keep_refusal(self):
  cases=[one('n%0'),one('(n/2.0)%2'),one('((n+1)-1)%1',initial=2147483647,event=''),one('(n<0)?((n+1)-1):0',initial=2147483647,event=''),one('n/(-1)',initial=-2147483648,event='')]
  for text in cases:
   with self.subTest(source=text),self.assertRaises(CompileError):simple(text)

 def test_bin256_accepted_but257_still_refused_and_instance_bounds_fresh(self):
  p=simple(one('n/1'));self.assertGreater(primitive_count(p.operators),0)
  with self.assertRaisesRegex(CompileError,'quotient-bin'):simple(one('n/1'),last=256)
  # The old structural modulo enclosure can be wider than its mathematical range.
  # Do not use a tighter new bound to skip that original parent bin refusal.
  with self.assertRaisesRegex(CompileError,'quotient-bin'):simple(one('(n%2)/1'))
  source=one('n/1')
  with self.assertRaisesRegex(CompileError,'quotient-bin'):
   compile_sources({'fresh-pow2.va':source},[Instance('good','one',dict(y='a')),Instance('bad','one',dict(y='b'),dict(last=256))])

 def test_real_alias_mixed_use_nested_target_and_repeated_writer_stay_old(self):
  for text in [one('n%2',last=3,tail='V(y)<+b;'),one('n%2',last=3).replace('transition(b,','transition(b+0.0,'),one('n%2',last=3).replace('b=n%2;','b=n%2;b=b+0.0;')]:
   p=simple(text);self.assertEqual(primitive_count(p.operators),0)
  with self.assertRaises(CompileError):simple(one('n%2',last=3,tail='V(y)<+(b%2);'))

 def test_event_display_and_trigger_alias_reads_do_not_become_integer(self):
  for event in ['@(timer(1))$display("%g",b);','@(cross(b-0.5,+1))n=1;']:
   with self.assertRaises(CompileError):simple(one('n%2',last=3,event=event))

 def test_hidden_physical_time_and_operator_children_cannot_disappear(self):
  for rhs in ['(n%2)+0.0*V(y)','(n%2)+0.0*$abstime','(n>0)?n%2:ddt(0.0)','(n>0)?n%2:((n+2147483647)-2147483647)']:
   with self.subTest(rhs=rhs),self.assertRaises(CompileError):simple(one(rhs))

 def test_zero_mask_keeps_integer_state_dependency_and_foreign_role_rejection(self):
  import copy,subprocess
  p=simple(one('n%1'));self.assertGreater(primitive_count(p.operators),0)
  raw=json.loads(json.dumps(p.to_dict()))
  for mode in ['real-state','foreign-origin','ordinary-contribution']:
   bad=copy.deepcopy(raw);target=bad['operators'][0]['input']
   if mode=='real-state':bad['states'][0]['kind']='real'
   elif mode=='foreign-origin':target['origin']['instance']='foreign'
   else:bad['contributions'][0]['rhs']=target
   request=dict(program=bad,driven=[],samples=[],transient=dict(pwl=[],output_times=[0,1.25],stop=1.25,max_step=.25))
   r=__import__('subprocess').run([str(KERNEL)],input=json.dumps(request),capture_output=True,text=True,timeout=10)
   self.assertNotEqual(r.returncode,0,mode)

 def test_full_wire_budget_exhaustion_and_two_retries_share_one_owner(self):
  p=simple(one('n%1'));owner=p._native_audit;success=0
  while True:
   try:p.to_dict();success+=1
   except CompileError:break
  self.assertGreater(success,0);self.assertGreater(owner.used,100000);copies=owner.counts['copy_container']
  for _ in range(2):
   with self.assertRaises(CompileError):p.to_dict()
   self.assertIs(owner,p._native_audit);self.assertEqual(copies,owner.counts['copy_container'])


 def test_fresh_source_domain_and_mutable_AST_do_not_gain_cached_eligibility(self):
  from unittest.mock import patch
  from dataclasses import replace
  from evas import held_power2
  original=held_power2.source_plan;observed=[]
  def record(c,root):
   result=original(c,root)
   if result is not None:observed.append((c,root,c.ordinary_integer_bounds if c.ordinary_integer_bounds is not None else c.integer_state_ranges))
   return result
  with patch.object(held_power2,'source_plan',record):p=simple(one('n%2'))
  c,root,domains=observed[-1];c.ordinary_integer_bounds=domains
  self.assertIsNotNone(original(c,root))
  mutable=replace(root,args=list(root.args));self.assertIsNone(original(c,mutable))
  mutable_origin=replace(root,expansion=(['i',0],));self.assertIsNone(original(c,mutable_origin))
  index=c.state_ids['n'];old=domains[index];domains[index]=(-1,255)
  self.assertIsNone(original(c,root));domains[index]=old
  c.model.variables['n']='real';self.assertIsNone(original(c,root))

 def test_same_callback_intermediate_writes_do_not_make_a_history_edge(self):
  p=simple(one('n/2',event='@(timer(1))begin n=-1;n=3;end'))
  times=[0,.99,1,1.002,1.005,1.01,1.1]
  r=transient(p,{},times,stop=1.1,max_step=.1,kernel=KERNEL)
  values=[v['voltages'][r['nodes'].index('y')] for v in r['solutions']]
  self.assertEqual(values[0],0);self.assertAlmostEqual(values[-1],1,places=12)
  self.assertTrue(all(-1e-12<=v<=1+1e-12 for v in values))

 def test_active_source_probe_rejection_is_sticky_after_actual_wire_exhaustion(self):
  from unittest.mock import patch
  from evas.instance_compiler import InstanceCompiler
  from evas import held_power2
  original=InstanceCompiler.compile;seen=[]
  def record(c):result=original(c);seen.append(c);return result
  with patch.object(InstanceCompiler,'compile',record):p=simple(one('n%1'))
  c=seen[-1];root=c.held_power2_ready['b'];owner=p._native_audit
  while True:
   try:p.to_dict()
   except CompileError:break
  visits=owner.counts['held_power2_source_visit'];emits=owner.counts['emit_object']
  for _ in range(2):
   with self.assertRaises(CompileError):held_power2.source_plan(c,root)
   self.assertEqual(visits,owner.counts['held_power2_source_visit']);self.assertEqual(emits,owner.counts['emit_object'])
   self.assertIs(owner,c.compilation.native_audit)


class HeldPower2ConstantBindings(unittest.TestCase):
 def test_composed_constant_divisors_keep_old_affine_contract(self):
  for rhs,want in [('n/(4/2)',[0,0,1,1]),('n/((8/2)/2)',[0,0,1,1]),('n%(4/2)',[0,1,0,1])]:
   with self.subTest(rhs=rhs):
    p=simple(one(rhs,last=3));owner=p._native_audit
    r=transient(p,{},[0,1.25,2.25,3.25],stop=3.25,max_step=.25,kernel=KERNEL)
    self.assertEqual([v['voltages'][r['nodes'].index('y')] for v in r['solutions']],want)
    self.assertIs(owner,p._native_audit);self.assertLessEqual(owner.used,100000)
    self.assertGreater(owner.counts.get('held_power2_constant_dispatch',0),0)

 def test_nested_constant_numerator_stays_exact_integer_toward_zero(self):
  for constant in ['((4/2)/2)','((6/4)/1)']:
   p=simple(one('(n%2)?'+constant+':0',last=3))
   r=transient(p,{},[0,1.25,2.25,3.25],stop=3.25,max_step=.25,kernel=KERNEL)
   self.assertEqual([v['voltages'][r['nodes'].index('y')] for v in r['solutions']],[0,1,0,1])

 def test_constant_subtree_zero_and_overflow_still_refuse(self):
  for rhs in ['n/(4/0)','n/(2147483648/2)','(n%2)?(2147483648/2):0']:
   with self.subTest(rhs=rhs),self.assertRaises(CompileError):simple(one(rhs,last=3))

 def test_constant_dispatch_cannot_bypass_active_exhaustion(self):
  p=simple(one('n/(4/2)',last=3));owner=p._native_audit
  while True:
   try:p.to_dict()
   except CompileError:break
  copies=owner.counts['copy_container'];count=owner.counts.get('held_power2_constant_dispatch',0)
  for _ in range(2):
   with self.assertRaises(CompileError):p.to_dict()
   self.assertEqual(owner.counts['copy_container'],copies)
   self.assertEqual(owner.counts.get('held_power2_constant_dispatch',0),count)

 def test_real_divisor_subtrees_keep_real_division_without_primitive(self):
  for rhs,want in [('n/(4/2.0)',[0,.5,1,1.5]),('n/(4/(2/2.0))',[0,.25,.5,.75])]:
   p=simple(one(rhs,last=3));self.assertEqual(primitive_count(p.operators),0)
   r=transient(p,{},[0,1.25,2.25,3.25],stop=3.25,max_step=.25,kernel=KERNEL)
   self.assertEqual([v['voltages'][r['nodes'].index('y')] for v in r['solutions']],want)

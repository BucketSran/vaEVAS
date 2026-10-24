"""Conservative source-selected finite admission, not a scalar value proof."""
GUARDS = ['LANG', 'EVENT-CONDITIONS']
from fractions import Fraction
from types import SimpleNamespace
import math,unittest
from evas import CompileError,Instance,compile_sources
from evas.ir import Affine,Binary,RealBinary,RealBoundary,Select,Origin,StateRef,RealLocal
from evas.native_audit import NativeAudit
from evas.program_real_facts import ProgramRealFacts

O=Origin('interval.va',1,1,'dut')
def node(op,a,b):return RealBinary(op,a,b,O)
def branch(a,b):return Select('lt',StateRef(9),Affine(0.,()),a,b,O)

def public(body,extra=''):
 source=('`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;real a,q;integer c;'+extra+'analog begin @(initial_step)begin '+body+' end V(y)<+q;end endmodule')
 return compile_sources({'interval.va':source},[Instance('dut','m',dict(u='u',y='y'))])

class InitialSelectedInterval(unittest.TestCase):
 def facts(self):
  owner=NativeAudit();return owner,ProgramRealFacts(owner.ir_work)
 def test_input_selected_domain_never_becomes_global_closed_or_scalar(self):
  owner,f=self.facts();v=branch(Affine(1.,()),Affine(2.,()))
  self.assertEqual(f.query(v,'selected_interval'),(1.,2.))
  self.assertFalse(f.query(v).closed)
  self.assertIsNone(f.query(v).value)
  self.assertTrue(owner.active)
  self.assertEqual(owner.used,sum(owner.counts.values()))
 def test_each_real_operation_rounds_while_mathematical_binary_is_outward(self):
  _,f=self.facts();a,b=Affine(1.,()),Affine(2.**-54,())
  self.assertEqual(f.query(node('add',a,b),'selected_interval'),(1.,1.))
  lower,upper=f.query(Binary('add',a,b),'selected_interval')
  exact=Fraction(1)+Fraction(2.**-54)
  self.assertLessEqual(Fraction(lower),exact);self.assertGreaterEqual(Fraction(upper),exact)
  self.assertEqual(upper,math.nextafter(1.,math.inf))
 def test_zero_crossing_unknown_state_and_cycle_do_not_get_domain_certificate(self):
  _,f=self.facts()
  for value in [StateRef(0),node('divide',Affine(1.,()),branch(Affine(-1.,()),Affine(1.,()))),node('divide',Affine(1.,()),Affine(0.,()))]:
   self.assertIsNone(f.query(value,'selected_interval'))
  read=RealLocal(0);f.record_read(read,(read,))
  self.assertIsNone(f.query(read,'selected_interval'))
  self.assertFalse(f.active)
 def test_math_cancellation_cannot_hide_a_zero_crossing_divisor(self):
  _,f=self.facts();a=Affine(2.**53,());b=Affine(1.,());neg=Affine(-2.**53,())
  divisor=Binary('add',Binary('add',a,b),neg)
  lo,hi=f.query(divisor,'selected_interval')
  self.assertLessEqual(lo,1.);self.assertGreaterEqual(hi,1.)
  self.assertIsNone(f.query(node('divide',Affine(1.,()),divisor),'selected_interval'))
 def test_all_source_branch_corner_results_are_enclosed(self):
  _,f=self.facts()
  for op in ('add','subtract','multiply','divide'):
   a=branch(Affine(-3.,()),Affine(2.,()));b=branch(Affine(1.5,()),Affine(4.,()))
   lo,hi=f.query(node(op,a,b),'selected_interval')
   for x in (-3.,2.):
    for y in (1.5,4.):
     result={'add':lambda:x+y,'subtract':lambda:x-y,'multiply':lambda:x*y,'divide':lambda:x/y}[op]()
     self.assertLessEqual(lo,result);self.assertGreaterEqual(hi,result)
 def test_public_positive_selected_denominator_retains_guard_and_round_tree(self):
  p=public('a=(V(u)>0.5)?1.0:2.0;q=1.0/a;');wire=p.to_dict()
  self.assertTrue(wire['procedures']);self.assertEqual(len(wire['events']),1)
  self.assertTrue(all(state.initial==0 for state in p.states))
  self.assertEqual(p._native_audit.used,sum(p._native_audit.counts.values()))
 def test_public_continuous_unknown_and_possible_zero_denominators_reject(self):
  for assignment in ('a=V(u)+1.0;','a=(V(u)>0.5)?0.0:2.0;'):
   with self.subTest(assignment=assignment),self.assertRaises(CompileError):public(assignment+'q=1.0/a;')
 def test_integer_assignment_retains_select_without_body_explosion(self):
  body='c='+ '+'.join(str(2**i)+'*((V(u)>'+str(i)+')?1:0)' for i in range(8))+';q=c+1.0;'
  p=public(body);wire=p.to_dict()
  def count(v,kind):
   if isinstance(v,dict):return int(v.get('kind')==kind)+sum(count(x,kind) for x in v.values())
   if isinstance(v,(tuple,list)):return sum(count(x,kind) for x in v)
   return 0
  self.assertEqual(len(wire['events'][0]['body']),2)
  self.assertEqual(count(wire['events'][0]['body'],'if'),0)
  self.assertTrue(p._native_audit.active)
 def test_legacy_assignment_route_keeps_its_existing_split(self):
  from evas.instance_compiler import InstanceCompiler
  from evas.ir import Conditional,Assignment
  fake=SimpleNamespace(compilation=SimpleNamespace(states=[SimpleNamespace(kind='integer')]),
      procedure_builder=None,compact_event_candidate=lambda:False,
      make_ir=lambda cls,*args:cls(*args),split_selection=InstanceCompiler.split_selection)
  value=Binary('add',branch(Affine(0.,()),Affine(1.,())),branch(Affine(2.,()),Affine(3.,())))
  result=InstanceCompiler.event_assignment(fake,0,value,O)
  self.assertIsInstance(result[0],Conditional)
  fake.procedure_builder=object()
  result=InstanceCompiler.event_assignment(fake,0,value,O)
  self.assertIsInstance(result[0],Assignment)
  self.assertIs(result[0].rhs,value)
 def test_natural_domain_work_exhaustion_and_sticky_retry_stay_on_same_owner(self):
  owner,f=self.facts()
  with self.assertRaises(CompileError) as got:
   for i in range(10000):f.query(node('add',Affine(float(i),()),Affine(1.,())),'selected_interval')
  self.assertEqual(got.exception.diagnostic['code'],'resource_budget')
  for _ in range(2):
   with self.assertRaises(CompileError):f.query(Affine(1.,()),'selected_interval')
  self.assertEqual(owner.used,sum(owner.counts.values()))

if __name__=='__main__':unittest.main()

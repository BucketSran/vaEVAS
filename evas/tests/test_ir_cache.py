"""Immutable request-local shape reuse retains expanded limits and budgets."""
GUARDS = ["LANG"]
import unittest
from dataclasses import dataclass
from evas import CompileError
from evas.limits import check_ir
from evas.native_audit import NativeAudit
from evas.ir import Affine,Binary
class CacheControls(unittest.TestCase):
 def owner(self):
  a=NativeAudit();a.activate(None);return a
 def check(self,v,a):return check_ir(v,work=a.ir_work,cache=a.ir_cache)
 def test_recursive_expansion_counts_each_occurrence_and_rejects(self):
  a=self.owner();v=Affine(1.,())
  for i in range(17):
   v=Binary('add',v,v)
   if i<10:self.assertEqual(self.check(v,a),check_ir(v))
  with self.assertRaisesRegex(CompileError,'expanded IR size'):self.check(v,a)
 def test_depth_and_cycle_limits(self):
  a=self.owner();v=()
  for _ in range(97):v=(v,)
  with self.assertRaisesRegex(CompileError,'depth'):self.check(v,a)
  v=[];v.append(v)
  with self.assertRaisesRegex(CompileError,'cyclic'):self.check(v,self.owner())
 def test_mutable_descendants_are_never_cached_and_changes_rechecked(self):
  @dataclass(frozen=True)
  class Box: child:object
  a=self.owner();xs=[1];v=Box((xs,));self.assertEqual(self.check(v,a),check_ir(v));self.assertNotIn(id(v),a.ir_cache)
  xs.extend([1]*100001)
  with self.assertRaises(CompileError):self.check(v,a)
 def test_cross_request_cache_isolation_keepalive_and_retry_exhaustion(self):
  a=self.owner();b=self.owner();v=Affine(1.,())
  self.check(v,a);self.assertIs(a.ir_cache[id(v)][0],v);self.assertFalse(b.ir_cache)
  first=a.used;self.check(v,a);self.assertGreater(a.used,first)
  while a.used<=100000:
   try:self.check(v,a)
   except CompileError:break
  used=a.used
  for _ in range(2):
   with self.assertRaises(CompileError):self.check(v,a)
   self.assertGreater(a.used,used);used=a.used


 def test_production_schema_enumeration_is_prepaid_and_retry_remains_exhausted(self):
  from unittest.mock import patch
  from evas.ir import Program
  import evas.limits as limits
  # A real Program has seven schema fields. After the pending-pop and cache
  # lookup charges, no work remains for its metadata helper.
  value=Program(('0',),())
  owner=self.owner()
  owner.debit('prior_request_work',99998-owner.used)
  original=limits.fields
  calls=[]
  def metadata(item):
   calls.append(item)
   return original(item)
  with patch.object(limits,'fields',metadata):
   prior=owner.used
   for _ in range(3):
    with self.assertRaisesRegex(CompileError,'aggregate audit'):
     self.check(value,owner)
    self.assertGreater(owner.used,prior)
    prior=owner.used
    self.assertEqual(calls,[])

"""Public conditional integer decoder keeps default aggregate work and wire identity."""
import hashlib,json,os,unittest
from pathlib import Path
from fractions import Fraction
from evas import compile_sources,Instance,transient,CompileError
GUARDS=['LANG']
KERNEL=Path(os.environ.get('EVAS_TEST_KERNEL',str(Path(__file__).resolve().parents[1]/'rust_core/target/debug/evas-kernel')))
def counter():
 ports=[f'y{k}' for k in range(6)]
 body='@(initial_step)n=0;@(timer(1,1))if(n<=223)n=n+32;else if(n<255)n=255;'
 for k,d in enumerate([64,32,16,8,4,2]):body+=f'b{k}=(((n/{d})%2)==1)?1.0:0.0;V(y{k})<+b{k};'
 return '`include "disciplines.vams"\nmodule m('+','.join(ports)+');output '+','.join(ports)+';electrical '+','.join(ports)+';integer n;real '+','.join(f'b{k}' for k in range(6))+';analog begin '+body+' end endmodule',ports
class DecisionRawReuse(unittest.TestCase):
 def test_public_sixbit_conditional_decoder_default_owner_full_wire(self):
  text,ports=counter();p=compile_sources({'decoder_sixbit.va':text},[Instance('dut','m',{v:v for v in ports})]);owner=p._native_audit
  before=owner.used;before_counts=owner.counts.copy()
  from unittest.mock import patch
  import evas.runtime as runtime
  invoke=runtime._invoke;requests=[]
  def capture(request,*args,**kwargs):
   requests.append(request);return invoke(request,*args,**kwargs)
  with patch.object(runtime,'_invoke',side_effect=capture):
   result=transient(p,{},[0]+[k+.25 for k in range(1,9)],stop=8.25,max_step=.25,kernel=KERNEL)
  self.assertEqual(len(requests),1)
  # Only the IR version changes. Keep the prior full structural identity and
  # independently check current transport; values retain their Fraction oracle.
  prior_program=dict(requests[0]['program'])
  self.assertEqual(prior_program['schema_version'],32)
  prior_program['schema_version']=31
  program_hash=hashlib.sha256(json.dumps(prior_program,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  self.assertEqual(program_hash,'c3a7f0821fc23df5ca74357558d03a92b4eb5913d3ab2f583b1d90818a5a94f2')
  print('decoder request sha256',hashlib.sha256(json.dumps(requests[0],sort_keys=True,separators=(',',':')).encode()).hexdigest())
  self.assertIs(owner,p._native_audit);self.assertLessEqual(owner.used,100000)
  for k,d in enumerate([64,32,16,8,4,2]):
   expected=[int(Fraction(n,d))%2 for n in [0,32,64,96,128,160,192,224,255]]
   self.assertEqual([v['voltages'][result['nodes'].index(f'y{k}')] for v in result['solutions']],expected)
  print('decoder default owner',before,owner.used,dict(owner.counts-before_counts))

 def test_positive_quotient_normalization_keeps_rebuilt_guard_and_complete_consumer(self):
  from unittest.mock import patch
  import evas.instance_compiler as ic
  from evas import solve
  from test_rational_predicate_closure import SOURCE,compile_model
  original=ic.normalize_positive_quotient_comparison;changed=[]
  def observe(*args,**kwargs):
   result=original(*args,**kwargs)
   if result is not None:changed.append(result)
   return result
  source=SOURCE.replace('clip(numerator / denominator)','(numerator / denominator > 0.125) ? 0.9 : 0.0')
  with patch.object(ic,'normalize_positive_quotient_comparison',side_effect=observe):p=compile_model(source,{'lower':.1})
  self.assertGreater(len(changed),0)
  result=solve(p,['n','d','en','ref'],[[.03125,.5,1,0],[.0625,.5,1,0],[.125,.5,1,0]],kernel=KERNEL)
  self.assertEqual([s['voltages'][result['nodes'].index('y')] for s in result['solutions']],[0,0,.9])

 def _compiler(self):
  from unittest.mock import patch
  from evas.instance_compiler import InstanceCompiler
  observed=[];original=InstanceCompiler.expression_select
  def capture(compiler,expr,*args,**kwargs):
   result=original(compiler,expr,*args,**kwargs);observed.append((compiler,expr));return result
  source='`include "disciplines.vams"\nmodule m(u,y);input u;output y;electrical u,y;analog begin V(y)<+((V(u)>0)?1.0:0.0);end endmodule'
  with patch.object(InstanceCompiler,'expression_select',capture):program=compile_sources({'raw-controls.va':source},[Instance('dut','m',dict(u='u',y='y'))])
  observed[-1][0]._test_program=program
  return observed[-1]

 def _raw(self,compiler,expr,left,then_value=None,else_value=None):
  from evas.ir import Select,Origin,Affine
  return Select('lt',left,Affine(1.,()),then_value if then_value is not None else Affine(1.,()),else_value if else_value is not None else Affine(0.,()),Origin(expr.token.source or compiler.model.source,expr.token.line,expr.token.column,compiler.instance.name,expr.expansion))

 def _call(self,compiler,expr,raw,*,reuse=True):
  # This is the same fresh original-tree audit as the production factory.
  compiler.checked_ir(raw,raw.origin)
  return compiler.expression_select(expr,raw.relation,raw.left,raw.right,raw.then_value,raw.else_value,raw=raw if reuse else None)

 def test_mutable_descendant_is_freshly_checked_after_mutation(self):
  from evas.ir import Affine,Term
  compiler,expr=self._compiler();guard=Affine(0.,[]);raw=self._raw(compiler,expr,guard)
  self._call(compiler,expr,raw);owner=compiler.compilation.native_audit
  self.assertNotIn(id(raw),owner.ir_cache)
  before=owner.counts['ir_fields'];guard.terms.append(Term(999,1.))
  with self.assertRaises(CompileError):self._call(compiler,expr,raw)
  self.assertGreater(owner.counts['ir_fields'],before);self.assertNotIn(id(raw),owner.ir_cache)

 def test_foreign_owner_fact_is_not_reused_and_binding_role_is_fresh(self):
  from evas.ir import Affine,Term
  compiler,expr=self._compiler();guard=Affine(0.,(Term(next(iter(compiler.allowed_condition_nodes)),1.),));raw=self._raw(compiler,expr,guard)
  self._call(compiler,expr,raw);first=compiler.compilation.native_audit
  other,other_expr=self._compiler();second=other.compilation.native_audit
  self.assertIsNot(first,second);self.assertNotIn(id(raw),second.ir_cache)
  before=second.counts['ir_fields'];self._call(other,other_expr,raw)
  self.assertGreater(second.counts['ir_fields'],before)
  self.assertIs(second.ir_cache[id(raw)][0],raw)
  other.allowed_condition_nodes=set()
  with self.assertRaisesRegex(CompileError,'input/inout'):self._call(other,other_expr,raw)

 def test_raw_metadata_cannot_change_operands_or_source_role(self):
  from evas.ir import Affine
  compiler,expr=self._compiler();raw=self._raw(compiler,expr,Affine(0.,()))
  with self.assertRaisesRegex(CompileError,'original decision'):
   compiler.expression_select(expr,raw.relation,Affine(0.,()),raw.right,raw.then_value,raw.else_value,raw=raw)
  compiler.instance=Instance('foreign','m',dict(u='u',y='y'))
  with self.assertRaisesRegex(CompileError,'source role'):self._call(compiler,expr,raw)

 def test_checked_operator_and_invalid_hidden_arms_keep_old_rejection(self):
  from evas.ir import Affine,Term,Select,CheckedInteger,OperatorRef,IntegerRound,StateRef,Origin,Transition
  from evas import solve,KernelError
  from dataclasses import replace
  compiler,expr=self._compiler();origin=self._raw(compiler,expr,Affine(0.,())).origin
  cases=[CheckedInteger(Affine(2147483648.,()),origin),OperatorRef(0),IntegerRound(Affine(1.5,()),origin)]
  for hidden in cases+[Affine(0.,(Term(999,1.),)),StateRef(999)]:
   errors=[]
   for reuse in [False,True]:
    c,e=self._compiler();c.compilation.operators.append(Transition(Affine(0.,()),0.,1.,1.,origin));raw=self._raw(c,e,Affine(0.,()),else_value=hidden)
    try:
     value=self._call(c,e,raw,reuse=reuse)
     base=c._test_program;program=replace(base,contributions=(replace(base.contributions[0],rhs=value),))
     solve(program,['u'],[[0.]],kernel=KERNEL)
    except (CompileError,KernelError) as error:errors.append((type(error).__name__,str(error)))
    else:self.fail('invalid hidden arm was admitted by complete consumer')
   self.assertEqual(errors[0],errors[1])

 def test_full_wire_natural_exhaustion_has_two_sticky_retries(self):
  text,ports=counter();p=compile_sources({'decoder_sixbit.va':text},[Instance('dut','m',{v:v for v in ports})]);owner=p._native_audit
  p.to_dict();self.assertLessEqual(owner.used,100000)
  with self.assertRaises(CompileError):p.to_dict()
  copies=owner.counts['copy_container'];used=owner.used
  for _ in range(2):
   with self.assertRaises(CompileError):p.to_dict()
   self.assertIs(p._native_audit,owner);self.assertGreater(owner.used,used)
   self.assertEqual(owner.counts['copy_container'],copies);used=owner.used

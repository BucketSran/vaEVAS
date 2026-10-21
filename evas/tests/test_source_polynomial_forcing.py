"""Independent source-product plus held-transition acceptance, not a gold clone."""
from pathlib import Path
from fractions import Fraction
import copy,json,unittest
from evas import Instance, CompileError, KernelError, compile_sources, solve, transient
ROOT=Path(__file__).resolve().parents[2]
KERNEL=ROOT/'evas/rust_core/target/debug/evas-kernel'
PREFIX='''`include "disciplines.vams"
module product(a,b,c,y); input a,b,c; output y; electrical a,b,c,y; real q;
analog begin @(initial_step) q=0; @(cross(V(c)-0.5,+1)) q=1;
'''
GUARDS = ["LANG", "ANALOG", "EVENT-ORDER", "TIMED-OPERATOR", "COMPOSE"]

class LegacyDispatchContracts(unittest.TestCase):
 def test_quadratic_beside_quartic_keeps_original_polynomial_route(self):
  from evas.ir import Forcing
  source='''`include "disciplines.vams"
module legacy(a,b,y); input a,b; output y; electrical a,b,y;
analog begin V(y)<+V(a)*V(b)+pow(V(a)+1,4)/2; end endmodule'''
  p=compile_sources({'old-polynomial.va':source},[Instance('dut','legacy',dict(a='a',b='b',y='y'),{})])
  # This algebraic relation already has a polynomial kernel consumer. The
  # held-history Forcing marker would replace that public execution route.
  self.assertFalse(any(isinstance(c.rhs,Forcing) for c in p.contributions))
  result=solve(p,['a','b'],[[.5,.75]],kernel=KERNEL)
  self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')],93/32)
 def test_inout_algebraic_feedback_beside_integral_keeps_original_dae_route(self):
  from evas.ir import Forcing
  source='''`include "disciplines.vams"
module legacy(z,y); inout z,y; electrical z,y;
analog begin V(z)<+idt(1,0.3125); V(y)<+V(z)-V(y)*V(y); end endmodule'''
  p=compile_sources({'old-dae.va':source},[Instance('dut','legacy',dict(z='z',y='y'),{})])
  # Compilation preserves the original implicit relation y+y*y=z. This
  # syntax test grants no waveform qualification to the DAE support probe.
  self.assertFalse(any(isinstance(c.rhs,Forcing) for c in p.contributions))
 def test_cross_instance_order_preserves_quadratic_source_and_held_state(self):
  source='''`include "disciplines.vams"
module mixed(a,b,y); input a,b; output y; electrical a,b,y; real q;
analog begin @(initial_step) q=0; @(timer(0.5)) q=1;
V(y)<+V(a)*V(b)+q; end endmodule
module history(m); output m; electrical m; real q;
analog begin @(initial_step) q=0; @(timer(0.25)) q=1;
V(m)<+transition(q,0,0.125,0.125); end endmodule'''
  mixed=Instance('mixed_dut','mixed',dict(a='a',b='b',y='y'),{})
  history=Instance('history_dut','history',dict(m='m'),{})
  # Independent formula y=t*(1-t)+[t>=1/2]. An unrelated held history
  # cannot make its admission or waveform depend on instance compile order.
  expected=[Fraction(0),Fraction(3,16),Fraction(19,16),Fraction(1)]
  for instances in ([mixed,history],[history,mixed]):
   with self.subTest(order=[item.name for item in instances]):
    p=compile_sources({'ordered-source-history.va':source},instances)
    result=transient(p,{'a':[[0,0],[1,1]],'b':[[0,1],[1,0]]},
                     [0,.25,.75,1],stop=1,max_step=1,kernel=KERNEL)
    n=result['nodes'].index('y')
    for row,frame,want in zip(result['solutions'],result['observation_evidence']['voltage_bounds_V'],expected):
     actual=row['voltages'][n];lo,hi=frame[n]
     self.assertLessEqual(abs(actual-float(want)),1e-10)
     self.assertLessEqual(Fraction.from_float(lo),want)
     self.assertGreaterEqual(Fraction.from_float(hi),want)

class ContributionEmissionLifecycle(unittest.TestCase):
 def compilation(self,source,connections,has_operators=False):
  from evas.frontend import parse_sources
  from evas.hierarchy import bind_hierarchy
  from evas.instance_compiler import Compilation,InstanceCompiler
  models=parse_sources({'emission-lifecycle.va':source})
  inst=Instance('dut','m',connections,{})
  # Match the real frontend's scalarization/event normalization before the
  # instance compiler; retain the original source for its final role audit.
  bindings=bind_hierarchy(models,[inst],Instance)
  inst,model,nets=bindings[0]
  compilation=Compilation(('0',*sorted(set(nets.values())-{'0'})),has_operators)
  compilation.has_waveform_operators=has_operators
  compilation.held_power2_bindings=bindings
  compilation.held_power2_source_models=models
  InstanceCompiler(inst,model,nets,compilation,source_model=models[model.name]).compile()
  return compilation
 def test_repeated_program_reads_keep_one_relation_and_one_emission_charge(self):
  c=self.compilation('''`include "disciplines.vams"
module m(y); output y; electrical y;
analog begin V(y)<+0.125; end endmodule''',dict(y='y'))
  first=c.program();visits=c.native_audit.counts['contribution_queue_visit']
  second=c.program()
  self.assertEqual(first.contributions,second.contributions)
  self.assertEqual(c.native_audit.counts['contribution_queue_visit'],visits)
  for p in [first,second]:
   result=solve(p,[],[[]],kernel=KERNEL)
   self.assertEqual(result['solutions'][0]['voltages'][result['nodes'].index('y')],0.125)
 def test_partial_emission_failure_keeps_its_instance_and_cannot_reappend(self):
  c=self.compilation('''`include "disciplines.vams"
module m(a,b,c); inout a,b,c; electrical a,b,c;
analog begin V(a,b)<+1; V(a,c)<+2; end endmodule''',dict(a='a',b='b',c='b'))
  with self.assertRaisesRegex(CompileError,'distinct local contribution branches alias') as first:
   c.program()
  partial=tuple(c.contributions);visits=c.native_audit.counts['contribution_queue_visit']
  for _ in range(2):
   with self.assertRaises(CompileError) as again:c.program()
   self.assertEqual(again.exception.diagnostic,first.exception.diagnostic)
   self.assertEqual(again.exception.diagnostic['instance'],'dut')
   self.assertEqual(tuple(c.contributions),partial)
   self.assertEqual(c.native_audit.counts['contribution_queue_visit'],visits)
 def test_original_audit_failure_after_emission_does_not_reemit_on_retry(self):
  c=self.compilation('''`include "disciplines.vams"
module m(a,b,y,m); input a,b; output y,m; electrical a,b,y,m; real q,unused;
analog begin @(initial_step) q=0; @(timer(0.5)) q=1;
unused=0*V(y); V(y)<+V(a)*V(b)+q;
V(m)<+transition(q,0,0.125,0.125); end endmodule''',dict(a='a',b='b',y='y',m='m'),True)
  with self.assertRaises(CompileError) as first:c.program()
  partial=tuple(c.contributions);visits=c.native_audit.counts['contribution_queue_visit']
  for _ in range(2):
   with self.assertRaises(CompileError) as again:c.program()
   self.assertEqual(again.exception.diagnostic,first.exception.diagnostic)
   self.assertEqual(again.exception.diagnostic['code'],'unsupported_forcing_scope')
   self.assertEqual(tuple(c.contributions),partial)
   self.assertEqual(c.native_audit.counts['contribution_queue_visit'],visits)

class SourcePolynomialForcing(unittest.TestCase):
 def run_case(self,body,expected):
  source=PREFIX+body+' end endmodule'
  p=compile_sources({'independent-source-polynomial.va':source},[Instance('dut','product',dict(a='a',b='b',c='c',y='y'),{})])
  result=transient(p,{'a':[[0,0],[1,1]],'b':[[0,1],[1,0]],'c':[[0,0],[1,1]]},[0,.25,.75,1],stop=1,max_step=1,kernel=KERNEL)
  n=result['nodes'].index('y')
  for row,frame,want in zip(result['solutions'],result['observation_evidence']['voltage_bounds_V'],expected):
   actual=row['voltages'][n];lo,hi=frame[n]
   self.assertLessEqual(abs(actual-float(want)),1e-10)
   self.assertLessEqual(Fraction.from_float(lo),want)
   self.assertGreaterEqual(Fraction.from_float(hi),want)
  self.assertEqual([e['time'] for e in result['transient']['events']],[.5])
  return result,p
 def test_same_output_source_quadratic_plus_held_transition(self):
  self.run_case('V(y)<+V(a)*V(b)+transition(q,0,0.125,0.125);',[Fraction(0),Fraction(3,16),Fraction(19,16),Fraction(1)])
 def test_old_affine_plus_same_transition(self):
  self.run_case('V(y)<+V(a)+transition(q,0,0.125,0.125);',[Fraction(0),Fraction(1,4),Fraction(7,4),Fraction(2)])
 def test_old_physical_coefficient_transition(self):
  self.run_case('V(y)<+V(a)-(1-V(b))*transition(q,0,0.125,0.125);',[Fraction(0),Fraction(1,4),Fraction(0),Fraction(0)])
 def test_same_branch_separate_contributions_accumulate(self):
  self.run_case('V(y)<+V(a)*V(b); V(y)<+transition(q,0,0.125,0.125);',[Fraction(0),Fraction(3,16),Fraction(19,16),Fraction(1)])
 def test_reversed_branch_preserves_contribution_sign(self):
  self.run_case('V(0,y)<+V(a)*V(b)+transition(q,0,0.125,0.125);',[Fraction(0),Fraction(-3,16),Fraction(-19,16),Fraction(-1)])
 def test_source_difference_product_and_held_subtraction(self):
  self.run_case('V(y)<+(V(a)-0.25)*V(b)-transition(q,0,0.125,0.125);',[Fraction(-1,4),Fraction(0),Fraction(-7,8),Fraction(-1)])
 def test_explicit_output_feedback_rejects_before_kernel(self):
  source=PREFIX+'V(y)<+V(a)*V(b)+(V(y)+transition(q,0,0.125,0.125)); end endmodule'
  with self.assertRaises(CompileError) as error:
   compile_sources({'feedback.va':source},[Instance('dut','product',dict(a='a',b='b',c='c',y='y'),{})])
  self.assertEqual(error.exception.diagnostic['code'],'unsupported_forcing_scope')
 def test_unused_original_zero_read_of_output_still_rejects(self):
  source=PREFIX.replace('real q;','real q,discard;')+'discard=0*V(y); V(y)<+V(a)*V(b)+transition(q,0,0.125,0.125); end endmodule'
  with self.assertRaises(CompileError) as error:
   compile_sources({'hidden.va':source},[Instance('dut','product',dict(a='a',b='b',c='c',y='y'),{})])
  self.assertEqual(error.exception.diagnostic['code'],'unsupported_forcing_scope')
 def marked(self):
  return json.loads(json.dumps(compile_sources({'marked.va':PREFIX+'V(y)<+V(a)*V(b)+transition(q,0,0.125,0.125); end endmodule'},[Instance('dut','product',dict(a='a',b='b',c='c',y='y'),{})]).to_dict()))
 def raw(self,program,driven=None):
  from evas.runtime import _invoke
  driven=driven or ['a','b','c']
  return _invoke(dict(program=program,driven=driven,samples=[],transient=dict(pwl=[[[0,0],[1,1]]] * len(driven),output_times=[0,1],stop=1,max_step=1),tolerances=dict(absolute=1e-12,relative=1e-10)),KERNEL,20)
 def test_actual_driven_mapping_cannot_be_replaced_by_input_label(self):
  with self.assertRaises(KernelError) as error:self.raw(self.marked(),['b','c'])
  self.assertEqual(error.exception.diagnostic['kind'],'unsupported_forcing_scope')
 def test_raw_hidden_arms_roles_zero_reads_and_foreign_branches(self):
  base=self.marked();index=next(i for i,c in enumerate(base['contributions']) if c['rhs']['op']=='forcing')
  marker=base['contributions'][index]['rhs'];node=base['nodes'].index('y');cases=[]
  zero=dict(op='affine',constant=0,terms=[dict(node=node,coefficient=0)])
  for bad in [zero,dict(op='state',state=0),dict(op='operator',operator=0),dict(op='integer_round',value=dict(op='affine',constant=0,terms=[]),origin=marker['origin']),dict(op='event_math',function='floor',args=[dict(op='affine',constant=0,terms=[])],origin=marker['origin'])]:
   # Existing strict IR31 role validation precedes Forcing partition: a valid
   # IntegerRound node outside its assignment-root role is invalid_ir, not a
   # new Forcing scope admission. All other forbidden sources fail Graph audit.
   expected='invalid_ir' if bad['op']=='integer_round' else 'unsupported_forcing_scope'
   for location in ['checked','hidden_arm']:
    raw=copy.deepcopy(base);m=raw['contributions'][index]['rhs']
    if location=='checked':m['checked']=[bad]
    else:m['value']=dict(op='select',relation='gt',left=dict(op='affine',constant=1,terms=[]),right=dict(op='affine',constant=0,terms=[]),then_value=m['value'],else_value=bad,origin=m['origin'])
    cases.append((bad['op']+'_'+location,raw,expected))
  raw=copy.deepcopy(base);raw['contributions'].append(copy.deepcopy(raw['contributions'][index]));cases.append(('duplicate_marker',raw,'unsupported_forcing_scope'))
  raw=copy.deepcopy(base);residual=next(c for c in raw['contributions'] if c['rhs']['op']!='forcing');residual['branch']['local_positive']='foreign';cases.append(('foreign_branch',raw,'unsupported_forcing_scope'))
  raw=copy.deepcopy(base);raw['operators'][0]['input']=dict(op='affine',constant=0,terms=[dict(node=base['nodes'].index('a'),coefficient=1)]);cases.append(('nonheld_source_cursor_target',raw,'unsupported_operator'))
  raw=copy.deepcopy(base);m=raw['contributions'][index]['rhs'];a=dict(op='affine',constant=0,terms=[dict(node=base['nodes'].index('a'),coefficient=1)]);b=dict(op='affine',constant=0,terms=[dict(node=base['nodes'].index('b'),coefficient=1)])
  m['value']=dict(op='multiply',left=a,right=dict(op='select',relation='gt',left=dict(op='affine',constant=1,terms=[]),right=dict(op='affine',constant=0,terms=[]),then_value=b,else_value=dict(op='affine',constant=0,terms=[]),origin=m['origin']));cases.append(('quadratic_outside_select',raw,'unsupported_forcing_scope'))
  for name,raw,expected in cases:
   with self.subTest(case=name):
    with self.assertRaises(KernelError) as error:self.raw(raw)
    self.assertEqual(error.exception.diagnostic['stage'],'kernel')
    self.assertEqual(error.exception.diagnostic['kind'],expected)
    if expected=='invalid_ir':self.assertIn('only allowed as the RHS root of a scalar integer assignment',str(error.exception))
 def test_paid_scalar_held_expression_preserves_original_bare_target_values(self):
  raw=self.marked();raw['operators'][0]['input']=dict(op='add',left=dict(op='state',state=0),right=dict(op='affine',constant=0,terms=[]))
  result=self.raw(raw);n=result['nodes'].index('y')
  for row,box,want in zip(result['solutions'],result['observation_evidence']['voltage_bounds_V'],[Fraction(0),Fraction(2)]):
   self.assertEqual(row['voltages'][n],float(want))
   self.assertLessEqual(Fraction.from_float(box[n][0]),want);self.assertGreaterEqual(Fraction.from_float(box[n][1]),want)
 def test_extra_queries_preserve_event_and_common_history_values(self):
  # Two independent mixed branches exercise distinct cached boxes at one phase.
  prefix=PREFIX.replace('c,y);','c,y,z);').replace('output y;','output y,z;').replace('electrical a,b,c,y;','electrical a,b,c,y,z;')
  p=compile_sources({'repeat.va':prefix+'V(y)<+V(a)*V(b)+transition(q,0,0.125,0.125); V(z)<+2*V(a)*V(b)+transition(q,0,0.125,0.125); end endmodule'},[Instance('dut','product',dict(a='a',b='b',c='c',y='y',z='z'),{})])
  inputs={'a':[[0,0],[1,1]],'b':[[0,1],[1,0]],'c':[[0,0],[1,1]]}
  sparse=[0,0.25,0.75,1];dense=[i/16 for i in range(17)]
  a=transient(p,inputs,sparse,stop=1,max_step=1,kernel=KERNEL);b=transient(p,inputs,dense,stop=1,max_step=1,kernel=KERNEL)
  self.assertEqual(a['transient']['events'],b['transient']['events'])
  self.assertEqual(a['solutions'],[b['solutions'][dense.index(t)] for t in sparse])
  self.assertEqual(a['observation_evidence']['voltage_bounds_V'],[b['observation_evidence']['voltage_bounds_V'][dense.index(t)] for t in sparse])
  for t,row,box in zip(dense,b['solutions'],b['observation_evidence']['voltage_bounds_V']):
   t=Fraction(t);held=min(Fraction(1),max(Fraction(0),(t-Fraction(1,2))*8))
   for name,multiplier in [('y',1),('z',2)]:
    expected=multiplier*t*(1-t)+held;n=b['nodes'].index(name)
    self.assertLessEqual(abs(row['voltages'][n]-float(expected)),1e-10)
    self.assertLessEqual(Fraction.from_float(box[n][0]),expected)
    self.assertGreaterEqual(Fraction.from_float(box[n][1]),expected)
 def test_unchanged_default_expression_budget_rejects_on_two_retries(self):
  prefix=PREFIX.replace('analog begin','analog function real f; input x; real x; begin f=x+x; end endfunction analog begin',1)
  value='V(a)'
  for _ in range(20):value='f('+value+')'
  for _ in range(2):
   with self.assertRaises(CompileError) as error:
    compile_sources({'budget.va':prefix+'V(y)<+'+value+'*V(b)+transition(q,0,0.125,0.125); end endmodule'},[Instance('dut','product',dict(a='a',b='b',c='c',y='y'),{})])
   self.assertEqual(error.exception.diagnostic['code'],'resource_budget')
if __name__=='__main__':unittest.main(verbosity=2)

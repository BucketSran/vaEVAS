import os,sys,json,unittest,traceback
from pathlib import Path
R=Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
sys.dont_write_bytecode=True
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
os.chdir(R)
from evas import CompileError,KernelError
rows=[]
originals={cls:cls.__init__ for cls in (CompileError,KernelError)}
for cls in originals:
 def init(self,*args,_cls=cls,**kwargs):
  originals[_cls](self,*args,**kwargs)
  rows.append(dict(kind=_cls.__name__,message=str(self),detail=getattr(self,'detail',None),stack=traceback.format_stack(limit=6)))
 cls.__init__=init
ids=['test_absdelay.AbsDelayRejections.test_internal_state_nested_nonlinear_and_feedback_inputs_rejected','test_absdelay.AbsDelayRejections.test_cross_on_delayed_output_direct_or_indirect_is_rejected','test_absdelay.AbsDelayRejections.test_cross_instance_guard_dependency_survives_cancellation','test_slew.SlewContracts.test_unsupported_inputs_and_operator_uses_are_rejected','test_deferred_rdist.DeferredRdist.test_bad_raw_leaf_seed_and_signature_are_rejected','test_events.EventRejections.test_frontend_rejects_nonconstant_init_and_unsupported_events','test_held_integer_targets.HeldIntegerTargets.test_each_source_child_overflow_precedes_mask_and_retarget']
if len(sys.argv)>1:ids=sys.argv[1:]
report=[]
for id in ids:
 rows.clear(); suite=unittest.defaultTestLoader.loadTestsFromName(id); result=unittest.TestResult();suite.run(result)
 report.append(dict(id=id,run=result.testsRun,errors=[str(x[1]) for x in result.errors],failures=[str(x[1]) for x in result.failures],exceptions=rows.copy()))
print(json.dumps(report,indent=2))

# A valid retained deferred leaf must survive the exact mutation placement.
# Fault injection changes only the real deferred-leaf validator in memory.
import ast,inspect,hashlib
from dataclasses import replace
from unittest.mock import patch
from evas.ir import UnsupportedSystemCall
import evas.program_real_validation as validator
from test_deferred_rdist import build

def verdict(program):
 try:
  program.to_dict()
  return {'outcome':'accepted'}
 except CompileError as error:
  return {'outcome':'rejected','message':str(error),'diagnostic':error.diagnostic}

def leaf_controls():
 p=build(wire=False)
 i,event=next((i,e) for i,e in enumerate(p.events) if isinstance(e.body[0].rhs.value,UnsupportedSystemCall))
 assignment=event.body[0];boundary=assignment.rhs;leaf=boundary.value
 result={'selected_event_index':i,'events':[{'index':j,'trigger':e.trigger.kind,'procedure_id':e.procedure_id,'expanded_statement_ordinal':e.expanded_statement_ordinal} for j,e in enumerate(p.events)],'positive':verdict(p),'controls':[]}
 for name,bad in [('unchanged_legal_leaf',leaf),('wrong_function',replace(leaf,function='rdist_uniform')),('real_state_seed',replace(leaf,seed=0)),('wrong_arity',replace(leaf,args=leaf.args[:1]))]:
  changed=replace(event,body=(replace(assignment,rhs=replace(boundary,value=bad)),))
  original=replace(p,events=(*p.events[:-1],changed))
  corrected=replace(p,events=tuple(changed if j==i else e for j,e in enumerate(p.events)))
  result['controls'].append({'case':name,'original_test_placement':verdict(original),'index_preserved_placement':verdict(corrected)})
 return result

normal=leaf_controls()
module_source=Path(validator.__file__).read_text()
tree=ast.parse(module_source)
class RemoveDeferredLeafChecks(ast.NodeTransformer):
 count=0
 def visit_If(self,node):
  self.generic_visit(node)
  if ast.unparse(node.test)=='isinstance(value, UnsupportedSystemCall)':
   # Preserve argument traversal and return, remove signature/seed/owner checks.
   node.body=ast.parse('for argument in value.args:\n visit(argument)\nreturn').body
   self.count+=1
  return node
transform=RemoveDeferredLeafChecks();tree=transform.visit(tree);ast.fix_missing_locations(tree)
assert transform.count==1
namespace=dict(validator.__dict__)
exec(compile(tree,validator.__file__,'exec'),namespace)
with patch.object(validator,'validate_program_ir',namespace['validate_program_ir']):
 mutated=leaf_controls()
 suite=unittest.defaultTestLoader.loadTestsFromName('test_deferred_rdist.DeferredRdist.test_bad_raw_leaf_seed_and_signature_are_rejected')
 test_result=unittest.TestResult();suite.run(test_result)
 mutant_test={'run':test_result.testsRun,'errors':[e[1] for e in test_result.errors],'failures':[e[1] for e in test_result.failures]}
calibration={'candidate_digest':'e5df94a01dd621346777137e6c9073a690bf2ce58713a6db2cb5e0f62c7243e2','test_file_sha256':hashlib.sha256((R/'evas/tests/test_deferred_rdist.py').read_bytes()).hexdigest(),'validator_sha256':hashlib.sha256(module_source.encode()).hexdigest(),'mutation':'Remove only UnsupportedSystemCall signature/seed/owner checks, preserving argument traversal; executed as an in-memory replacement function.','production':normal,'mutant':mutated,'original_test_under_mutant':mutant_test}
output=Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/pr-review-20261025/test-scheme-audit/passing-negative/calibration.json')
output.write_text(json.dumps(calibration,indent=2)+'\n')
print(json.dumps({'calibration_written':str(output),'original_test_under_mutant':mutant_test},indent=2))

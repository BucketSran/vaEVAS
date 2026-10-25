"""Bounded static/compiler/arithmetic and forged-response probes; no kernel run."""
import json, pathlib, sys, unittest
from fractions import Fraction as F
from unittest.mock import patch
from types import SimpleNamespace
from probe_context import context
ROOT,OUTPUT=context()
DATA={'scope':{'source_commit':'15eb7216f7071edb7eda7a9b0c56b7e8933c4c79'}}
sys.path[:0]=[str(ROOT/'evas/src'),str(ROOT/'evas/tests')]
import test_idt,test_refinement
from test_stateless_expressions import compile_expr
from evas.ir import SCHEMA_VERSION
from evas import compile_sources
from test_affine import model,instance
out={'scope':'No simulator or build. Arithmetic uses exact binary64 Fractions. Counterfeit response runs original two unittest methods with subprocess boundary replaced.', 'source_root':'verified repository checkout','source_commit':DATA['scope']['source_commit']}
out['arithmetic']={
 'ordinary_if':{'input':'u(t)=t/3,t=1,threshold=binary64(0.3333333333333333)', 'derivation':'Sample RN(1/3) first; RN(1/3) equals threshold so strict > is false.', 'old_exact_truth':F(1,3)>F(.3333333333333333),'rounded_truth':float(F(1,3))>.3333333333333333,'rn_hex':float(F(1,3)).hex()},
 'cold_seed':{'input':'.62-.01 stored in real out; y=transition(out)-.61 at cold start','derivation':'out=RN(binary(.62)-binary(.01))=.61. Physical output .61-.61=0.','unrounded_old_expected':str(F(.62)-F(.01)-F(.61)),'rounded_state_hex':(.62-.01).hex(),'rounded_output_exact':str(F(.62-.01)-F(.61))},
 'cold_display_seed':{'input':'.125+2**-60 stored in real a','derivation':'2**-60 is below half ulp of .125; RN gives .125, so singleton voltage box need not include unrounded sum.','unrounded_expected':str(F(.125)+F(2**-60)),'rounded_state_hex':(.125+2**-60).hex()},
 'sampled_history':{'input':'b=RN(1/3); c=RN(RN(2**30*b - binary(357913941.3333333))+1)','derivation':'2**30 scales the rounded b exactly to the same binary64 subtractand; c=1. No original 1/3 uncertainty survives singleton real sample.','old_expected':str(F(2**30,3)-F(357913941.3333333)+1),'rn_result_hex':(2**30*float(F(1,3))-357913941.3333333+1).hex()}}
spoofs=[]
for module,cls,name,payload in [
 (test_refinement,test_refinement.RefinementContracts,'test_exact_dyadic_solution_after_refinement_dense_and_sparse',{'solutions':[{'voltages':[],'max_residual_ratio':0}]}),
 (test_idt,test_idt.IdtContracts,'test_raw_zero_voltage_feedback_preserves_explicit_initial_value',{'solutions':[]})]:
 case=cls(name);result=unittest.TestResult()
 fake=SimpleNamespace(returncode=0,stdout=json.dumps(payload),stderr='')
 with patch.object(module.subprocess,'run',return_value=fake) as calls:case.run(result)
 spoofs.append({'id':module.__name__+'.'+cls.__name__+'.'+name,'input':payload,'expected':'Test must reject missing voltage/state evidence.','actual_test_success':result.wasSuccessful(),'failures':result.failures,'errors':result.errors,'process_calls':calls.call_count})
out['counterfeit_response_calibration']=spoofs
p=compile_sources({'ordinary.va':model('if(V(u,r)>0.3333333333333333) tmp=7; else tmp=-3; V(y,r)<+tmp;','real tmp;')},[instance()])
a=compile_expr('V(u)>0.3333333333333333')
b=compile_expr('discard(V(a)>0)',declarations='analog function real discard; input x; real x; begin discard=1; end endfunction ')
out['compiler_structure']={'schema_version':SCHEMA_VERSION,'ordinary_if_step':repr(p.procedures[0].body[0].action), 'direct_equation_select':repr(a.contributions[0].rhs), 'constant_function_return':repr(b.contributions[0].rhs), 'interpretation':'Ordinary procedure predicate has sample boundary. Direct contribution Select has no sample boundary and keeps physical equation contract. Function return has explicit RealBoundary even when constant.'}
OUTPUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'forged_successes':[r['actual_test_success'] for r in spoofs],'schema':SCHEMA_VERSION,'output':str(OUTPUT)}))

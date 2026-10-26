#!/usr/bin/env python3
"""Run original test methods with real process responses and one response mutation.
No source or checker is modified. Protocol validation is diagnostic only.
"""
import copy,hashlib,importlib,json,os,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
R=pathlib.Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
S=pathlib.Path(__file__).resolve().parent
(S/'temp').mkdir(exist_ok=True);tempfile.tempdir=str(S/'temp')
sys.dont_write_bytecode=True
sys.path[:0]=[str(R/'evas/src'),str(R/'evas/tests')]
import evas.runtime as runtime
from evas.protocol import validate_response
from evas import compile_sources,Instance
original_run=subprocess.run
rows=[]
TARGETS=[('test_bound_step.BoundStepContracts.test_bound_caps_actual_nonlinear_integration_segments',['identity','drop_initial_solution','wrong_initial_voltage','wrong_final_voltage']),('test_bound_step.BoundStepContracts.test_sampled_clock_activation_preserves_physics_and_caps_inner_segments',['identity','wrong_times','drop_cross_event','wrong_cross_after','wrong_final_voltage'])]
for identifier,modes in TARGETS:
 for mode in modes:
  captures=[]
  def intercept(*args,**kwargs):
   result=original_run(*args,**kwargs)
   if result.returncode or not kwargs.get('input'):return result
   req=json.loads(kwargs['input']);data=json.loads(result.stdout);base=copy.deepcopy(data)
   active_mode=mode if not captures else 'identity'
   if active_mode=='drop_initial_solution':data['solutions']=data['solutions'][1:]
   elif active_mode=='wrong_initial_voltage':
    y=data['nodes'].index('y');data['solutions'][0]['voltages'][y]=100.
    data['observation_evidence']['voltage_bounds_V'][0][y]=[100.,100.]
   elif active_mode=='wrong_final_voltage':
    y=data['nodes'].index('y');data['solutions'][-1]['voltages'][y]=123.
    data['observation_evidence']['voltage_bounds_V'][-1][y]=[123.,123.]
   elif active_mode=='wrong_times':data['transient']['times']=[x+10 for x in data['transient']['times']]
   elif active_mode=='drop_cross_event':data['transient']['events']=[e for e in data['transient']['events'] if e['kind']!='cross']
   elif active_mode=='wrong_cross_after':next(e for e in data['transient']['events'] if e['kind']=='cross')['after']=[-1.]
   # Recompile the original source fixtures only to ask the production protocol
   # whether the mutated response remains legal. This does not affect the test.
   import test_bound_step as tb
   if 'nonlinear_integration' in identifier:p=tb.program('$bound_step(0.01); V(y,r)<+idt(pow(V(y,r),2),1);')
   else:p=tb.program('''@(initial_step) q=-1;
            @(cross(V(u,r)-0.7,+1)) q=$abstime;
            if(q>=0) if($abstime-q<0.2) $bound_step(0.01);
            V(y,r)<+idt(1/(1+V(u,r)*V(u,r)),0);''','real q;')
   try:validate_response(data,p,len(req['transient']['output_times']),req['transient']['output_times']);protocol='accepted'
   except Exception as e:protocol=type(e).__name__+': '+str(e)
   n=len(captures);prefix=S/(identifier.split('.')[-1]+'--'+mode+'--'+str(n))
   for name,payload in [('request',req),('original-response',base),('mutated-response',data)]:prefix.with_suffix('.'+name+'.json').write_text(json.dumps(payload,indent=2))
   diag=kwargs.get('env',{}).get('EVAS_DIAGNOSTICS_PATH')
   if diag and pathlib.Path(diag).exists():prefix.with_suffix('.diagnostics.json').write_bytes(pathlib.Path(diag).read_bytes())
   captures.append(dict(applied_mutation=active_mode,protocol=protocol,original_count=len(base['solutions']),mutated_count=len(data['solutions']),original_event_count=len(base['transient']['events']),mutated_event_count=len(data['transient']['events']),prefix=str(prefix)))
   return subprocess.CompletedProcess(result.args,result.returncode,json.dumps(data),result.stderr)
  suite=unittest.defaultTestLoader.loadTestsFromName(identifier)
  import io
  stream=io.StringIO()
  with patch('evas.runtime.subprocess.run',side_effect=intercept):outcome=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
  row=dict(id=identifier,mutation=mode,passed=outcome.wasSuccessful(),tests_run=outcome.testsRun,failures=len(outcome.failures),errors=len(outcome.errors),captures=captures,output=stream.getvalue())
  rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('captures','output')}),flush=True)
(S/'raw-results.json').write_text(json.dumps(dict(workspace=str(R),base='f210ebd59dfd5db78eea7ac0751479bc9e02beed',candidate_digest='e5df94a01dd621346777137e6c9073a690bf2ce58713a6db2cb5e0f62c7243e2',kernel_sha256=hashlib.sha256((R/'evas/rust_core/target/debug/evas-kernel').read_bytes()).hexdigest(),results=rows),indent=2))

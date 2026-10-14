"""Portable retained-point recomputation. No EVAS import, backend or local raw dependency."""
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as Q,localcontext
import ast,hashlib,importlib.util,json,math,re,sys
sys.dont_write_bytecode=True
D=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
I=load(D/'INVENTORY.json')
for path,entry in I['files'].items():
 assert sha(D/path)==entry['sha256'],path
 assert entry.get('kind') and entry.get('original_local_path'),path
# Import only pure functions from exact archived checker source, never its top-level CLI.
spec=importlib.util.spec_from_file_location('oracle',D/'oracles/n19_oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
namespace=dict(F=F,Q=Q,localcontext=localcontext,math=math,re=re,oracle=oracle)
tree=ast.parse((D/'provenance/pair_candidate.py').read_text());names={'native','finite_gate','expected'};defs=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names];assert len(defs)==3
exec(compile(ast.Module(body=defs,type_ignores=[]),'archived pure checker','exec'),namespace)
native,gate,expected=[namespace[n] for n in ['native','finite_gate','expected']]
assert gate([F(0)],F('1e-8')) and not gate([F('1e-3')],F('1e-8'))
for bad in [float('nan'),float('inf')]:
 try:gate([bad],F(1));raise AssertionError('nonfinite accepted')
 except ValueError:pass
M=load(D/'provenance/REFERENCE-MAP.json');P=load(D/'controls19/PAIRING.json')
assert sha(D/'provenance/pair_candidate.py')==P['script_sha256'];assert I['files']['provenance/REFERENCE-MAP.json']['original_sha256']==P['reference_map_sha256'];assert sha(D/'oracles/n19_oracle.py')==M['n19_oracle_sha256']
count=0;math_count=0;paired_pass=0;missing_count=0
for c,p in zip(M['cases'],P['cases']):
 assert c['id']==p['id'];folder=D/'controls19'/c['id'];s=load(folder/'SPEC.json');receipt=load(folder/'RECEIPT.json');assert sha(folder/'dut.va')==c['source_sha256'];assert sha(folder/'SPEC.json')==c['spec_sha256'];assert receipt['status']==p['candidate_status'];assert receipt['controls']==s;assert receipt['kernel_sha256']==load(D/'SOURCE-IDENTITY.json')['kernels']['release']['sha256']
 if receipt['status']!='completed':assert receipt['exception']==p['exception'];continue
 response=load(folder/'response.json');assert sha(folder/'response.json')==receipt['response_sha256'];assert response['transient']['times']==s['output_times']
 rows=native(folder/'reference/query-native.psf');missing=[];pairs=[];checks=[]
 for i,t in enumerate(s['output_times']):
  token=format(t,'.17g');matches=[r for r in rows if r['time']==Q(token)]
  if not matches:missing.append(token)
  for node,(lo,hi) in expected(c,t,s).items():
   j=response['nodes'].index(node);v=F(response['solutions'][i]['voltages'][j]);low,high=map(F,response['observation_evidence']['voltage_bounds_V'][i][j]);budget=F(str(c['budget_V']));err=max(abs(v-lo),abs(v-hi));checks.append(dict(time=token,node=node,contains=low<=lo<=hi<=high,error_V=float(err),pass_budget=err<=budget))
   for r in matches:pairs.append(dict(time=token,node=node,error_V=float(abs(v-F(r[node]))),pass_=abs(v-F(r[node]))<=budget))
 pairs=[{('pass' if k=='pass_' else k):v for k,v in x.items()} for x in pairs]
 assert checks==p['mathchecks'] and pairs==p['pairs'] and missing==p['missing_exact_native_tokens'],c['id']
 assert p['qualification'] is None and p['reference_qualification_not_upgraded']
 verdict=None if c['role']=='unscored_safety' else not missing and bool(pairs) and all(x['pass'] for x in pairs) and all(x['pass_budget'] for x in checks)
 assert verdict==p['finite_pair_pass'];paired_pass+=bool(verdict);missing_count+=bool(missing);count+=len(pairs);math_count+=len(checks)
assert len(M['cases'])==19 and paired_pass==8 and missing_count==5
# Exact original zero-V finalizer function, with known accept/reject/nonfinite calibration.
tree=ast.parse((D/'provenance/finalize_display_analysis.py').read_text());defs=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='gate'];ns={'Q':Q};exec(compile(ast.Module(body=defs,type_ignores=[]),'original zero budget','exec'),ns);zero=ns['gate'];assert zero(Q(0)) and not zero(Q('1e-30'))
try:zero(Q('NaN'));raise AssertionError('nonfinite accepted')
except ValueError:pass
A=load(D/'display4/ANALYSIS-original-budget.json');assert sha(D/'provenance/finalize_display_analysis.py')==A['finalizer_sha256'];assert 'incorrect' in A['budget_correction'];assert load(D/'display4/ANALYSIS.json')['cases'][0]['original_budget_V']==1e-8
variants=load(D/'display4/VARIANT-MAP.json');display_points=0
for c,vmap in zip(A['cases'],variants):
 folder=D/'display4'/c['label'];assert c['original_budget_V']==0;assert sha(folder/'dut.va')==vmap['variant_source_sha256'];assert sha(folder/'tb.scs')==vmap['unchanged_deck_sha256'];assert sha(folder/'REQUEST.json')==vmap['request_sha256']
 logs=load(folder/'spectre-log-excerpt.json');text='\n'.join(x['text'] for x in logs['lines']);callbacks=[dict(time=t,n=int(n)) for t,n in re.findall(r'N07 zero t=(\S+) n=(\d+)',text)];assert callbacks==c['spectre_callback_records'];assert 'spectre completes with 0 errors' in text
 rows=native(folder/'query-native.psf');missing=[format(t,'.17g') for t in c['request']['output_times'] if not any(r['time']==Q(format(t,'.17g')) for r in rows)];assert missing==c['exact_native_missing_tokens']
 if c['status']!='completed':assert 'event_resolution' in c['exception']['message'];continue
 response=load(folder/'response.json');assert sha(folder/'response.json')==c['response_sha256'];records=response['transient']['display_records'];assert records==c['candidate_callback_records'];assert [(Q(x['time']),x['n']) for x in callbacks]==[(Q(i)/8,i) for i in range(1,6)]
 pairs=[];j=response['nodes'].index('y')
 for i,t in enumerate(c['request']['output_times']):
  r=next(x for x in rows if x['time']==Q(format(t,'.17g')));val=Q.from_float(response['solutions'][i]['voltages'][j]);err=abs(val-r['y']);ae=abs(val-Q(i));assert zero(err) and zero(ae);pairs.append(dict(time=format(t,'.17g'),candidate=str(val),spectre=str(r['y']),error_V=str(err),analytic_error_V=str(ae)))
 assert pairs==c['pairs'] and c['finite_pair_pass'];display_points+=len(pairs)
assert display_points==12
# Original16: retained verdicts, not a re-run of the full original checker or 501-point raw comparison.
assert load(D/'original16/r01-summary.json')['completed']==12;assert load(D/'original16/regrade-summary.json')=={'completed':12,'original_checker_passed':12,'finite_spectre_observation_passed':6,'finite_spectre_output_passed':12}
witnesses=load(D/'original16/INPUT-OBSERVATION-WITNESSES.json')
for w in witnesses:
 def interp(points):
  a,b=points;t=w['finite_time'];return a['vin']+(t-a['time'])/(b['time']-a['time'])*(b['vin']-a['vin'])
 ev=interp(w['evas_saved_bracket']);sp=interp(w['spectre_native_bracket']);assert math.isclose(ev,w['evas_interpolated'],rel_tol=0,abs_tol=1e-12) and math.isclose(sp,w['spectre_interpolated'],rel_tol=0,abs_tol=1e-12);assert math.isclose(abs(ev-sp),w['difference'],rel_tol=0,abs_tol=1e-12) and w['difference']>w['original_tolerance']
assert len(witnesses)==6
source=load(D/'SOURCE-IDENTITY.json');assert len(source['source'])==325
assert source['kernels']['release']['sha256']=='867a112262b1311f07f0a612a594b471ad6c7b3c1a3bea9e207f7a06ea8cece4'
print(json.dumps(dict(inventory_files=len(I['files']),controls19_pairs=count,controls19_mathchecks=math_count,controls19_finite_pass=paired_pass,controls19_missing=missing_count,display4_zero_budget_points=display_points,original16_input_fail_witnesses=len(witnesses),source_files=325,backend_runs=0,scope='retained finite points only; full-file absence/full-native maxima/full original checker not re-certified'),indent=2))

# Every original input identity remains exact after curation.
for row in load(D/'original16/r01-results.json'):
 folder=D/'original16/inputs'/row['task_id']/row['condition']
 for name in ['dut.va','tb.scs']:
  assert sha(folder/name)==row['input_sha256']['run/work/verifier/'+row['condition']+'/'+name]
assert load(D/'provenance/COMMITTED-SOURCE.json')['source_commit']=='6b065e4f'

# Reference source/deck identity and actual PSF controls remain separately auditable.
for case in M['cases']:
 folder=D/'controls19'/case['id']/'reference'
 result=folder/'RESULT.json'
 if result.exists():
  r=load(result)
  assert sha(folder/'dut.va')==r['source_sha256']
  assert sha(folder/'tb.scs')==r['deck_sha256']
 header=(folder/'query-native.psf').read_text().split('\nVALUE\n',1)[0]
 assert '\n"simulator" "spectre"' in header
 assert re.search(r'^"version" "[^"\n]+"$',header,re.M)
for case in A['cases']:
 header=(D/'display4'/case['label']/'query-native.psf').read_text().split('\nVALUE\n',1)[0]
 for key,value in case['effective'].items():
  assert re.search(r'^"'+re.escape(key)+r'" (.+)$',header,re.M).group(1)==value
print('Original16 input hashes, candidate request/kernel identities, reference source/deck identities, display actual PSF settings verified.')

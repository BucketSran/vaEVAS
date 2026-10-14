"""Explicit candidate-only runner / read-only finite pairing. Never runs Spectre."""
import argparse, hashlib, importlib.util, json, math, re, subprocess, sys, time
from pathlib import Path
from fractions import Fraction as F
from decimal import Decimal as Q, localcontext
D=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mode',choices=['preflight','run','analyze'],required=True)
p.add_argument('--group',choices=['all','n08','n08c','n19','n07a','linear'],default='all')
p.add_argument('--identity',type=Path,help='complete fixed source/kernel receipt; required for candidate run')
p.add_argument('--source',type=Path);p.add_argument('--kernel',type=Path);p.add_argument('--kernel-sha256')
p.add_argument('--output',type=Path)
p.add_argument('--linear-raw',type=Path,help='completed raw directory of exactly frozen linear-controls-v2 inputs')
a=p.parse_args();sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest();load=lambda path:json.loads(path.read_text())
def dump(path,obj):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
m=load(D/'REFERENCE-MAP.json');cases=[c for c in m['cases'] if a.group=='all' or c['group']==a.group]
for c in cases:
 assert sha(Path(c['source']))==c['source_sha256'] and sha(Path(c['spec']))==c['spec_sha256']
 for key in ['reference_source','reference_deck','reference_psf','reference_log']:
  if key in c:assert sha(Path(c[key]))==c[key+'_sha256']
if a.mode=='preflight':print(json.dumps({'selected':len(cases),'ids':[c['id'] for c in cases],'candidate_executed':False}));sys.exit()
assert a.output and a.output.resolve().is_relative_to(D) and a.output.resolve()!=D,'output must belong to reference-plan'
out=a.output.resolve()
if a.mode=='run':
 assert a.source and a.kernel and a.kernel_sha256 and a.identity
 src=a.source.resolve();kernel=a.kernel.resolve();assert sha(kernel)==a.kernel_sha256
 assert not out.exists(),'use a fresh run directory'
 reviewed=load(a.identity);assert len(reviewed['source'])==325 and all(sha(src/path)==h for path,h in reviewed['source'].items());assert any(k['sha256']==a.kernel_sha256 for k in reviewed['kernels'].values())
 hashes={str(f.relative_to(src)):sha(f) for directory,suffix in [('evas/src','.py'),('evas/rust_core/src','.rs'),('evas/rust_core/ir/src','.rs')] for f in (src/directory).rglob('*'+suffix)}
 def identity():
  assert sha(kernel)==a.kernel_sha256
  assert all(sha(src/path)==h for path,h in reviewed['source'].items())
  assert all(sha(src/path)==h for path,h in hashes.items())
 git=lambda argv:subprocess.run(['git',*argv],cwd=src,text=True,capture_output=True,check=True).stdout.strip()
 dump(out/'IDENTITY.json',dict(kernel=str(kernel),kernel_sha256=a.kernel_sha256,source=str(src),source_sha256=hashes,head=git(['rev-parse','HEAD']),git_status=git(['status','--porcelain']),python=sys.version,script_sha256=sha(Path(__file__)),complete_reviewed_identity_path=str(a.identity.resolve()),complete_reviewed_identity_sha256=sha(a.identity),complete_source_files_checked=len(reviewed['source']),scope='candidate public API newly compiles frozen DUTs; no old DUT response reused'))
 sys.path.insert(0,str(src/'evas/src'));from evas import compile_sources,Instance,transient
 for c in cases:
  identity();spec=load(Path(c['spec']));folder=out/c['id'];folder.mkdir(parents=True);start=time.monotonic();record={'id':c['id'],'source_sha256':c['source_sha256'],'controls':spec,'kernel_sha256':a.kernel_sha256}
  try:
   program=compile_sources({'dut.va':Path(c['source']).read_text()},[Instance(**i) for i in spec['instances']]);dump(folder/'program.json',program.to_dict());record['program_sha256']=sha(folder/'program.json')
   options={k:spec[k] for k in ['stop','max_step','vabstol','reltol','strobetimes','timeout'] if k in spec}
   response=transient(program,spec['pwl'],spec['output_times'],kernel=kernel,**options);dump(folder/'response.json',response);record.update(status='completed',response_sha256=sha(folder/'response.json'))
  except Exception as error:record.update(status='rejected',exception={'type':type(error).__name__,'message':str(error),'detail':getattr(error,'detail',None)})
  identity();record['elapsed_seconds']=time.monotonic()-start;dump(folder/'RECEIPT.json',record);print(c['id'],record['status'],flush=True)
 dump(out/'AFTER.json',{'identities_unchanged':True,'kernel_sha256':sha(kernel),'cases':len(cases)});sys.exit()
# Pure analysis: no EVAS imports, kernel runs or writes outside requested output.
def native(path):
 rows=[];row=None;ended=False
 with path.open() as file:
  for line in file:
   if line.strip()=='VALUE':break
  else:raise ValueError('missing VALUE')
  for line in file:
   if line.strip()=='END':ended=True;break
   match=re.fullmatch(r'"([^\"]+)"\s+(\S+)',line.strip())
   if not match:raise ValueError('bad PSF row')
   k,v=match.groups();v=Q(v)
   if not v.is_finite():raise ValueError('nonfinite PSF')
   if k=='time':
    if row:rows.append(row)
    row={'time':v}
   elif row is None or k in row:raise ValueError('duplicate/missing time')
   else:row[k]=v
 if not ended:raise ValueError('missing END')
 if row:rows.append(row)
 if any(x['time']>=y['time'] for x,y in zip(rows,rows[1:])):raise ValueError('unordered PSF')
 return rows
def finite_gate(errors,budget):
 if not errors or any(not math.isfinite(float(x)) for x in errors):raise ValueError('empty/nonfinite gate')
 return max(errors)<=budget
cal={'accept':finite_gate([F(0)],F('1e-8')),'reject':not finite_gate([F('1e-3')],F('1e-8'))}
try:finite_gate([float('nan')],F(1));cal['nonfinite_rejected']=False
except ValueError:cal['nonfinite_rejected']=True
assert all(cal.values())
sp=importlib.util.spec_from_file_location('frozen_n19_oracle',D/'frozen/n19_oracle.py');oracle=importlib.util.module_from_spec(sp);sp.loader.exec_module(oracle)
assert sha(D/'frozen/n19_oracle.py')==m['n19_oracle_sha256']
def expected(c,t,spec):
 group=c['group'];case=c['case'];t=F(t)
 if group=='n19':return oracle.expected(case,t,'physical_history')
 if group=='n07a':return {'y':(F(round(float(t)*8)),)*2}
 if group=='n08':
  x=max(t-F(1,2),0)
  v=x if case=='parent' else max(t-F(1,4),0) if case=='boolean' else F(1,4)+max(t-F(3,8),0) if case=='held' else F(0) if t<=F(1,2) else F(math.atan(float(t))-math.atan(.5)) if case=='nonlinear' else F(float(x)-.125*(-math.expm1(-8*float(x))))
  return {'y':(v,v)}
 if group=='n08c':
  A,B,L=F(3e-8),F(3.02e-8),F(1.8);root=A+(B-A)*F(.9)/L;v=F(10**8)*max(t-root,0);return {'y':(v,v)}
 if group=='linear':
  if case=='linear_idt':v=F(1,4)+2*min(t,F(1,2))-max(t-F(1,2),0)
  elif case=='linear_held_gate':v=F(1,4)+2*min(t,F(1,2))-max(min(t,F(3,4))-F(1,2),0)
  else:
   with localcontext() as ctx:ctx.prec=80;v=F(Q(2) if t<=F(1,2) else -Q(1)+3*(-4*(Q(t.numerator)/Q(t.denominator)-Q('.5'))).exp())
  return {'y':(v,v)}
 raise ValueError(group)
results=[]
for c in cases:
 folder=out/c['id'];receipt=load(folder/'RECEIPT.json');spec=load(Path(c['spec']));row={'id':c['id'],'role':c['role'],'candidate_status':receipt['status'],'scope':'finite pair only, not original task score'}
 if receipt['status']!='completed':row.update(exception=receipt['exception'],qualification=False if c['role']!='unscored_safety' else None);results.append(row);continue
 response=load(folder/'response.json');assert sha(folder/'response.json')==receipt['response_sha256'];times=spec['output_times'];assert len(response['solutions'])==len(times) and response['transient']['times']==times
 if c['group']=='linear':
  if not a.linear_raw:row.update(reference='pending new actual run',qualification=None);results.append(row);continue
  reference=a.linear_raw/c['label'];assert sha(reference/'dut.va')==c['source_sha256'];assert sha(reference/'REQUEST.json')==c['spec_sha256'];psf=reference/'psf/tran.tran.tran'
 else:psf=Path(c['reference_psf'])
 rows=native(psf);missing=[];pairs=[];mathchecks=[]
 for i,t in enumerate(times):
  token=format(t,'.17g');matches=[r for r in rows if r['time']==Q(token)]
  if not matches:missing.append(token)
  for node,(lo,hi) in expected(c,t,spec).items():
   j=response['nodes'].index(node);v=F(response['solutions'][i]['voltages'][j]);bounds=response['observation_evidence']['voltage_bounds_V'][i][j];low,high=map(F,bounds);budget=F(str(c['budget_V']));point_error=max(abs(v-lo),abs(v-hi));mathchecks.append({'time':token,'node':node,'contains':low<=lo<=hi<=high,'error_V':float(point_error),'pass_budget':point_error<=budget})
   for r in matches:pairs.append({'time':token,'node':node,'error_V':float(abs(v-F(r[node]))),'pass':abs(v-F(r[node]))<=budget})
 callback=None
 if c['group']=='n07a' and c['role']=='exact_dyadic_control':
  text=Path(c['reference_log']).read_text();spectre=[(float(x),int(n)) for x,n in re.findall(r'N07 zero t=(\S+) n=(\d+)',text)];records=response['transient']['display_records'];candidate=[(r['time'],int(re.search(r'n=(\d+)',r['text'])[1])) for r in records];callback=candidate==spectre==[(i/8,i) for i in range(1,6)]
 qualification=None if c['role']=='unscored_safety' else not missing and bool(pairs) and all(r['pass'] for r in pairs) and all(r['pass_budget'] for r in mathchecks) and (callback is not False)
 row.update(missing_exact_native_tokens=missing,pairs=pairs,mathchecks=mathchecks,callback_sequence_equal=callback,finite_pair_pass=qualification,reference_qualification_not_upgraded=True,qualification=None,qualification_note='Final qualification additionally requires unchanged reference acceptance/configuration/full native mathematical checks; this script never upgrades old incomplete or diagnostic references')
 results.append(row)
dump(out/'PAIRING.json',{'script_sha256':sha(Path(__file__)),'reference_map_sha256':sha(D/'REFERENCE-MAP.json'),'calibration':cal,'candidate_identity':load(out/'IDENTITY.json'),'cases':results,'historical_scores_changed':False});print([(r['id'],r.get('finite_pair_pass'),r.get('missing_exact_native_tokens')) for r in results])

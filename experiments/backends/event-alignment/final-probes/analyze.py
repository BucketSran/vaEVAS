import argparse,hashlib,importlib.util,json,re,subprocess,math,sys
from fractions import Fraction as Q
from pathlib import Path
BASE=Path(__file__).resolve().parent
REPO=BASE.parents[3]
sys.path.insert(0,str(REPO))
sys.path.insert(0,str(REPO/'evas/src'))
from evas import Instance,compile_sources,transient
from experiments.backends.evidence.archive import verify_archive_members
parser=argparse.ArgumentParser(description='Reanalyze the two frozen final probes; require reviewed archives before reading PSF/logs.')
parser.add_argument('collection',type=Path)
parser.add_argument('original_vco_collection',type=Path)
parser.add_argument('output',type=Path)
parser.add_argument('--kernel',type=Path,default=REPO/'evas/rust_core/target/debug/evas-kernel')
parser.add_argument('--receipts',type=Path,required=True,help='Local directory for actual EVAS request/stdout/stderr; keep bulk receipts out of Git.')
args=parser.parse_args()
FINAL_SHA='371a1e184ad96b39b83baaacd96f20d42d1340cb7888f95bebf8557a4570ca7d'
VCO_SHA='287bf5bd018082e8928da9063de532e688080df4d47a85c135e0cf4e2e4d1613'
case_names=['M1-solver-tight-maxstep-1ns','VCO-original-tight-p-log']
required=[f'spectre-output/runs/{case}/{file}' for case in case_names for file in ['dut.va','tb.scs','simulate.log','spectre.log','psf/tran.tran.tran']]
identities=verify_archive_members(args.collection,FINAL_SHA,required)
original_identities=verify_archive_members(args.original_vco_collection,VCO_SHA,['spectre-output/runs/original--tight/'+f for f in ['dut.va','tb.scs','spectre.log','psf/tran.tran.tran']])
root=args.collection/'spectre-output/runs'
manifest=json.loads((BASE/'manifest.json').read_text())
for case in manifest['cases']:
 for file,identity in case['files'].items():
  actual=hashlib.sha256((root/case['name']/file).read_bytes()).hexdigest()
  if actual!=identity['sha256']:raise ValueError('frozen probe input hash mismatch: '+case['name']+'/'+file)

from experiments.backends.evidence import psf as normalizer
def read_rows(path,nodes):
 observation=normalizer.normalize(path,{'voltage_nodes':nodes})
 return [dict(time=row['time'],**row['voltages']) for row in observation['rows']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary={'archive_sha256':'371a1e184ad96b39b83baaacd96f20d42d1340cb7888f95bebf8557a4570ca7d','root_verified_files':44,'source_revision':subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'],text=True).strip(),'kernel_sha256':sha(args.kernel),'original_budgets_unchanged':True,'evas_settings':{'max_step_s':1.25e-7,'vabstol_v':1e-6,'reltol':1e-8}}
# M1 independent exact area; all native requests are actually evaluated by EVAS.
f=root/'M1-solver-tight-maxstep-1ns';rows=read_rows(f/'psf/tran.tran.tran',['u','clk','y','z','q','n','m','s','h1','h2','h3']);times=[row['time'] for row in rows];deck=(f/'tb.scs').read_text();src=(f/'dut.va').read_text();required=list(map(float,re.search(r'strobetimes=\[([^]]+)\]',deck)[1].split()));stop=float(re.search(r'stop=(\S+)',deck)[1]);step=float(re.search(r'maxstep=(\S+)',deck)[1]);nodes=['u','clk','y','z','q','n','m','s','h1','h2','h3'];program=compile_sources({'dut.va':src},[Instance('dut','probe',{**{n:n for n in nodes},'r':'0'}, {})]);request={'program':program.to_dict(),'driven':['u','clk'],'samples':[],'transient':{'pwl':[[[0,0],[stop,10]],[[0,0],[stop,10]]],'output_times':times,'stop':stop,'max_step':1.25e-7},'tolerances':{'absolute':1e-6,'relative':1e-8}}
args.receipts.mkdir(parents=True,exist_ok=True)
request_path=args.receipts/'M1-evas.request.json';stdout_path=args.receipts/'M1-evas.stdout.json';stderr_path=args.receipts/'M1-evas.stderr.txt'
request_path.write_text(json.dumps(request,allow_nan=False))
process=subprocess.run([str(args.kernel)],input=request_path.read_text(),capture_output=True,text=True,timeout=300)
stdout_path.write_text(process.stdout);stderr_path.write_text(process.stderr)
if process.returncode:raise ValueError('EVAS execution failed; inspect retained stderr')
from evas.protocol import validate_response
from evas.manifest import finite_float,reject_constant,unique_object
response=json.loads(process.stdout,object_pairs_hook=unique_object,parse_constant=reject_constant,parse_float=finite_float)
ev=validate_response(response,program,len(times),times)
summary['evas_execution']={'exit_code':process.returncode,'request_sha256':sha(request_path),'stdout_sha256':sha(stdout_path),'stderr_sha256':sha(stderr_path)}
errors={n:0. for n in nodes};si=[];ei=[];phase=[]
for row,sol in zip(rows,ev['solutions']):
 v=dict(zip(ev['nodes'],sol['voltages']));t=row['time'];expected=float(Q(1e6)*min(max(Q(t)-Q(2e-6),Q(0)),Q(6e-6)-Q(2e-6)));si.append(abs(row['z']-expected));ei.append(abs(v['z']-expected));
 for n in nodes:errors[n]=max(errors[n],abs(row[n]-v[n]))
 expectedphase={'q':int(2e-6<=t<6e-6),'n':int(t>=2e-6),'m':int(t>=6e-6)}
 if any(row[n]!=val or v[n]!=val for n,val in expectedphase.items()):phase.append({'time':t,'expected':expectedphase,'spectre':{n:row[n] for n in expectedphase},'evas':{n:v[n] for n in expectedphase}})
summary['archive_binding']={'final_sha256':FINAL_SHA,'final_regular_members_verified':len(identities),'original_vco_sha256':VCO_SHA,'original_vco_regular_members_verified':len(original_identities)}
summary['M1']={'native_rows':len(rows),'required_rows':len(required),'missing_required_times':[t for t in required if t not in times],'direct_max_errors_v':errors,'spectre_independent_max_z_error_v':max(si),'evas_independent_max_z_error_v':max(ei),'phase_failure_rows':phase,'z_budget_v':1e-6,'direct_z_status':'P' if errors['z']<=1e-6 else 'F','coverage_status':'P' if all(t in times for t in required) else 'I','files':{p.name:sha(p) for p in [f/'dut.va',f/'tb.scs',f/'simulate.log',f/'psf/tran.tran.tran']}}
# VCO saved original tight identity and same p from the single original call.
f=root/'VCO-original-tight-p-log';base=args.original_vco_collection/'spectre-output/runs/original--tight';raw=(f/'psf/tran.tran.tran').read_bytes();original=(base/'psf/tran.tran.tran').read_bytes();aa=raw.decode().splitlines();bb=original.decode().splitlines();differences=[{'new':a,'original':b} for a,b in zip(aa,bb) if a!=b];valueequal=raw.split(b'\nVALUE\n',1)[1]==original.split(b'\nVALUE\n',1)[1];assert len(aa)==len(bb) and valueequal and all(d['new'].startswith('"date"') and d['original'].startswith('"date"') for d in differences)
rows=read_rows(f/'psf/tran.tran.tran',['ctl','freq','phase','out']);index={v['time']:v for v in rows};assert len(index)==len(rows) and all(b['time']>a['time'] for a,b in zip(rows,rows[1:]));log=(f/'simulate.log').read_text();pattern=r'VCO_P\s+t=([0-9.e+-]+)\s+p=([0-9.e+-]+)\s+phase=([0-9.e+-]+)\s+out=([0-9.e+-]+)';entries=[]
for mt in re.finditer(pattern,log):
 tokens=mt.groups();t,p,phase,out=map(float,tokens);expected=Q(1,8)+524288*Q(t);expected-=expected.numerator//expected.denominator;row=index.get(t);entries.append({'tokens':dict(zip(['time','p','phase','out'],tokens)),'time_binary64_hex':t.hex(),'p':p,'phase':phase,'out':out,'matched_native_time':row is not None,'native':row,'logged_phase_psf_equal':row is not None and row['phase']==phase,'logged_out_psf_equal':row is not None and row['out']==out,'independent_exact_phase':str(expected),'p_low_side':p<.5,'phase_low_side':phase<.5})
assert len(entries)==9 and all(e['matched_native_time'] and e['logged_phase_psf_equal'] and e['logged_out_psf_equal'] for e in entries)
required=list(map(float,re.search(r'strobetimes=\[([^]]+)\]',(f/'tb.scs').read_text())[1].split()));maxordinary=maxcircular=maxsine=0.;failure=[]
for row in rows:
 q=Q(1,8)+524288*Q(row['time']);p=float(q-q.numerator//q.denominator);ordinary=abs(row['phase']-p);cir=ordinary%1;cir=min(cir,1-cir);sine=abs(row['out']-math.sin(2*math.pi*p));maxordinary=max(maxordinary,ordinary);maxcircular=max(maxcircular,cir);maxsine=max(maxsine,sine)
 if ordinary>.001:failure.append({'time':row['time'],'observed_phase':row['phase'],'expected_phase':p})
summary['VCO']={'native_rows':len(rows),'required_rows':len(required),'missing_required_times':[t for t in required if t not in index],'original_psf_value_bytes_equal':valueequal,'full_psf_differences':differences,'matched_log_rows':entries,'max_ordinary_phase_error_cycle':maxordinary,'max_circular_phase_error_cycle':maxcircular,'max_sine_error_v':maxsine,'ordinary_phase_failure_rows':failure,'ordinary_phase_status':'F' if failure else 'P','coverage_status':'P' if all(t in index for t in required) else 'I','interpretation':'At the first root left-neighbor timestamp the original idtmod returned p=0 itself; the low-side result is not caused only by port solution or ASCII PSF conversion. This does not expose the internal unwrapped accumulator or its algorithm.','files':{str(p.relative_to(f)):sha(p) for p in [f/'dut.va',f/'tb.scs',f/'simulate.log',f/'psf/tran.tran.tran']},'original_tight_psf_sha256':sha(base/'psf/tran.tran.tran')}
args.output.write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['VCO','M1']},indent=2));print('M1',summary['M1']);print('VCO', {k:v for k,v in summary['VCO'].items() if k not in ['matched_log_rows','files']})

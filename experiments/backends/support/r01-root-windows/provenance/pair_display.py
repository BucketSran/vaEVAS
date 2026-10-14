"""Run only the independent four display variants against an explicit frozen local candidate."""
import argparse,json,hashlib,sys,re,time
from pathlib import Path
from decimal import Decimal as Q
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--identity',type=Path,required=True);p.add_argument('--raw',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text());dump=lambda p,v:p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
D=Path(__file__).resolve().parent;inputs=D/'n07-display-controls-v1/inputs';assert a.output.resolve().is_relative_to(D) and not a.output.exists();a.output.mkdir();receipt=load(a.identity);kernel_sha='867a112262b1311f07f0a612a594b471ad6c7b3c1a3bea9e207f7a06ea8cece4'
def identity():
 assert len(receipt['source'])==325 and sha(a.kernel)==kernel_sha and all(sha(a.source/f)==h for f,h in receipt['source'].items())
identity();dump(a.output/'IDENTITY.json',{'source':str(a.source.resolve()),'identity_path':str(a.identity.resolve()),'identity_sha256':sha(a.identity),'source_files_checked':325,'kernel':str(a.kernel.resolve()),'kernel_sha256':kernel_sha,'script_sha256':sha(Path(__file__)),'variant_manifest_sha256':sha(inputs/'MANIFEST.json')})
manifest_checks={}
for base,names in [(inputs,['MANIFEST.json']),(a.raw,['MANIFEST.json','OUTPUT_MANIFEST.json'])]:
 for name in names:
  m=load(base/name);assert all(sha(base/f)==h for f,h in m.items());manifest_checks[str(base/name)]={'files':len(m),'sha256':sha(base/name),'all_match':True}
before=load(a.raw/'TOOL_IDENTITY.json');after=load(a.raw/'TOOL_IDENTITY_AFTER.json');assert before['file_sha256']==after['file_sha256'] and after['matches_before']
def native(path):
 text=path.read_text();header,values=text.split('\nVALUE\n',1);assert values.rstrip().endswith('END');rows=[];row=None
 for line in values.splitlines():
  if line=='END':break
  m=re.fullmatch(r'"([^\"]+)"\s+(\S+)',line.strip());assert m;key,val=m.groups();v=Q(val);assert v.is_finite()
  if key=='time':
   if row:rows.append(row)
   row={key:v}
  else:assert row is not None and key not in row;row[key]=v
 if row:rows.append(row)
 assert all(x['time']<y['time'] for x,y in zip(rows,rows[1:]));return header,rows
sys.path.insert(0,str(a.source/'evas/src'));from evas import compile_sources,Instance,transient
results=[]
for card in load(inputs/'PLAN.json'):
 label=card['label'];folder=a.output/label;folder.mkdir();spec=load(inputs/label/'REQUEST.json');assert spec['timeout']==120
 assert (a.raw/label/'dut.va').read_bytes()==(inputs/label/'dut.va').read_bytes() and (a.raw/label/'tb.scs').read_bytes()==(inputs/label/'tb.scs').read_bytes() and (a.raw/label/'REQUEST.json').read_bytes()==(inputs/label/'REQUEST.json').read_bytes()
 rr=load(a.raw/label/'RESULT.json');assert rr['returncode']==0 and not rr['timeout'] and rr['cleanup']['complete'];log=(a.raw/label/'spectre.log').read_text();assert 'spectre completes with 0 errors' in log
 header,rows=native(a.raw/label/'psf/tran.tran.tran');queries=spec['output_times'];missing=[format(t,'.17g') for t in queries if not any(r['time']==Q(format(t,'.17g')) for r in rows)];spectre_callbacks=[{'time':t,'n':int(n)} for t,n in re.findall(r'N07 zero t=(\S+) n=(\d+)',log)]
 result={'label':label,'source_sha256':sha(inputs/label/'dut.va'),'request':spec,'original_budget_V':1e-8,'spectre_receipt':rr,'exact_native_missing_tokens':missing,'spectre_callback_records':spectre_callbacks,'effective':{k:re.search(r'^"'+re.escape(k)+r'" (.+)$',header,re.M).group(1) for k in ['tolerance.relative','reltol','maxstep','method','abstol(V)']},'warnings':[x.strip() for x in log.splitlines() if 'WARNING (' in x]}
 identity();start=time.monotonic()
 try:
  program=compile_sources({'dut.va':(inputs/label/'dut.va').read_text()},[Instance(**i) for i in spec['instances']]);dump(folder/'program.json',program.to_dict());result['compiled']=True
  response=transient(program,spec['pwl'],queries,kernel=a.kernel,**{k:spec[k] for k in ['stop','max_step','vabstol','reltol','strobetimes','timeout']});dump(folder/'response.json',response);result['status']='completed';result['response_sha256']=sha(folder/'response.json');assert response['transient']['times']==queries
  cb=response['transient']['display_records'];result['candidate_callback_records']=cb
  candidate=[(Q(format(x['time'],'.17g')),int(re.search(r'n=(\d+)',x['text'])[1])) for x in cb];spectre=[(Q(x['time']),x['n']) for x in spectre_callbacks];expected=[(Q(i)/8,i) for i in range(1,6)]
  result['callback_sequence_pass']=candidate==spectre==expected
  j=response['nodes'].index('y');pairs=[]
  for i,t in enumerate(queries):
   matches=[r for r in rows if r['time']==Q(format(t,'.17g'))];v=Q.from_float(response['solutions'][i]['voltages'][j]);assert v.is_finite()
   for r in matches:pairs.append({'time':format(t,'.17g'),'candidate':str(v),'spectre':str(r['y']),'error_V':str(abs(v-r['y'])),'analytic_error_V':str(abs(v-Q(i)))})
  result['pairs']=pairs;result['finite_pair_pass']=not missing and len(pairs)==len(queries) and all(Q(x['error_V'])<=Q('1e-8') and Q(x['analytic_error_V'])<=Q('1e-8') for x in pairs) and result['callback_sequence_pass']
 except Exception as e:result.update(status='rejected',exception={'type':type(e).__name__,'message':str(e),'detail':getattr(e,'detail',None)})
 identity();result['elapsed_seconds']=time.monotonic()-start;dump(folder/'RECEIPT.json',result);results.append(result);print(label,result['status'],result.get('finite_pair_pass'),flush=True)
dump(a.output/'ANALYSIS.json',{'scope':'new independent 4 display variants; old 19 and strobe failures unchanged','manifest_checks':manifest_checks,'tool':before,'tool_before_after_equal':True,'cases':results,'source_kernel_unchanged_after_each_case':True,'interpolation':False,'checker_historical_scores_changed':False})

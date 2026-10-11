import pathlib,json,hashlib,tarfile,subprocess,collections
R=pathlib.Path(__file__).resolve().parents[1];ROOT=R.parents[1];B=R/'batch-ng-f03';name='foundation-openvaf_r_ngspice-f03-quoted';C=B/'collected'/name;L=C/'outputs'/name;A=R/'analysis-ng-f03-quoted-guarded-v1'
def rd(p):return json.loads(p.read_text())
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest(base,p):
 m=rd(p)
 for n,v in m.items():
  f=base/n;assert sh(f)==(v if isinstance(v,str) else v['sha256']),str(f)
  if isinstance(v,dict):assert f.stat().st_size==v['bytes'],str(f)
 return len(m)
src=rd(B/'SOURCE_MANIFEST.json');rev=rd(B/'SOURCE_PROVENANCE.json')['source_revision']
for n,d in src.items():assert sh(B/'repo'/n)==d and hashlib.sha256(subprocess.check_output(['git','show',rev+':'+n],cwd=ROOT)).hexdigest()==d,n
ni=manifest(B/'inputs',B/'inputs/MANIFEST.json');archive=rd(C/'COLLECTION.json')['archive_sha256'];assert sh(C/'raw.tar.gz')==archive
nt=0
with tarfile.open(C/'raw.tar.gz') as t:
 for m in t:
  if m.isfile():nt+=1;assert hashlib.sha256(t.extractfile(m).read()).hexdigest()==sh(C/m.name),m.name
nr=manifest(L,L/'FILE_MANIFEST.json');na=manifest(A,A/'ANALYSIS_MANIFEST.json');aid=rd(A/'ANALYSIS_IDENTITY.json')
for n,d in aid['source_hashes'].items():assert sh(A/'frozen-repo'/n)==d,n
rows=rd(A/'REANALYSIS.json');assert len(rows)==36
oldL=R/'batch-v2/collected/foundation-openvaf_r_ngspice-part1/outputs/foundation-openvaf_r_ngspice-part1';oldM=rd(oldL/'FILE_MANIFEST.json');out=[]
for row in rows:
 lab=row['label'];p=L/'runs'/lab;o=oldL/'runs'/lab;result=rd(p/'RESULT.json');assert row['identity']['original_result_sha256']==sh(p/'RESULT.json')
 for n,d in row['identity']['original_artifact_hashes'].items():assert sh(p/n)==d
 for n in ['dut.va','condition.json','requested_times.json','requested_settings.json','observation_plan.json','dut.osdi']:
  assert sh(p/n)==sh(o/n),lab+'/'+n
  assert sh(o/n)==oldM['runs/'+lab+'/'+n]['sha256']
  if n!='dut.osdi':assert sh(p/n)==sh(B/'inputs/runs/openvaf_r_ngspice'/lab/n)
 olddeck=(o/'tb.cir').read_text();newdeck=(p/'tb.cir').read_text();expect=olddeck
 for node in ['lt','le','gt','ge']:expect=expect.replace('v('+node+')','v("'+node+'")')
 assert newdeck==expect and sh(p/'tb.cir')==sh(B/'inputs/runs/openvaf_r_ngspice'/lab/'tb.cir')
 assert result['status']=='waveform_available' and sh(p/result['waveform'])==result['waveform_sha256']
 lines=(p/'waveform.txt').read_text().splitlines();heads=lines[0].split();raw=[list(map(float,x.split())) for x in lines[1:] if x.split()];condition=rd(p/'condition.json');u=condition['inputs']['u'][0][1];ix=heads.index('v(u)');mis=sum(x[ix]!=u for x in raw)
 assert all(len(x)==len(heads) for x in raw)
 tier=row['executed_target_tier'];assert row['qualified_tiers'][tier]=='evidence_insufficient';assert str(row['analysis_error']).startswith("ReadbackError('unsupported/mutable control command: wrdata waveform.txt")
 out.append({'label':lab,'requested_u':u,'requested_u_hex':float(u).hex(),'actual_u':sorted({x[ix] for x in raw}),'rows':len(raw),'u_mismatch_rows':mis,'t0':dict(zip(heads,raw[0])),'final':row['qualified_tiers'][tier],'analysis_error':row['analysis_error'],'numerical':row['assessment']['tiers'][tier]['numerical'],'input_exact':row['assessment']['input_exact_evidence'],'old_result_status':rd(o/'RESULT.json')['status'],'result_sha256':sh(p/'RESULT.json')})
# Verify every explicit diagnostic path/hash pointer; do not infer scientific qualification from diagnostics.
diagnostic=rd(R/'BREADTH-DIAGNOSTICS.json');ptr=[]
def walk(x):
 if isinstance(x,dict):
  if 'path' in x and 'sha256' in x:
   p=pathlib.Path(x['path']);p=p if p.is_absolute() else R/p;assert sh(p)==x['sha256'],str(p);ptr.append(str(p))
  for v in x.values():walk(v)
 elif isinstance(x,list):
  for v in x:walk(v)
walk(diagnostic)
res={'source_revision':rev,'source_files_git_verified':len(src),'input_manifest_files':ni,'archive_sha256':archive,'tar_members_verified':nt,'raw_manifest_files':nr,'analysis_manifest_files':na,'analysis_manifest_sha256':sh(A/'ANALYSIS_MANIFEST.json'),'analysis_revision':aid['revision'],'analysis_reanalyzer_sha256':aid['reanalyzer_sha256'],'diagnostics_sha256':sh(R/'BREADTH-DIAGNOSTICS.json'),'diagnostic_pointers_verified':len(ptr),'slots':out,'counts':{'execution':dict(collections.Counter(x['execution_status'] for x in rows)),'final':dict(collections.Counter(x['qualified_tiers'][x['executed_target_tier']] for x in rows))},'failures':[]}
(R/'review/astra-final-ng36-audit.json').write_text(json.dumps(res,indent=2)+'\n');print(json.dumps({k:v for k,v in res.items() if k!='slots'},indent=2))

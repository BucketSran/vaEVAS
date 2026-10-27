"""Integrate retained PR5 deliveries on the exact accepted PR4 main tree.

Uses the existing capture/generation tools. Does not change real checkout,
index or refs, run scientific tests, or accept/publish any candidate.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys

D=Path(__file__).resolve().parent
B=D.parents[1]
N=B/'pr4/post-review-integration-20261027'
P=N/'catalog-index-recovery-20261027'
S=D/'source'
MERGE=P/'merge-20261027/merge-verification.json'
PREP=B/'pr5/composed-consumers-grok-20261027'
FIX=B/'pr5/ci-inventory-completion-grok-20261027'
ARCHIVE_PARENT=None  # Bound to the accepted PR4 evidence branch at archive time.
PREFIX='evas/capabilities/observations/pr5-consumer-migration-20261027'
spec=importlib.util.spec_from_file_location('construction',N/'prepare_c0_candidate.py')
task=importlib.util.module_from_spec(spec);spec.loader.exec_module(task)
task.S,task.OUT=S,D
git,sha,write,PY=task.git,task.sha,task.write,task.PY
def load(p):return json.loads(p.read_text())
def env():return task.clean_env()|{'PYTHONDONTWRITEBYTECODE':'1'}
def base():
    r=load(MERGE)
    assert r['batch4_accepted'] and r['exact_reviewed_and_CI_tree']
    assert r['head']=='f974042a0af0b487568be935647caa322c3114fd'
    task.BASE=r['merge_commit'];return task.BASE
def invariant():
    task.preserved()
    assert S.resolve().is_relative_to(D.resolve())
def capture():
    parent=base()
    assert not S.exists() and not (D/'capture.json').exists()
    proof=load(PREP/'primary-verification.json');fix=load(FIX/'primary-verification.json')
    patches=[(PREP/'source.patch','b2396c2e1041186cf1c87fa15b0d97eba290985f5d4671ee262da820caa56ac2'),(FIX/'source.patch','ae8c42e477fa73ae91bbc2baa98702ffa2a9ee438c34f10c7e9ec683cb84e14b')]
    assert all(sha(p.read_bytes())==h for p,h in patches)
    assert git('rev-parse',parent+'^{tree}').decode().strip()==load(MERGE)['tree']
    S.mkdir();runtime=env()|{'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
    with (D/'export.stderr').open('xb') as err:
        producer=subprocess.Popen(['/usr/bin/git','--no-lazy-fetch','--git-dir='+str(task.GD),'--work-tree='+str(task.W),'archive',parent],env=runtime,stdout=subprocess.PIPE,stderr=err)
        consumer=subprocess.run(['/usr/bin/tar','-x','-C',str(S)],stdin=producer.stdout,env=runtime)
        producer.stdout.close();assert producer.wait()==consumer.returncode==0
    assert not (S/'.git').exists() and S.resolve().is_relative_to(D.resolve())
    subprocess.run(['/usr/bin/git','--git-dir='+str(S/'.git'),'--work-tree='+str(S),'init','--quiet','--template=','--initial-branch=local-pr5-consumers'],env=runtime,check=True)
    common=Path(git('rev-parse','--git-common-dir').decode().strip())
    (S/'.git/objects/info/alternates').write_text(str(common/'objects')+'\n')
    git('read-tree',parent,source=True);git('update-ref','HEAD',parent,source=True);invariant()
    for i,(patch,_) in enumerate(patches):
        r=subprocess.run(['/usr/bin/patch','-p1','-F','0','-i',str(patch)],cwd=S,env=runtime,capture_output=True)
        (D/f'patch-{i}.stdout').write_bytes(r.stdout);(D/f'patch-{i}.stderr').write_bytes(r.stderr)
        assert r.returncode==0
    source_paths=[r['path'] for r in proof['source_files']]+fix['changed_source_paths']
    assert len(source_paths)==len(set(source_paths))==22
    differences=[]
    for row in proof['source_files']:
        actual=sha((S/row['path']).read_bytes())
        if actual!=row['sha256']:
            assert row['path']=='.github/workflows/numerical-assurance.yml'
            prior=Path(proof['reconstruction'])/row['path']
            before=prior.read_text();after=(S/row['path']).read_text()
            assert before.replace('timeout-minutes: 10','timeout-minutes: 30',1)==after
            differences.append({'path':row['path'],'old_sha256':row['sha256'],'new_sha256':actual,'reason':'Retain adopted PR4 static job 30-minute timeout; migration hunk is identical.'})
    assert sha((S/fix['changed_source_paths'][0]).read_bytes())==fix['patched_sha256']
    tracked=git('diff','--name-only',source=True).decode().splitlines();new=git('ls-files','--others','--exclude-standard',source=True).decode().splitlines()
    assert set(tracked+new)==set(source_paths),(tracked,new)
    cap=task.make_commit(parent,source_paths,'Move current EVAS execution workers to validation adapters','capture')
    git('read-tree',cap['commit'],source=True);git('update-ref','HEAD',cap['commit'],parent,source=True)
    write(D/'capture.json',cap);(D/'source.patch').write_bytes(git('diff','--binary',parent,cap['commit']));(D/'source.commit').write_bytes(git('cat-file','commit',cap['commit']))
    observed=load(P/'assets.json');before=task.entries(observed['source_commit']);after=task.entries(cap['commit']);old={r['path']:r for r in observed['assets']};rows=[];changed=[]
    for path,(mode,oid) in sorted(after.items()):
        if before.get(path)==(mode,oid):
            row=old[path];assert row['git_blob_oid']==oid and row['git_mode']==mode;value,actual_mode=row['sha256'],row['actual_mode']
        else:
            raw=(S/path).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
            value,actual_mode=sha(raw),(S/path).stat().st_mode&0o777;changed.append(path)
        rows.append({'path':path,'sha256':value,'git_mode':mode,'actual_mode':actual_mode,'git_blob_oid':oid})
    write(D/'assets.json',dict(schema_version=1,producer='task-incremental-verified-asset-capture',source_commit=cap['commit'],source_tree=cap['tree'],source_object_format='sha1',source_kind='immutable-export',source_profile='git-tree-regular-blobs-v1',source_availability='local-only-before-publication',content_binding='verified-git-blob-oids',scope=observed['scope'],assets=rows,reuse_proof={'record':str(P/'assets.json'),'unchanged':len(rows)-len(changed),'changed':changed}))
    sys.path.insert(0,str(S/'scripts'))
    from run_regression import file_manifest,json_digest
    e1=load(task.I/'ci-40384473617/artifacts/python-regression-timings/python-regression.json')
    criteria=file_manifest(S,('evas/tests','evas/validation','evas/examples','experiments'));dut=file_manifest(S,('evas/src','evas/rust_core'))
    assert dut==e1['source_identity']['dut_files']
    old_criteria=dict(e1['source_identity']['criteria_files']);current=dict(criteria)
    delta=[p for p in sorted(set(old_criteria)|set(current)) if old_criteria.get(p)!=current.get(p)]
    assert set(delta)<=set(source_paths) and not any(p.startswith('evas/tests/') for p in delta)
    reused=[PREP/'primary-verification.json',FIX/'primary-verification.json',B/'pr5/comparison-remaining-grok-20261027/verification.json',B/'pr5/precision-history-grok-20261027/history-verification.json']
    write(D/'source-preparation.json',{'base':parent,'base_tree':load(MERGE)['tree'],'source_capture':cap['commit'],'source_paths':source_paths,'retained_patch_hashes':{str(p):h for p,h in patches},'preparation_byte_differences':differences,'matching_preparation_records':{str(p):sha(p.read_bytes()) for p in reused},'criteria_files':len(criteria),'criteria_id':json_digest(criteria),'criteria_changed_paths':delta,'DUT_files':len(dut),'DUT_id':json_digest(dut),'DUT_exact_E1':True,'scientific_test_owners_unchanged':True,'new_context_expected_if_full_regression_selected':True,'new_context_not_preaccepted':True,'scientific_execution':False,'scientific_qualification':False})
    invariant();print(json.dumps({'capture':cap['commit'],'tree':cap['tree'],'source_paths':len(source_paths),'criteria_delta':len(delta),'DUT_unchanged':True}),flush=True)

def discover():
    parent=base();invariant();assert sys.version_info[:2]==(3,12)
    assert not (D/'discovery-selection.json').exists()
    candidates=[]
    for config_path in (P/'config.json',N/'c1-rebind-20261027/config.json'):
        config=load(config_path)
        for item in config['discoveries']:
            p=Path(item['entry_file']);v=load(p);candidates.append((p,v,config['discovery_source_locators'][v['entry']['entry_id']]))
    for k in list(os.environ):
        if k.startswith('GIT_'):del os.environ[k]
    os.environ['CI_INVENTORY_BASE']=parent;os.environ['CI_INVENTORY_HEAD']=load(D/'capture.json')['commit']
    spec=importlib.util.spec_from_file_location('pr5_inventory',S/'scripts/capabilities/collect_ci_inventory.py');inventory=importlib.util.module_from_spec(spec);spec.loader.exec_module(inventory)
    parsed=inventory.parse_workflow((S/inventory.WORKFLOW).read_bytes());entries=parsed['entries']+[inventory.primary_entry(S,parsed)];assert len(entries)==31
    assets={r['path']:r['sha256'] for r in load(D/'assets.json')['assets']};chosen=[];new_count=0
    for i,entry in enumerate(entries):
        matching=[]
        for p,v,locator in candidates:
            r=v['receipt']
            if v['entry']!=entry or not r['complete'] or r['errors'] or r['unresolved_instances']:continue
            if assets.get(r['collector']['path'])!=r['collector']['sha256']:continue
            if any(assets.get(m['module_path'])!=m['module_sha256'] for m in r['methods']):continue
            matching.append((p,v,locator))
        if matching:
            p,v,locator=matching[0];assert git('show',locator['revision']+':'+locator['path'])==p.read_bytes()
            row={'entry_file':str(p),'entry_id':entry['entry_id'],'reused':True,'source_locator':locator,'sha256':sha(p.read_bytes()),'instances':v['receipt']['discovered_instances']}
        else:
            r=inventory.child(S,entry,90);assert r['complete'] and not r['errors'] and not r['unresolved_instances']
            p=D/'new-discovery'/('entry-%03d.json'%i);write(p,{'entry':entry,'receipt':r});new_count+=1
            row={'entry_file':str(p),'entry_id':entry['entry_id'],'reused':False,'sha256':sha(p.read_bytes()),'instances':r['discovered_instances']}
        row.update(start=entry['start'],pattern=entry['pattern']);chosen.append(row)
    counts={(r['start'],r['pattern']):r['instances'] for r in chosen}
    assert counts[('experiments/backends/paper','test_*.py')]==135
    assert counts[('experiments/backends/comparison','test_*.py')]==67
    assert counts[('evas/validation/support','test_*.py')]==226
    assert counts[('evas/tests','test*.py')]==3257
    write(D/'discovery-selection.json',{'entries':chosen,'entry_count':len(chosen),'reused':len(chosen)-new_count,'new_collections':new_count,'reuse_basis':'Exact workflow entry, collector, owner module SHA and immutable archived receipt; original identities retained.','test_bodies_executed':False,'scientific_qualification':False})
    invariant();print(json.dumps({'entries':len(chosen),'reused':len(chosen)-new_count,'new_collections':new_count}),flush=True)

def archive():
    base();invariant();assert not (D/'archive.json').exists()
    ARCHIVE_PARENT=load(P/'accepted-evidence-publication.json')['commit']
    dest=D/'archive-files'/PREFIX;dest.mkdir(parents=True)
    for name in ['capture.json','source.patch','source.commit','discovery-selection.json','source-preparation.json']:shutil.copyfile(D/name,dest/name)
    shutil.copytree(D/'new-discovery',dest/'new-discovery');shutil.copyfile(__file__,dest/'prepare_pr5.py')
    (dest/'README.md').write_text('# Current EVAS consumer migration construction\n\nFixed PR5 source and discovery evidence, built on accepted PR4 main. Existing paper/comparison/precision preparation retains its original identity. No scientific execution or qualification is granted by this archive. Final catalog generation, CI and independent Astra acceptance remain separate.\n')
    idx=D/'archive.index';git('read-tree',ARCHIVE_PARENT,index=idx);files=[]
    for p in sorted((D/'archive-files').rglob('*')):
        if not p.is_file():continue
        path=p.relative_to(D/'archive-files').as_posix();raw=p.read_bytes();oid=git('hash-object','-w','--stdin',data=raw).decode().strip();git('update-index','--add','--cacheinfo','100644,'+oid+','+path,index=idx);files.append({'path':path,'sha256':sha(raw),'bytes':len(raw)})
    tree=git('write-tree',index=idx).decode().strip();head=git('commit-tree',tree,'-p',ARCHIVE_PARENT,'-m','Archive current EVAS consumer migration construction').decode().strip();idx.unlink()
    write(D/'archive.json',{'parent':ARCHIVE_PARENT,'commit':head,'tree':tree,'prefix':PREFIX,'files':files,'published':False})
    config=load(P/'config.json');config.update(source_root=str(S),archive_repository=str(S),previous_data_dir=str(S/'evas/capabilities/data'),asset_receipt=str(D/'assets.json'),source_repositories={'vaevas':str(S)},discoveries=[],discovery_source_locators={})
    scripts=[]
    for row in load(D/'discovery-selection.json')['entries']:
        p=Path(row['entry_file']);config['discoveries'].append({'entry_file':str(p)})
        config['discovery_source_locators'][row['entry_id']]=row.get('source_locator')or{'kind':'git-object','repository':'vaevas','revision':head,'path':PREFIX+'/new-discovery/'+p.name}
        if row['start']=='scripts/tests' and row['pattern']=='test*.py':scripts.append(row['entry_id'])
    assert len(scripts)==1
    for bridge in config['bridge_evidence']:bridge['consumer_entry_ids']=scripts
    write(D/'config.json',config);invariant();print(json.dumps({'archive':head,'files':len(files)}),flush=True)

def generate():
    base();invariant()
    with (D/'generation.stdout').open('xb') as out,(D/'generation.stderr').open('xb') as err:
        r=subprocess.run([str(PY),'-B','scripts/capabilities/generate_catalog.py','--config',str(D/'config.json'),'--output',str(D/'catalog')],cwd=S,env=env(),stdout=out,stderr=err)
    assert r.returncode==0,'Read generation.stderr'
    report=load(D/'catalog/generation-report.json');previous=task.objects(S/'evas/capabilities/data');current=task.objects(D/'catalog/tree/evas/capabilities/data')
    assert all(current.get(k)==v for k,v in previous.items());assert report['previous_object_versions_retained']==len(previous) and not report['qualification_added']
    changed=[]
    for p in (D/'catalog/tree/evas/capabilities/data').glob('*.json'):
        target=S/'evas/capabilities/data'/p.name
        if p.read_bytes()!=target.read_bytes():target.write_bytes(p.read_bytes());changed.append(target.relative_to(S).as_posix())
    write(D/'generation-acceptance.json',{'paths':changed,'old_versions_retained':len(previous),'objects':report['objects'],'namespace_counts':report['namespace_counts'],'scientific_qualification':False})
    invariant();print(json.dumps({'generated_paths':len(changed),'old_versions_retained':len(previous)}),flush=True)

def precheck():
    parent=base();invariant();assert not (D/'precheck-acceptance.json').exists();results=[]
    e=env()|{'CARGO_TARGET_DIR':str(B/'pr4/bootstrap-integration-20261026/precheck-rust-target')}
    def run(name,argv):
        started=datetime.now(timezone.utc).isoformat()
        with (D/name).open('x') as out:
            out.write('COMMAND '+repr(argv)+'\n');out.flush();r=subprocess.run(argv,cwd=S,env=e,stdout=out,stderr=subprocess.STDOUT);out.write('\nreturncode='+str(r.returncode)+'\n')
        results.append({'command':argv,'receipt':str(D/name),'returncode':r.returncode,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat()});print(name,r.returncode,flush=True);assert r.returncode==0,name
    run('traceability-generate.txt',[str(PY),'-B','scripts/traceability.py','--catalog-data','evas/capabilities/data'])
    run('capability-render.txt',[str(PY),'-B','evas/capabilities/render.py'])
    paths=git('diff','--name-only',parent,source=True).decode().splitlines();sys.path.insert(0,str(S/'scripts'));import ci_selection
    write(D/'maintenance-plan.json',{'mode':'delivery','paths':paths,**ci_selection.classify(paths),'focused':False,'scope':'Complete PR5 quick gate; full scientific regression remains CI-only.'})
    run('maintenance-fast-checks.txt',[str(PY),'-B','scripts/ci_lint.py','--plan',str(D/'maintenance-plan.json')])
    run('capability-views.txt',[str(PY),'-B','evas/capabilities/render.py','--check'])
    run('ci-inventory-tests.txt',[str(PY),'-B','-m','unittest','discover','-s','scripts/tests','-p','test_ci_inventory.py','-v'])
    run('ci-selection-tests.txt',[str(PY),'-B','-m','unittest','discover','-s','scripts/tests','-p','test_ci_selection.py','-v'])
    run('capability-tests.txt',[str(PY),'-B','-m','unittest','discover','-s','evas/capabilities','-p','test_*.py','-v'])
    run('diff-check.txt',['/usr/bin/git','--git-dir='+str(S/'.git'),'--work-tree='+str(S),'diff','--check',parent])
    write(D/'precheck-acceptance.json',{'base':parent,'source_capture':load(D/'capture.json')['commit'],'paths':paths,'checks':results,'files':{p:sha((S/p).read_bytes()) for p in paths},'retained_migration_checks':load(D/'source-preparation.json')['matching_preparation_records'],'scientific_execution':False,'scientific_qualification':False})
    invariant()

def freeze():
    parent=base();invariant();pre=load(D/'precheck-acceptance.json');cap=load(D/'capture.json')
    assert all(x['returncode']==0 for x in pre['checks']) and all(sha((S/p).read_bytes())==h for p,h in pre['files'].items())
    generated=git('diff','--name-only',cap['commit'],source=True).decode().splitlines();final=task.make_commit(cap['commit'],generated,'Refresh migrated consumer catalog and traceability','final')
    final.update(base=parent,source_capture=cap['commit'],complete_paths=pre['paths'],precheck=str(D/'precheck-acceptance.json'),review='Fresh independent Astra Standards/Spec required',CI='pending',published=False,scientific_qualification=False)
    write(D/'final-candidate.json',final);(D/'candidate.patch').write_bytes(git('diff','--binary',parent,final['commit']));invariant();print(json.dumps({'commit':final['commit'],'tree':final['tree'],'paths':len(pre['paths'])}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','discover','archive','generate','precheck','freeze']);globals()[p.parse_args().stage]()

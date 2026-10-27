"""Integrate retained PR5 deliveries on the exact accepted PR4 main tree.

Uses the existing capture/generation tools. Does not change real checkout,
index or refs, run scientific tests, or accept/publish any candidate.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json, os, shutil, subprocess, sys

D=Path(__file__).resolve().parent
B=D.parents[2]
ORIGINAL=B/'pr5/consumer-integration-20261027/format-finalization-20261027'
OLD=D.parent/'candidate-integration'
FIX_WORKER=D.parent/'sol-implementation'
N=B/'pr4/post-review-integration-20261027'
P=N/'catalog-index-recovery-20261027'
S=D/'source'
MERGE=P/'merge-20261027/merge-verification.json'
PREP=B/'pr5/composed-consumers-grok-20261027'
FIX=B/'pr5/ci-inventory-completion-grok-20261027'
ARCHIVE_PARENT=None  # Bound to the accepted PR4 evidence branch at archive time.
PREFIX='evas/capabilities/observations/pr5-continuation-fixture-root-final-20261027'
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
    parent=base();previous=load(OLD/'capture.json');assert previous['commit']=='54effb075a42b6a2de55520e8bc335e6cfe0885a'
    assert not (D/'capture.json').exists()
    if S.exists():
        assert load(D/'stage-capture.json')['returncode']!=0
        invariant();assert git('rev-parse','HEAD',source=True).decode().strip()==previous['commit']
        assert not git('diff','--name-only',source=True).strip()
    else:
        S.mkdir();runtime=env()|{'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
        with (D/'export.stderr').open('xb') as err:
            producer=subprocess.Popen(['/usr/bin/git','--no-lazy-fetch','--git-dir='+str(task.GD),'--work-tree='+str(task.W),'archive',previous['commit']],env=runtime,stdout=subprocess.PIPE,stderr=err)
            consumer=subprocess.run(['/usr/bin/tar','-x','-C',str(S)],stdin=producer.stdout,env=runtime)
            producer.stdout.close();assert producer.wait()==consumer.returncode==0
        assert S.resolve().is_relative_to(D.resolve()) and not (S/'.git').exists()
        subprocess.run(['/usr/bin/git','--git-dir='+str(S/'.git'),'--work-tree='+str(S),'init','--quiet','--template=','--initial-branch=local-pr5-fixture-root'],env=runtime,check=True)
        assert Path(git('rev-parse','--git-common-dir',source=True).decode().strip()).resolve()==S/'.git'
        common=Path(git('rev-parse','--git-common-dir').decode().strip());(S/'.git/objects/info/alternates').write_text(str(common/'objects')+'\n')
        git('read-tree',previous['commit'],source=True);git('update-ref','HEAD',previous['commit'],source=True);invariant()
    path='experiments/backends/comparison/test_worker_adapter.py';target=S/path;raw=target.read_bytes()
    before=b'            root = Path(temp)\n';after_line=b'            root = Path(temp).resolve()\n'
    prefix,marker,body=raw.partition(b'class ContinuationIngestControls(');assert marker and body.count(before)==1
    fixed=prefix+marker+body.replace(before,after_line);target.write_bytes(fixed)
    assert git('diff','--name-only',source=True).decode().splitlines()==[path]
    cap=task.make_commit(previous['commit'],[path],'Resolve the synthetic continuation root before binding provenance controls','capture')
    git('read-tree',cap['commit'],source=True);git('update-ref','HEAD',cap['commit'],previous['commit'],source=True);write(D/'capture.json',cap)
    (D/'source.patch').write_bytes(git('diff','--binary',parent,cap['commit']));(D/'source.commit').write_bytes(git('cat-file','commit',cap['commit']))
    fix=load(OLD/'continuation-fix.json');fix['fixed_capture']=cap['commit'];fix['fixture_root_correction']={'path':path,'old_sha256':sha(raw),'new_sha256':sha(fixed),'old_red':str(OLD/'fixture-root-red.json'),'scope':'canonicalize synthetic temporary root only; production code unchanged'}
    write(D/'continuation-fix.json',fix);write(D/'fixture-root-correction.json',fix['fixture_root_correction'])
    observed=load(OLD/'assets.json');old_tree=task.entries(observed['source_commit']);new_tree=task.entries(cap['commit']);old_rows={r['path']:r for r in observed['assets']};rows=[];changed=[]
    for rel,(mode,oid) in sorted(new_tree.items()):
        if old_tree.get(rel)==(mode,oid):row=dict(old_rows[rel]);assert row['git_blob_oid']==oid
        else:
            data=(S/rel).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid
            row={'path':rel,'sha256':sha(data),'git_mode':mode,'actual_mode':(S/rel).stat().st_mode&0o777,'git_blob_oid':oid};changed.append(rel)
        rows.append(row)
    assert changed==[path]
    observed.update(source_commit=cap['commit'],source_tree=cap['tree'],assets=rows,reuse_proof={'record':str(OLD/'assets.json'),'unchanged':len(rows)-1,'changed':changed})
    write(D/'assets.json',observed)
    prep=load(OLD/'source-preparation.json');prep['source_capture']=cap['commit'];prep['continuation_fix']=fix
    prep['preparation_byte_differences'].append(fix['fixture_root_correction'])
    sys.path.insert(0,str(S/'scripts'));from run_regression import file_manifest,json_digest
    criteria=file_manifest(S,('evas/tests','evas/validation','evas/examples','experiments'));prep['criteria_id']=json_digest(criteria);assert len(criteria)==prep['criteria_files']
    parent_entries=task.entries(parent)
    assert all(parent_entries.get(p)==mode_oid for p,mode_oid in new_tree.items() if p.startswith(('evas/src/','evas/rust_core/','evas/tests/')))
    write(D/'source-preparation.json',prep)
    write(D/'precheck-reuse.json',{'prior_receipt':load(OLD/'precheck-reuse.json'),'fixture_correction':fix['fixture_root_correction'],'rerun':'All15 integrated adapter/continuation methods on canonicalized fixture; full required quick gate and generated checks use this exact source','scientific_execution':False})
    invariant();print(json.dumps({'capture':cap['commit'],'tree':cap['tree'],'fixture_paths':1}),flush=True)

def discover():
    parent=base();invariant();assert sys.version_info[:2]==(3,12)
    assert not (D/'discovery-selection.json').exists()
    candidates=[]
    for config_path in (OLD/'config.json',P/'config.json',N/'c1-rebind-20261027/config.json'):
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
            p=D/'new-discovery'/('entry-%03d.json'%i)
            retained=p.exists()
            if retained:
                saved=load(p);assert saved['entry']==entry;r=saved['receipt']
                assert assets.get(r['collector']['path'])==r['collector']['sha256']
                assert all(assets.get(m['module_path'])==m['module_sha256'] for m in r['methods'])
            else:
                r=inventory.child(S,entry,90)
            assert r['complete'] and not r['errors'] and not r['unresolved_instances']
            if not retained:write(p,{'entry':entry,'receipt':r})
            new_count+=1
            row={'entry_file':str(p),'entry_id':entry['entry_id'],'reused':False,'sha256':sha(p.read_bytes()),'instances':r['discovered_instances']}
        row.update(start=entry['start'],pattern=entry['pattern']);chosen.append(row)
    counts={(r['start'],r['pattern']):r['instances'] for r in chosen}
    assert counts[('experiments/backends/paper','test_*.py')]==135
    assert counts[('experiments/backends/comparison','test_*.py')]==78
    assert counts[('evas/validation/support','test_*.py')]==3
    assert counts[('experiments/backends/support','test_*.py')]==226
    assert counts[('evas/tests','test*.py')]==3257
    write(D/'discovery-selection.json',{'entries':chosen,'entry_count':len(chosen),'reused':len(chosen)-new_count,'new_collections':new_count,'reuse_basis':'Exact workflow entry, collector, owner module SHA and immutable archived receipt; original identities retained.','test_bodies_executed':False,'scientific_qualification':False})
    invariant();print(json.dumps({'entries':len(chosen),'reused':len(chosen)-new_count,'new_collections':new_count}),flush=True)

def archive():
    base();invariant();assert not (D/'archive.json').exists()
    ARCHIVE_PARENT=load(OLD/'archive.json')['commit']
    dest=D/'archive-files'/PREFIX;dest.mkdir(parents=True)
    for name in ['capture.json','source.patch','source.commit','discovery-selection.json','source-preparation.json','continuation-fix.json','fixture-root-correction.json','precheck-reuse.json']:shutil.copyfile(D/name,dest/name)
    (dest/'new-discovery').mkdir();shutil.copyfile(__file__,dest/'prepare_pr5.py')
    for p in (D/'new-discovery').glob('*.json'):shutil.copyfile(p,dest/'new-discovery'/p.name)
    shutil.copyfile(FIX_WORKER/'source.patch',dest/'worker-source.patch')
    shutil.copyfile(FIX_WORKER/'receipt.json',dest/'worker-receipt.json')
    shutil.copyfile(D.parent/'worker-intake.json',dest/'primary-worker-intake.json')
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
    extra_py=[p for p in load(D/'source-preparation.json')['source_paths'] if p.endswith('.py') and not p.startswith('scripts/')]
    targeted=load(D/'integrated-continuation-tests.json');assert targeted['returncode']==0 and targeted['source_capture']==load(D/'capture.json')['commit']
    assert all(sha((S/p).read_bytes())==h for p,h in targeted['files'].items());results.append(targeted)
    run('migration-python-lint.txt',[str(PY),'-m','ruff','check','--isolated','--select','E9,F63,F7,F82','--',*extra_py])
    run('capability-views.txt',[str(PY),'-B','evas/capabilities/render.py','--check'])
    run('diff-check.txt',['/usr/bin/git','--git-dir='+str(S/'.git'),'--work-tree='+str(S),'diff','--check',parent])
    write(D/'precheck-acceptance.json',{'base':parent,'source_capture':load(D/'capture.json')['commit'],'paths':paths,'checks':results,'files':{p:sha((S/p).read_bytes()) for p in paths},'reused_affected_tests':load(D/'precheck-reuse.json'),'retained_migration_checks':load(D/'source-preparation.json')['matching_preparation_records'],'scientific_execution':False,'scientific_qualification':False})
    invariant()

def freeze():
    parent=base();invariant();pre=load(D/'precheck-acceptance.json');cap=load(D/'capture.json')
    assert all(x['returncode']==0 for x in pre['checks']) and all(sha((S/p).read_bytes())==h for p,h in pre['files'].items())
    generated=git('diff','--name-only',cap['commit'],source=True).decode().splitlines();final=task.make_commit(cap['commit'],generated,'Refresh migrated consumer catalog and traceability','final')
    final.update(base=parent,source_capture=cap['commit'],complete_paths=pre['paths'],precheck=str(D/'precheck-acceptance.json'),review='Fresh independent Astra Standards/Spec required',CI='pending',published=False,scientific_qualification=False)
    write(D/'final-candidate.json',final);(D/'candidate.patch').write_bytes(git('diff','--binary',parent,final['commit']));invariant();print(json.dumps({'commit':final['commit'],'tree':final['tree'],'paths':len(pre['paths'])}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['capture','discover','archive','generate','precheck','freeze']);globals()[p.parse_args().stage]()

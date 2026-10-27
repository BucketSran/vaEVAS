"""Capture only exact authority and pointer on accepted C0, then use existing generators."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

R=Path(__file__).resolve().parent
B=R.parents[1]
D=R/'c0-candidate'
S=R/'source-c0'
N=B/'pr4/post-review-integration-20261027'
P=N/'catalog-index-recovery-20261027'
BASE='e10e1af5796f0cc7af3b6b5f5d26c420c0c03325'
PREFIX='evas/capabilities/observations/pr5-c0-context-authority-20261027'
spec=importlib.util.spec_from_file_location('existing_candidate_tools',N/'prepare_c0_candidate.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
t.S,t.OUT,t.BASE=S,D,BASE
git,sha,write,PY=t.git,t.sha,t.write,t.PY
load=lambda p:json.loads(p.read_text())
env=lambda:t.clean_env()|{'PYTHONDONTWRITEBYTECODE':'1'}
def invariant():
    t.preserved()
    assert S.resolve().is_relative_to(R)

def capture():
    invariant();proposal=load(R/'governance-draft/receipt.json')
    assert not proposal['effective_authority'] and proposal['context_count_before']==3
    assert not D.exists();D.mkdir()
    assert git('rev-parse','HEAD',source=True).decode().strip()==BASE
    assert not git('status','--porcelain=v1',source=True).strip()
    paths=['evas/validation/baselines/regression-v1.review.json','scripts/context-registration-bundle.json']
    for name,path in [('review.json',paths[0]),('bundle-pointer.json',paths[1])]:
        data=(R/'governance-draft'/name).read_bytes();assert sha(data)==proposal['files'][name]
        (S/path).write_bytes(data)
    assert sorted(git('diff','--name-only',source=True).decode().splitlines())==sorted(paths)
    cap=t.make_commit(BASE,paths,'Propose exact context authority for current EVAS consumer migration','capture')
    git('read-tree',cap['commit'],source=True);git('update-ref','HEAD',cap['commit'],BASE,source=True)
    write(D/'capture.json',cap)
    (D/'source.patch').write_bytes(git('diff','--binary',BASE,cap['commit']))
    (D/'source.commit').write_bytes(git('cat-file','commit',cap['commit']))
    old=load(P/'ci-40429826545/raw-intake-grok/artifacts/catalog-inventory/assets-before.json')
    prior={x['path']:x for x in old['assets']}
    before=t.entries(BASE);after=t.entries(cap['commit'])
    assert set(prior)==set(before)==set(after)
    for path,(mode,oid) in before.items():
        item=prior[path];assert item['git_mode']==mode and item['observed_blob_oid']==item['index_blob_oid']==oid
    rows=[];changed=[]
    for path,(mode,oid) in sorted(after.items()):
        if before[path]==(mode,oid):
            item=prior[path];value=item['sha256'];actual=item['actual_mode']
        else:
            data=(S/path).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==oid
            value=sha(data);actual=(S/path).stat().st_mode&0o777;changed.append(path)
        rows.append({'path':path,'sha256':value,'git_mode':mode,'actual_mode':actual,'git_blob_oid':oid})
    assert sorted(changed)==sorted(paths)
    write(D/'assets.json',{'schema_version':1,'producer':'task-incremental-verified-asset-capture',
        'source_commit':cap['commit'],'source_tree':cap['tree'],'source_object_format':'sha1',
        'source_kind':'immutable-export','source_profile':'git-tree-regular-blobs-v1',
        'source_availability':'local-only-before-publication','content_binding':'verified-git-blob-oids',
        'scope':old['scope'],'assets':rows,'reuse_proof':{'accepted_base':BASE,'accepted_CI':40429826545,'unchanged':len(rows)-2,'changed':changed}})
    rs=importlib.util.spec_from_file_location('pr5c0_manifest',S/'scripts/run_regression.py')
    runner=importlib.util.module_from_spec(rs);rs.loader.exec_module(runner)
    current=load(P/'ci-40429826545/raw-intake-grok/artifacts/python-regression-timings/python-regression.json')
    criteria=runner.file_manifest(S,('evas/tests','evas/validation','evas/examples','experiments'))
    dut=runner.file_manifest(S,('evas/src','evas/rust_core'))
    assert criteria==current['source_identity']['criteria_files']
    assert dut==current['source_identity']['dut_files']
    immutable=['.github/workflows/numerical-assurance.yml','evas/validation/baselines/regression-v1.json',
        'scripts/run_trusted_regression_gate.py','scripts/regression_gate.py','scripts/regression_context_registration.py',
        'scripts/materialize_registration_bundle.py','scripts/run_regression.py','scripts/ci_evidence.py',
        'scripts/regression_reason_identity.py','scripts/regression_observation_policy.json']
    for path in immutable:assert (S/path).read_bytes()==git('show',BASE+':'+path)
    write(D/'source-preparation.json',{'base':BASE,'source_capture':cap['commit'],'paths':paths,'criteria_id':runner.json_digest(criteria),
        'criteria_files':len(criteria),'dut_id':runner.json_digest(dut),'dut_files':len(dut),
        'criteria_DUT_exact_current_context':True,'unchanged_execution_and_trust_paths':immutable,
        'baseline_unchanged':True,'proposal':str(R/'governance-draft/receipt.json'),'scientific_execution':False,'scientific_qualification':False})
    invariant();print(json.dumps({'capture':cap['commit'],'paths':paths}),flush=True)

def discover():
    invariant();assert sys.version_info[:2]==(3,12)
    prior=load(P/'config.json');candidates=[]
    for row in prior['discoveries']:
        path=Path(row['entry_file']);value=load(path)
        candidates.append((path,value,prior['discovery_source_locators'][value['entry']['entry_id']]))
    spec=importlib.util.spec_from_file_location('pr5_c0_inventory',S/'scripts/capabilities/collect_ci_inventory.py')
    collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    parsed=collector.parse_workflow((S/collector.WORKFLOW).read_bytes())
    entries=parsed['entries']+[collector.primary_entry(S,parsed)];assert len(entries)==30
    assets={x['path']:x['sha256'] for x in load(D/'assets.json')['assets']}
    selected=[]
    for entry in entries:
        match=[]
        for path,value,locator in candidates:
            receipt=value['receipt']
            if value['entry']!=entry or not receipt['complete'] or receipt['errors'] or receipt['unresolved_instances']:continue
            if assets.get(receipt['collector']['path'])!=receipt['collector']['sha256']:continue
            if any(assets.get(m['module_path'])!=m['module_sha256'] for m in receipt['methods']):continue
            match.append((path,value,locator))
        assert len(match)==1,entry
        path,value,locator=match[0];assert git('show',locator['revision']+':'+locator['path'])==path.read_bytes()
        selected.append({'entry_id':entry['entry_id'],'entry_file':str(path),'sha256':sha(path.read_bytes()),'source_locator':locator,
            'start':entry['start'],'pattern':entry['pattern'],'instances':value['receipt']['discovered_instances'],'reused':True})
    write(D/'discovery-selection.json',{'entries':selected,'entry_count':30,'reused':30,'new_collections':0,
        'reuse_basis':'Identical workflow entry, collector and every owner module hash; existing immutable archived receipts.',
        'test_bodies_executed':False,'scientific_qualification':False})
    print('discovery:30 unchanged entries reused; no test bodies or new collection',flush=True)

def archive():
    invariant();parent=load(R/'bundle-archive.json')['commit']
    root=D/'archive-files';dest=root/PREFIX;dest.mkdir(parents=True)
    for name in ['capture.json','source.patch','source.commit','source-preparation.json','discovery-selection.json']:
        shutil.copyfile(D/name,dest/name)
    shutil.copyfile(__file__,dest/'prepare_c0_candidate.py')
    shutil.copyfile(R/'prepare_context_material.py',dest/'prepare_context_material.py')
    shutil.copyfile(R/'governance-draft/receipt.json',dest/'proposal-receipt.json')
    (dest/'README.md').write_text('# Exact PR5 context authority proposal\n\nThe C0 candidate changes only the exact authority record and data pointer, plus generated catalog/traceability. It retains accepted main criteria, DUT, collector, baseline and workflow. Thirty unchanged Python discovery entries are reused by exact source identity. No new collection or scientific execution is represented. Approval fields are proposed bytes and become effective only after independent exact review and C0 merge. Baseline append and PR5 activation remain separate.\n')
    idx=D/'archive.index';assert not idx.exists();git('read-tree',parent,index=idx);files=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        assert not path.is_symlink();data=path.read_bytes();assert len(data)<104857600
        relative=path.relative_to(root).as_posix();oid=git('hash-object','-w','--stdin',data=data).decode().strip()
        git('update-index','--add','--cacheinfo','100644,'+oid+','+relative,index=idx)
        files.append({'path':relative,'sha256':sha(data),'bytes':len(data)})
    tree=git('write-tree',index=idx).decode().strip();commit=git('commit-tree',tree,'-p',parent,'-m','Archive exact PR5 C0 authority construction').decode().strip();idx.unlink()
    write(D/'archive.json',{'commit':commit,'tree':tree,'parent':parent,'prefix':PREFIX,'files':files,'published':False})
    config=load(P/'config.json')
    config.update(source_root=str(S),archive_repository=str(S),previous_data_dir=str(S/'evas/capabilities/data'),
        asset_receipt=str(D/'assets.json'),source_repositories={'vaevas':str(S)},discoveries=[],discovery_source_locators={})
    for row in load(D/'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file':row['entry_file']})
        config['discovery_source_locators'][row['entry_id']]=row['source_locator']
    write(D/'config.json',config);print(json.dumps({'construction_archive':commit}),flush=True)

def generate():
    invariant()
    with (D/'generation.stdout').open('xb') as stdout,(D/'generation.stderr').open('xb') as stderr:
        proc=subprocess.run([str(PY),'-B','scripts/capabilities/generate_catalog.py','--config',str(D/'config.json'),'--output',str(D/'catalog')],cwd=S,env=env(),stdout=stdout,stderr=stderr)
    assert proc.returncode==0,'Read generation.stderr'
    report=load(D/'catalog/generation-report.json');previous=t.objects(S/'evas/capabilities/data');new=t.objects(D/'catalog/tree/evas/capabilities/data')
    assert all(new.get(k)==v for k,v in previous.items()) and report['previous_object_versions_retained']==len(previous)
    assert not report['qualification_added'];changed=[]
    for path in (D/'catalog/tree/evas/capabilities/data').glob('*.json'):
        target=S/'evas/capabilities/data'/path.name
        if path.read_bytes()!=target.read_bytes():target.write_bytes(path.read_bytes());changed.append(target.relative_to(S).as_posix())
    write(D/'generation-acceptance.json',{'paths':changed,'old_versions_retained':len(previous),
        'objects':report['objects'],'namespace_counts':report['namespace_counts'],'scientific_qualification':False})
    invariant();print(json.dumps({'generated_paths':len(changed),'old_versions_retained':len(previous)}),flush=True)

def precheck():
    invariant();results=[];e=env()|{'CARGO_TARGET_DIR':str(B/'pr4/bootstrap-integration-20261026/precheck-rust-target')}
    def run(name,argv):
        started=datetime.now(timezone.utc).isoformat()
        with (D/name).open('x') as out:
            out.write('COMMAND '+repr(argv)+'\n');out.flush();p=subprocess.run(argv,cwd=S,env=e,stdout=out,stderr=subprocess.STDOUT);out.write('\nreturncode='+str(p.returncode)+'\n')
        results.append({'command':argv,'receipt':str(D/name),'returncode':p.returncode,'started_at_utc':started,'finished_at_utc':datetime.now(timezone.utc).isoformat()})
        print(name,p.returncode,flush=True);assert p.returncode==0,name
    run('traceability-generate.txt',[str(PY),'-B','scripts/traceability.py','--catalog-data','evas/capabilities/data'])
    run('capability-render.txt',[str(PY),'-B','evas/capabilities/render.py'])
    paths=git('diff','--name-only',BASE,source=True).decode().splitlines()
    allowed=set(load(D/'capture.json')['paths']+load(D/'generation-acceptance.json')['paths']+['evas/docs/development/TRACEABILITY.md'])
    assert set(paths)<=allowed and set(load(D/'capture.json')['paths'])<=set(paths)
    plan={'mode':'delivery','maintenance':True,'regression':True,'focused':False,'paths':paths,
        'scope':'Exact context authority/pointer and generated assets. Complete fast maintenance precheck; full scientific execution is CI only.'}
    write(D/'maintenance-plan.json',plan)
    run('maintenance-fast-checks.txt',[str(PY),'-B','scripts/ci_lint.py','--plan',str(D/'maintenance-plan.json')])
    run('capability-views.txt',[str(PY),'-B','evas/capabilities/render.py','--check'])
    run('diff-check.txt',['/usr/bin/git','--no-lazy-fetch','--git-dir='+str(S/'.git'),'--work-tree='+str(S),'diff','--check',BASE])
    write(D/'precheck-acceptance.json',{'base':BASE,'source_capture':load(D/'capture.json')['commit'],'paths':paths,'checks':results,
        'files':{p:sha((S/p).read_bytes()) for p in paths},'actual_registration_controls':str(R/'governance-draft/validation.json'),
        'actual_registration_rejections':str(R/'governance-draft/negative-controls.json'),
        'unchanged_implementation_checks_reused':'Accepted main PR4 CI40429826545 and exact source-matched control receipts; no production code or checker changed.',
        'scientific_execution':False,'scientific_qualification':False})
    invariant()

def freeze():
    invariant();pre=load(D/'precheck-acceptance.json');assert all(x['returncode']==0 for x in pre['checks'])
    assert all(sha((S/p).read_bytes())==h for p,h in pre['files'].items())
    cap=load(D/'capture.json');paths=git('diff','--name-only',cap['commit'],source=True).decode().splitlines()
    result=t.make_commit(cap['commit'],paths,'Bind exact PR5 context authority to generated catalog','final')
    result.update(base=BASE,source_capture=cap['commit'],complete_paths=pre['paths'],
        precheck=str(D/'precheck-acceptance.json'),independent_review='pending',CI='pending',published=False)
    assert sorted(git('diff','--name-only',BASE,result['commit']).decode().splitlines())==sorted(pre['paths'])
    write(D/'final-candidate.json',result);(D/'candidate.patch').write_bytes(git('diff','--binary',BASE,result['commit']))
    invariant();print(json.dumps({'candidate':result['commit'],'tree':result['tree'],'paths':pre['paths']}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['capture','discover','archive','generate','precheck','freeze']);args=parser.parse_args();globals()[args.step]()


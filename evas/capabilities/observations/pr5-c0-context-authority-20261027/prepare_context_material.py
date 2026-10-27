"""Prepare exact registration data and a proposed authority; no adoption or push."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import gzip
import hashlib
import importlib.util
import json
import shutil
import sys

R=Path(__file__).resolve().parent
B=R.parents[1]
S=R/'source-c0'
W=R/'bundle-preparation-sonnet'
D=B/'pr5/comparison-continuation-fix-20261027/fixture-root-finalization'
C=D/'ci-40454789703'
N=B/'pr4/post-review-integration-20261027'
BASE='e10e1af5796f0cc7af3b6b5f5d26c420c0c03325'
HEAD='983b1ef6a4804c29483279ca34a7a92fce56a858'
PREFIX='evas/capabilities/observations/pr5-context-40454789703-20261027'
REVIEW=B/'night-coordination/pr5-exact-context-astra-r4-20261027/review-report.json'
spec=importlib.util.spec_from_file_location('registration_source_guard',N/'prepare_c0_candidate.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
t.S,t.OUT,t.BASE=S,R,BASE
git,sha,write=t.git,t.sha,t.write
load=lambda p:json.loads(p.read_text())
for name in ('http_proxy','https_proxy'):
    if t.os.environ.get(name):t.os.environ[name.upper()]=t.os.environ[name]
for name in ('ALL_PROXY','all_proxy'):t.os.environ.pop(name,None)

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);sys.modules[name]=result;spec.loader.exec_module(result);return result

def apis():
    for name in ['regression_gate.py','regression_context_registration.py']:
        assert (S/'scripts'/name).read_bytes()==git('show',BASE+':scripts/'+name)
    return module('pr5_governance_gate',S/'scripts/regression_gate.py'),module('pr5_governance_api',S/'scripts/regression_context_registration.py')

def current():
    p=N/'catalog-index-recovery-20261027/ci-40429826545/raw-intake-grok/artifacts/python-regression-timings/python-regression.json'
    assert sha(p.read_bytes())=='9097c8dce35461961b76782234c75e67d11f2c33a4f90d3abd98cc947ec9d981'
    return load(p)

def intake():
    t.preserved()
    done=load(W/'delegation-completed.json');assert done['status']=='completed' and not done['hasPendingChildRuns']
    receipt=load(W/'run-r3/receipt.json');verify=load(W/'verify-r2/verification.json')
    assert receipt['identity']['head']==HEAD and receipt['identity']['trusted_base']==BASE
    assert len(verify['checks'])==40 and verify['all_checks_ok'] and all(x['ok'] for x in verify['checks'].values())
    rows=[]
    for item in receipt['outputs']:
        path=W/'run-r3'/item['path']
        assert path.is_file() and not path.is_symlink() and path.stat().st_size==item['bytes']
        assert sha(path.read_bytes())==item['sha256'];rows.append(item)
    closure=load(C/'primary-raw-acceptance.json')
    assert closure['raw_source_binding_accepted'] and closure['merge_object_gap_closed']
    assert closure['candidate']==HEAD and closure['tree']=='7a99e40b4a58e00c138e4c721f3deaab1bdb2ba6'
    assert closure['synthetic_merge']['parents']==[BASE,HEAD]
    target=R/'bundle-bound';assert not target.exists();target.mkdir()
    for source in (W/'run-r3/bundle').iterdir():
        assert source.is_file() and not source.is_symlink()
        shutil.copyfile(source,target/source.name)
    old=(target/'dut_build').read_bytes();build=json.loads(old)
    phrase='whose commit object is NOT locally verified (inventory tree equals the head tree)'
    assert phrase in build['build_reference']
    build['build_reference']=build['build_reference'].replace(phrase,
        'whose commit parents ['+BASE+', '+HEAD+'] and tree were verified by the primary; '
        'the actual tree equals the fixed candidate; proof is retained in primary-raw-acceptance.json')
    (target/'dut_build').write_text(json.dumps(build,ensure_ascii=False,indent=2)+'\n')
    gate,api=apis();new=load(target/'report.json');old_report=current()
    mapping=load(W/'run-r3/obligation-map-draft.json')
    assert len(mapping)==7737
    api.mapped_obligations({'obligation_mapping':mapping},gate,old_report,new)
    provenance=copy.deepcopy(load(W/'run-r3/bundle-byte-binding.json')['entry_provenance_preview'])
    provenance['snapshot_reference']='https://github.com/BucketSran/vaEVAS/tree/'+HEAD+'; actual CI merge '+closure['synthetic_merge']['commit']+' parents/tree verified in primary-raw-acceptance.json'
    blobs={p.name:p.read_bytes() for p in target.iterdir() if p.name!='report.json'}
    sub=gate.execution_subject(old_report)
    harness={'artifacts':{role:{'sha256':sha(data)} for role,data in blobs.items()},
        'current_dut':{'manifest_sha256':sub['dut_files_sha256'],'kernel_sha256':sub['kernel_sha256']},
        'e1':{'raw_sha256':sha((target/'report.json').read_bytes()),'execution_subject':gate.execution_subject(new)}}
    api.evidence(harness,blobs,gate,new,{'source_identity':provenance},sub)
    assert gate.compare_report(old_report,load(S/api.BASELINE))['merge_allowed']
    rejection=gate.compare_report(new,load(S/api.BASELINE))
    assert rejection['differences']==['expected exactly one matching trusted baseline context']
    files=[{'name':p.name,'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(target.iterdir())]
    assert len(files)==10
    write(R/'bundle-intake.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'candidate':HEAD,'worker_task':done['taskId'],
        'worker_receipt':str(W/'run-r3/receipt.json'),'worker_outputs_verified':rows,'worker40_checks_reused':str(W/'verify-r2/verification.json'),
        'primary_merge_closure':str(C/'primary-raw-acceptance.json'),'provenance':provenance,'files':files,
        'metadata_correction':{'file':'dut_build','old_sha256':sha(old),'new_sha256':sha((target/'dut_build').read_bytes()),
            'scope':'updated factual source-closure reference only; recipe, DUT, kernel, report, artifacts and all scientific inputs unchanged'},
        'primary_new_checks':['production evidence on corrected metadata and exact bytes','mapped_obligations for all7737','C0 accepted and new report rejected on unchanged baseline'],
        'worker_failures_preserved':{'outputs':True,'older_script_versions':False,'limitation':'Worker edited scripts in place; original failing script bytes were not retained and are unknown.'},
        'effective_authority':False,'scientific_qualification':False})
    t.preserved();print('intake:10files and7737 mapping bound; source-closure text corrected in new copy',flush=True)

def archive():
    t.preserved();intake=load(R/'bundle-intake.json')
    parent=load(D/'publication.json')['archive'];assert parent=='e3f642ce8c5e763ef0e14c06a9b927747a31ebfb'
    root=R/'archive-data';assert not root.exists();dest=root/PREFIX;bundle=dest/'bundle';bundle.mkdir(parents=True)
    storage=[]
    for item in intake['files']:
        source=R/'bundle-bound'/item['name'];data=source.read_bytes();assert sha(data)==item['sha256']
        encoding='identity'
        if item['name']=='kernel_binary':
            data=git('show','ae1cd723c5b24bd17af866805d7e6ac742cd8b86:evas/capabilities/observations/pr4-e1-40384473617/bundle/kernel_binary')
            decoded=gzip.decompress(data);assert sha(decoded)==item['sha256'] and len(decoded)==item['bytes']
            encoding='gzip'
        (bundle/item['name']).write_bytes(data)
        storage.append({'name':item['name'],'stored_bytes':len(data),'stored_sha256':sha(data),
            'materialized_bytes':item['bytes'],'materialized_sha256':item['sha256'],'encoding':encoding})
    kernel={'encoding':'gzip','decoded_bytes':105862328,'decoded_sha256':'b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe'}
    write(dest/'storage.json',{'schema_version':1,'files':storage,'kernel_binary':kernel,'scientific_qualification':False,'codec':'unchanged accepted schema2; exact prior compressed kernel reused'})
    copies=[(R/'bundle-intake.json','proof/bundle-intake.json'),(C/'primary-raw-acceptance.json','proof/primary-raw-acceptance.json'),
        (C/'raw-intake-sol/receipt.json','proof/raw-worker-receipt.json'),(C/'raw-intake-sol/raw-verification.json','proof/raw-verification.json'),
        (C/'raw-intake-sol/verification-r3/source-identity-field-bindings.json','proof/source-identity-field-bindings.json'),
        (C/'raw-intake-sol/artifact-download-receipt.json','proof/artifact-download-receipt.json'),
        (D/'review-r3-acceptance.json','source-review/primary-acceptance.json'),
        (B/'night-coordination/pr5-continuation-fix-astra-r3-20261027/review-report.json','source-review/review-report.json'),
        (W/'REPORT.md','worker/REPORT.md'),(W/'prepare_bundle.py','worker/prepare_bundle.py'),
        (W/'verify.py','worker/verify.py'),(W/'delegation-completed.json','worker/delegation-completed.json'),
        (W/'run-r3/receipt.json','worker/receipt.json'),(W/'verify-r2/verification.json','worker/verification.json')]
    copies += [(W/'run-r3'/name,'proof/'+name) for name in ['stream-boundaries.json','bundle-byte-binding.json','obligation-map-draft.json','obligation-map-proof.json']]
    for source,relative in copies:
        target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    (dest/'README.md').write_text('# PR5 observed context evidence\n\nFixed983b, CI40454789703 attempt1. The CI completed with19 successful jobs and failed admission plus aggregate gate because the new criteria context was unregistered. Source repair passed the independent Astra R3 review. This archive preserves actual observations and draft7737-condition mapping; exact context approval, baseline append and activation remain pending. Scientific qualification is false.\n\nNine role files use their original/constructed bytes; kernel_binary reuses the previously accepted single-member gzip representation of the identical actual kernel. The primary corrected only the dut_build source-closure reference in a new copy after verifying merge33ed0fa1. The worker originals and failed outputs are retained locally; original failing script versions were not retained, so their exact replay is unavailable. Current worker scripts and successful control receipts are preserved here. Full13zip/467members remain in the owning run directory.\n')
    index=R/'bundle-archive.index';assert not index.exists();git('read-tree',parent,index=index);files=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file():continue
        assert not path.is_symlink();data=path.read_bytes();assert len(data)<104857600
        rel=path.relative_to(root).as_posix();oid=git('hash-object','-w','--stdin',data=data).decode().strip()
        git('update-index','--add','--cacheinfo','100644,'+oid+','+rel,index=index)
        files.append({'path':rel,'sha256':sha(data),'bytes':len(data),'blob':oid})
    tree=git('write-tree',index=index).decode().strip();commit=git('commit-tree',tree,'-p',parent,'-m','Archive fixed PR5 observations for exact context registration').decode().strip();index.unlink()
    write(R/'bundle-archive.json',{'commit':commit,'tree':tree,'parent':parent,'prefix':PREFIX,'files':files,
        'pointer':{'schema_version':2,'commit':commit,'prefix':PREFIX+'/bundle','kernel_binary':kernel},
        'published':False,'scientific_qualification':False})
    t.preserved();print(json.dumps({'bundle_archive':commit,'files':len(files),'published':False}),flush=True)

def governance():
    t.preserved();out=R/'governance-draft';assert not out.exists();out.mkdir()
    gate,api=apis();arc=load(R/'bundle-archive.json');intake=load(R/'bundle-intake.json')
    target=R/'bundle-bound';raw=(target/'report.json').read_bytes();new=json.loads(raw);old=current()
    baseline=load(S/api.BASELINE);prior_review=load(S/api.REVIEW)
    url='https://raw.githubusercontent.com/BucketSran/vaEVAS/'+arc['commit']+'/'+PREFIX
    exact_reference=str(REVIEW)+'; PROPOSED exact decision, effective only after fresh independent acceptance of these bytes and C0 authority merge; raw source proof: '+url+'/proof/primary-raw-acceptance.json'
    provenance=copy.deepcopy(intake['provenance']);provenance['raw_reference']=url+'/bundle/report.json'
    provenance['snapshot_reference'] += '; '+url+'/proof/primary-raw-acceptance.json'
    proposed_review={'status':'approved','semantic_status':'pending','reviewer':'independent codex/gpt-6-astra, max/default, fresh context','reference':exact_reference}
    entry=gate.propose_baseline(new,provenance,proposed_review)['contexts'][0]
    original=load(W/'run-r3/obligation-map-draft.json');mapping=copy.deepcopy(original)
    for row in mapping:row['review_reference']=exact_reference
    assert all({k:v for k,v in a.items() if k!='review_reference'}=={k:v for k,v in b.items() if k!='review_reference'} for a,b in zip(original,mapping))
    blobs={p.name:p.read_bytes() for p in target.iterdir() if p.name!='report.json'}
    subject=gate.execution_subject(old)
    auth={'schema_version':1,'id':'pr5-consumer-migration-CI40454789703','action':'append-one-criteria-collector-context',
        'old_baseline_canonical_sha256':api.digest(baseline),'previous_context_sha256':api.digest(gate._context(old)),
        'new_entry_canonical_sha256':api.digest(entry),'current_dut':{'manifest_sha256':subject['dut_files_sha256'],'kernel_sha256':subject['kernel_sha256']},
        'e1':{'raw_sha256':sha(raw),'canonical_report_sha256':api.digest(new),'execution_subject':gate.execution_subject(new),
              'raw_source_sha256':api.digest(new['source_identity']),'entry_source_sha256':api.digest(entry['source_identity']),'entry_review_sha256':api.digest(entry['review'])},
        'artifacts':{role:{'sha256':sha(data),'locator':url+'/bundle/'+role+('; decode schema2 gzip per '+url+'/storage.json' if role=='kernel_binary' else '')} for role,data in blobs.items()},
        'obligation_mapping':mapping}
    auth['independent_review']={'decision':'approved-exact-context-registration','reviewer':proposed_review['reviewer'],'reference':exact_reference,
        'entry_sha256':api.digest(entry),'evidence_sha256':api.digest(auth['e1']),'mapping_sha256':api.digest(mapping),'semantic_boundary':'human-exact-review-not-JSON-authentication'}
    authority=copy.deepcopy(prior_review);authority.setdefault(api.GOVERNANCE,[]).append(auth)
    assert authority[api.GOVERNANCE][:-1]==prior_review.get(api.GOVERNANCE,[])
    appended=copy.deepcopy(baseline);appended['contexts'].append(entry)
    result=api.validate_context_registration(gate,old,baseline,appended,authority,authority,[api.BASELINE],raw,blobs)
    assert result['merge_allowed'] and result['transition']['registration'] and not result['raw_successful'] and not result['semantic_qualification'],result
    negatives=[]
    for name,trusted,head,raw_bytes in [('HEAD-only authorization',prior_review,appended,raw),('changed raw',authority,appended,raw+b'\n')]:
        rejected=api.validate_context_registration(gate,old,baseline,head,trusted,authority,[api.BASELINE],raw_bytes,blobs)
        assert not rejected['merge_allowed'];negatives.append({'case':name,'differences':rejected['differences']})
    changed=copy.deepcopy(appended);changed['contexts'][0]['review']['reference']+=' changed'
    rejected=api.validate_context_registration(gate,old,baseline,changed,authority,authority,[api.BASELINE],raw,blobs)
    assert not rejected['merge_allowed'];negatives.append({'case':'changed old context','differences':rejected['differences']})
    for name,value in [('entry.json',entry),('authority.json',auth),('review.json',authority),('baseline-append.json',appended),('bundle-pointer.json',arc['pointer']),('validation.json',result),('negative-controls.json',negatives)]:
        write(out/name,value)
    assert appended['contexts'][:-1]==baseline['contexts']
    write(out/'receipt.json',{'kind':'unadopted-exact-context-proposal','candidate':HEAD,'trusted_base':BASE,'effective_authority':False,
        'independent_exact_review':'pending','review_destination':str(REVIEW),'mapping':'7737 exact preserved; only review_reference updated',
        'context_count_before':len(baseline['contexts']),'context_count_after':len(appended['contexts']),
        'entry_canonical_sha256':api.digest(entry),'authority_canonical_sha256':api.digest(auth),
        'baseline_append_bytes':(out/'baseline-append.json').stat().st_size,'old_contexts_unchanged':True,'scientific_qualification':False,
        'files':{p.name:sha(p.read_bytes()) for p in out.iterdir() if p.is_file()}})
    t.preserved();print(json.dumps({'proposal':'ready, not adopted','contexts':len(appended['contexts']),'baseline_bytes':(out/'baseline-append.json').stat().st_size,'negatives':len(negatives)}),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['intake','archive','governance']);args=parser.parse_args()
    globals()[args.step]()


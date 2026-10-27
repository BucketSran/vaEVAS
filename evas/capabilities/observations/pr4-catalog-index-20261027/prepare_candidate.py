"""Bind accepted C1 source to the adopted context and regenerate its catalog."""
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

D = Path(__file__).resolve().parent
N = D.parent
B = N.parents[1]
S = D / 'source'
BASE = 'cfe0ac45f75677fbd1e4dbf6243740b16d1caab0'
OLD_PR = '2a0e173a2164f6f7a0b544e344e4463226ad26c1'
ARCHIVE_PARENT = '9c4e6bafcd940530fe9bcea7a143139eda23dc6b'
PREFIX = 'evas/capabilities/observations/pr4-catalog-index-20261027'
OLD = N / 'c1-rebind-20261027'
PREP = B / 'pr6/catalog-validation-scan-grok-20261027'
spec = importlib.util.spec_from_file_location('prior_c0_construction', N / 'prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, BASE
PY = task.PY
git, write, sha = task.git, task.write, task.sha


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}


def invariant():
    task.preserved()
    assert S.resolve().is_relative_to(D.resolve())


def capture():
    assert not S.exists() and not (D / 'capture.json').exists()
    assert load(OLD / 'publication.json')['candidate'] == OLD_PR
    accepted = load(PREP / 'primary-verification.json')
    patch = PREP / 'source.patch'
    assert sha(patch.read_bytes()) == accepted['patch_sha256']
    assert git('rev-parse', '--show-toplevel').decode().strip() == str(task.W)
    assert git('rev-parse', 'HEAD').decode().strip() == task.REAL_HEAD
    S.mkdir()
    runtime = env() | {'GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':os.devnull}
    with (D / 'export.stderr').open('xb') as error:
        producer = subprocess.Popen(['/usr/bin/git','--no-lazy-fetch','--git-dir='+str(task.GD),'--work-tree='+str(task.W),'archive',OLD_PR],env=runtime,stdout=subprocess.PIPE,stderr=error)
        consumer = subprocess.run(['/usr/bin/tar','-x','-C',str(S)],stdin=producer.stdout,env=runtime)
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    assert S.resolve().is_relative_to(D.resolve()) and not (S / '.git').exists()
    subprocess.run(['/usr/bin/git','--git-dir='+str(S / '.git'),'--work-tree='+str(S),'init','--quiet','--template=','--initial-branch=local-catalog-index'],env=runtime,check=True)
    common=Path(git('rev-parse','--git-common-dir').decode().strip())
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree',OLD_PR,source=True);git('update-ref','HEAD',OLD_PR,source=True)
    invariant()
    paths=['evas/capabilities/asset_catalog.py','evas/capabilities/test_asset_catalog.py']
    for path in paths:
        assert git('show',OLD_PR+':'+path)==git('show',accepted['fixed_base']+':'+path)
    applied=subprocess.run(['/usr/bin/patch','-p1','-F','0','-i',str(patch)],cwd=S,env=runtime,capture_output=True)
    (D / 'patch.stdout').write_bytes(applied.stdout);(D / 'patch.stderr').write_bytes(applied.stderr)
    assert applied.returncode==0
    for path in paths:
        assert (S/path).read_bytes()==(PREP/'acceptance-run/tree'/path).read_bytes()
    assert set(git('diff','--name-only',source=True).decode().splitlines())==set(paths)
    assert not git('ls-files','--others','--exclude-standard',source=True).strip()
    cap=task.make_commit(OLD_PR,paths,'Bound catalog history validation to ordered versions of the same identity','capture')
    git('read-tree',cap['commit'],source=True);git('update-ref','HEAD',cap['commit'],OLD_PR,source=True)
    cap.update(trusted_base=BASE,scientific_execution=False,review='new independent Astra increment required')
    write(D/'capture.json',cap)
    (D/'source.patch').write_bytes(git('diff','--binary',OLD_PR,cap['commit']))
    (D/'source.commit').write_bytes(git('cat-file','commit',cap['commit']))
    observed=load(OLD/'assets.json');prior=task.entries(observed['source_commit']);after=task.entries(cap['commit'])
    prior_rows={r['path']:r for r in observed['assets']}; assert set(prior_rows)==set(prior)
    rows=[];changed=[]
    for path,(mode,oid) in sorted(after.items()):
        if prior.get(path)==(mode,oid):
            old=prior_rows[path];assert old['git_blob_oid']==oid and old['git_mode']==mode
            value=old['sha256'];actual_mode=old['actual_mode']
        else:
            raw=(S/path).read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==oid
            value=sha(raw);actual_mode=(S/path).stat().st_mode & 0o777;changed.append(path)
        rows.append({'path':path,'sha256':value,'git_mode':mode,'actual_mode':actual_mode,'git_blob_oid':oid})
    write(D/'assets.json',dict(schema_version=1,producer='task-incremental-verified-asset-capture',source_commit=cap['commit'],source_tree=cap['tree'],source_object_format='sha1',source_kind='immutable-export',source_profile='git-tree-regular-blobs-v1',source_availability='local-only-before-publication',content_binding='verified-git-blob-oids',scope=observed['scope'],assets=rows,reuse_proof={'parent_capture':observed['source_commit'],'record':str(OLD/'assets.json'),'unchanged':len(rows)-len(changed),'changed':changed}))
    sys.path.insert(0,str(S/'scripts'))
    rspec=importlib.util.spec_from_file_location('index_scientific_manifest',S/'scripts/run_regression.py')
    runner=importlib.util.module_from_spec(rspec);rspec.loader.exec_module(runner)
    raw_path=task.I/'ci-40384473617/artifacts/python-regression-timings/python-regression.json'
    raw=load(raw_path)
    criteria=runner.file_manifest(S,('evas/tests','evas/validation','evas/examples','experiments'))
    dut=runner.file_manifest(S,('evas/src','evas/rust_core'))
    assert criteria==raw['source_identity']['criteria_files'] and dut==raw['source_identity']['dut_files']
    immutable=['.github/workflows/numerical-assurance.yml','evas/validation/baselines/regression-v1.json','evas/validation/baselines/regression-v1.review.json','scripts/context-registration-bundle.json','scripts/run_trusted_regression_gate.py','scripts/regression_gate.py','scripts/regression_context_registration.py','scripts/run_regression.py','scripts/ci_evidence.py','scripts/regression_reason_identity.py','scripts/regression_observation_policy.json']
    for path in immutable: assert (S/path).read_bytes()==git('show',OLD_PR+':'+path)
    write(D/'source-preparation.json',{'fixed_parent':OLD_PR,'trusted_base':BASE,'source_snapshot':cap['commit'],'implementation_patch':str(patch),'implementation_patch_sha256':sha(patch.read_bytes()),'source_paths':paths,'deferred_generated_paths':load(OLD/'source-preparation.json')['deferred_generated_paths'],'criteria_file_count':len(criteria),'criteria_id':runner.json_digest(criteria),'dut_file_count':len(dut),'dut_id':runner.json_digest(dut),'criteria_and_DUT_exact_E1_source':True,'E1_raw':str(raw_path),'E1_raw_sha256':sha(raw_path.read_bytes()),'unchanged_trust_and_execution_paths':immutable,'prior_CI_failure':'30-minute maintenance timeout','scientific_execution':False,'scientific_qualification':False})
    invariant()
    print(json.dumps({'capture':cap['commit'],'tree':cap['tree'],'source_paths':len(paths),'assets':len(rows),'criteria_files':len(criteria),'DUT_files':len(dut)}),flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    candidates = []
    for config_path in (OLD / 'config.json', N / 'c0-candidate/config.json', task.I / 'config.json'):
        config = load(config_path)
        for item in config['discoveries']:
            path = Path(item['entry_file'])
            value = load(path)
            candidates.append((path, value, config['discovery_source_locators'][value['entry']['entry_id']]))
    for name in list(os.environ):
        if name.startswith('GIT_'): del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = load(D / 'capture.json')['commit']
    spec = importlib.util.spec_from_file_location('c1_inventory', S / 'scripts/capabilities/collect_ci_inventory.py')
    inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inventory)
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(entries) == 30
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    chosen, new_count = [], 0
    for i, entry in enumerate(entries):
        matching = []
        for path, value, locator in candidates:
            r = value['receipt']
            if value['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']: continue
            collector = r['collector']
            if assets.get(collector['path']) != collector['sha256']: continue
            if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']): continue
            matching.append((path, value, locator))
        if matching:
            path, value, locator = matching[0]
            assert git('show', locator['revision'] + ':' + locator['path']) == path.read_bytes()
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True,
                   'source_locator': locator, 'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances']}
        else:
            r = inventory.child(S, entry, 90)
            assert r['complete'] and not r['errors'] and not r['unresolved_instances']
            path = D / 'new-discovery' / ('entry-%03d.json' % i)
            write(path, {'entry': entry, 'receipt': r})
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': False,
                   'sha256': sha(path.read_bytes()), 'instances': r['discovered_instances']}
            new_count += 1
        row.update(start=entry['start'], pattern=entry['pattern'])
        chosen.append(row)
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen),
          'reused': len(chosen) - new_count, 'new_collections': new_count,
          'reuse_basis': 'Exact workflow entry, collector, owner module bytes and archived receipt blob; original execution identity retained.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'discovery-selection.json', 'source-preparation.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists(): shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_candidate.py')
    (dest / 'README.md').write_text('# Detector context activation construction\n\n'
        'This bounded maintenance increment removes repeated full catalog scans after the original C1 job exceeded its existing30-minute limit. The previously accepted C1 detector, workflow, baseline and scientific inputs remain unchanged. Fresh independent review is pending. '
        'Matching collection receipts retain their original identity; only changed TestLoader entries are recollected. No test bodies or simulator run here. '
        'Final catalog generation, precheck, candidate CI and merged-tree verification remain separate. Scientific qualification is false.\n')
    idx = D / 'archive.index'
    git('read-tree', ARCHIVE_PARENT, index=idx)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file(): continue
        path = p.relative_to(D / 'archive-files').as_posix()
        raw = p.read_bytes()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    head = git('commit-tree', tree, '-p', ARCHIVE_PARENT, '-m', 'Archive detector context activation construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': ARCHIVE_PARENT, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(task.I / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    script_entries = []
    for row in load(D / 'discovery-selection.json')['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        locator = row.get('source_locator') or {'kind': 'git-object', 'repository': 'vaevas', 'revision': head,
                                               'path': PREFIX + '/new-discovery/' + path.name}
        config['discovery_source_locators'][row['entry_id']] = locator
        if row['start'] == 'scripts/tests' and row['pattern'] == 'test*.py': script_entries.append(row['entry_id'])
    assert len(script_entries) == 1
    for bridge in config['bridge_evidence']: bridge['consumer_entry_ids'] = script_entries
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'archive': head, 'files': len(files)}), flush=True)


def generate():
    invariant()
    with (D / 'generation.stdout').open('xb') as out, (D / 'generation.stderr').open('xb') as err:
        run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                              '--output', str(D / 'catalog')], cwd=S, env=env(), stdout=out, stderr=err)
    assert run.returncode == 0, 'Read generation.stderr'
    report = load(D / 'catalog/generation-report.json')
    previous, current = task.objects(S / 'evas/capabilities/data'), task.objects(D / 'catalog/tree/evas/capabilities/data')
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    paths = []
    for p in (D / 'catalog/tree/evas/capabilities/data').glob('*.json'):
        target = S / 'evas/capabilities/data' / p.name
        if p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    write(D / 'generation-acceptance.json', {'paths': paths, 'old_versions_retained': len(previous),
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous)}), flush=True)


def precheck():
    invariant()
    assert not (D / 'precheck-acceptance.json').exists()
    results = []
    e = env() | {'CARGO_TARGET_DIR': str(B / 'pr4/bootstrap-integration-20261026/precheck-rust-target')}
    def run(name, argv):
        start = datetime.now(timezone.utc).isoformat()
        with (D / name).open('x') as out:
            out.write('COMMAND ' + repr(argv) + '\n'); out.flush()
            r = subprocess.run(argv, cwd=S, env=e, stdout=out, stderr=subprocess.STDOUT)
            out.write('\nreturncode=' + str(r.returncode) + '\n')
        results.append({'command': argv, 'receipt': str(D / name), 'returncode': r.returncode,
                        'started_at_utc': start, 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
        print(name, r.returncode, flush=True)
        assert r.returncode == 0, name
    run('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'])
    run('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'])
    paths = git('diff', '--name-only', BASE, source=True).decode().splitlines()
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths),
          'focused': False, 'scope': 'Complete C1 quick maintenance gate; full scientific regression is CI only.'})
    run('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')])
    run('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'])
    run('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'])
    run('affected-catalog-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_catalog_history_selection.py', '-v'])
    run('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE])
    write(D / 'precheck-acceptance.json', {'base': BASE, 'source_capture': load(D / 'capture.json')['commit'],
          'paths': paths, 'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in paths},
          'existing_scientific_calibration_and_fixture_controls_reused': str(B / 'night-coordination/pr4-context-increment-astra-r2-20261027/review-report.json'),
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def workflow():
    invariant()
    old=load(OLD/'activation-workflow-acceptance.json')
    assert old['base']==BASE and old['merge_allowed'] and not old['bundle_requested']
    prep=load(D/'source-preparation.json')
    assert prep['criteria_and_DUT_exact_E1_source']
    for path in prep['unchanged_trust_and_execution_paths']:
        assert (S/path).read_bytes()==git('show',OLD_PR+':'+path)
    write(D/'activation-workflow-acceptance.json',{'base':BASE,'source_capture':load(D/'capture.json')['commit'],'merge_allowed':True,'bundle_requested':False,'reused_original_record':str(OLD/'activation-workflow-acceptance.json'),'identity_proof':str(D/'source-preparation.json'),'new_shell_execution':False,'scientific_execution':False,'scientific_qualification':False,'new_candidate_CI_still_required':True})
    print('unchanged accepted shell evidence reused',flush=True)


def freeze():
    invariant()
    cap, pre = load(D / 'capture.json'), load(D / 'precheck-acceptance.json')
    assert load(D / 'activation-workflow-acceptance.json')['merge_allowed']
    assert all(row['returncode'] == 0 for row in pre['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in pre['files'].items())
    generated = git('diff', '--name-only', cap['commit'], source=True).decode().splitlines()
    final = task.make_commit(cap['commit'], generated, 'Refresh bound detector catalog and activation views', 'final')
    git('merge-base', '--is-ancestor', OLD_PR, final['commit'])
    git('merge-base', '--is-ancestor', BASE, final['commit'])
    final.update(base=BASE, source_capture=cap['commit'], complete_paths=pre['paths'], precheck=str(D / 'precheck-acceptance.json'),
                 review_reuse='Earlier C1 source/E1 and30-minute workflow remain accepted. New two-file ordered-index code requires fresh independent Astra increment; deterministic metadata checked by primary.',
                 CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', BASE, final['commit']))
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'paths': len(pre['paths']), 'CI': 'pending'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['capture', 'discover', 'archive', 'generate', 'precheck', 'workflow', 'freeze'])
    globals()[parser.parse_args().stage]()

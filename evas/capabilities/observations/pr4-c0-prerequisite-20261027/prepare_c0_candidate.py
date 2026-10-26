"""Construct the C0 prerequisite using existing catalog and fast-check tools.

Only task scratch, Git objects and explicitly selected archive refs are writable.
The real worktree/index/branch and twenty scientific candidates are preserved.
Each stage writes a new receipt and refuses to replace one.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

R = Path(__file__).resolve().parent
B = R.parents[1]
I = B / 'pr4/detector-integration-20261027'
S = R / 'source-c0'
OUT = R / 'c0-candidate'
W = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
GD = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night')
BASE = '842bde7101164330fa03e7aee58b45d1789cbed1'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
ARCHIVE_PARENT = 'ae1cd723c5b24bd17af866805d7e6ac742cd8b86'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
PREFIX = 'evas/capabilities/observations/pr4-c0-prerequisite-20261027'
PRIOR = B / 'pr4/bootstrap-integration-20261026/local-only-fix'
PY = B / 'pr4/trusted-context/SP-01/lint-venv/bin/python'


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def git(*args, index=None, data=None, source=False):
    env = clean_env() | {'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0'}
    if source:
        env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    return subprocess.check_output(['/usr/bin/git', '--no-lazy-fetch',
            '--git-dir=' + str(S / '.git' if source else GD),
            '--work-tree=' + str(S if source else W), *args], env=env, input=data)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    assert not path.exists(), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def preserved():
    assert git('rev-parse', '--show-toplevel').decode().strip() == str(W)
    assert git('rev-parse', 'HEAD').decode().strip() == REAL_HEAD
    assert not git('diff', '--cached', '--name-only').strip()
    assert git('config', 'user.name').decode().strip() == 'BucketSran'
    assert git('config', 'user.email').decode().strip() == '138781625+BucketSran@users.noreply.github.com'
    assert Path(git('rev-parse', '--absolute-git-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--git-common-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--show-toplevel', source=True).decode().strip()).resolve() == S
    plan = json.loads((B / 'main-plan.json').read_text())
    rows = [row for row in plan['handoff']['files'] if row['path'].startswith('evas/tests/')]
    assert len(rows) == 20
    assert all(sha((W / row['path']).read_bytes()) == row['sha256'] for row in rows)
    config = W.parents[1] / 'current/.git/config'
    assert sha(config.read_bytes()) == '2365548f0cb7f5b21311860afc37dc5a8f41d775b667f50ec8a678eb22a3d7aa'


def entries(commit):
    rows = {}
    for item in git('ls-tree', '-r', '-z', commit).split(b'\0'):
        if item:
            metadata, path = item.split(b'\t', 1)
            mode, kind, oid = metadata.decode().split()
            assert kind == 'blob'
            rows[path.decode()] = (mode, oid)
    return rows


def make_commit(parent, paths, message, receipt_prefix):
    previous = entries(parent)
    index = OUT / (receipt_prefix + '.index')
    assert not index.exists()
    git('read-tree', parent, index=index)
    files = {}
    for path in paths:
        target = S / path
        assert target.is_file() and not target.is_symlink()
        raw = target.read_bytes()
        mode = previous.get(path, ('100644', None))[0]
        assert target.stat().st_mode & 0o777 == (0o755 if mode == '100755' else 0o644)
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
        files[path] = sha(raw)
    tree = git('write-tree', index=index).decode().strip()
    commit = git('commit-tree', tree, '-p', parent, '-m', message).decode().strip()
    index.unlink()
    changed = git('diff', '--name-only', parent, commit).decode().splitlines()
    assert set(changed) == set(paths)
    return dict(base=parent, commit=commit, tree=tree, paths=changed, files=files,
                old20_preserved=True, scientific_qualification=False,
                time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())


def capture():
    preserved()
    assert not OUT.exists()
    OUT.mkdir()
    assert (R / 'codec-integration.json').is_file(), 'Codec must be independently checked before capture'
    proposal = json.loads((R / 'governance-draft/receipt.json').read_text())
    assert not proposal['effective_authority']
    for src, dest in [('review.json', 'evas/validation/baselines/regression-v1.review.json'),
                      ('bundle-pointer.json', 'scripts/context-registration-bundle.json')]:
        raw = (R / 'governance-draft' / src).read_bytes()
        assert sha(raw) == proposal['files'][src]
        (S / dest).write_bytes(raw)
    fixture_paths = {row['path'] for row in json.loads((I / 'fixture-integration-r2.json').read_text())['paths']}
    allowed = fixture_paths | {'.github/workflows/numerical-assurance.yml',
           'scripts/materialize_registration_bundle.py', 'scripts/tests/test_registration_bundle.py',
           'scripts/context-registration-bundle.json', 'evas/validation/baselines/regression-v1.review.json'}
    paths = set(git('diff', '--name-only', source=True).decode().splitlines())
    paths |= set(git('ls-files', '--others', '--exclude-standard', source=True).decode().splitlines())
    assert paths == allowed, sorted(paths ^ allowed)
    receipt = make_commit(BASE, sorted(paths), 'Capture C0 registration prerequisites and exact authority proposal', 'capture')
    git('read-tree', receipt['commit'], source=True)
    git('update-ref', 'HEAD', receipt['commit'], BASE, source=True)
    write(OUT / 'capture.json', receipt)
    (OUT / 'source.patch').write_bytes(git('diff', '--binary', BASE, receipt['commit']))
    (OUT / 'source.commit').write_bytes(git('cat-file', 'commit', receipt['commit']))
    old = json.loads((PRIOR / 'ci-40358433992/artifacts/catalog-inventory/assets-before.json').read_text())
    old_after = json.loads((PRIOR / 'ci-40358433992/artifacts/catalog-inventory/assets-after.json').read_text())
    assert old['assets'] == old_after['assets']
    prior = {row['path']: row for row in old['assets']}
    before, after = entries(BASE), entries(receipt['commit'])
    assert set(prior) == set(before)
    for path, (mode, oid) in before.items():
        assert prior[path]['git_mode'] == mode
        assert prior[path]['observed_blob_oid'] == prior[path]['index_blob_oid'] == oid
    rows = []
    for path, (mode, oid) in sorted(after.items()):
        if before.get(path) == (mode, oid):
            item = prior[path]
            rows.append(dict(path=path, sha256=item['sha256'], git_mode=mode,
                             actual_mode=item['actual_mode'], git_blob_oid=oid))
        else:
            target = S / path
            raw = target.read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid
            rows.append(dict(path=path, sha256=sha(raw), git_mode=mode,
                             actual_mode=target.stat().st_mode & 0o777, git_blob_oid=oid))
    write(OUT / 'assets.json', dict(schema_version=1, producer='task-incremental-verified-asset-capture',
          source_commit=receipt['commit'], source_tree=receipt['tree'], source_object_format='sha1',
          source_kind='immutable-export', source_profile='git-tree-regular-blobs-v1',
          source_availability='local-only', content_binding='verified-git-blob-oids', scope=old['scope'], assets=rows,
          reuse_proof=dict(parent_commit=BASE, actual_ci=40358433992, unchanged=len(rows)-len(paths), changed=sorted(paths),
                           all_prior_actual_blob_oids_verified=True)))
    preserved()
    print(json.dumps({k: receipt[k] for k in ('commit', 'tree', 'paths')}), flush=True)


def discover():
    preserved()
    assert sys.version_info[:2] == (3, 12)
    dest = OUT / 'discovery'
    assert not dest.exists()
    dest.mkdir()
    captured = json.loads((OUT / 'capture.json').read_text())
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = captured['commit']
    spec = importlib.util.spec_from_file_location('c0_inventory', S / 'scripts/capabilities/collect_ci_inventory.py')
    inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inventory)
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    selected = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    results = []
    for i, entry in enumerate(selected):
        receipt = inventory.child(S, entry, 90)
        path = dest / ('entry-%03d.json' % i)
        write(path, dict(entry=entry, receipt=receipt))
        results.append(dict(path=str(path), entry_id=entry['entry_id'], start=entry['start'],
                            instances=receipt['discovered_instances'], complete=receipt['complete'],
                            errors=receipt['errors']))
        assert receipt['complete'] and not receipt['errors'] and not receipt['unresolved_instances'], results[-1]
    write(OUT / 'discovery-summary.json', dict(source_capture=captured['commit'], actual_python=sys.version,
          entries=results, test_bodies_executed=False, scientific_qualification=False))
    preserved()
    print(json.dumps(dict(entries=len(results), methods=sum(x['instances'] for x in results))), flush=True)


def archive():
    preserved()
    assert not (OUT / 'archive.json').exists()
    dest = OUT / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'discovery-summary.json'):
        shutil.copyfile(OUT / name, dest / name)
    shutil.copytree(OUT / 'discovery', dest / 'discovery')
    shutil.copyfile(__file__, dest / 'prepare_c0_candidate.py')
    (dest / 'README.md').write_text('# C0 registration prerequisite construction\n\n'
        'This source capture retains the C0 scientific criteria, DUT and language profile. '
        'It prepares reviewed Git fixture isolation, raw artifact retention, optional lossless '
        'kernel materialization and a proposed exact context authority. The proposal remains '
        'unadopted until fixed-candidate independent review and CI are accepted.\n\n'
        'Discovery invokes the existing TestLoader collector without running test bodies. '
        'The final generated catalog, PR candidate and CI identities are separate. '
        'No scientific qualification is granted by these construction receipts.\n')
    index = OUT / 'archive.index'
    assert not index.exists()
    git('read-tree', ARCHIVE_PARENT, index=index)
    files = []
    for p in sorted((OUT / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        path = p.relative_to(OUT / 'archive-files').as_posix()
        raw = p.read_bytes()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=index)
        files.append(dict(path=path, sha256=sha(raw), bytes=len(raw)))
    tree = git('write-tree', index=index).decode().strip()
    commit = git('commit-tree', tree, '-p', ARCHIVE_PARENT, '-m',
                 'Archive C0 registration prerequisite construction').decode().strip()
    index.unlink()
    write(OUT / 'archive.json', dict(parent=ARCHIVE_PARENT, commit=commit, tree=tree, prefix=PREFIX,
          files=files, public=False, pushed=False, scientific_qualification=False))
    preserved()
    print(json.dumps(dict(commit=commit, files=len(files))), flush=True)


def generate():
    preserved()
    assert not (OUT / 'config.json').exists()
    arc = json.loads((OUT / 'archive.json').read_text())
    config = json.loads((I / 'config.json').read_text())
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(OUT / 'assets.json'), source_repositories={'vaevas': str(S)})
    config['discoveries'] = []
    config['discovery_source_locators'] = {}
    script_entries = []
    for p in sorted((OUT / 'discovery').glob('entry-*.json')):
        item = json.loads(p.read_text())
        entry = item['entry']
        config['discoveries'].append(dict(entry_file=str(p)))
        config['discovery_source_locators'][entry['entry_id']] = dict(kind='git-object', repository='vaevas',
                          revision=arc['commit'], path=PREFIX + '/discovery/' + p.name)
        if entry['start'] == 'scripts/tests' and entry['pattern'] == 'test*.py':
            script_entries.append(entry['entry_id'])
    assert len(script_entries) == 1
    for bridge in config['bridge_evidence']:
        bridge['consumer_entry_ids'] = script_entries
    write(OUT / 'config.json', config)
    with (OUT / 'generation.stdout').open('xb') as out, (OUT / 'generation.stderr').open('xb') as err:
        proc = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py',
                    '--config', str(OUT / 'config.json'), '--output', str(OUT / 'catalog')],
                    cwd=S, env=clean_env(), stdout=out, stderr=err)
    assert proc.returncode == 0, 'Read generation.stderr'
    report = json.loads((OUT / 'catalog/generation-report.json').read_text())
    assert report['qualification_added'] is False
    previous = objects(S / 'evas/capabilities/data')
    generated = OUT / 'catalog/tree/evas/capabilities/data'
    new = objects(generated)
    assert all(new.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous)
    changed = []
    for p in generated.glob('*.json'):
        target = S / 'evas/capabilities/data' / p.name
        if target.read_bytes() != p.read_bytes():
            target.write_bytes(p.read_bytes())
            changed.append(target.relative_to(S).as_posix())
    write(OUT / 'generation-acceptance.json', dict(paths=changed, previous_object_versions_retained=len(previous),
          objects=report['objects'], namespace_counts=report['namespace_counts'], scientific_qualification=False))
    preserved()
    print(json.dumps(dict(generated_paths=len(changed), previous_versions=len(previous))), flush=True)


def objects(path):
    header = json.loads((path / 'registry.json').read_text())
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads((path / part).read_text())['objects']
    return {(item['id'], item['version']): item for item in result}


def precheck():
    preserved()
    assert not (OUT / 'precheck-acceptance.json').exists()
    results = []
    env = clean_env() | {'PYTHONDONTWRITEBYTECODE': '1',
        'CARGO_TARGET_DIR': str(B / 'pr4/bootstrap-integration-20261026/precheck-rust-target')}

    def run(name, argv):
        target = OUT / name
        with target.open('x') as stream:
            stream.write('COMMAND ' + repr(argv) + '\n')
            stream.flush()
            proc = subprocess.run(argv, cwd=S, env=env, stdout=stream, stderr=subprocess.STDOUT)
            stream.write('\nreturncode=' + str(proc.returncode) + '\n')
        results.append(dict(command=argv, receipt=str(target), returncode=proc.returncode))
        print(name, proc.returncode, flush=True)
        assert proc.returncode == 0, name

    run('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'])
    captured = json.loads((OUT / 'capture.json').read_text())
    generated = json.loads((OUT / 'generation-acceptance.json').read_text())
    paths = sorted(set(captured['paths'] + generated['paths'] + ['evas/docs/development/TRACEABILITY.md']))
    plan = dict(mode='delivery', maintenance=True, regression=True, focused=False, paths=paths,
                scope='Complete C0 prerequisite fast maintenance gate; scientific regression remains CI only')
    write(OUT / 'maintenance-plan.json', plan)
    run('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(OUT / 'maintenance-plan.json')])
    run('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'])
    run('affected-catalog-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_catalog_history_selection.py', '-v'])
    run('affected-inventory-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_ci_inventory.py', '-v'])
    run('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check'])
    write(OUT / 'precheck-acceptance.json', dict(source_capture=captured['commit'], paths=paths, checks=results,
          files={p: sha((S / p).read_bytes()) for p in paths}, scientific_qualification=False,
          actual_python=sys.version, real_git_authority_environment_inherited=False))
    preserved()


def freeze():
    preserved()
    accepted = json.loads((OUT / 'precheck-acceptance.json').read_text())
    assert all(c['returncode'] == 0 for c in accepted['checks'])
    assert all(sha((S / p).read_bytes()) == h for p, h in accepted['files'].items())
    receipt = make_commit(BASE, accepted['paths'], 'Preauthorize exact detector context on unchanged C0', 'final')
    receipt.update(precheck=str(OUT / 'precheck-acceptance.json'), independent_review='pending', CI='pending', published=False)
    write(OUT / 'final-candidate.json', receipt)
    (OUT / 'final-candidate.patch').write_bytes(git('diff', '--binary', BASE, receipt['commit']))
    preserved()
    print(json.dumps({k: receipt[k] for k in ('commit', 'tree', 'paths')}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['capture', 'discover', 'archive', 'generate', 'precheck', 'freeze'])
    args = parser.parse_args()
    globals()[args.step]()

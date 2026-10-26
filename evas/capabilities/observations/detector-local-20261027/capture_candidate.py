"""Capture an explicit export delta without staging retained science candidates."""
from pathlib import Path
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

R = Path(__file__).resolve().parent
B = R.parents[1]
S = R / 'source'
W = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
GD = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night')
BASE = '842bde7101164330fa03e7aee58b45d1789cbed1'
PRIOR = B / 'pr4/bootstrap-integration-20261026/local-only-fix'
CI = PRIOR / 'ci-40358433992/artifacts/catalog-inventory'
CAPTURE_JSON = 'capture-r2.json'
SOURCE_PATCH = 'source-r2.patch'
SOURCE_COMMIT = 'source-r2.commit'
ASSETS_JSON = 'assets-r2.json'


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def git(*args, index=None, data=None):
    env = clean_env()
    if index is not None:
        # Only this Git command receives the alternate index, never a test tree.
        env['GIT_INDEX_FILE'] = str(index)
    return subprocess.check_output(['/usr/bin/git', '--git-dir=' + str(GD),
                                    '--work-tree=' + str(W), *args], env=env, input=data)


def export_git(*args):
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    return subprocess.check_output(['/usr/bin/git', '--git-dir=' + str(S / '.git'),
                                    '--work-tree=' + str(S), *args], env=env)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(name, value):
    (R / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def preserved():
    plan = json.loads((B / 'main-plan.json').read_text())
    old = [x for x in plan['handoff']['files'] if x['path'].startswith('evas/tests/')]
    assert len(old) == 20
    assert all(sha((W / x['path']).read_bytes()) == x['sha256'] for x in old)
    assert git('rev-parse', '--show-toplevel').decode().strip() == str(W)
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert not git('diff', '--cached', '--name-only').strip()


def entries(revision):
    result = {}
    for item in git('ls-tree', '-r', '-z', revision).split(b'\0'):
        if item:
            metadata, path = item.split(b'\t')
            mode, kind, oid = metadata.decode().split()
            assert kind == 'blob'
            result[path.decode()] = (mode, oid)
    return result


def init_export():
    preserved()
    assert not (S / '.git').exists()
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    subprocess.run(['/usr/bin/git', 'init', '--quiet', '--template=',
                    '--initial-branch=pr4-export', str(S)], env=env, check=True)
    assert (S / '.git').resolve().is_relative_to(R.resolve())
    common = Path(git('rev-parse', '--git-common-dir').decode().strip())
    if not common.is_absolute():
        common = (W / common).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    export_git('read-tree', BASE)
    export_git('update-ref', 'HEAD', BASE)
    assert Path(export_git('rev-parse', '--show-toplevel').decode().strip()).resolve() == S
    assert Path(export_git('rev-parse', '--absolute-git-dir').decode().strip()).resolve() == S / '.git'
    write('export-git-isolation.json', dict(root=str(S), git_dir=str(S / '.git'),
          read_only_object_alternate=str(common / 'objects'), base=BASE,
          real_git_environment_passed_to_tests=False, real_index_unchanged=True))
    preserved()
    print('Isolated export metadata created; no real refs/index/config changed.', flush=True)


def capture():
    preserved()
    assert not (R / CAPTURE_JSON).exists()
    selected = json.loads((R / 'candidate-inputs-r5.json').read_text())['paths']
    selected += json.loads((R / 'fixture-integration-r2.json').read_text())['paths']
    by_path = {row['path']: row for row in selected}
    assert len(by_path) == len(selected)
    before = entries(BASE)
    index = R / 'candidate.index'
    assert not index.exists()
    git('read-tree', BASE, index=index)
    for path, row in sorted(by_path.items()):
        target = S / path
        assert target.is_file() and not target.is_symlink()
        raw = target.read_bytes()
        assert sha(raw) == row['sha256'], path
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        mode = before.get(path, ('100644', None))[0]
        assert (target.stat().st_mode & 0o777) == (0o755 if mode == '100755' else 0o644), path
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    commit = git('commit-tree', tree, '-p', BASE, '-m',
                 'Capture PR4 detector corrections and fixture isolation').decode().strip()
    index.unlink()
    assert set(git('diff', '--name-only', BASE, commit).decode().splitlines()) == set(by_path)
    export_git('read-tree', commit)
    prior_capture = json.loads((R / 'capture.json').read_text())['commit']
    export_git('update-ref', 'HEAD', commit, prior_capture)
    write(CAPTURE_JSON, dict(base=BASE, commit=commit, tree=tree, source_root=str(S),
          previous_local_capture=prior_capture,
          paths=sorted(by_path), old20_preserved=True, qualification=False,
          time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()))
    (R / SOURCE_PATCH).write_bytes(git('diff', '--binary', BASE, commit))
    (R / SOURCE_COMMIT).write_bytes(git('cat-file', 'commit', commit))
    observed = json.loads((CI / 'assets-before.json').read_text())
    after = json.loads((CI / 'assets-after.json').read_text())
    assert observed['assets'] == after['assets']
    prior = {row['path']: row for row in observed['assets']}
    current = entries(commit)
    assert set(prior) == set(before)
    for path, (mode, oid) in before.items():
        assert prior[path]['git_mode'] == mode
        assert prior[path]['observed_blob_oid'] == prior[path]['index_blob_oid'] == oid
    rows, changed = [], []
    for path, (mode, oid) in sorted(current.items()):
        if before.get(path) == (mode, oid):
            value = prior[path]
            rows.append(dict(path=path, sha256=value['sha256'], git_mode=mode,
                             actual_mode=value['actual_mode'], git_blob_oid=oid))
        else:
            target = S / path
            raw = target.read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid
            rows.append(dict(path=path, sha256=sha(raw), git_mode=mode,
                             actual_mode=target.stat().st_mode & 0o777, git_blob_oid=oid))
            changed.append(path)
    assert set(changed) == set(by_path)
    write(ASSETS_JSON, dict(schema_version=1, producer='task-incremental-verified-asset-capture',
          source_commit=commit, source_tree=tree, source_object_format='sha1',
          source_kind='immutable-export', source_profile='git-tree-regular-blobs-v1',
          source_availability='local-only', content_binding='verified-git-blob-oids',
          scope=observed['scope'], assets=rows,
          relation_to_ci_input_key='independent-local-construction-not-CI',
          reuse_proof=dict(parent_commit=BASE, actual_ci=40358433992,
                          unchanged=len(rows)-len(changed), changed=changed,
                          all_prior_actual_blob_oids_verified=True)))
    preserved()
    print(json.dumps(dict(commit=commit, tree=tree, changed=len(changed), assets=len(rows))), flush=True)


def discover():
    assert sys.version_info[:2] == (3, 12)
    assert not (R / 'discovery-complete').exists()
    captured = json.loads((R / CAPTURE_JSON).read_text())
    for key in list(os.environ):
        if key.startswith('GIT_'):
            del os.environ[key]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = captured['commit']
    spec = importlib.util.spec_from_file_location('pr4_inventory', S / 'scripts/capabilities/collect_ci_inventory.py')
    inventory = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(inventory)
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries_list = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    output = R / 'discovery-complete'
    output.mkdir()
    results = []
    for i, entry in enumerate(entries_list):
        previous_path = R / f'discovery/entry-{i:03}.json'
        previous = json.loads(previous_path.read_text()) if previous_path.is_file() else None
        reusable = (previous is not None and previous['entry'] == entry
                    and previous['receipt']['complete'] and not previous['receipt']['errors']
                    and not previous['receipt']['unresolved_instances'])
        receipt = previous['receipt'] if reusable else inventory.child(S, entry, 90)
        name = f'discovery-complete/entry-{i:03}.json'
        write(name, dict(entry=entry, receipt=receipt))
        row = dict(path=name, entry_id=entry['entry_id'], start=entry['start'],
                   pattern=entry['pattern'], complete=receipt['complete'],
                   instances=receipt['discovered_instances'], errors=receipt['errors'],
                   reused_from=str(previous_path) if reusable else None)
        results.append(row)
        write('discovery-progress.json', results)
        print(json.dumps({k: v for k, v in row.items() if k != 'errors'}), flush=True)
        assert receipt['complete'] and not receipt['errors'] and not receipt['unresolved_instances'], row
    write('discovery-summary.json', dict(source_capture=captured['commit'],
          actual_python=sys.version, entries=results, test_bodies_executed=False,
          scientific_qualification=False))
    preserved()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['init-export', 'capture', 'discover'])
    args = parser.parse_args()
    {'init-export': init_export, 'capture': capture, 'discover': discover}[args.step]()

"""Capture only the reviewed SP-01 delta and refresh its actual discovery."""
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile

W = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
R = Path(__file__).resolve().parent
B = R.parents[2]
BASE = '49bd7f32614b4e292672addef4b79a5dfdcc4bb8'
PATHS = ['scripts/README.md', 'scripts/regression_context_registration.py',
         'scripts/tests/regression_registration_fixtures.py',
         'scripts/tests/test_trusted_regression_gate.py']

def git(*args, env=None):
    return subprocess.check_output(['git', '-C', str(W), *args], env=env)

def write(name, value):
    (R / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

assert not (R / 'capture.json').exists(), 'Capture already exists; reuse it rather than overwrite'
assert git('rev-parse', 'HEAD').decode().strip() == BASE
plan = json.loads((B / 'main-plan.json').read_text())
old = [x for x in plan['handoff']['files'] if x['path'].startswith('evas/tests/')]
assert len(old) == 20
assert all(hashlib.sha256((W / x['path']).read_bytes()).hexdigest() == x['sha256'] for x in old)
index = R / 'source.index'
env = dict(os.environ, GIT_INDEX_FILE=str(index))
git('read-tree', BASE, env=env)
git('add', '--', *PATHS, env=env)
tree = git('write-tree', env=env).decode().strip()
commit = git('commit-tree', tree, '-p', BASE, '-m', 'capture SP-01 original shard identity repair').decode().strip()
index.unlink()
assert set(git('diff', '--name-only', BASE, commit).decode().splitlines()) == set(PATHS)
source = R / 'source'
source.mkdir()
roots = [line.split('\t')[1] for line in git('ls-tree', commit).decode().splitlines()
         if line.split()[1] == 'blob']
roots += ['.agents', '.github', 'docs', 'evas', 'experiments', 'scripts',
          'benchmark/material/draftbench/templates/INSTRUCTION.md',
          'benchmark/material/historyref/tasks/va07-triangle-repair/SOURCE.md']
with tarfile.open(fileobj=io.BytesIO(git('archive', commit, '--', *roots))) as archive:
    archive.extractall(source, filter='data')
write('capture.json', dict(base=BASE, commit=commit, tree=tree, source_root=str(source),
                           paths=PATHS, old20_preserved=True, qualification=False))
(R / 'source.patch').write_bytes(git('diff', '--binary', BASE, commit))
(R / 'source.commit').write_bytes(git('cat-file', 'commit', commit))

# Reuse the actual previous CI inventory only after every old tree OID matches.
ci = B / 'pr4/trusted-context/recovered-20261026/vaevas-context-ci-40311281686/artifacts/catalog-inventory'
before = json.loads((ci / 'assets-before.json').read_text())
after = json.loads((ci / 'assets-after.json').read_text())
assert before['assets'] == after['assets']
prior = {x['path']: x for x in before['assets']}
def entries(revision):
    result = {}
    for row in git('ls-tree', '-r', '-z', revision).split(b'\0'):
        if row:
            header, path = row.split(b'\t')
            mode, kind, oid = header.decode().split()
            assert kind == 'blob'
            result[path.decode()] = (mode, oid)
    return result
previous, current = entries(BASE), entries(commit)
assert previous.keys() == current.keys() == prior.keys()
for path, (mode, oid) in previous.items():
    assert prior[path]['git_mode'] == mode
    assert prior[path]['observed_blob_oid'] == prior[path]['index_blob_oid'] == oid
rows = []
changed = []
for path, (mode, oid) in current.items():
    if previous[path] == (mode, oid):
        p = prior[path]
        rows.append(dict(path=path, sha256=p['sha256'], git_mode=mode,
                         actual_mode=p['actual_mode'], git_blob_oid=oid))
    else:
        target = source / path
        raw = target.read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid
        rows.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), git_mode=mode,
                         actual_mode=target.stat().st_mode & 0o777, git_blob_oid=oid))
        changed.append(path)
assert set(changed) == set(PATHS)
write('assets.json', dict(schema_version=1, producer='task-incremental-verified-asset-capture',
    source_commit=commit, source_tree=tree, source_object_format='sha1', source_kind='immutable-export',
    source_profile='git-tree-regular-blobs-v1', source_availability='local-only',
    content_binding='verified-git-blob-oids', scope=before['scope'], assets=rows,
    source_commit_relationship='Verified Git delta from exact CI candidate; unchanged actual CI blob identities reused',
    relation_to_ci_input_key='independent-local-construction-not-CI',
    reuse_proof=dict(parent_commit=BASE, actual_ci=40311281686, unchanged=len(rows)-len(changed),
                     changed=changed, all_prior_actual_blob_oids_verified=True)))

# Preserve existing raw receipt bytes and public locators; rerun only the affected entry.
config = json.loads(Path('/tmp/vaevas-context-fixture/config.json').read_text())
config.update(source_root=str(source), previous_data_dir=str(source / 'evas/capabilities/data'),
              asset_receipt=str(R / 'assets.json'))
inputs = R / 'prior-inputs'
inputs.mkdir()
for item in config['discoveries']:
    p = Path(item['entry_file'])
    target = inputs / p.name
    target.write_bytes(p.read_bytes())
    item['entry_file'] = str(target)
for item in config['rust_listings']:
    p = Path(item['receipt_file']); target = inputs / p.name
    target.write_bytes(p.read_bytes()); item['receipt_file'] = str(target)
for key in ['readiness_file']:
    p = Path(config[key]); target = inputs / p.name
    target.write_bytes(p.read_bytes()); config[key] = str(target)
for item in config['bridge_evidence']:
    p = Path(item['source_file']); target = inputs / p.name
    target.write_bytes(p.read_bytes()); item['source_file'] = str(target)
spec = importlib.util.spec_from_file_location('sp01_inventory', source / 'scripts/capabilities/collect_ci_inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)
entry = json.loads((ci / 'entry-005.json').read_text())['entry']
assert entry in inventory.parse_workflow((source / inventory.WORKFLOW).read_bytes())['entries']
receipt = inventory.child(source, entry, 60)
write('entry-005.json', dict(entry=entry, receipt=receipt))
assert receipt['complete'] and not receipt['errors'] and not receipt['unresolved_instances']
for item in config['discoveries']:
    oldentry = json.loads(Path(item['entry_file']).read_text())['entry']
    if oldentry['entry_id'] == entry['entry_id']:
        item['entry_file'] = str(R / 'entry-005.json')
        break
else:
    raise AssertionError('Affected entry not found in original config')
write('invocation.json', dict(source_commit=commit, actual_python=sys.version,
    scope='actual local single-entry TestLoader construction; no test bodies, CI, E1 or semantic qualification',
    instances=receipt['discovered_instances'], old20_preserved=True))
write('config-unpublished.json', config)
print(json.dumps(dict(capture=commit, tree=tree, actual_instances=receipt['discovered_instances'],
                      changed=changed, reused_asset_rows=len(rows)-len(changed), old20_preserved=True)))

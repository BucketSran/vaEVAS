"""PR273 r4: the stale-shard incident test and the STD-R3-01 fix on top of r3, then the catalog regenerated.

Commits on e8da1f77 (r3): a test commit (the incident reproduction the coordinator asked for as condition 2 of the coverage fix,
and the self-scan comparing resolved paths, review r3 STD-R3-01, P3) and a catalog commit regenerated from r3's catalog, twice,
byte for byte. Only scripts/tests/test_regression_shard_selection.py changes; workflow bytes stay those of r3, so every discovery
entry except the one owning that module is reused. Criteria, collector, DUT and language profile stay those of main.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the private export are writable; the
real worktree, index, branch, shared config and 20 old candidates stay unchanged. No scientific test bodies, simulator or backend run.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
B = D.parents[2]
S = D / 'source'
R3 = D.parent / 'r3'
INCIDENT = D.parent / 'r4-incident-test/incident-test.patch'
INCIDENT_SHA = '473c6249b6ca563a209fc7722e4f88345161f57be7918bf3f6295987e03db295'
BASE = 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'
OLD_BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
PRH = '9ea5de9f1a76c039cd8707f1a6db06ecf1829310'
PR_R1 = '6bfa35ea22cee6e2bbc1819164571364fd6938da'
R3_HEAD = 'e8da1f77cd59a6f50c2e9556b9830ade09285b20'
R3_TREE = '59eaeacaaafa4183b8d636f7c95c10e854b22495'
R3_FIXES = '668994c35b0af9cf7c4d03c6a74e034f2846cc6c'
R3_PUBLICATION_ARCHIVE = 'c300206570342f3fc8d59a6d1904b745685ba779'
RETENTION_REVS = (('pr273_r3', R3_HEAD), ('main', BASE), ('pr273_r2', PRH), ('pr273_r1', PR_R1), ('main_before_split', OLD_BASE))
PREFIX = 'evas/capabilities/observations/ci-version-pins-r4-20261028'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DATA = 'evas/capabilities/data/'
TEST_PATH = 'scripts/tests/test_regression_shard_selection.py'
P3_OLD = " and path != Path(__file__):"
P3_NEW = " and path != Path(__file__).resolve():"
SELF_SCAN_TEST = 'test_the_artifact_name_carries_the_attempt_and_nothing_else_names_the_old_one'
# The runs volume is reached through a symlink; loading the test through it is the reviewer's STD-R3-01 trigger.
LOGICAL_RUNS = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs')
WARNING_BYTES = 50 * 1024 * 1024
D1_PART_THRESHOLD = 35 * 1000 * 1000
TEST_MESSAGE = ('Test that coverage never merges a superseded shard from another image, and compare resolved paths in the '
                'attempt-name self-scan')
FINAL_MESSAGE = 'Regenerate the catalog for the shard selection test, keeping every object version'
AFFECTED_TESTS = ('test_regression_shard_selection.py', 'test_regression_admission.py', 'test_ci_pins.py', 'test_discover_rust.py',
                  'test_ci_inventory.py', 'test_ci_selection.py', 'test_catalog_part_split.py', 'test_catalog_history_selection.py',
                  'test_context_registration.py', 'test_regression_gate.py', 'test_trusted_regression_gate.py')
spec = importlib.util.spec_from_file_location('pins_r4_prior_task', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, BASE
PY = task.PY
git, write, sha = task.git, task.write, task.sha
spec = importlib.util.spec_from_file_location('pins_r4_r7_helpers', B / 'pr6/rebind-r7-20261027/prepare_pr6_r7.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.D, h.S, h.task, h.PY = D, S, task, PY
h.git, h.write, h.sha = git, write, sha
CRITERIA_PREFIXES, COLLECTOR, DERIVED_DATA = h.CRITERIA_PREFIXES, h.COLLECTOR, h.DERIVED_DATA
DUT_PREFIXES = ('evas/src/', 'evas/rust_core/')


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}
def guard(): return h.guard()
def stable(g): return h.stable(g)
def show(rev, path): return h.show(rev, path)
def names(a, b): return h.names(a, b)


def invariant():
    guard()
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(git('rev-parse', key, source=True).decode().strip()).resolve().is_relative_to(D.resolve())
    assert S.resolve().is_relative_to(D.resolve())


def logical(path):
    """The same directory reached through current/runs, whose entries are symlinks to the runs volume."""
    parts = path.resolve().parts
    index = parts.index('pr-review-20261025')
    candidate = LOGICAL_RUNS.joinpath(*parts[index:])
    assert candidate.resolve() == path.resolve() and str(candidate) != str(path.resolve()), candidate
    return candidate


def run_focused(name, root, results):
    """Run the selection tests from root; the return code is recorded, not asserted (the red run must fail)."""
    argv = [str(PY), '-B', '-m', 'unittest', 'discover', '-s', str(root / 'scripts/tests'), '-p', 'test_regression_shard_selection.py', '-v']
    with (D / name).open('x') as out:
        out.write('COMMAND ' + repr(argv) + '\nCWD ' + str(root) + '\n')
        out.flush()
        r = subprocess.run(argv, cwd=root, env=env(), stdout=out, stderr=subprocess.STDOUT)
        out.write('\nreturncode=' + str(r.returncode) + '\n')
    results.append({'name': name, 'command': argv, 'cwd': str(root), 'returncode': r.returncode, 'log': str(D / name),
                    'log_sha256': sha((D / name).read_bytes())})
    print(name, r.returncode, flush=True)
    return r.returncode


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert sha(INCIDENT.read_bytes()) == INCIDENT_SHA
    assert git('rev-parse', R3_HEAD + '^{tree}').decode().strip() == R3_TREE
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W), 'archive', R3_HEAD],
                                    env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pins-r4'], cwd=S, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', R3_HEAD, source=True)
    git('update-ref', 'HEAD', R3_HEAD, source=True)
    invariant()
    assert not h.changed_vs(R3_HEAD)
    r = subprocess.run(['/usr/bin/git', 'apply', '--whitespace=nowarn', str(INCIDENT)], cwd=S, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
    text = (S / TEST_PATH).read_text()
    assert text.count(P3_OLD) == 1 and P3_NEW not in text
    results = []
    # STD-R3-01 before the fix: the physical path passes, the logical path fails because the self-scan does not skip itself.
    red_physical = run_focused('p3-red-physical.txt', S, results)
    red_logical = run_focused('p3-red-logical.txt', logical(S), results)
    assert red_physical == 0 and red_logical != 0, (red_physical, red_logical)
    red_log = (D / 'p3-red-logical.txt').read_text()
    assert red_log.count('\nFAIL: ') == 1 and '\nERROR: ' not in red_log, 'Read p3-red-logical.txt'
    assert '\nFAIL: ' + SELF_SCAN_TEST + ' ' in red_log and 'FAILED (failures=1)' in red_log, 'Read p3-red-logical.txt'
    (S / TEST_PATH).write_text(text.replace(P3_OLD, P3_NEW))
    green_physical = run_focused('p3-green-physical.txt', S, results)
    green_logical = run_focused('p3-green-logical.txt', logical(S), results)
    assert green_physical == green_logical == 0, (green_physical, green_logical)
    assert sorted(h.changed_vs(R3_HEAD)) == [TEST_PATH]
    (D / 'test.diff').write_bytes(git('diff', R3_HEAD, '--', TEST_PATH, source=True))
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'parent': R3_HEAD, 'parent_tree': R3_TREE,
          'base': BASE, 'incident_patch': str(INCIDENT), 'incident_patch_sha256': INCIDENT_SHA, 'p3_fix': {'finding': 'STD-R3-01',
          'old': P3_OLD.strip(), 'new': P3_NEW.strip(), 'file': TEST_PATH}, 'focused_runs': results, 'changed': [TEST_PATH],
          'test_sha256': sha((S / TEST_PATH).read_bytes()), 'before': before, 'after': after, 'scientific_execution': False,
          'executed_by': 'tclaude/claude-opus-5-5'})


def commit_tree(parent_index_rev, paths, message, parents, name):
    index = D / (name + '.index')
    assert not index.exists()
    git('read-tree', parent_index_rev, index=index)
    modes = task.entries(parent_index_rev)
    for path in paths:
        target = S / path
        if target.exists():
            raw = target.read_bytes()
            mode = modes.get(path, ('100755' if os.access(target, os.X_OK) else '100644', None))[0]
            oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
            git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
        else:
            git('update-index', '--force-remove', path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    args = []
    for p in parents:
        args += ['-p', p]
    head = git('commit-tree', tree, *args, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return head, tree


def commit():
    invariant()
    prep = load(D / 'source-preparation.json')
    assert not (D / 'test-commit.json').exists()
    assert sha((S / TEST_PATH).read_bytes()) == prep['test_sha256']
    head, tree = commit_tree(R3_HEAD, [TEST_PATH], TEST_MESSAGE, [R3_HEAD], 'test')
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    assert sorted(names(R3_HEAD, head)) == [TEST_PATH]
    write(D / 'test-commit.json', {'commit': head, 'tree': tree, 'parent': R3_HEAD, 'paths': [TEST_PATH], 'message': TEST_MESSAGE,
          'scientific_qualification': False})
    print(json.dumps({'test_commit': head, 'tree': tree}), flush=True)


def assets():
    """Asset receipt for the test commit, reusing r3's verified receipt of 668994c3 for unchanged blobs."""
    invariant()
    tc = load(D / 'test-commit.json')
    assert not (D / 'assets.json').exists()
    observed = load(R3 / 'assets.json')
    assert observed['source_commit'] == R3_FIXES
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(R3_FIXES), task.entries(tc['commit'])
    assert set(prior) == set(old_rows)
    out, changed = [], []
    for path, (mode, oid) in sorted(after.items()):
        old = old_rows.get(path)
        if prior.get(path) == (mode, oid):
            assert (old['git_mode'], old['git_blob_oid']) == (mode, oid), path
            value, actual_mode = old['sha256'], old['actual_mode']
        else:
            raw = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid, path
            value, actual_mode = sha(raw), (S / path).stat().st_mode & 0o777
            changed.append(path)
        out.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual_mode, 'git_blob_oid': oid})
    assert sorted(changed) == sorted(p for p in names(R3_FIXES, tc['commit']) if p in after)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': tc['commit'], 'source_tree': tc['tree'], 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': out,
          'reuse_proof': {'previous_receipt': str(R3 / 'assets.json'), 'previous_receipt_sha256': sha((R3 / 'assets.json').read_bytes()),
                          'previous_source_commit': R3_FIXES, 'unchanged': len(out) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'assets': len(out), 'changed': len(changed)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    tc = load(D / 'test-commit.json')
    config = load(R3 / 'config.json')
    candidates = {}
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    changed_paths = sorted(names(R3_HEAD, tc['commit']) - DERIVED_DATA)
    assert changed_paths == [TEST_PATH], changed_paths
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = tc['commit']
    inventory = h.module('pins_r4_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    tip = h.remote_archive()
    assert tip == R3_PUBLICATION_ARCHIVE, tip
    chosen, new_count = [], 0
    for i, entry in enumerate(entries):
        start = entry['start'].rstrip('/') + '/'
        touched = sorted(p for p in changed_paths if p.startswith(start) and fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern']))
        matching = []
        if not touched:
            for path, value, locator in candidates.values():
                r = value['receipt']
                if value['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']:
                    continue
                if assets.get(r['collector']['path']) != r['collector']['sha256']:
                    continue
                if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                    continue
                matching.append((path, value, locator))
            assert len(matching) == 1, (entry['entry_id'], len(matching))
        if matching:
            path, value, locator = matching[0]
            assert git('show', locator['revision'] + ':' + locator['path']) == path.read_bytes()
            git('merge-base', '--is-ancestor', locator['revision'], tip)
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
                   'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances']}
        else:
            r = inventory.child(S, entry, 90)
            assert r['complete'] and not r['errors'] and not r['unresolved_instances'], entry['entry_id']
            path = D / 'new-discovery' / ('entry-%03d.json' % i)
            path.parent.mkdir(exist_ok=True)
            write(path, {'entry': entry, 'receipt': r})
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': False, 'forced_by_changed_paths': touched,
                   'sha256': sha(path.read_bytes()), 'instances': r['discovered_instances']}
            new_count += 1
        row.update(start=entry['start'], pattern=entry['pattern'])
        chosen.append(row)
    assert new_count >= 1
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen) - new_count,
          'new_collections': new_count, 'changed_paths_vs_r3': changed_paths, 'archive_tip_checked': tip,
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the r3 build receipts; entries owning the changed test are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def union():
    """Previous catalog for generation: r3's catalog, which already keeps every object version of main and PR273 r1/r2."""
    invariant()
    union_dir = D / 'previous-union'
    assert not union_dir.exists() and not (D / 'union-acceptance.json').exists()
    union_dir.mkdir()
    header = json.loads(show(R3_HEAD, DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts'], 'catalog-sources.json', 'asset-index.json', 'entrypoint-index.json']:
        raw = show(R3_HEAD, DATA + name)
        if raw is not None:
            (union_dir / name).write_bytes(raw)
    merged = task.objects(union_dir)
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    write(D / 'union-acceptance.json', {'previous': R3_HEAD, 'union_dir': str(union_dir), 'union_objects': len(merged), 'retention': retention,
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'union_objects': len(merged)}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = h.remote_archive()
    assert parent == R3_PUBLICATION_ARCHIVE, parent
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('source-preparation.json', 'test-commit.json', 'test.diff', 'assets.json', 'discovery-selection.json', 'union-acceptance.json',
                 'p3-red-physical.txt', 'p3-red-logical.txt', 'p3-green-physical.txt', 'p3-green-logical.txt'):
        shutil.copyfile(D / name, dest / name)
    for name in ('incident-test.patch', 'incident-test-receipt.json', 'green-run.txt', 'red-run-new-test.txt', 'red-run-all.txt'):
        shutil.copyfile(INCIDENT.parent / name, dest / ('incident-' + name.removeprefix('incident-')))
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_pins_r4.py')
    (dest / 'README.md').write_text('# CI version pins r4\n\n'
        'The test commit on r3 (e8da1f77) adds the reproduction of the CI 40602342818 incident to the shard selection tests: shard 2 '
        'ran on a new runner image, its rerun on the old one, and both uploads stayed in the run. The new step selects the rerun, the '
        'merged runtime profile equals each selected shard, and the old single-name layout makes the merge refuse the mixed shards. '
        'The same commit makes the attempt-name self-scan compare resolved paths (review r3, STD-R3-01). The catalog is regenerated from '
        "r3's catalog. Criteria, collector and DUT are unchanged. Scientific qualification is false.\n")
    idx = D / 'archive.index'
    assert not idx.exists()
    git('read-tree', parent, index=idx)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        path = p.relative_to(D / 'archive-files').as_posix()
        raw = p.read_bytes()
        assert len(raw) < WARNING_BYTES, (path, len(raw))
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive CI version pins r4 construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'remote_parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R3 / 'config.json')
    old = {}
    for item in config['discoveries']:
        entry = load(Path(item['entry_file']))['entry']
        old[entry['entry_id']] = entry
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(D / 'previous-union'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    selection = load(D / 'discovery-selection.json')
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': head, 'path': PREFIX + '/new-discovery/' + path.name}
    new = {e['entry_id']: e for e in selection['entries']}
    for bridge in config['bridge_evidence']:
        assert all(cid in new and cid in old for cid in bridge['consumer_entry_ids']), bridge['path']
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'archive': head, 'parent': parent, 'files': len(files)}), flush=True)


def generate():
    invariant()
    assert not (D / 'generation-acceptance.json').exists()
    assert load(D / 'config.json')['previous_data_dir'] == str(D / 'previous-union')
    for name in ('catalog', 'catalog-repeat'):
        with (D / ('generation-' + name + '.stdout')).open('xb') as out, (D / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                                  '--output', str(D / name)], cwd=S, env=env(), stdout=out, stderr=err)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    first, second = D / 'catalog/tree/evas/capabilities/data', D / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / 'catalog/generation-report.json')
    previous, current = task.objects(D / 'previous-union'), task.objects(first)
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    header = load(first / 'registry.json')
    versions, prev_versions = {}, {}
    for (i, v) in current:
        versions.setdefault(i, []).append(v)
    for (i, v) in previous:
        prev_versions.setdefault(i, []).append(v)
    problems = []
    for i, vs in versions.items():
        new = set(vs) - set(prev_versions.get(i, []))
        if len(new) > 1 or (new and header['current'].get(i) not in new):
            problems.append({'id': i, 'new_versions': sorted(new), 'current': header['current'].get(i)})
        if i in header['current'] and header['current'][i] not in vs:
            problems.append({'id': i, 'current_missing': header['current'][i]})
    assert not problems, problems[:5]
    paths = []
    for p in sorted(first.glob('*.json')):
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    largest = max(sizes.items(), key=lambda x: x[1])
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
          'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind, 'deterministic_double_generation': True,
          'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes, 'largest_data_file': largest,
          'd1_threshold': {'rule': 'coordinator 2026-10-28: schedule D1 when any catalog part exceeds 35 MB', 'bytes': D1_PART_THRESHOLD,
                           'reached': largest[1] > D1_PART_THRESHOLD},
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'new_object_versions': len(new_objects),
                      'by_kind': by_kind, 'largest': largest}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    h.run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    h.run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    tc = load(D / 'test-commit.json')
    paths = h.changed_vs(tc['commit'])
    rendered = set(h.render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'test_commit': tc['commit'], 'paths_vs_test_commit': paths, 'render_outputs': len(rendered), 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()}, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_test_commit': len(paths)}), flush=True)


def freeze():
    invariant()
    tc, der = load(D / 'test-commit.json'), load(D / 'derive-acceptance.json')
    assert not (D / 'final-candidate.json').exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = h.changed_vs(tc['commit'])
    assert sorted(generated) == sorted(der['paths_vs_test_commit'])
    head, tree = commit_tree(tc['commit'], generated, FINAL_MESSAGE, [tc['commit']], 'final')
    for anc in (R3_HEAD, PRH, BASE, tc['commit']):
        git('merge-base', '--is-ancestor', anc, head)
    complete = sorted(git('diff', '--name-only', BASE, head).decode().splitlines())
    increment = sorted(git('diff', '--name-only', R3_HEAD, head).decode().splitlines())
    criteria = sorted(p for p in complete if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in complete if p in COLLECTOR)
    dut = sorted(p for p in complete if p.startswith(DUT_PREFIXES))
    assert not criteria and not collector and not dut, (criteria, collector, dut)
    assert all(p == TEST_PATH or p in DERIVED_DATA or p in set(h.render_outputs(S)) for p in increment), increment
    blobs, changed = [], set(complete)
    for line in git('ls-tree', '-r', '-l', head).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final = {'commit': head, 'tree': tree, 'base': BASE, 'parent': R3_HEAD, 'test_commit': tc['commit'], 'complete_paths': complete,
             'increment_vs_r3': increment, 'criteria_changes': criteria, 'collector_changes': collector, 'dut_changes': dut,
             'derive': str(D / 'derive-acceptance.json'), 'large_unchanged_blobs': blobs,
             'precheck': 'runs on the frozen head in parallel with CI', 'CI': 'pending',
             'review': 'r3 review accepted; STD-R3-01 (P3) fixed here under the P3 rule; STD-01 and NOTE-R3-01 go to follow-up issues (tools tier, round 3)',
             'published': False, 'scientific_qualification': False, 'frozen_at_utc': datetime.now(timezone.utc).isoformat()}
    write(D / 'final-candidate.json', final)
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': head, 'tree': tree, 'complete_paths': len(complete), 'increment': len(increment)}), flush=True)


def precheck():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    results = []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths), 'focused': False,
          'scope': 'CI version pins r4, quick maintenance gate; full scientific regression is CI only.'})
    h.run_logged('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], results)
    h.run_logged('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'], results)
    h.run_logged('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], results)
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    for name in AFFECTED_TESTS:
        h.run_logged('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'],
                     results, extra_env=tools)
    h.run_logged('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': paths,
          'checks': results, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def inventory():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'inventory-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    results = []
    out = D / 'catalog-inventory-local'
    h.run_logged('inventory-local.txt', [str(PY), '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                                         '--require-catalog', '--registry-data', 'evas/capabilities/data'], results,
                 extra_env={'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']})
    summary = load(out / 'summary.json')
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree']
    write(D / 'inventory-acceptance.json', {'candidate': final['commit'], 'tree': final['tree'], 'checks': results,
          'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'commit', 'assets', 'discover', 'union', 'archive', 'generate', 'derive', 'freeze',
                                          'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

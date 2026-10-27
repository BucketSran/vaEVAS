"""Fix the PR6 review-r3 findings on top of 5455ae7b.

Two source commits come from worker patches: the Markdown support audit (R3-01, R3-02) and the
Rust follow-up (R3-03 strict argv for new receipts, R3-04 the fixed toolchain passed to the
package workflow). The catalog is then regenerated from the union of the 5455ae7b catalog and
the c76cb65f objects that the rebuild dropped (R3-05), and checked to keep every object version
of main, c76cb65f and 5455ae7b.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the
private export are writable; the real worktree, index, branch, shared config and 20 old
candidates stay unchanged. No scientific test bodies, simulator or backend run here.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import copy
import difflib
import fnmatch
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
B = D.parents[1]
S = D / 'source'
R4 = B / 'pr6/rebind-r4-20261027'
W1 = B / 'pr6/support-audit-r4-grok-20261027'
W2 = B / 'pr6/rust-pin-followup-sonnet-20261027'
BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
BASE_TREE = 'a68a89e1c145767f830fd5d602ab1be9f96b6b90'
PRIOR = 'c76cb65f7c260712eb77bc9322bb294ec32287c5'
PARENT = '5455ae7b006488902476bba045e9e2971102d8f5'
PARENT_TREE = 'c9622d94210ce88732cdae34a66ae1c3cf463bcd'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
OBSERVED = D / 'ci-40524845780/catalog-inventory/assets-before.json'
# previous-union holds the attempt-r1 copy, kept as failure evidence: registry.load refused a data dir outside the source root.
UNION = D / 'previous-union-r2'
PREFIX = 'evas/capabilities/observations/pr6-review-r3-fixes-r5-20261027'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DERIVED_DATA = {
    'evas/capabilities/data/asset-index.json', 'evas/capabilities/data/catalog-sources.json',
    'evas/capabilities/data/entrypoint-index.json', 'evas/capabilities/data/historical-index.json',
    'evas/capabilities/data/method-index.json', 'evas/capabilities/data/registry.json',
    'evas/docs/development/TRACEABILITY.md',
}
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
             'scripts/regression_observation_policy.json', 'evas/capabilities/data/language-profile.json')
AFFECTED_TESTS = ('test_discover_rust.py', 'test_rust_catalog_reconcile.py', 'test_ci_evidence_v3.py', 'test_regression_runner.py',
                  'test_regression_admission.py', 'test_ci_selection.py', 'test_ci_inventory.py', 'test_fast_feedback.py',
                  'test_catalog_derived_outputs.py', 'test_catalog_history_selection.py', 'test_regression_gate.py',
                  'test_trusted_regression_gate.py', 'test_context_registration.py')
WORKERS = (('audit', W1, 'Match Markdown support records within their requirement and reject duplicates or contradictions'),
           ('rust', W2, 'Pass the fixed Rust toolchain to the package workflow and keep +stable for historical receipts only'))
FINAL_MESSAGE = 'Refresh PR6 catalog and generated views, keeping every earlier object version'
SHARED_CONFIG = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/config')
NOTES = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/local/notes/t3-orchestration-20261026/shared-git-config-20261027')
ACCEPTED_CONFIG = NOTES / 'config.accepted-20261027T075910Z'
ACCEPTED_RECEIPT = NOTES / 'accepted-20261027T075910Z.json'
ACCEPTED_CONFIG_SHA = 'de2b08ef3ba66e96be8b70c87346ff4a96f905e1272934ddd86c218dba501ea8'
VSCODE_MERGE_BASE = re.compile(r'\tvscode-merge-base = \S+\n?')
BRANCH_HEADER = re.compile(r'\[branch "[^"\n]+"\]\n?')
spec = importlib.util.spec_from_file_location('prior_c0_construction', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, PARENT
PY = task.PY
git, write, sha = task.git, task.write, task.sha


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}


def module(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(s)
    s.loader.exec_module(result)
    return result


def config_guard():
    """Coordinator rule: pure vscode-merge-base additions to the accepted reference are recorded and accepted."""
    current = SHARED_CONFIG.read_bytes()
    accepted = ACCEPTED_CONFIG.read_bytes()
    assert sha(accepted) == ACCEPTED_CONFIG_SHA
    if sha(current) == ACCEPTED_CONFIG_SHA:
        return {'sha256': ACCEPTED_CONFIG_SHA, 'status': 'equal-accepted-reference'}
    old, new = accepted.decode().splitlines(True), current.decode().splitlines(True)
    added = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        assert tag == 'insert', 'shared config change beyond accepted editor drift; stop and report to coordinator'
        block = new[j1:j2]
        for k, line in enumerate(block):
            if VSCODE_MERGE_BASE.fullmatch(line):
                continue
            following = block[k + 1:k + 2]
            assert BRANCH_HEADER.fullmatch(line) and following and VSCODE_MERGE_BASE.fullmatch(following[0]), \
                'shared config change beyond accepted editor drift; stop and report to coordinator'
        added.extend(block)
    record = D / ('shared-config-drift-' + sha(current)[:16] + '.json')
    if not record.exists():
        write(record, {'observed_at_utc': datetime.now(timezone.utc).isoformat(), 'observed_sha256': sha(current),
                       'accepted_reference': str(ACCEPTED_CONFIG), 'accepted_sha256': ACCEPTED_CONFIG_SHA,
                       'added_lines': added, 'removed_lines': [], 'policy': str(ACCEPTED_RECEIPT),
                       'classification': 'pre-accepted editor vscode-merge-base drift; report in next ordinary receipt'})
    return {'sha256': sha(current), 'status': 'accepted-editor-drift', 'record': str(record)}


def guard():
    assert git('rev-parse', '--show-toplevel').decode().strip() == str(task.W)
    assert git('rev-parse', 'HEAD').decode().strip() == REAL_HEAD
    assert not git('diff', '--cached', '--name-only').strip()
    assert git('config', 'user.name').decode().strip() == 'BucketSran'
    assert git('config', 'user.email').decode().strip() == '138781625+BucketSran@users.noreply.github.com'
    plan = load(B / 'main-plan.json')
    rows = [r for r in plan['handoff']['files'] if r['path'].startswith('evas/tests/')]
    assert len(rows) == 20
    for row in rows:
        assert sha((task.W / row['path']).read_bytes()) == row['sha256'], row['path']
    config = config_guard()
    return {'head': REAL_HEAD, 'index_sha256': sha((task.GD / 'index').read_bytes()),
            'shared_config_sha256': config['sha256'], 'shared_config_status': config['status'], 'old_candidates': len(rows)}


def stable(g):
    return {k: v for k, v in g.items() if not k.startswith('shared_config_')}


def invariant():
    guard()
    assert Path(git('rev-parse', '--absolute-git-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--git-common-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--show-toplevel', source=True).decode().strip()).resolve() == S
    assert S.resolve().is_relative_to(D.resolve())


def private_env():
    return env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0'}


def changed_vs(rev):
    git('add', '--intent-to-add', '--', '.', source=True)
    paths = git('diff', '--name-only', rev, source=True).decode().splitlines()
    git('reset', '--quiet', source=True)
    return paths


def run_logged(name, argv, results, cwd=None, extra_env=None):
    start = datetime.now(timezone.utc).isoformat()
    e = env() | {'CARGO_TARGET_DIR': str(B / 'pr4/bootstrap-integration-20261026/precheck-rust-target')} | (extra_env or {})
    with (D / name).open('x') as out:
        out.write('COMMAND ' + repr(argv) + '\n')
        out.flush()
        r = subprocess.run(argv, cwd=cwd or S, env=e, stdout=out, stderr=subprocess.STDOUT)
        out.write('\nreturncode=' + str(r.returncode) + '\n')
    results.append({'command': argv, 'cwd': str(cwd or S), 'receipt': str(D / name), 'returncode': r.returncode,
                    'started_at_utc': start, 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
    print(name, r.returncode, flush=True)
    assert r.returncode == 0, name


def render_outputs():
    sys.path.insert(0, str(S / 'evas/capabilities'))
    renderer = module('fix_render_outputs', S / 'evas/capabilities/render.py')
    files = renderer.outputs(renderer.registry())
    return sorted(Path(p).resolve().relative_to(S.resolve()).as_posix() for p in files)


def objects_at(rev):
    """(id, version) -> object for the catalog committed at rev, read from Git objects."""
    header = json.loads(git('show', rev + ':evas/capabilities/data/registry.json'))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(git('show', rev + ':evas/capabilities/data/' + part))['objects']
    return {(item['id'], item['version']): item for item in result}


def patch_paths(patch):
    paths = []
    for line in patch.read_text().splitlines():
        if line.startswith('diff --git a/'):
            a, b = line[len('diff --git a/'):].split(' b/', 1)
            assert a == b, line
            paths.append(a)
    return paths


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', PARENT + '^{tree}').decode().strip() == PARENT_TREE
    git('merge-base', '--is-ancestor', BASE, PARENT)
    git('merge-base', '--is-ancestor', PRIOR, PARENT)
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', PARENT], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pr6-r5'], cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', PARENT, source=True)
    git('update-ref', 'HEAD', PARENT, source=True)
    invariant()
    plan = []
    seen = set()
    for kind, worker, message in WORKERS:
        patch = worker / 'source.patch'
        paths = patch_paths(patch)
        assert paths and not seen & set(paths), (kind, paths)
        assert not any(p.startswith(CRITERIA_PREFIXES) or p in COLLECTOR or p in DERIVED_DATA for p in paths), (kind, paths)
        seen |= set(paths)
        files_before = {p: sha((S / p).read_bytes()) if (S / p).exists() else None for p in paths}
        check = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'apply', '--check', str(patch)],
                               cwd=S, env=private_env(), capture_output=True, text=True)
        assert check.returncode == 0, (kind, check.stderr)
        plan.append({'kind': kind, 'worker': str(worker), 'patch': str(patch), 'patch_sha256': sha(patch.read_bytes()),
                     'message': message, 'paths': paths, 'before': files_before})
    for row in plan:
        applied = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'apply', row['patch']],
                                 cwd=S, env=private_env(), capture_output=True, text=True)
        assert applied.returncode == 0, (row['kind'], applied.stderr)
        row['after'] = {p: sha((S / p).read_bytes()) for p in row['paths']}
    results = []
    run_logged('pre-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    paths = changed_vs(PARENT)
    assert set(paths) == seen, sorted(set(paths) ^ seen)
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-plan.json', {'parent': PARENT, 'patches': plan})
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'parent': PARENT,
          'parent_tree': PARENT_TREE, 'plan': str(D / 'source-plan.json'), 'paths': sorted(paths), 'pre_render_checks': results,
          'criteria_collector_language_unchanged': True,
          'review': str(B / 'night-coordination/pr6-rebuild-astra-r3-20261027/review-report.json'),
          'before': before, 'after': after, 'published': False, 'scientific_execution': False,
          'semantic_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'paths': sorted(paths)}), flush=True)


def commit_paths(parent, paths, message):
    index = D / 'commit.index'
    assert not index.exists()
    git('read-tree', parent, index=index)
    prior = task.entries(parent)
    for path in paths:
        raw = (S / path).read_bytes()
        mode = prior.get(path, ('100644', None))[0]
        assert (S / path).stat().st_mode & 0o777 == (0o755 if mode == '100755' else 0o644), path
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    head = git('commit-tree', tree, '-p', parent, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return head, tree


def capture():
    invariant()
    plan = load(D / 'source-plan.json')
    assert not (D / 'capture.json').exists()
    commits, parent = [], PARENT
    for row in plan['patches']:
        assert all(sha((S / p).read_bytes()) == v for p, v in row['after'].items()), row['kind']
        head, tree = commit_paths(parent, row['paths'], row['message'])
        assert sorted(git('diff', '--name-only', parent, head).decode().splitlines()) == sorted(row['paths'])
        commits.append({'kind': row['kind'], 'commit': head, 'tree': tree, 'parents': [parent], 'paths': row['paths']})
        parent = head
    git('read-tree', parent, source=True)
    git('update-ref', 'HEAD', parent, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    paths = sorted(git('diff', '--name-only', PARENT, parent).decode().splitlines())
    write(D / 'capture.json', {'parent': PARENT, 'commit': parent, 'tree': commits[-1]['tree'], 'commits': commits, 'paths': paths,
          'scientific_qualification': False})
    (D / 'source.patch').write_bytes(git('diff', '--binary', PARENT, parent))
    (D / 'source.commits').write_text('\n'.join(git('cat-file', 'commit', c['commit']).decode() for c in commits))
    observed = load(OBSERVED)
    assert observed['source_tree'] == PARENT_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(PARENT), task.entries(parent)
    assert set(prior) == set(old_rows) and set(prior) <= set(after)
    rows, changed = [], []
    for path, (mode, oid) in sorted(after.items()):
        old = old_rows.get(path)
        if prior.get(path) == (mode, oid):
            assert (old['git_mode'], old['observed_blob_oid'], old['index_blob_oid']) == (mode, oid, oid), path
            value, actual_mode = old['sha256'], old['actual_mode']
        else:
            raw = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid, path
            value, actual_mode = sha(raw), (S / path).stat().st_mode & 0o777
            changed.append(path)
        rows.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual_mode, 'git_blob_oid': oid})
    assert sorted(changed) == paths
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': parent, 'source_tree': commits[-1]['tree'], 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': rows,
          'reuse_proof': {'actual_CI': 40524845780, 'observation': str(OBSERVED), 'unchanged': len(rows) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'commits': [c['commit'] for c in commits], 'paths': paths, 'assets': len(rows)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(R4 / 'config.json')
    candidates = {}
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    changed_paths = load(D / 'capture.json')['paths']
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = load(D / 'capture.json')['commit']
    inventory = module('pr6_r5_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(entries) == len(candidates) == 31, (len(entries), len(candidates))
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
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
            assert len(matching) <= 1, entry['entry_id']
        if matching:
            path, value, locator = matching[0]
            assert git('show', locator['revision'] + ':' + locator['path']) == path.read_bytes()
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
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen) - new_count,
          'new_collections': new_count,
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the 5455ae7b receipts; entries whose start/pattern match a changed path, or whose entry changed, are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def union():
    """Previous catalog for generation: the 5455ae7b catalog plus the c76cb65f objects it dropped (R3-05)."""
    invariant()
    assert not UNION.exists() and not (D / 'union-acceptance.json').exists()
    data = S / 'evas/capabilities/data'
    assert not any(p.startswith('evas/capabilities/data/') for p in changed_vs(PARENT))
    shutil.copytree(data, UNION)
    header = load(UNION / 'registry.json')
    present = task.objects(UNION)
    assert present == objects_at(PARENT)
    prior_header = json.loads(git('show', PRIOR + ':evas/capabilities/data/registry.json'))
    parts = {'registry.json': prior_header['objects']}
    for part in prior_header['object_parts']:
        parts[part] = json.loads(git('show', PRIOR + ':evas/capabilities/data/' + part))['objects']
    added, added_objects, conflicts, by_part = [], [], [], {}
    for part, items in parts.items():
        assert part == 'registry.json' or part in header['object_parts'], part
        target = UNION / part
        doc = load(target)
        for obj in items:
            key = (obj['id'], obj['version'])
            if key in present:
                if present[key] != obj:
                    conflicts.append(list(key))
                continue
            doc['objects'].append(obj)
            present[key] = obj
            added_objects.append(obj)
            added.append({'part': part, 'id': obj['id'], 'version': obj['version']})
            by_part[part] = by_part.get(part, 0) + 1
        target.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + '\n')
    assert not conflicts, conflicts[:5]
    merged = task.objects(UNION)
    assert all(merged.get(k) == v for k, v in objects_at(PARENT).items())
    assert all(merged.get(k) == v for k, v in objects_at(PRIOR).items())
    assert all(merged.get(k) == v for k, v in objects_at(BASE).items())
    sys.path.insert(0, str(S / 'evas/capabilities'))
    registry = module('pr6_r5_registry', S / 'evas/capabilities/registry.py')
    # registry.load accepts only data inside the source root, so validate the union in memory.
    before = registry.load(data, root=S, repositories={'vaevas': S})
    candidate = copy.deepcopy(before.data)
    candidate['objects'].extend(copy.deepcopy(added_objects))
    after = registry.Registry(candidate, root=S, repositories={'vaevas': S})
    assert after.data['current'] == before.data['current']
    write(D / 'union-acceptance.json', {'parent': PARENT, 'prior': PRIOR, 'base': BASE, 'union_dir': str(UNION),
          'parent_objects': len(objects_at(PARENT)), 'added_from_prior': len(added), 'added_by_part': by_part,
          'conflicts': conflicts, 'union_objects': len(merged), 'registry_load_passed': True, 'current_unchanged': True,
          'added': added, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'added_from_prior': len(added), 'added_by_part': by_part, 'union_objects': len(merged)}), flush=True)


def remote_archive():
    line = git('ls-remote', 'origin', ARCHIVE_REF).decode().split()
    assert len(line) == 2 and line[1] == ARCHIVE_REF, line
    return line[0]


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    union_receipt = load(D / 'union-acceptance.json')
    parent = remote_archive()
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commits', 'discovery-selection.json', 'source-preparation.json',
                 'source-plan.json', 'union-acceptance.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_pr6_r5.py')
    shutil.copyfile(W1 / 'result.json', dest / 'audit-fix-result.json')
    shutil.copyfile(W2 / 'result.json', dest / 'rust-followup-result.json')
    (dest / 'README.md').write_text('# PR6 review-r3 fixes on 5455ae7b\n\n'
        'Two source commits: the Markdown support audit now matches qualification records within their own requirement '
        'and rejects duplicate, extra or contradictory records and header fields (R3-01, R3-02); the Rust listing check '
        'keeps the old +stable argv for historical receipts only, and the package workflow receives the one fixed Rust '
        'toolchain from the main workflow (R3-03, R3-04). The catalog is regenerated from the 5455ae7b catalog plus the '
        + str(union_receipt['added_from_prior']) + ' c76cb65f object versions that the rebuild had dropped (R3-05). '
        'Criteria, collector and language profile are unchanged by this round. Scientific qualification is false.\n')
    idx = D / 'archive.index'
    git('read-tree', parent, index=idx)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        path = p.relative_to(D / 'archive-files').as_posix()
        raw = p.read_bytes()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive PR6 review-r3 fixes construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R4 / 'config.json')
    old = {}
    for item in config['discoveries']:
        entry = load(Path(item['entry_file']))['entry']
        old[entry['entry_id']] = entry
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(UNION),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    selection = load(D / 'discovery-selection.json')
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': head, 'path': PREFIX + '/new-discovery/' + path.name}
    new = {e['entry_id']: e for e in selection['entries']}
    remap = []
    for bridge in config['bridge_evidence']:
        ids = []
        for cid in bridge['consumer_entry_ids']:
            if cid in new:
                ids.append(cid)
                continue
            match = [k for k, v in new.items() if (v['start'], v['pattern']) == (old[cid]['start'], old[cid]['pattern'])]
            assert len(match) == 1, (cid, match)
            ids.append(match[0])
            remap.append({'bridge': bridge['path'], 'old_entry_id': cid, 'new_entry_id': match[0],
                          'start': old[cid]['start'], 'pattern': old[cid]['pattern']})
        bridge['consumer_entry_ids'] = ids
    write(D / 'bridge-consumer-remap.json', {'reason': 'workflow edits change entry identities; the bridged TestLoader entry keeps its start and pattern',
          'remap': remap})
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'archive': head, 'parent': parent, 'files': len(files), 'bridge_remap': len(remap)}), flush=True)


def generate():
    invariant()
    assert load(D / 'config.json')['previous_data_dir'] == str(UNION)
    with (D / 'generation.stdout').open('xb') as out, (D / 'generation.stderr').open('xb') as err:
        run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                              '--output', str(D / 'catalog')], cwd=S, env=env(), stdout=out, stderr=err)
    assert run.returncode == 0, 'Read generation.stderr'
    report = load(D / 'catalog/generation-report.json')
    previous, current = task.objects(UNION), task.objects(D / 'catalog/tree/evas/capabilities/data')
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in (('main', BASE), ('prior_pr6', PRIOR), ('parent', PARENT)):
        expected = objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    paths = []
    for p in (D / 'catalog/tree/evas/capabilities/data').glob('*.json'):
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert 'evas/capabilities/data/language-profile.json' not in paths
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'retention': retention, 'objects': report['objects'], 'namespace_counts': report['namespace_counts'],
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'retention': retention,
                      'objects': report['objects']}), flush=True)


def derive():
    """Regenerate the committed derived files; checks run later against the frozen head."""
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    cap = load(D / 'capture.json')
    paths = changed_vs(PARENT)
    rendered = set(render_outputs())
    unexpected = sorted(set(paths) - set(cap['paths']) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'parent': PARENT, 'source_capture': cap['commit'],
          'paths_vs_parent': paths, 'render_outputs': len(rendered), 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_parent': len(paths)}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(cap['commit'])
    final = task.make_commit(cap['commit'], generated, FINAL_MESSAGE + TRAILER, 'final')
    git('merge-base', '--is-ancestor', PARENT, final['commit'])
    assert sorted(git('diff', '--name-only', PARENT, final['commit']).decode().splitlines()) == sorted(der['paths_vs_parent'])
    complete = sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines())
    final.update(base=BASE, parent=PARENT, source_capture=cap['commit'], commits=cap['commits'], complete_paths=complete,
                 delta_vs_parent=der['paths_vs_parent'], derive=str(D / 'derive-acceptance.json'),
                 precheck='runs on the frozen head in parallel with CI',
                 review='Incremental Astra r4 after CI selection and fast-checks pass on this head', CI='pending', published=False,
                 scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', PARENT, final['commit']))
    git('read-tree', final['commit'], source=True)
    git('update-ref', 'HEAD', final['commit'], source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'delta_vs_parent': len(der['paths_vs_parent'])}), flush=True)


def precheck():
    """Local checks on the frozen head; they do not change any committed byte."""
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    results = []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths),
          'focused': False, 'scope': 'PR6 review-r3 fixes quick maintenance gate; full scientific regression is CI only.'})
    run_logged('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], results)
    run_logged('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'], results)
    run_logged('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], results)
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    for name in AFFECTED_TESTS:
        run_logged('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'],
                   results, extra_env=tools)
    run_logged('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'],
          'paths_vs_base': paths, 'checks': results, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def inventory():
    """Run the CI catalog-inventory command on the frozen tree."""
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'inventory-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    results = []
    out = D / 'catalog-inventory-local'
    run_logged('inventory-local.txt', [str(PY), '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                                       '--require-catalog', '--registry-data', 'evas/capabilities/data'], results,
               extra_env={'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']})
    summary = load(out / 'summary.json')
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree']
    write(D / 'inventory-acceptance.json', {'candidate': final['commit'], 'tree': final['tree'], 'checks': results,
          'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
          'command_matches_CI_step': 'python3 -B scripts/capabilities/collect_ci_inventory.py --root . --output runs/catalog-inventory --require-catalog --registry-data evas/capabilities/data',
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count'], 'denominators': summary['denominators']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'capture', 'discover', 'union', 'archive', 'generate', 'derive', 'freeze',
                                          'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

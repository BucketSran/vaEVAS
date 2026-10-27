"""Rebuild PR6 on main 02dee32b: merge, R2 audit fixes, Rust pin (B), derived refresh.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the
private export are writable; the real worktree, index, branch, shared config and 20 old
candidates stay unchanged. No scientific test bodies, simulator or backend run here.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
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
R2 = B / 'pr6/runner-image-tolerance-20261027/r2'
BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
BASE_TREE = 'a68a89e1c145767f830fd5d602ab1be9f96b6b90'
OLD_BASE = 'ac1b6e8d8de743b8da3f862c0f50bdf0a1a1ca14'
PR6 = 'c76cb65f7c260712eb77bc9322bb294ec32287c5'
PR6_TREE = '863e78837993c3116459a91207138da6ef4c9b96'
PR6_EXPORT = B / 'pr6/final-integration-r2-20261027/source'
R3 = B / 'pr6/support-audit-r3-grok-20261027'
RUST = B / 'pr6/rust-pin-b-20261027'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
OBSERVED = R2 / 'ci-40507402194/attempt-1/artifacts/catalog-inventory/assets-before.json'
PREFIX = 'evas/capabilities/observations/pr6-rebind-r3-20261027'
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
task.S, task.OUT, task.BASE = S, D, BASE
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


PR6_CRITERIA_DOCS = {'evas/validation/METHOD_QUALIFICATION.md', 'evas/validation/PROTOCOL.md', 'evas/validation/README.md',
                     'experiments/README.md'}
COMMITS = (('merge', 'Merge main into the PR6 support views after the runner-host fix'),
           ('r3', 'Check every requirement, toolchain source and view label in the Markdown support view'),
           ('rust', 'Pin the CI Rust toolchain to 1.99.1 through RUSTUP_TOOLCHAIN'))


def show(rev, path):
    try:
        return git('show', rev + ':' + path)
    except subprocess.CalledProcessError:
        return None


def pr6_render_outputs():
    sys.path.insert(0, str(PR6_EXPORT / 'evas/capabilities'))
    renderer = module('pr6_head_render', PR6_EXPORT / 'evas/capabilities/render.py')
    reg = renderer.load()
    files = renderer.outputs(renderer.registry(reg), reg)
    sys.path.pop(0)
    return {Path(p).resolve().relative_to(PR6_EXPORT.resolve()).as_posix() for p in files}


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    assert git('rev-parse', PR6 + '^{tree}').decode().strip() == PR6_TREE
    git('merge-base', '--is-ancestor', OLD_BASE, BASE)
    git('merge-base', '--is-ancestor', OLD_BASE, PR6)
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', BASE], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pr6-r3'], cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    pr6_paths = set(git('diff', '--name-only', OLD_BASE, PR6).decode().splitlines())
    main_paths = set(git('diff', '--name-only', OLD_BASE, BASE).decode().splitlines())
    rendered_pr6 = pr6_render_outputs()
    sources = sorted(pr6_paths - rendered_pr6 - DERIVED_DATA)
    entries = task.entries(PR6)
    merged = []
    for path in sources:
        ours = show(PR6, path)
        target = S / path
        if path in main_paths:
            base_raw, theirs = show(OLD_BASE, path), show(BASE, path)
            assert ours is not None and base_raw is not None and theirs is not None, path
            scratch = D / 'merge-file' / path.replace('/', '__')
            scratch.mkdir(parents=True)
            for name, raw in (('ours', ours), ('base', base_raw), ('theirs', theirs)):
                (scratch / name).write_bytes(raw)
            result = subprocess.run(['/usr/bin/git', 'merge-file', '-p', str(scratch / 'ours'), str(scratch / 'base'), str(scratch / 'theirs')],
                                    env=private_env(), capture_output=True)
            assert result.returncode == 0, ('conflict', path)
            raw, how = result.stdout, 'three-way merge of PR6 and main edits'
        else:
            assert ours is not None, path
            raw, how = ours, 'PR6 version (main unchanged since ac1b6e8d)'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if entries[path][0] == '100755' else 0o644)
        merged.append({'path': path, 'sha256': sha(raw), 'resolution': how})
    r3 = load(R3 / 'result.json')
    r3_rows = []
    for row in r3['files']:
        assert sha((S / row['path']).read_bytes()) == row['before_sha256'], row['path']
        raw = (R3 / 'export' / row['path']).read_bytes()
        assert sha(raw) == row['after_sha256'], row['path']
        r3_rows.append(row)
    rust = load(RUST / 'rust-pin-receipt.json')
    for row in rust['files']:
        assert sha((S / row['path']).read_bytes()) == row['before_sha256'], row['path']
        assert sha((RUST / 'dev' / row['path']).read_bytes()) == row['after_sha256'], row['path']
    write(D / 'source-plan.json', {'merge_sources': merged, 'r3': r3_rows, 'rust': rust['files'],
          'pr6_render_outputs': sorted(rendered_pr6), 'main_paths': sorted(main_paths)})
    results = []
    run_logged('pre-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'pr6': PR6, 'pr6_tree': PR6_TREE, 'old_base': OLD_BASE, 'plan': str(D / 'source-plan.json'),
          'merge_sources': len(merged), 'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')],
          'pre_render_checks': results, 'before': before, 'after': after, 'published': False,
          'scientific_execution': False, 'semantic_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'merge_sources': len(merged), 'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')]}), flush=True)


def commit_paths(parent, paths, message, parents=None):
    index = D / 'commit.index'
    assert not index.exists()
    git('read-tree', parent, index=index)
    prior = task.entries(parent)
    for path in paths:
        raw = (S / path).read_bytes()
        mode = prior.get(path, ('100644', None))[0]
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    args = []
    for p in (parents or [parent]):
        args += ['-p', p]
    head = git('commit-tree', tree, *args, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return head, tree


def capture():
    invariant()
    plan = load(D / 'source-plan.json')
    assert not (D / 'capture.json').exists()
    rendered = set(render_outputs())
    merge_paths = sorted({m['path'] for m in plan['merge_sources']} | {p for p in rendered if show(BASE, p) != (S / p).read_bytes()})
    commits = []
    c1, t1 = commit_paths(BASE, merge_paths, COMMITS[0][1], parents=[PR6, BASE])
    commits.append({'kind': 'merge', 'commit': c1, 'tree': t1, 'parents': [PR6, BASE], 'paths': merge_paths})
    for row in plan['r3']:
        (S / row['path']).write_bytes((R3 / 'export' / row['path']).read_bytes())
    c2, t2 = commit_paths(c1, [row['path'] for row in plan['r3']], COMMITS[1][1])
    commits.append({'kind': 'r3', 'commit': c2, 'tree': t2, 'parents': [c1], 'paths': [row['path'] for row in plan['r3']]})
    for row in plan['rust']:
        (S / row['path']).write_bytes((RUST / 'dev' / row['path']).read_bytes())
    c3, t3 = commit_paths(c2, [row['path'] for row in plan['rust']], COMMITS[2][1])
    commits.append({'kind': 'rust', 'commit': c3, 'tree': t3, 'parents': [c2], 'paths': [row['path'] for row in plan['rust']]})
    git('read-tree', c3, source=True)
    git('update-ref', 'HEAD', c3, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    git('merge-base', '--is-ancestor', PR6, c3)
    git('merge-base', '--is-ancestor', BASE, c3)
    paths = sorted(git('diff', '--name-only', BASE, c3).decode().splitlines())
    criteria = sorted(p for p in paths if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in paths if p in COLLECTOR)
    assert set(criteria) == PR6_CRITERIA_DOCS, criteria
    assert collector == ['scripts/ci_evidence.py'], collector
    write(D / 'capture.json', {'base': BASE, 'pr6': PR6, 'commit': c3, 'tree': t3, 'commits': commits, 'paths': paths,
          'criteria_changes': criteria, 'collector_changes': collector, 'non_force_successor_of_PR269': True,
          'scientific_qualification': False})
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, c3))
    (D / 'source.commits').write_text('\n'.join(git('cat-file', 'commit', c['commit']).decode() for c in commits))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(BASE), task.entries(c3)
    assert set(prior) == set(old_rows)
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
    for required in ('evas/capabilities/generated/support.md', 'evas/capabilities/generated/support-facts.json'):
        assert required in after, required
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': c3, 'source_tree': t3, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': rows,
          'reuse_proof': {'actual_CI': 40507402194, 'observation': str(OBSERVED), 'unchanged': len(rows) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'commits': [c['commit'] for c in commits], 'tree': t3, 'paths': len(paths), 'assets': len(rows)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(R2 / 'config.json')
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
    inventory = module('pr6_r3_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(entries) == 31
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
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the main receipts; entries whose start/pattern match a changed path are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def remote_archive():
    line = git('ls-remote', 'origin', ARCHIVE_REF).decode().split()
    assert len(line) == 2 and line[1] == ARCHIVE_REF, line
    return line[0]


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = remote_archive()
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commits', 'discovery-selection.json', 'source-preparation.json', 'source-plan.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_pr6_r3.py')
    shutil.copyfile(RUST / 'rust-pin-receipt.json', dest / 'rust-pin-receipt.json')
    shutil.copyfile(R3 / 'result.json', dest / 'r3-audit-fix-result.json')
    (dest / 'README.md').write_text('# PR6 rebuild on main 02dee32b\n\n'
        'Merge commit (PR6 c76cb65f + main 02dee32b, one three-way doc merge), then the R2 audit fixes '
        '(per-requirement and per-source Markdown checks, view_status and provisional checks) and the Rust pin '
        '(RUSTUP_TOOLCHAIN 1.99.1; scripts no longer name the stable channel) as separate commits, then the derived '
        'refresh. The criteria change comes from the PR6 documents; the collector change comes from the Rust pin '
        '(scripts/ci_evidence.py). Scientific qualification is false.\n')
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive PR6 rebuild construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R2 / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    selection = load(D / 'discovery-selection.json')
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': head, 'path': PREFIX + '/new-discovery/' + path.name}
    old = {e['entry_id']: e for e in load(R2 / 'discovery-selection.json')['entries']}
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
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert 'evas/capabilities/data/language-profile.json' not in paths
    index = load(S / 'evas/capabilities/data/asset-index.json')
    text = json.dumps(index, ensure_ascii=False)
    registered = {p: (p in text) for p in ('evas/capabilities/generated/support.md', 'evas/capabilities/generated/support-facts.json')}
    assert all(registered.values()), registered
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'support_files_registered': registered,
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'objects': report['objects']}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    capture = load(D / 'capture.json')
    paths = changed_vs(BASE)
    rendered = set(render_outputs())
    unexpected = sorted(set(paths) - set(capture['paths']) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    delta = changed_vs(capture['commit'])
    assert set(delta) <= rendered | DERIVED_DATA, sorted(set(delta) - rendered - DERIVED_DATA)
    write(D / 'derive-acceptance.json', {'base': BASE, 'source_capture': capture['commit'], 'paths_vs_base': paths, 'derived_delta': delta,
          'render_outputs': len(rendered), 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_base': len(paths), 'derived_delta': delta}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(cap['commit'])
    final = task.make_commit(cap['commit'], generated, 'Refresh PR6 catalog, traceability and generated views on main 02dee32b' + TRAILER, 'final')
    for ancestor in (PR6, BASE, cap['commit']):
        git('merge-base', '--is-ancestor', ancestor, final['commit'])
    assert sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines()) == sorted(der['paths_vs_base'])
    final.update(base=BASE, pr6=PR6, source_capture=cap['commit'], commits=cap['commits'], complete_paths=der['paths_vs_base'],
                 criteria_changes=cap['criteria_changes'], collector_changes=cap['collector_changes'],
                 derive=str(D / 'derive-acceptance.json'), precheck='runs on the frozen head in parallel with CI',
                 review='Incremental tcodex Astra on c76cb65f..final (merge, R2 fixes, Rust pin) after CI selection and fast-checks pass',
                 CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', PR6, final['commit']))
    git('read-tree', final['commit'], source=True)
    git('update-ref', 'HEAD', final['commit'], source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'paths_vs_base': len(der['paths_vs_base'])}), flush=True)


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
          'focused': False, 'scope': 'Complete PR6 rebuild quick maintenance gate; full scientific regression is CI only.'})
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
    parser.add_argument('stage', choices=['source', 'capture', 'discover', 'archive', 'generate', 'derive', 'freeze', 'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

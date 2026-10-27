"""Merge the new main (catalog part split, #274) into PR6 after review round 5 and regenerate the catalog.

The merge commit joins the reviewed r6 source commit (4751f951, a child of the published PR6 head 340ef10e) with
main 4d6ebc71. Source paths changed only by PR6 take PR6's bytes, paths changed only by main keep main's bytes, and
paths changed by both are merged with git merge-file (a conflict stops the build). Catalog data and derived files
come from main in the merge commit and are then regenerated in the part layout from the union of main's and
340ef10e's catalog objects, twice, byte for byte. The local r6 commit 23f81e68 (its single-file method index
exceeds GitHub's file limit) is not an ancestor of the result.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the private export are
writable; the real worktree, index, branch, shared config and 20 old candidates stay unchanged. No scientific test
bodies, simulator or backend run here.
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
D6 = B / 'pr6/rebind-r6-20261027'
S6 = D6 / 'source'
BASE = '4d6ebc71efea35822a28f2861f2b0a2a6db17e59'
BASE_TREE = '33a1a097624a24d46dda3ec289b1d899280d7e18'
OLD_BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
PR6 = '4751f9519fbc07efba94373e803c39aefe39472b'
PR6_PUBLISHED = '340ef10e723c3fd06058f4d33ffa7dd07a9a3646'
R6_LOCAL = '23f81e68d10e3b4d3a6c324bba2b8d7ff58a6397'
RETENTION_REVS = (('main', BASE), ('old_main', OLD_BASE), ('pr6_published', PR6_PUBLISHED),
                  ('r4_head', '5455ae7b006488902476bba045e9e2971102d8f5'), ('prior_pr6', 'c76cb65f7c260712eb77bc9322bb294ec32287c5'))
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
OBSERVED = D / 'ci-40569530278/catalog-inventory/assets-before.json'
ARCHIVE_PARENT_LOCAL = '5329442b3db87a902b7fa3beb71b1fb3715d5aea'
ARCHIVE_REMOTE_EXPECTED = '5e6b81e788530cce267c5703882b0b463c0acfe2'
UNION = D / 'previous-union'
PREFIX = 'evas/capabilities/observations/pr6-main-merge-r7-20261027'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DATA = 'evas/capabilities/data/'
RETIRED = (DATA + 'historical-index.json', DATA + 'method-index.json')
PART_FILES = tuple([DATA + 'method-index-%02d.json' % i for i in range(16)] + [DATA + 'historical-index-%02d.json' % i for i in range(16)])
DERIVED_DATA = {DATA + 'registry.json', DATA + 'catalog-sources.json', DATA + 'asset-index.json', DATA + 'entrypoint-index.json',
                *PART_FILES, *RETIRED, 'evas/docs/development/TRACEABILITY.md'}
WARNING_BYTES = 50 * 1024 * 1024
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
             'scripts/regression_observation_policy.json', 'evas/capabilities/data/language-profile.json')
PR6_CRITERIA_DOCS = {'evas/validation/METHOD_QUALIFICATION.md', 'evas/validation/PROTOCOL.md', 'evas/validation/README.md', 'experiments/README.md'}
AFFECTED_TESTS = ('test_catalog_part_split.py', 'test_discover_rust.py', 'test_rust_catalog_reconcile.py', 'test_ci_evidence_v3.py',
                  'test_regression_runner.py', 'test_regression_admission.py', 'test_ci_selection.py', 'test_ci_inventory.py',
                  'test_fast_feedback.py', 'test_catalog_derived_outputs.py', 'test_catalog_history_selection.py',
                  'test_regression_gate.py', 'test_trusted_regression_gate.py', 'test_context_registration.py')
MERGE_MESSAGE = 'Merge main (catalog part split) into the PR6 support views'
FINAL_MESSAGE = 'Regenerate the PR6 catalog in the part layout, keeping every object version of both parents'
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


def names(a, b):
    return set(git('diff', '--name-only', a, b).decode().splitlines())


def show(rev, path):
    try:
        return git('show', rev + ':' + path)
    except subprocess.CalledProcessError:
        return None


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


def render_outputs(root):
    sys.path.insert(0, str(root / 'evas/capabilities'))
    try:
        renderer = module('r7_render_' + hashlib.sha1(str(root).encode()).hexdigest()[:8], root / 'evas/capabilities/render.py')
        files = renderer.outputs(renderer.registry())
    finally:
        sys.path.pop(0)
    return sorted(Path(p).resolve().relative_to(root.resolve()).as_posix() for p in files)


def objects_at(rev):
    header = json.loads(git('show', rev + ':' + DATA + 'registry.json'))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(git('show', rev + ':' + DATA + part))['objects']
    return {(item['id'], item['version']): item for item in result}


def hunks(diff_text):
    """Diff body lines without hunk positions, so the same change at shifted lines compares equal."""
    return [line for line in diff_text.splitlines() if line[:1] in '+- ' and not line.startswith(('+++', '---'))]


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    for anc, desc in ((OLD_BASE, BASE), (OLD_BASE, PR6), (PR6_PUBLISHED, PR6)):
        git('merge-base', '--is-ancestor', anc, desc)
    assert git('merge-base', PR6, BASE).decode().strip() == OLD_BASE
    assert git('rev-parse', PR6 + '^').decode().strip() == PR6_PUBLISHED
    assert git('rev-parse', R6_LOCAL + '^').decode().strip() == PR6
    assert S6.is_dir()
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', BASE], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pr6-r7'], cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    pr6_paths = names(OLD_BASE, PR6)
    main_paths = names(OLD_BASE, BASE)
    rendered_pr6 = set(render_outputs(S6))
    sources = sorted(pr6_paths - rendered_pr6 - DERIVED_DATA)
    entries = task.entries(PR6)
    merged = []
    for path in sources:
        ours = show(PR6, path)
        assert ours is not None, ('PR6 deletes ' + path)
        target = S / path
        if path in main_paths:
            base_raw, theirs = show(OLD_BASE, path), show(BASE, path)
            assert base_raw is not None and theirs is not None, path
            scratch = D / 'merge-file' / path.replace('/', '__')
            scratch.mkdir(parents=True)
            for name, raw in (('ours', ours), ('base', base_raw), ('theirs', theirs)):
                (scratch / name).write_bytes(raw)
            result = subprocess.run(['/usr/bin/git', 'merge-file', '-p', str(scratch / 'ours'), str(scratch / 'base'), str(scratch / 'theirs')],
                                    env=private_env(), capture_output=True)
            assert result.returncode == 0, ('conflict: needs manual resolution and a small priority review', path)
            raw, how = result.stdout, 'three-way merge of PR6 and main edits'
        else:
            raw, how = ours, 'PR6 version (main unchanged since 02dee32b)'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        target.chmod(0o755 if entries[path][0] == '100755' else 0o644)
        merged.append({'path': path, 'sha256': sha(raw), 'resolution': how})
    write(D / 'source-plan.json', {'pr6': PR6, 'base': BASE, 'old_base': OLD_BASE, 'merge_sources': merged,
          'pr6_render_outputs': sorted(rendered_pr6), 'main_paths': sorted(main_paths), 'pr6_paths': sorted(pr6_paths)})
    results = []
    run_logged('pre-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'pr6': PR6, 'pr6_published': PR6_PUBLISHED, 'old_base': OLD_BASE, 'r6_local_not_ancestor': R6_LOCAL,
          'plan': str(D / 'source-plan.json'), 'merge_sources': len(merged),
          'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')],
          'pre_render_checks': results, 'before': before, 'after': after, 'published': False,
          'scientific_execution': False, 'semantic_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'merge_sources': len(merged), 'three_way': [m['path'] for m in merged if m['resolution'].startswith('three-way')]}), flush=True)


def commit_merge(paths, message, parents):
    index = D / 'merge.index'
    assert not index.exists()
    git('read-tree', BASE, index=index)
    prior = task.entries(PR6)
    for path in paths:
        raw = (S / path).read_bytes()
        mode = prior.get(path, task.entries(BASE).get(path, ('100644', None)))[0]
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    args = []
    for p in parents:
        args += ['-p', p]
    head = git('commit-tree', tree, *args, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return head, tree


def capture():
    invariant()
    plan = load(D / 'source-plan.json')
    assert not (D / 'capture.json').exists()
    rendered = set(render_outputs(S))
    merge_paths = sorted({m['path'] for m in plan['merge_sources']} | {p for p in rendered if show(BASE, p) != (S / p).read_bytes()})
    head, tree = commit_merge(merge_paths, MERGE_MESSAGE, [PR6, BASE])
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    git('merge-base', '--is-ancestor', PR6, head)
    git('merge-base', '--is-ancestor', BASE, head)
    # Source equality receipt: the merged code is the reviewed code.
    pr6_paths, main_paths = set(plan['pr6_paths']), set(plan['main_paths'])
    rows, problems = [], []
    for path in sorted((pr6_paths | main_paths) - DERIVED_DATA - set(plan['pr6_render_outputs'])):
        got = show(head, path)
        if path in pr6_paths and path not in main_paths:
            expected, kind = show(PR6, path), 'pr6-only: equals reviewed PR6 r6 source'
        elif path in main_paths and path not in pr6_paths:
            expected, kind = show(BASE, path), 'main-only: equals main'
        else:
            assert any(m['path'] == path and m['resolution'].startswith('three-way') for m in plan['merge_sources']), path
            expected, kind = (S / path).read_bytes(), 'both: three-way merge'
            vs_base = git('diff', BASE, head, '--', path).decode()
            vs_pr6 = git('diff', PR6, head, '--', path).decode()
            pr6_change = git('diff', OLD_BASE, PR6, '--', path).decode()
            main_change = git('diff', OLD_BASE, BASE, '--', path).decode()
            both = {'merged_vs_main_equals_pr6_change': hunks(vs_base) == hunks(pr6_change),
                    'merged_vs_pr6_equals_main_change': hunks(vs_pr6) == hunks(main_change)}
            (D / 'merge-diffs').mkdir(exist_ok=True)
            for name, text in (('vs-main', vs_base), ('vs-pr6', vs_pr6), ('pr6-change', pr6_change), ('main-change', main_change)):
                (D / 'merge-diffs' / (path.replace('/', '__') + '.' + name + '.diff')).write_text(text)
            if not all(both.values()):
                problems.append({'path': path, **both})
            kind += ' ' + json.dumps(both)
        ok = got == expected
        if not ok:
            problems.append({'path': path, 'kind': kind, 'ok': False})
        rows.append({'path': path, 'kind': kind, 'sha256': sha(got) if got is not None else None, 'equal': ok})
    assert not problems, problems
    # The reviewed r6 increment (340ef10e -> 4751f951) is present unchanged except where main also changed the file.
    r6_paths = sorted(names(PR6_PUBLISHED, PR6))
    r6_rows = [{'path': p, 'equal_to_reviewed': show(head, p) == show(PR6, p), 'also_changed_by_main': p in main_paths} for p in r6_paths]
    assert all(r['equal_to_reviewed'] or r['also_changed_by_main'] for r in r6_rows), r6_rows
    criteria = sorted(p for p in names(BASE, head) if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in names(BASE, head) if p in COLLECTOR)
    assert set(criteria) == PR6_CRITERIA_DOCS, criteria
    assert collector == ['scripts/ci_evidence.py'], collector
    write(D / 'source-equality.json', {'merge_commit': head, 'tree': tree, 'parents': [PR6, BASE], 'rows': rows, 'r6_increment': r6_rows,
          'criteria_changes_vs_main': criteria, 'collector_changes_vs_main': collector, 'problems': problems})
    write(D / 'capture.json', {'base': BASE, 'pr6': PR6, 'commit': head, 'tree': tree, 'parents': [PR6, BASE], 'paths': merge_paths,
          'criteria_changes': criteria, 'collector_changes': collector, 'non_force_successor_of_PR269': True, 'scientific_qualification': False})
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, head, '--', *merge_paths))
    (D / 'source.commit').write_bytes(git('cat-file', 'commit', head))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(BASE), task.entries(head)
    assert set(prior) == set(old_rows)
    out, changed = [], []
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
        out.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual_mode, 'git_blob_oid': oid})
    assert sorted(changed) == sorted(names(BASE, head))
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': head, 'source_tree': tree, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': out,
          'reuse_proof': {'actual_CI': 40569530278, 'observation': str(OBSERVED), 'unchanged': len(out) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'merge': head, 'tree': tree, 'paths': len(merge_paths), 'assets': len(out), 'source_rows': len(rows)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(D6 / 'config.json')
    candidates = {}
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    cap = load(D / 'capture.json')
    changed_paths = sorted(names(R6_LOCAL, cap['commit']) - DERIVED_DATA)
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = cap['commit']
    inventory = module('r7_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
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
            git('merge-base', '--is-ancestor', locator['revision'], ARCHIVE_PARENT_LOCAL)
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
          'new_collections': new_count, 'changed_paths_vs_r6_local': changed_paths,
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the r6 receipts (archived in 5329442b, published with this build); entries whose start/pattern match a path main changed are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def union():
    """Previous catalog for generation: main's part-layout catalog plus every 340ef10e object it lacks."""
    invariant()
    assert not UNION.exists() and not (D / 'union-acceptance.json').exists()
    data = S / 'evas/capabilities/data'
    shutil.copytree(data, UNION)
    for path in RETIRED:
        assert not (UNION / Path(path).name).exists(), path
    writer = module('r7_union_writer', S / 'scripts/capabilities/generate_catalog.py')
    header = load(UNION / 'registry.json')
    present = task.objects(UNION)
    assert present == objects_at(BASE)
    docs = {name: load(UNION / name) for name in header['object_parts']}
    kind_file = {'sources': 'catalog-sources.json', 'assets': 'asset-index.json', 'entrypoints': 'entrypoint-index.json'}
    added, conflicts, by_part = [], [], {}
    pr6_header = json.loads(git('show', PR6_PUBLISHED + ':' + DATA + 'registry.json'))
    pr6_parts = {'registry.json': pr6_header['objects']}
    for part in pr6_header['object_parts']:
        doc = json.loads(git('show', PR6_PUBLISHED + ':' + DATA + part))
        pr6_parts[part] = (doc['kind'], doc['objects'])
    header_objects = list(header['objects'])
    for part, value in pr6_parts.items():
        kind, items = (None, value) if part == 'registry.json' else value
        for obj in items:
            key = (obj['id'], obj['version'])
            if key in present:
                if present[key] != obj:
                    conflicts.append(list(key))
                continue
            if part == 'registry.json':
                header_objects.append(obj); target = 'registry.json'
            else:
                target = writer.part_file(kind, obj['id']) if kind in ('methods', 'history') else kind_file[kind]
                docs[target]['objects'].append(obj)
            present[key] = obj
            added.append({'part': target, 'id': obj['id'], 'version': obj['version']})
            by_part[target] = by_part.get(target, 0) + 1
    assert not conflicts, conflicts[:5]
    header['objects'] = header_objects
    (UNION / 'registry.json').write_text(json.dumps(header, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    for name, doc in docs.items():
        (UNION / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    merged = task.objects(UNION)
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
    sys.path.insert(0, str(S / 'evas/capabilities'))
    registry = module('r7_registry', S / 'evas/capabilities/registry.py')
    before = registry.load(data, root=S, repositories={'vaevas': S})
    candidate = copy.deepcopy(before.data)
    # attempt-r1 recomputed task.objects(data) for every object (re-parsing the whole catalog each time) and was stopped.
    base_keys = set(task.objects(data))
    candidate['objects'].extend(copy.deepcopy(obj) for key, obj in merged.items() if key not in base_keys)
    after = registry.Registry(candidate, root=S, repositories={'vaevas': S})
    assert after.data['current'] == before.data['current']
    write(D / 'union-acceptance.json', {'base': BASE, 'pr6_published': PR6_PUBLISHED, 'union_dir': str(UNION),
          'base_objects': len(objects_at(BASE)), 'added_from_pr6': len(added), 'added_by_part': by_part, 'conflicts': conflicts,
          'union_objects': len(merged), 'retention_revisions': [r for _, r in RETENTION_REVS], 'registry_validation_passed': True,
          'current_unchanged': True, 'added': added, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'added_from_pr6': len(added), 'added_by_part': by_part, 'union_objects': len(merged)}), flush=True)


def remote_archive():
    line = git('ls-remote', 'origin', ARCHIVE_REF).decode().split()
    assert len(line) == 2 and line[1] == ARCHIVE_REF, line
    return line[0]


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    assert remote_archive() == ARCHIVE_REMOTE_EXPECTED
    assert git('rev-parse', ARCHIVE_PARENT_LOCAL + '^').decode().strip() == ARCHIVE_REMOTE_EXPECTED
    parent = ARCHIVE_PARENT_LOCAL
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'source-plan.json', 'source-equality.json', 'discovery-selection.json',
                 'source-preparation.json', 'union-acceptance.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    if (D / 'merge-diffs').exists():
        shutil.copytree(D / 'merge-diffs', dest / 'merge-diffs')
    shutil.copyfile(__file__, dest / 'prepare_pr6_r7.py')
    (dest / 'README.md').write_text('# PR6 merge of main after the catalog part split\n\n'
        'The merge commit joins the reviewed r6 source commit 4751f951 with main 4d6ebc71 (#274). PR6-only source paths '
        'keep the reviewed bytes, main-only paths keep main, and paths both changed are a clean three-way merge listed with '
        'their diffs against both parents. The catalog is regenerated in the part layout from the union of both parents. '
        'The parent of this archive commit is the r6 construction archive 5329442b, so the r6 discovery receipts that this '
        'build reuses are published with it. Scientific qualification is false.\n')
    idx = D / 'archive.index'
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive PR6 main merge construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'remote_parent': ARCHIVE_REMOTE_EXPECTED, 'commit': head, 'tree': tree, 'prefix': PREFIX,
          'files': files, 'published': False})
    config = load(D6 / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(UNION),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    selection = load(D / 'discovery-selection.json')
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': head, 'path': PREFIX + '/new-discovery/' + path.name}
    new_ids = {e['entry_id'] for e in selection['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= new_ids, bridge['path']
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'archive': head, 'parent': parent, 'files': len(files)}), flush=True)


def generate():
    """Generate twice from the same inputs; the two outputs must be byte-identical."""
    invariant()
    assert load(D / 'config.json')['previous_data_dir'] == str(UNION)
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
    previous, current = task.objects(UNION), task.objects(first)
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    header = load(first / 'registry.json')
    versions = {}
    for (i, v) in current:
        versions.setdefault(i, []).append(v)
    prev_versions = {}
    for (i, v) in previous:
        prev_versions.setdefault(i, []).append(v)
    version_problems = []
    for i, vs in versions.items():
        old = set(prev_versions.get(i, []))
        new = set(vs) - old
        if len(new) > 1 or (new and header['current'].get(i) not in new):
            version_problems.append({'id': i, 'new_versions': sorted(new), 'current': header['current'].get(i)})
        if i in header['current'] and header['current'][i] not in vs:
            version_problems.append({'id': i, 'current_missing': header['current'][i]})
    assert not version_problems, version_problems[:5]
    for name in ('historical-index.json', 'method-index.json'):
        assert not (first / name).exists(), name
    paths = []
    for p in sorted(first.glob('*.json')):
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
          'deterministic_double_generation': True, 'version_lists': {'ids': len(versions), 'problems': 0,
          'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
          'largest_data_file': max(sizes.items(), key=lambda x: x[1]), 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'objects': report['objects'],
                      'largest': max(sizes.items(), key=lambda x: x[1])}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    cap = load(D / 'capture.json')
    paths = changed_vs(cap['commit'])
    rendered = set(render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'merge_commit': cap['commit'], 'paths_vs_merge': paths, 'render_outputs': len(rendered),
          'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_merge': len(paths)}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(cap['commit'])
    assert sorted(generated) == sorted(der['paths_vs_merge'])
    final = task.make_commit(cap['commit'], generated, FINAL_MESSAGE + TRAILER, 'final')
    for anc in (PR6_PUBLISHED, PR6, BASE, cap['commit']):
        git('merge-base', '--is-ancestor', anc, final['commit'])
    assert subprocess.run(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), 'merge-base', '--is-ancestor', R6_LOCAL, final['commit']],
                          env=env()).returncode == 1, 'the oversized local r6 commit must not be an ancestor'
    complete = sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines())
    criteria = sorted(p for p in complete if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in complete if p in COLLECTOR)
    assert set(criteria) == PR6_CRITERIA_DOCS and collector == ['scripts/ci_evidence.py'], (criteria, collector)
    # attempt-r1 asserted on every large blob and stopped on the unchanged trusted baseline (89.9 MB, already on main);
    # the size condition covers what this head changes, and every large unchanged blob is listed.
    blobs, changed = [], set(complete)
    for line in git('ls-tree', '-r', '-l', final['commit']).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final.update(base=BASE, merge_commit=cap['commit'], pr6=PR6, pr6_published=PR6_PUBLISHED, complete_paths=complete,
                 criteria_changes=criteria, collector_changes=collector, derive=str(D / 'derive-acceptance.json'),
                 source_equality=str(D / 'source-equality.json'), r6_local_not_ancestor=R6_LOCAL, large_unchanged_blobs=blobs,
                 precheck='runs on the frozen head in parallel with CI', review='r5 covers the r6 source; merge and regeneration verified by receipts',
                 CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch.identity.json').write_text(json.dumps({'base': BASE, 'head': final['commit'], 'command': 'git diff --binary <base> <head>'}, indent=2) + '\n')
    git('read-tree', final['commit'], source=True)
    git('update-ref', 'HEAD', final['commit'], source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'complete_paths': len(complete)}), flush=True)


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
          'focused': False, 'scope': 'PR6 after the main merge, quick maintenance gate; full scientific regression is CI only.'})
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

"""Bind the prepared PR6 composition to accepted PR5 main and freeze a complete candidate.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and
the private export are writable; the real worktree, index, branch, shared config and 20 old
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
P5 = B / 'pr5/context-registration-20261027'
REBIND = P5 / 'pr266-rebind-20261027'
PREVIEW = B / 'pr6/integration-preview-on-pr5-20261027'
BASE = 'ac1b6e8d8de743b8da3f862c0f50bdf0a1a1ca14'
BASE_TREE = '1b83f28af63dbaddc60fea500309f19962e7f947'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
OBSERVED = REBIND / 'ci-40473087175/artifacts/catalog-inventory/assets-before.json'
PREFIX = 'evas/capabilities/observations/pr6-support-views-20261027'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
PATCHES = [
    ('support-view-binding-fix-grok-20261027', 'aaf946299b8364648c8c1c1d4332bfeb5d0579a5337cf87f8e208978c8304573'),
    ('view-consumers-grok-20261027', '5f2f87f91cd4d181e2f05a3974db2a69e51a3145032eb0e54efe9a1dfc650e7e'),
    ('catalog-flow-completion-grok-20261027', 'f57e438a8cc7d7d7acd1933d28fdf7be7e71ef87b73ffb59a4d4834798c9b063'),
]
DERIVED_DATA = {
    'evas/capabilities/data/asset-index.json', 'evas/capabilities/data/catalog-sources.json',
    'evas/capabilities/data/entrypoint-index.json', 'evas/capabilities/data/historical-index.json',
    'evas/capabilities/data/method-index.json', 'evas/capabilities/data/registry.json',
    'evas/docs/development/TRACEABILITY.md',
}
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


def invariant():
    guard()
    assert Path(git('rev-parse', '--absolute-git-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--git-common-dir', source=True).decode().strip()).resolve() == S / '.git'
    assert Path(git('rev-parse', '--show-toplevel', source=True).decode().strip()).resolve() == S
    assert S.resolve().is_relative_to(D.resolve())


def private_git(*args):
    # git apply resolves patch paths against the current directory, so run inside the export.
    e = env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0'}
    return subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), *args], cwd=S, env=e, capture_output=True)


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    act = load(REBIND / 'merge-20261027/merge-verification.json')
    assert act['merge_commit'] == BASE and act['tree'] == BASE_TREE
    comp = load(PREVIEW / 'composition.json')
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', BASE], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    assert not (S / '.git').exists()
    p = private_git('init', '--quiet', '--template=', '--initial-branch=pr6-final')
    assert p.returncode == 0, p.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    applied = []
    for i, (name, digest) in enumerate(PATCHES):
        patch = B / 'pr6' / name / 'source.patch'
        assert sha(patch.read_bytes()) == digest
        for mode in ('check', 'apply'):
            argv = ['apply', '--check', str(patch)] if mode == 'check' else ['apply', str(patch)]
            r = private_git(*argv)
            (D / f'patch-{i}-{mode}.stdout').write_bytes(r.stdout)
            (D / f'patch-{i}-{mode}.stderr').write_bytes(r.stderr)
            assert r.returncode == 0, (name, mode, r.stderr.decode())
        applied.append({'name': name, 'sha256': digest})
    paths = set(comp['paths'])
    git('add', '--intent-to-add', '--', *sorted(paths), source=True)
    actual = set(git('diff', '--name-only', BASE, source=True).decode().splitlines())
    assert actual == paths, sorted(actual ^ paths)
    for path, digest in comp['files'].items():
        assert sha((S / path).read_bytes()) == digest, path
    main_since_preview = set(git('diff', '--name-only', comp['base'], BASE).decode().splitlines())
    assert not main_since_preview & paths
    git('reset', '--quiet', source=True)
    new_files = sorted(p for p in paths if not git('ls-tree', BASE, '--', p).strip())
    after = guard()
    assert {k: v for k, v in before.items() if not k.startswith('shared_config_')} == {k: v for k, v in after.items() if not k.startswith('shared_config_')}
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'patches': applied, 'paths': sorted(paths), 'new_files': new_files, 'files': comp['files'],
          'composition_identical_to_preview': True, 'preview': str(PREVIEW / 'composition.json'),
          'main_changes_since_preview_base_overlap': [], 'before': before, 'after': after,
          'published': False, 'scientific_execution': False, 'semantic_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'paths': len(paths), 'new_files': new_files, 'composition_identical_to_preview': True}), flush=True)


def capture():
    invariant()
    prep = load(D / 'source-preparation.json')
    assert not (D / 'capture.json').exists()
    paths = prep['paths']
    actual = set(git('diff', '--name-only', source=True).decode().splitlines()) | set(git('ls-files', '--others', '--exclude-standard', source=True).decode().splitlines())
    assert actual == set(paths), sorted(actual ^ set(paths))
    index = D / 'capture.index'
    assert not index.exists()
    git('read-tree', BASE, index=index)
    prior = task.entries(BASE)
    files = {}
    for path in paths:
        raw = (S / path).read_bytes()
        assert sha(raw) == prep['files'][path]
        mode = prior.get(path, ('100644', None))[0]
        assert (S / path).stat().st_mode & 0o777 == (0o755 if mode == '100755' else 0o644), path
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
        files[path] = sha(raw)
    tree = git('write-tree', index=index).decode().strip()
    head = git('commit-tree', tree, '-p', BASE, '-m', 'Switch current support views and unify the daily validation workflow' + TRAILER).decode().strip()
    index.unlink()
    assert set(git('diff', '--name-only', BASE, head).decode().splitlines()) == set(paths)
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, BASE, source=True)
    write(D / 'capture.json', {'base': BASE, 'commit': head, 'tree': tree, 'parents': [BASE], 'paths': paths, 'files': files,
          'scientific_qualification': False})
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, head))
    (D / 'source.commit').write_bytes(git('cat-file', 'commit', head))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    after = task.entries(head)
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
    assert sorted(changed) == sorted(paths)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': head, 'source_tree': tree, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': rows,
          'reuse_proof': {'actual_CI': 40473087175, 'verification': str(REBIND / 'ci-40473087175/raw-verification.json'),
                          'unchanged': len(rows) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'capture': head, 'tree': tree, 'paths': len(paths), 'assets': len(rows)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(REBIND / 'config.json')
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
    inventory = module('pr6_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
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
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes; entries whose start/pattern match a changed or new path are always recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = load(P5 / 'batch5-accepted-evidence-archive.json')['commit']
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'discovery-selection.json', 'source-preparation.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_pr6.py')
    (dest / 'README.md').write_text('# PR6 support views and daily workflow construction\n\n'
        'Three prepared PR6 patches are applied unchanged to accepted PR5 main ac1b6e8d; the composed 22 files equal the earlier '
        'reviewed-by-primary preview byte for byte. Changed TestLoader entries are recollected, unchanged ones reuse exact receipts. '
        'No scientific test bodies or simulator run here. Catalog generation, precheck, CI, independent review and the context '
        'registration required by changed criteria documents remain separate. Scientific qualification is false.\n')
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive PR6 support-view construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(REBIND / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    script_entries = []
    for row in load(D / 'discovery-selection.json')['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': head, 'path': PREFIX + '/new-discovery/' + path.name}
        if row['start'] == 'scripts/tests' and row['pattern'] == 'test*.py':
            script_entries.append(row['entry_id'])
    assert len(script_entries) == 1
    for bridge in config['bridge_evidence']:
        bridge['consumer_entry_ids'] = script_entries
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
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'objects': report['objects']}), flush=True)


def render_outputs():
    # The exact set render.py writes and --check compares, taken from the candidate's own renderer.
    sys.path.insert(0, str(S / 'evas/capabilities'))
    renderer = module('pr6_render_outputs', S / 'evas/capabilities/render.py')
    reg = renderer.load()
    files = renderer.outputs(renderer.registry(reg), reg)
    return sorted(Path(p).resolve().relative_to(S.resolve()).as_posix() for p in files)


def precheck():
    invariant()
    assert not (D / 'precheck-acceptance.json').exists()
    results = []
    e = env() | {'CARGO_TARGET_DIR': str(B / 'pr4/bootstrap-integration-20261026/precheck-rust-target')}

    def run(name, argv, cwd=S):
        start = datetime.now(timezone.utc).isoformat()
        with (D / name).open('x') as out:
            out.write('COMMAND ' + repr(argv) + '\n')
            out.flush()
            r = subprocess.run(argv, cwd=cwd, env=e, stdout=out, stderr=subprocess.STDOUT)
            out.write('\nreturncode=' + str(r.returncode) + '\n')
        results.append({'command': argv, 'cwd': str(cwd), 'receipt': str(D / name), 'returncode': r.returncode,
                        'started_at_utc': start, 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
        print(name, r.returncode, flush=True)
        assert r.returncode == 0, name

    run('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'])
    run('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'])
    git('add', '--intent-to-add', '--', '.', source=True)
    paths = git('diff', '--name-only', BASE, source=True).decode().splitlines()
    git('reset', '--quiet', source=True)
    composition = set(load(D / 'capture.json')['paths'])
    derived = sorted(set(paths) - composition)
    rendered = render_outputs()
    assert all(p in DERIVED_DATA or p in rendered for p in derived), sorted(set(derived) - DERIVED_DATA - set(rendered))
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths),
          'focused': False, 'scope': 'Complete PR6 quick maintenance gate; full scientific regression is CI only.'})
    run('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')])
    run('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'])
    run('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'])
    for name in ('test_catalog_derived_outputs.py', 'test_ci_selection.py', 'test_ci_inventory.py', 'test_catalog_history_selection.py'):
        run('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'])
    drill_module = module('pr6_path_drill', B / 'pr6/catalog-flow-completion-grok-20261027/verify.py')
    drill = drill_module.drill(S)
    write(D / 'path-drill.json', drill)
    assert not drill['errors'] and len(drill['rows']) == 9
    run('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE])
    write(D / 'precheck-acceptance.json', {'base': BASE, 'source_capture': load(D / 'capture.json')['commit'],
          'paths': paths, 'derived_paths': derived, 'render_outputs': len(rendered),
          'derived_classes': {'catalog_and_traceability': sorted(set(derived) & DERIVED_DATA), 'render_outputs_changed': sorted(set(derived) & set(rendered))},
          'checks': results, 'path_drill': str(D / 'path-drill.json'), 'path_drill_rows': 9,
          'files': {p: sha((S / p).read_bytes()) for p in paths}, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def freeze():
    invariant()
    cap, pre = load(D / 'capture.json'), load(D / 'precheck-acceptance.json')
    assert all(row['returncode'] == 0 for row in pre['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in pre['files'].items())
    git('add', '--intent-to-add', '--', '.', source=True)
    generated = git('diff', '--name-only', cap['commit'], source=True).decode().splitlines()
    git('reset', '--quiet', source=True)
    assert set(generated) == set(pre['derived_paths']), sorted(set(generated) ^ set(pre['derived_paths']))
    final = task.make_commit(cap['commit'], generated, 'Refresh PR6 catalog, traceability and generated support views' + TRAILER, 'final')
    git('merge-base', '--is-ancestor', BASE, final['commit'])
    assert sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines()) == sorted(pre['paths'])
    final.update(base=BASE, source_capture=cap['commit'], complete_paths=pre['paths'], precheck=str(D / 'precheck-acceptance.json'),
                 review='Fresh independent Astra Standards/Spec required', CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', BASE, final['commit']))
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'paths': len(pre['paths']), 'CI': 'pending'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'capture', 'discover', 'archive', 'generate', 'precheck', 'freeze'])
    globals()[parser.parse_args().stage]()

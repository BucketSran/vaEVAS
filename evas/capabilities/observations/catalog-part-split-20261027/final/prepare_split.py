"""Build the catalog part-split maintenance PR on main 02dee32b.

The writer (scripts/capabilities/generate_catalog.py) stores methods and history objects in 16 part files
each, chosen by a stable hash of the object id; readers are unchanged. The source commit carries the writer,
its test and README patch, and retires the two monolithic index files from Git. The files stay on disk only
while the generator's initial load reads the old layout, so the asset receipt never lists them. The derived
commit holds the regenerated catalog. A control generation with main's own writer on the same input tree
proves that only the layout changed.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the private export
are writable; the real worktree, index, branch, shared config and 20 old candidates stay unchanged. No
scientific test bodies, simulator or backend run here.
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
B = D.parent
S = D / 'source'
W4 = B / 'catalog-split-grok-20261027'
R2 = B / 'pr6/runner-image-tolerance-20261027/r2'
BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
BASE_TREE = 'a68a89e1c145767f830fd5d602ab1be9f96b6b90'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
PATCH = W4 / 'source.patch'
OBSERVED = R2 / 'ci-40507402194/attempt-1/artifacts/catalog-inventory/assets-before.json'
MAIN_WRITER = W4 / 'main-export/scripts/capabilities/generate_catalog.py'
EQUIVALENCE = W4 / 'check_split_equivalence.py'
DATA = 'evas/capabilities/data/'
RETIRED = (DATA + 'historical-index.json', DATA + 'method-index.json')
PART_FILES = tuple([DATA + 'method-index-%02d.json' % i for i in range(16)] + [DATA + 'historical-index-%02d.json' % i for i in range(16)])
DERIVED_DATA = {DATA + 'registry.json', DATA + 'catalog-sources.json', DATA + 'asset-index.json', DATA + 'entrypoint-index.json',
                *PART_FILES, 'evas/docs/development/TRACEABILITY.md'}
PREFIX = 'evas/capabilities/observations/catalog-part-split-20261027'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
SOURCE_MESSAGE = 'Split catalog method and history objects into fixed part files'
FINAL_MESSAGE = 'Regenerate the catalog in the part-file layout'
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
FORBIDDEN_PREFIXES = CRITERIA_PREFIXES + ('evas/src/', 'evas/rust_core/', '.github/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
             'scripts/regression_observation_policy.json', 'evas/capabilities/data/language-profile.json')
AFFECTED_TESTS = ('test_catalog_part_split.py', 'test_catalog_history_selection.py', 'test_ci_inventory.py', 'test_ci_selection.py',
                  'test_fast_feedback.py', 'test_rust_catalog_reconcile.py', 'test_discover_rust.py', 'test_context_registration.py')
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
    renderer = module('split_render_outputs', S / 'evas/capabilities/render.py')
    files = renderer.outputs(renderer.registry())
    return sorted(Path(p).resolve().relative_to(S.resolve()).as_posix() for p in files)


def objects_at(rev):
    header = json.loads(git('show', rev + ':' + DATA + 'registry.json'))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(git('show', rev + ':' + DATA + part))['objects']
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
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    acceptance = load(B / 'catalog-split-verification-20261027/split-acceptance.json')
    assert acceptance['patch_sha256'] == sha(PATCH.read_bytes()), 'patch differs from the accepted delivery'
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', BASE], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=catalog-part-split'], cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    paths = patch_paths(PATCH)
    assert not any(p.startswith(FORBIDDEN_PREFIXES) or p in COLLECTOR or p in DERIVED_DATA or p in RETIRED for p in paths), paths
    before_files = {p: sha((S / p).read_bytes()) if (S / p).exists() else None for p in paths}
    applied = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'apply', str(PATCH)],
                             cwd=S, env=private_env(), capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr
    results = []
    run_logged('pre-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    changed = changed_vs(BASE)
    assert set(changed) == set(paths), sorted(set(changed) ^ set(paths))
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'patch': str(PATCH), 'patch_sha256': sha(PATCH.read_bytes()), 'paths': sorted(paths), 'retired': list(RETIRED),
          'files': {p: {'before': before_files[p], 'after': sha((S / p).read_bytes())} for p in paths},
          'pre_render_checks': results, 'criteria_dut_collector_workflow_unchanged': True,
          'before': before, 'after': after, 'published': False, 'scientific_execution': False, 'semantic_qualification': False,
          'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'paths': sorted(paths)}), flush=True)


def capture():
    invariant()
    prep = load(D / 'source-preparation.json')
    assert not (D / 'capture.json').exists()
    paths = prep['paths']
    index = D / 'capture.index'
    assert not index.exists()
    git('read-tree', BASE, index=index)
    prior = task.entries(BASE)
    files = {}
    for path in paths:
        raw = (S / path).read_bytes()
        mode = prior.get(path, ('100644', None))[0]
        assert (S / path).stat().st_mode & 0o777 == (0o755 if mode == '100755' else 0o644), path
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
        files[path] = sha(raw)
    for path in RETIRED:
        assert path in prior, path
        git('update-index', '--force-remove', '--', path, index=index)
    tree = git('write-tree', index=index).decode().strip()
    head = git('commit-tree', tree, '-p', BASE, '-m', SOURCE_MESSAGE + '\n\nThe two monolithic index files are retired here; the next commit regenerates the catalog in the part layout.' + TRAILER).decode().strip()
    index.unlink()
    assert sorted(git('diff', '--name-only', BASE, head).decode().splitlines()) == sorted(paths + list(RETIRED))
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, BASE, source=True)
    for path in RETIRED:
        assert (S / path).is_file(), path
    write(D / 'capture.json', {'base': BASE, 'commit': head, 'tree': tree, 'parents': [BASE], 'paths': paths, 'retired': list(RETIRED),
          'files': files, 'retired_files_on_disk_until_generation': True, 'scientific_qualification': False})
    # The retired monoliths (about 115 MB) would make a full binary diff exceed GitHub's file limit in the evidence
    # archive (build r2 was rejected for that), so the archived patch covers the source paths and the deletions are
    # recorded by path, blob and hash.
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, head, '--', *paths))
    write(D / 'source-retired.json', {'base': BASE, 'commit': head, 'retired': [
        {'path': path, 'git_mode': prior[path][0], 'git_blob_oid': prior[path][1], 'sha256': sha(git('show', BASE + ':' + path)),
         'bytes': len(git('show', BASE + ':' + path))} for path in RETIRED]})
    (D / 'source.commit').write_bytes(git('cat-file', 'commit', head))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    after = task.entries(head)
    assert set(prior) == set(old_rows)
    assert set(after) == (set(prior) - set(RETIRED)) | set(paths)
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
          'reuse_proof': {'actual_CI': 40507402194, 'observation': str(OBSERVED), 'unchanged': len(rows) - len(changed), 'changed': changed,
                          'removed': list(RETIRED)}})
    invariant()
    print(json.dumps({'capture': head, 'tree': tree, 'paths': len(paths), 'assets': len(rows)}), flush=True)


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
    cap = load(D / 'capture.json')
    changed_paths = cap['paths'] + cap['retired']
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = cap['commit']
    inventory = module('split_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
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
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the main receipts; entries whose start/pattern match a changed path, or whose entry changed, are recollected.',
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
    for name in ('capture.json', 'source.patch', 'source-retired.json', 'source.commit', 'discovery-selection.json', 'source-preparation.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / 'prepare_split.py')
    shutil.copyfile(EQUIVALENCE, dest / 'check_split_equivalence.py')
    shutil.copyfile(W4 / 'result.json', dest / 'split-worker-result.json')
    (dest / 'README.md').write_text('# Catalog part split\n\n'
        'The catalog writer stores method and history objects in 16 part files each, chosen by a stable hash of the '
        'object id, so that no single committed file approaches the GitHub file size limit. Readers are unchanged. '
        'A control generation with the previous writer on the same input tree shows that only the layout changed. '
        'Criteria, DUT, collector, language profile and workflows are unchanged. Scientific qualification is false.\n')
    idx = D / 'archive.index'
    git('read-tree', parent, index=idx)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        path = p.relative_to(D / 'archive-files').as_posix()
        raw = p.read_bytes()
        assert len(raw) < 50 * 1024 * 1024, (path, len(raw))
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + path, index=idx)
        files.append({'path': path, 'sha256': sha(raw), 'bytes': len(raw)})
    tree = git('write-tree', index=idx).decode().strip()
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive catalog part split construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R2 / 'config.json')
    old = {}
    for item in config['discoveries']:
        entry = load(Path(item['entry_file']))['entry']
        old[entry['entry_id']] = entry
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
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
    """Split writer (the patched source) and the control writer (main's) on the same input tree."""
    invariant()
    assert sha(MAIN_WRITER.read_bytes()) == sha(git('show', BASE + ':scripts/capabilities/generate_catalog.py'))
    for name, writer in (('control', MAIN_WRITER), ('catalog', S / 'scripts/capabilities/generate_catalog.py')):
        with (D / ('generation-' + name + '.stdout')).open('xb') as out, (D / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', str(writer), '--config', str(D / 'config.json'), '--output', str(D / name)],
                                 cwd=S, env=env(), stdout=out, stderr=err)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    report = load(D / 'catalog/generation-report.json')
    generated_dir = D / 'catalog/tree/evas/capabilities/data'
    previous, current = task.objects(S / 'evas/capabilities/data'), task.objects(generated_dir)
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    main_objects = objects_at(BASE)
    missing = [list(k) for k in main_objects if k not in current]
    rewritten = [list(k) for k, v in main_objects.items() if k in current and current[k] != v]
    assert not missing and not rewritten, (len(missing), len(rewritten))
    for name in ('historical-index.json', 'method-index.json'):
        assert not (generated_dir / name).exists(), name
    paths = []
    for p in sorted(generated_dir.glob('*.json')):
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    for path in RETIRED:
        (S / path).unlink()
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'retired_removed_from_disk': list(RETIRED),
          'old_versions_retained': len(previous), 'main_retention': {'objects': len(main_objects), 'missing': 0, 'rewritten': 0},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
          'largest_data_file': max(sizes.items(), key=lambda x: x[1]), 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'objects': report['objects'],
                      'largest': max(sizes.items(), key=lambda x: x[1])}), flush=True)


def equivalence():
    """Control (main writer) and split (new writer) on the same input tree: only the layout may differ."""
    invariant()
    assert not (D / 'equivalence.json').exists()
    base_data = D / 'base-data'
    base_data.mkdir()
    header = json.loads(git('show', BASE + ':' + DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts']]:
        (base_data / name).write_bytes(git('show', BASE + ':' + DATA + name))
    run = subprocess.run([str(PY), '-B', str(EQUIVALENCE), str(D / 'control/tree/evas/capabilities/data'),
                          str(D / 'catalog/tree/evas/capabilities/data'), '--committed', str(base_data), '--output', str(D / 'equivalence.json')],
                         env=env(), capture_output=True, text=True)
    (D / 'equivalence.stdout').write_text(run.stdout)
    (D / 'equivalence.stderr').write_text(run.stderr)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
    invariant()
    print(run.stdout.strip()[-1500:], flush=True)


def derive():
    """Regenerate the committed derived files; checks run later against the frozen head."""
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    cap = load(D / 'capture.json')
    paths = changed_vs(cap['commit'])
    rendered = set(render_outputs())
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(FORBIDDEN_PREFIXES) or p in COLLECTOR for p in paths)
    for path in RETIRED:
        assert not (S / path).exists(), path
    write(D / 'derive-acceptance.json', {'source_capture': cap['commit'], 'paths_vs_capture': paths, 'render_outputs': len(rendered),
          'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_capture': len(paths)}), flush=True)


def freeze():
    invariant()
    cap, der = load(D / 'capture.json'), load(D / 'derive-acceptance.json')
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(cap['commit'])
    assert sorted(generated) == sorted(der['paths_vs_capture'])
    final = task.make_commit(cap['commit'], generated, FINAL_MESSAGE + TRAILER, 'final')
    git('merge-base', '--is-ancestor', BASE, final['commit'])
    complete = sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines())
    assert not any(p.startswith(FORBIDDEN_PREFIXES) or p in COLLECTOR for p in complete), complete
    final.update(base=BASE, source_capture=cap['commit'], complete_paths=complete, retired=list(RETIRED),
                 derive=str(D / 'derive-acceptance.json'), equivalence=str(D / 'equivalence.json'),
                 precheck='runs on the frozen head in parallel with CI',
                 review='tcodex Astra (serviceTier=priority, user decision 2A) after CI selection and fast-checks pass', CI='pending',
                 published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', BASE, final['commit']))
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
          'focused': False, 'scope': 'catalog part split quick maintenance gate; full scientific regression is CI only.'})
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
    parser.add_argument('stage', choices=['source', 'capture', 'discover', 'archive', 'generate', 'equivalence', 'derive', 'freeze',
                                          'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

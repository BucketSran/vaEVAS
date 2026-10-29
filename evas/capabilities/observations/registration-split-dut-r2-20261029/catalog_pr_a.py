"""Regenerate the capability catalog for PR-A r2 (gate fix + split-DUT registration) on main d6b7543f, as in r2a.

PR-A r2 changes six files under scripts/: four changed blobs and two new test modules (15 + 6 methods). The catalog's
asset index and the maintenance namespace must follow. Stages, each writing new receipts under W/r2a2/catalog-02 and
refusing to replace them:
  assets    asset receipt for the PR-A head, reusing main's push CI 40635877195 observation for unchanged blobs
  discover  the 31 discovery entries: reuse the PR273 r4 receipts by exact entry, collector and owner-module hashes;
            recollect only entries owning a changed test module (discovery imports modules; no test bodies run)
  union     main's catalog as the previous union, with the retention check of the C0 flow
  archive   one unpublished construction-archive commit (private repo only) on the published archive tip
  generate  generate_catalog.py twice; outputs must be byte-identical and keep every previous object version
  derive    traceability.py and render.py; only derived files may change
  commit    commit the derived files on top of PR-A commits 1 and 2 (private repo only)
Git: the private repo W/r2a2/repo reads the shared object store through objects/info/alternates; nothing is written
there. No refs, index or config of the real repository change. No scientific test, simulator or kernel runs.
Two construction archives for this change stay unpublished and are replaced by this one, under its own prefix and tag:
7f9045d1 (r2a) and c93e5ffd (W/r2a2/catalog, stopped during generation to fold a README change into commit 2).
Usage: python3 -B catalog_pr_a.py <stage>   (the 3.12 lint venv)
"""
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

sys.dont_write_bytecode = True
R2A = Path(__file__).resolve().parents[1]
B = R2A.parents[1]
S = R2A / 'repo'
D = R2A / 'catalog-02'
PY = B / 'pr4/trusted-context/SP-01/lint-venv/bin/python'
R4 = B / 'pr6/ci-pins-a-20261027/r4'
OBSERVED = B / 'capability-batch1-registration-20261029/flow/runs/main-push-40635877195-catalog/catalog-inventory/assets-before.json'
BASE = 'd6b7543fc815aaa584c886108691b6f2c01eb220'
BASE_TREE = 'c299c287165fa29ead86442956296b0a825aa35b'
ARCHIVE_TIP = '0b485dd319e46058bd78672943458e025183baea'  # gh api read 2026-10-29T02:44:13Z, r2a2/logs/gh-archive-ref-01.json
PREFIX = 'evas/capabilities/observations/registration-split-dut-r2-20261029'
ARCHIVE_TAG = 'archive-pr-a-r2-02'
RULE_COMMITS = 2
EXPECTED_CHANGED = ['scripts/README.md', 'scripts/regression_context_registration.py', 'scripts/regression_gate.py',
                    'scripts/tests/regression_registration_fixtures.py']
EXPECTED_ADDED = ['scripts/tests/test_registration_split_dut.py', 'scripts/tests/test_regression_vanished_nonpass.py']
DATA = 'evas/capabilities/data/'
RETENTION_REVS = (('main', BASE), ('main_before_pr273', 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'),
                  ('main_before_split', '02dee32b2c9b25f166cbd77f8a895953e004f288'))
WARNING_BYTES = 50 * 1024 * 1024
PART_FILES = tuple([DATA + 'method-index-%02d.json' % i for i in range(16)] + [DATA + 'historical-index-%02d.json' % i for i in range(16)])
DERIVED_DATA = {DATA + 'registry.json', DATA + 'catalog-sources.json', DATA + 'asset-index.json', DATA + 'entrypoint-index.json',
                *PART_FILES, 'evas/docs/development/TRACEABILITY.md'}
CRITERIA_PREFIXES = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
DUT_PREFIXES = ('evas/src/', 'evas/rust_core/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
             'scripts/regression_observation_policy.json', 'evas/capabilities/data/language-profile.json')
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
COMMIT_MESSAGE = ('Regenerate the catalog for the vanished non-pass and split-DUT tests\n\n'
                  'Two new modules add 21 maintenance methods: scripts/tests/test_regression_vanished_nonpass.py\n'
                  '(6) and scripts/tests/test_registration_split_dut.py (15). Four scripts change content. The\n'
                  'asset index and method index follow; every previous object version is kept. Discovery\n'
                  'recollects only the scripts/tests entry that owns the new modules; the other 30 entries reuse\n'
                  'their archived receipts. Two generations are byte-identical.')


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def write_new(path, value):
    path = Path(path)
    assert path.resolve().is_relative_to(R2A.resolve()), path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
    return path


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def git(*args, index=None, data=None, check=True):
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C',
                         'GIT_AUTHOR_NAME': 'BucketSran', 'GIT_AUTHOR_EMAIL': 'BucketSran@users.noreply.github.com',
                         'GIT_COMMITTER_NAME': 'BucketSran', 'GIT_COMMITTER_EMAIL': 'BucketSran@users.noreply.github.com'}
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    r = subprocess.run(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S),
                        '-c', 'core.hooksPath=' + str(R2A / 'tools/no-hooks'), *args],
                       env=env, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=S)
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def show(rev, path):
    return git('show', rev + ':' + path)


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def entries(rev):
    rows = {}
    for item in git('ls-tree', '-r', '-z', rev).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            assert kind == 'blob', path
            rows[path.decode()] = (mode, oid)
    return rows


def objects_dir(path):
    header = json.loads((Path(path) / 'registry.json').read_text())
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads((Path(path) / part).read_text())['objects']
    return {(item['id'], item['version']): item for item in result}


def objects_at(rev):
    header = json.loads(show(rev, DATA + 'registry.json'))
    result = list(header['objects'])
    for part in header['object_parts']:
        result += json.loads(show(rev, DATA + part))['objects']
    return {(item['id'], item['version']): item for item in result}


def head():
    return git('rev-parse', 'HEAD').decode().strip(), git('rev-parse', 'HEAD^{tree}').decode().strip()


def changed_vs(rev):
    git('add', '--intent-to-add', '--', '.')
    paths = git('diff', '--no-renames', '--name-only', rev).decode().splitlines()
    git('reset', '--quiet')
    return paths


def run_logged(name, argv, results, extra_env=None, limit=3000):
    log = D / name
    start = utc()
    env = clean_env() | {'PYTHONDONTWRITEBYTECODE': '1', 'PATH': str(PY.parent) + ':/usr/bin:/bin:/usr/sbin:/sbin'} | (extra_env or {})
    with log.open('x') as out:
        out.write('COMMAND ' + repr([str(a) for a in argv]) + '\nCWD ' + str(S) + '\nSTARTED ' + start + '\n')
        out.flush()
        r = subprocess.run(['/usr/bin/perl', '-e', 'alarm shift; exec @ARGV or die "exec: $!"', str(limit), *map(str, argv)],
                           cwd=S, env=env, stdout=out, stderr=subprocess.STDOUT)
        out.write('\nFINISHED ' + utc() + '\nreturncode=' + str(r.returncode) + '\n')
    results.append({'command': [str(a) for a in argv], 'log': str(log), 'returncode': r.returncode, 'started_at_utc': start,
                    'finished_at_utc': utc()})
    assert r.returncode == 0, name
    return r.returncode


def assets():
    assert not (D / 'assets.json').exists()
    commit, tree = head()
    assert git('rev-parse', 'HEAD~%d' % RULE_COMMITS).decode().strip() == BASE and not git('status', '--porcelain=v1').strip()
    observed = load(OBSERVED)
    assert observed['source_commit'] == BASE and observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    before, after = entries(BASE), entries(commit)
    assert set(old_rows) == set(before)
    rows, changed, added = [], [], []
    for path, (mode, oid) in sorted(after.items()):
        item = old_rows.get(path)
        if before.get(path) == (mode, oid):
            assert (item['git_mode'], item['observed_blob_oid'], item['index_blob_oid']) == (mode, oid, oid), path
            value, actual = item['sha256'], item['actual_mode']
        else:
            data = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid, path
            value, actual = sha(data), (S / path).stat().st_mode & 0o777
            (changed if path in before else added).append(path)
        rows.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual, 'git_blob_oid': oid})
    removed = sorted(set(before) - set(after))
    assert not removed
    expected = set(git('diff', '--no-renames', '--name-only', BASE, commit).decode().splitlines())
    assert set(changed) | set(added) == expected, (changed, added, expected)
    assert (changed, added) == (EXPECTED_CHANGED, EXPECTED_ADDED), (changed, added)
    write_new(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
              'source_commit': commit, 'source_tree': tree, 'source_object_format': 'sha1',
              'source_kind': 'immutable-export', 'source_profile': 'git-tree-regular-blobs-v1',
              'source_availability': 'local-only-before-publication', 'content_binding': 'verified-git-blob-oids',
              'scope': observed['scope'], 'assets': rows,
              'reuse_proof': {'actual_CI': 40635877195, 'observation': str(OBSERVED), 'observation_sha256': sha(OBSERVED.read_bytes()),
                              'unchanged': len(rows) - len(changed) - len(added), 'changed': changed, 'added': added}})
    print(json.dumps({'assets': len(rows), 'changed': changed, 'added': added}), flush=True)


def discover():
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(R4 / 'config.json')
    candidates = []
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates.append((path, value, config['discovery_source_locators'][value['entry']['entry_id']]))
    commit, _ = head()
    changed = git('diff', '--no-renames', '--name-only', BASE, commit).decode().splitlines()
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = commit
    inventory = module('pr_a_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    found = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(found) == len(candidates) == 31, (len(found), len(candidates))
    assets_by_path = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    chosen, new_count = [], 0
    for index, entry in enumerate(found):
        start = entry['start'].rstrip('/') + '/'
        touched = sorted(p for p in changed if p.startswith(start) and fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern']))
        matching = []
        if not touched:
            for path, value, locator in candidates:
                r = value['receipt']
                if value['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']:
                    continue
                if assets_by_path.get(r['collector']['path']) != r['collector']['sha256']:
                    continue
                if any(assets_by_path.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                    continue
                matching.append((path, value, locator))
            assert len(matching) == 1, (entry['entry_id'], len(matching))
        if matching:
            path, value, locator = matching[0]
            assert show(locator['revision'], locator['path']) == path.read_bytes(), path
            git('merge-base', '--is-ancestor', locator['revision'], ARCHIVE_TIP)
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
                   'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances']}
        else:
            receipt = inventory.child(S, entry, 120)
            assert receipt['complete'] and not receipt['errors'] and not receipt['unresolved_instances'], entry['entry_id']
            path = D / 'new-discovery' / ('entry-%03d.json' % index)
            write_new(path, {'entry': entry, 'receipt': receipt})
            row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': False, 'forced_by_changed_paths': touched,
                   'sha256': sha(path.read_bytes()), 'instances': receipt['discovered_instances']}
            new_count += 1
        row.update(start=entry['start'], pattern=entry['pattern'], line=entry.get('line'))
        chosen.append(row)
    assert not git('status', '--porcelain=v1').strip()
    write_new(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen) - new_count,
              'new_collections': new_count, 'changed_paths_vs_main': changed, 'archive_tip_checked': ARCHIVE_TIP,
              'workflow_sha256': parsed['workflow_sha256'],
              'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the PR273 r4 receipts (main tests); '
                             'entries owning a changed test module are recollected.',
              'test_bodies_executed': False, 'scientific_qualification': False})
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count,
                      'recollected': [c['start'] + ' ' + c['pattern'] for c in chosen if not c['reused']]}), flush=True)


def union():
    union_dir = D / 'previous-union'
    assert not union_dir.exists() and not (D / 'union-acceptance.json').exists()
    union_dir.mkdir(parents=True)
    header = json.loads(show(BASE, DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts']]:
        (union_dir / name).write_bytes(show(BASE, DATA + name))
    merged = objects_dir(union_dir)
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    assert merged == objects_dir(S / DATA)
    write_new(D / 'union-acceptance.json', {'previous': BASE, 'union_dir': str(union_dir), 'union_objects': len(merged),
              'retention': retention, 'scientific_qualification': False})
    print(json.dumps({'union_objects': len(merged)}), flush=True)


def archive():
    assert not (D / 'archive.json').exists()
    assert git('rev-parse', ARCHIVE_TIP + '^{commit}').decode().strip() == ARCHIVE_TIP
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('assets.json', 'discovery-selection.json', 'union-acceptance.json'):
        shutil.copyfile(D / name, dest / name)
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    shutil.copyfile(__file__, dest / Path(__file__).name)
    commit, _ = head()
    (dest / 'README.md').write_text(
        '# Catalog inputs for the vanished non-pass check and the split-DUT registration change\n\n'
        'The change refuses an unchanged baseline when a registered non-pass vanished, and lets an E1 that ran on the '
        'batch\'s own DUT register while the registration run stays on main\'s DUT. It touches scripts/ only: four '
        'changed blobs and two new test modules. Discovery recollects the scripts/tests entry that owns the new modules; '
        'the other 30 entries reuse their archived receipts. Criteria, DUT, collector, language profile and invocation '
        'are unchanged. Head ' + commit[:8] + ' on main ' + BASE[:8] + '. It replaces the unpublished construction '
        'archives 7f9045d1 and c93e5ffd of earlier attempts. Scientific qualification is false.\n')
    index = D / 'archive.index'
    assert not index.exists()
    git('read-tree', ARCHIVE_TIP, index=index)
    files = []
    for p in sorted((D / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < WARNING_BYTES, (p, len(raw))
        rel = p.relative_to(D / 'archive-files').as_posix()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + rel, index=index)
        files.append({'path': rel, 'sha256': sha(raw), 'bytes': len(raw), 'blob': oid})
    tree = git('write-tree', index=index).decode().strip()
    archived = git('commit-tree', tree, '-p', ARCHIVE_TIP, '-m',
                   'Archive the vanished non-pass and split-DUT catalog inputs' + TRAILER).decode().strip()
    index.unlink()
    git('tag', ARCHIVE_TAG, archived)
    write_new(D / 'archive.json', {'commit': archived, 'tree': tree, 'parent': ARCHIVE_TIP, 'prefix': PREFIX, 'files': files,
              'published': False, 'object_store': str(S / '.git'),
              'publication': 'push this exact commit to refs/heads/codex/evas-method-audit-archive-20261025 (fast-forward from '
                             + ARCHIVE_TIP[:8] + ') before PR-A CI; if the archive tip moved, rebuild from the archive stage'})
    config = load(R4 / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(D / 'previous-union'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    for row in load(D / 'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file': row['entry_file']})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': archived,
            'path': PREFIX + '/new-discovery/' + Path(row['entry_file']).name}
    ids = {row['entry_id'] for row in load(D / 'discovery-selection.json')['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= ids, bridge['path']
    write_new(D / 'config.json', config)
    print(json.dumps({'construction_archive': archived, 'parent': ARCHIVE_TIP, 'files': len(files)}), flush=True)


def generate():
    assert load(D / 'config.json')['previous_data_dir'] == str(D / 'previous-union')
    assert not (D / 'generation-acceptance.json').exists()
    env = clean_env() | {'PYTHONDONTWRITEBYTECODE': '1', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    for name in ('catalog', 'catalog-repeat'):
        with (D / ('generation-' + name + '.stdout')).open('xb') as out, (D / ('generation-' + name + '.stderr')).open('xb') as err:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(D / 'config.json'),
                                  '--output', str(D / name)], cwd=S, env=env, stdout=out, stderr=err)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    first, second = D / 'catalog/tree/evas/capabilities/data', D / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / 'catalog/generation-report.json')
    previous, current = objects_dir(D / 'previous-union'), objects_dir(first)
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
    inline_before = {o['id']: o for o in json.loads((S / DATA / 'registry.json').read_text())['objects']}
    inline_after = {o['id']: o for o in header['objects']}
    assert all(inline_after.get(k) == v for k, v in inline_before.items()), 'hand-written registry objects changed'
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
        target = S / DATA / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / DATA).glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    largest = max(sizes.items(), key=lambda x: x[1])
    write_new(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
              'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind,
              'new_object_ids': sorted({k[0] for k in new_objects}),
              'deterministic_double_generation': True, 'hand_written_registry_objects_unchanged': len(inline_before),
              'version_lists': {'ids': len(versions), 'problems': 0,
                                'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
              'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
              'largest_data_file': largest, 'scientific_qualification': False})
    print(json.dumps({'generated_paths': paths, 'new_object_versions': len(new_objects), 'by_kind': by_kind, 'largest': largest}), flush=True)


def render_outputs():
    sys.path.insert(0, str(S / 'evas/capabilities'))
    try:
        renderer = module('pr_a_render', S / 'evas/capabilities/render.py')
        files = renderer.outputs(renderer.registry())
    finally:
        sys.path.pop(0)
    return sorted(Path(p).resolve().relative_to(S.resolve()).as_posix() for p in files)


def derive():
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [PY, '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [PY, '-B', 'evas/capabilities/render.py'], results)
    commit, _ = head()
    paths = changed_vs(commit)
    rendered = set(render_outputs())
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write_new(D / 'derive-acceptance.json', {'rule_head': commit, 'paths_vs_rule_head': paths, 'render_outputs': len(rendered),
              'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()},
              'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'paths_vs_rule_head': paths}), flush=True)


def commit():
    assert not (D / 'commit.json').exists()
    rule_head, _ = head()
    assert git('rev-parse', 'HEAD~%d' % RULE_COMMITS).decode().strip() == BASE
    selection, receipt = load(D / 'discovery-selection.json'), load(D / 'assets.json')['reuse_proof']
    # The message states these counts; refuse to commit if the receipts say otherwise.
    assert (selection['entry_count'], selection['reused'], selection['new_collections']) == (31, 30, 1), selection['entry_count']
    assert (receipt['changed'], receipt['added']) == (EXPECTED_CHANGED, EXPECTED_ADDED)
    accepted = load(D / 'derive-acceptance.json')
    paths = changed_vs(rule_head)
    assert paths == accepted['paths_vs_rule_head'], (paths, accepted['paths_vs_rule_head'])
    assert all(sha((S / p).read_bytes()) == accepted['files'][p] for p in paths)
    git('add', '--', *paths)
    git('-c', 'commit.gpgsign=false', 'commit', '-q', '-m', COMMIT_MESSAGE + TRAILER)
    catalog_commit, tree = head()
    assert git('rev-parse', 'HEAD~1').decode().strip() == rule_head and not git('status', '--porcelain=v1').strip()
    write_new(D / 'commit.json', {'rule_head': rule_head, 'catalog_commit': catalog_commit, 'tree': tree, 'paths': paths,
                                  'at_utc': utc()})
    print(json.dumps({'catalog_commit': catalog_commit, 'tree': tree, 'paths': len(paths)}), flush=True)


if __name__ == '__main__':
    stage = sys.argv[1]
    assert stage in ('assets', 'discover', 'union', 'archive', 'generate', 'derive', 'commit'), stage
    D.mkdir(exist_ok=True)
    started = utc()
    globals()[stage]()
    print(json.dumps({'stage': stage, 'started_at_utc': started, 'finished_at_utc': utc()}), flush=True)

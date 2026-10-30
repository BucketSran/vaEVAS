"""Regenerate the capability catalog for the EVAS documentation sync, on a given main.

The documentation sync changes six Markdown files that are catalog assets (GLOSSARY.md, evas/README.md,
evas/docs/README.md, evas/docs/UPDATE.md, evas/docs/COMPARISON.md, evas/docs/development/DECISIONS.md). Their
asset entries gain new versions; no test module, collector, criteria or DUT path changes. Every input that moves
when main or the construction archive moves is a parameter, so the same script rebuilds the catalog after a rebase:
  --repo          private checkout whose HEAD is the last documentation commit on --main
  --main          main commit the documentation commits sit on (asset reuse, discovery diff, retention)
  --archive-tip   construction-archive tip the new archive commit extends (codex/evas-method-audit-archive-20261025)
  --observation   catalog-inventory assets-before.json of a successful main push CI run on --main, checked against
                  --observation-zip (the artifact zip), --observation-api (artifacts.json) and --observation-run-json
  --observation-run  that run's id
  --candidates    the construction config of the catalog now on --main (its discovery receipts are reused)
  --docs-commits  number of documentation commits on --main (the catalog commit goes on top)
  --out           a new directory for this run's receipts
Stages, each writing new receipts under --out and refusing to replace them:
  assets    asset receipt for the docs head: blobs unchanged since --main reuse the CI observation, every other blob
            is hashed from the private checkout and checked against its Git OID
  discover  the 31 discovery entries: reuse candidate receipts by exact entry, collector and owner-module hashes;
            a documentation change owns no test module, so all 31 must be reused (no test bodies run)
  union     main's catalog as the previous union, with the retention check
  archive   one unpublished construction-archive commit (private repo only) on --archive-tip
  generate  generate_catalog.py twice; outputs must be byte-identical and keep every previous object version
  derive    traceability.py and render.py; only derived files may change
  commit    commit the derived files on top of the documentation commits (private repo only)
Run scripts/diagnostic_inventory.py --write in the checkout first; it must leave the tree clean.
Git: the private repo reads the shared object store through objects/info/alternates; nothing is written there.
No refs, index or config of the real repository change. No scientific test, simulator or kernel runs.
Usage: python3 -B catalog_docs.py <stage> [options]   (the 3.12 lint venv)
"""
import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone

sys.dont_write_bytecode = True
W = Path(__file__).resolve().parents[1]
B = W.parent
PY = B / 'pr4/trusted-context/SP-01/lint-venv/bin/python'
FLOW = B / 'capability-batch1-registration-20261029/flow/r2/runs/main-push-40864041959-catalog-inventory'
DEFAULTS = dict(
    repo=W / 'repo',
    main='b4a072959d55fa3b23e34dfcadd92103ec89f2a3',
    archive_tip='e91f96cc0b08385268dc187e47ad198e2f3637d7',
    observation=FLOW / 'catalog-inventory/assets-before.json',
    observation_zip=FLOW / 'catalog-inventory.zip',
    observation_api=FLOW / 'api/artifacts.json',
    observation_run_json=FLOW / 'api/run.json',
    observation_run=40864041959,
    candidates=B / 'registration-rule-dut-fix-impl-opus-20261029/r2a2/catalog-02/config.json',
    docs_commits=7,
    prefix='evas/capabilities/observations/docs-sync-20261029',
    out=W / 'catalog-01')
ARCHIVE_TAG = 'archive-docs-sync'
EXPECTED_DIFF = ['M\tGLOSSARY.md', 'M\tevas/README.md', 'M\tevas/docs/COMPARISON.md', 'M\tevas/docs/README.md',
                 'M\tevas/docs/UPDATE.md', 'M\tevas/docs/development/DECISIONS.md']
DATA = 'evas/capabilities/data/'
# The given main and the mains before it: every object version they hold must survive.
RETENTION_REVS = (('main', None), ('main_at_docs_sync_start', 'b4a072959d55fa3b23e34dfcadd92103ec89f2a3'),
                  ('pr293_merge', '6fed3c820b6eaecdfabd6d5dcacf8febdd197e4c'),
                  ('main_before_pr293', 'd6b7543fc815aaa584c886108691b6f2c01eb220'),
                  ('main_before_pr273', 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'),
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
ARGS = None


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def out():
    return Path(ARGS.out)


def repo():
    return Path(ARGS.repo)


def write_new(path, value):
    path = Path(path)
    assert path.resolve().is_relative_to(W.resolve()), path
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())
    return path


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def git(*args, index=None, data=None, check=True):
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C',
                         'GIT_AUTHOR_NAME': 'BucketSran', 'GIT_AUTHOR_EMAIL': '138781625+BucketSran@users.noreply.github.com',
                         'GIT_COMMITTER_NAME': 'BucketSran', 'GIT_COMMITTER_EMAIL': '138781625+BucketSran@users.noreply.github.com'}
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    r = subprocess.run(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(repo() / '.git'), '--work-tree=' + str(repo()),
                        '-c', 'core.hooksPath=' + str(W / 'tools/no-hooks'), *args],
                       env=env, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=repo())
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


def docs_head():
    """HEAD before the catalog commit: the last documentation commit, --docs-commits above --main."""
    commit, _ = head()
    assert git('rev-parse', 'HEAD~%d' % ARGS.docs_commits).decode().strip() == ARGS.main, 'HEAD is not the docs head'
    return commit


def changed_vs(rev):
    git('add', '--intent-to-add', '--', '.')
    paths = git('diff', '--no-renames', '--name-only', rev).decode().splitlines()
    git('reset', '--quiet')
    return paths


def run_logged(name, argv, results, extra_env=None, limit=3000):
    log = out() / name
    start = utc()
    env = clean_env() | {'PYTHONDONTWRITEBYTECODE': '1', 'PATH': str(PY.parent) + ':/usr/bin:/bin:/usr/sbin:/sbin'} | (extra_env or {})
    with log.open('x') as stream:
        stream.write('COMMAND ' + repr([str(a) for a in argv]) + '\nCWD ' + str(repo()) + '\nSTARTED ' + start + '\n')
        stream.flush()
        r = subprocess.run(['/usr/bin/perl', '-e', 'alarm shift; exec @ARGV or die "exec: $!"', str(limit), *map(str, argv)],
                           cwd=repo(), env=env, stdout=stream, stderr=subprocess.STDOUT)
        stream.write('\nFINISHED ' + utc() + '\nreturncode=' + str(r.returncode) + '\n')
    results.append({'command': [str(a) for a in argv], 'log': str(log), 'returncode': r.returncode, 'started_at_utc': start,
                    'finished_at_utc': utc()})
    assert r.returncode == 0, name
    return r.returncode


def docs_diff(commit):
    return git('diff', '--no-renames', '--name-status', ARGS.main, commit).decode().splitlines()


def observation():
    """The CI asset observation, checked against the artifact zip it came in and the API digest of that zip."""
    raw = Path(ARGS.observation).read_bytes()
    zipped = Path(ARGS.observation_zip).read_bytes()
    api = load(ARGS.observation_api)
    rows = api['artifacts'] if isinstance(api, dict) else api
    digests = [row.get('digest') for row in rows if row.get('name') == 'catalog-inventory']
    assert digests == ['sha256:' + sha(zipped)], (digests, sha(zipped))
    with zipfile.ZipFile(Path(ARGS.observation_zip)) as archive:
        assert archive.read('assets-before.json') == raw
    run = load(ARGS.observation_run_json)
    assert (run['id'], run['head_sha'], run['event'], run['conclusion']) == (ARGS.observation_run, ARGS.main, 'push', 'success'), run
    value = json.loads(raw)
    return value, dict(run=ARGS.observation_run, head_sha=run['head_sha'], conclusion=run['conclusion'],
                       observation=str(ARGS.observation), observation_sha256=sha(raw),
                       artifact_zip_sha256=sha(zipped), api_digest=digests[0])


def assets():
    assert not (out() / 'assets.json').exists()
    commit = docs_head()
    _, tree = head()
    assert not git('status', '--porcelain=v1').strip()
    observed, proof = observation()
    main_tree = git('rev-parse', ARGS.main + '^{tree}').decode().strip()
    assert observed['source_commit'] == ARGS.main and observed['source_tree'] == main_tree and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    before, after = entries(ARGS.main), entries(commit)
    assert set(old_rows) == set(before)
    rows, changed, added = [], [], []
    for path, (mode, oid) in sorted(after.items()):
        item = old_rows.get(path)
        if before.get(path) == (mode, oid):
            assert (item['git_mode'], item['observed_blob_oid'], item['index_blob_oid']) == (mode, oid, oid), path
            value, actual = item['sha256'], item['actual_mode']
        else:
            data = (repo() / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest() == oid, path
            value, actual = sha(data), (repo() / path).stat().st_mode & 0o777
            (changed if path in before else added).append(path)
        rows.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual, 'git_blob_oid': oid})
    assert not sorted(set(before) - set(after))
    expected = set(git('diff', '--no-renames', '--name-only', ARGS.main, commit).decode().splitlines())
    assert set(changed) | set(added) == expected, (changed, added, expected)
    assert docs_diff(commit) == EXPECTED_DIFF, docs_diff(commit)
    write_new(out() / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
              'source_commit': commit, 'source_tree': tree, 'source_object_format': 'sha1',
              'source_kind': 'immutable-export', 'source_profile': 'git-tree-regular-blobs-v1',
              'source_availability': 'local-only-before-publication', 'content_binding': 'verified-git-blob-oids',
              'scope': observed['scope'], 'assets': rows,
              'reuse_proof': dict(proof, actual_CI=ARGS.observation_run, unchanged=len(rows) - len(changed) - len(added),
                                  changed=changed, added=added)})
    print(json.dumps({'assets': len(rows), 'changed': changed, 'added': added}), flush=True)


def discover():
    assert sys.version_info[:2] == (3, 12)
    assert not (out() / 'discovery-selection.json').exists()
    config = load(ARGS.candidates)
    candidates = []
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates.append((path, value, config['discovery_source_locators'][value['entry']['entry_id']]))
    commit = docs_head()
    changed = git('diff', '--no-renames', '--name-only', ARGS.main, commit).decode().splitlines()
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = ARGS.main
    os.environ['CI_INVENTORY_HEAD'] = commit
    inventory = module('docs_sync_discovery', repo() / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((repo() / inventory.WORKFLOW).read_bytes())
    found = parsed['entries'] + [inventory.primary_entry(repo(), parsed)]
    assert len(found) == len(candidates) == 31, (len(found), len(candidates))
    assets_by_path = {r['path']: r['sha256'] for r in load(out() / 'assets.json')['assets']}
    chosen = []
    for index, entry in enumerate(found):
        start = entry['start'].rstrip('/') + '/'
        touched = sorted(p for p in changed if p.startswith(start) and fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern']))
        assert not touched, ('a documentation change must not own a discovery entry', entry['entry_id'], touched)
        matching = []
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
        path, value, locator = matching[0]
        assert show(locator['revision'], locator['path']) == path.read_bytes(), path
        git('merge-base', '--is-ancestor', locator['revision'], ARGS.archive_tip)
        row = {'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
               'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances'],
               'start': entry['start'], 'pattern': entry['pattern'], 'line': entry.get('line')}
        chosen.append(row)
    assert not git('status', '--porcelain=v1').strip()
    write_new(out() / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen),
              'new_collections': 0, 'changed_paths_vs_main': changed, 'archive_tip_checked': ARGS.archive_tip,
              'candidates_config': str(ARGS.candidates), 'candidates_config_sha256': sha(Path(ARGS.candidates).read_bytes()),
              'workflow_sha256': parsed['workflow_sha256'],
              'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the construction config of the '
                             'catalog on --main; the documentation change owns no test module, so every entry is reused.',
              'test_bodies_executed': False, 'scientific_qualification': False})
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen), 'new_collections': 0}), flush=True)


def retention_revs():
    return [(name, rev or ARGS.main) for name, rev in RETENTION_REVS]


def union():
    union_dir = out() / 'previous-union'
    assert not union_dir.exists() and not (out() / 'union-acceptance.json').exists()
    union_dir.mkdir(parents=True)
    header = json.loads(show(ARGS.main, DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts']]:
        (union_dir / name).write_bytes(show(ARGS.main, DATA + name))
    merged = objects_dir(union_dir)
    retention = {}
    for name, rev in retention_revs():
        git('merge-base', '--is-ancestor', rev, ARGS.main)
        expected = objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    assert merged == objects_dir(repo() / DATA)
    write_new(out() / 'union-acceptance.json', {'previous': ARGS.main, 'union_dir': str(union_dir), 'union_objects': len(merged),
              'retention': retention, 'scientific_qualification': False})
    print(json.dumps({'union_objects': len(merged)}), flush=True)


def archive():
    assert not (out() / 'archive.json').exists()
    assert git('rev-parse', ARGS.archive_tip + '^{commit}').decode().strip() == ARGS.archive_tip
    dest = out() / 'archive-files' / ARGS.prefix
    dest.mkdir(parents=True)
    for name in ('assets.json', 'discovery-selection.json', 'union-acceptance.json'):
        shutil.copyfile(out() / name, dest / name)
    shutil.copyfile(__file__, dest / Path(__file__).name)
    commit = docs_head()
    (dest / 'README.md').write_text(
        '# Catalog inputs for the EVAS documentation sync\n\n'
        'The change edits six Markdown files that are catalog assets: GLOSSARY.md, evas/README.md, '
        'evas/docs/README.md, evas/docs/UPDATE.md, evas/docs/COMPARISON.md and evas/docs/development/DECISIONS.md. '
        'It changes no test module, collector, criteria, DUT, language profile or invocation, so all 31 discovery '
        'entries reuse their archived receipts. Head ' + commit[:8] + ' on main ' + ARGS.main[:8] + '; parent archive '
        + ARGS.archive_tip[:8] + '. Scientific qualification is false.\n')
    index = out() / 'archive.index'
    assert not index.exists()
    git('read-tree', ARGS.archive_tip, index=index)
    files = []
    for p in sorted((out() / 'archive-files').rglob('*')):
        if not p.is_file():
            continue
        raw = p.read_bytes()
        assert len(raw) < WARNING_BYTES, (p, len(raw))
        rel = p.relative_to(out() / 'archive-files').as_posix()
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        git('update-index', '--add', '--cacheinfo', '100644,' + oid + ',' + rel, index=index)
        files.append({'path': rel, 'sha256': sha(raw), 'bytes': len(raw), 'blob': oid})
    tree = git('write-tree', index=index).decode().strip()
    archived = git('commit-tree', tree, '-p', ARGS.archive_tip, '-m',
                   'Archive the catalog inputs of the EVAS documentation sync' + TRAILER).decode().strip()
    index.unlink()
    tag = ARCHIVE_TAG + '-' + out().name
    git('tag', tag, archived)
    write_new(out() / 'archive.json', {'commit': archived, 'tree': tree, 'parent': ARGS.archive_tip, 'prefix': ARGS.prefix,
              'files': files, 'published': False, 'object_store': str(repo() / '.git'), 'tag': tag,
              'publication': 'push this exact commit to refs/heads/codex/evas-method-audit-archive-20261025 as a fast-forward '
                             'from ' + ARGS.archive_tip[:8] + ' before the docs PR CI; if the archive tip moved, rebuild from '
                             'the archive stage with --archive-tip set to the new tip'})
    config = load(ARGS.candidates)
    # archive_commit names the method-audit archive behind the historical records; it stays as the candidates have it.
    config.update(source_root=str(repo()), archive_repository=str(repo()), previous_data_dir=str(out() / 'previous-union'),
                  asset_receipt=str(out() / 'assets.json'), source_repositories={'vaevas': str(repo())}, discoveries=[],
                  discovery_source_locators={})
    for row in load(out() / 'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file': row['entry_file']})
        config['discovery_source_locators'][row['entry_id']] = row['source_locator']
    ids = {row['entry_id'] for row in load(out() / 'discovery-selection.json')['entries']}
    for bridge in config['bridge_evidence']:
        assert set(bridge['consumer_entry_ids']) <= ids, bridge['path']
    write_new(out() / 'config.json', config)
    print(json.dumps({'construction_archive': archived, 'parent': ARGS.archive_tip, 'files': len(files), 'tag': tag}), flush=True)


def generate():
    assert load(out() / 'config.json')['previous_data_dir'] == str(out() / 'previous-union')
    assert not (out() / 'generation-acceptance.json').exists()
    env = clean_env() | {'PYTHONDONTWRITEBYTECODE': '1', 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_OPTIONAL_LOCKS': '0'}
    for name in ('catalog', 'catalog-repeat'):
        with (out() / ('generation-' + name + '.stdout')).open('xb') as stdout, \
                (out() / ('generation-' + name + '.stderr')).open('xb') as stderr:
            run = subprocess.run([str(PY), '-B', 'scripts/capabilities/generate_catalog.py', '--config',
                                  str(out() / 'config.json'), '--output', str(out() / name)],
                                 cwd=repo(), env=env, stdout=stdout, stderr=stderr)
        assert run.returncode == 0, 'Read generation-' + name + '.stderr'
    first, second = out() / 'catalog/tree/evas/capabilities/data', out() / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(out() / 'catalog/generation-report.json')
    previous, current = objects_dir(out() / 'previous-union'), objects_dir(first)
    assert all(current.get(k) == v for k, v in previous.items())
    # A documentation change adds asset versions only; the historical audit records must keep their versions.
    historical = [k for k in current if k not in previous and current[k].get('kind', '').startswith('historical')]
    assert not historical, ('historical records gained versions', len(historical))
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in retention_revs():
        expected = objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    header = load(first / 'registry.json')
    inline_before = {o['id']: o for o in json.loads((repo() / DATA / 'registry.json').read_text())['objects']}
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
        target = repo() / DATA / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(repo()).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((repo() / DATA).glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    new_ids = sorted({k[0] for k in new_objects})
    new_asset_paths = sorted(current[k].get('current_path') for k in new_objects if current[k].get('kind') == 'asset')
    largest = max(sizes.items(), key=lambda x: x[1])
    write_new(out() / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
              'retention': retention, 'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind,
              'new_object_ids': new_ids, 'new_asset_version_paths': new_asset_paths,
              'deterministic_double_generation': True, 'hand_written_registry_objects_unchanged': len(inline_before),
              'version_lists': {'ids': len(versions), 'problems': 0,
                                'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
              'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
              'largest_data_file': largest, 'scientific_qualification': False})
    print(json.dumps({'generated_paths': paths, 'new_object_versions': len(new_objects), 'by_kind': by_kind,
                      'new_asset_version_paths': new_asset_paths, 'largest': largest}), flush=True)


def render_outputs():
    sys.path.insert(0, str(repo() / 'evas/capabilities'))
    try:
        renderer = module('docs_sync_render', repo() / 'evas/capabilities/render.py')
        files = renderer.outputs(renderer.registry())
    finally:
        sys.path.pop(0)
    return sorted(Path(p).resolve().relative_to(repo().resolve()).as_posix() for p in files)


def derive():
    assert not (out() / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [PY, '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [PY, '-B', 'evas/capabilities/render.py'], results)
    commit = docs_head()
    paths = changed_vs(commit)
    rendered = set(render_outputs())
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write_new(out() / 'derive-acceptance.json', {'docs_head': commit, 'paths_vs_docs_head': paths, 'render_outputs': len(rendered),
              'checks': results, 'files': {p: sha((repo() / p).read_bytes()) for p in sorted(paths) if (repo() / p).is_file()},
              'scientific_execution': False, 'scientific_qualification': False})
    print(json.dumps({'paths_vs_docs_head': paths}), flush=True)


def message():
    """The catalog commit message; its counts come from the stage receipts."""
    selection = load(out() / 'discovery-selection.json')
    assert (selection['entry_count'], selection['reused'], selection['new_collections']) == (31, 31, 0), selection
    accepted = load(out() / 'generation-acceptance.json')
    by_kind = accepted['new_object_versions_by_kind']
    assert not any(kind.startswith(('historical', 'method')) for kind in by_kind), by_kind
    kinds = ', '.join('%d %s' % (n, kind) for kind, n in sorted(by_kind.items()))
    return ('Regenerate the catalog for the documentation sync\n\n'
            'The edited documents get new asset versions (new object versions: %s);\n'
            'every previous object version is kept. No test module, collector,\n'
            'criteria or DUT path changes, so all 31 discovery entries reuse their\n'
            'archived receipts. Two generations are byte-identical.' % kinds)


def commit():
    assert not (out() / 'commit.json').exists()
    head_commit = docs_head()
    assert docs_diff(head_commit) == EXPECTED_DIFF
    accepted = load(out() / 'derive-acceptance.json')
    paths = changed_vs(head_commit)
    assert paths == accepted['paths_vs_docs_head'], (paths, accepted['paths_vs_docs_head'])
    assert all(sha((repo() / p).read_bytes()) == accepted['files'][p] for p in paths)
    text = message()
    git('add', '--', *paths)
    git('-c', 'commit.gpgsign=false', 'commit', '-q', '-m', text + TRAILER)
    catalog_commit, tree = head()
    assert git('rev-parse', 'HEAD~1').decode().strip() == head_commit and not git('status', '--porcelain=v1').strip()
    write_new(out() / 'commit.json', {'docs_head': head_commit, 'catalog_commit': catalog_commit, 'tree': tree, 'paths': paths,
                                      'message': text, 'at_utc': utc()})
    print(json.dumps({'catalog_commit': catalog_commit, 'tree': tree, 'paths': len(paths)}), flush=True)


def main():
    global ARGS
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('stage', choices=('assets', 'discover', 'union', 'archive', 'generate', 'derive', 'commit'))
    for key, value in DEFAULTS.items():
        parser.add_argument('--' + key.replace('_', '-'), type=type(value) if isinstance(value, int) else Path
                            if isinstance(value, Path) else str, default=value)
    ARGS = parser.parse_args()
    for key in ('main', 'archive_tip'):
        setattr(ARGS, key, git('rev-parse', '--verify', getattr(ARGS, key) + '^{commit}').decode().strip())
    out().mkdir(parents=True, exist_ok=True)
    started = utc()
    globals()[ARGS.stage]()
    print(json.dumps({'stage': ARGS.stage, 'started_at_utc': started, 'finished_at_utc': utc(),
                      'parameters': {k: str(v) for k, v in vars(ARGS).items()}}), flush=True)


if __name__ == '__main__':
    main()

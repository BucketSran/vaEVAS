"""Regenerate the capability catalog for a PR from that PR's own CI artifacts.

Use when a PR changes tests or Rust sources, so its `catalog-inventory` and `rust-regression` jobs fail on drift.
Inputs are the artifacts of one CI run whose checkout tree equals the PR head tree:
  --ci-dir      directory holding the downloaded `catalog-inventory/` and `rust-test-listing/` artifacts
  --repo        clean checkout at the PR head (its catalog data must equal --main's)
  --main        main commit the PR sits on; its catalog is the previous union, every object version is kept
  --candidates  construction config of the catalog now on --main (receipts reused when the owned methods match)
  --archive-tip tip of codex/evas-method-audit-archive-20261025 the new archive commit extends
  --prefix      archive directory for this PR's new receipts
  --out         new working directory
Stages: prepare (assets, discovery selection, archive commit, config), generate (twice, byte-identical, retention),
derive (traceability + render). Push the archive commit as a fast-forward of the archive branch before PR CI.
No test body, simulator or kernel runs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

DATA = 'evas/capabilities/data/'
METHOD_KEYS = ('module_path', 'runtime_id', 'module_sha256', 'definition', 'generated')
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
IDENTITY = {'GIT_AUTHOR_NAME': 'BucketSran', 'GIT_AUTHOR_EMAIL': '138781625+BucketSran@users.noreply.github.com',
            'GIT_COMMITTER_NAME': 'BucketSran', 'GIT_COMMITTER_EMAIL': '138781625+BucketSran@users.noreply.github.com'}
A = None


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return sha(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode())


def load(path):
    return json.loads(Path(path).read_bytes())


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return path


def git(*args, index=None, data=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')} | IDENTITY | {'LC_ALL': 'C'}
    if index is not None:
        env['GIT_INDEX_FILE'] = str(index)
    return subprocess.run(['git', '-C', str(A.repo), *args], env=env, input=data, check=True,
                          stdout=subprocess.PIPE).stdout


def tree_entries(rev):
    rows = {}
    for item in git('ls-tree', '-r', '-z', rev).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            rows[path.decode()] = (mode, oid)
    return rows


def objects_in(header, read):
    result = list(header['objects'])
    for part in header['object_parts']:
        result += read(part)['objects']
    return {(o['id'], o['version']): o for o in result}


def objects_dir(path):
    path = Path(path)
    return objects_in(load(path / 'registry.json'), lambda name: load(path / name))


def objects_at(rev):
    return objects_in(json.loads(git('show', rev + ':' + DATA + 'registry.json')),
                      lambda name: json.loads(git('show', rev + ':' + DATA + name)))


def owned(receipt):
    return canonical(dict(collector=receipt['collector'].get('sha256'),
                          methods=sorted(({k: m.get(k) for k in METHOD_KEYS} for m in receipt['methods']),
                                         key=lambda m: (m['module_path'], m['runtime_id']))))


def prepare():
    out, ci = A.out, A.ci_dir
    assert not out.exists(), out
    out.mkdir(parents=True)
    assert not git('status', '--porcelain=v1').strip(), 'checkout must be clean'
    head = git('rev-parse', 'HEAD').decode().strip()
    tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
    edited = git('diff', '--name-only', A.main, head, '--', DATA).decode().split()
    assert set(edited) <= {DATA + 'registry.json'}, ('PR edits generated catalog parts', edited)
    union = out / 'previous-union'
    union.mkdir()
    main_header = json.loads(git('show', A.main + ':' + DATA + 'registry.json'))
    for name in ['registry.json', *main_header['object_parts']]:
        (union / name).write_bytes(git('show', A.main + ':' + DATA + name))

    observed = load(ci / 'catalog-inventory/assets-before.json')
    assert observed['source_tree'] == tree and not observed['dirty_paths'], (observed['source_tree'], tree)
    entries = tree_entries(head)
    assert {r['path'] for r in observed['assets']} == set(entries)
    rows = []
    for r in observed['assets']:
        mode, oid = entries[r['path']]
        assert (r['git_mode'], r['observed_blob_oid'], r['index_blob_oid']) == (mode, oid, oid), r['path']
        rows.append({'path': r['path'], 'sha256': r['sha256'], 'git_mode': mode, 'actual_mode': r['actual_mode'],
                     'git_blob_oid': oid})
    assets = dict(schema_version=1, producer='ci-observation-verified-against-head-tree', source_commit=head,
                  source_tree=tree, source_object_format='sha1', source_kind='immutable-export',
                  source_profile='git-tree-regular-blobs-v1', source_availability='local-only-before-publication',
                  content_binding='verified-git-blob-oids', scope=observed['scope'], assets=rows,
                  ci_observation=dict(path='catalog-inventory/assets-before.json',
                                      sha256=sha((ci / 'catalog-inventory/assets-before.json').read_bytes()),
                                      source_commit=observed['source_commit']))
    dump(out / 'archive-files' / A.prefix / 'assets.json', assets)

    config = load(A.candidates)
    candidates = []
    for item in config['discoveries']:
        value = load(item['entry_file'])
        candidates.append((item['entry_file'], value, config['discovery_source_locators'][value['entry']['entry_id']]))
    asset_sha = {r['path']: r['sha256'] for r in rows}
    selection, new_files = [], []
    for path in sorted((ci / 'catalog-inventory').glob('entry-*.json')):
        value = load(path)
        r = value['receipt']
        assert r['complete'] and not r['errors'] and not r['unresolved_instances'], path
        assert all(asset_sha.get(m['module_path']) == m['module_sha256'] for m in r['methods']), path
        match = [c for c in candidates if c[1]['entry'] == value['entry'] and owned(c[1]['receipt']) == owned(r)]
        assert len(match) <= 1, path
        if match:
            selection.append(dict(entry_id=value['entry']['entry_id'], entry_file=match[0][0], reused=True,
                                  source_locator=match[0][2]))
        else:
            rel = A.prefix + '/new-discovery/' + path.name
            (out / 'archive-files' / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, out / 'archive-files' / rel)
            new_files.append(rel)
            selection.append(dict(entry_id=value['entry']['entry_id'], entry_file=str(out / 'archive-files' / rel),
                                  reused=False, archive_path=rel))
    assert len(selection) == len(candidates), (len(selection), len(candidates))

    rust_old = config['rust_listings'][0]
    old_source = load(rust_old['receipt_file'])['source']
    listing = ci / 'rust-test-listing/rust-test-listing.json'
    if listing.exists():
        rust_new = load(listing)
    else:
        rust_files = {r['path']: r['sha256'] for r in rows if r['path'].startswith('evas/rust_core/')}
        assert rust_files == {r['path']: r['sha256'] for r in old_source['files']}, 'Rust changed; supply the CI listing'
        rust_new = dict(source=old_source)
    if rust_new['source'] == old_source:
        rust = dict(rust_old, reused=True)
    else:
        rel = A.prefix + '/rust-listing/rust-test-listing.json'
        (out / 'archive-files' / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ci / 'rust-test-listing/rust-test-listing.json', out / 'archive-files' / rel)
        rust = dict(receipt_file=str(out / 'archive-files' / rel), profile=rust_old['profile'], reused=False, archive_path=rel)

    reused = sum(s['reused'] for s in selection)
    dump(out / 'archive-files' / A.prefix / 'discovery-selection.json',
         dict(head=head, main=A.main, entries=selection, reused=reused, new=len(selection) - reused, rust=rust,
              test_bodies_executed=False, scientific_qualification=False))
    shutil.copyfile(__file__, out / 'archive-files' / A.prefix / Path(__file__).name)
    (out / 'archive-files' / A.prefix / 'README.md').write_text(
        '# Catalog inputs for %s\n\nHead %s on main %s; parent archive %s. %d of %d discovery entries reuse archived '
        'receipts, %d come from the PR CI artifacts; Rust listing %s. Scientific qualification is false.\n'
        % (A.label, head[:8], A.main[:8], A.archive_tip[:8], reused, len(selection), len(selection) - reused,
           'reused' if rust['reused'] else 'new'))

    index = out / 'archive.index'
    git('read-tree', A.archive_tip, index=index)
    for p in sorted((out / 'archive-files').rglob('*')):
        if p.is_file():
            oid = git('hash-object', '-w', '--stdin', data=p.read_bytes()).decode().strip()
            git('update-index', '--add', '--cacheinfo', '100644,%s,%s' % (oid, p.relative_to(out / 'archive-files').as_posix()),
                index=index)
    archive_tree = git('write-tree', index=index).decode().strip()
    index.unlink()
    archived = git('commit-tree', archive_tree, '-p', A.archive_tip, '-m',
                   'Archive the catalog inputs of ' + A.label + TRAILER).decode().strip()

    def locator(rel):
        return {'kind': 'git-object', 'repository': 'vaevas', 'revision': archived, 'path': rel}
    config.update(source_root=str(A.repo), archive_repository=str(A.repo), source_repositories={'vaevas': str(A.repo)},
                  previous_data_dir=str(out / 'previous-union'), asset_receipt=str(out / 'archive-files' / A.prefix / 'assets.json'),
                  discoveries=[], discovery_source_locators={})
    for s in selection:
        config['discoveries'].append({'entry_file': s['entry_file']})
        config['discovery_source_locators'][s['entry_id']] = s['source_locator'] if s['reused'] else locator(s['archive_path'])
    config['rust_listings'] = [{k: rust[k] for k in ('receipt_file', 'profile', 'source_locator')}] if rust['reused'] else \
        [dict(receipt_file=rust['receipt_file'], profile=rust['profile'], source_locator=locator(rust['archive_path']))]
    dump(out / 'config.json', config)
    dump(out / 'archive.json', dict(commit=archived, tree=archive_tree, parent=A.archive_tip, prefix=A.prefix))
    print(json.dumps(dict(archive=archived, reused=reused, new=len(selection) - reused, new_files=new_files,
                          rust='reused' if rust['reused'] else 'new')))


def generate():
    out = A.out
    py = sys.executable
    for name in ('catalog', 'catalog-repeat'):
        with (out / (name + '.stderr')).open('wb') as err:
            subprocess.run([py, '-B', 'scripts/capabilities/generate_catalog.py', '--config', str(out / 'config.json'),
                            '--output', str(out / name)], cwd=A.repo, check=True, stdout=subprocess.DEVNULL, stderr=err)
    first, second = out / 'catalog/tree' / DATA, out / 'catalog-repeat/tree' / DATA
    files = {p.name: p.read_bytes() for p in first.glob('*.json')}
    assert files == {p.name: p.read_bytes() for p in second.glob('*.json')}, 'generation is not deterministic'
    previous, current = objects_at(A.main), objects_dir(first)
    assert all(current.get(k) == v for k, v in previous.items()), 'a previous object version was lost or rewritten'
    header = load(first / 'registry.json')
    versions = {}
    for i, v in current:
        versions.setdefault(i, set()).add(v)
    for i, vs in versions.items():
        new = vs - {v for (j, v) in previous if j == i}
        assert len(new) <= 1 and (not new or header['current'].get(i) in new), i
    changed = []
    for name, raw in sorted(files.items()):
        target = A.repo / DATA / name
        if not target.exists() or target.read_bytes() != raw:
            target.write_bytes(raw)
            changed.append(name)
    new = [k for k in current if k not in previous]
    kinds = {}
    for k in new:
        kinds[current[k]['kind']] = kinds.get(current[k]['kind'], 0) + 1
    sizes = {p.name: p.stat().st_size for p in (A.repo / DATA).glob('*.json')}
    dump(out / 'generation-acceptance.json', dict(changed=changed, retained=len(previous), new_by_kind=kinds,
                                                  largest=max(sizes.items(), key=lambda x: x[1])))
    print(json.dumps(dict(changed=changed, retained=len(previous), new_by_kind=kinds)))


def derive():
    py = sys.executable
    for argv in (['scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], ['evas/capabilities/render.py']):
        subprocess.run([py, '-B', *argv], cwd=A.repo, check=True, stdout=subprocess.DEVNULL)
    print(git('status', '--short').decode())


def main():
    global A
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('stage', choices=('prepare', 'generate', 'derive'))
    for name in ('ci-dir', 'repo', 'candidates', 'out'):
        p.add_argument('--' + name, type=lambda s: Path(s).resolve(), required=True)
    for name in ('main', 'archive-tip', 'prefix', 'label'):
        p.add_argument('--' + name, required=True)
    A = p.parse_args()
    A.main = git('rev-parse', '--verify', A.main + '^{commit}').decode().strip()
    A.archive_tip = git('rev-parse', '--verify', A.archive_tip + '^{commit}').decode().strip()
    globals()[A.stage]()


if __name__ == '__main__':
    main()

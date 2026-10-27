"""Register the Rust listing observed with the fixed toolchain on top of PR6 head 93ec69a4 (catalog only).

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
BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
BASE_TREE = 'a68a89e1c145767f830fd5d602ab1be9f96b6b90'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
PREFIX = 'evas/capabilities/observations/pr6-rust-listing-r4-20261027'
R3 = B / 'pr6/rebind-r3-20261027'
PARENT = '93ec69a4352710b26209bd18cf4bda7d1ecfc95d'
PARENT_TREE = 'e05e011a65d99e3e0107b72ac6a2430742af0897'
OBSERVED = R3 / 'ci-40520607138/catalog-inventory/assets-before.json'
RECEIPT = R3 / 'rust-listing-40520607138/artifact/rust-test-listing.json'
PROFILE = 'linux-x86_64-regression-opt1-v1'
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


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', PARENT + '^{tree}').decode().strip() == PARENT_TREE
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W),
                                     'archive', PARENT], env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pr6-r4'], cwd=S, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', PARENT, source=True)
    git('update-ref', 'HEAD', PARENT, source=True)
    invariant()
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    receipt = load(RECEIPT)
    assert receipt['complete'] and not receipt['errors']
    assert {k: receipt['toolchain'][k]['argv'] for k in ('rustc', 'cargo')} == {'rustc': ['rustc', '-vV'], 'cargo': ['cargo', '--version']}
    observed = load(OBSERVED)
    assert observed['source_tree'] == PARENT_TREE and not observed['dirty_paths']
    entries = task.entries(PARENT)
    rows = []
    for row in observed['assets']:
        mode, oid = entries[row['path']]
        assert (row['git_mode'], row['observed_blob_oid'], row['index_blob_oid']) == (mode, oid, oid), row['path']
        rows.append({'path': row['path'], 'sha256': row['sha256'], 'git_mode': mode, 'actual_mode': row['actual_mode'], 'git_blob_oid': oid})
    assert len(rows) == len(entries)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': PARENT, 'source_tree': PARENT_TREE, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'published', 'content_binding': 'verified-git-blob-oids',
          'scope': observed['scope'], 'assets': rows, 'reuse_proof': {'actual_CI': 40520607138, 'observation': str(OBSERVED), 'unchanged': len(rows), 'changed': []}})
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'parent': PARENT, 'parent_tree': PARENT_TREE,
          'receipt': str(RECEIPT), 'receipt_sha256': sha(RECEIPT.read_bytes()), 'receipt_run': 40520607138,
          'receipt_platform': receipt['environment']['platform'], 'before': before, 'after': after, 'published': False,
          'scientific_execution': False, 'semantic_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'assets': len(rows), 'receipt_platform': receipt['environment']['platform']}), flush=True)


def remote_archive():
    line = git('ls-remote', 'origin', ARCHIVE_REF).decode().split()
    assert len(line) == 2 and line[1] == ARCHIVE_REF, line
    return line[0]


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = remote_archive()
    dest = D / 'archive-files' / PREFIX
    (dest / 'rust-listing').mkdir(parents=True)
    shutil.copyfile(RECEIPT, dest / 'rust-listing/rust-test-listing.json')
    shutil.copyfile(R3 / 'rust-listing-40520607138/summary.json', dest / 'rust-listing/summary.json')
    shutil.copyfile(__file__, dest / 'prepare_pr6_r4.py')
    (dest / 'README.md').write_text('# Rust listing observed with the fixed toolchain\n\n'
        'Native listing from the rust-regression job of CI 40520607138 on PR6 head 93ec69a4: rustc and cargo queried '
        'without a toolchain argument under RUSTUP_TOOLCHAIN 1.99.1. It replaces the earlier +stable receipt as the '
        'registered listing; the catalog keeps every earlier object version. Scientific qualification is false.\n')
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive the Rust listing observed with the fixed toolchain').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R3 / 'config.json')
    old_listings = config['rust_listings']
    assert [x['profile'] for x in old_listings] == [PROFILE]
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)},
                  rust_listings=[{'receipt_file': str(RECEIPT), 'profile': PROFILE,
                                  'source_locator': {'kind': 'git-object', 'repository': 'vaevas', 'revision': head,
                                                     'path': PREFIX + '/rust-listing/rust-test-listing.json'}}])
    write(D / 'config.json', config)
    write(D / 'rust-listing-change.json', {'old': old_listings, 'new': config['rust_listings']})
    invariant()
    print(json.dumps({'archive': head, 'parent': parent, 'files': len(files)}), flush=True)


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
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'objects': report['objects']}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    delta = changed_vs(PARENT)
    rendered = set(render_outputs())
    assert set(delta) <= rendered | DERIVED_DATA, sorted(set(delta) - rendered - DERIVED_DATA)
    write(D / 'derive-acceptance.json', {'parent': PARENT, 'delta_vs_parent': delta, 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(delta) if (S / p).is_file()},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'delta_vs_parent': delta}), flush=True)


def freeze():
    invariant()
    der = load(D / 'derive-acceptance.json')
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    final = task.make_commit(PARENT, der['delta_vs_parent'], 'Register the Rust listing observed with the fixed toolchain' + TRAILER, 'final')
    git('merge-base', '--is-ancestor', PARENT, final['commit'])
    complete = sorted(git('diff', '--name-only', BASE, final['commit']).decode().splitlines())
    final.update(base=BASE, parent=PARENT, complete_paths=complete, delta_vs_parent=der['delta_vs_parent'], derive=str(D / 'derive-acceptance.json'),
                 precheck='runs on the frozen head in parallel with CI', CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', PARENT, final['commit']))
    git('read-tree', final['commit'], source=True)
    git('update-ref', 'HEAD', final['commit'], source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'delta_vs_parent': len(der['delta_vs_parent'])}), flush=True)


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
          'focused': False, 'scope': 'PR6 Rust listing registration quick maintenance gate; full scientific regression is CI only.'})
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
    parser.add_argument('stage', choices=['source', 'archive', 'generate', 'derive', 'freeze', 'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

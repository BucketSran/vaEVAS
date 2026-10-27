"""Rebind the reviewed PR266 consumer migration onto main after its context was adopted (PR267, PR268).

Stages write new receipts and refuse to replace them. Only task scratch, Git objects and
the private export are writable; the real worktree, index, branch and 20 old candidates stay
unchanged. No test bodies, simulator or backend run here; full regression is CI only.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile

D = Path(__file__).resolve().parent
X = D.parent
B = X.parents[1]
S = D / 'source'
F = B / 'pr5/comparison-continuation-fix-20261027/fixture-root-finalization'
OLD_PR = '983b1ef6a4804c29483279ca34a7a92fce56a858'
OLD_PR_TREE = '7a99e40b4a58e00c138e4c721f3deaab1bdb2ba6'
OLD_BASE = 'e10e1af5796f0cc7af3b6b5f5d26c420c0c03325'
BASE_TREE = 'b531c9d1f2fbdf6f4ea9c5d3aafb6c0fa55e741e'
REAL_HEAD = '168a9d7a4305e7ce21d1577b4ca1dda65beae4ce'
E1 = X / 'bundle-bound/report.json'
E1_SHA = '531016babc8a288fd130f3af99364dbcaf20f25c225201d1f35e73e6b0a6c995'
OBSERVED = X / 'ci-40467108985/artifacts/catalog-inventory/assets-before.json'
PREFIX = 'evas/capabilities/observations/pr5-activation-rebind-20261027'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
BASELINE = 'evas/validation/baselines/regression-v1.json'
GENERATED = {
    'evas/capabilities/data/asset-index.json',
    'evas/capabilities/data/catalog-sources.json',
    'evas/capabilities/data/entrypoint-index.json',
    'evas/capabilities/data/historical-index.json',
    'evas/capabilities/data/method-index.json',
    'evas/capabilities/data/registry.json',
    'evas/capabilities/generated/normative.md',
    'evas/docs/development/TRACEABILITY.md',
}
TRUST_FILES = {BASELINE, 'evas/validation/baselines/regression-v1.review.json', 'scripts/context-registration-bundle.json'}
COLLECTORS = ('run_regression.py', 'ci_evidence.py', 'regression_reason_identity.py', 'regression_observation_policy.json',
              'regression_gate.py', 'run_trusted_regression_gate.py', 'regression_context_registration.py')
spec = importlib.util.spec_from_file_location('prior_c0_construction', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
PY = task.PY
git, write, sha = task.git, task.write, task.sha


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}


def merged_base():
    merge = load(X / 'baseline-merge-20261027/merge-verification.json')
    assert merge['tree'] == BASE_TREE and merge['exact_reviewed_and_CI_tree'] and merge['baseline_append_adopted']
    return merge['merge_commit']


BASE = merged_base()
task.S, task.OUT, task.BASE = S, D, BASE


def module(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(s)
    s.loader.exec_module(result)
    return result


def guard():
    assert git('rev-parse', '--show-toplevel').decode().strip() == str(task.W)
    assert git('rev-parse', 'HEAD').decode().strip() == REAL_HEAD
    assert not git('diff', '--cached', '--name-only').strip()
    plan = load(B / 'main-plan.json')
    rows = [r for r in plan['handoff']['files'] if r['path'].startswith('evas/tests/')]
    assert len(rows) == 20
    for row in rows:
        assert sha((task.W / row['path']).read_bytes()) == row['sha256'], row['path']
    config = task.W.parents[1] / 'current/.git/config'
    assert sha(config.read_bytes()) == '2365548f0cb7f5b21311860afc37dc5a8f41d775b667f50ec8a678eb22a3d7aa'
    return {'head': REAL_HEAD, 'index_sha256': sha((task.GD / 'index').read_bytes()),
            'shared_config_sha256': sha(config.read_bytes()), 'old_candidates': rows}


def invariant():
    task.preserved()
    assert S.resolve().is_relative_to(D.resolve())


def show(rev, path):
    return git('show', rev + ':' + path) if git('ls-tree', rev, '--', path).strip() else None


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    assert git('rev-parse', OLD_PR + '^{tree}').decode().strip() == OLD_PR_TREE
    git('merge-base', '--is-ancestor', OLD_BASE, BASE)
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        p = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', f'--git-dir={task.GD}', f'--work-tree={task.W}', 'archive', '--format=tar', BASE],
                             env=env(), stdout=subprocess.PIPE, stderr=err)
        with tarfile.open(fileobj=p.stdout, mode='r|') as archive:
            archive.extractall(S, filter='data')
        assert p.wait() == 0
    assert not (S / '.git').exists()
    changes = git('diff', '--name-only', OLD_BASE, OLD_PR).decode().splitlines()
    assert len(changes) == 29
    source_paths = sorted(set(changes) - GENERATED)
    assert len(source_paths) == 22
    main_changes = set(git('diff', '--name-only', OLD_BASE, BASE).decode().splitlines())
    assert not main_changes & set(source_paths), sorted(main_changes & set(source_paths))
    old_entries = task.entries(OLD_PR)
    rows = []
    for path in source_paths:
        base_raw, old_base_raw, accepted = show(BASE, path), show(OLD_BASE, path), git('show', OLD_PR + ':' + path)
        assert base_raw == old_base_raw, path
        target = S / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(accepted)
        target.chmod(0o755 if old_entries[path][0] == '100755' else 0o644)
        rows.append({'path': path, 'accepted_983b_sha256': sha(accepted), 'resolved_sha256': sha(accepted),
                     'base_sha256': sha(base_raw) if base_raw is not None else None, 'git_mode': old_entries[path][0],
                     'changed_from_base': base_raw != accepted, 'resolution': 'Exact accepted 983b source; main unchanged since e10'})
    retained = {}
    for path in sorted(GENERATED | TRUST_FILES):
        raw = (S / path).read_bytes()
        assert raw == git('show', BASE + ':' + path), path
        retained[path] = sha(raw)
    sys.path.insert(0, str(S / 'scripts'))
    runner = module('rebind_runner', S / 'scripts/run_regression.py')
    gate = module('rebind_gate', S / 'scripts/regression_gate.py')
    assert sha(E1.read_bytes()) == E1_SHA
    report = load(E1)
    criteria = runner.file_manifest(S, ('evas/tests', 'evas/validation', 'evas/examples', 'experiments'))
    dut = runner.file_manifest(S, ('evas/src', 'evas/rust_core'))
    assert criteria == report['source_identity']['criteria_files']
    assert dut == report['source_identity']['dut_files']
    assert runner.json_digest(criteria) == report['metadata']['criteria_id']
    baseline = load(S / BASELINE)
    registered = [i for i, c in enumerate(baseline['contexts']) if c['context'] == gate._context(report)]
    assert registered == [len(baseline['contexts']) - 1] == [3], registered
    collectors = {}
    for name in COLLECTORS:
        path = 'scripts/' + name
        data = (S / path).read_bytes()
        assert data == git('show', OLD_PR + ':' + path) == git('show', BASE + ':' + path), path
        collectors[path] = sha(data)
    inventory = module('rebind_inventory', S / 'scripts/capabilities/collect_ci_inventory.py')
    actual = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    accepted = inventory.parse_workflow(git('show', OLD_PR + ':' + inventory.WORKFLOW))
    assert actual == accepted
    write(D / 'workflow-declarations.json', actual)
    check = subprocess.run([sys.executable, '-B', str(task.W / 'scripts/check_workspaces.py'), '--repo', str(task.W),
                            '--report', str(D / 'workspaces-prepared.json')], env=env(), cwd=task.W, capture_output=True)
    (D / 'workspaces.stdout').write_bytes(check.stdout)
    (D / 'workspaces.stderr').write_bytes(check.stderr)
    assert check.returncode == 0, check.stderr.decode()
    after = guard()
    assert before == after
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'old_pr': OLD_PR, 'old_pr_tree': OLD_PR_TREE, 'old_base': OLD_BASE, 'source_paths': rows,
          'changed_paths': sum(r['changed_from_base'] for r in rows), 'main_changes_since_old_base': sorted(main_changes),
          'source_root': str(S), 'retained_base_files': retained, 'deferred_generated_paths': sorted(GENERATED),
          'criteria_file_count': len(criteria), 'criteria_id': runner.json_digest(criteria),
          'dut_file_count': len(dut), 'dut_id': runner.json_digest(dut), 'criteria_and_DUT_equal_registered_context': True,
          'registered_context_index': 3, 'E1_raw': str(E1), 'E1_raw_sha256': E1_SHA, 'collector_files': collectors,
          'workflow_declarations_exact_983b': True, 'before': before, 'after': after, 'published': False,
          'scientific_execution': False, 'semantic_qualification': False,
          'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'source_paths': len(rows), 'criteria_id': runner.json_digest(criteria), 'registered_context_index': 3}), flush=True)


def capture():
    prep = load(D / 'source-preparation.json')
    assert prep['base'] == BASE and not (S / '.git').exists() and not (D / 'capture.json').exists()
    for row in prep['source_paths']:
        assert sha((S / row['path']).read_bytes()) == row['resolved_sha256'], row['path']
    for path, digest in prep['retained_base_files'].items():
        assert sha((S / path).read_bytes()) == digest, path
    private_env = env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull}
    subprocess.run(['/usr/bin/git', 'init', '--quiet', '--template=', '--initial-branch=pr266-rebind', str(S)], env=private_env, check=True)
    common = Path(git('rev-parse', '--git-common-dir').decode().strip())
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    paths = sorted(row['path'] for row in prep['source_paths'] if row['changed_from_base'])
    modes = {row['path']: row['git_mode'] for row in prep['source_paths']}
    actual = set(git('diff', '--name-only', source=True).decode().splitlines()) | set(git('ls-files', '--others', '--exclude-standard', source=True).decode().splitlines())
    assert actual == set(paths), sorted(actual ^ set(paths))
    index = D / 'capture.index'
    assert not index.exists()
    git('read-tree', BASE, index=index)
    old_entries = task.entries(OLD_PR)
    files = {}
    for path in paths:
        raw = (S / path).read_bytes()
        assert (S / path).stat().st_mode & 0o777 == (0o755 if modes[path] == '100755' else 0o644)
        oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
        assert (modes[path], oid) == old_entries[path], path
        git('update-index', '--add', '--cacheinfo', modes[path] + ',' + oid + ',' + path, index=index)
        files[path] = sha(raw)
    tree = git('write-tree', index=index).decode().strip()
    head = git('commit-tree', tree, '-p', OLD_PR, '-p', BASE, '-m', 'Bind reviewed consumer migration to the adopted observation context' + TRAILER).decode().strip()
    index.unlink()
    git('merge-base', '--is-ancestor', OLD_PR, head)
    git('merge-base', '--is-ancestor', BASE, head)
    assert set(git('diff', '--name-only', BASE, head).decode().splitlines()) == set(paths)
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, BASE, source=True)
    write(D / 'capture.json', {'base': BASE, 'commit': head, 'tree': tree, 'parents': [OLD_PR, BASE],
          'paths': paths, 'files': files, 'non_force_successor_of_PR266': True, 'scientific_qualification': False})
    (D / 'source.patch').write_bytes(git('diff', '--binary', BASE, head))
    (D / 'source.commit').write_bytes(git('cat-file', 'commit', head))
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(BASE), task.entries(head)
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
    assert changed == paths
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': head, 'source_tree': tree, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': rows,
          'reuse_proof': {'actual_CI': 40467108985, 'verification': str(X / 'ci-40467108985/raw-verification.json'),
                          'unchanged': len(rows) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'capture': head, 'tree': tree, 'paths': len(paths), 'assets': len(rows)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    config = load(F / 'config.json')
    candidates = {}
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = load(D / 'capture.json')['commit']
    inventory = module('rebind_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assert len(entries) == 31
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    chosen = []
    for entry in entries:
        matching = []
        for path, value, locator in candidates.values():
            r = value['receipt']
            if value['entry'] != entry or not r['complete'] or r['errors'] or r['unresolved_instances']:
                continue
            if assets.get(r['collector']['path']) != r['collector']['sha256']:
                continue
            if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                continue
            matching.append((path, value, locator))
        assert len(matching) == 1, entry['entry_id']
        path, value, locator = matching[0]
        assert git('show', locator['revision'] + ':' + locator['path']) == path.read_bytes()
        chosen.append({'entry_file': str(path), 'entry_id': entry['entry_id'], 'reused': True, 'source_locator': locator,
                       'sha256': sha(path.read_bytes()), 'instances': value['receipt']['discovered_instances'],
                       'start': entry['start'], 'pattern': entry['pattern']})
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen), 'new_collections': 0,
          'reuse_basis': 'Exact workflow entry, collector and owner module bytes equal accepted 983b receipts; original identity retained.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen), 'new_collections': 0}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = load(X / 'c0-candidate/archive.json')['commit']
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'source.patch', 'source.commit', 'discovery-selection.json', 'source-preparation.json'):
        shutil.copyfile(D / name, dest / name)
    shutil.copyfile(__file__, dest / 'prepare_rebind.py')
    (dest / 'README.md').write_text('# Consumer-migration activation rebind\n\n'
        'The exact context authority (#267) and baseline append (#268) have merged. This capture merges main into the reviewed '
        'PR266 head without changing any reviewed source byte: the 22 source paths equal 983b1ef6 and main had not changed them since e10e1af5. '
        'Criteria and DUT manifests equal the registered context of CI 40454789703. All 31 discovery receipts are reused by exact '
        'workflow, collector and owner-module hashes. No test bodies or simulator run here. Catalog generation, precheck, candidate CI '
        'and merged-tree verification remain separate. Scientific qualification is false.\n')
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive consumer-migration activation rebind construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(F / 'config.json')
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(S / 'evas/capabilities/data'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={})
    for row in load(D / 'discovery-selection.json')['entries']:
        config['discoveries'].append({'entry_file': row['entry_file']})
        config['discovery_source_locators'][row['entry_id']] = row['source_locator']
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
        if p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous),
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous)}), flush=True)


def precheck():
    invariant()
    assert not (D / 'precheck-acceptance.json').exists()
    results = []
    e = env() | {'CARGO_TARGET_DIR': str(B / 'pr4/bootstrap-integration-20261026/precheck-rust-target')}

    def run(name, argv):
        start = datetime.now(timezone.utc).isoformat()
        with (D / name).open('x') as out:
            out.write('COMMAND ' + repr(argv) + '\n')
            out.flush()
            r = subprocess.run(argv, cwd=S, env=e, stdout=out, stderr=subprocess.STDOUT)
            out.write('\nreturncode=' + str(r.returncode) + '\n')
        results.append({'command': argv, 'receipt': str(D / name), 'returncode': r.returncode,
                        'started_at_utc': start, 'finished_at_utc': datetime.now(timezone.utc).isoformat()})
        print(name, r.returncode, flush=True)
        assert r.returncode == 0, name

    run('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'])
    run('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'])
    paths = git('diff', '--name-only', BASE, source=True).decode().splitlines()
    allowed = set(load(D / 'capture.json')['paths']) | GENERATED
    assert set(paths) <= allowed, sorted(set(paths) - allowed)
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths),
          'focused': False, 'scope': 'Complete PR266 rebind quick maintenance gate; full scientific regression is CI only.'})
    run('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')])
    run('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'])
    run('affected-catalog-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_catalog_history_selection.py', '-v'])
    run('affected-inventory-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_ci_inventory.py', '-v'])
    run('affected-selection-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_ci_selection.py', '-v'])
    run('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE])
    write(D / 'precheck-acceptance.json', {'base': BASE, 'source_capture': load(D / 'capture.json')['commit'],
          'paths': paths, 'checks': results, 'files': {p: sha((S / p).read_bytes()) for p in paths},
          'accepted_source_review': str(F / 'review-r3-acceptance.json'),
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def workflow():
    invariant()
    assert not (D / 'activation-workflow-acceptance.json').exists()
    out = D / 'activation-workflow'
    out.mkdir()
    assert sha(E1.read_bytes()) == load(D / 'source-preparation.json')['E1_raw_sha256']
    (S / 'runs').mkdir(exist_ok=True)
    target = S / 'runs/python-regression.json'
    assert not target.exists()
    shutil.copyfile(E1, target)
    sys.path.insert(0, str(S / 'scripts/tests'))
    support = module('rebind_admission_shell', S / 'scripts/tests/test_regression_admission.py')
    body = support.AdmissionIntegrationTests().run_body('regression-admission', 'Compare raw observations with the trusted comparator')
    assert body == (X / 'baseline-append-20261027/workflow-check/actual-workflow.sh').read_text()
    (out / 'actual-workflow.sh').write_text(body)
    write(out / 'event.json', {'repository': {'full_name': 'BucketSran/vaEVAS', 'default_branch': 'main'},
          'pull_request': {'base': {'sha': BASE, 'ref': 'main', 'repo': {'full_name': 'BucketSran/vaEVAS'}}}})
    (out / 'bin').mkdir()
    (out / 'bin/python3').symlink_to(PY)
    runtime = env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                       'PATH': str(out / 'bin') + os.pathsep + os.environ['PATH'], 'GITHUB_EVENT_NAME': 'pull_request',
                       'GITHUB_EVENT_PATH': str(out / 'event.json')}
    with (out / 'stdout').open('xb') as stdout, (out / 'stderr').open('xb') as stderr:
        run = subprocess.run(['bash', '-e', str(out / 'actual-workflow.sh')], cwd=S, env=runtime, stdout=stdout, stderr=stderr, timeout=300)
    assert run.returncode == 0, (out / 'stderr').read_text()
    admission = load(S / 'runs/regression-admission.json')
    bundle = load(S / 'runs/regression-bundle-source.json')
    assert admission['merge_allowed'] and not admission['differences']
    assert admission['raw_successful'] is admission['semantic_qualification'] is False
    assert admission['trust']['trusted_commit'] == BASE
    assert bundle['requested'] is bundle['materialized'] is False
    write(D / 'activation-workflow-acceptance.json', {'base': BASE, 'source_capture': load(D / 'capture.json')['commit'],
          'existing_E1_raw': str(E1), 'existing_E1_raw_sha256': E1_SHA, 'same_production_shell': True,
          'returncode': run.returncode, 'merge_allowed': True, 'trusted_baseline_contains_exact_E1_context': True,
          'bundle_requested': False,
          'reports': {name: sha((S / 'runs' / name).read_bytes()) for name in ('regression-admission.json', 'regression-bootstrap-source.json', 'regression-bundle-source.json')},
          'scientific_execution': False, 'scientific_qualification': False, 'new_candidate_CI_still_required': True})
    invariant()
    print(json.dumps({'activation_workflow': 'passed', 'trusted_base': BASE, 'bundle_requested': False, 'scientific_execution': False}), flush=True)


def freeze():
    invariant()
    cap, pre = load(D / 'capture.json'), load(D / 'precheck-acceptance.json')
    assert load(D / 'activation-workflow-acceptance.json')['merge_allowed']
    assert all(row['returncode'] == 0 for row in pre['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in pre['files'].items())
    generated = git('diff', '--name-only', cap['commit'], source=True).decode().splitlines()
    assert set(generated) <= GENERATED, sorted(set(generated) - GENERATED)
    final = task.make_commit(cap['commit'], generated, 'Refresh bound consumer-migration catalog and views' + TRAILER, 'final')
    git('merge-base', '--is-ancestor', OLD_PR, final['commit'])
    git('merge-base', '--is-ancestor', BASE, final['commit'])
    source_paths = [r['path'] for r in load(D / 'source-preparation.json')['source_paths']]
    for path in source_paths:
        assert git('rev-parse', final['commit'] + ':' + path) == git('rev-parse', OLD_PR + ':' + path), path
    final.update(base=BASE, source_capture=cap['commit'], complete_paths=pre['paths'], precheck=str(D / 'precheck-acceptance.json'),
                 review_reuse='Astra R3 accepted the 983b source (Standards/Spec []); r4 accepted the exact context now merged. '
                              'This delta keeps every reviewed source byte and adds only regenerated derived metadata on merged main.',
                 CI='pending', published=False, scientific_qualification=False)
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch').write_bytes(git('diff', '--binary', BASE, final['commit']))
    invariant()
    print(json.dumps({'commit': final['commit'], 'tree': final['tree'], 'paths': len(pre['paths']), 'CI': 'pending'}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'capture', 'discover', 'archive', 'generate', 'precheck', 'workflow', 'freeze'])
    globals()[parser.parse_args().stage]()

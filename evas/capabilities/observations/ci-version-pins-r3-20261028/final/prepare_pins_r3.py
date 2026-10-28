"""PR273 r3: merge main (PR6 and its context registration) into the CI version pins, apply the r2/r3 fixes, regenerate the catalog.

Commits: a merge commit (parents 9ea5de9f, main bf2ec410) whose source bytes are the reviewed worker resolution (PR273-only paths
keep 9ea5de9f bytes, main-only paths keep main, numerical-assurance.yml keeps both sides of the three conflict blocks); a fixes
commit with the r2/r3 changes (STD-01 pin test, Rust assertions in the PR6 form, the dated fuzz-smoke nightly, coverage taking the
latest attempt of each shard); and a catalog commit regenerated from the union of main's and PR273's catalog objects, twice, byte
for byte. Criteria, collector, DUT and language profile stay those of main.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the private export are writable; the
real worktree, index, branch, shared config and 20 old candidates stay unchanged. No scientific test bodies, simulator or backend run.
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
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
B = D.parents[2]
S = D / 'source'
R8 = B / 'pr6/rebind-r8-20261027'
WORKER = B / 'pr273-r3-source-sonnet-20261028'
BASE = 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'
BASE_TREE = 'a089a91def27a37686fc3cc98c3b53bf315fa3bb'
OLD_BASE = '02dee32b2c9b25f166cbd77f8a895953e004f288'
PRH = '9ea5de9f1a76c039cd8707f1a6db06ecf1829310'
PR_R1 = '6bfa35ea22cee6e2bbc1819164571364fd6938da'
RETENTION_REVS = (('main', BASE), ('pr273_r2', PRH), ('pr273_r1', PR_R1), ('main_before_split', OLD_BASE))
OBSERVED = D / 'ci-40614646318/catalog-inventory/assets-before.json'
PREFIX = 'evas/capabilities/observations/ci-version-pins-r3-20261028'
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DATA = 'evas/capabilities/data/'
PR_SOURCES = ('.github/workflows/benchmark-evidence.yml', '.github/workflows/numerical-assurance.yml', '.github/workflows/package-install.yml',
              'scripts/capabilities/collect_ci_inventory.py', 'scripts/tests/test_ci_inventory.py', 'scripts/tests/test_ci_pins.py')
FIX_ALLOWED = set(PR_SOURCES) | {'scripts/tests/test_discover_rust.py'}
FIX_ALLOWED_PREFIX = 'scripts/tests/'
WARNING_BYTES = 50 * 1024 * 1024
# package-install.yml merges cleanly, but PR6 passes the fixed toolchain as a workflow_call input; PR273's top-level literal is dropped.
DROPPED_PACKAGE_LINES = ['# Fixed Rust toolchain for the sdist build, which uses it through rustup.\n', 'env:\n', "  RUSTUP_TOOLCHAIN: '1.99.1'\n", '\n']
MERGE_MESSAGE = 'Merge main (PR6 support views and their context registration) into the CI version pins'
FIX_MESSAGE = ('Pin fixes from review r2 and the PR6 merge: the pin test reads quoted, flow and matrix YAML forms and fails on '
               'unknown ones; Rust selection is checked only by the PR6 toolchain guard; fuzz-smoke pins one dated nightly')
COVERAGE_MESSAGE = ('Coverage merges the newest attempt of each regression shard: shard artifacts carry the run attempt, and a '
                    'missing, duplicated or malformed shard artifact fails the job')
# The coordinator asked for the coverage fix as its own commit; these paths and the workflow hunks after the header
# comment belong to it, everything else in the worker's fixes.patch to the pin-fix commit.
COVERAGE_PATHS = ('scripts/tests/test_regression_admission.py', 'scripts/tests/test_regression_shard_selection.py')
WORKFLOW = '.github/workflows/numerical-assurance.yml'
NIGHTLY_COMMENT_OLD = '# Exception: fuzz-smoke installs and names the nightly channel, which cargo-fuzz requires.\n'
NIGHTLY_COMMENT_NEW = ('# Exception: fuzz-smoke installs and names one fixed dated nightly, which cargo-fuzz requires; its spelling is\n'
                       '# FUZZ_NIGHTLY in scripts/tests/test_discover_rust.py, and a different date means changing both together.\n')
FINAL_MESSAGE = 'Regenerate the catalog for the CI version pins, keeping every object version of both parents'
AFFECTED_TESTS = ('test_ci_pins.py', 'test_discover_rust.py', 'test_rust_catalog_reconcile.py', 'test_ci_inventory.py', 'test_ci_selection.py',
                  'test_fast_feedback.py', 'test_regression_admission.py', 'test_catalog_part_split.py', 'test_catalog_history_selection.py',
                  'test_context_registration.py', 'test_regression_gate.py', 'test_trusted_regression_gate.py')
spec = importlib.util.spec_from_file_location('pins_r3_prior_task', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, BASE
PY = task.PY
git, write, sha = task.git, task.write, task.sha
spec = importlib.util.spec_from_file_location('pins_r3_r7_helpers', B / 'pr6/rebind-r7-20261027/prepare_pr6_r7.py')
h = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h)
h.D, h.S, h.task, h.PY = D, S, task, PY
h.git, h.write, h.sha = git, write, sha
CRITERIA_PREFIXES, COLLECTOR, DERIVED_DATA = h.CRITERIA_PREFIXES, h.COLLECTOR, h.DERIVED_DATA
DUT_PREFIXES = ('evas/src/', 'evas/rust_core/')


def load(path): return json.loads(path.read_text())
def env(): return task.clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}
def guard(): return h.guard()
def stable(g): return h.stable(g)
def show(rev, path): return h.show(rev, path)
def names(a, b): return h.names(a, b)


def invariant():
    guard()
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(git('rev-parse', key, source=True).decode().strip()).resolve().is_relative_to(D.resolve())
    assert S.resolve().is_relative_to(D.resolve())


def worker_files():
    """The worker's accepted deliverables; their hashes are pinned in worker-acceptance.json by the primary."""
    acc = load(D / 'worker-acceptance.json')
    for name, digest in acc['files'].items():
        assert sha((WORKER / name).read_bytes()) == digest, name
    return acc


def apply_patch(name):
    r = subprocess.run(['/usr/bin/git', 'apply', '--whitespace=nowarn', str(WORKER / name)], cwd=S, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, (name, r.stderr.decode())


def source():
    before = guard()
    assert not S.exists() and not (D / 'source-preparation.json').exists()
    worker_files()
    assert git('rev-parse', BASE + '^{tree}').decode().strip() == BASE_TREE
    assert git('merge-base', PRH, BASE).decode().strip() == OLD_BASE
    S.mkdir(parents=True)
    with (D / 'export.stderr').open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W), 'archive', BASE],
                                    env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(S)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'init', '--quiet', '--template=',
                        '--initial-branch=pins-r3'], cwd=S, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (S / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', BASE, source=True)
    git('update-ref', 'HEAD', BASE, source=True)
    invariant()
    apply_patch('merge-resolution.patch')
    pr_paths, main_paths = names(OLD_BASE, PRH), names(OLD_BASE, BASE)
    sources = sorted(pr_paths - DERIVED_DATA)
    assert set(sources) == set(PR_SOURCES), sources
    changed = sorted(h.changed_vs(BASE))
    assert set(changed) <= set(PR_SOURCES), changed
    rows = []
    for path in sources:
        got = (S / path).read_bytes()
        if path not in main_paths:
            assert got == show(PRH, path), path
            rows.append({'path': path, 'resolution': 'PR273 bytes (main unchanged since 02dee32b)', 'sha256': sha(got)})
            continue
        scratch = D / 'merge-file' / path.replace('/', '__')
        scratch.mkdir(parents=True)
        for name, raw in (('ours', show(PRH, path)), ('base', show(OLD_BASE, path)), ('theirs', show(BASE, path))):
            (scratch / name).write_bytes(raw)
        mf = subprocess.run(['/usr/bin/git', 'merge-file', '-p', str(scratch / 'ours'), str(scratch / 'base'), str(scratch / 'theirs')],
                            env=h.private_env(), capture_output=True)
        (scratch / 'merge-file-output').write_bytes(mf.stdout)
        (scratch / 'resolution').write_bytes(got)
        merged, resolved = mf.stdout.decode().splitlines(True), got.decode().splitlines(True)
        ops = [op for op in difflib.SequenceMatcher(a=merged, b=resolved, autojunk=False).get_opcodes() if op[0] != 'equal']
        assert all(tag == 'delete' for tag, *_ in ops), (path, 'the resolution may only drop lines of the merge-file output')
        dropped = [line for _, i1, i2, _, _ in ops for line in merged[i1:i2]]
        if mf.returncode == 0:
            # attempt-r1 compared the dropped lines as a list; difflib may attribute the blank separator to either side.
            block = ''.join(DROPPED_PACKAGE_LINES[:-1])
            text = mf.stdout.decode()
            assert path == '.github/workflows/package-install.yml', path
            assert not dropped or got.decode() in (text.replace(block + '\n', '', 1), text.replace('\n' + block, '', 1)), (path, dropped)
            assert not dropped or text.count(block) == 1, path
            check = 'clean merge' if not dropped else 'clean merge minus the PR273 top-level RUSTUP_TOOLCHAIN literal (PR6 input wiring)'
        else:
            inside, depth = set(), False
            for i, line in enumerate(merged):
                if line.startswith('<<<<<<< '):
                    depth = True
                if depth:
                    inside.add(i)
                if line.startswith('>>>>>>> '):
                    depth = False
            assert all(i in inside for _, i1, i2, _, _ in ops for i in range(i1, i2)), (path, 'lines dropped outside conflict blocks')
            assert not any(l.startswith(('<<<<<<< ', '=======', '>>>>>>> ')) for l in resolved), path
            check = '%d conflict blocks; each keeps lines of one or both sides, nothing outside the blocks changes' % mf.returncode
        rows.append({'path': path, 'merge_file_returncode': mf.returncode, 'conflict_blocks': mf.returncode if mf.returncode > 0 else 0,
                     'dropped_lines': dropped, 'resolution_check': check, 'resolution_verified': True, 'sha256': sha(got),
                     'resolution': 'worker resolution (see merge-file/' + path.replace('/', '__') + ')'})
    write(D / 'source-plan.json', {'base': BASE, 'pr_head': PRH, 'old_base': OLD_BASE, 'merge_sources': rows,
          'main_paths': sorted(main_paths), 'pr_paths': sorted(pr_paths)})
    results = []
    h.run_logged('pre-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'source-preparation.json', {'prepared_at_utc': datetime.now(timezone.utc).isoformat(), 'base': BASE, 'base_tree': BASE_TREE,
          'pr_head': PRH, 'old_base': OLD_BASE, 'plan': str(D / 'source-plan.json'), 'pre_render_checks': results,
          'before': before, 'after': after, 'scientific_execution': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'merge_sources': len(rows), 'conflicted': [r['path'] for r in rows if r.get('merge_file_returncode', 0) > 0]}), flush=True)


def commit_tree(parent_index_rev, paths, message, parents, name):
    index = D / (name + '.index')
    assert not index.exists()
    git('read-tree', parent_index_rev, index=index)
    modes = task.entries(parent_index_rev)
    for path in paths:
        target = S / path
        if target.exists():
            raw = target.read_bytes()
            mode = modes.get(path, ('100755' if os.access(target, os.X_OK) else '100644', None))[0]
            oid = git('hash-object', '-w', '--stdin', data=raw).decode().strip()
            git('update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
        else:
            git('update-index', '--force-remove', path, index=index)
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
    rendered = set(h.render_outputs(S))
    merge_paths = sorted({r['path'] for r in plan['merge_sources']} | {p for p in rendered if show(BASE, p) != ((S / p).read_bytes() if (S / p).exists() else None)})
    head, tree = commit_tree(BASE, merge_paths, MERGE_MESSAGE, [PRH, BASE], 'merge')
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    git('merge-base', '--is-ancestor', PRH, head)
    git('merge-base', '--is-ancestor', BASE, head)
    pr_paths, main_paths = set(plan['pr_paths']), set(plan['main_paths'])
    rows = []
    for path in sorted((pr_paths | main_paths) - DERIVED_DATA - rendered):
        got = show(head, path)
        if path in pr_paths and path not in main_paths:
            ok, kind = got == show(PRH, path), 'pr-only: equals PR273 r2'
        elif path in main_paths and path not in pr_paths:
            ok, kind = got == show(BASE, path), 'main-only: equals main'
        else:
            ok, kind = True, 'both: worker resolution, diffs retained'
            (D / 'merge-diffs').mkdir(exist_ok=True)
            for label, a, b in (('vs-main', BASE, head), ('vs-pr', PRH, head), ('pr-change', OLD_BASE, PRH), ('main-change', OLD_BASE, BASE)):
                (D / 'merge-diffs' / (path.replace('/', '__') + '.' + label + '.diff')).write_bytes(git('diff', a, b, '--', path))
            row = next(r for r in plan['merge_sources'] if r['path'] == path)
            ok = row['resolution_verified'] and got == (S / path).read_bytes() and sha(got) == row['sha256']
            kind += '; ' + row['resolution_check']
        rows.append({'path': path, 'kind': kind, 'sha256': sha(got) if got is not None else None, 'equal': ok})
    assert all(r['equal'] for r in rows), [r for r in rows if not r['equal']]
    criteria = sorted(p for p in names(BASE, head) if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in names(BASE, head) if p in COLLECTOR)
    assert not criteria and not collector, (criteria, collector)
    write(D / 'source-equality.json', {'merge_commit': head, 'tree': tree, 'parents': [PRH, BASE], 'rows': rows,
          'criteria_changes_vs_main': criteria, 'collector_changes_vs_main': collector})
    write(D / 'capture.json', {'base': BASE, 'pr_head': PRH, 'commit': head, 'tree': tree, 'parents': [PRH, BASE], 'paths': merge_paths,
          'non_force_successor_of_PR273': True, 'scientific_qualification': False})
    (D / 'merge.patch').write_bytes(git('diff', '--binary', BASE, head, '--', *merge_paths))
    print(json.dumps({'merge': head, 'tree': tree, 'paths': len(merge_paths), 'source_rows': len(rows)}), flush=True)


def fixes():
    """Two commits on the merge: the pin fixes, then the coverage fix (coordinator condition: its own commit)."""
    invariant()
    cap = load(D / 'capture.json')
    assert not (D / 'fixes.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == cap['commit']
    worker_files()
    merged_workflow = (S / WORKFLOW).read_text()
    assert merged_workflow.count(NIGHTLY_COMMENT_OLD) == 1
    apply_patch('fixes.patch')
    changed = sorted(h.changed_vs(cap['commit']))
    assert changed and all(p in FIX_ALLOWED or (p.startswith(FIX_ALLOWED_PREFIX) and p.endswith('.py')) for p in changed), changed
    final_workflow = (S / WORKFLOW).read_text()
    intermediate = merged_workflow.replace(NIGHTLY_COMMENT_OLD, NIGHTLY_COMMENT_NEW)
    assert intermediate.count(NIGHTLY_COMMENT_NEW) == 1 == final_workflow.count(NIGHTLY_COMMENT_NEW)
    # Only the coverage hunks remain between the pin-fix workflow and the final workflow: every changed line lies
    # inside the regression and regression-coverage jobs.
    a, b = intermediate.splitlines(), final_workflow.splitlines()
    start = next(i for i, line in enumerate(b) if line == '  regression:')
    stop = next(i for i, line in enumerate(b) if line == '  regression-admission:')
    ops = [op for op in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes() if op[0] != 'equal']
    assert ops and all(start < j1 and j2 <= stop for _, _, _, j1, j2 in ops), ops
    pin_paths = sorted(p for p in changed if p not in COVERAGE_PATHS and p != WORKFLOW) + [WORKFLOW]
    coverage_paths = sorted(p for p in changed if p in COVERAGE_PATHS) + [WORKFLOW]
    assert set(pin_paths) | set(coverage_paths) == set(changed)
    final_bytes = {p: (S / p).read_bytes() for p in changed}
    (S / WORKFLOW).write_text(intermediate)
    for p in coverage_paths:
        if p != WORKFLOW:
            original = show(cap['commit'], p)
            if original is None:
                (S / p).unlink()
            else:
                (S / p).write_bytes(original)
    pin_head, pin_tree = commit_tree(cap['commit'], pin_paths, FIX_MESSAGE, [cap['commit']], 'fixes-pins')
    for p, raw in final_bytes.items():
        (S / p).write_bytes(raw)
    cov_head, cov_tree = commit_tree(pin_head, coverage_paths, COVERAGE_MESSAGE, [pin_head], 'fixes-coverage')
    git('read-tree', cov_head, source=True)
    git('update-ref', 'HEAD', cov_head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    assert sorted(names(cap['commit'], pin_head)) == sorted(pin_paths) and sorted(names(pin_head, cov_head)) == sorted(coverage_paths)
    head, tree = cov_head, cov_tree
    total = sorted(names(BASE, head) - DERIVED_DATA - set(h.render_outputs(S)))
    # The committed layers must equal the worker's cumulative patch applied to main.
    check = D / 'cumulative-check'
    assert not check.exists()
    for path in total:
        target = check / path
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = show(BASE, path)
        if raw is not None:
            target.write_bytes(raw)
    r = subprocess.run(['/usr/bin/git', 'apply', '--whitespace=nowarn', str(WORKER / 'source.patch')], cwd=check, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr.decode()
    mismatched = [p for p in total if (check / p).read_bytes() != show(head, p)]
    assert not mismatched, mismatched
    write(D / 'fixes.json', {'merge_commit': cap['commit'], 'pin_commit': pin_head, 'pin_tree': pin_tree, 'pin_paths': pin_paths,
          'coverage_commit': cov_head, 'coverage_tree': cov_tree, 'coverage_paths': coverage_paths, 'commit': head, 'tree': tree,
          'paths': changed, 'patch': str(WORKER / 'fixes.patch'), 'patch_sha256': sha((WORKER / 'fixes.patch').read_bytes()),
          'cumulative_equals_worker_source_patch': True, 'scientific_qualification': False})
    (D / 'fixes.diff').write_bytes(git('diff', '--binary', cap['commit'], head))
    print(json.dumps({'pin_commit': pin_head, 'coverage_commit': cov_head, 'paths': changed}), flush=True)


def assets():
    """Asset receipt for the fixes commit, reusing the CI observation of main's tree for unchanged blobs."""
    invariant()
    fx = load(D / 'fixes.json')
    assert not (D / 'assets.json').exists()
    observed = load(OBSERVED)
    assert observed['source_tree'] == BASE_TREE and not observed['dirty_paths']
    old_rows = {row['path']: row for row in observed['assets']}
    prior, after = task.entries(BASE), task.entries(fx['commit'])
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
    assert sorted(changed) == sorted(p for p in names(BASE, fx['commit']) if p in after)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': fx['commit'], 'source_tree': fx['tree'], 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'local-only-before-publication',
          'content_binding': 'verified-git-blob-oids', 'scope': observed['scope'], 'assets': out,
          'reuse_proof': {'actual_CI': 40614646318, 'observation': str(OBSERVED), 'unchanged': len(out) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'assets': len(out), 'changed': len(changed)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    fx = load(D / 'fixes.json')
    config = load(R8 / 'config.json')
    candidates = {}
    for item in config['discoveries']:
        path = Path(item['entry_file'])
        value = load(path)
        candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    changed_paths = sorted(names(BASE, fx['commit']) - DERIVED_DATA)
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = fx['commit']
    inventory = h.module('pins_r3_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    tip = h.remote_archive()
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
            git('merge-base', '--is-ancestor', locator['revision'], tip)
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
          'new_collections': new_count, 'changed_paths_vs_main': changed_paths, 'archive_tip_checked': tip,
          'reuse_basis': 'Exact workflow entry, collector and owner-module hashes from the PR6 activation build receipts; changed or touched entries are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count}), flush=True)


def union():
    """Previous catalog for generation: main's part-layout catalog plus every PR273 (r1, r2) object it lacks."""
    invariant()
    union_dir = D / 'previous-union'
    assert not union_dir.exists() and not (D / 'union-acceptance.json').exists()
    data = S / 'evas/capabilities/data'
    base_data = D / 'base-data'
    assert not base_data.exists()
    base_data.mkdir()
    header = json.loads(show(BASE, DATA + 'registry.json'))
    (base_data / 'registry.json').write_bytes(show(BASE, DATA + 'registry.json'))
    for part in header['object_parts']:
        (base_data / part).write_bytes(show(BASE, DATA + part))
    for name in ('catalog-sources.json', 'asset-index.json', 'entrypoint-index.json'):
        if show(BASE, DATA + name) is not None:
            (base_data / name).write_bytes(show(BASE, DATA + name))
    shutil.copytree(base_data, union_dir)
    writer = h.module('pins_r3_union_writer', S / 'scripts/capabilities/generate_catalog.py')
    present = h.objects_at(BASE)
    docs = {name: load(union_dir / name) for name in header['object_parts']}
    kind_file = {'sources': 'catalog-sources.json', 'assets': 'asset-index.json', 'entrypoints': 'entrypoint-index.json'}
    added, conflicts, by_part = [], [], {}
    header_objects = list(header['objects'])
    for rev in (PRH, PR_R1):
        pr_header = json.loads(git('show', rev + ':' + DATA + 'registry.json'))
        parts = {'registry.json': (None, pr_header['objects'])}
        for part in pr_header['object_parts']:
            doc = json.loads(git('show', rev + ':' + DATA + part))
            parts[part] = (doc['kind'], doc['objects'])
        for part, (kind, items) in parts.items():
            for obj in items:
                key = (obj['id'], obj['version'])
                if key in present:
                    if present[key] != obj:
                        conflicts.append(list(key))
                    continue
                if part == 'registry.json':
                    header_objects.append(obj)
                    target = 'registry.json'
                else:
                    target = writer.part_file(kind, obj['id']) if kind in ('methods', 'history') else kind_file[kind]
                    docs[target]['objects'].append(obj)
                present[key] = obj
                added.append({'from': rev[:8], 'part': target, 'id': obj['id'], 'version': obj['version']})
                by_part[target] = by_part.get(target, 0) + 1
    assert not conflicts, conflicts[:5]
    header['objects'] = header_objects
    (union_dir / 'registry.json').write_text(json.dumps(header, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    for name, doc in docs.items():
        (union_dir / name).write_text(json.dumps(doc, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    merged = task.objects(union_dir)
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
    write(D / 'union-acceptance.json', {'base': BASE, 'pr_revisions': [PRH, PR_R1], 'union_dir': str(union_dir), 'base_objects': len(h.objects_at(BASE)),
          'added': len(added), 'added_by_part': by_part, 'conflicts': conflicts, 'union_objects': len(merged),
          'retention_revisions': [r for _, r in RETENTION_REVS], 'scientific_qualification': False})
    invariant()
    print(json.dumps({'added': len(added), 'union_objects': len(merged)}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = h.remote_archive()
    dest = D / 'archive-files' / PREFIX
    dest.mkdir(parents=True)
    for name in ('capture.json', 'merge.patch', 'source-plan.json', 'source-equality.json', 'fixes.json', 'fixes.diff', 'discovery-selection.json',
                 'source-preparation.json', 'union-acceptance.json', 'worker-acceptance.json'):
        shutil.copyfile(D / name, dest / name)
    for name in ('merge-resolution.patch', 'fixes.patch', 'source.patch', 'REPORT.md', 'result.json'):
        shutil.copyfile(WORKER / name, dest / ('worker-' + name))
    for sub in ('new-discovery', 'merge-diffs'):
        if (D / sub).exists():
            shutil.copytree(D / sub, dest / sub)
    shutil.copyfile(__file__, dest / 'prepare_pins_r3.py')
    (dest / 'README.md').write_text('# CI version pins r3\n\n'
        'The merge commit joins PR273 r2 (9ea5de9f) with main after PR6 and its context registration (bf2ec410). PR273-only source '
        'paths keep the r2 bytes, main-only paths keep main, and numerical-assurance.yml keeps both sides of its three conflict blocks. '
        'The fixes commit closes review findings STD-01 and STD-R2-01 and adapts the pins to PR6: the pin test reads quoted, flow and '
        'matrix YAML forms and fails on unknown ones; Rust pins are checked in the PR6 input form; fuzz-smoke pins one dated nightly; '
        'and regression-coverage merges the latest attempt of each shard. The catalog is regenerated from the union of both parents. '
        'Criteria, collector and DUT are unchanged. Scientific qualification is false.\n')
    idx = D / 'archive.index'
    assert not idx.exists()
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
    head = git('commit-tree', tree, '-p', parent, '-m', 'Archive CI version pins r3 construction').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'remote_parent': parent, 'commit': head, 'tree': tree, 'prefix': PREFIX, 'files': files, 'published': False})
    config = load(R8 / 'config.json')
    old = {}
    for item in config['discoveries']:
        entry = load(Path(item['entry_file']))['entry']
        old[entry['entry_id']] = entry
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(D / 'previous-union'),
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
            remap.append({'bridge': bridge['path'], 'old_entry_id': cid, 'new_entry_id': match[0], 'start': old[cid]['start'], 'pattern': old[cid]['pattern']})
        bridge['consumer_entry_ids'] = ids
    write(D / 'bridge-consumer-remap.json', {'reason': 'workflow edits change entry identities; the bridged entry keeps its start and pattern', 'remap': remap})
    write(D / 'config.json', config)
    invariant()
    print(json.dumps({'archive': head, 'parent': parent, 'files': len(files), 'bridge_remap': len(remap)}), flush=True)


def generate():
    invariant()
    assert not (D / 'generation-acceptance.json').exists()
    assert load(D / 'config.json')['previous_data_dir'] == str(D / 'previous-union')
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
    previous, current = task.objects(D / 'previous-union'), task.objects(first)
    assert all(current.get(k) == v for k, v in previous.items())
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        missing = [list(k) for k in expected if k not in current]
        rewritten = [list(k) for k, v in expected.items() if k in current and current[k] != v]
        assert not missing and not rewritten, (name, len(missing), len(rewritten))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': 0}
    header = load(first / 'registry.json')
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
    new_objects = [k for k in current if k not in previous]
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
          'new_object_versions': len(new_objects), 'deterministic_double_generation': True,
          'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes,
          'largest_data_file': max(sizes.items(), key=lambda x: x[1]), 'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'new_object_versions': len(new_objects),
                      'largest': max(sizes.items(), key=lambda x: x[1])}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    h.run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    h.run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    fx = load(D / 'fixes.json')
    paths = h.changed_vs(fx['commit'])
    rendered = set(h.render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA)
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'fixes_commit': fx['commit'], 'paths_vs_fixes': paths, 'render_outputs': len(rendered), 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()}, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_fixes': len(paths)}), flush=True)


def freeze():
    invariant()
    fx, der = load(D / 'fixes.json'), load(D / 'derive-acceptance.json')
    assert not (D / 'final-candidate.json').exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = h.changed_vs(fx['commit'])
    assert sorted(generated) == sorted(der['paths_vs_fixes'])
    head, tree = commit_tree(fx['commit'], generated, FINAL_MESSAGE, [fx['commit']], 'final')
    for anc in (PRH, BASE, fx['commit']):
        git('merge-base', '--is-ancestor', anc, head)
    complete = sorted(git('diff', '--name-only', BASE, head).decode().splitlines())
    criteria = sorted(p for p in complete if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in complete if p in COLLECTOR)
    dut = sorted(p for p in complete if p.startswith(DUT_PREFIXES))
    assert not criteria and not collector and not dut, (criteria, collector, dut)
    blobs, changed = [], set(complete)
    for line in git('ls-tree', '-r', '-l', head).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final = {'commit': head, 'tree': tree, 'base': BASE, 'pr_head': PRH, 'merge_commit': load(D / 'capture.json')['commit'], 'fixes_commit': fx['commit'],
             'complete_paths': complete, 'criteria_changes': criteria, 'collector_changes': collector, 'dut_changes': dut,
             'derive': str(D / 'derive-acceptance.json'), 'source_equality': str(D / 'source-equality.json'), 'large_unchanged_blobs': blobs,
             'precheck': 'runs on the frozen head in parallel with CI', 'review': 'pending: incremental priority Astra (r3)', 'CI': 'pending',
             'published': False, 'scientific_qualification': False, 'frozen_at_utc': datetime.now(timezone.utc).isoformat()}
    write(D / 'final-candidate.json', final)
    (D / 'candidate.patch.identity.json').write_text(json.dumps({'base': BASE, 'head': head, 'command': 'git diff --binary <base> <head>'}, indent=2) + '\n')
    git('read-tree', head, source=True)
    git('update-ref', 'HEAD', head, source=True)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    invariant()
    print(json.dumps({'commit': head, 'tree': tree, 'complete_paths': len(complete)}), flush=True)


def precheck():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    results = []
    paths = final['complete_paths']
    sys.path.insert(0, str(S / 'scripts'))
    import ci_selection
    write(D / 'maintenance-plan.json', {'mode': 'delivery', 'paths': paths, **ci_selection.classify(paths), 'focused': False,
          'scope': 'CI version pins r3, quick maintenance gate; full scientific regression is CI only.'})
    h.run_logged('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], results)
    h.run_logged('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'], results)
    h.run_logged('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], results)
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    extra = sorted({Path(p).name for p in load(D / 'fixes.json')['paths'] if p.startswith('scripts/tests/test_') and p.endswith('.py')} - set(AFFECTED_TESTS))
    for name in tuple(AFFECTED_TESTS) + tuple(extra):
        h.run_logged('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'],
                     results, extra_env=tools)
    h.run_logged('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': paths,
          'checks': results, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def inventory():
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'inventory-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    results = []
    out = D / 'catalog-inventory-local'
    h.run_logged('inventory-local.txt', [str(PY), '-B', 'scripts/capabilities/collect_ci_inventory.py', '--root', '.', '--output', str(out),
                                         '--require-catalog', '--registry-data', 'evas/capabilities/data'], results,
                 extra_env={'CI_INVENTORY_BASE': BASE, 'CI_INVENTORY_HEAD': final['commit']})
    summary = load(out / 'summary.json')
    assert summary['success'] and summary['reconciled'] and summary['construction_complete'] and not summary['errors'], summary.get('errors')
    assert summary['source']['source_tree'] == final['tree']
    write(D / 'inventory-acceptance.json', {'candidate': final['commit'], 'tree': final['tree'], 'checks': results,
          'summary': {k: summary[k] for k in ('success', 'reconciled', 'construction_complete', 'mode', 'entry_count', 'denominators')},
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'inventory': 'reconciled', 'entries': summary['entry_count']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['source', 'capture', 'fixes', 'assets', 'discover', 'union', 'archive', 'generate', 'derive', 'freeze',
                                          'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

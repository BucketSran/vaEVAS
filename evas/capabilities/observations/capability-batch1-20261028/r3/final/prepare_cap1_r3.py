"""Capability batch 1 PR, round 3: the r3 fixes (R1-ST-01 registered baseline-kernel selector, R1-ST-02 by-name runner and receipt
check, R1-SP-01 explicit null in a CLI manifest, card update) on the published round 2 head eb26e5b1, then the catalog. Round 2's docstring follows; the differences are listed in ROUND3.

Stage series exports 5888e9fa, applies the r2 worker's patch series as one commit per topic, regenerates the diagnostic
inventory before any asset observation, and checks the result byte for byte against the worker's combined patch. Stage
listing reuses the Linux Rust listing of CI 40663661365 on 5888e9fa only when no Rust input changed since then. The rest
follows prepare_cap1.py: assets, discovery (entries whose workflow definition or owned modules changed are recollected),
main's catalog as the previous union, the construction archive with the one-time PR evidence, double generation, render
and traceability, freeze, quick checks and the local inventory.

Stages write new receipts and refuse to replace them. Only this directory, Git objects and the private export are writable;
the real worktree, its index, branch, shared config and the 20 old candidates stay unchanged. No scientific test bodies run.
Usage: python3 -I -B prepare_cap1_r3.py <stage>   (discover needs the 3.12 lint venv)

ROUND3: base PREV = eb26e5b1 (published r2 head); the Rust listing still comes from CI 40663661365 on 5888e9fa (LISTING_HEAD)
under the same inserted-step rule; the previous catalog is the published r2 catalog (superset of main's), so r2's object
versions are kept; discovery reuses R4 and r2 receipts; archive under PREFIX/r3; precheck adds every command of the
static-checks 'Traceability and frozen validation identities' step.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import fnmatch
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

D = Path(__file__).resolve().parent
B = D.parent
P1 = B / 'capability-batch1-pr-20261028'
S = D / 'source'
WORKER = B / 'capability-batch1-r2-fixes-opus-20261028' / 'r3'
PATCH = WORKER / 'source.patch'
R2 = B / 'capability-batch1-pr-r2-20261028'
PATCH_SHA = '558f7646e7bfc874a1bbb7dc45bf7e665909d72ff72affa9972a7aff0138f020'  # r3 delivery, 2026-10-28
SERIES = ('0001-Read-the-registered-baseline-kernel-variables-in-the.patch', '0002-Fail-the-by-name-RC-check-when-a-check-ends-early-or.patch',
          '0003-Reject-an-explicit-null-proof_work_limit-in-a-CLI-ma.patch', '0004-Update-the-batch-1-cards-for-the-r3-fixes.patch')
BASE = 'd6b7543fc815aaa584c886108691b6f2c01eb220'
BASE_TREE = 'c299c287165fa29ead86442956296b0a825aa35b'
PREV = 'eb26e5b12e1ec6b36024e972d1211aec4e288ab3'
PREV_TREE = '236590e69aae9ffce66bbe4f1577928aa8c56738'
LISTING_HEAD = '5888e9fad23601021e70edce16ec41fafc6e6c6b'
PREV_LISTING_RUN = 40663661365
R2_CONSTRUCTION = 'ee41998cd2a8af47bc25258f5c411f715b355a86'
ARCHIVE_TIP = '7f5352aadf5cf36be6e5c26825b2fcc87634e469'
R4 = B / 'pr6/ci-pins-a-20261027/r4'
R4_TEST_COMMIT = '30ac23c4e670c833bc42230e9503f4aa6fd69010'
R4_ARCHIVE = 'ff8368c2f8ff15c2a826244ee607b221a14d2eac'
RETENTION_REVS = (('main', BASE), ('main_before_pr273', 'bf2ec4105a17af2bf73f2802c828c5f76a6236b5'),
                  ('main_before_split', '02dee32b2c9b25f166cbd77f8a895953e004f288'), ('pr282_r2_published', 'eb26e5b12e1ec6b36024e972d1211aec4e288ab3'))
# The phase 1 construction archive (capability-batch1-pr-20261028/archive.json) was never published, so the prefix is free.
PREFIX = 'evas/capabilities/observations/capability-batch1-20261028'
PREFIX3 = PREFIX + '/r3'
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
DATA = 'evas/capabilities/data/'
DIAG = 'evas/docs/development/diagnostic-inventory.json'
PROFILE = 'linux-x86_64-regression-opt1-v1'
REPO = 'BucketSran/vaEVAS'
WARNING_BYTES = 50 * 1024 * 1024
D1_PART_THRESHOLD = 35 * 1000 * 1000
DIAG_MESSAGE = 'Regenerate the diagnostic inventory for the round 3 messages'
FINAL_MESSAGE = 'Regenerate the catalog for capability batch 1, keeping every object version'
LISTING_INPUTS = ('scripts/capabilities/discover_rust.py',)
WORKFLOW = '.github/workflows/numerical-assurance.yml'
LISTING_UPLOAD_END = '            runs/rust-test-listing/\n'
spec = importlib.util.spec_from_file_location('cap1r3_prior_task', B / 'pr4/post-review-integration-20261027/prepare_c0_candidate.py')
task = importlib.util.module_from_spec(spec)
spec.loader.exec_module(task)
task.S, task.OUT, task.BASE = S, D, BASE
PY = task.PY
git, write, sha = task.git, task.write, task.sha
spec = importlib.util.spec_from_file_location('cap1r3_r7_helpers', B / 'pr6/rebind-r7-20261027/prepare_pr6_r7.py')
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
def gh(*args): return subprocess.check_output(['gh', *args], env=env())


def names(a, b):
    """Changed paths without rename detection, so a rename lists both sides."""
    return set(git('diff', '--no-renames', '--name-only', a, b).decode().splitlines())


def changed_vs(rev):
    """Working tree of the private export against rev, without rename detection (h.changed_vs lets Git pair renames)."""
    git('add', '--intent-to-add', '--', '.', source=True)
    paths = git('diff', '--no-renames', '--name-only', rev, source=True).decode().splitlines()
    git('reset', '--quiet', source=True)
    return paths


def rust_job(raw):
    """Text of the rust-regression job, from its header to the next job header."""
    lines = raw.decode().splitlines(True)
    start = lines.index('  rust-regression:\n')
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('  ') and not lines[i].startswith('   ') and lines[i].rstrip().endswith(':'))
    return ''.join(lines[start:end])


def rust_input(path):
    return (path.startswith('evas/rust_core/') or path.rsplit('/', 1)[-1] in ('Cargo.toml', 'Cargo.lock', 'rust-toolchain', 'rust-toolchain.toml')
            or path in LISTING_INPUTS)


def invariant():
    guard()
    if (S / '.git').exists():
        for key in ('--absolute-git-dir', '--git-common-dir', '--show-toplevel'):
            assert Path(git('rev-parse', key, source=True).decode().strip()).resolve().is_relative_to(D.resolve())
    assert S.resolve().is_relative_to(D.resolve())


def head2():
    cm = load(D / 'commits.json')
    return cm['head'], cm['tree']


def patch_message(patch):
    """Commit message of a format-patch file (git mailinfo), without its Co-Authored-By trailer: commit_tree adds TRAILER."""
    out = D / ('mailinfo-' + patch.stem)
    out.mkdir()
    info = subprocess.run(['/usr/bin/git', 'mailinfo', str(out / 'msg'), str(out / 'patch')], stdin=patch.open('rb'),
                          capture_output=True, env=h.private_env(), cwd=out)
    assert info.returncode == 0, info.stderr
    subject = [line[len('Subject: '):] for line in info.stdout.decode().splitlines() if line.startswith('Subject: ')]
    assert len(subject) == 1, info.stdout
    body = (out / 'msg').read_text().strip()
    assert body.endswith(TRAILER.strip()), patch.name
    body = body[:-len(TRAILER.strip())].rstrip()
    return subject[0].strip() + ('\n\n' + body if body else '')


def patch_paths(patch):
    paths = set()
    for line in patch.read_text().splitlines():
        if line.startswith('diff --git '):
            a, b = line.split()[2:4]
            paths.update({a[2:], b[2:]})
    return sorted(paths)


def export(rev, target, private_repo):
    target.mkdir(parents=True)
    with (D / ('export-' + target.name + '.stderr')).open('xb') as err:
        producer = subprocess.Popen(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(task.GD), '--work-tree=' + str(task.W), 'archive', rev],
                                    env=env(), stdout=subprocess.PIPE, stderr=err)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(target)], stdin=producer.stdout, env=env())
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    if not private_repo:
        return
    assert target == S, 'the private repository helpers act on S only'
    r = subprocess.run(['/usr/bin/git', '--git-dir=' + str(target / '.git'), '--work-tree=' + str(target), 'init', '--quiet', '--template=',
                        '--initial-branch=capability-batch1-r3'], cwd=target, env=h.private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    common = Path(git('rev-parse', '--git-common-dir').decode().strip()).resolve()
    (target / '.git/objects/info/alternates').write_text(str(common / 'objects') + '\n')
    git('read-tree', rev, source=True)
    git('update-ref', 'HEAD', rev, source=True)


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


def series():
    """Export 5888e9fa, apply the series one patch at a time (each commit reads the tree after its own patch), regenerate
    the diagnostic inventory, and check the result against the combined patch applied to a second export."""
    before = guard()
    assert not S.exists() and not (D / 'commits.json').exists()
    assert sha(PATCH.read_bytes()) == PATCH_SHA
    patches = sorted((WORKER / 'series').glob('*.patch'))
    assert SERIES and tuple(p.name for p in patches) == SERIES, [p.name for p in patches]
    messages = {p.name: patch_message(p) for p in patches}
    assert git('rev-parse', PREV + '^{tree}').decode().strip() == PREV_TREE
    export(PREV, S, private_repo=True)
    invariant()
    assert not changed_vs(PREV)
    rows, parent = [], PREV
    for p in patches:
        r = subprocess.run(['/usr/bin/git', 'apply', '--whitespace=nowarn', str(p)], cwd=S, env=h.private_env(), capture_output=True)
        (D / ('apply-' + p.stem + '.stderr')).write_bytes(r.stderr)
        assert r.returncode == 0, r.stderr.decode()
        paths = patch_paths(p)
        assert sorted(changed_vs(parent)) == paths, (p.name, sorted(set(changed_vs(parent)) ^ set(paths)))
        head, tree = commit_tree(parent, paths, messages[p.name], [parent], 'series-' + p.stem)
        assert sorted(names(parent, head)) == paths
        git('read-tree', head, source=True)
        git('update-ref', 'HEAD', head, source=True)
        assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
        rows.append({'patch': str(p), 'patch_sha256': sha(p.read_bytes()), 'commit': head, 'tree': tree, 'paths': paths,
                     'message': messages[p.name]})
        parent = head
    results = []
    h.run_logged('diagnostic-inventory-write.txt', [str(PY), '-B', 'scripts/diagnostic_inventory.py', '--write'], results)
    h.run_logged('diagnostic-inventory-check.txt', [str(PY), '-B', 'scripts/diagnostic_inventory.py', '--check'], results)
    extra = changed_vs(parent)
    if extra:
        assert extra == [DIAG], extra
        head, tree = commit_tree(parent, [DIAG], DIAG_MESSAGE, [parent], 'diagnostics-r2')
        git('read-tree', head, source=True)
        git('update-ref', 'HEAD', head, source=True)
        rows.append({'patch': None, 'commit': head, 'tree': tree, 'paths': [DIAG], 'message': DIAG_MESSAGE,
                     'reason': 'diagnostic_inventory.py --write changed it after the series; derived before any asset observation'})
        parent = head
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    head, tree = parent, git('rev-parse', parent + '^{tree}').decode().strip()
    combined = D / 'patch-check'
    export(PREV, combined, private_repo=False)
    r = subprocess.run(['/usr/bin/git', 'apply', '--whitespace=nowarn', str(PATCH)], cwd=combined, env=h.private_env(), capture_output=True)
    (D / 'apply-combined.stderr').write_bytes(r.stderr)
    assert r.returncode == 0, r.stderr.decode()
    expected = set(patch_paths(PATCH)) | ({DIAG} if extra else set())
    actual = names(PREV, head)
    assert actual == expected, sorted(actual ^ expected)
    for path in sorted(patch_paths(PATCH)):
        a, c = S / path, combined / path
        assert a.exists() == c.exists() and (not a.exists() or a.read_bytes() == c.read_bytes()), path
    complete = sorted(names(BASE, head))
    criteria = sorted(p for p in complete if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in complete if p in COLLECTOR)
    dut = sorted(p for p in complete if p.startswith(DUT_PREFIXES))
    r2 = sorted(actual)
    assert not collector and DATA + 'language-profile.json' not in complete
    after = guard()
    assert stable(before) == stable(after)
    write(D / 'commits.json', {'base': BASE, 'prev': PREV, 'prev_tree': PREV_TREE, 'phase1_receipts': str(P1 / 'commits.json'),
          'phase1b_receipt': str(P1 / 'phase1b.json'), 'patch': str(PATCH), 'patch_sha256': PATCH_SHA, 'series': rows,
          'checks': results, 'head': head, 'tree': tree, 'r2_paths': r2, 'r2_criteria': sorted(p for p in r2 if p.startswith(CRITERIA_PREFIXES)),
          'r2_dut': sorted(p for p in r2 if p.startswith(DUT_PREFIXES)), 'r2_rust_inputs': sorted(p for p in r2 if rust_input(p)),
          'complete_paths': complete, 'criteria_changes': criteria, 'dut_changes': len(dut), 'collector_changes': collector,
          'files': {p: sha((S / p).read_bytes()) for p in r2 if (S / p).is_file()}, 'before': before, 'after': after,
          'scientific_execution': False, 'scientific_qualification': False, 'executed_by': 'tclaude/claude-opus-5-5'})
    print(json.dumps({'commits': [r['commit'] for r in rows], 'head': head, 'tree': tree, 'r2_paths': len(r2),
                      'rust_inputs': sorted(p for p in r2 if rust_input(p))}), flush=True)


def listing():
    """Reuse the Linux Rust listing of 5888e9fa when no Rust input changed in round 2."""
    invariant()
    head, _ = head2()
    out = D / 'rust-listing'
    assert not out.exists()
    rust = sorted(p for p in names(LISTING_HEAD, head) if rust_input(p))
    if rust:
        raise SystemExit('Rust inputs changed since 5888e9fa; publish the round 3 commits and take a CI listing first: ' + repr(rust))
    # The listing comes from the rust-regression steps up to the rust-test-listing upload; they and the job header must be
    # unchanged, so any new step sits after the upload.
    old_job, new_job = rust_job(show(LISTING_HEAD, WORKFLOW)), rust_job(show(head, WORKFLOW))
    old_lines, new_lines = old_job.splitlines(True), new_job.splitlines(True)
    import difflib
    ops = [op for op in difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False).get_opcodes() if op[0] != 'equal']
    # Round 3 may extend the round 2 block or add a self-contained step after the listing upload; every listing line stays.
    assert ops and all(op[0] == 'insert' for op in ops), ops
    listing_at = next(i for i, line in enumerate(old_lines) if line.strip() == '- name: Collect actual owned Rust binary listing')
    upload_end = next(i for i in range(listing_at, len(old_lines)) if old_lines[i] == LISTING_UPLOAD_END) + 1
    inserted, bodies = [], []
    for _, i1, _, j1, j2 in ops:
        block = new_lines[j1:j2]
        assert i1 <= listing_at or i1 >= upload_end, ('insertion inside the listing steps', i1)
        assert i1 == len(old_lines) or old_lines[i1].startswith('      - '), ('insertion not at a step boundary', old_lines[i1:i1 + 1])
        assert block[0].startswith('      - ') or block[0].startswith('      #'), block[:2]
        body = ''.join(block)
        for token in ('GITHUB_ENV', 'GITHUB_PATH', 'GITHUB_OUTPUT', 'RUSTFLAGS', 'CARGO_PROFILE', 'CARGO_TARGET_DIR', 'cargo update', 'rustup'):
            assert token not in body, token
        assert not any(line.startswith('    env:') or line.startswith('  ') and not line.startswith('    ') for line in block if line.strip())
        inserted += block
        bodies.append(body)
    body = ''.join(bodies)
    i1 = ops[0][1]
    prefix = ''.join(old_lines[:i1])
    src = P1 / 'rust-listing'
    summary = load(src / 'summary.json')
    assert summary['head'] == LISTING_HEAD and summary['run'] == PREV_LISTING_RUN and summary['complete'] and not summary['errors']
    raw = (src / 'rust-test-listing.zip').read_bytes()
    assert 'sha256:' + sha(raw) == summary['artifact']['digest']
    receipt = (src / 'artifact/rust-test-listing.json').read_bytes()
    out.mkdir()
    (out / 'artifact').mkdir()
    for name in ('summary.json', 'job.json', 'job.log', 'rust-test-listing.zip'):
        shutil.copyfile(src / name, out / name)
    shutil.copyfile(src / 'artifact/rust-test-listing.json', out / 'artifact/rust-test-listing.json')
    write(out / 'reuse.json', {'reused_from': str(src), 'run': summary['run'], 'listing_head': LISTING_HEAD, 'head': head, 'round': 3,
          'rust_inputs_changed_since_listing_head': [], 'rust_input_rule': 'evas/rust_core/**, Cargo.toml, Cargo.lock, rust-toolchain*, ' + ', '.join(LISTING_INPUTS),
          'workflow_rule': 'one inserted, self-contained step in rust-regression (step-level env, no GITHUB_ENV/PATH/OUTPUT, no Rust profile, toolchain or target changes); every other line of the job, including checkout, toolchain, cache, the Rust regression and the listing steps, is byte-identical',
          'inserted_step_sha256': sha(body.encode()), 'inserted_lines': len(inserted),
          'rust_job_sha256': {'prev': sha(old_job.encode()), 'head': sha(new_job.encode()), 'unchanged_prefix_sha256': sha(prefix.encode())},
          'artifact_digest': summary['artifact']['digest'], 'receipt_sha256': sha(receipt), 'scientific_qualification': False})
    invariant()
    print(json.dumps({'reused_run': summary['run'], 'tests_discovered': summary['tests_discovered']}), flush=True)


def assets():
    """Asset receipt for the round 2 head, reusing the verified r4 receipt (test commit 30ac23c4) for unchanged blobs."""
    invariant()
    assert not (D / 'assets.json').exists()
    observed = load(R4 / 'assets.json')
    assert observed['source_commit'] == R4_TEST_COMMIT
    old_rows = {row['path']: row for row in observed['assets']}
    head, tree = head2()
    prior, after = task.entries(R4_TEST_COMMIT), task.entries(head)
    assert set(prior) == set(old_rows)
    out, changed = [], []
    for path, (mode, oid) in sorted(after.items()):
        old = old_rows.get(path)
        if prior.get(path) == (mode, oid):
            assert (old['git_mode'], old['git_blob_oid']) == (mode, oid), path
            value, actual_mode = old['sha256'], old['actual_mode']
        else:
            raw = (S / path).read_bytes()
            assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid, path
            value, actual_mode = sha(raw), (S / path).stat().st_mode & 0o777
            changed.append(path)
        out.append({'path': path, 'sha256': value, 'git_mode': mode, 'actual_mode': actual_mode, 'git_blob_oid': oid})
    assert sorted(changed) == sorted(p for p in names(R4_TEST_COMMIT, head) if p in after)
    write(D / 'assets.json', {'schema_version': 1, 'producer': 'task-incremental-verified-asset-capture',
          'source_commit': head, 'source_tree': tree, 'source_object_format': 'sha1', 'source_kind': 'immutable-export',
          'source_profile': 'git-tree-regular-blobs-v1', 'source_availability': 'published', 'content_binding': 'verified-git-blob-oids',
          'scope': observed['scope'], 'assets': out,
          'reuse_proof': {'previous_receipt': str(R4 / 'assets.json'), 'previous_receipt_sha256': sha((R4 / 'assets.json').read_bytes()),
                          'previous_source_commit': R4_TEST_COMMIT, 'unchanged': len(out) - len(changed), 'changed': changed}})
    invariant()
    print(json.dumps({'assets': len(out), 'changed': len(changed)}), flush=True)


def discover():
    invariant()
    assert sys.version_info[:2] == (3, 12)
    assert not (D / 'discovery-selection.json').exists()
    candidates = {}
    for config in (load(R4 / 'config.json'), load(R2 / 'config.json')):
        for item in config['discoveries']:
            path = Path(item['entry_file'])
            value = load(path)
            candidates[str(path)] = (path, value, config['discovery_source_locators'][value['entry']['entry_id']])
    head, _ = head2()
    changed_paths = sorted(names(BASE, head) - DERIVED_DATA)
    for name in list(os.environ):
        if name.startswith('GIT_'):
            del os.environ[name]
    os.environ['CI_INVENTORY_BASE'] = BASE
    os.environ['CI_INVENTORY_HEAD'] = head
    inventory = h.module('cap1r3_discovery', S / 'scripts/capabilities/collect_ci_inventory.py')
    parsed = inventory.parse_workflow((S / inventory.WORKFLOW).read_bytes())
    entries = parsed['entries'] + [inventory.primary_entry(S, parsed)]
    assets = {r['path']: r['sha256'] for r in load(D / 'assets.json')['assets']}
    tip = h.remote_archive()
    chosen, new_count = [], 0
    for i, entry in enumerate(entries):
        start = entry['start'].rstrip('/') + '/'
        touched = sorted(p for p in changed_paths if p.startswith(start) and fnmatch.fnmatch(p.rsplit('/', 1)[-1], entry['pattern']))
        matching, definition_changed = [], True
        if not touched:
            for path, value, locator in candidates.values():
                r = value['receipt']
                if value['entry'] != entry:
                    continue
                definition_changed = False
                if not r['complete'] or r['errors'] or r['unresolved_instances']:
                    continue
                if assets.get(r['collector']['path']) != r['collector']['sha256']:
                    continue
                if any(assets.get(m['module_path']) != m['module_sha256'] for m in r['methods']):
                    continue
                matching.append((path, value, locator))
            assert len(matching) <= 1, (entry['entry_id'], [m[0] for m in matching])
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
                   'workflow_definition_changed': bool(not touched and definition_changed),
                   'sha256': sha(path.read_bytes()), 'instances': r['discovered_instances']}
            new_count += 1
        row.update(start=entry['start'], pattern=entry['pattern'], line=entry.get('line'))
        chosen.append(row)
    write(D / 'discovery-selection.json', {'entries': chosen, 'entry_count': len(chosen), 'reused': len(chosen) - new_count,
          'new_collections': new_count, 'changed_paths_vs_main': changed_paths, 'archive_tip_checked': tip,
          'workflow_sha256': parsed['workflow_sha256'],
          'reuse_basis': 'Exact workflow entry (including its line), collector and owner-module hashes from the PR273 r4 and #282 r2 build receipts; '
                         'entries owning changed modules or whose workflow definition moved are recollected.',
          'test_bodies_executed': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'entries': len(chosen), 'reused': len(chosen) - new_count, 'new_collections': new_count,
                      'recollected': [c['start'] + ' ' + c['pattern'] for c in chosen if not c['reused']]}), flush=True)


def union():
    """Previous catalog for generation: main's catalog, which keeps every object version of PR273 r1-r4, PR6 and earlier."""
    invariant()
    union_dir = D / 'previous-union'
    assert not union_dir.exists() and not (D / 'union-acceptance.json').exists()
    union_dir.mkdir()
    header = json.loads(show(PREV, DATA + 'registry.json'))
    for name in ['registry.json', *header['object_parts'], 'catalog-sources.json', 'asset-index.json', 'entrypoint-index.json']:
        raw = show(PREV, DATA + name)
        if raw is not None:
            (union_dir / name).write_bytes(raw)
    merged = task.objects(union_dir)
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        assert all(merged.get(k) == v for k, v in expected.items()), name
        retention[name] = {'revision': rev, 'objects': len(expected)}
    write(D / 'union-acceptance.json', {'previous': PREV, 'previous_kind': 'published r2 catalog (superset of main)', 'union_dir': str(union_dir), 'union_objects': len(merged), 'retention': retention,
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'union_objects': len(merged)}), flush=True)


def archive():
    invariant()
    assert not (D / 'archive.json').exists()
    parent = h.remote_archive()
    assert parent == ARCHIVE_TIP, parent
    git('merge-base', '--is-ancestor', R2_CONSTRUCTION, parent)
    receipt = D / 'rust-listing/artifact/rust-test-listing.json'
    summary = load(D / 'rust-listing/summary.json')
    reuse = load(D / 'rust-listing/reuse.json')
    head, _ = head2()
    assert summary['head'] == LISTING_HEAD == reuse['listing_head'] and reuse['head'] == head and summary['complete']
    archived_listing = git('show', R2_CONSTRUCTION + ':' + PREFIX + '/rust-listing/rust-test-listing.json')
    assert archived_listing == receipt.read_bytes(), 'the r2 archived listing differs from the reused receipt'
    dest = D / 'archive-files' / PREFIX3
    (dest / 'rust-listing').mkdir(parents=True)
    shutil.copyfile(D / 'rust-listing/reuse.json', dest / 'rust-listing/reuse.json')
    for name in ('commits.json', 'assets.json', 'discovery-selection.json', 'union-acceptance.json'):
        shutil.copyfile(D / name, dest / name)
    shutil.copyfile(R2 / 'publication.json', dest / 'r2-publication.json')
    if (D / 'new-discovery').exists():
        shutil.copytree(D / 'new-discovery', dest / 'new-discovery')
    evidence = load(WORKER / 'result.json').get('archive_evidence') or []
    for item in evidence:
        rel = item['archive_path']
        assert rel and not rel.startswith('/') and '..' not in rel.split('/'), rel
        raw = Path(item['source']).read_bytes()
        assert sha(raw) == item['sha256'], rel
        target = dest / 'pr-evidence' / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        assert not target.exists(), rel
        target.write_bytes(raw)
    shutil.copyfile(__file__, dest / 'prepare_cap1_r3.py')
    (dest / 'README.md').write_text('# Capability batch 1 catalog inputs, round 3\n\n'
        'Round 3, on the round 2 head ' + PREV[:8] + ', fixes the three review findings: the two main-kernel comparisons read the '
        'registered EVAS_TEST_BASELINE_KERNEL selector pinned to the main kernel sha (R1-ST-01); the by-name check runner fails when a '
        'check ends early or leaves no complete receipt, and a workflow step verifies the receipt (R1-ST-02); an explicit null '
        'proof_work_limit in a CLI manifest is rejected (R1-SP-01); the batch 1 cards follow. No Rust input changed after ' + LISTING_HEAD[:8] + ', so the Rust listing is the one '
        'archived in round 2 (' + R2_CONSTRUCTION[:8] + ', CI ' + str(summary['run']) + '). Discovery entries owning changed test modules are '
        'recollected; the others reuse the PR273 r4 and round 2 receipts. pr-evidence/ holds the new one-time PR evidence. '
        'Criteria and DUT change; collector, language profile and invocation do not. Scientific qualification is false.\n')
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
    commit = git('commit-tree', tree, '-p', parent, '-m', 'Archive the capability batch 1 round 3 catalog inputs').decode().strip()
    idx.unlink()
    write(D / 'archive.json', {'parent': parent, 'remote_parent': parent, 'commit': commit, 'tree': tree, 'prefix': PREFIX, 'files': files,
          'pr_evidence': evidence, 'published': False})
    config = load(R4 / 'config.json')
    old_listings = config['rust_listings']
    assert [x['profile'] for x in old_listings] == [PROFILE]
    r2_listings = load(R2 / 'config.json')['rust_listings']
    config.update(source_root=str(S), archive_repository=str(S), previous_data_dir=str(D / 'previous-union'),
                  asset_receipt=str(D / 'assets.json'), source_repositories={'vaevas': str(S)}, discoveries=[], discovery_source_locators={},
                  rust_listings=[{'receipt_file': str(receipt), 'profile': PROFILE,
                                  'source_locator': {'kind': 'git-object', 'repository': 'vaevas', 'revision': R2_CONSTRUCTION,
                                                     'path': PREFIX + '/rust-listing/rust-test-listing.json'}}])
    selection = load(D / 'discovery-selection.json')
    for row in selection['entries']:
        path = Path(row['entry_file'])
        config['discoveries'].append({'entry_file': str(path)})
        config['discovery_source_locators'][row['entry_id']] = row.get('source_locator') or {
            'kind': 'git-object', 'repository': 'vaevas', 'revision': commit, 'path': PREFIX3 + '/new-discovery/' + path.name}
    new = {e['entry_id'] for e in selection['entries']}
    for bridge in config['bridge_evidence']:
        assert all(cid in new for cid in bridge['consumer_entry_ids']), bridge['path']
    write(D / 'config.json', config)
    assert [x['source_locator'] for x in r2_listings] == [x['source_locator'] for x in config['rust_listings']], 'round 3 keeps the round 2 listing locator'
    write(D / 'rust-listing-change.json', {'old': old_listings, 'r2': r2_listings, 'new': config['rust_listings']})
    invariant()
    print(json.dumps({'archive': commit, 'parent': parent, 'files': len(files), 'pr_evidence': len(evidence)}), flush=True)


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
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    largest = max(sizes.items(), key=lambda x: x[1])
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
          'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind, 'deterministic_double_generation': True,
          'hand_written_registry_objects_unchanged': len(inline_before),
          'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes, 'largest_data_file': largest,
          'd1_threshold': {'rule': 'coordinator 2026-10-28: schedule D1 when any catalog part exceeds 35 MB', 'bytes': D1_PART_THRESHOLD,
                           'reached': largest[1] > D1_PART_THRESHOLD},
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'new_object_versions': len(new_objects),
                      'by_kind': by_kind, 'largest': largest}), flush=True)


def generate_accept():
    """Acceptance of the attempt 1 generation outputs (catalog/, catalog-repeat/), which completed twice and byte-identical;
    attempt 1 stopped in its own acceptance at the strict retention of the published r2 catalog. The round 3 card commit edits
    the PR's hand-written registry objects in place at version 1, as round 2 did on the phase 1 head; the generator keeps
    normative (hand-written) objects as written. So the only allowed differences from the previous union are hand-written objects
    of this PR that main does not have. Generated objects keep every previous version; main and older revisions keep everything."""
    invariant()
    assert not (D / 'generation-acceptance.json').exists()
    assert load(D / 'config.json')['previous_data_dir'] == str(D / 'previous-union')
    for name in ('catalog', 'catalog-repeat'):
        assert (D / name / 'generation-report.json').exists(), name
        assert (D / ('generation-' + name + '.stdout')).exists()
    first, second = D / 'catalog/tree/evas/capabilities/data', D / 'catalog-repeat/tree/evas/capabilities/data'
    files_a = {p.name: p.read_bytes() for p in first.glob('*.json')}
    files_b = {p.name: p.read_bytes() for p in second.glob('*.json')}
    assert files_a.keys() == files_b.keys() and all(files_a[k] == files_b[k] for k in files_a), 'generation is not deterministic'
    report = load(D / 'catalog/generation-report.json')
    assert report['source_capture'] == head2()[0]
    previous, current = task.objects(D / 'previous-union'), task.objects(first)
    normative = {(o['id'], o['version']) for o in json.loads((S / DATA / 'registry.json').read_text())['objects']}
    main_objects = h.objects_at(BASE)
    missing = sorted(k for k in previous if k not in current)
    rewritten = sorted(k for k, v in previous.items() if k in current and current[k] != v)
    allowed = sorted(k for k in rewritten if k in normative and k not in main_objects)
    assert not missing and rewritten == allowed, (missing[:5], sorted(set(rewritten) - set(allowed))[:5])
    assert report['previous_object_versions_retained'] == len(previous) and not report['qualification_added']
    retention = {}
    for name, rev in RETENTION_REVS:
        expected = h.objects_at(rev)
        lost = [list(k) for k in expected if k not in current]
        changed = [k for k, v in expected.items() if k in current and current[k] != v]
        exempt = [k for k in changed if k in allowed and name == 'pr282_r2_published']
        assert not lost and len(changed) == len(exempt), (name, len(lost), len(changed), len(exempt))
        retention[name] = {'revision': rev, 'objects': len(expected), 'missing': 0, 'rewritten': len(exempt),
                           'rewritten_rule': 'PR-only hand-written objects edited in place by the round 3 card commit' if exempt else None}
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
        target = S / 'evas/capabilities/data' / p.name
        if not target.exists() or p.read_bytes() != target.read_bytes():
            target.write_bytes(p.read_bytes())
            paths.append(target.relative_to(S).as_posix())
    assert DATA + 'language-profile.json' not in paths
    sizes = {p.name: p.stat().st_size for p in sorted((S / 'evas/capabilities/data').glob('*.json'))}
    assert all(size < WARNING_BYTES for size in sizes.values()), sizes
    new_objects = [k for k in current if k not in previous]
    by_kind = {}
    for k in new_objects:
        kind = current[k].get('kind', 'unknown')
        by_kind[kind] = by_kind.get(kind, 0) + 1
    largest = max(sizes.items(), key=lambda x: x[1])
    write(D / 'generation-acceptance.json', {'paths': sorted(paths), 'old_versions_retained': len(previous), 'retention': retention,
          'pr_only_hand_written_objects_rewritten': [list(k) for k in allowed],
          'rewrite_rule': 'hand-written (normative) registry objects of this PR, absent from main, edited in place at version 1 by the round 3 card commit; round 2 did the same on the phase 1 head; generated objects keep every previous version',
          'generation_attempt': 'attempt 1 outputs reused: both generations completed and are byte-identical; attempt 1 stopped only in its own strict acceptance (prepare_cap1_r3.attempt1-generate-strict-retention.py, generate.stderr)',
          'new_object_versions': len(new_objects), 'new_object_versions_by_kind': by_kind, 'deterministic_double_generation': True,
          'hand_written_registry_objects_unchanged': len(inline_before),
          'version_lists': {'ids': len(versions), 'problems': 0, 'rule': 'each id keeps every previous version and gains at most one new version, which is current'},
          'objects': report['objects'], 'namespace_counts': report['namespace_counts'], 'data_file_sizes': sizes, 'largest_data_file': largest,
          'd1_threshold': {'rule': 'coordinator 2026-10-28: schedule D1 when any catalog part exceeds 35 MB', 'bytes': D1_PART_THRESHOLD,
                           'reached': largest[1] > D1_PART_THRESHOLD},
          'scientific_qualification': False})
    invariant()
    print(json.dumps({'generated_paths': len(paths), 'old_versions_retained': len(previous), 'rewritten_pr_only': len(allowed),
                      'new_object_versions': len(new_objects), 'by_kind': by_kind, 'largest': largest}), flush=True)


def derive():
    invariant()
    assert not (D / 'derive-acceptance.json').exists()
    results = []
    h.run_logged('capability-render.txt', [str(PY), '-B', 'evas/capabilities/render.py'], results)
    h.run_logged('traceability-generate.txt', [str(PY), '-B', 'scripts/traceability.py', '--catalog-data', 'evas/capabilities/data'], results)
    head, _ = head2()
    paths = changed_vs(head)
    rendered = set(h.render_outputs(S))
    unexpected = sorted(set(paths) - rendered - DERIVED_DATA - {'evas/docs/development/TRACEABILITY.md'})
    assert not unexpected, unexpected
    assert not any(p.startswith(CRITERIA_PREFIXES + DUT_PREFIXES) or p in COLLECTOR for p in paths)
    write(D / 'derive-acceptance.json', {'r3_head': head, 'paths_vs_r3': paths, 'render_outputs': len(rendered), 'checks': results,
          'files': {p: sha((S / p).read_bytes()) for p in sorted(paths) if (S / p).is_file()}, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'paths_vs_r3': len(paths)}), flush=True)


def freeze():
    invariant()
    cm, der = load(D / 'commits.json'), load(D / 'derive-acceptance.json')
    parent, _ = head2()
    assert not (D / 'final-candidate.json').exists()
    assert all(row['returncode'] == 0 for row in der['checks'])
    assert all(sha((S / path).read_bytes()) == digest for path, digest in der['files'].items())
    generated = changed_vs(parent)
    assert sorted(generated) == sorted(der['paths_vs_r3'])
    head, tree = commit_tree(parent, generated, FINAL_MESSAGE, [parent], 'final')
    for anc in (BASE, PREV, parent):
        git('merge-base', '--is-ancestor', anc, head)
    complete = sorted(git('diff', '--no-renames', '--name-only', BASE, head).decode().splitlines())
    criteria = sorted(p for p in complete if p.startswith(CRITERIA_PREFIXES))
    collector = sorted(p for p in complete if p in COLLECTOR)
    dut = sorted(p for p in complete if p.startswith(DUT_PREFIXES))
    assert not collector and DATA + 'language-profile.json' not in complete
    assert criteria == cm['criteria_changes'] and len(dut) == cm['dut_changes']
    blobs, changed = [], set(complete)
    for line in git('ls-tree', '-r', '-l', head).decode().splitlines():
        meta, path = line.split('\t', 1)
        size = int(meta.split()[3])
        if size >= WARNING_BYTES:
            blobs.append({'path': path, 'bytes': size, 'changed_vs_main': path in changed})
    assert not [b for b in blobs if b['changed_vs_main']], blobs
    final = {'commit': head, 'tree': tree, 'base': BASE, 'prev': PREV, 'r3_head': parent, 'complete_paths': complete,
             'criteria_changes': criteria, 'collector_changes': collector, 'dut_changes': dut, 'derive': str(D / 'derive-acceptance.json'),
             'large_unchanged_blobs': blobs, 'precheck': 'runs on the frozen head in parallel with CI', 'CI': 'pending',
             'review': 'pending: strict-tier priority Astra', 'registration': 'required (criteria and DUT change)',
             'published': False, 'scientific_qualification': False, 'frozen_at_utc': datetime.now(timezone.utc).isoformat()}
    write(D / 'final-candidate.json', final)
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
          'scope': 'Capability batch 1 round 3, quick maintenance gate plus every static-checks traceability step command; full scientific regression is CI only.'})
    h.run_logged('maintenance-fast-checks.txt', [str(PY), '-B', 'scripts/ci_lint.py', '--plan', str(D / 'maintenance-plan.json')], results)
    h.run_logged('capability-views.txt', [str(PY), '-B', 'evas/capabilities/render.py', '--check'], results)
    h.run_logged('capability-tests.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'evas/capabilities', '-p', 'test_*.py', '-v'], results)
    h.run_logged('requirement-links.txt', [str(PY), '-B', 'evas/capabilities/requirement_links.py'], results)
    h.run_logged('traceability-check.txt', [str(PY), '-B', 'scripts/traceability.py', '--check', '--catalog-data', 'evas/capabilities/data'], results)
    h.run_logged('diagnostic-inventory-check-final.txt', [str(PY), '-B', 'scripts/diagnostic_inventory.py', '--check'], results)
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    modules = ['test_catalog_derived_outputs.py', 'test_catalog_part_split.py', 'test_catalog_history_selection.py', 'test_traceability.py',
               'test_rust_catalog_reconcile.py', 'test_ci_inventory.py', 'test_ci_selection.py', 'test_ci_pins.py', 'test_discover_rust.py',
               'test_regression_shard_selection.py', 'test_regression_admission.py', 'test_context_registration.py', 'test_regression_gate.py']
    modules += [p.rsplit('/', 1)[-1] for p in load(D / 'commits.json')['r2_paths']
                if p.startswith('scripts/tests/test_') and p.endswith('.py') and p.rsplit('/', 1)[-1] not in modules]
    for name in modules:
        h.run_logged('affected-' + name.removesuffix('.py') + '.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', name, '-v'],
                     results, extra_env=tools)
    fixtures = D / 'git-fixture-isolation'
    fixtures.mkdir(exist_ok=True)
    static_env = tools | {'GIT_FIXTURE_RETAIN_DIR': str(fixtures)}
    h.run_logged('static-verify-validation-version.txt', [str(PY), '-B', 'scripts/verify_validation_version.py'], results, extra_env=static_env)
    h.run_logged('static-scripts-tests-full.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-v'], results, extra_env=static_env)
    h.run_logged('diff-check.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': len(paths),
          'checks': results, 'scientific_execution': False, 'scientific_qualification': False})
    invariant()


def precheck_retry():
    """Attempt 1 of precheck ran every check on the frozen head; all passed except the full scripts/tests discovery, whose
    test_git_fixture_isolation.setUpClass requires GIT_FIXTURE_RETAIN_DIR not to exist yet (mkdir exist_ok=False) while
    attempt 1 had created that directory first (harness error, CI uses a fresh runs/git-fixture-isolation). Rerun that
    command with a fresh retention path and new log names, then the diff check; earlier logs are read, never rewritten."""
    invariant()
    final = load(D / 'final-candidate.json')
    assert not (D / 'precheck-acceptance.json').exists()
    assert git('rev-parse', 'HEAD', source=True).decode().strip() == final['commit']
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip()
    earlier = []
    for line in (D / 'precheck.stdout').read_text().splitlines():
        name, code = line.rsplit(' ', 1)
        log = (D / name).read_text()
        assert log.rstrip().endswith('returncode=' + code), name
        command = log.splitlines()[0]
        assert command.startswith('COMMAND '), name
        earlier.append({'receipt': str(D / name), 'returncode': int(code), 'command': command[len('COMMAND '):],
                        'receipt_sha256': sha((D / name).read_bytes()), 'attempt': 1})
    failed = [r for r in earlier if r['returncode'] != 0]
    assert [Path(r['receipt']).name for r in failed] == ['static-scripts-tests-full.txt'], failed
    assert 'FileExistsError' in (D / 'static-scripts-tests-full.txt').read_text()
    results = []
    tools = {'PATH': str(Path.home() / '.cargo/bin') + ':' + os.environ.get('PATH', '/usr/bin:/bin')}
    fixtures = D / 'git-fixture-isolation-retry1'
    assert not fixtures.exists()
    static_env = tools | {'GIT_FIXTURE_RETAIN_DIR': str(fixtures)}
    h.run_logged('static-scripts-tests-full-retry1.txt', [str(PY), '-B', '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-v'], results, extra_env=static_env)
    h.run_logged('diff-check-retry1.txt', ['/usr/bin/git', '--git-dir=' + str(S / '.git'), '--work-tree=' + str(S), 'diff', '--check', BASE], results)
    assert not git('status', '--porcelain=v1', '--untracked-files=no', source=True).strip(), 'checks changed committed bytes'
    checks = [dict(r, attempt=1) for r in earlier if r['returncode'] == 0] + [dict(r, attempt=2) for r in results]
    write(D / 'precheck-acceptance.json', {'base': BASE, 'candidate': final['commit'], 'tree': final['tree'], 'paths_vs_base': len(final['complete_paths']),
          'checks': checks, 'failed_attempts': [dict(r, reason='harness created GIT_FIXTURE_RETAIN_DIR before the run; the test requires a fresh path') for r in failed],
          'scientific_execution': False, 'scientific_qualification': False})
    invariant()
    print(json.dumps({'checks': len(checks), 'retried': [Path(r['receipt']).name for r in results]}), flush=True)


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
    parser.add_argument('stage', choices=['series', 'listing', 'assets', 'discover', 'union', 'archive', 'generate', 'generate_accept', 'derive', 'precheck_retry',
                                          'freeze', 'precheck', 'inventory'])
    globals()[parser.parse_args().stage]()

"""Round-2 helpers for the #282 C0 rebuild on the new main 6fed3c82 (PR-A merged as #293).

Reuses the round-1 helpers of ../common.py by import only (that file is not changed). Round-2 writes go to flow/r2 and
flow/c0-r2; round-1 files are read, never rewritten. Git objects of the new main come from three read-only sources, listed
as alternates of the round-2 private repository: the shared store, the PR-A implementer's private repository (PR-A head
e59bf81f, archive tip 18a202cb) and the round-1 private C0 repository (bundle archive 2b2569c4). The GitHub merge commit
6fed3c82 itself is rebuilt from the API record (check_pr_a.py) and written into the round-2 private repository only.
"""
from pathlib import Path
import sys

R2 = Path(__file__).resolve().parent
FLOW = R2.parent
sys.path.insert(0, str(FLOW))
from common import *  # noqa: E402,F401,F403  (round-1 helpers, imported read-only)
import common as round1  # noqa: E402

C0R2 = FLOW / 'c0-r2'
PRA_REPO = B / 'registration-rule-dut-fix-impl-opus-20261029/r2a2/repo/.git'
ROUND1_C0 = FLOW / 'c0'
ROUND1_REPO = ROUND1_C0 / 'source/.git'
NEW_MAIN = '6fed3c820b6eaecdfabd6d5dcacf8febdd197e4c'
NEW_MAIN_TREE = '38ee802ae85703e070812d7dfedd7af0bf7d4043'
OLD_MAIN = round1.MAIN
PRA_HEAD = 'e59bf81f063159e29c379623a98928d73786aa45'
ARCHIVE_TIP_R2 = '18a202cb00c0a040e504d6235c503f0a52f5ebd7'
BUNDLE_ARCHIVE = '2b2569c4ededf5701446c29e9853c61a45457bad'
MAIN_PUSH_RUN = 40857285671
COLLECTOR4 = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
              'scripts/regression_observation_policy.json')
ALTERNATES = (COMMON_OBJECTS, PRA_REPO / 'objects', ROUND1_REPO / 'objects')
MIB80 = 80 * 1024 * 1024


def inside_r2(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(R2.resolve()) or resolved.is_relative_to(C0R2.resolve()), resolved
    return resolved


def write_r2(path, value):
    inside_r2(Path(path).parent)
    return write_new(path, value)


def commit_paths_r2(repo, parent, paths, message, parents, index_name):
    """round1.commit_paths with its temporary index under r2/indexes (round-1 directories stay untouched)."""
    index = R2 / 'indexes' / (index_name + '.index')
    assert not index.exists(), index
    index.parent.mkdir(exist_ok=True)
    pgit(repo, 'read-tree', parent, index=index)
    modes = entries(repo, parent)
    files = {}
    for path in paths:
        target = Path(repo) / path
        if target.exists():
            raw = target.read_bytes()
            mode = modes.get(path, ('100755' if os.access(target, os.X_OK) else '100644', None))[0]
            oid = pgit(repo, 'hash-object', '-w', '--stdin', data=raw).decode().strip()
            pgit(repo, 'update-index', '--add', '--cacheinfo', mode + ',' + oid + ',' + path, index=index)
            files[path] = sha(raw)
        else:
            pgit(repo, 'update-index', '--force-remove', path, index=index)
            files[path] = None
    tree = pgit(repo, 'write-tree', index=index).decode().strip()
    args = []
    for p in parents:
        args += ['-p', p]
    commit = pgit(repo, 'commit-tree', tree, *args, '-m', message + TRAILER).decode().strip()
    index.unlink()
    return {'commit': commit, 'tree': tree, 'parents': list(parents), 'paths': sorted(paths), 'files': files, 'at_utc': utc()}


def guard_record_r2(name):
    out = R2 / 'guards' / (name + '.json')
    args = [sys.executable, '-B', str(R2 / 'guard_r2.py'), str(out), '--compare', str(R2 / 'guard-before-r2.json')]
    r = subprocess.run(args, env=env_py(), capture_output=True, cwd=R2)
    record = load(out)
    assert r.returncode == 0 and record['all_unchanged'] and record['config_ok'], (r.returncode, r.stdout.decode()[-800:])
    if record['shared_config']['status'] != 'equal-accepted':
        print('shared config pre-accepted change recorded in', out, flush=True)
    return record


def production_r2(repo, rev=NEW_MAIN, tag='main'):
    """regression_gate and regression_context_registration exactly as committed at rev, read from the private repository."""
    out = R2 / 'code' / (tag + '-' + rev[:8])
    out.mkdir(parents=True, exist_ok=True)
    blobs = {}
    for name in ('regression_gate.py', 'regression_context_registration.py', 'materialize_registration_bundle.py'):
        raw = pgit(repo, 'show', rev + ':scripts/' + name)
        path = out / name
        if not path.exists():
            path.write_bytes(raw)
        assert path.read_bytes() == raw, path
        blobs[name] = sha(raw)
    gate = module('flow_r2_gate_' + tag, out / 'regression_gate.py')
    reg = module('flow_r2_reg_' + tag, out / 'regression_context_registration.py')
    return gate, reg, dict(blobs, revision=rev, directory=str(out))

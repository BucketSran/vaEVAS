"""Shared helpers for the #282 trusted-context registration flow (everything under W/flow).

Boundaries (brief of 2026-10-29):
- The real repository is read only: /usr/bin/git --no-lazy-fetch --git-dir=<worktree git dir>, inherited GIT_* cleared,
  read subcommands only. No refs, index, config or object writes there, no fetch.
- Every write goes under W/flow. Private exports get their own .git whose objects/info/alternates points at the shared
  object store; every new object, index and commit lives in that private .git.
- Receipts and logs are created exclusively and never replaced; a retry writes new names.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys

sys.dont_write_bytecode = True

F = Path(__file__).resolve().parent
W = F.parent
B = W.parent
PR6 = B / 'pr6/context-registration-20261027'
R3 = B / 'capability-batch1-pr-r3-20261028'
R4 = B / 'pr6/ci-pins-a-20261027/r4'
REAL_WORKTREE = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/worktrees/ir33-regression-night')
GD = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/worktrees/ir33-regression-night')
COMMON_OBJECTS = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/objects')
# 3.12 lint venv used by the PR6 and #282 r3 prechecks (CI uses 3.12.15; no other 3.12 is installed here).
PY = B / 'pr4/trusted-context/SP-01/lint-venv/bin/python'
GIT = '/usr/bin/git'
REPO = 'BucketSran/vaEVAS'
REPO_URL = 'https://github.com/' + REPO

MAIN = 'd6b7543fc815aaa584c886108691b6f2c01eb220'
MAIN_TREE = 'c299c287165fa29ead86442956296b0a825aa35b'
HEAD282 = '84d6b71f8fbfd19b31f1696a88cb35643b375b3d'
HEAD282_TREE = 'e2e9755ea7916b03144e27b553da3ef89562a034'
E1_RUN = 40762672880
E1_RUN_URL = REPO_URL + '/actions/runs/' + str(E1_RUN)
E1_RAW_SHA = '7cc4bd08613c01716c69d47eeb29e6e484781664a454aa1c8497b4259561c6ac'
E1_MAPPING_SHA = '2c144950169c347721566f4530fdf3dd7daeca19303855b12f3d69fdb075a477'
E1_RECORD_SHA = '885ce82e'  # prefix given in the brief; the full value is read from the file and recorded
MATCHED_CONTEXT = 4
D0_DUT = '5e9bf28ad121569a6975811f0b5ea9e60423e676e6dfcf88048948bfd19ba056'
D0_KERNEL = 'b957460310caebac4a8c86710b1e35d8dc74fe63784bc06f1fe0319521337dbe'
E1_DUT = '7713308b855e99f30f5979b3b93f80489f5f772eadd86d53d52497674a5bec9b'
E1_KERNEL = '3353bed859b7904de383e540d9efdc3b386ed90abceca77557c8119813214687'
NEW_POOL = {'platform': 'Linux-7.0.0-1017-azure-x86_64-with-glibc2.39', 'ImageVersion': '20261026.354.1'}
OLD_POOL = {'platform': 'Linux-6.17.0-1022-azure-x86_64-with-glibc2.39', 'ImageVersion': '20261023.334.3'}

BASELINE_PATH = 'evas/validation/baselines/regression-v1.json'
REVIEW_PATH = 'evas/validation/baselines/regression-v1.review.json'
POINTER_PATH = 'scripts/context-registration-bundle.json'
ROLES = ('composition_recipe', 'snapshot_manifest', 'dut_build', 'kernel_binary', 'collector_manifest',
         'artifact_manifest', 'stdout', 'stderr', 'shard_reports')
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
AUTHOR = {'GIT_AUTHOR_NAME': 'BucketSran', 'GIT_AUTHOR_EMAIL': '138781625+BucketSran@users.noreply.github.com',
          'GIT_COMMITTER_NAME': 'BucketSran', 'GIT_COMMITTER_EMAIL': '138781625+BucketSran@users.noreply.github.com'}
READ_ONLY = {'show', 'ls-tree', 'rev-parse', 'cat-file', 'archive', 'merge-base', 'diff', 'log', 'rev-list', 'ls-files'}


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return sha(canonical(value))


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def load(path):
    return json.loads(Path(path).read_bytes())


def inside_flow(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(F.resolve()), resolved
    return resolved


def write_new(path, value):
    """Create a receipt exclusively under W/flow; bytes are written as given, other values as indent-2 JSON."""
    path = Path(path)
    inside_flow(path.parent if not path.exists() else path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else dump(value))
    return path


def clean_env():
    return {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def env_py():
    return clean_env() | {'PYTHONDONTWRITEBYTECODE': '1'}


def rgit(*args, data=None, check=True):
    """Read-only git on the shared object store through the real worktree's git dir."""
    assert args and args[0] in READ_ONLY, args
    env = clean_env() | {'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'LC_ALL': 'C'}
    r = subprocess.run([GIT, '--no-lazy-fetch', '--git-dir=' + str(GD), *args], env=env, input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=F)
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def rshow(rev, path):
    return rgit('show', rev + ':' + path)


def private_env(index=None):
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0',
                         'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'} | AUTHOR
    if index is not None:
        env['GIT_INDEX_FILE'] = str(inside_flow(Path(index).parent) / Path(index).name)
    return env


def pgit(repo, *args, index=None, data=None, check=True):
    """Git on a private export under W/flow; writes stay in its own .git (alternates only read the shared store)."""
    repo = inside_flow(repo)
    r = subprocess.run([GIT, '--no-lazy-fetch', '--git-dir=' + str(repo / '.git'), '--work-tree=' + str(repo), *args],
                       env=private_env(index), input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=repo)
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def export(rev, target, private_repo, branch='flow'):
    """git archive of rev from the shared store into a new directory; optionally a private .git with alternates."""
    target = Path(target)
    inside_flow(target.parent)
    assert not target.exists(), target
    target.mkdir(parents=True)
    with (target.parent / ('export-' + target.name + '.stderr')).open('xb') as err:
        env = clean_env() | {'GIT_OPTIONAL_LOCKS': '0', 'GIT_TERMINAL_PROMPT': '0', 'GIT_CONFIG_NOSYSTEM': '1', 'LC_ALL': 'C'}
        producer = subprocess.Popen([GIT, '--no-lazy-fetch', '--git-dir=' + str(GD), 'archive', rev], env=env,
                                    stdout=subprocess.PIPE, stderr=err, cwd=F)
        consumer = subprocess.run(['/usr/bin/tar', '-x', '-C', str(target)], stdin=producer.stdout, env=env)
        producer.stdout.close()
        assert producer.wait() == consumer.returncode == 0
    if not private_repo:
        return
    r = subprocess.run([GIT, '--git-dir=' + str(target / '.git'), '--work-tree=' + str(target), 'init', '--quiet', '--template=',
                        '--initial-branch=' + branch], cwd=target, env=private_env(), capture_output=True)
    assert r.returncode == 0, r.stderr
    (target / '.git/objects/info/alternates').write_text(str(COMMON_OBJECTS) + '\n')
    pgit(target, 'read-tree', rev)
    pgit(target, 'update-ref', 'HEAD', rev)
    assert Path(pgit(target, 'rev-parse', '--absolute-git-dir').decode().strip()).resolve() == (target / '.git').resolve()


def entries(repo, rev):
    """{path: (mode, blob)} of a commit, read from the private repo (alternates) or the shared store when repo is None."""
    run = (lambda *a: pgit(repo, *a)) if repo is not None else rgit
    rows = {}
    for item in run('ls-tree', '-r', '-z', rev).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            assert kind == 'blob', path
            rows[path.decode()] = (mode, oid)
    return rows


def commit_paths(repo, parent, paths, message, parents, index_name):
    """Commit the export's bytes of paths on top of parent, in the private repo only."""
    index = F / 'indexes' / (index_name + '.index')
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


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def production(rev=MAIN, tag='main'):
    """regression_gate and regression_context_registration exactly as committed at rev, loaded from W/flow copies."""
    out = F / 'code' / (tag + '-' + rev[:8])
    gate_raw, reg_raw = rshow(rev, 'scripts/regression_gate.py'), rshow(rev, 'scripts/regression_context_registration.py')
    out.mkdir(parents=True, exist_ok=True)
    for name, raw in (('regression_gate.py', gate_raw), ('regression_context_registration.py', reg_raw)):
        path = out / name
        if not path.exists():
            path.write_bytes(raw)
        assert path.read_bytes() == raw, path
    gate = module('flow_gate_' + tag, out / 'regression_gate.py')
    reg = module('flow_reg_' + tag, out / 'regression_context_registration.py')
    return gate, reg, {'regression_gate.py': sha(gate_raw), 'regression_context_registration.py': sha(reg_raw), 'revision': rev}


def run_logged(log, argv, cwd, results, extra_env=None, limit=3000):
    """Run argv under a perl alarm limit, output to a new log under W/flow; record and return the return code."""
    log = Path(log)
    inside_flow(log.parent)
    start = utc()
    env = env_py() | (extra_env or {})
    with log.open('x') as out:
        out.write('COMMAND ' + repr(argv) + '\nCWD ' + str(cwd) + '\nLIMIT_SECONDS ' + str(limit) + '\nSTARTED ' + start + '\n')
        out.flush()
        r = subprocess.run(['/usr/bin/perl', '-e', 'alarm shift; exec @ARGV or die "exec: $!"', str(limit), *map(str, argv)],
                           cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT)
        out.write('\nFINISHED ' + utc() + '\nreturncode=' + str(r.returncode) + '\n')
    row = {'command': [str(a) for a in argv], 'cwd': str(cwd), 'log': str(log), 'returncode': r.returncode,
           'started_at_utc': start, 'finished_at_utc': utc(), 'limit_seconds': limit,
           'extra_env': {k: v for k, v in (extra_env or {}).items()}}
    results.append(row)
    print(log.name, r.returncode, flush=True)
    return r.returncode


def guard_record(name):
    """Run guard.py into a new file under W/flow/guards and return its record."""
    out = F / 'guards' / (name + '.json')
    out.parent.mkdir(exist_ok=True)
    before = F / 'guard-before.json'
    args = [sys.executable, '-B', str(F / 'guard.py'), str(out), '--compare', str(before)]
    r = subprocess.run(args, env=env_py(), capture_output=True, cwd=F)
    assert r.returncode == 0, r.stderr.decode()
    record = load(out)
    assert record['all_unchanged'] and record['head_matches'] and record['candidate_files_all_match_plan'], record
    return record

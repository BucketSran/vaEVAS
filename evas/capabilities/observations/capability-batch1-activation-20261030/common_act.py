"""Shared helpers for the #282 activation (round 1): the main merge into #282, the catalog, and the main session's scripts.

Boundaries (brief of 2026-10-30, W/brief.txt): only W = flow/activation-r1 is written. The real worktree, its index,
branch and shared config stay unchanged (guarded by ../r2/guard_r2.py, outputs in W/guards). Git runs as
/usr/bin/git --no-lazy-fetch with inherited GIT_* cleared and no system or global config; nothing is fetched. Commits
go to the private repository W/source/.git, whose alternates read the shared store and the three earlier private
repositories (round-3 C0, PR-A, round-1 C0) that hold main 0ad80828, the archive history and the bundle commit.
Every receipt and log is created exclusively; retries write new names.
"""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import threading
import time

sys.dont_write_bytecode = True

W = Path(__file__).resolve().parent
F = W.parent
B = F.parents[1]
GIT = '/usr/bin/git'
REPO = 'BucketSran/vaEVAS'
REPO_URL = 'https://github.com/' + REPO
PY = B / 'pr4/trusted-context/SP-01/lint-venv/bin/python'
COMMON_OBJECTS = Path('/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/.git/objects')
ALTERNATES = (COMMON_OBJECTS, F / 'c0-r3/source/.git/objects', B / 'registration-rule-dut-fix-impl-opus-20261029/r2a2/repo/.git/objects',
              F / 'c0/source/.git/objects')
VIEW = W / 'view.git'
S = W / 'source'
S282 = W / 'source-282'
TMP = W / 'tmp'
GUARD = F / 'r2/guard_r2.py'
GUARD_BEFORE = W / 'guards/activation-before.json'

BASE = '0ad80828f47aaea2dac94fcaf3acb99aeca0cf0d'           # main after #296 (C0 authority) and #297 (baseline append)
BASE_TREE = 'b0fa321b42eee3322eb5fde7c4542da52e87ac5f'
BASE_PARENTS = ['7a487c8f6e02ea06e0ec2531674d2a1a5086602f', '9ef7a700b07ef539c1ab0950536fdacff2ce1ff2']
HEAD282 = '84d6b71f8fbfd19b31f1696a88cb35643b375b3d'        # #282 head, branch codex/evas-capability-batch1
HEAD282_TREE = 'e2e9755ea7916b03144e27b553da3ef89562a034'
MERGE_BASE = 'd6b7543fc815aaa584c886108691b6f2c01eb220'
ARCHIVE_TIP = 'e91f96cc0b08385268dc187e47ad198e2f3637d7'     # gh api 2026-10-29T20:11:36Z (W/gh/archive-ref-start.json)
ARCHIVE_REF = 'refs/heads/codex/evas-method-audit-archive-20261025'
PR_BRANCH = 'refs/heads/codex/evas-capability-batch1'
PR = 282
PUSH_RUN = 40944364517                                       # main's push CI on 0ad80828
E1_RUN = 40762672880
E1_REPORT = F / 'bundle-r1/bundle/report.json'
E1_RAW_SHA = '7cc4bd08613c01716c69d47eeb29e6e484781664a454aa1c8497b4259561c6ac'
E1_MAPPING = F.parent / 'e1-mapping.json'
E1_MAPPING_SHA = '2c144950169c347721566f4530fdf3dd7daeca19303855b12f3d69fdb075a477'
R282 = B / 'capability-batch1-pr-r3-20261028'               # #282's own construction (head 84d6b71f)
C0R3 = F / 'c0-r3'                                           # main's last construction (head 9071629e, merged as #296)
NEW_HEADER, NEW_IMAGE = '20261025.353.1', '20261026.354.1'
DATA = 'evas/capabilities/data/'
PART_FILES = tuple([DATA + 'method-index-%02d.json' % i for i in range(16)] + [DATA + 'historical-index-%02d.json' % i for i in range(16)])
DERIVED_DATA = frozenset({DATA + 'registry.json', DATA + 'catalog-sources.json', DATA + 'asset-index.json', DATA + 'entrypoint-index.json',
                          *PART_FILES, 'evas/docs/development/TRACEABILITY.md'})
CRITERIA_DIRS = ('evas/tests', 'evas/validation', 'evas/examples', 'experiments')
DUT_DIRS = ('evas/src', 'evas/rust_core')
MANIFEST_SKIP = ('__pycache__', 'target', 'baselines', '.git', 'runs')   # scripts/run_regression.py file_manifest
LANGUAGE_PROFILE = 'evas/capabilities/data/language-profile.json'
COLLECTOR4 = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py',
              'scripts/regression_observation_policy.json')
BASELINE_PATH = 'evas/validation/baselines/regression-v1.json'
REVIEW_PATH = 'evas/validation/baselines/regression-v1.review.json'
WARNING_BYTES = 50 * 1024 * 1024
AUTHOR = {'GIT_AUTHOR_NAME': 'BucketSran', 'GIT_AUTHOR_EMAIL': '138781625+BucketSran@users.noreply.github.com',
          'GIT_COMMITTER_NAME': 'BucketSran', 'GIT_COMMITTER_EMAIL': '138781625+BucketSran@users.noreply.github.com'}
TRAILER = '\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'
CHAIN = 'c2'   # construction chain 2: registry.json keeps #282's hand-written objects; chain 1 (unsuffixed files) is superseded


def C(name):
    """The chain-2 name of a receipt, log, index or directory: capture.json -> capture-c2.json, previous-union -> previous-union-c2."""
    head, dot, ext = name.rpartition('.')
    return head + '-' + CHAIN + '.' + ext if dot and '/' not in ext else name + '-' + CHAIN


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


def load(path):
    return json.loads(Path(path).read_bytes())


def dump(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def inside_w(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(W.resolve()), resolved
    return resolved


def write_new(path, value):
    """Create a receipt exclusively inside W; bytes are written as given, other values as indent-2 JSON."""
    path = Path(path)
    inside_w(path.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(value if isinstance(value, bytes) else dump(value))
    return path


def clean_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    TMP.mkdir(exist_ok=True)
    env.update(TMPDIR=str(TMP), RUSTUP_AUTO_INSTALL='0', CARGO_NET_OFFLINE='true', PYTHONDONTWRITEBYTECODE='1')
    return env


def private_env(index=None):
    env = clean_env() | {'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_OPTIONAL_LOCKS': '0',
                         'GIT_TERMINAL_PROMPT': '0', 'LC_ALL': 'C'} | AUTHOR
    if index is not None:
        env['GIT_INDEX_FILE'] = str(inside_w(Path(index).parent) / Path(index).name)
    return env


def vgit(*args, data=None, check=True):
    """Git on W/view.git (bare, alternates only): reads before the private export exists."""
    r = subprocess.run([GIT, '--no-lazy-fetch', '--git-dir=' + str(VIEW), *args], env=private_env(), input=data,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=W)
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def pgit(repo, *args, index=None, data=None, check=True):
    """Git on a private repository inside W; new objects and refs stay in its own .git."""
    repo = inside_w(repo)
    r = subprocess.run([GIT, '--no-lazy-fetch', '--git-dir=' + str(repo / '.git'), '--work-tree=' + str(repo), *args],
                       env=private_env(index), input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=repo)
    if check and r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def show(rev, path, repo=None):
    r = subprocess.run([GIT, '--no-lazy-fetch', '--git-dir=' + str((repo / '.git') if repo else VIEW), 'show', rev + ':' + path],
                       env=private_env(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=W)
    return r.stdout if r.returncode == 0 else None


def entries(rev, repo=None):
    """{path: (mode, blob)} of a commit."""
    run = (lambda *a: pgit(repo, *a)) if repo is not None else vgit
    rows = {}
    for item in run('ls-tree', '-r', '-z', rev).split(b'\0'):
        if item:
            meta, path = item.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            assert kind == 'blob', path
            rows[path.decode()] = (mode, oid)
    return rows


def names(a, b, repo=None):
    run = (lambda *x: pgit(repo, *x)) if repo is not None else vgit
    rows = {}
    for line in run('diff', '--name-status', '--no-renames', a, b).decode().splitlines():
        status, path = line.split('\t', 1)
        rows[path] = status
    return rows


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def guard(name):
    """The real worktree's guard (ls-files -s SHA256, HEAD, branch, index.lock, 20 old candidates, shared config)."""
    out = W / 'guards' / (name + '.json')
    r = subprocess.run([sys.executable, '-B', str(GUARD), str(out), '--compare', str(GUARD_BEFORE)], env=clean_env(), capture_output=True, cwd=W)
    record = load(out)
    assert r.returncode == 0 and record['all_unchanged'] and record['config_ok'], ('guard', name, r.stdout.decode()[-600:])
    return record['observed_at']


def kernel_procs():
    r = subprocess.run(['/bin/ps', '-Ao', 'comm'], capture_output=True, env=clean_env())
    return sum(1 for line in r.stdout.decode(errors='replace').splitlines() if line.strip().rsplit('/', 1)[-1] == 'evas-kernel')


def kernel_log(text):
    with (W / 'logs/kernel-slot.log').open('a') as log:
        log.write('%s %s\n' % (utc(), text))


class KernelWatch:
    """Simulation slot rule: wait while the machine runs 2 evas-kernel processes, then sample during the step."""

    def __init__(self, label):
        self.label, self.peak, self.stop = label, 0, threading.Event()

    def __enter__(self):
        waited = 0
        while (n := kernel_procs()) >= 2:
            if waited % 300 == 0:
                kernel_log('wait %s: %d evas-kernel running' % (self.label, n))
            time.sleep(15)
            waited += 15
        kernel_log('before %s: %d evas-kernel' % (self.label, n))
        self.thread = threading.Thread(target=self.sample, daemon=True)
        self.thread.start()
        return self

    def sample(self):
        while not self.stop.wait(5):
            self.peak = max(self.peak, kernel_procs())

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        kernel_log('after %s: %d evas-kernel (peak during the step %d)' % (self.label, kernel_procs(), self.peak))
        return False


def run_logged(log, argv, cwd, results, extra_env=None, limit=3000, remove=()):
    """Run argv under a perl alarm limit with output to a new log inside W; record and return the return code."""
    log = Path(log)
    inside_w(log.parent)
    log.parent.mkdir(parents=True, exist_ok=True)
    start = utc()
    env = clean_env() | (extra_env or {})
    for key in remove:
        env.pop(key, None)
    with KernelWatch(log.name) as watch, log.open('x') as out:
        out.write('COMMAND ' + repr([str(a) for a in argv]) + '\nCWD ' + str(cwd) + '\nLIMIT_SECONDS ' + str(limit) + '\nSTARTED ' + start + '\n')
        out.flush()
        r = subprocess.run(['/usr/bin/perl', '-e', 'alarm shift; exec @ARGV or die "exec: $!"', str(limit), *map(str, argv)],
                           cwd=cwd, env=env, stdout=out, stderr=subprocess.STDOUT)
        out.write('\nFINISHED ' + utc() + '\nreturncode=' + str(r.returncode) + '\n')
    results.append({'command': [str(a) for a in argv], 'cwd': str(cwd), 'log': str(log), 'returncode': r.returncode,
                    'started_at_utc': start, 'finished_at_utc': utc(), 'limit_seconds': limit,
                    'extra_env': {k: v for k, v in (extra_env or {}).items()}, 'evas_kernel_peak_during_step': watch.peak})
    print(log.name, r.returncode, flush=True)
    return r.returncode


def gh_json(path, target):
    """One read-only gh api GET into a new file inside W."""
    target = Path(target)
    inside_w(target.parent)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('xb') as stream, Path(str(target) + '.stderr').open('xb') as err:
        r = subprocess.run(['gh', 'api', path], env=clean_env(), stdout=stream, stderr=err)
    assert r.returncode == 0, (path, Path(str(target) + '.stderr').read_text()[-400:])
    return load(target)


def disk_ok():
    """Stop rule: internal disk below 10 GiB free."""
    st = os.statvfs('/')
    free = st.f_bavail * st.f_frsize
    assert free >= 10 * 1024 ** 3, 'internal disk below 10 GiB free; stop and report'
    return free

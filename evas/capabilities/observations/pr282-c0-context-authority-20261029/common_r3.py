"""Round-3 helpers for the #282 C0 rebuild on main b4a07295 (#294, a squash commit on the PR-A main 6fed3c82).

Imports the round-2 helpers (common_r2.py, unchanged) and adds the round-3 directory flow/c0-r3. Round-3 writes go to
flow/r2 (new file names only) and flow/c0-r3. The objects of b4a07295 and of 6fed3c82 are in the shared store; the archive
tip 18a202cb (PR-A's construction archive) and the bundle commit 2b2569c4 are still read through the same two read-only
alternates as round 2 (the PR-A implementer's repository and the round-1 private C0 repository).
"""
from common_r2 import *  # noqa: F401,F403  (round-2 and round-1 helpers, imported read-only)

C0R3 = FLOW / 'c0-r3'
R3_MAIN = 'b4a072959d55fa3b23e34dfcadd92103ec89f2a3'
R3_MAIN_TREE = 'fa40153a848827cdac08f71147dda24fc1d30b6d'
ARCHIVE_TIP_R3 = '18a202cb00c0a040e504d6235c503f0a52f5ebd7'
R3_PUSH_RUN = 40864041959
R3_PUSH_DIR = R2 / 'runs/main-push-40864041959-catalog-inventory'
PRA_REGISTRATION_SHA = '098f0f4afd5c3434555f8510093b1ac91932b36a48ab42bd7e8d3fd2c4fe04af'
CONTEXT_KEY_PATHS = ('evas/tests', 'evas/validation', 'evas/examples', 'experiments', 'evas/src', 'evas/rust_core',
                     'evas/capabilities/data/language-profile.json') + COLLECTOR4


def inside_r3(path):
    resolved = Path(path).resolve()
    assert resolved.is_relative_to(R2.resolve()) or resolved.is_relative_to(C0R3.resolve()), resolved
    return resolved


def write_r3(path, value):
    inside_r3(Path(path).parent)
    return write_new(path, value)


def commit_paths_r3(repo, parent, paths, message, parents, index_name):
    """commit_paths_r2 with a round-3 index name (r2/indexes/r3-<name>.index)."""
    return commit_paths_r2(repo, parent, paths, message, parents, 'r3-' + index_name)


def gh_save(api_path, target):
    """One read-only gh api GET into a new file under flow/r2 (stderr next to it); returns the parsed JSON."""
    target = Path(target)
    inside_r3(target.parent)
    with target.open('xb') as stream, Path(str(target) + '.stderr').open('xb') as err:
        r = subprocess.run(['gh', 'api', api_path], env=clean_env(), stdout=stream, stderr=err)
    assert r.returncode == 0, (api_path, Path(str(target) + '.stderr').read_text()[-400:])
    return load(target)


def kernel_slot(label):
    """Simulation slot rule: count evas-kernel processes machine-wide and log the count (round-3 log, appended)."""
    r = subprocess.run(['/bin/ps', '-Ao', 'comm'], capture_output=True, env=clean_env())
    count = sum(1 for line in r.stdout.decode(errors='replace').splitlines() if line.strip().rsplit('/', 1)[-1] == 'evas-kernel')
    with (R2 / 'logs/kernel-slot-r3.log').open('a') as log:
        log.write('kernel procs: %d at %s (%s)\n' % (count, utc(), label))
    return count

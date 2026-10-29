"""Round 3 (main b4a07295 = #294 squash on 6fed3c82): base checks and the push-CI gate, before any C0 stage.

Main session instruction of 2026-10-29: rebuild C0 on b4a07295; first re-check `git diff --name-only 6fed3c82 b4a07295`
and record it; wait for push CI 40864041959, read every job's conclusion, and only when all are success use its
catalog-inventory as OBSERVED; if any job is not success, stop and report.
Read only: the diff and the commit object come from the shared store (rgit), main's tip from gh api, the CI conclusions
from r2/runs/main-push-40864041959-catalog/fetch-receipt.json (fetch_main_push_r3.py) and the saved selection-job log.
Writes c0-r3/base-checks.json (new) and r2/gh/main-branch-r5.json. Exit 3 when the CI gate fails: no C0 stage runs then.
Usage: python3 -B check_base_r3.py
"""
import subprocess

from common_r2 import *

C0R3 = FLOW / 'c0-r3'
BASE = 'b4a072959d55fa3b23e34dfcadd92103ec89f2a3'
BASE_TREE = 'fa40153a848827cdac08f71147dda24fc1d30b6d'
PREVIOUS = NEW_MAIN
RUN = 40864041959
CI = R2 / 'runs/main-push-40864041959-catalog/fetch-receipt.json'
SELECTION_LOG = R2 / 'gh/selection-job-40864041959-r1.log'
ARTIFACTS = R2 / 'gh/run-40864041959-artifacts-r1.json'
STANDIN_R2 = R2 / 'runs/main-push-40857285671-catalog/python-regression-timings/python-regression.json'
# Paths that C0 binds or regenerates; none may change between 6fed3c82 and the new base.
BOUND = COLLECTOR4 + ('scripts/regression_context_registration.py', 'scripts/regression_gate.py',
                      'scripts/materialize_registration_bundle.py', BASELINE_PATH, REVIEW_PATH, POINTER_PATH)


def write_r3(path, value):
    assert Path(path).resolve().parent.is_relative_to(C0R3.resolve()), path
    return write_new(path, value)


def strings_with_prefix(value, prefix):
    found, stack = 0, [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
        elif isinstance(item, str) and item.startswith(prefix):
            found += 1
    return found


def main():
    out = C0R3 / 'base-checks.json'
    assert not out.exists()
    started = utc()
    exact = rgit('diff', '--name-only', PREVIOUS, BASE)
    raw = rgit('diff', '--name-only', '--no-renames', PREVIOUS, BASE)
    names = sorted(set(raw.decode().splitlines()) | set(exact.decode().splitlines()))
    other = [n for n in names if not n.startswith('benchmark/')]
    commit = rgit('cat-file', '-p', BASE).decode().split('\n\n', 1)[0].splitlines()
    tree = [line.split()[1] for line in commit if line.startswith('tree ')]
    parents = [line.split()[1] for line in commit if line.startswith('parent ')]
    tip_path = R2 / 'gh/main-branch-r5.json'
    with tip_path.open('xb') as stream, (R2 / 'gh/main-branch-r5.json.stderr').open('xb') as err:
        r = subprocess.run(['gh', 'api', 'repos/%s/branches/main' % REPO], env=clean_env(), stdout=stream, stderr=err)
    assert r.returncode == 0
    tip = load(tip_path)['commit']['sha']
    tip_at = utc()
    ci = load(CI)
    log = SELECTION_LOG.read_text(errors='replace').splitlines()
    selection = [line.split('Z ', 1)[1] for line in log if 'Selected:' in line or 'Changed paths:' in line]
    artifacts = [a['name'] for a in load(ARTIFACTS)['artifacts']]
    gate_ok = ci['all_green'] and not ci['jobs_not_success']
    base_ok = not other and tree == [BASE_TREE] and parents == [PREVIOUS] and not set(BOUND) & set(names)
    write_r3(out, {
        'round': 3, 'base': BASE, 'base_tree': BASE_TREE, 'previous_main': PREVIOUS, 'started_at_utc': started,
        'diff': {'command': '/usr/bin/git --no-lazy-fetch diff --name-only %s %s (shared store, read only)' % (PREVIOUS, BASE),
                 'exact_command_paths': len(exact.decode().splitlines()), 'exact_listing_sha256': sha(exact),
                 'no_renames_paths': len(raw.decode().splitlines()), 'no_renames_listing_sha256': sha(raw),
                 'paths': len(names), 'all_under_benchmark': not other, 'not_under_benchmark': other,
                 'bound_paths_changed': sorted(set(BOUND) & set(names)), 'bound_paths_checked': list(BOUND),
                 'same_as_earlier_listing': exact == (R2 / 'gh/diff-6fed3c82-b4a07295.txt').read_bytes()},
        'commit_object': {'tree': tree, 'parents': parents, 'tree_matches': tree == [BASE_TREE], 'single_parent_previous_main': parents == [PREVIOUS]},
        'main_tip': {'record': str(tip_path), 'sha': tip, 'at_utc': tip_at, 'equals_base': tip == BASE},
        'ci_gate': {'run': RUN, 'receipt': str(CI), 'receipt_sha256': sha_file(CI)[0], 'status': ci['status'], 'conclusion': ci['conclusion'],
                    'head_sha': ci['head_sha'], 'jobs': ci['jobs'], 'jobs_not_success': ci['jobs_not_success'], 'all_jobs_success': gate_ok,
                    'selection_job_log': str(SELECTION_LOG), 'selection_job_log_sha256': sha_file(SELECTION_LOG)[0], 'selection_lines': selection,
                    'artifacts': artifacts},
        'supporting_fact': {'round2_standin': str(STANDIN_R2), 'strings_starting_benchmark/': strings_with_prefix(load(STANDIN_R2), 'benchmark/')},
        'base_ok': base_ok, 'stop': not (gate_ok and base_ok),
        'stop_reason': None if gate_ok and base_ok else
                       ('push CI %d: %d job(s) not success (%s); the instruction says stop and report' %
                        (RUN, len(ci['jobs_not_success']), ', '.join('%s=%s' % kv for kv in ci['jobs_not_success'].items()))
                        if not gate_ok else 'base check failed'),
        'stages_run': [], 'finished_at_utc': utc()})
    print(json.dumps({'paths': len(names), 'all_under_benchmark': not other, 'tree_ok': tree == [BASE_TREE], 'parents': parents,
                      'tip': tip, 'all_jobs_success': gate_ok, 'not_success': len(ci['jobs_not_success']), 'selection': selection,
                      'artifacts': artifacts}), flush=True)
    return 0 if gate_ok and base_ok else 3


if __name__ == '__main__':
    raise SystemExit(main())

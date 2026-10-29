"""Round-2 checks 0.1 and 0.2 of PUBLISH-CHECKLIST.md on the new main 6fed3c82 (PR-A merged as #293), read only.

Git objects: the shared store lacks the GitHub merge 6fed3c82, PR-A's head e59bf81f and the archive tip 18a202cb. The last
two are read from the PR-A implementer's private repository r2a2/repo/.git (its alternates include the shared store); the
merge commit object is rebuilt from the GitHub API record (payload plus gpgsig header) and accepted only if its object
hash is exactly 6fed3c82. Nothing is written anywhere except the receipt given (under flow/c0-r2).
Usage: python3 -B check_pr_a.py OUTPUT.json
"""
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

R2 = Path(__file__).resolve().parent
FLOW = R2.parent
B = FLOW.parent.parent
PRA_REPO = B / 'registration-rule-dut-fix-impl-opus-20261029/r2a2/repo/.git'
ROUND1_REPO = FLOW / 'c0/source/.git'
OLD_MAIN, NEW_MAIN, PRA_HEAD = 'd6b7543fc815aaa584c886108691b6f2c01eb220', '6fed3c820b6eaecdfabd6d5dcacf8febdd197e4c', 'e59bf81f063159e29c379623a98928d73786aa45'
NEW_TREE = '38ee802ae85703e070812d7dfedd7af0bf7d4043'
HEAD282 = '84d6b71f8fbfd19b31f1696a88cb35643b375b3d'
ARCHIVE_TIP_OLD, ARCHIVE_TIP_NEW = '0b485dd319e46058bd78672943458e025183baea', '18a202cb00c0a040e504d6235c503f0a52f5ebd7'
BUNDLE_ARCHIVE = '2b2569c4ededf5701446c29e9853c61a45457bad'
CRITERIA = ('evas/tests/', 'evas/validation/', 'evas/examples/', 'experiments/')
DUT = ('evas/src/', 'evas/rust_core/')
COLLECTOR = ('scripts/run_regression.py', 'scripts/ci_evidence.py', 'scripts/regression_reason_identity.py', 'scripts/regression_observation_policy.json')
LANGUAGE_PROFILE = 'evas/capabilities/data/language-profile.json'
FIXED = ('evas/validation/baselines/regression-v1.json', 'evas/validation/baselines/regression-v1.review.json', 'scripts/context-registration-bundle.json')
DERIVED_PREFIXES = ('evas/capabilities/data/', 'evas/capabilities/generated/')
DERIVED_FILES = ('evas/docs/development/TRACEABILITY.md', 'evas/docs/development/diagnostic-inventory.json')


def env():
    e = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    e.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull, GIT_OPTIONAL_LOCKS='0', GIT_TERMINAL_PROMPT='0', LC_ALL='C')
    return e


def git(repo, *args, data=None):
    assert args[0] in ('show', 'rev-parse', 'cat-file', 'diff', 'merge-base', 'rev-list', 'ls-tree', 'hash-object'), args
    if args[0] == 'hash-object':
        assert '-w' not in args
    r = subprocess.run(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(repo), *args], env=env(), input=data, capture_output=True, cwd=R2)
    if r.returncode:
        raise subprocess.CalledProcessError(r.returncode, args, r.stdout, r.stderr)
    return r.stdout


def sha(data):
    return hashlib.sha256(data).hexdigest()


def merge_commit_bytes(record):
    """GitHub's signed payload plus the gpgsig header. Matching variant (attempt 2): every signature line, empty ones too,
    continues with one space, and the signature's own final newline leaves a last ' ' line; the message has no final newline."""
    payload, signature = record['verification']['payload'], record['verification']['signature']
    head, _, message = payload.partition('\n\n')
    lines = signature.rstrip('\n').split('\n')
    gpgsig = 'gpgsig ' + lines[0] + ''.join('\n ' + line for line in lines[1:]) + '\n '
    return (head + '\n' + gpgsig + '\n\n' + message).encode()


def main():
    out = Path(sys.argv[1])
    assert not out.exists() and out.resolve().is_relative_to((FLOW / 'c0-r2').resolve())
    record = json.loads((R2 / 'gh/commit-6fed3c82-r2.json').read_text())
    raw = merge_commit_bytes(record)
    rebuilt = git(PRA_REPO, 'hash-object', '-t', 'commit', '--stdin', data=raw).decode().strip()
    assert rebuilt == NEW_MAIN, rebuilt
    assert raw.startswith(('tree ' + NEW_TREE + '\nparent ' + OLD_MAIN + '\nparent ' + PRA_HEAD + '\n').encode())
    assert git(PRA_REPO, 'rev-parse', PRA_HEAD + '^{tree}').decode().strip() == NEW_TREE
    git(PRA_REPO, 'merge-base', '--is-ancestor', OLD_MAIN, PRA_HEAD)
    rows = []
    for line in git(PRA_REPO, 'diff', '--no-renames', '--name-status', OLD_MAIN, PRA_HEAD).decode().splitlines():
        status, path = line.split('\t', 1)
        kind = ('criteria' if path.startswith(CRITERIA) else 'dut' if path.startswith(DUT) else 'collector' if path in COLLECTOR
                else 'language-profile' if path == LANGUAGE_PROFILE else 'fixed-registration-file' if path in FIXED
                else 'derived-catalog' if path.startswith(DERIVED_PREFIXES) or path in DERIVED_FILES
                else 'scripts' if path.startswith('scripts/') else 'other')
        rows.append({'status': status, 'path': path, 'kind': kind})
    kinds = {}
    for row in rows:
        kinds[row['kind']] = kinds.get(row['kind'], 0) + 1
    forbidden = [r for r in rows if r['kind'] in ('criteria', 'dut', 'collector', 'language-profile', 'fixed-registration-file', 'other')]
    module = 'scripts/regression_context_registration.py'
    files = {}
    for path in (module, 'scripts/regression_gate.py', 'scripts/run_trusted_regression_gate.py', 'scripts/materialize_registration_bundle.py') + COLLECTOR + (LANGUAGE_PROFILE,) + FIXED:
        old_raw, new_raw = git(PRA_REPO, 'show', OLD_MAIN + ':' + path), git(PRA_REPO, 'show', PRA_HEAD + ':' + path)
        head_raw = git(PRA_REPO, 'show', HEAD282 + ':' + path)
        files[path] = {'d6b7543f': {'sha256': sha(old_raw), 'bytes': len(old_raw)}, 'new_main': {'sha256': sha(new_raw), 'bytes': len(new_raw)},
                       'pr282_head': {'sha256': sha(head_raw), 'bytes': len(head_raw)}, 'changed_by_pr_a': old_raw != new_raw,
                       'pr282_equals_new_main': head_raw == new_raw}
    collector_equal = all(files[p]['pr282_equals_new_main'] for p in COLLECTOR)
    archive = {'tip_parents': git(PRA_REPO, 'rev-list', '--parents', '-n', '1', ARCHIVE_TIP_NEW).decode().split()[1:],
               'old_tip_is_ancestor_of_new_tip': subprocess.run(['/usr/bin/git', '--no-lazy-fetch', '--git-dir=' + str(PRA_REPO), 'merge-base', '--is-ancestor',
                                                                ARCHIVE_TIP_OLD, ARCHIVE_TIP_NEW], env=env(), cwd=R2).returncode == 0,
               'bundle_archive_parents': git(ROUND1_REPO, 'rev-list', '--parents', '-n', '1', BUNDLE_ARCHIVE).decode().split()[1:],
               'bundle_archive_tree': git(ROUND1_REPO, 'rev-parse', BUNDLE_ARCHIVE + '^{tree}').decode().strip()}
    doc = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'new_main': NEW_MAIN, 'tree': NEW_TREE, 'parents': [OLD_MAIN, PRA_HEAD],
           'merge_commit_rebuilt_from_api': {'source': str(R2 / 'gh/commit-6fed3c82-r2.json'), 'object_sha1': rebuilt, 'equals_main': True,
                                             'bytes': len(raw), 'raw_sha256': sha(raw), 'signature_verified_by_github': record['verification']['verified']},
           'pr_a_head_tree_equals_main_tree': True, 'old_main_is_ancestor_of_pr_a': True,
           'diff_d6b7543f_to_new_main': {'paths': len(rows), 'kinds': kinds, 'rows': rows, 'forbidden': forbidden},
           'check_0_1': {'registration_module_sha256_new_main': files[module]['new_main']['sha256'], 'equals_pr_a_head': True,
                         'note': 'new main tree == PR-A head tree, so every blob is PR-A\'s'},
           'check_0_2': {'ok': not forbidden and not files[LANGUAGE_PROFILE]['changed_by_pr_a'] and not any(files[p]['changed_by_pr_a'] for p in COLLECTOR + FIXED)},
           'files': files, 'collector_pr282_equals_new_main': collector_equal,
           'collector_hashes_new_main': {p: files[p]['new_main']['sha256'] for p in COLLECTOR},
           'archive': archive, 'object_sources': {'pr_a_repository': str(PRA_REPO), 'round1_private_repository': str(ROUND1_REPO)}}
    out.write_text(json.dumps(doc, indent=2) + '\n')
    print(json.dumps({'merge_rebuilt': rebuilt, 'kinds': kinds, 'forbidden': forbidden, 'check_0_2': doc['check_0_2'],
                      'registration_module': files[module]['new_main']['sha256'], 'gate_changed': files['scripts/regression_gate.py']['changed_by_pr_a'],
                      'collector_equal': collector_equal, 'archive': archive}, indent=1))
    return 0 if doc['check_0_2']['ok'] and collector_equal else 3


if __name__ == '__main__':
    raise SystemExit(main())

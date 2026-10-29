"""Baseline-PR byte check for the #282 registration: parse both files and prove a pure one-context append.

Checks (the coordinator's baseline-PR definition used for PR6, here for the sixth context):
  1. only evas/validation/baselines/regression-v1.json changes between the trusted base and the head commit;
  2. the five old contexts are canonically equal to the trusted file, in order, and the top level is unchanged;
  3. the sixth context equals the authorized entry: its canonical SHA-256 is the authorization's
     new_entry_canonical_sha256 in the trusted-base review record (and the governance draft entry when given);
  4. writing the trusted contexts plus the entry, rewriting the head file, and repeating the write all give the head
     bytes (baseline_layout.line_per_context, the PR6 module unchanged).
The canonical digest is regression_context_registration.digest of the trusted base. Read only: Git objects through the
private repository given (or the shared store), files given by path. Writes one new JSON receipt.
Usage: python3 -B check_baseline.py --repo PRIVATE_REPO --base COMMIT --head COMMIT --authorization-id ID --output NEW.json
                                     [--entry entry.json]
"""
import argparse

from common import *

LAYOUT_SHA = '418aa2c99c757f96ad427d0d60bf5cc7bd856a7e6db317b07dc5cf996e35e5ee'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--base', required=True)
    parser.add_argument('--head', required=True)
    parser.add_argument('--authorization-id', required=True)
    parser.add_argument('--entry', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    run = (lambda *a: pgit(args.repo, *a))
    layout_path = F / 'baseline_layout.py'
    assert sha_file(layout_path)[0] == LAYOUT_SHA, 'baseline_layout.py differs from the PR6 module'
    lay = module('check_baseline_layout', layout_path)
    registration_raw = run('show', args.base + ':scripts/regression_context_registration.py')
    code_dir = F / 'code' / ('check-' + args.base[:8])
    code_dir.mkdir(parents=True, exist_ok=True)
    if not (code_dir / 'regression_context_registration.py').exists():
        (code_dir / 'regression_context_registration.py').write_bytes(registration_raw)
    assert (code_dir / 'regression_context_registration.py').read_bytes() == registration_raw
    reg = module('check_baseline_registration', code_dir / 'regression_context_registration.py')
    paths = run('diff', '--no-renames', '--name-only', args.base, args.head).decode().splitlines()
    trusted_raw = run('show', args.base + ':' + BASELINE_PATH)
    head_raw = run('show', args.head + ':' + BASELINE_PATH)
    review = json.loads(run('show', args.base + ':' + REVIEW_PATH))
    auths = [a for a in review.get(reg.GOVERNANCE, []) if isinstance(a, dict) and a.get('id') == args.authorization_id]
    assert len(auths) == 1, 'expected one authorization with this id in the trusted-base review record'
    auth = auths[0]
    trusted, head = json.loads(trusted_raw), json.loads(head_raw)
    n = len(trusted['contexts'])
    entry = head['contexts'][-1] if len(head['contexts']) == n + 1 else None
    entry_file = load(args.entry) if args.entry else None
    checks = lay.append_checks(trusted_raw, head_raw, entry if entry is not None else {}, reg.digest)
    coordinator = {
        '1_one_path': paths == [BASELINE_PATH],
        '2_old_contexts_canonically_equal_in_order': checks['old_contexts_equal_in_order'] and checks['top_level_fields_unchanged'],
        '3_new_context_equals_authorized_entry': (entry is not None and checks['exactly_one_context_appended']
                                                  and reg.digest(entry) == auth['new_entry_canonical_sha256']
                                                  and (entry_file is None or reg.digest(entry_file) == reg.digest(entry))
                                                  and reg.digest(trusted) == auth['old_baseline_canonical_sha256']),
        '4_two_write_paths_and_repeat_byte_identical': checks['write_from_trusted_plus_entry_equals_head_bytes']
                                                        and checks['rewrite_of_head_equals_head_bytes'] and checks['repeated_write_identical'],
    }
    doc = {'checked_at_utc': utc(), 'repo': str(args.repo), 'base': args.base, 'head': args.head, 'paths': paths,
           'trusted': {'bytes': len(trusted_raw), 'sha256': sha(trusted_raw), 'contexts': n, 'canonical_sha256': reg.digest(trusted)},
           'head_file': {'bytes': len(head_raw), 'sha256': sha(head_raw), 'contexts': len(head['contexts']),
                         'below_50MiB_warning': len(head_raw) < 50 * 1024 * 1024, 'below_100MiB_limit': len(head_raw) < 100 * 1024 * 1024},
           'authorization': {'id': args.authorization_id, 'old_baseline_canonical_sha256': auth['old_baseline_canonical_sha256'],
                             'new_entry_canonical_sha256': auth['new_entry_canonical_sha256']},
           'new_context_canonical_sha256': reg.digest(entry) if entry is not None else None,
           'layout_module': {'path': str(layout_path), 'sha256': LAYOUT_SHA, 'equals_pr6': True},
           'registration_code_sha256': sha(registration_raw), 'layout_checks': checks, 'coordinator_checks': coordinator,
           'all_pass': all(coordinator.values()) and all(checks.values())}
    write_new(args.output, doc)
    print(json.dumps({'all_pass': doc['all_pass'], 'coordinator_checks': coordinator}), flush=True)
    return 0 if doc['all_pass'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

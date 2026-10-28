"""Fail unless a run_explicit_checks receipt shows every named check executed exactly once and passed.

A separate CI step after scripts/run_explicit_checks.py. It reads only the JSON receipt, so a
runner that ended without writing one, or wrote an incomplete one, still fails the job:

    python3 -B scripts/verify_explicit_checks.py --report runs/explicit-checks.json \
        --check <module>.<Class>.check_<name> --require-file-env EVAS_TEST_KERNEL

The receipt must come from the runner (schema 1), report success with nothing refused, and list
exactly the named checks, each with executed 1, outcome ok and a module SHA-256. Each
--require-file-env variable must be recorded with the SHA-256 of the file it names (the kernel),
and every check row must carry that same digest.
"""
import argparse
import json
from pathlib import Path
import re
import sys

DIGEST = re.compile(r'[0-9a-f]{64}')


def problems(receipt, checks, files):
    if not isinstance(receipt, dict):
        return ['receipt is not a JSON object']
    found = []
    if receipt.get('schema_version') != 1 or receipt.get('producer') != 'scripts/run_explicit_checks.py':
        found.append('receipt is not a schema 1 receipt of scripts/run_explicit_checks.py')
    if receipt.get('success') is not True:
        found.append('runner did not report success')
    if receipt.get('refused') != []:
        found.append(f"runner refused: {receipt.get('refused')}")
    rows = receipt.get('checks')
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return found + ['receipt has no list of check rows']
    ids = [row.get('id') for row in rows]
    if sorted(ids) != sorted(set(checks)) or len(ids) != len(set(ids)):
        found.append(f'checks in receipt {ids} differ from the named checks {list(checks)}')
    environment = receipt.get('environment_files')
    digests = {}
    for name in files:
        item = environment.get(name) if isinstance(environment, dict) else None
        digest = item.get('sha256') if isinstance(item, dict) else None
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            found.append(f'no SHA-256 recorded for the file named by {name}')
        digests[name] = digest
    for row in rows:
        label = row.get('id')
        if type(row.get('executed')) is not int or row.get('executed') != 1:
            found.append(f"{label}: executed {row.get('executed')!r}, expected exactly 1")
        if row.get('outcome') != 'ok':
            found.append(f"{label}: outcome {row.get('outcome')!r}, expected 'ok'")
        if not isinstance(row.get('module_sha256'), str) or not DIGEST.fullmatch(row['module_sha256']):
            found.append(f'{label}: no module SHA-256')
        row_digests = row.get('environment_sha256')
        for name in files:
            if not isinstance(row_digests, dict) or row_digests.get(name) != digests[name]:
                found.append(f'{label}: {name} SHA-256 differs from the receipt or is missing')
    return found


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--report', required=True, type=Path)
    parser.add_argument('--check', action='append', required=True)
    parser.add_argument('--require-file-env', action='append', default=[])
    args = parser.parse_args(argv)
    try:
        receipt = json.loads(args.report.read_text())
    except (OSError, ValueError) as error:
        print(f'explicit check receipt {args.report} missing or unreadable: {error}', flush=True)
        return 1
    found = problems(receipt, args.check, args.require_file_env)
    rows = {row.get('id'): row for row in receipt.get('checks', []) if isinstance(row, dict)} if isinstance(receipt, dict) else {}
    for check in args.check:
        row = rows.get(check, {})
        status = 'verified' if not found else 'NOT verified'
        print(f"{status} explicit check {check}: executed {row.get('executed')} "
              f"{'time' if row.get('executed') == 1 else 'times'}, outcome {row.get('outcome')}", flush=True)
    for problem in found:
        print('problem: ' + problem, flush=True)
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main())

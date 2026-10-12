"""Select CI work from Git changes; fail closed when change identity is unavailable."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PREFIXES = (
    'benchmark/', 'experiments/va_screen/', 'experiments/benchmark_first_batch/',
    'experiments/benchmark_v2/', 'experiments/benchmark_next/',
)
TASK_PREFIXES = (
    'benchmark/tasks/', 'benchmark/first_batch/',
    'experiments/benchmark_first_batch/', 'experiments/benchmark_v2/',
    'experiments/benchmark_next/',
)
CI_FILES = {'scripts/ci_selection.py', 'scripts/tests/test_ci_selection.py'}
PACKAGE_FILES = {
    'evas/setup.py', 'evas/pyproject.toml', 'evas/MANIFEST.in',
    'evas/rust_core/Cargo.toml', 'evas/rust_core/Cargo.lock',
    'evas/rust_core/fuzz/seeds/static.json', 'scripts/check_installed_evas.py',
    'scripts/tests/test_installed_evas_package.py',
}
PACKAGE_PREFIXES = (
    'evas/src/', 'evas/rust_core/src/', 'evas/rust_core/ir/',
    'evas/rust_core/benches/',
)
LANES = {
    'numerical': ('full', ('regression', 'properties-and-ngspice', 'fuzz-smoke')),
    'package': ('package', ('install',)),
    'benchmark': ('benchmark', ('identity', 'first-batch')),
}


def flags(full=False, package=False, benchmark=False):
    return {'full': full, 'package': package, 'benchmark': benchmark}


def classify(paths):
    selected = flags()
    for path in paths:
        if path.startswith('.github/') or path in CI_FILES:
            return flags(True, True, True)
        # Task instructions are test inputs, even when written in Markdown.
        if path.startswith(TASK_PREFIXES):
            selected['benchmark'] = True
            continue
        if Path(path).suffix.lower() in ('.md', '.rst'):
            continue
        if path.startswith(BENCHMARK_PREFIXES) or path == 'scripts/benchmark_workbench.py':
            selected['benchmark'] = True
            continue
        if path.startswith(('evas/', 'experiments/', 'scripts/')):
            selected['full'] = True
            if path in PACKAGE_FILES or path.startswith(PACKAGE_PREFIXES):
                selected['package'] = True
            if path.startswith('evas/rust_core/') and not path.startswith(
                ('evas/rust_core/tests/', 'evas/rust_core/fuzz/', 'evas/rust_core/examples/')
            ):
                selected['package'] = True
            # An unfamiliar EVAS build input must not bypass installation.
            if path.startswith('evas/') and not path.startswith(
                ('evas/docs/', 'evas/tests/', 'evas/validation/', 'evas/rust_core/')
            ):
                selected['package'] = True
            continue
        # Unknown non-documentation paths may introduce a shared dependency.
        return flags(True, True, True)
    return selected


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.PIPE)


def commit(repo, sha):
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{40,64}', sha) or not int(sha, 16):
        raise ValueError('missing or invalid commit identity')
    return git(repo, 'rev-parse', '--verify', sha + '^{commit}').decode().strip()


def select(repo, event_name, event):
    plan = {**flags(True, True, True), 'base': '', 'head': '', 'paths': []}
    if event_name == 'workflow_dispatch':
        return {**plan, 'reason': 'manual full check'}
    try:
        if event_name == 'pull_request':
            base = commit(repo, event['pull_request']['base']['sha'])
            head = commit(repo, event['pull_request']['head']['sha'])
            base = git(repo, 'merge-base', base, head).decode().strip()
        elif event_name == 'push':
            base = commit(repo, event['before'])
            head = commit(repo, event['after'])
        else:
            raise ValueError('unsupported event')
        # Disable rename detection so both the removed and added paths are checked.
        raw = git(repo, 'diff', '--name-only', '--no-renames', '-z', base, head, '--')
        paths = [os.fsdecode(path) for path in raw.split(b'\0') if path]
        return {**classify(paths), 'base': base, 'head': head, 'paths': paths,
                'reason': 'classified complete Git diff'}
    except (KeyError, TypeError, ValueError, subprocess.CalledProcessError) as error:
        return {**plan, 'reason': f'full check: change identity unavailable ({error})'}


def gate_errors(lane, needs):
    flag, jobs = LANES[lane]
    errors = []
    required = ['selection']
    if lane == 'numerical':
        required.append('static-checks')
    value = needs.get('selection', {}).get('outputs', {}).get(flag)
    if value not in ('true', 'false'):
        errors.append(f'invalid selection output: {flag}={value!r}')
    if value == 'true':
        required.extend(jobs)
    for job in required:
        result = needs.get(job, {}).get('result')
        if result != 'success':
            errors.append(f'{job}: expected success, got {result!r}')
    # Never ignore a failed job, even if the selector did not require it.
    for job in jobs:
        result = needs.get(job, {}).get('result')
        if result not in ('success', 'skipped') and job not in required:
            errors.append(f'{job}: unexpected result {result!r}')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    selection = commands.add_parser('select')
    selection.add_argument('--repo', type=Path, default=ROOT)
    selection.add_argument('--event-name', default=os.environ.get('GITHUB_EVENT_NAME'))
    selection.add_argument('--event-path', type=Path,
                           default=os.environ.get('GITHUB_EVENT_PATH'))
    selection.add_argument('--output', type=Path, default=os.environ.get('GITHUB_OUTPUT'))
    gate = commands.add_parser('gate')
    gate.add_argument('--lane', choices=LANES, required=True)
    args = parser.parse_args()
    if args.command == 'gate':
        needs = json.loads(os.environ['CI_NEEDS'])
        errors = gate_errors(args.lane, needs)
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0
    try:
        event = json.loads(args.event_path.read_text()) if args.event_path else {}
    except (OSError, ValueError):
        event = {}
    plan = select(args.repo, args.event_name, event)
    if args.output:
        with args.output.open('a') as output:
            for key in (*flags(), 'base', 'head'):
                value = str(plan[key]).lower() if key in flags() else plan[key]
                output.write(f'{key}={value}\n')
    print(json.dumps(plan, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())

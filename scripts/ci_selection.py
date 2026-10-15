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
    'experiments/benchmark_paths.py', 'experiments/test_benchmark_paths.py',
)
BENCHMARK_FILES = {
    'scripts/benchmark_workbench.py', 'scripts/benchmark_package.py',
    'scripts/tests/test_benchmark_workbench.py', 'scripts/tests/test_benchmark_package.py',
}
CI_FILES = {'scripts/ci_selection.py', 'scripts/tests/test_ci_selection.py'}
CHECKS = ('maintenance', 'calibration', 'provenance', 'regression',
          'differential', 'fuzz', 'package', 'benchmark')
JOB_FLAGS = {
    'static-checks': ('maintenance', 'calibration', 'provenance'),
    'regression': ('regression',),
    'properties-and-ngspice': ('differential',),
    'fuzz-smoke': ('fuzz',),
    'package': ('package',),
    'benchmark': ('benchmark',),
}
CHILD_RESULTS = {'package': ('install_result',),
                 'benchmark': ('identity_result', 'first_batch_result')}
MAINTENANCE_FILES = {
    'scripts/traceability.py', 'scripts/diagnostic_inventory.py',
    'scripts/verify_validation_version.py', 'scripts/check_workspaces.py',
    'scripts/tests/test_traceability.py',
    'scripts/tests/test_diagnostic_inventory.py', 'scripts/tests/test_workspaces.py',
}
PACKAGE_FILES = {'scripts/check_installed_evas.py',
                 'scripts/tests/test_installed_evas_package.py'}
PROVENANCE_PREFIXES = ('evas/validation/paper/', 'evas/validation/support/',
                       'experiments/backends/paper/', 'experiments/backends/support/')
CALIBRATION_PREFIXES = (
    'experiments/backends/evidence/', 'experiments/backends/dvs2-spectre-validation/',
    'experiments/backends/spectre-alignment/', 'experiments/backends/event-alignment/',
    'experiments/backends/sample-edge-filter/', 'experiments/performance/',
)
# These are consumed by development regressions, not only by backend checkers.
REGRESSION_INPUTS = {
    'experiments/backends/paper/inputs.py',
    'experiments/backends/dvs2-spectre-validation/run_suite.py',
    'experiments/backends/dvs2-spectre-validation/check_results.py',
}


def flags(*enabled):
    return {key: key in enabled for key in CHECKS}


def classify(paths):
    selected = set()
    for path in paths:
        suffix = Path(path).suffix.lower()
        if path.startswith('.github/') or path in CI_FILES:
            return flags(*CHECKS)
        # Sources and contract docs also feed generated benchmark views.
        if path.startswith(BENCHMARK_PREFIXES) or path in BENCHMARK_FILES:
            selected.add('benchmark')
        elif suffix in ('.md', '.rst'):
            if path in ('evas/docs/COMPARISON.md', 'evas/docs/COMPARISON-METHODOLOGY.md'):
                selected.add('provenance')
                if path.endswith('METHODOLOGY.md'):
                    selected.add('calibration')
            elif path.startswith(PROVENANCE_PREFIXES):
                selected.add('provenance')
            elif path.startswith(('evas/docs/math/', 'evas/validation/', *CALIBRATION_PREFIXES)):
                selected.add('calibration')
            elif path.startswith('evas/docs/development/'):
                selected.add('maintenance')
        elif path in MAINTENANCE_FILES:
            selected.add('maintenance')
        elif path in PACKAGE_FILES:
            selected.update(('maintenance', 'package'))
        elif path == 'scripts/recompile_evas_manifests.py':
            selected.update(('maintenance', 'regression', 'calibration'))
        elif path.startswith(('evas/src/', 'evas/rust_core/')):
            selected.update(('maintenance', 'calibration', 'provenance', 'regression'))
            if path.startswith('evas/rust_core/fuzz/'):
                selected.add('fuzz')
                if path == 'evas/rust_core/fuzz/seeds/static.json':
                    selected.add('package')
            elif not path.startswith('evas/rust_core/tests/'):
                selected.update(('differential', 'fuzz', 'package'))
        elif path.startswith('evas/tests/'):
            selected.update(('maintenance', 'calibration', 'provenance', 'regression'))
        elif path.startswith('evas/validation/differential/'):
            selected.update(('maintenance', 'calibration', 'differential'))
        elif path.startswith((*PROVENANCE_PREFIXES, *CALIBRATION_PREFIXES)):
            # Backend modules share archive/parser helpers and paper contracts.
            selected.update(('calibration', 'provenance'))
            if path in REGRESSION_INPUTS or suffix not in ('.py', '.csv'):
                selected.update(('maintenance', 'regression'))
        elif path.startswith('evas/validation/'):
            selected.update(('maintenance', 'calibration', 'provenance', 'regression'))
            if path.startswith(('evas/validation/smoke/', 'evas/validation/cases/')):
                selected.add('differential')
        elif path.startswith('evas/docs/'):
            selected.update(('maintenance', 'calibration', 'provenance'))
        elif path.startswith('evas/'):
            # Unfamiliar package/build inputs must not bypass installation.
            selected.update(CHECKS[:-1])
        else:
            # Unknown scripts/experiments may introduce a shared dependency.
            return flags(*CHECKS)
    return flags(*selected)


def git(repo, *args):
    return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.PIPE)


def commit(repo, sha):
    if not isinstance(sha, str) or not re.fullmatch(r'[0-9a-fA-F]{40,64}', sha) or not int(sha, 16):
        raise ValueError('missing or invalid commit identity')
    return git(repo, 'rev-parse', '--verify', sha + '^{commit}').decode().strip()


def select(repo, event_name, event):
    plan = {**flags(*CHECKS), 'base': '', 'head': '', 'paths': []}
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


def gate_errors(needs):
    errors = []
    selection = needs.get('selection', {})
    if selection.get('result') != 'success':
        errors.append('selection did not succeed')
    outputs = selection.get('outputs', {})
    for flag in CHECKS:
        if outputs.get(flag) not in ('true', 'false'):
            errors.append(f'invalid selection output: {flag}={outputs.get(flag)!r}')
    for job, required_flags in JOB_FLAGS.items():
        required = any(outputs.get(flag) == 'true' for flag in required_flags)
        result = needs.get(job, {}).get('result')
        if required and result != 'success':
            errors.append(f'{job}: expected success, got {result!r}')
        elif not required and result not in ('success', 'skipped'):
            errors.append(f'{job}: unexpected result {result!r}')
        # A reusable workflow can be green even if one of its jobs was skipped.
        if required:
            for child in CHILD_RESULTS.get(job, ()):
                value = needs.get(job, {}).get('outputs', {}).get(child)
                if value != 'success':
                    errors.append(f'{job}/{child}: expected success, got {value!r}')
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
    commands.add_parser('gate')
    args = parser.parse_args()
    if args.command == 'gate':
        needs = json.loads(os.environ['CI_NEEDS'])
        errors = gate_errors(needs)
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

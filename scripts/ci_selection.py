"""Select CI work from Git changes; fail closed when change identity is unavailable."""
import argparse
import ast
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
    'scripts/development_records.py', 'scripts/tests/test_development_records.py',
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
    'experiments/backends/sample-edge-filter/', 'experiments/backends/implicit-event-restart/',
    'experiments/performance/',
)
# These are consumed by development regressions, not only by backend checkers.
REGRESSION_INPUTS = {
    'experiments/backends/paper/inputs.py',
    'experiments/backends/dvs2-spectre-validation/run_suite.py',
    'experiments/backends/dvs2-spectre-validation/check_results.py',
}
# Audited historical reports, not fixtures or executable inputs. Keep this an
# exact path list: an unfamiliar JSON file still selects its regression consumers.
HISTORICAL_REPORTS = {
    'experiments/backends/sample-edge-filter/rea-boundary-receipt.json',
}
PROGRESS_START = '<!-- ci:progress:start -->'
PROGRESS_END = '<!-- ci:progress:end -->'


def flags(*enabled):
    return {key: key in enabled for key in CHECKS}


def classify(paths):
    selected = set()
    for path in paths:
        suffix = Path(path).suffix.lower()
        if path == 'scripts/tests/test_ci_selection.py':
            selected.add('maintenance')
            continue
        elif path.startswith('.github/') or path in CI_FILES:
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
        elif (path.startswith('evas/tests/') and suffix == '.py'
              or path.startswith('evas/rust_core/tests/') and suffix == '.rs'):
            # Calibration does not read development tests. Provenance freezes
            # both Python and Rust tests in source-identity manifests.
            selected.update(('maintenance', 'provenance', 'regression'))
        elif path.startswith(('evas/rust_core/src/', 'evas/rust_core/ir/src/')) and suffix == '.rs':
            # Calibration does not read Rust implementation. Provenance does:
            # its producer-identity controls inspect the production source closure.
            selected.update(('maintenance', 'provenance', 'regression',
                             'differential', 'fuzz', 'package'))
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
            if path in REGRESSION_INPUTS or (suffix not in ('.py', '.csv')
                                             and path not in HISTORICAL_REPORTS):
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


def maintenance_registration_only(before, after):
    """Compare executable selector syntax, allowing only audited registrations."""
    trees, registrations = [], []
    for source in (before, after):
        tree = ast.parse(source)
        matches = [node for node in tree.body if isinstance(node, ast.Assign)
                   and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == 'MAINTENANCE_FILES']
        if len(matches) != 1:
            return False
        node = matches[0]
        values = ast.literal_eval(node.value)
        if not isinstance(values, set) or not all(isinstance(p, str) for p in values):
            return False
        registrations.append(values)
        tree.body.remove(node)
        trees.append(ast.dump(tree, include_attributes=False))
    changed = registrations[0] ^ registrations[1]
    # Only paths already audited in this selector can use the exemption.
    # New/unfamiliar registrations retain the full gate until audited here.
    return (trees[0] == trees[1] and bool(changed)
            and changed <= MAINTENANCE_FILES
            and all(re.fullmatch(r'scripts/(?:[a-z_]+|tests/test_[a-z_]+)\.py', p)
                    and p not in CI_FILES | BENCHMARK_FILES | PACKAGE_FILES
                    for p in changed))


def without_progress(source):
    """One explicit prose block; tables, headings and criteria stay outside it."""
    if source.count(PROGRESS_START) != 1 or source.count(PROGRESS_END) != 1:
        return None
    prefix, rest = source.split(PROGRESS_START)
    progress, suffix = rest.split(PROGRESS_END)
    # A block is prose only. Empty blocks, table rows, headings, fences and
    # nested comments cannot become an alternative capability table.
    if (not progress.strip() or any(line.lstrip().startswith(('|', '#', '```', '~~~', '<!--'))
                                    for line in progress.splitlines())):
        return None
    return prefix + PROGRESS_START + PROGRESS_END + suffix


def classify_changes(repo, base, head, paths):
    """Use full blobs for the two narrow exemptions; paths alone fail closed."""
    selected, reasons = set(), []
    for path in paths:
        checks = classify([path])
        reason = 'path contract'
        if path in ('scripts/ci_selection.py', 'evas/docs/COMPARISON.md'):
            try:
                blobs = []
                for revision in (base, head):
                    entry = git(repo, 'ls-tree', '-z', revision, '--', path)
                    if not entry.startswith(b'100644 blob '):
                        raise ValueError('not an existing regular file')
                    blobs.append(git(repo, 'show', f'{revision}:{path}').decode('utf-8'))
                if path == 'scripts/ci_selection.py' and maintenance_registration_only(*blobs):
                    checks, reason = flags('maintenance'), 'audited maintenance registration only'
                elif path == 'evas/docs/COMPARISON.md':
                    protected = [without_progress(blob) for blob in blobs]
                    if protected[0] is not None and protected[0] == protected[1]:
                        checks, reason = flags(), 'explicit progress prose only; protected text unchanged'
            except (ValueError, SyntaxError, TypeError, UnicodeError, subprocess.CalledProcessError):
                reason = 'full path contract: content identity unavailable or unsafe'
        selected.update(key for key in CHECKS if checks[key])
        reasons.append({'path': path, 'checks': [key for key in CHECKS if checks[key]],
                        'reason': reason})
    return flags(*selected), reasons


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
        checks, reasons = classify_changes(repo, base, head, paths)
        return {**checks, 'base': base, 'head': head, 'paths': paths, 'reasons': reasons,
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
    selection.add_argument('--report', type=Path, help='Save the complete plan once as JSON')
    selection.add_argument('--json', action='store_true', help='Print the complete plan as JSON')
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
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(plan, indent=2) + '\n')
    if args.json:
        print(json.dumps(plan, indent=2))
    else:
        print('Selected: ' + (', '.join(key for key in CHECKS if plan[key]) or 'selection/whitespace only'))
        print(plan['reason'])
        print(f"Changed paths: {len(plan['paths'])}; base={plan['base']}; head={plan['head']}")
        print(f'Evidence: {args.report}' if args.report else 'Details: --json or --report <task-path>')
    return 0


if __name__ == '__main__':
    sys.exit(main())

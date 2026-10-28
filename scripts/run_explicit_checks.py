"""Run named explicit check_ methods in CI, each exactly once, and fail closed.

unittest discovery never collects check_ methods: they need something that an
ordinary CI test run does not provide, such as a release kernel. A CI step runs
selected ones by name through this runner, for example

    python3 -B scripts/run_explicit_checks.py --start evas/tests --require-env EVAS_TEST_KERNEL \
        --check test_output_point_limit.LargeGridEndToEnd.check_rc_step_response_over_a_hundred_thousand_rows \
        --report runs/explicit-checks.json

Before anything is imported, every named check must be <module>.<Class>.check_<name>
defined in <start>/<module>.py and listed in the checks of a current case in
evas/capabilities/data/registry.json, and every --require-env variable must be set
and nonempty; otherwise nothing runs and the exit status is 2. Each check then runs
through unittest and must execute exactly once under its own id, without skip,
expected failure or unexpected success, and pass; otherwise the exit status is 1.
The receipt names every check, its outcome and how many times it ran.
scripts/capabilities/collect_ci_inventory.py records each workflow invocation as a
CI by-name check entry and applies the same static rules.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = 'evas/capabilities/data/registry.json'
CHECK_ID = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\.(check_[A-Za-z0-9_]+)')
ENV_NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def literal_path(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts or str(path) != value
            or any(x in value for x in ('$', '`', '\\', '\n', '\x00'))):
        raise ValueError('not a literal repository-relative path: ' + repr(value))
    return value


def locate(root, start, check):
    """(module path, definition line, problem) of one named check, read statically."""
    match = CHECK_ID.fullmatch(check)
    if not match:
        return None, None, f'{check} is not <module>.<Class>.check_<name>'
    module, name, method = match.groups()
    path = str(PurePosixPath(start) / (module + '.py'))
    source = Path(root) / path
    if not source.is_file():
        return path, None, f'{check}: module {path} not found'
    try:
        tree = ast.parse(source.read_bytes())
    except (SyntaxError, ValueError) as error:
        return path, None, f'{check}: module {path} does not parse: {error}'
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method:
                    return path, item.lineno, None
            return path, None, f'{check}: method not found in class {name} (renamed or deleted?)'
    return path, None, f'{check}: class {name} not found in {path}'


def registered(root):
    """{(module, runtime_id): [case@version, ...]} for the checks of every current case."""
    data = json.loads((Path(root) / REGISTRY).read_text(encoding='utf-8'))
    objects = {(obj.get('id'), obj.get('version')): obj for obj in data.get('objects', [])}
    found = {}
    for name, version in data.get('current', {}).items():
        obj = objects.get((name, version))
        if obj is None or obj.get('kind') != 'case' or not isinstance(obj.get('checks'), list):
            continue
        for value in obj['checks']:
            if isinstance(value, dict):
                found.setdefault((value.get('module'), value.get('runtime_id')), []).append(f'{name}@{version}')
    return found


class Recorder(unittest.TextTestResult):
    """Counts every start of every test id and keeps each outcome."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.started, self.outcomes = {}, {}

    def startTest(self, test):
        super().startTest(test)
        self.started[test.id()] = self.started.get(test.id(), 0) + 1

    def _keep(self, test, outcome):
        self.outcomes.setdefault(test.id(), []).append(outcome)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._keep(test, 'ok')

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._keep(test, 'FAIL')

    def addError(self, test, err):
        super().addError(test, err)
        self._keep(test, 'ERROR')

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._keep(test, 'skipped')

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._keep(test, 'expected_failure')

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._keep(test, 'unexpected_success')

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._keep(test, 'FAIL' if issubclass(err[0], test.failureException) else 'ERROR')


def execute(check):
    """Run one check by name; (executed count, outcome, details)."""
    suite = unittest.defaultTestLoader.loadTestsFromName(check)
    runner = unittest.TextTestRunner(stream=sys.stderr, verbosity=2, resultclass=Recorder)
    result = runner.run(suite)
    executed = result.started.get(check, 0)
    outcomes = [x for values in result.outcomes.values() for x in values]
    others = sorted(set(result.started) - {check})
    problems = []
    if executed != 1 or others or result.testsRun != 1:
        problems.append(f'expected exactly one run of {check}; ran {result.testsRun} test(s), '
                        f'{executed} of them this check, others {others}')
    bad = [x for x in outcomes if x != 'ok']
    if bad or result.outcomes.get(check) != ['ok'] or not result.wasSuccessful():
        problems.append('outcomes ' + json.dumps(result.outcomes, sort_keys=True))
    if problems:
        outcome = next((x for x in ('FAIL', 'ERROR', 'skipped', 'expected_failure', 'unexpected_success')
                        if x in outcomes), 'not_run_once')
    else:
        outcome = 'ok'
    return executed, outcome, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--start', required=True, help='test directory placed first on sys.path, as discover -s does')
    parser.add_argument('--check', action='append', required=True, help='<module>.<Class>.check_<name>')
    parser.add_argument('--require-env', action='append', default=[], help='variable that must be set and nonempty')
    parser.add_argument('--report', required=True, help='receipt path, repository-relative')
    args = parser.parse_args(argv)
    try:
        start, report = literal_path(args.start), literal_path(args.report)
    except ValueError as error:
        parser.error(str(error))
    refused, rows = [], []
    for name in args.require_env:
        if not ENV_NAME.fullmatch(name):
            refused.append(f'prerequisite name {name!r} is not an environment variable name')
        elif not os.environ.get(name):
            refused.append(f'prerequisite {name} is not set')
    try:
        known = registered(ROOT)
    except (OSError, ValueError, AttributeError, TypeError) as error:
        known = {}
        refused.append(f'registry {REGISTRY} unreadable: {error}')
    seen = set()
    for check in args.check:
        module, line, problem = locate(ROOT, start, check)
        row = dict(id=check, module=module, line=line, module_sha256=None, registered_by=[],
                   executed=0, outcome='not_run', seconds=None, problems=[])
        if check in seen:
            problem = f'{check} is named more than once'
        seen.add(check)
        if problem is None:
            row['module_sha256'] = hashlib.sha256((ROOT / module).read_bytes()).hexdigest()
            row['registered_by'] = known.get((module, check), [])
            if not row['registered_by']:
                problem = f'{check} is not registered in the checks of a current case ({REGISTRY})'
        if problem is not None:
            refused.append(problem)
            row['problems'].append(problem)
        rows.append(row)
    receipt = dict(schema_version=1, producer='scripts/run_explicit_checks.py', start=start,
                   required_environment={name: os.environ.get(name) for name in args.require_env},
                   python=sys.version, checks=rows, refused=refused, success=False)
    if not refused:
        sys.path.insert(0, str(ROOT / start))
        for row in rows:
            started = time.monotonic()
            row['executed'], row['outcome'], row['problems'] = execute(row['id'])
            row['seconds'] = round(time.monotonic() - started, 3)
        receipt['success'] = all(row['outcome'] == 'ok' and row['executed'] == 1 for row in rows)
    target = Path(report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n')
    for row in rows:
        times = 'time' if row['executed'] == 1 else 'times'
        print(f"explicit check {row['id']}: executed {row['executed']} {times}, outcome {row['outcome']}"
              + (f", {row['seconds']} s" if row['seconds'] is not None else '')
              + (f"; {'; '.join(row['problems'])}" if row['problems'] else ''), flush=True)
    for problem in refused:
        print('refused: ' + problem, flush=True)
    passed = sum(row['outcome'] == 'ok' and row['executed'] == 1 for row in rows)
    print(f'explicit checks: {len(rows)} named, {passed} executed exactly once and passed', flush=True)
    if refused:
        return 2
    return 0 if receipt['success'] else 1


if __name__ == '__main__':
    sys.exit(main())

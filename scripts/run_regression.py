"""Run unittest unchanged, with per-test durations and a flushed progress journal."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import unittest


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


def partition(suite, modules, count, weights, reserved=()):
    groups = {}
    for test in cases(suite):
        name = test.__class__.__module__
        if isinstance(test, unittest.loader._FailedTest):
            name = test._testMethodName
        groups.setdefault(name, []).append(test)
    if modules:
        missing = set(modules) - groups.keys()
        if missing:
            raise ValueError('requested test modules missing: ' + ', '.join(sorted(missing)))
        groups = {name: groups[name] for name in sorted(set(modules))}
    if len(reserved) > count or any(item < 0 for item in reserved):
        raise ValueError('shard reservations must be non-negative and no longer than the shard count')
    shards = [[] for _ in range(count)]
    loads = [float(reserved[index]) if index < len(reserved) else 0.0 for index in range(count)]
    for name in sorted(groups, key=lambda n: (-weights.get(n, len(groups[n])), n)):
        index = min(range(count), key=lambda i: (loads[i], i))
        shards[index].extend(groups[name])
        loads[index] += weights.get(name, len(groups[name]))
    return shards


def merge_reports(paths):
    reports = [json.loads(path.read_text()) for path in paths]
    if not reports:
        raise ValueError('no shard reports')
    first = reports[0]; count = first['shard_count']
    if len(reports) != count or {r['shard_index'] for r in reports} != set(range(count)):
        raise ValueError('missing or duplicate shard reports')
    expected = first['discovered_test_ids']; seen = []
    for report in reports:
        if (report['discovered_test_ids'] != expected or report['assignment'] != first['assignment']
                or report['complete'] is not True or report['successful'] is not True):
            raise ValueError('incomplete, failed or incompatible shard')
        if (any(report.get(k, 0) for k in ('failures', 'errors', 'unexpected_successes'))
                or any(t.get('outcome') not in ('passed', 'skipped', 'expected_failure')
                       for t in report['tests'])):
            raise ValueError('shard contains an unsuccessful test outcome')
        selected = report['selected_test_ids']
        if selected != first['assignment'][report['shard_index']]:
            raise ValueError('shard selected a different test manifest')
        executed = [t['id'] for t in report['tests']]
        skipped = report.get('setup_skipped_test_ids', [])
        if (len(executed + skipped) != len(set(executed + skipped))
                or sorted(executed + skipped) != sorted(selected)
                or report.get('tests_run', len(executed)) != len(executed)):
            raise ValueError('shard did not account for every selected test')
        seen.extend(selected)
    if len(seen) != len(set(seen)) or sorted(seen) != sorted(expected) or not expected:
        raise ValueError('test coverage is empty, overlapping or incomplete')
    total_run = sum(r.get('tests_run', len(r['tests'])) for r in reports)
    if total_run == 0:
        raise ValueError('no tests executed across the complete regression')
    return dict(schema_version=2, complete=True, successful=True,
                tests_run=total_run,
                planned_tests=len(seen),
                setup_skipped_test_ids=[t for r in reports for t in r.get('setup_skipped_test_ids', [])],
                shard_count=count, tests=[t for r in reports for t in r['tests']],
                seconds=sum(r['seconds'] for r in reports),
                timing_scope='sum of shard test durations, not wall time')


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, journal, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal
        self.timings = []
        self.active = None
        self.setup_skips = []

    def emit(self, event, **fields):
        self.journal.write(json.dumps(dict(event=event, **fields)) + "\n")
        self.journal.flush()

    def startTest(self, test):
        self.started = time.perf_counter()
        self.active = dict(id=test.id(), outcome="interrupted")
        self.emit("start", id=test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.active["seconds"] = time.perf_counter() - self.started
        self.timings.append(self.active)
        self.emit("stop", **self.active)
        self.active = None
        super().stopTest(test)

    def outcome(self, value):
        # Class/module setup errors have no individual startTest call. unittest
        # still reports them in errors/skips, so success never depends on rows.
        priority = {"interrupted": 0, "passed": 1, "skipped": 2, "expected_failure": 2,
                    "unexpected_success": 3, "failed": 4, "error": 5}
        if self.active is not None and priority[value] > priority[self.active["outcome"]]:
            self.active["outcome"] = value

    def addSuccess(self, test):
        self.outcome("passed")
        super().addSuccess(test)

    def addFailure(self, test, err):
        self.outcome("failed")
        super().addFailure(test, err)

    def addError(self, test, err):
        self.outcome("error")
        super().addError(test, err)

    def addSkip(self, test, reason):
        if self.active is None:
            scope = test.id()
            for kind in ('setUpClass', 'setUpModule'):
                prefix = kind + ' ('
                if scope.startswith(prefix) and scope.endswith(')'):
                    self.setup_skips.append(dict(prefix=scope[len(prefix):-1] + '.', reason=reason))
        self.outcome("skipped")
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.outcome("expected_failure")
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.outcome("unexpected_success")
        super().addUnexpectedSuccess(test)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            self.outcome("failed" if issubclass(err[0], test.failureException) else "error")
        super().addSubTest(test, subtest, err)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-directory", default="evas/tests")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument('--modules', nargs='+', default=[])
    parser.add_argument('--shard-count', type=int, default=1)
    parser.add_argument('--shard-index', type=int, default=0)
    parser.add_argument('--weights', type=Path)
    parser.add_argument('--merge', type=Path, nargs='+')
    args = parser.parse_args(argv)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    if args.merge:
        try:
            payload = merge_reports(args.merge)
        except (ValueError, KeyError, OSError, TypeError) as error:
            print(error, file=sys.stderr)
            return 1
        args.report.write_text(json.dumps(payload, indent=2) + '\n')
        return 0
    if not 1 <= args.shard_count <= 16 or not 0 <= args.shard_index < args.shard_count:
        parser.error('invalid shard index/count')
    suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern)
    try:
        payload = json.loads(args.weights.read_text()) if args.weights else {}
        weights = payload.get('module_seconds', {})
        reserved = payload.get('shard_reserved_seconds', [])
        if any(not isinstance(v, (int, float)) or not 0 < v < 86400 for v in weights.values()):
            raise ValueError('invalid module duration')
        if (not isinstance(reserved, list) or any(
                not isinstance(item, (int, float)) or item < 0 or item >= 86400 for item in reserved)):
            raise ValueError('invalid shard reservation')
        shards = partition(suite, args.modules, args.shard_count, weights, reserved)
    except (ValueError, KeyError, OSError, TypeError) as error:
        parser.error(str(error))
    assignment = [[test.id() for test in shard] for shard in shards]
    all_ids = sorted(t for shard in assignment for t in shard)
    if len(all_ids) != len(set(all_ids)):
        parser.error('duplicate discovered test identities')
    selected_ids = assignment[args.shard_index]
    suite = unittest.TestSuite(shards[args.shard_index])
    complete = False
    started = time.perf_counter()
    with args.report.with_suffix(".jsonl").open("w") as journal:
        # Keep the result even when an interrupt escapes runner.run(). Each
        # start is flushed before executing the test, including a hung test.
        result = None

        def make_result(*positional, **keywords):
            nonlocal result
            result = TimedResult(*positional, journal=journal, **keywords)
            return result

        try:
            unittest.TextTestRunner(verbosity=2, resultclass=make_result).run(suite)
            complete = True
        except KeyboardInterrupt:
            print("Regression interrupted; partial timings retained.", file=sys.stderr)
        finally:
            if result is not None:
                payload = dict(
                    schema_version=2, complete=complete,
                    successful=complete and bool(all_ids) and result.wasSuccessful()
                    and (result.testsRun > 0 or args.shard_count > 1),
                    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                    unexpected_successes=len(result.unexpectedSuccesses),
                    seconds=time.perf_counter() - started, tests=result.timings,
                    discovered_test_ids=all_ids, selected_test_ids=selected_ids,
                    shard_count=args.shard_count, shard_index=args.shard_index,
                    assignment=assignment,
                    setup_skips=result.setup_skips,
                    setup_skipped_test_ids=[identity for identity in selected_ids
                        if any(identity.startswith(skip['prefix']) for skip in result.setup_skips)],
                )
                args.report.write_text(json.dumps(payload, indent=2) + "\n")
                slowest = sorted(result.timings, key=lambda row: row["seconds"], reverse=True)[:20]
                summary = ["## Python regression", "",
                           f"Tests: {result.testsRun}; complete: {complete}; passed: {payload['successful']}.",
                           "", "| Seconds | Outcome | Test |", "| ---: | --- | --- |"]
                summary.extend(f"| {row['seconds']:.3f} | {row['outcome']} | `{row['id']}` |"
                               for row in slowest)
                print("\n".join(summary), file=sys.stderr)
                if os.environ.get("GITHUB_STEP_SUMMARY"):
                    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as stream:
                        stream.write("\n".join(summary) + "\n")
    return 0 if payload["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

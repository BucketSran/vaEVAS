"""Run unittest unchanged, with per-test durations and a flushed progress journal."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import unittest


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, journal, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal
        self.timings = []
        self.active = None

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
    args = parser.parse_args(argv)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.discover(args.start_directory, pattern=args.pattern)
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
                    schema_version=1, complete=complete,
                    successful=complete and result.testsRun > 0 and result.wasSuccessful(),
                    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                    unexpected_successes=len(result.unexpectedSuccesses),
                    seconds=time.perf_counter() - started, tests=result.timings,
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

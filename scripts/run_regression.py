"""Run unittest unchanged, with per-test durations and a flushed progress journal."""

import argparse
import ast
from functools import lru_cache
import hashlib
import inspect
import json
import os
import platform
from pathlib import Path
import sys
import struct
import traceback
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


def sibling_module(name):
    # The runner is also imported directly by maintenance tests without scripts
    # on sys.path. Load the one maintained validator from its sibling path.
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge_v3(reports):
    gate = sibling_module('regression_gate')
    first = reports[0]
    count = first['shard_count']
    if len(reports) != count or {r['shard_index'] for r in reports} != set(range(count)):
        raise ValueError('missing or duplicate shard reports')
    for report in reports:
        validation = gate.validate_report(report)
        if not validation['valid']:
            raise ValueError('; '.join(validation['errors']))
        for key in ('metadata', 'discovered_test_ids', 'assignment'):
            if report[key] != first[key]:
                raise ValueError('incompatible shard ' + key)
        public_source = lambda r: {k: v for k, v in r['source_identity'].items() if k != 'execution_identity'}
        if public_source(report) != public_source(first):
            raise ValueError('incompatible shard source_identity')
        if report.get('merged'):
            raise ValueError('cannot merge an already merged report')
    reports = sorted(reports, key=lambda r: r['shard_index'])
    payload = dict(first, merged=True, shard_index=None, planned_tests=len(first['discovered_test_ids']),
                   selected_test_ids=first['discovered_test_ids'],
                   successful=all(r['successful'] for r in reports),
                   tests=[t for r in reports for t in r['tests']],
                   fixtures=[t for r in reports for t in r['fixtures']],
                   setup_skipped_test_ids=[t for r in reports for t in r['setup_skipped_test_ids']],
                   setup_skips=[t for r in reports for t in r['setup_skips']],
                   seconds=sum(r['seconds'] for r in reports),
                   timing_scope='sum of shard durations, not wall time',
                   parts=[{key: r[key] for key in ('shard_index', 'complete', 'collection_complete',
                           'selected_test_ids', 'metadata', 'input_identity', 'source_identity')} for r in reports])
    payload['source_identity'] = public_source(first)
    for key in gate.COUNTERS:
        payload[key] = sum(r[key] for r in reports)
    payload.pop('input_identity', None)
    validation = gate.validate_report(payload)
    if not validation['valid']:
        raise ValueError('; '.join(validation['errors']))
    return payload


def file_manifest(root, directories):
    entries = []
    for directory in directories:
        folder = root / directory
        if not folder.exists():
            continue
        for path in sorted(folder.rglob('*')):
            relative = path.relative_to(root)
            if any(part in ('__pycache__', 'target', 'baselines', '.git', 'runs') for part in relative.parts):
                continue
            if path.is_file():
                entries.append([relative.as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()])
    return entries


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def observation_identity(start_directory, source_root, modules, pattern):
    root = source_root.resolve() if source_root else Path(start_directory).resolve().parents[1]
    if (root / 'evas/tests').is_dir():
        criteria = file_manifest(root, ('evas/tests', 'evas/validation', 'evas/examples', 'experiments'))
        dut = file_manifest(root, ('evas/src', 'evas/rust_core'))
    else:
        folder = Path(start_directory).resolve()
        criteria = [[p.relative_to(folder).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest()]
                    for p in sorted(folder.rglob('*.py'))]
        dut = []
    profile = root / 'evas/capabilities/data/language-profile.json'
    if not profile.exists():
        profile = Path(__file__).resolve().parents[1] / 'evas/capabilities/data/language-profile.json'
    policy = sibling_module('ci_evidence')
    metadata = dict(criteria_id=json_digest(criteria), language_profile=hashlib.sha256(profile.read_bytes()).hexdigest(),
                    collector_sha256=json_digest(dict(runner=source_digest(__file__),
                                                       environment_policy=source_digest(policy.__file__))),
                    runtime_profile=dict(python=sys.version, platform=platform.platform(), machine=platform.machine(),
                         variables={key: os.environ.get(key) for key in policy.ENVIRONMENT}),
                    invocation=dict(modules=sorted(set(modules)), pattern=pattern))
    kernel = root / 'evas/rust_core/target/debug/evas-kernel'
    source = dict(criteria_files=criteria, dut_files=dut,
                  kernel_sha256=hashlib.sha256(kernel.read_bytes()).hexdigest() if kernel.exists() else None)
    return metadata, source


def merge_reports(paths):
    reports = [json.loads(path.read_text()) for path in paths]
    if not reports:
        raise ValueError('no shard reports')
    schemas = {r.get('schema_version', 2) for r in reports}
    if schemas == {3}:
        return merge_v3(reports)
    if schemas != {2}:
        raise ValueError('mixed or unsupported report schemas')
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


def parameter_value(value, depth=0):
    """Retain JSON values; opaque parameters remain explicitly unmatchable."""
    if value is None or type(value) in (str, bool, int):
        return value, True
    if type(value) is float:
        return {'float64_bits': struct.pack('!d', value).hex()}, True
    if depth < 12 and type(value) in (list, tuple):
        pairs = [parameter_value(v, depth + 1) for v in value]
        values = [v for v, _ in pairs]
        return ({'tuple': values} if type(value) is tuple else values), all(ok for _, ok in pairs)
    if depth < 12 and type(value) is dict and all(type(k) is str for k in value):
        pairs = {k: parameter_value(v, depth + 1) for k, v in value.items()}
        values = {k: v for k, (v, _) in pairs.items()}
        return (values if depth == 0 else {'mapping_items': list(values.items())}), all(ok for _, ok in pairs.values())
    if depth < 12 and '__dataclass_fields__' in vars(type(value)):
        # Read stored fields only. Do not call repr, asdict, custom iteration or
        # field descriptors, any of which can execute test/user code.
        try:
            stored = object.__getattribute__(value, '__dict__')
        except AttributeError:
            stored = None
        fields = vars(type(value))['__dataclass_fields__']
        if type(stored) is dict and all(name in stored for name in fields):
            values, complete = parameter_value(stored, depth + 1)
            return {'dataclass': type(value).__module__ + '.' + type(value).__qualname__,
                    'fields': values}, complete
    return {'opaque_type': type(value).__module__ + '.' + type(value).__qualname__}, False


@lru_cache(maxsize=512)
def source_digest(filename):
    try:
        return hashlib.sha256(Path(filename).read_bytes()).hexdigest()
    except OSError:
        return None


@lru_cache(maxsize=128)
def source_tree(filename):
    try:
        return ast.parse(Path(filename).read_text())
    except (OSError, SyntaxError, UnicodeError):
        return None


def iteration_context(frames):
    contexts = []
    complete = True
    for frame, line in frames:
        tree = source_tree(frame.f_code.co_filename)
        if tree is None:
            complete = False
            continue
        functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and n.name == frame.f_code.co_name and n.lineno <= line <= n.end_lineno]
        if not functions:
            continue
        function = min(functions, key=lambda n: n.end_lineno - n.lineno)
        for loop in ast.walk(function):
            if not isinstance(loop, (ast.For, ast.AsyncFor, ast.While)) or not loop.lineno <= line <= loop.end_lineno:
                continue
            if isinstance(loop, ast.While):
                names = {n.id for n in ast.walk(loop.test) if isinstance(n, ast.Name)
                         and n.id in frame.f_locals and n.id != 'self'}
                if not names or any(isinstance(n, (ast.Attribute, ast.Call)) for n in ast.walk(loop.test)):
                    complete = False
            else:
                names = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
            values = {}
            for name in sorted(names):
                if name not in frame.f_locals:
                    complete = False
                    continue
                values[name], ok = parameter_value(frame.f_locals[name])
                complete = complete and ok
            contexts.append(dict(function=frame.f_code.co_qualname, line=loop.lineno,
                                 values=values))
    return contexts, complete


def frame_site(frame, line=None):
    source_hash = source_digest(frame.f_code.co_filename)
    return dict(module=frame.f_globals.get('__name__', ''),
                function=frame.f_code.co_qualname, line=line or frame.f_lineno,
                source_sha256=source_hash)


def method_site(test):
    method = inspect.getattr_static(test, getattr(test, '_testMethodName', ''), None)
    method = getattr(method, '__func__', method)
    code = getattr(method, '__code__', None)
    if code is None:
        return None
    return dict(module=getattr(method, '__module__', ''), function=code.co_qualname,
                line=code.co_firstlineno, source_sha256=source_digest(code.co_filename))


def error_details(test, err):
    frames = list(traceback.walk_tb(err[2]))
    phases = {'setUp': 'setup', '_callSetUp': 'setup',
              'tearDown': 'teardown', '_callTearDown': 'teardown',
              'setUpClass': 'setup_class', 'tearDownClass': 'teardown_class',
              'setUpModule': 'setup_module', 'tearDownModule': 'teardown_module'}
    phase = next((phases[f.f_code.co_name] for f, _ in frames
                  if f.f_code.co_name in phases), 'test')
    candidates = [(f, n) for f, n in frames if f.f_locals.get('self') is test
                  and not f.f_globals.get('__name__', '').startswith('unittest')]
    if not candidates:
        candidates = [(f, n) for f, n in frames if f.f_code.co_name in phases
                      and not f.f_globals.get('__name__', '').startswith('unittest')]
    site = frame_site(*candidates[-1]) if candidates else None
    context, context_complete = iteration_context(candidates)
    try:
        message = str(err[1])
    except Exception:
        message = '<exception string unavailable>'
    reason = dict(kind='assertion' if issubclass(err[0], (getattr(test, 'failureException', None) or AssertionError))
                  else 'exception', exception_type=err[0].__module__ + '.' + err[0].__qualname__,
                  message=message, site=site,
                  traceback=''.join(traceback.format_exception(*err)),
                  attribution='unreviewed-observation', context=context,
                  context_complete=context_complete)
    return phase, site, reason


def condition_context(test):
    frame = inspect.currentframe()
    frames = []
    try:
        while frame is not None:
            module = frame.f_globals.get('__name__', '')
            if frame.f_locals.get('self') is test and not module.startswith(('unittest', 'contextlib')):
                frames.append((frame, frame.f_lineno))
            frame = frame.f_back
        context, complete = iteration_context(frames)
        return (frame_site(*frames[0]) if frames else None), context, complete
    finally:
        del frame
        frames.clear()


class TimedResult(unittest.TextTestResult):
    def __init__(self, *args, journal, **kwargs):
        super().__init__(*args, **kwargs)
        self.journal = journal
        self.timings = []
        self.active = None
        self.setup_skips = []
        self.fixture_events = []

    def emit(self, event, **fields):
        self.journal.write(json.dumps(dict(event=event, **fields)) + "\n")
        self.journal.flush()

    def startTest(self, test):
        self.started = time.perf_counter()
        self.active = dict(id=test.id(), outcome="interrupted", conditions=[])
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
        if self.active is not None and not self.active["conditions"]:
            self.record_simple(test, "passed", kind="method_completion")
        self.outcome("passed")
        super().addSuccess(test)

    def append_condition(self, test, condition):
        if self.active is not None:
            existing = self.active['conditions']
            original = condition['id']
            repeats = [c for c in existing if c.get('repeated_identity', c['id']) == original]
            if repeats:
                # Preserve every observation but never waive ambiguous repeated
                # conditions using an occurrence number as semantic identity.
                for previous in repeats:
                    previous['identity_complete'] = False
                    self.emit('identity_ambiguous', method=test.id(), condition_id=previous['id'])
                condition.update(repeated_identity=original, identity_complete=False,
                                 id=json_digest(dict(identity=original, occurrence=len(repeats))))
            existing.append(condition)
        else:
            self.fixture_events.append(dict(scope=test.id(), **condition))
        self.emit('condition', method=test.id(), condition=condition)

    def record_simple(self, test, outcome, *, kind='method_status', message=None):
        site = method_site(test)
        identity = dict(method=test.id(), phase='test', kind=kind, site=site)
        condition = dict(id=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                         kind=kind, phase='test', site=site, outcome=outcome,
                         identity_complete=bool(site and site.get('source_sha256')))
        if message is not None:
            condition['reason'] = dict(kind='skip', message=message, site=site)
        self.append_condition(test, condition)

    def record_error(self, test, err, outcome):
        phase, site, reason = error_details(test, err)
        identity = dict(method=test.id(), phase=phase, site=site, context=reason['context'])
        condition = dict(id=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                         phase=phase, site=site, reason=reason, outcome=outcome,
                         context=reason['context'],
                         identity_complete=bool(site and site.get('source_sha256') and reason['context_complete']))
        if outcome == 'skipped':
            condition['reason']['kind'] = 'skip'
        self.append_condition(test, condition)

    def addFailure(self, test, err):
        self.record_error(test, err, "failed")
        self.outcome("failed")
        super().addFailure(test, err)

    def addError(self, test, err):
        self.record_error(test, err, "error")
        self.outcome("error")
        super().addError(test, err)

    def addSkip(self, test, reason):
        err = sys.exc_info()
        skip_error = err if err[0] is not None and issubclass(err[0], unittest.SkipTest) else None
        if isinstance(test, unittest.case._SubTest):
            self.record_subtest(test.test_case, test, 'skipped', err=skip_error, skip_reason=reason)
        elif skip_error is not None:
            self.record_error(test, skip_error, 'skipped')
        else:
            self.record_simple(test, 'skipped', message=reason)
        if self.active is None:
            scope = test.id()
            for kind in ('setUpClass', 'setUpModule'):
                prefix = kind + ' ('
                if scope.startswith(prefix) and scope.endswith(')'):
                    self.setup_skips.append(dict(prefix=scope[len(prefix):-1] + '.', reason=reason))
        self.outcome("skipped")
        super().addSkip(test, reason)

    def addExpectedFailure(self, test, err):
        self.record_error(test, err, "expected_failure")
        self.outcome("expected_failure")
        super().addExpectedFailure(test, err)

    def addUnexpectedSuccess(self, test):
        self.record_simple(test, "unexpected_success")
        self.outcome("unexpected_success")
        super().addUnexpectedSuccess(test)

    def record_subtest(self, test, subtest, outcome, err=None, skip_reason=None):
        params, complete = parameter_value(dict(subtest.params))
        message = getattr(subtest, '_message', unittest.case._subtest_msg_sentinel)
        message, message_complete = parameter_value(
            None if message is unittest.case._subtest_msg_sentinel else message)
        site, context, context_complete = condition_context(test)
        identity = dict(method=test.id(), phase='test', params=params, message=message, site=site, context=context)
        condition = dict(id=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                         params=params, message=message, site=site, phase='test', context=context,
                         identity_complete=bool(complete and message_complete and context_complete
                                                and site and site.get("source_sha256")),
                         kind='subtest', outcome=outcome)
        if err is not None:
            _, _, condition['reason'] = error_details(test, err)
            condition['identity_complete'] = condition['identity_complete'] and condition['reason']['context_complete']
        if skip_reason is not None:
            condition['reason'] = dict(kind='skip', message=skip_reason, site=site)
        self.append_condition(test, condition)

    def addSubTest(self, test, subtest, err):
        outcome = 'passed' if err is None else 'failed' if issubclass(err[0], test.failureException) else 'error'
        self.record_subtest(test, subtest, outcome, err=err)
        if err is not None:
            self.outcome(outcome)
        super().addSubTest(test, subtest, err)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-directory", default="evas/tests")
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--input-identity", type=Path)
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
        return 0 if payload['successful'] else 1
    if not 1 <= args.shard_count <= 16 or not 0 <= args.shard_index < args.shard_count:
        parser.error('invalid shard index/count')
    loader = unittest.TestLoader()
    suite = loader.discover(args.start_directory, pattern=args.pattern)
    metadata, source_identity = observation_identity(args.start_directory, args.source_root, args.modules, args.pattern)
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
    if args.input_identity:
        source_identity['execution_identity'] = json.loads(args.input_identity.read_text())
        environment = source_identity['execution_identity'].get('environment', {})
        metadata['runtime_profile']['execution_toolchain'] = {
            key: value for key, value in environment.items() if key not in ('kernel_sha256', 'kernel_overrides', 'shard')}
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
                    schema_version=3, complete=complete,
                    collection_complete=not loader.errors, collection_errors=loader.errors,
                    metadata=metadata, source_identity=source_identity,
                    input_identity=json_digest(dict(metadata=metadata, source_identity=source_identity,
                                                    selected_test_ids=selected_ids)),
                    successful=complete and bool(all_ids) and result.wasSuccessful()
                    and (result.testsRun > 0 or args.shard_count > 1),
                    tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                    skipped=len(result.skipped), expected_failures=len(result.expectedFailures),
                    unexpected_successes=len(result.unexpectedSuccesses),
                    seconds=time.perf_counter() - started, tests=result.timings,
                    discovered_test_ids=all_ids, selected_test_ids=selected_ids,
                    shard_count=args.shard_count, shard_index=args.shard_index,
                    assignment=assignment,
                    fixtures=result.fixture_events,
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

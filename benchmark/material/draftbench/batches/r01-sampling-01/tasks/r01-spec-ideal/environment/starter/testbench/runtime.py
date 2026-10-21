"""Task-local native Spectre runner. Importing or preparing never launches a tool.

The deployment supplies a licensed binary in a separate trusted environment.
Tests inject a process double; such output is always marked software-test-double.
"""
import bisect
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time

from contract import crossings, diagnose, observations, render, validate


class ProtocolError(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data):
    Path(path).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def read_json(path):
    def unique(pairs):
        result = {}
        for k, value in pairs:
            if k in result:
                raise ProtocolError('duplicate JSON key: ' + k)
            result[k] = value
        return result
    def bad_constant(value):
        raise ProtocolError('nonfinite JSON number: ' + value)
    return json.loads(Path(path).read_text(), object_pairs_hook=unique, parse_constant=bad_constant)


def check_settings(settings):
    if settings.get('status') not in ('specified_unvalidated', 'calibrated'):
        raise ProtocolError('contract decisions are not finalized')
    for key in ('voltage_atol', 'time_atol', 'event_guard', 'probe_step', 'timeout_seconds'):
        value = settings.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ProtocolError('positive finalized setting required: ' + key)
    if settings['time_atol'] >= settings['event_guard']:
        raise ProtocolError('timestamp tolerance must be smaller than the event exclusion')
    for key in ('parameter_domain', 'stimulus_domain', 'control_boundaries', 'backend_version'):
        if not settings.get(key):
            raise ProtocolError('finalized protocol field required: ' + key)
    for key in ('reltol', 'vabstol', 'iabstol', 'maxstep'):
        value = settings.get('numerical_settings', {}).get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ProtocolError('positive numerical setting required: ' + key)
    return settings


def validate_domain(cases, settings):
    """Keep every generated case inside the public numerical envelope."""
    p = settings['parameter_domain']
    d = settings['stimulus_domain']
    def within(value, bounds):
        lo, hi = bounds
        return (value >= lo or math.isclose(value, lo, rel_tol=1e-12)) and (value <= hi or math.isclose(value, hi, rel_tol=1e-12))
    for case in cases:
        if not within(case['stop'], d['duration_s']):
            raise ProtocolError('case duration outside public domain')
        for i in case['instances']:
            for key in ('vth', 'vinit'):
                if not within(i[key], p[key]):
                    raise ProtocolError(key + ' outside public parameter domain')
            if any(not within(v, d['vin_V']) for t, v in i['vin']):
                raise ProtocolError('vin outside public domain')
            for (a, x), (b, y) in zip(i['vin'], i['vin'][1:]):
                slope = abs((y-x)/(b-a))
                if slope > d['vin_max_slope_V_per_s'] and not math.isclose(slope, d['vin_max_slope_V_per_s'], rel_tol=1e-12):
                    raise ProtocolError('vin slope outside public domain')
            control_events = []
            for signal in ('track', 'rst'):
                points = i[signal]
                if all(v == i['vth'] for t, v in points):
                    continue  # Declared startup-equality constant control.
                if any(v not in d['control_levels_V'] for t, v in points):
                    raise ProtocolError('control endpoint outside declared low/high levels')
                for (a, x), (b, y) in zip(points, points[1:]):
                    if x != y and not within(b-a, d['control_ramp_s']):
                        raise ProtocolError('control ramp duration outside public domain')
                control_events += crossings(points, i['vth'])
            control_events.sort()
            intervals = ([control_events[0], case['stop']-control_events[-1]] +
                         [b-a for a,b in zip(control_events,control_events[1:])]) if control_events else []
            if any(gap < d['min_event_gap_s'] and not math.isclose(gap, d['min_event_gap_s'], rel_tol=1e-12) for gap in intervals):
                raise ProtocolError('control crossing separation outside public domain')
    return cases


def read_psf(path, signals):
    """Read scalar native PSF ASCII. Reject incomplete or ambiguous measurements."""
    lines = Path(path).read_text().splitlines()
    if not lines or lines[-1].strip() != 'END' or sum(line.strip() == 'VALUE' for line in lines) != 1:
        raise ValueError('incomplete or invalid PSF ASCII')
    start = next(n for n, line in enumerate(lines) if line.strip() == 'VALUE') + 1
    rows = []
    row = None
    for line in lines[start:-1]:
        match = re.fullmatch(r'"([^"\n]+)"\s+(\S+)', line.strip())
        if not match:
            raise ValueError('unsupported scalar PSF record')
        name, raw = match.groups()
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError('nonfinite native waveform')
        if name == 'time':
            if row is not None:
                rows.append(row)
            row = {'time': value}
        else:
            if row is None or name in row:
                raise ValueError('missing time or duplicate native signal')
            row[name] = value
    if row is not None:
        rows.append(row)
    if len(rows) < 2 or any(not set(signals).issubset(row) for row in rows):
        raise ValueError('missing native signals or waveform')
    if any(b['time'] <= a['time'] for a, b in zip(rows, rows[1:])):
        raise ValueError('native waveform timestamps must strictly increase')
    return rows


def measured_observations(rows, plan, case, mapping, time_atol):
    """Select native strobe rows only. Never interpolate across a switch."""
    times = [r['time'] for r in rows]
    if abs(times[0]) > time_atol or abs(times[-1] - case['stop']) > time_atol:
        raise ValueError('native waveform does not span startup through stop')
    observed = []
    for expected in plan:
        if expected['case'] != case['name']:
            continue
        index = bisect.bisect_left(times, expected['time'])
        choices = [j for j in (index - 1, index) if 0 <= j < len(times)]
        nearest = min(choices, key=lambda j: abs(times[j] - expected['time']))
        actual = rows[nearest]
        if abs(actual['time'] - expected['time']) > time_atol:
            raise ValueError('missing native observation: ' + str((expected['instance'], expected['probe'])))
        observed.append(dict(case=case['name'], instance=expected['instance'], probe=expected['probe'],
                             time=actual['time'], **{s: actual[node] for s, node in mapping[expected['instance']].items()}))
    return observed


def execute(argv, cwd, log_path, timeout):
    """Bound a complete process group. No shell and no environment dump."""
    start = time.monotonic()
    env = dict(os.environ, OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    with Path(log_path).open('x') as stream:
        process = subprocess.Popen(argv, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                                   env=env, start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                code = None
            finally:
                # The leader may exit while a child ignores SIGTERM. Always
                # kill the group before treating the timed-out attempt as done.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if code is None:
                code = process.wait()
    return dict(returncode=code, timeout=timed_out, elapsed_s=time.monotonic() - start,
                argv=argv, log_sha256=digest(log_path))


def freeze(candidate, destination):
    """Copy exactly one stable regular file; the original is never executed."""
    candidate = Path(candidate)
    fd = os.open(candidate, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0))
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('submission must be a regular file')
        data = stream.read()
        after = os.fstat(stream.fileno())
    if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
        raise ValueError('submission changed while being frozen')
    if not data.strip():
        raise ValueError('empty submission')
    Path(destination).write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def preflight(candidate):
    text = Path(candidate).read_text()
    code = re.sub(r'"(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*',
                  lambda match: match[0] if match[0].startswith('"') else ' ', text)
    # Resolve local object macros for basic contract checks. This is not a
    # general VA preprocessor or a substitute for deployment isolation.
    flattened = code.replace('\\\n', '')
    macros = {}
    for match in re.finditer(r'^\s*`define[ \t]+([A-Za-z_]\w*)([^\n]*)', flattened, re.M):
        body = match[2]
        if not body.startswith('('):
            macros[match[1]] = body.strip()
    expanded = re.sub(r'^\s*`define[^\n]*', '', flattened, flags=re.M)
    for unused in range(32):
        next_code = re.sub(r'`([A-Za-z_]\w*)', lambda m: macros.get(m[1], m[0]), expanded)
        if next_code == expanded:
            break
        expanded = next_code
    code = expanded
    # These checks enforce the declared model-file contract, not a VA subset.
    includes = re.findall(r'`include\s+"([^"\n]+)"', code)
    if any(name not in ('constants.vams', 'disciplines.vams') for name in includes):
        raise ValueError('submitted model uses a nonstandard include')
    # Strip ordinary string contents before checking system task names.
    tokens = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)
    if re.search(r'\$(?:system|fopen|fclose|fwrite|fdisplay|fstrobe|fscanf|fgets|readmem\w*|getenv)\b', tokens):
        raise ValueError('submitted model uses external file/process access')


def suite_result(required, records):
    if not required or len(set(required)) != len(required):
        raise ValueError('empty or duplicate required case set')
    ids = [r['case'] for r in records]
    if len(set(ids)) != len(ids) or set(ids) - set(required):
        raise ValueError('duplicate or unexpected result')
    if any(r['status'] not in ('pass', 'fail', 'error', 'timeout', 'not_run') for r in records):
        raise ValueError('unknown result status')
    failures = [r for r in records if r['status'] not in ('pass', 'not_run')]
    if failures:
        return dict(score=0, status='fail', reasons=failures)
    if len(records) != len(required) or any(r['status'] == 'not_run' for r in records):
        return dict(score=None, status='not_run', reasons=['required execution incomplete'])
    return dict(score=1, status='pass', reasons=[])


def code_identities():
    return {p.name: digest(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def run_suite(candidate, output, cases, settings, *, launch=False, binary='spectre', executor=None, grading=True):
    """Prepare or execute one frozen attempt; launch defaults to false.

    No observation/result file can be supplied as a CLI scoring input. An executor
    injection is a unit-test seam and is visibly recorded as a test double.
    """
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any((output / name).exists() for name in ('attempt', 'result.json', 'reward.txt')):
        raise FileExistsError('refuse to overwrite an existing attempt/result')
    work = output / 'attempt'
    work.mkdir(mode=0o700)
    report = dict(protocol=settings.get('protocol'), status='not_run', score=None,
                  execution_kind='software-test-double' if executor is not None else 'native-spectre',
                  qualification='not_calibrated', cases=[], source=None,
                  checker_sha256=code_identities())
    def finish():
        if not grading:
            report['diagnostic_only'] = True
            report['passed'] = None if report['score'] is None else report['score'] == 1
            report['score'] = None
        dump(output / 'result.json', report)
        if report['score'] is not None:
            (output / 'reward.txt').write_text(str(report['score']) + '\n')
        return report
    try:
        check_settings(settings)
        validate(cases)
        validate_domain(cases, settings)
        plan = observations(cases, settings['probe_step'], settings['event_guard'])
    except (ValueError, KeyError, TypeError) as exc:
        report.update(reason='protocol_not_ready: ' + str(exc))
        return finish()
    dump(work / 'protocol.json', settings)
    dump(work / 'cases.json', cases)
    dump(work / 'plan.json', plan)
    report['protocol_sha256'] = digest(work / 'protocol.json')
    report['cases_sha256'] = digest(work / 'cases.json')
    report['plan_sha256'] = digest(work / 'plan.json')
    frozen = work / 'circuit.va'
    try:
        report['source'] = freeze(candidate, frozen)
        preflight(frozen)
    except (OSError, ValueError, UnicodeError) as exc:
        report.update(status='fail' if launch else 'not_run', score=0 if launch else None,
                      reason='submission_contract: ' + str(exc))
        return finish()
    artifacts = {frozen: digest(frozen)}
    prepared = []
    for case in cases:
        case_work = work / case['name']
        case_work.mkdir()
        mapping = render(case, plan, case_work, settings)
        shutil.copyfile(frozen, case_work / 'circuit.va')
        for name in ('circuit.va', 'tb.scs', 'nodes.json', 'expected.json'):
            artifacts[case_work / name] = digest(case_work / name)
        prepared.append((case, case_work, mapping))
    for name in ('protocol.json', 'cases.json', 'plan.json'):
        artifacts[work / name] = digest(work / name)
    report['input_manifest'] = {str(path.relative_to(output)): value for path, value in artifacts.items()}
    dump(work / 'input-manifest.json', report['input_manifest'])
    if not launch:
        report.update(reason='prepared only; no process was launched', prepared_cases=[c['name'] for c in cases])
        return finish()
    call = executor or execute
    resolved_binary = str(binary) if executor is not None else shutil.which(str(binary))
    if resolved_binary is None:
        report.update(status='fail', score=0, reason='environment: licensed Spectre executable unavailable')
        return finish()
    report['binary'] = resolved_binary
    if executor is None:
        report['binary_sha256'] = digest(resolved_binary)
    try:
        version_path = work / 'version.log'
        version = call([resolved_binary, '-W'], work, version_path, 30)
        report['version_probe'] = version
        version_text = version_path.read_text(errors='replace')
        if version['timeout'] or version['returncode'] != 0 or settings['backend_version'] not in version_text:
            report.update(status='fail', score=0, reason='environment: backend version preflight failed')
            return finish()
        for case, case_work, mapping in prepared:
            argv = [resolved_binary, '-64', 'tb.scs', '+log', 'spectre.log', '-format', 'psfascii',
                    '-raw', 'psf', '+lqtimeout', '30', '+mt=1']
            record = dict(case=case['name'])
            try:
                execution = call(argv, case_work, case_work / 'stdout.log', settings['timeout_seconds'])
                record['execution'] = execution
                if execution['timeout']:
                    record.update(status='timeout', reason='simulator_timeout')
                elif execution['returncode'] != 0:
                    record.update(status='error', reason='compile_or_runtime_failure; inspect native logs')
                else:
                    waveform = case_work / 'psf/tran.tran.tran'
                    signals = [node for nodes in mapping.values() for node in nodes.values()]
                    rows = read_psf(waveform, signals)
                    actual = measured_observations(rows, plan, case, mapping, settings['time_atol'])
                    own_plan = [r for r in plan if r['case'] == case['name']]
                    diagnosis = diagnose(own_plan, actual, settings['voltage_atol'], settings['time_atol'])
                    dump(case_work / 'observed.json', actual)
                    dump(case_work / 'diagnosis.json', diagnosis)
                    record.update(status=diagnosis['status'], reason='accepted' if diagnosis['status'] == 'pass' else 'specification_mismatch',
                                  waveform_sha256=digest(waveform), native_rows=len(rows), observations=len(own_plan),
                                  diagnosis_sha256=digest(case_work / 'diagnosis.json'))
                if any(not path.is_file() or digest(path) != value for path, value in artifacts.items()):
                    record.update(status='error', reason='frozen_input_changed')
            except (OSError, ValueError, KeyError, TypeError) as exc:
                record.update(status='error', reason='execution_or_measurement: ' + str(exc))
            report['cases'].append(record)
        report.update(suite_result([c['name'] for c in cases], report['cases']))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report.update(status='fail', score=0, reason='environment_or_runner: ' + str(exc))
    return finish()

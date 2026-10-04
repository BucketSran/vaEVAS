"""Independent triangle-oscillator oracle and bounded Spectre task verifier.

Canonical copy; va07/tests/verify.py must have identical bytes. Uses only stdlib.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def area(case, t):
    total = 0.
    for (a, va), (b, vb) in zip(case['control'], case['control'][1:]):
        dt = max(0., min(t, b) - a)
        total += va*dt + (vb-va)*dt*dt/(2*(b-a))
        if t <= b:
            break
    return total


def reference(case, t):
    width = case['hi']-case['lo']
    phase = case['initial']-case['lo']
    if case['direction'] < 0:
        phase = 2*width-phase
    phase = (phase+area(case, t)) % (2*width)
    return case['lo'] + (phase if phase <= width else 2*width-phase)


def roots(case):
    width = case['hi']-case['lo']
    target = (case['hi']-case['initial'] if case['direction'] > 0
              else case['initial']-case['lo'])
    total = area(case, case['stop'])
    result = []
    while target < total:
        prior = 0.
        for (a, va), (b, vb) in zip(case['control'], case['control'][1:]):
            segment = (va+vb)*(b-a)/2
            if target <= prior+segment:
                rem = target-prior
                slope = (vb-va)/(b-a)
                dt = 2*rem/(va+math.sqrt(va*va+2*slope*rem))
                result.append(a+dt)
                break
            prior += segment
        target += width
    return result


def read_psf(path):
    rows = []
    with Path(path).open() as stream:
        for line in stream:
            if line.strip() == 'VALUE':
                break
        else:
            raise ValueError('missing PSF VALUE section')
        row = None
        ended = False
        for line in stream:
            if line.strip() == 'END':
                ended = True
                break
            match = re.fullmatch(r'"([^"]+)"\s+(\S+)', line.strip())
            if not match:
                raise ValueError('unsupported PSF value')
            key, value = match[1], float(match[2])
            if key == 'time':
                if row is not None:
                    rows.append(row)
                row = {'time': value}
            elif row is None or key in row:
                raise ValueError('duplicate signal or missing time')
            else:
                row[key] = value
        if row is not None:
            rows.append(row)
        if not ended:
            raise ValueError('incomplete PSF')
    return rows


def evaluate(rows, case, event_times=None):
    expected = roots(case)
    if len(rows) < 3 or any(not {'time','z','count'} <= r.keys() for r in rows):
        raise ValueError('missing waveform or signals')
    if any(not math.isfinite(v) for r in rows for v in r.values()):
        raise ValueError('nonfinite waveform')
    times = [r['time'] for r in rows]
    if times[0] != 0 or abs(times[-1]-case['stop']) > 1e-12*max(1.,case['stop']):
        raise ValueError('incomplete transient interval')
    gaps = [b-a for a,b in zip(times,times[1:])]
    if min(gaps) < 0 or max(gaps) > case['maxstep']*(1+1e-7):
        raise ValueError('unordered or sparse waveform')
    observed = []
    old = 0
    for row in rows:
        n = round(row['count'])
        if n < 0 or abs(row['count']-n) > case['wave_atol']:
            raise ValueError('noninteger count')
        if n != old:
            if n != old+1:
                raise ValueError('missing, grouped or reversed count')
            observed.append(row['time'])
            old = n
        if all(abs(row['time']-t) > case['time_atol'] for t in expected):
            if n != sum(row['time'] > t for t in expected):
                raise ValueError('incorrect count outside event windows')
    actual = observed if event_times is None else event_times
    if len(observed) != len(expected) or len(actual) != len(expected):
        raise ValueError('incorrect event count')
    voltage_error = max(abs(r['z']-reference(case,r['time'])) for r in rows)
    time_error = max((abs(a-b) for a,b in zip(actual,expected)), default=0.)
    return dict(passed=voltage_error <= case['wave_atol'] and time_error <= case['time_atol'],
                max_voltage_error_v=voltage_error, max_event_error_s=time_error,
                expected_events=expected, observed_events=actual, rows=len(rows))


def execute(binary, work, timeout=15):
    """Bound both time and output; kill the full simulation group on timeout."""
    def limits():
        resource.setrlimit(resource.RLIMIT_FSIZE, (16*1024*1024, 16*1024*1024))
    argv = [binary, '-64', 'tb.scs', '+log', 'spectre.log', '-format', 'psfascii',
            '-raw', 'psf', '+lqtimeout', '5', '+mt=1']
    start = time.monotonic()
    with (work/'stdout.log').open('w') as stream:
        process = subprocess.Popen(argv, cwd=work, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=limits)
        try:
            code = process.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            code, timed_out = None, True
    return dict(returncode=code, timeout=timed_out, elapsed_s=time.monotonic()-start)


def verify(candidate, output, cases_path):
    output.mkdir(parents=True, exist_ok=True)
    cases = json.loads(cases_path.read_text())
    owned = ['report.json', 'reward.txt', *[c['name'] for c in cases]]
    if any((output/name).exists() for name in owned):
        raise ValueError('verifier results already exist; use a new output directory')
    binary = os.environ.get('SPECTRE', 'spectre')
    report = dict(candidate_sha256=sha(candidate), checker_sha256=sha(__file__),
                  cases_sha256=sha(cases_path), cases=[], status='completed', reward=None)
    text = candidate.read_text()
    if any(h not in ['disciplines.vams','constants.vams'] for h in re.findall(r'`include\s+"([^"]+)"',text)) or re.search(r'\$(?:system|fopen|fwrite|fdisplay|readmem\w*)\b', text):
        report.update(status='submission_contract_violation', reward=0)
    else:
        try:
            version = subprocess.run([binary,'-W'], capture_output=True, text=True, timeout=15, check=True)
            report['spectre_version'] = version.stdout.strip()
            for case in cases:
                work = output/case['name']; work.mkdir()
                (work/'dut.va').write_text(text)
                (work/'tb.scs').write_text(case['netlist'])
                record = dict(name=case['name'], **execute(binary,work))
                log = (work/'stdout.log').read_text(errors='replace')
                if 'SPECTRE-209' in log:
                    raise RuntimeError('Spectre license unavailable')
                record['passed'] = False
                if record['returncode'] == 0 and not record['timeout']:
                    path = work/'psf/tran.tran.tran'
                    try:
                        record.update(evaluate(read_psf(path),case), waveform_sha256=sha(path))
                    except (ValueError,KeyError,OSError) as error:
                        record['reason'] = str(error)
                report['cases'].append(record)
            report['reward'] = int(all(c['passed'] for c in report['cases']))
        except (OSError, subprocess.SubprocessError, RuntimeError) as error:
            report.update(status='infrastructure_error', reason=str(error))
    dump(output/'report.json', report)
    if report['reward'] is not None:
        (output/'reward.txt').write_text(str(report['reward'])+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cases', type=Path, default=Path(__file__).with_name('cases.json'))
    args = parser.parse_args()
    result = verify(args.candidate.resolve(), args.output.resolve(), args.cases.resolve())
    print(json.dumps(dict(status=result['status'],reward=result['reward'])))
    raise SystemExit(2 if result['reward'] is None else 0)

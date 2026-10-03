#!/usr/bin/env python3
"""Measure complete JSON requests in separate processes; preserve raw artifacts."""
import argparse
import hashlib
import json
import os
import platform
import re
import resource
import subprocess
import time
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()



def validate(case, request, response):
    """Independent analytic answers; this work is outside the measured boundary."""
    kind, size = case.rsplit('-', 1)
    if request.get('transient'):
        times = request['transient']['output_times']
        expected_events = [0.125*i for i in range(1,9)] if kind == 'timer' else [0.125,0.375,0.625,0.875] if kind == 'cross' else []
        assert [e['time'] for e in response['transient']['events']] == expected_events
        for t, solution in zip(times, response['solutions']):
            expected = {'pwl':lambda:t, 'idt':lambda:0.5*t*t, 'nonlinear_idt':lambda:1/(1+t),
                        'timer':lambda:int(8*t), 'cross':lambda:sum(e<=t for e in expected_events)}[kind]()
            assert abs(solution['voltages'][2]-expected) < 1e-9, (case,t)
    else:
        for sample, solution in zip(request['samples'], response['solutions']):
            value, previous = sample[0], 0.0
            for result in solution['voltages'][2:]:
                if kind == 'chain':
                    expected = value+0.25*previous
                elif kind in ('ring','star','dense'):
                    expected = value/0.75
                elif kind == 'cubic':
                    low, high = -1.0, 1.0
                    for _ in range(60):
                        middle=(low+high)/2
                        if middle+middle**3 < value: low=middle
                        else: high=middle
                    expected=(low+high)/2
                else:
                    assert kind in ('random','grid')
                    expected = value
                assert abs(result-expected) < 1e-9, (case, result, expected)
                previous = expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--baseline-kernel', type=Path)
    parser.add_argument('--baseline-revision')
    parser.add_argument('--requests', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--case', default='*')
    args = parser.parse_args()
    if args.out.exists() or args.repeats < 1:
        parser.error('output must not exist; repeats must be positive')
    args.out.mkdir(parents=True)
    kernel = args.kernel.resolve()
    kernels = [('candidate', kernel)]
    if args.baseline_kernel:
        kernels.insert(0, ('baseline', args.baseline_kernel.resolve()))
    receipt = dict(host=platform.platform(), kernel_sha256=sha(kernel),
                   kernels={name: dict(path=str(binary), sha256=sha(binary)) for name, binary in kernels},
                   baseline_revision=args.baseline_revision,
                   base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                   rust_source_sha256={str(p):sha(p) for p in sorted(Path('evas/rust_core').rglob('*')) if p.is_file() and 'target' not in p.parts and 'fuzz' not in p.parts},
                   boundaries=dict(process='Python serialize + spawn + child read/decode/run/encode + Python parse',
                                   stages='inclusive, overlap; caller thread only; metrics omit allocation sizes',
                                   peak='kernel child RSS from macOS time -l; Python highwater is whole profiler process including prior repeats/cases, not combined concurrent RSS'), records=[])
    paths = sorted(args.requests.glob(args.case+'.json'))
    if not paths:
        parser.error('no matching requests')
    for path in paths:
        request = json.loads(path.read_text())
        for repeat in range(args.repeats):
            expected_output = None
            # Alternate order to reduce a systematic warm-cache bias.
            modes = [(name, binary, diagnostic) for diagnostic in (False, True) for name, binary in kernels]
            if repeat % 2:
                modes.reverse()
            for name, binary, diagnostic in modes:
                label = f'{path.stem}-{repeat}-{name}-{int(diagnostic)}'
                sidecar = (args.out/f'{label}.diagnostics.json').resolve()
                env = dict(os.environ)
                for key in ['EVAS_DIAGNOSTICS_PATH','EVAS_DIAGNOSTICS_RECORDS','EVAS_DIAGNOSTICS_BYTES','EVAS_STATIC_THREADS']:
                    env.pop(key, None)
                if diagnostic:
                    env.update(EVAS_DIAGNOSTICS_PATH=str(sidecar), EVAS_DIAGNOSTICS_RECORDS='0', EVAS_DIAGNOSTICS_BYTES='0')
                start = time.perf_counter()
                encode_start = time.perf_counter()
                data = json.dumps(request, allow_nan=False).encode()
                encode_s = time.perf_counter()-encode_start
                command = [str(binary)]
                if platform.system() == 'Darwin':
                    command = ['/usr/bin/time','-l',*command]
                result = subprocess.run(command, input=data, capture_output=True, env=env, timeout=300)
                process_s = time.perf_counter()-start
                parse_start = time.perf_counter()
                if result.returncode:
                    raise RuntimeError(f'{label}: {result.stderr.decode()}')
                response = json.loads(result.stdout)
                parse_s = time.perf_counter()-parse_start
                end_to_end_s = time.perf_counter()-start
                validate(path.stem, request, response)
                if expected_output is not None and result.stdout != expected_output:
                    raise AssertionError(f'kernel or diagnostics changed response bytes: {label}')
                expected_output = result.stdout
                (args.out/f'{label}.stdout.json').write_bytes(result.stdout)
                (args.out/f'{label}.stderr.log').write_bytes(result.stderr)
                match = re.search(rb'(\d+)\s+maximum resident set size', result.stderr)
                report = json.loads(sidecar.read_text()) if diagnostic else None
                receipt['records'].append(dict(case=path.stem, repeat=repeat, kernel=name, diagnostics=diagnostic,
                    input_sha256=sha(path), wire_input_sha256=hashlib.sha256(data).hexdigest(),
                    output_sha256=hashlib.sha256(result.stdout).hexdigest(), outputs=len(response['solutions']),
                    input_bytes=len(data), output_bytes=len(result.stdout), python_encode_s=encode_s,
                    process_s=process_s, python_parse_s=parse_s, end_to_end_s=end_to_end_s,
                    peak_kernel_rss_bytes=int(match[1]) if match else None,
                    python_process_highwater_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if platform.system()=='Darwin' else 1024),
                    stages=report['stages'] if report else None,
                    counters=report['counters'] if report else None))
            print(f'{path.stem} {repeat} verified', flush=True)
            (args.out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':
    main()

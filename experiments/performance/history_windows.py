#!/usr/bin/env python3
"""Freeze and measure F2 closed-history workloads without timing instrumentation.

Run prepare before changing the implementation. Run measure only after freezing
both release binaries and reserving a quiet interval. Twenty timed launches plus
four instrumented profiles are reported separately. The optional joint case uses
ten additional timed launches after a relevance gate. No retries.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import time

MODEL = '''module m(u,y,q); input u; output y,q; electrical u,y,q,z; integer n; analog begin @(initial_step) n=0; V(z)<+idt(V(u),0); V(y)<+V(u)+V(z); @(cross(V(y)-0.625,1,1e-10,1e-8)) n=1; V(q)<+n; end endmodule'''
CASES = [('many-segments', 8192, 1025), ('ordinary-control', 2, 129)]
JOINT_MODEL = 'module m(u,y,q); input u; output y,q; electrical u,y,q,z; integer n; analog begin @(initial_step) n=0; V(z)<+idt(V(u)-V(z),0); V(y)<+V(u)+V(z); @(cross(V(y)-0.6486049696783552,1,1e-10,1e-8)) n=1; V(q)<+n; end endmodule'
JOINT_CASE = ('joint-history-offset', 8192, 1025)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(directory):
    from evas import Instance, compile_sources
    program = compile_sources({'f2.va': MODEL}, [Instance('dut', 'm', dict(u='u', y='y', q='q'))])
    directory.mkdir(parents=True, exist_ok=True)
    for name, segments, outputs in CASES + [JOINT_CASE]:
        if name == JOINT_CASE[0]:
            program = compile_sources({'f2-joint-offset.va': JOINT_MODEL}, [Instance('dut', 'm', dict(u='u', y='y', q='q'))])
        request = dict(program=program.to_dict(), driven=['u'], samples=[], transient=dict(
            pwl=[[[i / segments, i / segments] for i in range(segments + 1)]],
            output_times=[i / (outputs - 1) for i in range(outputs)], stop=1., max_step=1 / 1024),
            tolerances=dict(absolute=1e-8, relative=0.))
        path = directory / (name + '.json')
        data = json.dumps(request, separators=(',', ':')).encode()
        if path.exists() and path.read_bytes() != data:
            raise ValueError(f'refusing to overwrite a different frozen request: {path}')
        path.write_bytes(data)


def validate(request, response, case):
    if response.get('error'):
        raise ValueError(response['error'])
    solutions = response['solutions']
    times = request['transient']['output_times']
    assert response['transient']['times'] == times
    assert len(solutions) == len(times)
    events = response['transient']['events']
    joint = case == JOINT_CASE[0]
    crossing = .53 if joint else .5
    assert len(events) == 1 and abs(events[0]['time'] - crossing) <= 1e-10, events
    y, q = (response['nodes'].index(node) for node in ['y', 'q'])
    maximum_error = 0.
    for t, row in zip(times, solutions):
        expected = 2 * t - 1 + math.exp(-t) if joint else t + .5 * t * t
        error = abs(row['voltages'][y] - expected)
        maximum_error = max(maximum_error, error)
        assert error <= 1e-8, (t, error)
        if abs(t - crossing) > 1e-10:
            assert row['voltages'][q] == float(t > crossing), (t, row)
    return dict(outputs=len(solutions), events=len(events), maximum_error=maximum_error)


def measure(args):
    args.out.mkdir(parents=True, exist_ok=False)
    kernels = {side: getattr(args, side).resolve() for side in ['baseline', 'candidate']}
    cases = [JOINT_CASE] if args.case == JOINT_CASE[0] else CASES
    receipt = dict(host=platform.platform(), base_revision=args.base_revision,
        candidate_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        source_sha256=sha(Path('evas/rust_core/src/continuous.rs')),
        measurement_tool_sha256=sha(Path(__file__)),
        kernel_sha256={side: sha(binary) for side, binary in kernels.items()},
        request_sha256={name: sha(args.requests / (name + '.json')) for name, _, _ in cases},
        settings=dict(build='cargo build --release --locked', timeout_seconds=30, repeats=5,
            threads=1, absolute=1e-8, relative=0., max_step=1 / 1024),
        boundary='spawn + child read/decode/run/encode + Python response parse; frozen input encoding excluded',
        outside_contention=args.outside_contention, records=[], profiles=[], failures=[], timed_launches=[])
    env = dict(os.environ)
    for key in ['EVAS_DIAGNOSTICS_PATH', 'EVAS_DIAGNOSTICS_RECORDS', 'EVAS_DIAGNOSTICS_BYTES', 'EVAS_STATIC_THREADS']:
        env.pop(key, None)
    env['EVAS_STATIC_THREADS'] = '1'
    wall_start = time.monotonic()
    expected = {}
    try:
        for name, _, _ in cases:
            data = (args.requests / (name + '.json')).read_bytes()
            request = json.loads(data)
            for repeat in range(5):
                sides = ['baseline', 'candidate'] if repeat % 2 == 0 else ['candidate', 'baseline']
                for side in sides:
                    assert time.monotonic() - wall_start < 1200
                    label = f'{name}-{repeat}-{side}'
                    receipt['timed_launches'].append(dict(case=name, repeat=repeat, side=side))
                    started = time.perf_counter()
                    try:
                        result = subprocess.run([str(kernels[side])], input=data, capture_output=True,
                            env=env, timeout=30)
                    except subprocess.TimeoutExpired as error:
                        # Preserve the failed launch in the denominator and retain
                        # partial streams when subprocess supplied them. No retry.
                        if error.stdout is not None:
                            (args.out / (label + '.stdout.partial')).write_bytes(error.stdout)
                        if error.stderr is not None:
                            (args.out / (label + '.stderr.partial')).write_bytes(error.stderr)
                        receipt['failures'].append(dict(case=name, repeat=repeat, side=side,
                            kind='timeout', timeout_seconds=30, seconds=time.perf_counter() - started,
                            stdout_available=error.stdout is not None, stderr_available=error.stderr is not None))
                        continue
                    process_seconds = time.perf_counter() - started
                    # Save raw data before parsing/checking, outside the timed boundary.
                    (args.out / (label + '.stdout.json')).write_bytes(result.stdout)
                    (args.out / (label + '.stderr.log')).write_bytes(result.stderr)
                    assert result.returncode == 0, result.stderr.decode()
                    parse_started = time.perf_counter()
                    response = json.loads(result.stdout)
                    elapsed = process_seconds + time.perf_counter() - parse_started
                    correctness = validate(request, response, name)
                    if name in expected:
                        assert result.stdout == expected[name], 'response bytes differ across repeats or sides'
                    expected[name] = result.stdout
                    receipt['records'].append(dict(case=name, repeat=repeat, side=side, seconds=elapsed,
                        stdout_sha256=hashlib.sha256(result.stdout).hexdigest(), returncode=result.returncode,
                        correctness=correctness))
            # These optional diagnostic builds instrument only traversal work and
            # time. Their four launches never contribute to the timing medians.
            for side in ['baseline', 'candidate']:
                binary = getattr(args, side + '_profile')
                if binary is None:
                    continue
                diagnostic = (args.out / (name + '-' + side + '-profile.json')).resolve()
                profile_env = dict(env, EVAS_DIAGNOSTICS_PATH=str(diagnostic),
                    EVAS_DIAGNOSTICS_RECORDS='0', EVAS_DIAGNOSTICS_BYTES='0')
                result = subprocess.run([str(binary.resolve())], input=data, capture_output=True,
                    env=profile_env, timeout=30)
                assert result.returncode == 0 and result.stdout == expected[name], result.stderr.decode()
                validate(request, json.loads(result.stdout), name)
                receipt['profiles'].append(dict(case=name, side=side, kernel_sha256=sha(binary),
                    diagnostic_sha256=sha(diagnostic), report=json.loads(diagnostic.read_text())))
        receipt['summary'] = {}
        for name, _, _ in cases:
            receipt['summary'][name] = {}
            for side in kernels:
                values = [r['seconds'] for r in receipt['records'] if r['case'] == name and r['side'] == side]
                receipt['summary'][name][side] = dict(median=statistics.median(values), minimum=min(values),
                    maximum=max(values), successful_count=len(values),
                    attempted_count=sum(r['case'] == name and r['side'] == side for r in receipt['timed_launches']))
        receipt['status'] = 'failed' if receipt['failures'] else 'complete'
    except Exception as error:
        receipt['status'] = 'failed'
        receipt['failures'].append(dict(kind=type(error).__name__, message=str(error)))
        raise
    finally:
        receipt['wall_seconds'] = time.monotonic() - wall_start
        (args.out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if receipt['failures']:
        raise RuntimeError('measurement has failed launches; see receipt.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    preparation = commands.add_parser('prepare')
    preparation.add_argument('--requests', required=True, type=Path)
    measurement = commands.add_parser('measure')
    measurement.add_argument('--requests', required=True, type=Path)
    measurement.add_argument('--out', required=True, type=Path)
    measurement.add_argument('--baseline', required=True, type=Path)
    measurement.add_argument('--candidate', required=True, type=Path)
    measurement.add_argument('--baseline-profile', type=Path)
    measurement.add_argument('--candidate-profile', type=Path)
    measurement.add_argument('--case', choices=['initial', JOINT_CASE[0]], default='initial')
    measurement.add_argument('--base-revision', required=True)
    measurement.add_argument('--outside-contention', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.requests)
    else:
        measure(args)


if __name__ == '__main__':
    main()

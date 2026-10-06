"""Run an explicit manifest into a new, complete JSON/CSV output directory."""
import csv
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import sys

from . import CompileError, Instance, KernelError, compile_sources
from .errors import DiagnosticArgumentParser, diagnostic
from .identity import inspect_identity
from .lint import read_input_bytes, decode_input, parse_manifest_input
from .protocol import validate_response
from .runtime import DEFAULT_TIMEOUT, _invoke, _tolerances


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return (json.dumps(value, allow_nan=False, indent=2) + '\n').encode()


def _status(path, value):
    """Replace the sole completion marker only after a complete write."""
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as file:
        file.write(_json(value))
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def _request(manifest, program):
    transient = 'transient' in manifest
    static = 'driven' in manifest or 'samples' in manifest
    if transient == static:
        raise ValueError('manifest requires exactly one static or transient mode')
    if static and not {'driven', 'samples'} <= manifest.keys():
        raise ValueError('static mode requires driven and samples')
    tolerances = manifest.get('tolerances', {})
    if set(tolerances) - {'vabstol', 'reltol', 'absolute', 'relative'}:
        raise ValueError('unknown voltage tolerance')
    request = dict(program=program.to_dict(), tolerances=_tolerances(
        tolerances.get('vabstol'), tolerances.get('reltol'),
        tolerances.get('absolute'), tolerances.get('relative')))
    if static:
        request.update(driven=manifest['driven'], samples=manifest['samples'])
        return 'static', request, len(manifest['samples']), None
    config = manifest['transient']
    if set(config) != {'sources', 'output_times', 'stop', 'max_step'}:
        raise ValueError('transient mode requires sources/output_times/stop/max_step')
    times = config['output_times']
    stop = config['stop']
    if (not isinstance(config['sources'], dict) or not isinstance(times, list) or not times
            or isinstance(stop, bool) or not isinstance(stop, (int, float))
            or not math.isfinite(stop) or stop < 0
            or any(isinstance(t, bool) or not isinstance(t, (int, float))
                   or not math.isfinite(t) or t < 0 or t > stop for t in times)
            or any(a >= b for a, b in zip(times, times[1:]))):
        raise ValueError('transient observation times must be finite, increasing and within stop')
    request.update(driven=list(config['sources']), samples=[], transient=dict(
        pwl=list(config['sources'].values()), output_times=times,
        stop=stop, max_step=config['max_step']))
    return 'transient', request, len(times), times


def _binary64(value):
    converted = float(value)
    if not math.isfinite(converted) or converted != value:
        raise KernelError(dict(kind='invalid_response', message='observation is not a lossless finite binary64 value'))
    return repr(converted)


def run(manifest_path, *, kernel=None, out, timeout=DEFAULT_TIMEOUT):
    """Return the final bundle manifest or raise an error with failed state saved.

    A pre-existing directory is never owned or changed by this call. In a new
    directory, manifest.json is the sole completion marker and is written last.
    """
    out = Path(out)
    out.mkdir()  # Exclusive ownership, before reading even the first input file.
    state = dict(bundle_version=1, status='running', mode=None, files=[],
                 columns=[], identity=None, error=None)
    marker = out / 'manifest.json'

    def save(name, data):
        with (out / name).open('xb') as file:
            file.write(data)
        state['files'].append(dict(path=name, sha256=_digest(data), bytes=len(data)))

    try:
        _status(marker, state)
        if timeout is not None and (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                                    or not math.isfinite(timeout) or timeout <= 0):
            raise ValueError('timeout must be positive finite seconds or None')
        manifest_path = Path(manifest_path).resolve()
        raw = read_input_bytes(manifest_path, 'manifest_io')
        save('input.json', raw)
        state['input'] = dict(path=str(manifest_path), sha256=_digest(raw))
        manifest = parse_manifest_input(decode_input(raw, 'manifest_input'))
        sources = {}
        source_records = []
        for index, name in enumerate(manifest['models']):
            path = (manifest_path.parent / name).resolve()
            data = read_input_bytes(path, 'source_io')
            snapshot = f'source-{index}.va'
            save(snapshot, data)
            source_records.append(dict(path=str(path), sha256=_digest(data), snapshot=snapshot))
            sources[str(path)] = decode_input(data, 'source_input')
        state['sources'] = source_records
        state['frontend_sha256'] = _digest(_json({
            path.name: _digest(path.read_bytes())
            for path in sorted(Path(__file__).resolve().parent.glob('*.py'))}))
        program = compile_sources(sources, [Instance(**row) for row in manifest['instances']])
        mode, request, count, times = _request(manifest, program)
        state.update(mode=mode, observations=count, timeout_seconds=timeout)
        save('request.json', _json(request))
        from .kernel import select_kernel
        kernel = select_kernel(kernel)
        identity, identity_error = inspect_identity(kernel)
        state['identity'] = identity
        if identity_error is not None:
            raise identity_error
        selected = Path(identity['kernel']['path'])
        response = _invoke(request, selected, timeout)
        # Preserve the original decoded machine response even if it is incomplete.
        save('result.json', _json(response))
        validate_response(response, program, count, times)
        if not selected.is_file() or _digest(selected.read_bytes()) != identity['kernel']['sha256']:
            raise KernelError(dict(kind='kernel_process', message='selected kernel changed during run'))
        first = dict(name='sample_index', unit='1') if times is None else dict(name='time_s', unit='s')
        columns = [first, *[dict(name=f'{node}_V', node=node, unit='V') for node in response['nodes']]]
        state['columns'] = columns
        csv_path = out / 'observations.csv'
        with csv_path.open('x', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([column['name'] for column in columns])
            for index, row in enumerate(response['solutions']):
                coordinate = index if times is None else _binary64(times[index])
                writer.writerow([coordinate, *map(_binary64, row['voltages'])])
        data = csv_path.read_bytes()
        state['files'].append(dict(path=csv_path.name, sha256=_digest(data), bytes=len(data)))
        # Recheck closed artifacts before installing the only success marker.
        for artifact in state['files']:
            data = (out / artifact['path']).read_bytes()
            if len(data) != artifact['bytes'] or _digest(data) != artifact['sha256']:
                raise OSError(f"output artifact changed during run: {artifact['path']}")
        state['status'] = 'complete'
        _status(marker, state)
        return state
    except (CompileError, KernelError, OSError, ValueError, KeyError, TypeError,
            OverflowError, metadata.PackageNotFoundError) as exc:
        detail = exc.diagnostic if isinstance(exc, (CompileError, KernelError)) else diagnostic(
            'input_io' if isinstance(exc, OSError) else 'input_error', str(exc))
        state.update(status='failed', error=detail)
        try:
            _status(marker, state)
        except OSError as write_error:
            # Missing/still-running marker remains meaningful when the filesystem
            # cannot save failure state. Preserve both failures on stderr.
            detail = dict(detail, output_write_error=str(write_error))
        if isinstance(exc, (CompileError, KernelError)):
            exc.bundle_diagnostic = detail
            raise
        error = CompileError(str(exc), code=detail['code'])
        error.bundle_diagnostic = detail
        raise error from exc


def main(argv=None):
    parser = DiagnosticArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run'])
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--kernel', type=Path, help='override the bundled kernel')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)
    try:
        state = run(args.manifest, kernel=args.kernel, out=args.out, timeout=args.timeout)
    except (CompileError, KernelError) as exc:
        print(json.dumps(getattr(exc, 'bundle_diagnostic', exc.diagnostic), allow_nan=False), file=sys.stderr)
        return 2
    except OSError as exc:
        print(json.dumps(diagnostic('input_io', str(exc)), allow_nan=False), file=sys.stderr)
        return 2
    print(json.dumps(dict(bundle_version=1, status=state['status'], out=str(args.out.resolve()))))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

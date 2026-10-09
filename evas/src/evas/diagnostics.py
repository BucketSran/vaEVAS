"""Capture and query a bound diagnostic artifact; queries never run the kernel."""
import hashlib
import json
from pathlib import Path
import tempfile

from .errors import DiagnosticArgumentParser
from . import CompileError, Instance, KernelError, compile_sources
from .ir import SCHEMA_VERSION
from .manifest import unique_object, reject_constant, finite_float
from .lint import read_input_bytes, decode_input, parse_manifest_input
from .protocol import validate_response
from .strobe import FIELDS as STROBE_FIELDS, controls as strobe_controls
from .query import static_index, query_static
from .runtime import _invoke, _tolerances, DEFAULT_TIMEOUT


def canonical(value):
    return json.dumps(value, allow_nan=False, sort_keys=True, separators=(',', ':')).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_json(text):
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=reject_constant, parse_float=finite_float)


def frontend_identity():
    directory = Path(__file__).resolve().parent
    return digest(canonical({p.name: digest(p.read_bytes()) for p in sorted(directory.glob('*.py'))}))


def capture(manifest_path, kernel, *, timeout=DEFAULT_TIMEOUT):
    """Return a complete or failed run artifact. A timeout has no complete trace."""
    manifest_path, kernel = Path(manifest_path).resolve(), Path(kernel).resolve()
    manifest_bytes = read_input_bytes(manifest_path, 'manifest_io')
    manifest = parse_manifest_input(decode_input(manifest_bytes, 'manifest_input'))
    paths = [(manifest_path.parent / name).resolve() for name in manifest['models']]
    source_bytes = {str(path): read_input_bytes(path, 'source_io') for path in paths}
    sources = {path: decode_input(data, 'source_input') for path, data in source_bytes.items()}
    identities = dict(manifest=dict(path=str(manifest_path), sha256=digest(manifest_bytes)),
                      sources=[dict(path=path, sha256=digest(data)) for path, data in source_bytes.items()],
                      kernel=dict(path=str(kernel), sha256=digest(kernel.read_bytes())),
                      frontend_sha256=frontend_identity())
    instances = [Instance(**row) for row in manifest['instances']]
    program = compile_sources(sources, instances)
    request = dict(program=program.to_dict(),
                   tolerances=_tolerances(manifest.get('tolerances', {}).get('vabstol'),
                                          manifest.get('tolerances', {}).get('reltol'),
                                          manifest.get('tolerances', {}).get('absolute'),
                                          manifest.get('tolerances', {}).get('relative')))
    # Use the same transport shape as runtime.solve/transient. Manifest-specific
    # arguments are validated explicitly; unknown keys cannot silently disappear.
    if 'transient' in manifest:
        config = manifest['transient']
        if not {'sources', 'output_times', 'stop', 'max_step'} <= config.keys() or set(config) - {'sources', 'output_times', 'stop', 'max_step'} - STROBE_FIELDS:
            raise ValueError('diagnostic transient requires sources/output_times/stop/max_step')
        request.update(driven=list(config['sources']), samples=[], transient=dict(
            pwl=list(config['sources'].values()), output_times=config['output_times'],
            stop=config['stop'], max_step=config['max_step'], **strobe_controls(config)))
        count, times = len(config['output_times']), config['output_times']
    else:
        request.update(driven=manifest['driven'], samples=manifest['samples'])
        count, times = len(manifest['samples']), None
    if set(manifest.get('tolerances', {})) - {'vabstol', 'reltol', 'absolute', 'relative'}:
        raise ValueError('unknown voltage tolerance')
    identities.update(ir_sha256=digest(canonical(request['program'])), request_sha256=digest(canonical(request)))
    response, error, diagnostic, error_diagnostic = None, None, None, None
    with tempfile.TemporaryDirectory(prefix='evas-diagnostic-') as directory:
        sidecar = Path(directory) / 'kernel.json'
        try:
            response = _invoke(request, kernel, timeout, diagnostics_path=sidecar)
            validate_response(response, program, count, times, strobetimes=request.get("transient", {}).get("strobetimes", []))
        except KernelError as exc:
            error = exc.detail
            error_diagnostic = exc.diagnostic
        if sidecar.exists():
            diagnostic = load_json(sidecar.read_text())
    # A binary/source replaced during execution cannot be bound to this session.
    check_files(identities)
    if frontend_identity() != identities['frontend_sha256']:
        raise ValueError('frontend changed during capture')
    status = 'complete' if response is not None and error is None else 'failed'
    if diagnostic is not None:
        if diagnostic.get('diagnostic_version') != 1 or diagnostic.get('status') != status:
            raise ValueError('diagnostic producer/status mismatch')
        if status == 'failed' and diagnostic.get('error') != error:
            raise ValueError('diagnostic error mismatch')
    payload = dict(request=request, static=static_index(program, instances, sources),
                   status=status, response=response, error=error, error_diagnostic=error_diagnostic, diagnostics=diagnostic)
    return dict(session_version=1, identity=identities,
                payload=payload, payload_sha256=digest(canonical(payload)))


def check_files(identity):
    for item in [identity['manifest'], identity['kernel'], *identity['sources']]:
        if digest(Path(item['path']).read_bytes()) != item['sha256']:
            raise ValueError(f"stale session: {item['path']}")


class Session:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.bytes = self.path.read_bytes()
        self.artifact = load_json(self.bytes.decode())
        self.check()

    def check(self):
        artifact = self.artifact
        if self.path.read_bytes() != self.bytes:
            raise ValueError('session file changed after opening')
        if artifact.get('session_version') != 1:
            raise ValueError('unsupported diagnostic session version')
        payload, identity = artifact['payload'], artifact['identity']
        if digest(canonical(payload)) != artifact['payload_sha256']:
            raise ValueError('session payload hash mismatch')
        if (digest(canonical(payload['request'])) != identity['request_sha256'] or
                digest(canonical(payload['request']['program'])) != identity['ir_sha256'] or
                payload['request']['program']['schema_version'] != SCHEMA_VERSION):
            raise ValueError('session IR/request mismatch')
        check_files(identity)
        if frontend_identity() != identity['frontend_sha256']:
            raise ValueError('stale session: frontend changed')

    def query(self, section, *, start=0, limit=100):
        self.check()
        payload = self.artifact['payload']
        if section == 'status':
            report = payload['diagnostics']
            return dict(status=payload['status'], error=payload['error'],
                        error_diagnostic=payload.get('error_diagnostic'),
                        diagnostic_available=report is not None,
                        trace_truncated=report['truncated'] if report else None,
                        identity=self.artifact['identity'])
        if section in ('modules', 'instances', 'nodes', 'contributions', 'operators', 'states', 'events'):
            return query_static(payload['static'], section, start=start, limit=limit)
        if type(start) is not int or start < 0 or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('invalid query range')
        if section == 'trace':
            report = payload['diagnostics']
            if report is None:
                return dict(items=[], status='unknown', reason='No diagnostic sidecar was completed.')
            rows = report['records']
            metadata = dict(status=payload['status'], truncated=report['truncated'], coverage=report['coverage'])
        elif section in ('samples', 'firings'):
            response = payload['response']
            if response is None:
                return dict(items=[], status='unknown', reason='The run did not complete a response.')
            rows = response['solutions'] if section == 'samples' else response.get('transient', {}).get('events', [])
            metadata = dict(status=payload['status'])
        elif section == 'metrics':
            report = payload['diagnostics']
            return dict(status=payload['status'], stages=report['stages'] if report else None,
                        counters=report['counters'] if report else None,
                        timing_boundary='inclusive; stages overlap; calling thread only')
        else:
            raise ValueError('unknown session section')
        stop = min(start+limit, len(rows))
        return dict(items=rows[start:stop], total=len(rows),
                    next_start=stop if stop < len(rows) else None, **metadata)

    def why_no_cross(self, event):
        self.check()
        payload = self.artifact['payload']
        events = payload['static']['events']
        if type(event) is not int or not 0 <= event < len(events):
            raise ValueError('invalid event index')
        if events[event]['trigger']['kind'] not in ('cross', 'or'):
            raise ValueError('selected event is not a cross event')
        response = payload['response']
        firings = response.get('transient', {}).get('events', []) if response else []
        matches = [row for row in firings if row['event'] == event]
        # We do not export a complete guard-sign trajectory. Absence of firing
        # therefore cannot distinguish no root, wrong direction, or failed work.
        return dict(status='observed' if matches else 'unknown', event=event,
                    firing_count=len(matches),
                    reason='Firing records exist.' if matches else 'No complete guard-sign trajectory is available; absence of firing does not establish the cause.')


def main():
    parser = DiagnosticArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    record = sub.add_parser('capture')
    record.add_argument('manifest', type=Path)
    record.add_argument('--kernel', required=True, type=Path)
    record.add_argument('--out', required=True, type=Path)
    record.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT)
    query = sub.add_parser('query')
    query.add_argument('session', type=Path)
    query.add_argument('section')
    query.add_argument('--start', type=int, default=0)
    query.add_argument('--limit', type=int, default=100)
    args = parser.parse_args()
    try:
        if args.action == 'capture':
            result = capture(args.manifest, args.kernel, timeout=args.timeout)
            with args.out.open('x') as output:
                json.dump(result, output, allow_nan=False, indent=2)
            print(json.dumps(dict(status=result['payload']['status'], session=str(args.out))))
        else:
            print(json.dumps(Session(args.session).query(args.section, start=args.start, limit=args.limit), allow_nan=False))
    except (CompileError, KernelError) as exc:
        parser.exit(2, json.dumps(exc.diagnostic, allow_nan=False) + '\n')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        from .errors import diagnostic
        parser.exit(2, json.dumps(diagnostic('input_io' if isinstance(exc, OSError) else 'input_error', str(exc)), allow_nan=False) + '\n')


if __name__ == '__main__':
    main()

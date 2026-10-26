"""Discover declared CI Python entrypoints and independently observe tracked assets.

This is construction-only in --observe-only mode. No TestCase run/setup/body is
called. Trusted imports execute under discover_methods' bounded audit policy.
The YAML support is intentionally restricted to current literal run forms.
"""
import argparse
import ast
import base64
import contextlib
import copy
import fnmatch
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess
import sys
import traceback

WORKFLOW = '.github/workflows/numerical-assurance.yml'
TOOL = Path(__file__).resolve()
NAMESPACES = ('python-regression', 'maintenance', 'validation', 'calibration')
MATH_SCRIPTS = {'evas/validation/check_design_math.py', 'evas/validation/check_timed_operator_math.py',
                'evas/validation/check_dynamics_math.py', 'evas/validation/check_event_conditions_math.py'}
KNOWN_ENV_EXPRESSIONS = {'${{ steps.changes.outputs.base }}': 'CI_INVENTORY_BASE',
                         '${{ steps.changes.outputs.head }}': 'CI_INVENTORY_HEAD'}
BOOTSTRAP = ('import os,runpy,sys; '
             'sys.path[0]=os.getcwd(); '
             'tool=sys.argv[1]; sys.argv=sys.argv[1:]; '
             'runpy.run_path(tool,run_name="__main__")')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return sha(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode())


def relative(value):
    path = PurePosixPath(value)
    if (not value or path.is_absolute() or '..' in path.parts or str(path) != value
            or any(x in value for x in ('$', '`', '\\', '\n', '\x00'))):
        raise ValueError('not a literal repository-relative path: ' + repr(value))
    return value


def namespace(start):
    if start == 'evas/tests':
        return 'python-regression'
    if start in ('scripts/tests', 'evas/capabilities'):
        return 'maintenance'
    return 'validation'


def _unittest(command):
    """Only exact discover syntax. Unknown expansion/control syntax never guessed."""
    if any(token in command for token in ('${', '$(', '`', ';', '&&', '||', '|', '\\')):
        raise ValueError('dynamic/control syntax in unittest command: ' + command)
    args = shlex.split(command, comments=True)
    if args[:5] != ['python3', '-B', '-m', 'unittest', 'discover']:
        raise ValueError('unknown unittest discover command: ' + command)
    start, pattern = None, 'test*.py'
    i = 5
    seen = set()
    while i < len(args):
        option = args[i]
        if option in ('-s', '--start-directory', '-p', '--pattern'):
            key = 'start' if option in ('-s', '--start-directory') else 'pattern'
            if key in seen or i + 1 == len(args):
                raise ValueError('duplicate/incomplete unittest option')
            seen.add(key)
            if key == 'start':
                start = relative(args[i + 1])
            else:
                pattern = args[i + 1]
                if not pattern or '/' in pattern or '$' in pattern:
                    raise ValueError('unknown dynamic unittest pattern')
            i += 2
        elif option in ('-v', '--verbose', '-q', '--quiet'):
            i += 1
        else:
            raise ValueError('unsupported unittest discover option: ' + option)
    if start is None:
        raise ValueError('literal unittest entry needs explicit start directory')
    return start, pattern


def parse_workflow(raw):
    """Parse job/step/run literals, preserving source lines and declaration phases."""
    lines = raw.decode('utf-8').splitlines()
    entries, scripts, jobs = [], [], {}
    job, step, step_if, in_jobs = None, None, None, False
    run_indent = None
    run_style, folded = None, []
    job_env_indent = step_env_indent = None
    step_env = {}
    commands = []
    def flush_folded():
        if folded:
            first = folded[0]
            commands.append((first[0], ' '.join(row[1] for row in folded), *first[2:]))
            folded.clear()
    for number, line in enumerate(lines, 1):
        stripped, indent = line.strip(), len(line) - len(line.lstrip())
        if line == 'jobs:':
            in_jobs = True
            continue
        if not in_jobs:
            continue
        match = re.fullmatch(r'  ([A-Za-z][A-Za-z0-9_-]*):', line)
        if match:
            flush_folded()
            job = match[1]
            jobs[job] = {'env': {}, 'if': None, 'python_versions': []}
            step, step_if, step_env, run_indent = None, None, {}, None
            job_env_indent = step_env_indent = None
            continue
        if job is None:
            continue
        if job_env_indent is not None and stripped and indent <= job_env_indent and stripped != 'env:':
            job_env_indent = None
        if step_env_indent is not None and stripped and indent <= step_env_indent and stripped != 'env:':
            step_env_indent = None
        if run_indent is not None:
            if stripped and indent > run_indent:
                row = (number, stripped, job, step, step_if, copy.deepcopy(step_env))
                if run_style == 'folded':
                    folded.append(row)
                else:
                    commands.append(row)
                continue
            if stripped:
                flush_folded()
                run_indent = None
        if line.startswith('      - '):
            step, step_if, step_env, step_env_indent = None, None, {}, None
            if stripped.startswith('- name:'):
                step = stripped.split(':', 1)[1].strip()
        if indent == 4 and stripped.startswith('if:'):
            jobs[job]['if'] = stripped[3:].strip()
        elif indent == 8 and stripped.startswith('if:'):
            step_if = stripped[3:].strip()
        if stripped.startswith('python-version:'):
            jobs[job]['python_versions'].append(stripped.split(':', 1)[1].strip().strip('"\''))
        if stripped == 'env:':
            if indent == 4:
                job_env_indent = indent
            elif indent == 8:
                step_env_indent = indent
            continue
        env_match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*):\s*(.*)', stripped)
        if env_match and job_env_indent is not None and indent == job_env_indent + 2:
            jobs[job]['env'][env_match[1]] = env_match[2].strip('"\'')
        if env_match and step_env_indent is not None and indent == step_env_indent + 2:
            step_env[env_match[1]] = env_match[2].strip('"\'')
        run = re.match(r'^(?:-\s*)?run:\s*(.*)$', stripped)
        if run:
            value = run[1]
            if value in ('|', '>-'):
                run_indent = indent
                run_style = 'literal' if value == '|' else 'folded'
            elif value.startswith(('>', '|')):
                raise ValueError('unsupported folded/chomp run scalar at line ' + str(number))
            elif value:
                commands.append((number, value, job, step, step_if, copy.deepcopy(step_env)))
    flush_folded()
    for number, command, job, step, step_if, env in commands:
        origin = dict(workflow=WORKFLOW, line=number, job=job, step=step,
                      job_if=jobs[job]['if'], step_if=step_if, command=command,
                      environment_overrides=jobs[job]['env'] | env,
                      declared_python_versions=jobs[job]['python_versions'])
        # Detect unknown forms rather than silently losing a literal-looking entry.
        if re.search(r'\bpython\S*\b.*(?:\bunittest\b|\bdiscover\b)', command):
            start, pattern = _unittest(command)
            if any(('$' in value or '`' in value) and value not in KNOWN_ENV_EXPRESSIONS
                   for value in origin['environment_overrides'].values()):
                raise ValueError('dynamic environment on discovery entry line ' + str(number))
            entry = dict(origin, start=start, pattern=pattern, namespace=namespace(start),
                         collector='unittest', mode='declared-ci-literal', purpose='role-not-semantic-qualification')
            entry['entry_id'] = canonical(entry)
            entries.append(entry)
        elif command.startswith('python3 -B '):
            try:
                args = shlex.split(command)
            except ValueError as error:
                raise ValueError('unknown Python command quoting at line ' + str(number)) from error
            if len(args) > 2 and args[2].endswith('.py') and not any(c in args[2] for c in '$`'):
                scripts.append(dict(origin, source=relative(args[2]), method_denominator=None,
                                    kind='direct-math-script' if args[2] in MATH_SCRIPTS else 'other-python-script',
                                    executed=False))
    return {'schema_version': 1, 'workflow_sha256': sha(raw), 'entries': entries,
            'script_entries': scripts, 'literal_entry_count': len(entries),
            'scope': 'Declared literal set across phases; scheduling expressions recorded, not executed.'}


def primary_entry(root, parsed):
    path = Path(root) / 'scripts/run_regression.py'
    raw = path.read_bytes()
    defaults = {}
    for node in ast.walk(ast.parse(raw)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add_argument' and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value in ('--pattern', '--start-directory')):
            key = node.args[0].value
            values = [kw.value.value for kw in node.keywords if kw.arg == 'default' and isinstance(kw.value, ast.Constant)]
            if key in defaults or len(values) != 1 or not isinstance(values[0], str):
                raise ValueError('main discovery default is not a unique literal argparse value')
            defaults[key] = values[0]
    if set(defaults) != {'--pattern', '--start-directory'}:
        raise ValueError('main discovery defaults missing; do not guess test_*.py')
    calls = [e for e in parsed['script_entries'] if e['source'] == 'scripts/run_regression.py' and e['job'] == 'regression']
    if not calls:
        raise ValueError('primary regression command not found in actual workflow')
    if any(re.search(r'--(?:pattern|start-directory|modules)(?:[=\s]|$)', call['command']) for call in calls):
        raise ValueError('primary invocation overrides discovery defaults; do not guess collection')
    entry = dict(workflow=WORKFLOW, job='regression', step='primary argparse collection',
                 command=None, line=None, origins=calls, source='scripts/run_regression.py',
                 source_sha256=sha(raw), start=relative(defaults['--start-directory']),
                 pattern=defaults['--pattern'], namespace='python-regression', collector='unittest',
                 mode='primary-runner-argparse-discovery-only', environment_overrides=calls[0]['environment_overrides'],
                 declared_python_versions=calls[0]['declared_python_versions'],
                 purpose='Full method construction; not selected scientific test execution.')
    if entry['start'] != 'evas/tests':
        raise ValueError('unknown primary source root; explicit policy review required')
    entry['entry_id'] = canonical(entry)
    return entry


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def error_details(error):
    def stream(value):
        return {'encoding': 'base64', 'data': base64.b64encode(value).decode()} if isinstance(value, bytes) else value
    value = {'type': type(error).__name__, 'message': str(error), 'traceback': traceback.format_exc(),
             'stdout': stream(getattr(error, 'stdout', None)), 'stderr': stream(getattr(error, 'stderr', None))}
    if error.__cause__ is not None:
        value['cause'] = error_details(error.__cause__)
    return value


def child(root, entry, timeout):
    tool = Path(root) / 'scripts/capabilities/discover_methods.py'
    declared = entry['declared_python_versions']
    if declared and (len(declared) != 1 or declared[0] != str(sys.version_info.major) + '.' + str(sys.version_info.minor)):
        raise ValueError('inventory interpreter does not match unique declared phase Python major/minor')
    environment = os.environ.copy()
    # python -m at repository cwd places the cwd on sys.path[0]. The wrapper
    # recreates that startup shape, then runs the same owned discovery worker.
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    if 'PYTHONPATH' not in entry['environment_overrides']:
        environment.pop('PYTHONPATH', None)
    resolved = {}
    for key, value in entry['environment_overrides'].items():
        if value in KNOWN_ENV_EXPRESSIONS:
            actual_key = KNOWN_ENV_EXPRESSIONS[value]
            if actual_key not in os.environ:
                raise ValueError('declared dynamic phase env requires actual CI output: ' + actual_key)
            resolved[key] = os.environ[actual_key]
        else:
            resolved[key] = value
    environment.update(resolved)
    argv = [sys.executable, '-B', '-c', BOOTSTRAP, str(tool), '--worker', '--root', str(root),
            '--start', entry['start'], '--pattern', entry['pattern'], '--namespace', entry['namespace']]
    proc = None
    try:
        proc = subprocess.run(argv, cwd=root, env=environment, capture_output=True, text=True, timeout=timeout)
        parsed = json.loads(proc.stdout.splitlines()[-1])
        if (not isinstance(parsed, dict) or type(parsed.get('schema_version')) is not int
                or parsed['schema_version'] != 1 or parsed.get('namespace') != entry['namespace']
                or not isinstance(parsed.get('methods'), list) or not isinstance(parsed.get('errors'), list)
                or type(parsed.get('discovered_instances')) is not int or type(parsed.get('complete')) is not bool):
            raise ValueError('unknown discovery worker receipt schema')
        if (parsed.get('collector', {}).get('sha256') != sha(tool.read_bytes())
                or parsed['collector'].get('source_relationship') != 'owned-source-root'):
            raise ValueError('discovery worker is not bound to the owned tool source')
        parsed['transport'] = dict(argv=argv, cwd=str(root), returncode=proc.returncode,
                                   stdout=proc.stdout, stderr=proc.stderr,
                                   environment_overrides=entry['environment_overrides'],
                                   actual_resolved_overrides=resolved,
                                   collection_profile='inventory-child runtime; not original phase execution/skip results',
                                   original_python_equivalence='major-minor-declared-only' if declared else 'unpinned-runner-python3-unproven',
                                   sys_path_contract='repository-cwd first, then literal phase PYTHONPATH; TestLoader adds start directory')
        if proc.returncode or not parsed.get('complete') or parsed.get('errors'):
            parsed['complete'] = False
        return parsed
    except (ValueError, IndexError, OSError, subprocess.SubprocessError) as error:
        return dict(schema_version=1, namespace=entry['namespace'], complete=False,
                    errors=[error_details(error)], methods=[], discovered_instances=0,
                    transport=dict(error_details(error), argv=argv, cwd=str(root),
                                   stdout=proc.stdout if proc is not None else error_details(error)['stdout'],
                                   stderr=proc.stderr if proc is not None else error_details(error)['stderr'],
                                   returncode=proc.returncode if proc is not None else None))


def merge_entries(entries, receipts):
    if len(entries) != len(receipts) or len({e['entry_id'] for e in entries}) != len(entries):
        raise ValueError('entry set missing or duplicated')
    merged = {}
    for entry, receipt in zip(entries, receipts):
        ns = entry['namespace']
        bucket = merged.setdefault(ns, dict(schema_version=1, namespace=ns, complete=True,
                                            errors=[], methods=[], entrypoints=[], instance_count=0))
        bucket['entrypoints'].append(dict(entry=entry, discovered_instances=receipt.get('discovered_instances'),
                                         complete=receipt.get('complete'), errors=receipt.get('errors')))
        if (receipt.get('schema_version') != 1 or receipt.get('namespace') != ns
                or receipt.get('complete') is not True or receipt.get('errors')):
            bucket['complete'] = False
            bucket['errors'].append({'entry_id': entry['entry_id'], 'errors': receipt.get('errors')})
        count = receipt.get('discovered_instances')
        if type(count) is not int or count < 0:
            raise ValueError('unknown actual discovered instance count')
        bucket['instance_count'] += count
        for row in receipt.get('methods', []):
            key = (row['module_path'], row['runtime_id'])
            owned = {k: row[k] for k in ('module_path', 'runtime_id', 'module_sha256', 'definition', 'generated')}
            observation = {k: copy.deepcopy(row[k]) for k in ('skip_declaration', 'native_skip_wrapper') if k in row}
            observation['entrypoint_id'] = entry['entry_id']
            previous = next((r for r in bucket['methods'] if (r['module_path'], r['runtime_id']) == key), None)
            if previous is None:
                bucket['methods'].append(copy.deepcopy(owned) | {'entrypoint_ids': [entry['entry_id']],
                                                                  'discovery_observations': [observation]})
            else:
                if {k: previous[k] for k in owned} != owned:
                    raise ValueError('method identity/source conflict in namespace ' + ns + ': ' + str(key))
                if entry['entry_id'] not in previous['entrypoint_ids']:
                    previous['entrypoint_ids'].append(entry['entry_id'])
                previous['discovery_observations'].append(observation)
    for bucket in merged.values():
        bucket['methods'].sort(key=lambda row: (row['module_path'], row['runtime_id']))
        bucket['unique_method_count'] = len(bucket['methods'])
        bucket['generated_count'] = sum(row['generated'] for row in bucket['methods'])
    return merged


def require_catalog(root, data, observation, merged, entries):
    registry = load(Path(root) / 'evas/capabilities/registry.py', 'ci_inventory_registry').load(
        data, root=root, repositories={'vaevas': root})
    catalog = registry.catalog()
    catalog.validate()
    if registry.data.get('asset_scope', {}).get('id') != 'EVAS-scope-v1':
        raise ValueError('require-catalog needs explicit reviewed asset scope; no legacy fallback')
    if not catalog.current('asset') or not catalog.current('method'):
        raise ValueError('require-catalog needs full asset/method data')
    histories = [o for o in registry.objects.values() if o['kind'] in ('historical-audit-record', 'historical-finding')]
    if not histories:
        raise ValueError('require-catalog needs reviewed historical records')
    for obj in histories:
        catalog.read_history(obj)
    rows = observation['assets']
    assets = catalog.reconcile_assets(rows, external_manifest={row['path']: row for row in rows})
    for ns, receipt in merged.items():
        catalog.reconcile_methods(ns, receipt)
    expected = {(e['namespace'], e['start'], e.get('pattern', 'test*.py'))
                for e in catalog.current('entrypoint') if e['collector'] == 'unittest'}
    actual = {(e['namespace'], e['start'], e['pattern']) for e in entries}
    if expected != actual:
        raise ValueError('registered unittest entrypoints differ from actual literal/primary set')
    grouped = {}
    for entry in entries:
        grouped.setdefault((entry['namespace'], entry['start'], entry['pattern']), set()).add(entry['entry_id'])
    registered_origins = {}
    workflow_sha = sha((Path(root) / WORKFLOW).read_bytes())
    for entry in catalog.current('entrypoint'):
        if entry['collector'] != 'unittest':
            continue
        key = (entry['namespace'], entry['start'], entry.get('pattern', 'test*.py'))
        ids = entry.get('ci_entrypoint_ids')
        previous = registered_origins.setdefault(key, set())
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)) or previous.intersection(ids) or not set(ids).issubset(grouped[key]):
            raise ValueError('catalog entrypoint lost exact source phase/pattern origins')
        previous.update(ids)
        if entry.get('workflow_sha256') != workflow_sha:
            raise ValueError('catalog entrypoint workflow bytes changed')
    if registered_origins != grouped:
        raise ValueError('registered CI source origins missing or extra')
    return {'reconciled': True, 'assets': assets, 'historical_rows_read': len(histories),
            'namespace_counts': catalog.namespace_counts(),
            'reconciled_scope': ['Python namespaces', 'reviewed asset scope', 'declared historical source rows'],
            'rust_status': 'not collected by this Python/assets job; independent reviewed receipt integration pending'}


def collect(root, output, *, mode, registry_data=None, timeout=30,
            source_repository=None, source_revision=None, observer=None, collector=None, reconciler=None):
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    result = dict(schema_version=1, producer='capabilities.collect-ci-inventory-v1', mode=mode,
                  construction_complete=False, reconciled=False, scientific_execution=False, errors=[])
    def write(name, value):
        (output / name).write_text(json.dumps(value, sort_keys=True, indent=2, default=str) + '\n')
    try:
        if mode not in ('observe-only', 'require-catalog'):
            raise ValueError('explicit observe-only or require-catalog mode required')
        raw = (root / WORKFLOW).read_bytes()
        parsed = parse_workflow(raw)
        entries = [*parsed['entries'], primary_entry(root, parsed)]
        write('entrypoints.json', parsed | {'primary': entries[-1]})
        observed = observer or load(root / 'scripts/capabilities/observe_assets.py', 'ci_inventory_observer').observe
        streams = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(streams[0]), contextlib.redirect_stderr(streams[1]):
            before = observed(root, source_repository=source_repository, source_revision=source_revision)
        write('observer-before-transport.json', {'stdout': streams[0].getvalue(), 'stderr': streams[1].getvalue()})
        write('assets-before.json', before)
        result['source'] = {k: before.get(k) for k in ('source_commit', 'source_tree', 'source_kind', 'source_profile', 'dirty_paths')}
        result['tool_sources'] = {path: sha((root / path).read_bytes()) for path in
            ('scripts/capabilities/collect_ci_inventory.py', 'scripts/capabilities/discover_methods.py',
             'scripts/capabilities/observe_assets.py')}
        receipts = []
        for index, entry in enumerate(entries):
            try:
                receipt = (collector or child)(root, entry, timeout)
            except Exception as error:
                receipt = dict(schema_version=1, namespace=entry['namespace'], complete=False,
                               errors=[error_details(error)], methods=[], discovered_instances=0,
                               transport=error_details(error))
            receipts.append(receipt)
            write('entry-%03d.json' % index, {'entry': entry, 'receipt': receipt})
        merged = merge_entries(entries, receipts)
        write('namespaces.json', merged)
        streams = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(streams[0]), contextlib.redirect_stderr(streams[1]):
            after = observed(root, source_repository=source_repository, source_revision=source_revision)
        write('observer-after-transport.json', {'stdout': streams[0].getvalue(), 'stderr': streams[1].getvalue()})
        write('assets-after.json', after)
        if before != after:
            raise ValueError('source/assets/modes changed during discovery')
        if raw != (root / WORKFLOW).read_bytes() or parse_workflow(raw)['entries'] != parsed['entries']:
            raise ValueError('actual workflow literal set changed')
        selected_files = {row['module_path'] for receipt in receipts for row in receipt.get('methods', [])}
        paper = []
        for path in sorted((root / 'evas/validation/paper').glob('test_*.py')):
            rel = path.relative_to(root).as_posix()
            literals = [e for e in entries if e['start'] == 'evas/validation/paper' and fnmatch.fnmatchcase(path.name, e['pattern'])]
            if not literals and rel not in selected_files:
                paper.append(dict(path=rel, sha256=sha(path.read_bytes()), status='unrouted-by-observed-literals-pending',
                                  method_denominator=None, executed=False))
        write('unrouted-paper.json', {'files': paper, 'methods': None,
                                    'scope': 'Source-file routing fact only; no extra discovery or test execution.'})
        for script in parsed['script_entries']:
            path = root / script['source']
            script['source_sha256'] = sha(path.read_bytes()) if path.is_file() else None
        write('script-entrypoints.json', {'entries': parsed['script_entries'], 'method_denominator': None})
        result['denominators'] = {ns: {k: value[k] for k in ('instance_count', 'unique_method_count', 'generated_count')}
                                  for ns, value in merged.items()}
        result['entry_count'] = len(entries)
        if any(not receipt['complete'] for receipt in merged.values()):
            raise ValueError('one or more actual discovery entries incomplete; raw errors retained')
        result['construction_complete'] = True
        if mode == 'require-catalog':
            result['catalog'] = (reconciler or require_catalog)(root, registry_data or root / 'evas/capabilities/data', before, merged, entries)
            result['reconciled'] = True
        else:
            result['catalog'] = {'reconciled': False, 'status': 'construction-only; full data/history reconciliation not requested'}
        result['success'] = True
    except Exception as error:
        result['success'] = False
        result['errors'].append(error_details(error))
        if hasattr(error, 'report'):
            result['asset_scope_failure'] = error.report
    finally:
        result['actual_python'] = {'version': sys.version, 'executable': sys.executable,
                                   'bytecode_disabled': sys.dont_write_bytecode}
        result['coordinator'] = {'path': str(TOOL), 'sha256': sha(TOOL.read_bytes())}
        write('summary.json', result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--observe-only', action='store_true')
    mode.add_argument('--require-catalog', action='store_true')
    parser.add_argument('--registry-data', type=Path)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--source-repository', type=Path)
    parser.add_argument('--source-revision')
    args = parser.parse_args(argv)
    result = collect(args.root, args.output, mode='require-catalog' if args.require_catalog else 'observe-only',
                     registry_data=args.registry_data, timeout=args.timeout,
                     source_repository=args.source_repository, source_revision=args.source_revision)
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    sys.exit(main())

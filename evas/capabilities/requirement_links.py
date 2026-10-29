"""Locate the tests that back a requirement card. Links are navigation, never support.

A case names its tests in `tests` and binds its requirement cards in
`requirements`. Python methods are located by namespace, module path and
unittest id; Rust tests by package, target kind, target and native listing id.
Locators are stable keys resolved against Registry.current, because the method
objects themselves are regenerated with content versions on every catalog build
and Rust tests have no method objects. `test_scope` names whole test containers
(a Python module, a Rust test module path) whose every current test must be
linked by some case. `checks` names explicit check_ methods that discovery
never collects (they need an external kernel); they are located in the
registered module source. Nothing here runs a test or confers qualification.

    python3 -B evas/capabilities/requirement_links.py
    python3 -B evas/capabilities/requirement_links.py --base-data OLD/evas/capabilities/data --base-root OLD
"""
import argparse
import ast
import json
from pathlib import Path, PurePosixPath
import sys

from registry import RegistryError, digest, load

ROOT = Path(__file__).resolve().parents[2]
RUST = 'rust-tests'
EXPLICIT = 'explicit-check'
PYTHON_NAMESPACES = ('python-regression', 'validation', 'calibration', 'maintenance')
CAPABILITY_NAMESPACES = ('python-regression', 'validation', RUST)
PYTHON_TEST = ('namespace', 'module', 'runtime_id')
RUST_TEST = ('namespace', 'package', 'target_kind', 'target', 'local_id')
PYTHON_SCOPE = ('namespace', 'module')
RUST_SCOPE = ('namespace', 'package', 'target_kind', 'target', 'module_path')
CHECK = ('module', 'runtime_id')


def _text(value):
    return isinstance(value, str) and bool(value) and value == value.strip()


def _path(value):
    if not _text(value) or '\\' in value or ':' in value:
        return False
    path = PurePosixPath(value)
    return not path.is_absolute() and '..' not in path.parts and str(path) == value


def _shape(value, python, rust):
    if not isinstance(value, dict):
        return None
    namespace = value.get('namespace')
    fields = rust if namespace == RUST else python if namespace in PYTHON_NAMESPACES else None
    if fields is None or set(value) != set(fields) or not all(_text(value[key]) for key in fields):
        return None
    if namespace != RUST and not _path(value['module']):
        return None
    return tuple(value[key] for key in fields)


def test_key(value):
    """Stable key of one test locator, or None when the locator is malformed."""
    return _shape(value, PYTHON_TEST, RUST_TEST)


def scope_key(value):
    """Stable key of one test container, or None when it is malformed."""
    return _shape(value, PYTHON_SCOPE, RUST_SCOPE)


def check_key(value):
    """Key of one explicit check locator, or None when it is malformed."""
    if (not isinstance(value, dict) or set(value) != set(CHECK) or not all(_text(value[key]) for key in CHECK)
            or not _path(value['module'])):
        return None
    return (EXPLICIT, value['module'], value['runtime_id'])


def show(key):
    if key[0] == RUST:
        return f'{RUST}:{key[1]}/{key[2]}/{key[3]}::{key[4]}'
    return ':'.join(key)


def explicit_check(registry, key, modules):
    """None when the check exists, else why not. Discovery must never collect it."""
    _, module, runtime_id = key
    parts = runtime_id.split('.')
    if module not in modules:
        return 'module is not a current catalog asset'
    if len(parts) != 3 or parts[0] != PurePosixPath(module).stem:
        return 'id is not <module>.<class>.<method>'
    if parts[2].startswith('test'):
        return 'name starts with test, so discovery would collect it'
    try:
        tree = ast.parse((Path(registry.root) / module).read_text())
    except (OSError, SyntaxError, ValueError, TypeError):
        return 'module source unreadable'
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == parts[1]:
            if any(isinstance(item, ast.FunctionDef) and item.name == parts[2] for item in node.body):
                return None
    return 'method not found in the module source'


def _member(key, scope):
    if scope[0] == RUST:
        return key[:4] == scope[:4] and key[4].startswith(scope[4] + '::')
    return key[:2] == scope


def _listing_tests(raw):
    """Test keys of one native listing receipt; the catalog reconciles its authenticity."""
    binaries, rows = raw.get('binaries'), raw.get('tests')
    if not isinstance(binaries, list) or not isinstance(rows, list):
        raise ValueError('unknown Rust listing structure')
    found = set()
    for row in rows:
        index = row.get('binary_index') if isinstance(row, dict) else None
        if type(index) is not int or not 0 <= index < len(binaries) or not _text(row.get('local_id')):
            raise ValueError('unknown Rust listing row')
        binary = binaries[index]
        kind = binary.get('target_kind')
        if (not isinstance(kind, list) or len(kind) != 1 or not _text(kind[0])
                or not _text(binary.get('package')) or not _text(binary.get('name'))):
            raise ValueError('unknown Rust listing target')
        if row.get('kind') == 'test':
            found.add((RUST, binary['package'], kind[0], binary['name'], row['local_id']))
    return found


def current_tests(registry):
    """(tests, problems): every current Python method and Rust listing test by stable key.

    A Rust key counts only when every current native listing profile lists it.
    An unreadable listing contributes no Rust test, so its locators fail closed.
    """
    catalog = registry.catalog()
    tests, problems, profiles = {}, [], {}
    for method in catalog.current('method'):
        owner = catalog.bound(method['module'], 'asset')
        tests[(method['namespace'], owner['current_path'], method['runtime_id'])] = (
            method['id'] + '@' + method['version'])
    for entry in catalog.current('entrypoint'):
        if entry.get('collector') == 'binary-listing':
            source = json.dumps(entry['listing_source'], sort_keys=True)
            profiles.setdefault(entry['listing_profile'], set()).add(source)
    if not profiles:
        problems.append('no current Rust listing')
    listed = []
    for profile, sources in sorted(profiles.items()):
        found = set()
        for source in sorted(sources):
            try:
                raw = registry.read_source(catalog.bound(json.loads(source), 'source'))
                found |= _listing_tests(json.loads(raw))
            except (OSError, ValueError, TypeError, KeyError) as error:
                problems.append(f'Rust listing unavailable for {profile}: {error}')
                found = set()
                break
        listed.append(found)
    if listed:
        tests.update((key, 'listed') for key in set.intersection(*listed))
    return tests, problems


def _requirements(registry, case, where, errors):
    current = registry.data['current']
    refs = case.get('requirements')
    if not isinstance(refs, list) or not refs:
        errors.append(f'{where}: tests need at least one bound requirement card')
        return []
    names = []
    for ref in refs:
        if not isinstance(ref, dict):
            errors.append(f'{where}: unknown requirement {ref!r}')
            continue
        label = f"{ref.get('id')}@{ref.get('version')}"
        target = registry.objects.get((ref.get('id'), ref.get('version')))
        if target is None:
            errors.append(f'{where}: unknown requirement {label}')
            continue
        if target['kind'] != 'requirement':
            errors.append(f"{where}: {label} is a {target['kind']}, not a requirement card")
            continue
        if current.get(target['id']) != target['version']:
            errors.append(f'{where}: {label} is not the current version')
        if ref.get('sha256') != digest(target):
            errors.append(f'{where}: {label} content changed since the link was bound')
        if ref not in case.get('dependencies', []):
            errors.append(f'{where}: {label} is not a bound dependency')
        names.append(label)
    return names


def _has_checker(registry, case):
    current = registry.data['current']
    found = False
    for ref in case.get('dependencies', []):
        target = registry.objects.get((ref.get('id'), ref.get('version')))
        if target is None or target['kind'] != 'checker':
            continue
        if ref.get('sha256') != digest(target) or current.get(target['id']) != target['version']:
            return False
        found = True
    return found


def check(registry):
    """Resolve every case link and every declared container against Registry.current."""
    tests, problems = current_tests(registry)
    current = registry.data['current']
    modules = {asset['current_path'] for asset in registry.catalog().current('asset')}
    by_runtime = {}
    for key in tests:
        if key[0] != RUST:
            by_runtime.setdefault(key[2], []).append(key)
    errors, rows, linked, scopes, rust_used = [], [], {}, {}, False
    fields = ('tests', 'test_scope', 'checks')
    for name, version in sorted(current.items()):
        obj = registry.objects[(name, version)]
        where = f'{name}@{version}'
        if obj['kind'] != 'case':
            if any(field in obj for field in fields):
                errors.append(f"{where}: tests, test_scope and checks belong on a case, not a {obj['kind']}")
            continue
        if 'method' in obj and len(by_runtime.get(obj['method'], [])) != 1:
            errors.append(f"{where}: legacy method {obj['method']} does not name exactly one current method")
        if not any(field in obj for field in fields):
            continue
        cards = _requirements(registry, obj, where, errors)
        if not _has_checker(registry, obj):
            errors.append(f'{where}: tests need a bound current checker')
        values, checks = obj.get('tests', []), obj.get('checks', [])
        if not isinstance(values, list) or not isinstance(checks, list) or not values + checks:
            errors.append(f'{where}: tests and checks must be lists, not both empty')
            values, checks = [], []
        seen = set()
        for parse, value in [*((test_key, v) for v in values), *((check_key, v) for v in checks)]:
            key = parse(value)
            if key is None:
                errors.append(f'{where}: malformed test locator {json.dumps(value, sort_keys=True)}')
                continue
            rust_used |= key[0] == RUST
            if key in seen:
                errors.append(f'{where}: repeated test {show(key)}')
                continue
            seen.add(key)
            if key[0] == EXPLICIT:
                problem = explicit_check(registry, key, modules)
                if problem:
                    errors.append(f'{where}: unknown explicit check {show(key)} ({problem})')
                    continue
            elif key not in tests:
                errors.append(f'{where}: unknown test {show(key)}')
                continue
            linked.setdefault(key, set()).update(cards)
            rows.append((where, key))
        containers = obj.get('test_scope', [])
        for value in containers if isinstance(containers, list) else [containers]:
            key = scope_key(value)
            if key is None:
                errors.append(f'{where}: malformed test scope {json.dumps(value, sort_keys=True)}')
                continue
            rust_used |= key[0] == RUST
            scopes.setdefault(key, []).append(where)
    if rust_used:
        errors.extend(problems)
    for scope, owners in sorted(scopes.items()):
        prefix = f'{", ".join(owners)}: test scope {show(scope)}'
        members = sorted(key for key in tests if _member(key, scope))
        if not members:
            errors.append(f'{prefix} has no current tests')
        errors.extend(f'{prefix}: capability test {show(key)} is not linked to a requirement card'
                      for key in members if key not in linked)
    links = [dict(case=where, test=show(key), resolved=tests.get(key, 'module-source'), requirements=sorted(linked[key]))
             for where, key in sorted(rows, key=lambda row: (row[0], show(row[1])))]
    return dict(schema_version=1, errors=sorted(set(errors)), links=links,
                linked_tests=sum(key[0] != EXPLICIT for key in linked),
                linked_checks=sum(key[0] == EXPLICIT for key in linked),
                containers=[show(scope) for scope in sorted(scopes)], confers_support=False)


def linked_keys(registry):
    """Keys that current cases link, whether or not they resolve."""
    found = set()
    for name, version in registry.data['current'].items():
        obj = registry.objects[(name, version)]
        if obj['kind'] == 'case' and isinstance(obj.get('tests'), list):
            found.update(key for key in map(test_key, obj['tests']) if key is not None)
    return found


def new_unlinked(base, head, namespaces=CAPABILITY_NAMESPACES):
    """Tests current in head but not in base, and those no head case links.

    A review aid covering every new test, also outside declared containers. An
    unreadable base listing is a problem, never a reason to count tests as new.
    """
    before, base_problems = current_tests(base)
    after, problems = current_tests(head)
    new = sorted(key for key in after.keys() - before.keys() if key[0] in namespaces)
    linked = linked_keys(head)
    return dict(schema_version=1, new_tests=len(new), unlinked=[show(key) for key in new if key not in linked],
                base_problems=base_problems, problems=problems, confers_support=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'evas/capabilities/data')
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--base-data', type=Path, help='earlier catalog data; list new tests that no case links')
    parser.add_argument('--base-root', type=Path, help='source root of --base-data (default: --root)')
    parser.add_argument('--require-linked', action='store_true', help='also fail when a new test is unlinked')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    # Both catalogs read archived sources from the Git history of the checkout at --root.
    repositories = {'vaevas': args.root}
    try:
        head = load(args.data_dir, root=args.root, repositories=repositories)
        report = check(head)
        if args.base_data is not None:
            base = load(args.base_data, root=args.base_root or args.root, repositories=repositories)
            report['new_since_base'] = new_unlinked(base, head)
    except RegistryError as error:
        print(json.dumps({'errors': [str(error)]}), file=sys.stderr)
        return 2
    if args.report is not None:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    summary = dict(linked_tests=report['linked_tests'], linked_checks=report['linked_checks'],
                   containers=report['containers'], errors=report['errors'])
    since = report.get('new_since_base', {})
    if since:
        summary['new_since_base'] = {key: since[key] for key in ('new_tests', 'unlinked', 'base_problems')}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    unlinked = args.require_linked and since.get('unlinked')
    return 1 if report['errors'] or since.get('base_problems') or unlinked else 0


if __name__ == '__main__':
    sys.exit(main())

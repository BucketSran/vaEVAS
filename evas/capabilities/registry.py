"""Load version-bound evidence without turning execution success into support.

The current map selects versions. References bind both a version and its content.
Historical evaluation retains the old version selection, but never overrides an
explicit revocation or incomplete evidence. This module does not run a backend.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / 'data'

def _owned(name):
    spec = importlib.util.spec_from_file_location('_evas_' + name, Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module



class RegistryError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def reference(obj):
    return {'id': obj['id'], 'version': obj['version'], 'sha256': digest(obj)}


class Registry:
    def __init__(self, data, *, root=None, repositories=None):
        self.repositories = repositories or {}
        if data.get('schema_version') != 1:
            raise RegistryError('unsupported registry schema')
        if data.get('inventory_identity') and digest(data['inventory']) != data['inventory_identity']:
            raise RegistryError('inventory identity changed; reconcile with fixed sources and review')
        self.data = data
        self.root = Path(root) if root is not None else None
        self.objects = {}
        for obj in data['objects']:
            key = (obj['id'], obj['version'])
            if key in self.objects:
                raise RegistryError(f'duplicate object version: {key}')
            self.objects[key] = obj
        for name, version in data['current'].items():
            if (name, version) not in self.objects:
                raise RegistryError(f'unknown current version: {name}@{version}')
        inventory = [item['id'] for item in data['inventory']]
        mapped = [item['source_id'] for item in data['dispositions']]
        if len(set(inventory)) != len(inventory) or len(set(mapped)) != len(mapped):
            raise RegistryError('duplicate inventory or disposition')
        missing = set(inventory) - set(mapped)
        extra = set(mapped) - set(inventory)
        if missing or extra:
            raise RegistryError(f'unmapped inventory: {sorted(missing)}; unknown: {sorted(extra)}')
        inventory_ids = set(inventory)
        for item in data['inventory']:
            refs = item.get('occurrence_ids', []) + [item[key] for key in ('parent_id', 'caption_source_id') if item.get(key)]
            if any(ref not in inventory_ids for ref in refs):
                raise RegistryError(f'unreachable inventory reference: {item["id"]}')
        for item in data['dispositions']:
            if item['decision'] not in ('included', 'excluded', 'pending') or not item.get('reason'):
                raise RegistryError(f'invalid disposition: {item}')
        for obj in self.objects.values():
            self._check_links(obj, set())
        try:
            self.catalog().validate()
        except (ValueError, KeyError, TypeError) as error:
            raise RegistryError(str(error)) from error

    def catalog(self):
        return _owned('asset_catalog').Catalog(self)

    def read_source(self, source):
        return _owned('source_reader').read_source(source, root=self.root, repositories=self.repositories)

    def _check_links(self, obj, visiting):
        key = (obj['id'], obj['version'])
        if key in visiting:
            raise RegistryError(f'dependency cycle: {key}')
        for ref in obj.get('dependencies', []):
            target = self.objects.get((ref['id'], ref['version']))
            if target is None:
                raise RegistryError(f'missing dependency: {ref}')
            if not isinstance(ref.get('sha256'), str) or len(ref['sha256']) != 64:
                raise RegistryError(f'unbound dependency: {ref}')
            self._check_links(target, visiting | {key})

    def effective_standard(self, feature):
        profile = self.data['language_profile']
        selected = [profile['changes'][change][feature]
                    for change in profile['selected_changes']
                    if feature in profile['changes'].get(change, {})]
        if len(set(selected)) > 1:
            raise RegistryError(f'conflicting language selection: {feature}')
        return selected[0] if selected else profile['base']

    def qualification_gaps(self, name, *, historical=False):
        version = self.data['current'][name]
        gaps = []
        visited = set()

        def gap(obj, message):
            gaps.append(f"{obj['id']}@{obj['version']}: {message}")

        def dependency_refs(obj, kind):
            return [ref for ref in obj.get('dependencies', [])
                    if self.objects[(ref['id'], ref['version'])]['kind'] == kind]

        def one(obj, kind):
            refs = dependency_refs(obj, kind)
            if len(refs) != 1:
                gap(obj, f'requires exactly one {kind} identity')
                return None
            return self.objects[(refs[0]['id'], refs[0]['version'])]

        def bound(obj, field, kind):
            ref = obj.get(field)
            if not isinstance(ref, dict) or ref not in obj.get('dependencies', []):
                gap(obj, f'{field} is not a bound {kind} dependency')
                return None
            if kind != 'source' and len(dependency_refs(obj, kind)) != 1:
                gap(obj, f'{field} has ambiguous {kind} dependencies')
                return None
            target = self.objects.get((ref.get('id'), ref.get('version')))
            if target is None or target['kind'] != kind:
                gap(obj, f'{field} has the wrong evidence kind')
                return None
            return target

        def receipt(obj, field):
            source = bound(obj, field, 'source')
            if source is None:
                return None
            try:
                raw = self.read_source(source)
                payload = json.loads(raw)
                if not isinstance(payload, dict) or payload.get('schema_version') != 1:
                    gap(obj, f'{field} has an unknown receipt format')
                    return None
                return payload
            except (OSError, ValueError, TypeError):
                gap(obj, f'{field} evidence cannot be read')
                return None

        def same_receipt_fields(obj, payload, expected, field):
            if payload is not None and any(payload.get(k) != v for k, v in expected.items()):
                gap(obj, f'{field} does not bind the declared evidence and scope')

        def controls_valid(obj):
            controls = obj.get('controls', {})
            if not isinstance(controls, dict):
                gap(obj, 'missing accept/reject calibration')
                return False
            groups = [controls.get(key) for key in ('accept', 'reject')]
            if any(not isinstance(values, list) or not values
                   or any(not isinstance(value, str) or not value for value in values)
                   for values in groups):
                gap(obj, 'missing accept/reject calibration')
                return False
            ids = groups[0] + groups[1]
            if len(ids) != len(set(ids)):
                gap(obj, 'calibration control identities overlap or repeat')
                return False
            return True

        def check_qualification(obj):
            evidence = {kind: one(obj, kind) for kind in
                        ('case', 'execution', 'analysis', 'review')}
            for parent, child in (('analysis', 'case'), ('analysis', 'execution'),
                                  ('review', 'analysis'), ('review', 'case')):
                if evidence[parent] and evidence[child]:
                    if reference(evidence[child]) not in evidence[parent].get('dependencies', []):
                        gap(obj, f'{parent} does not bind the selected {child}')
            case, execution, review = (evidence[k] for k in ('case', 'execution', 'review'))
            if case and execution and case.get('inputs') != execution.get('inputs'):
                gap(obj, 'execution does not bind the selected scientific inputs')
            if case:
                for owner in (evidence['analysis'], review):
                    if owner and owner.get('case') != reference(case):
                        gap(obj, 'analysis/review does not identify the selected case')
            claim = {key: obj.get(key) for key in ('scope', 'requirements', 'backend')}
            if not all(claim.values()):
                gap(obj, 'qualification requires scope, requirements and backend')
            if review and review.get('claim') != claim:
                gap(obj, 'qualification exceeds or differs from the reviewed claim')
            if case and (case.get('scope') != claim['scope']
                         or case.get('requirements') != claim['requirements']):
                gap(obj, 'qualification differs from the reviewed case scope/requirements')
            if execution and execution.get('backend') != claim['backend']:
                gap(obj, 'qualification differs from the executed backend identity')
            for owner in (obj, case, review):
                if owner is None:
                    continue
                for ref in claim.get('requirements') or []:
                    target = self.objects.get((ref.get('id'), ref.get('version')))
                    if ref not in owner.get('dependencies', []) or not target or target['kind'] != 'requirement':
                        gap(obj, 'claim requirement is not bound by qualification, case and review')

        def visit(obj):
            key = (obj['id'], obj['version'])
            if key in visited:
                return
            visited.add(key)
            if not historical and self.data['current'].get(obj['id']) != obj['version']:
                gap(obj, 'superseded version')
            if obj.get('status') != 'active':
                gap(obj, obj.get('status', 'missing status'))
            kind = obj['kind']
            deps = obj.get('dependencies', [])
            if kind == 'source':
                sha = obj.get('sha256', '')
                if not obj.get('origin') or not isinstance(sha, str) or len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                    gap(obj, 'missing source identity')
                if 'embedded' in obj and digest(obj['embedded']) != sha:
                    gap(obj, 'embedded source bytes changed')
                if obj.get('path'):
                    path = self.root / obj['path'] if self.root is not None else None
                    if path is None or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
                        gap(obj, 'source file missing or changed')
            else:
                if not deps:
                    gap(obj, 'missing evidence dependencies')
                if kind not in ('execution', 'analysis', 'review', 'calibration-execution'):
                    if obj.get('review') != 'approved':
                        gap(obj, 'review missing')
                if kind == 'checker-definition':
                    if not dependency_refs(obj, 'source') or not obj.get('scope') or not obj.get('budget'):
                        gap(obj, 'checker definition requires source, scope and budget')
                elif kind == 'calibration-execution':
                    bound(obj, 'subject', 'checker-definition')
                    payload = receipt(obj, 'raw_report')
                    same_receipt_fields(obj, payload, {
                        'subject': obj.get('subject'), 'complete': True,
                        'backend': obj.get('backend'), 'outcomes': obj.get('outcomes')}, 'raw_report')
                    if obj.get('complete') is not True or obj.get('outcome') != 'passed' or not obj.get('backend'):
                        gap(obj, 'incomplete or nonpassing calibration execution')
                    if controls_valid(obj):
                        outcomes = obj.get('outcomes', {})
                        for category, expected in (('accept', 'accepted'), ('reject', 'rejected')):
                            for control in obj['controls'][category]:
                                if outcomes.get(control) != expected:
                                    gap(obj, f'control {control} lacks its expected observed outcome')
                elif kind == 'calibration':
                    subject = bound(obj, 'subject', 'checker-definition')
                    execution = bound(obj, 'execution', 'calibration-execution')
                    payload = receipt(obj, 'approval')
                    controls_valid(obj)
                    if not obj.get('reviewer') or not obj.get('scope'):
                        gap(obj, 'calibration review identity or scope missing')
                    if subject and subject.get('scope') != obj.get('scope'):
                        gap(obj, 'calibration scope differs from its subject')
                    if execution and (execution.get('subject') != obj.get('subject')
                                      or execution.get('controls') != obj.get('controls')):
                        gap(obj, 'calibration execution tested another subject or controls')
                    same_receipt_fields(obj, payload, {
                        'decision': 'approved', 'reviewer': obj.get('reviewer'),
                        'subject': obj.get('subject'), 'execution': obj.get('execution'),
                        'scope': obj.get('scope'), 'controls': obj.get('controls')}, 'approval')
                elif kind == 'checker':
                    subject = bound(obj, 'subject', 'checker-definition')
                    calibration = one(obj, 'calibration')
                    if calibration and (calibration.get('subject') != obj.get('subject')
                                        or calibration.get('scope') != obj.get('scope')):
                        gap(obj, 'checker does not match its calibrated subject and scope')
                    if subject and subject.get('scope') != obj.get('scope'):
                        gap(obj, 'checker scope differs from its definition')
                elif kind == 'case-inputs':
                    if not dependency_refs(obj, 'source'):
                        gap(obj, 'scientific inputs require source identities')
                elif kind == 'case':
                    bound(obj, 'inputs', 'case-inputs')
                    if not obj.get('scope') or not obj.get('requirements'):
                        gap(obj, 'case scope or requirements missing')
                elif kind == 'execution':
                    bound(obj, 'inputs', 'case-inputs')
                    payload = receipt(obj, 'raw_report')
                    same_receipt_fields(obj, payload, {
                        'inputs': obj.get('inputs'), 'complete': True,
                        'outcome': obj.get('outcome'), 'backend': obj.get('backend')}, 'raw_report')
                    if obj.get('outcome') != 'passed' or obj.get('complete') is not True or not obj.get('backend'):
                        gap(obj, 'incomplete or nonpassing execution')
                elif kind == 'analysis':
                    execution = one(obj, 'execution')
                    checkers = dependency_refs(obj, 'checker')
                    if not checkers:
                        gap(obj, 'analysis requires checker identities')
                    case = bound(obj, 'case', 'case')
                    if case and sorted(map(digest, checkers)) != sorted(map(digest, dependency_refs(case, 'checker'))):
                        gap(obj, 'analysis checker identity differs from its case')
                    if case and execution and case.get('inputs') != execution.get('inputs'):
                        gap(obj, 'analysis execution used different scientific inputs')
                    if obj.get('outcome') != 'accepted':
                        gap(obj, 'analysis not accepted')
                elif kind == 'review':
                    analysis = one(obj, 'analysis')
                    bound(obj, 'case', 'case')
                    payload = receipt(obj, 'evidence')
                    if obj.get('decision') != 'approved' or not obj.get('reviewer') or not obj.get('claim'):
                        gap(obj, 'missing independent approval identity and claim')
                    same_receipt_fields(obj, payload, {
                        'decision': 'approved', 'reviewer': obj.get('reviewer'),
                        'claim': obj.get('claim'), 'case': obj.get('case'),
                        'analysis': reference(analysis) if analysis else None}, 'evidence')
                elif kind == 'qualification':
                    check_qualification(obj)
            for ref in deps:
                target = self.objects[(ref['id'], ref['version'])]
                if ref['sha256'] != digest(target):
                    gap(obj, f'dependency content changed: {ref["id"]}')
                visit(target)

        visit(self.objects[(name, version)])
        return sorted(set(gaps))

    def qualified(self, name, *, historical=False):
        # Provenance and readiness are not an approval of a case or backend.
        obj = self.objects[(name, self.data['current'][name])]
        return obj['kind'] in ('checker', 'qualification') and not self.qualification_gaps(name, historical=historical)


def load(data_dir=DATA, *, root=None, repositories=None):
    """Read one logical registry; the inventory is independent of its dispositions."""
    data_dir = Path(data_dir)
    data = json.loads((data_dir / 'registry.json').read_text())
    catalog = _owned('asset_catalog')
    parts = data.get('object_parts', [])
    if not isinstance(parts, list) or len(parts) != len(set(parts)):
        raise RegistryError('duplicate/invalid object parts')
    for name in parts:
        try:
            catalog.relative(name)
            part = json.loads((data_dir / name).read_text())
            if set(part) != {'schema_version', 'kind', 'objects'} or part['schema_version'] != 1 or part['kind'] not in catalog.KINDS:
                raise ValueError('unknown object part schema')
            if any(o.get('kind') not in catalog.KINDS[part['kind']] for o in part['objects']):
                raise ValueError('wrong object kind in part')
            data['objects'].extend(part['objects'])
        except (ValueError, KeyError, TypeError) as error:
            raise RegistryError(str(error)) from error
    effective_root = Path(root) if root is not None else Path(__file__).resolve().parents[2]
    try:
        prefix = data_dir.resolve().relative_to(effective_root.resolve())
        data['_catalog_metadata_paths'] = [(prefix / name).as_posix() for name in ['registry.json', *parts]]
    except ValueError as error:
        raise RegistryError('registry data must be inside the declared source root') from error
    data['inventory'] = json.loads((data_dir / 'source-inventory.json').read_text())['items']
    data['dispositions'] = json.loads((data_dir / 'dispositions.json').read_text())['items']
    audit = json.loads((data_dir / 'boundary-audit.json').read_text())
    data['inventory_identity'] = audit['normalized_inventory_identity']
    data['target_scope'] = json.loads((data_dir / 'target-scope.json').read_text())
    data['language_profile'] = json.loads((data_dir / 'language-profile.json').read_text())
    return Registry(data, root=root if root is not None else Path(__file__).resolve().parents[2], repositories=repositories)


def main():
    reg = load()
    current = reg.data['current']
    qualifications = [name for name in current
                      if reg.objects[(name, current[name])]['kind'] == 'qualification']
    print(json.dumps({'inventory_items': len(reg.data['inventory']),
                      'dispositions': len(reg.data['dispositions']),
                      'current_objects': len(current),
                      'qualified_scopes': [name for name in qualifications if reg.qualified(name)]},
                     ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()

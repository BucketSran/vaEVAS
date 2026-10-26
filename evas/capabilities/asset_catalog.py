"""Metadata views over Registry.current, never a qualification authority."""
import hashlib
import json
from pathlib import PurePosixPath

KINDS = {'assets': {'asset'}, 'methods': {'method'}, 'sources': {'source'},
         'history': {'historical-audit-record', 'historical-finding'},
         'entrypoints': {'entrypoint'}}
NAMESPACES = {'python-regression', 'rust-tests', 'calibration', 'maintenance', 'validation'}
EXTERNAL_ROLES = {'catalog-meta', 'derived', 'governance'}

def relative(path):
    if not isinstance(path, str) or not path or "\\" in path or ":" in path:
        raise ValueError('invalid relative path')
    value = PurePosixPath(path)
    if value.is_absolute() or '..' in value.parts or str(value) != path:
        raise ValueError('invalid relative path')
    return path

def sha(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('invalid SHA256')

def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

class Catalog:
    def __init__(self, registry):
        self.registry = registry

    def current(self, kind):
        r = self.registry
        return [r.objects[(name, version)] for name, version in r.data['current'].items()
                if r.objects[(name, version)]['kind'] == kind]

    def bound(self, ref, kind=None):
        obj = self.registry.objects.get((ref.get('id'), ref.get('version')))
        if obj is None or canonical(obj) != ref.get('sha256') or (kind and obj['kind'] != kind):
            raise ValueError('missing, changed or wrong-kind catalogue reference')
        return obj

    def validate(self):
        seen = set()
        for obj in self.registry.objects.values():
            kind = obj['kind']
            if kind not in set.union(*KINDS.values()):
                continue
            # Existing PR1 sources retain their established schema.
            if kind == 'source' and 'schema_version' not in obj:
                continue
            if obj.get('schema_version') != 1:
                raise ValueError('unsupported catalogue object schema')
            for ref in obj.get('dependencies', []):
                self.bound(ref)
            if kind == 'asset':
                relative(obj['current_path'])
                content = obj['content']
                role = obj['role']
                governed = {'evas/validation/baselines/regression-v1.json',
                            'evas/validation/baselines/regression-v1.review.json'}
                must_be_external = obj['current_path'] in governed | set(self.registry.data.get('_catalog_metadata_paths', []))
                if must_be_external and content.get('algorithm') != 'external-input-manifest':
                    raise ValueError('catalog/governance path cannot store its own latest whole-file SHA')
                if role.get('status') not in ('pending', 'confirmed') or not role.get('reason'):
                    raise ValueError('asset role requires explicit status/reason')
                if content.get('algorithm') == 'sha256':
                    sha(content.get('value'))
                    if role.get('value') in EXTERNAL_ROLES:
                        raise ValueError('self/governance identity must be external')
                elif content.get('algorithm') == 'external-input-manifest':
                    if role.get('value') not in EXTERNAL_ROLES or content != {
                        'algorithm': 'external-input-manifest', 'scope': 'actual-execution-inputs',
                        'producer': 'capabilities.observe-assets-v1'}:
                        raise ValueError('invalid external identity scope')
                else:
                    raise ValueError('unknown content identity')
                if obj.get('consumer_status') not in ('pending', 'partial', 'complete'):
                    raise ValueError('consumer closure must be explicit')
                for ref in obj.get('consumers', []):
                    self.bound(ref)
            elif kind == 'method':
                if obj['namespace'] not in NAMESPACES - {'rust-tests'} or not isinstance(obj['generated'], bool):
                    raise ValueError('invalid method namespace/generated flag')
                owner = self.bound(obj['module'], 'asset')
                relative(obj['definition']['path']); sha(obj['definition']['sha256'])
                if obj['definition']['path'] != owner['current_path']:
                    self.bound(obj['definition_asset'], 'asset')
                if obj.get('semantic_status') not in ('pending', 'reviewed'):
                    raise ValueError('missing semantic status')
                for ref in obj['entrypoints']:
                    if self.bound(ref, 'entrypoint')['namespace'] != obj['namespace']:
                        raise ValueError('entrypoint namespace mismatch')
            elif kind == 'source':
                if obj.get('availability') not in ('repository-contained', 'published-archive', 'pending', 'local-only', 'reference-only') or not obj.get('origin'):
                    raise ValueError('source requires availability and origin')
                sha(obj.get('sha256'))
                locator = obj.get('locator', {})
                if locator.get('kind') == 'repository-relative':
                    relative(locator['path'])
                elif locator.get('kind') == 'git-object':
                    import re
                    relative(locator['path'])
                    if not locator.get('repository') or not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}', locator.get('revision') or ''):
                        raise ValueError('published archive requires immutable full commit')
                    if obj['availability'] != 'published-archive':
                        raise ValueError('Git source must declare published availability')
                elif locator.get('kind') == 'pending-archive':
                    relative(locator['path'])
                    if obj['availability'] != 'pending' or locator.get('revision') is not None or not locator.get('repository'):
                        raise ValueError('invalid unpublished archive identity')
                elif locator.get('kind') != 'embedded' or 'value' not in locator:
                    raise ValueError('unknown source locator schema')
            elif kind == 'entrypoint':
                if obj['namespace'] not in NAMESPACES or obj['collector'] not in ('unittest', 'binary-listing'):
                    raise ValueError('unsupported entrypoint')
                if obj['collector'] == 'unittest':
                    relative(obj['start'])
                else:
                    if obj['namespace'] != 'rust-tests':
                        raise ValueError('binary listing requires separate Rust namespace')
                    self.bound(obj['listing_source'], 'source')
            elif kind.startswith('historical-'):
                self.bound(obj['source'], 'source')
                sha(obj['original_row_sha256']); sha(obj['scope_sha256'])
                if not isinstance(obj.get('row_pointer'), str) or not isinstance(obj.get('scope_pointer'), str):
                    raise ValueError('historical row and scope require source pointers')
                binding = self._history_module('history_binding')
                for ref in binding.shape(obj):
                    method = self.bound(ref, 'method')
                    if obj['alignment']['status'] == 'matched':
                        owner = self.bound(method['module'], 'asset')
                        if obj.get('source_method_sha256') != method['definition']['sha256'] or obj.get('source_module_sha256') != owner['content'].get('value'):
                            raise ValueError('declared historical hashes differ from bound current method')
                # This validates declarations only. read_history additionally validates
                # actual immutable raw row IDs/verdict/hashes before a consumer uses them.
            if kind in ('asset', 'method'):
                field, history, prior = ('current_path', 'location_history', 'prior_asset') if kind == 'asset' else ('runtime_id', 'runtime_history', 'prior_method')
                for old in self.registry.objects.values():
                    if old['id'] == obj['id'] and old['version'] != obj['version'] and old.get(field) != obj.get(field):
                        # Only selected current versions must retain the prior identity.
                        if self.registry.data['current'].get(obj['id']) == obj['version'] and not any(self.bound(h[prior]) == old for h in obj.get(history, []) if prior in h):
                            raise ValueError('rename/move lost known historical identity')
        for obj in self.current('method'):
            key = (obj['namespace'], self.bound(obj['module'])['current_path'], obj['runtime_id'])
            if key in seen:
                raise ValueError('duplicate current runtime identity')
            seen.add(key)
        self.scope().validate_catalog()
        paths = [o['current_path'] for o in self.current('asset')]
        if len(paths) != len(set(paths)):
            raise ValueError('duplicate current asset path')

    def namespace_counts(self):
        result = {n: {'methods': 0, 'generated': 0, 'entrypoints': 0} for n in sorted(NAMESPACES)}
        for method in self.current('method'):
            result[method['namespace']]['methods'] += 1
            result[method['namespace']]['generated'] += int(method['generated'])
        for entry in self.current('entrypoint'):
            result[entry['namespace']]['entrypoints'] += 1
        return result

    def scope(self):
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location('_owned_asset_scope', Path(__file__).with_name('asset_scope.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module.Scope(self)

    def partition_assets(self, observations):
        rows = list(observations)
        seen = set()
        for row in rows:
            path = relative(row['path']); sha(row['sha256'])
            if path in seen:
                raise ValueError('duplicate asset observation: ' + path)
            seen.add(path)
        return self.scope().partition(rows)

    def reconcile_assets(self, observations, *, external_manifest=None):
        rows = list(observations)
        report = self.partition_assets(rows)
        included = set(report['in_scope_paths'])
        actual = {row['path']: row for row in rows if row['path'] in included}
        expected = {o['current_path']: o for o in self.current('asset')}
        report.update(missing=sorted(expected.keys()-actual.keys()),
                      extra=sorted(actual.keys()-expected.keys()), drift=[], external_identity_missing=[])
        for path in expected.keys() & actual.keys():
            obj = expected[path]
            if obj['content']['algorithm'] == 'sha256':
                if obj['content']['value'] != actual[path]['sha256']:
                    report['drift'].append(path)
            else:
                row = (external_manifest or {}).get(path)
                if row != actual[path] or not all(k in row for k in ('git_mode', 'actual_mode')):
                    report['external_identity_missing'].append(path)
        report['drift'].sort(); report['external_identity_missing'].sort()
        report['ok'] = not any(report[key] for key in ('missing', 'extra', 'unknown', 'drift', 'external_identity_missing'))
        if not report['ok']:
            # Exception carries the same complete ownership boundary report as success.
            import importlib.util
            from pathlib import Path
            spec = importlib.util.spec_from_file_location('_scope_reject', Path(__file__).with_name('asset_scope.py'))
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            raise module.ReconciliationError(report)
        return report

    def reconcile_methods(self, namespace, receipt):
        if namespace not in NAMESPACES or receipt.get('schema_version') != 1 or receipt.get('namespace') != namespace or not receipt.get('complete') or receipt.get('errors'):
            raise ValueError('incomplete/unknown discovery receipt')
        actual = {}
        for row in receipt['methods']:
            key = (row['module_path'], row['runtime_id'])
            if key in actual:
                raise ValueError('duplicate discovery identity')
            actual[key] = row
        expected = {(self.bound(o['module'])['current_path'], o['runtime_id']): o for o in self.current('method') if o['namespace'] == namespace}
        if actual.keys() != expected.keys():
            raise ValueError('method missing/extra')
        for key, obj in expected.items():
            row = actual[key]
            owner = self.bound(obj['module'])
            if row['definition'] != obj['definition'] or row['generated'] != obj['generated'] or row['module_sha256'] != owner['content'].get('value'):
                raise ValueError('method source drift')
        return True

    def _history_module(self, name):
        import importlib.util
        from pathlib import Path
        spec = importlib.util.spec_from_file_location('_owned_' + name, Path(__file__).with_name(name + '.py'))
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        return module

    def read_history(self, obj):
        if obj['kind'] not in ('historical-audit-record', 'historical-finding'):
            raise ValueError('not historical evidence')
        import copy
        binding = self._history_module('history_binding')
        refs = binding.shape(obj)
        # Resolve and check content-bound references on every call, including cache hits.
        methods = []
        for ref in refs:
            method = self.bound(ref, 'method')
            methods.append((method, self.bound(method['module'], 'asset')))
        source = self.bound(obj['source'], 'source')
        if not hasattr(self, '_history_reader'):
            reader = self._history_module('source_reader')
            self._history_reader = reader.DocumentReader(root=self.registry.root, repositories=self.registry.repositories)
        reader = self._history_reader
        document = reader._document(source)
        row = reader._bound_value(document, obj['row_pointer'], obj['original_row_sha256'])
        reader._bound_value(document, obj['scope_pointer'], obj['scope_sha256'])
        binding.validate(obj, document, row, methods)
        return copy.deepcopy(row)

    def reconcile_listing(self, entrypoint, receipt):
        entry = self.bound(entrypoint, 'entrypoint')
        if entry['collector'] != 'binary-listing' or entry['namespace'] != 'rust-tests':
            raise ValueError('not a Rust binary listing')
        source = self.bound(entry['listing_source'], 'source')
        expected = json.loads(self.registry.read_source(source))
        for value in (expected, receipt):
            if value.get('schema_version') != 1 or value.get('namespace') != 'rust-tests' or not value.get('complete') or value.get('errors'):
                raise ValueError('incomplete Rust listing')
            sha(value.get('binary_sha256'))
            if not isinstance(value.get('runtime_ids'), list) or len(value['runtime_ids']) != len(set(value['runtime_ids'])):
                raise ValueError('duplicate/invalid Rust listing')
        if expected['binary_sha256'] != receipt['binary_sha256'] or set(expected['runtime_ids']) != set(receipt['runtime_ids']):
            raise ValueError('Rust listing missing/extra or binary drift')
        return len(receipt['runtime_ids'])

    def reconcile_rust_listing(self, receipt, *, profile):
        """Reconcile every owned native target against one registered profile."""
        return self._history_module('rust_listing').reconcile(self, receipt, profile)

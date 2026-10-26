"""Versioned component ownership over a complete independent observation."""
INCLUDED = ['.agents/', '.github/', 'docs/', 'evas/', 'experiments/', 'scripts/']
EXTERNAL = [{'prefix': 'benchmark/', 'owner': 'benchmark'}]

class ReconciliationError(ValueError):
    def __init__(self, report):
        self.report = report
        super().__init__('asset reconciliation rejected: ' + str({k: report[k] for k in ('missing', 'extra', 'unknown', 'drift', 'external_identity_missing')}))

class Scope:
    def __init__(self, catalog):
        self.catalog = catalog
        self.policy = catalog.registry.data.get('asset_scope')
        self.bridges = {}
        if self.policy is None:
            self.id = 'legacy-all-tracked-v1'
            return
        p = self.policy
        if not isinstance(p, dict) or set(p) != {'schema_version', 'id', 'owner', 'included_prefixes', 'root_files', 'external_components', 'bridges'}:
            raise ValueError('unknown asset scope schema')
        if type(p['schema_version']) is not int or p['schema_version'] != 1 or p['id'] != 'EVAS-scope-v1' or p['owner'] != 'evas' or p['included_prefixes'] != INCLUDED or p['root_files'] != 'included' or p['external_components'] != EXTERNAL or not isinstance(p['bridges'], list):
            raise ValueError('unsupported asset scope policy/version')
        self.id = p['id']
        for bridge in p['bridges']:
            if not isinstance(bridge, dict) or set(bridge) != {'path', 'owner', 'reason', 'source', 'consumers'}:
                raise ValueError('unknown asset bridge schema')
            path = bridge['path']
            if not isinstance(path, str) or not path.startswith('benchmark/') or path in self.bridges or not isinstance(bridge['reason'], str) or not bridge['reason'].strip() or bridge['owner'] != 'benchmark':
                raise ValueError('bridge must name one exact benchmark-owned path')
            if not isinstance(bridge['consumers'], list) or not bridge['consumers']:
                raise ValueError('bridge requires explicit bound partial consumers')
            for ref in [bridge['source'], *bridge['consumers']]:
                if not isinstance(ref, dict) or set(ref) != {'id', 'version', 'sha256'}:
                    raise ValueError('bridge reference schema must be exact')
            self.catalog.bound(bridge['source'], 'source')
            if len({str(sorted(ref.items())) for ref in bridge['consumers']}) != len(bridge['consumers']):
                raise ValueError('duplicate bridge consumers')
            for ref in bridge['consumers']:
                self.catalog.bound(ref)
            self.bridges[path] = bridge

    def classification(self, path):
        if self.policy is None:
            return 'included', None
        if path in self.bridges:
            return 'bridge', 'benchmark'
        if '/' not in path or any(path.startswith(prefix) for prefix in INCLUDED):
            return 'included', 'evas'
        if path.startswith('benchmark/'):
            return 'external', 'benchmark'
        return 'unknown', None

    def validate_catalog(self):
        assets = {obj['current_path']: obj for obj in self.catalog.current('asset')}
        for path, obj in assets.items():
            kind, owner = self.classification(path)
            if kind in ('unknown', 'external'):
                raise ValueError('catalog path outside declared asset scope: ' + path)
            if kind == 'bridge':
                bridge = self.bridges[path]
                if obj['consumer_status'] != 'partial' or bridge['source'] not in obj.get('dependencies', []) or any(ref not in obj['consumers'] for ref in bridge['consumers']):
                    raise ValueError('cross-component asset requires source-bound partial consumers: ' + path)
        if set(self.bridges) - assets.keys():
            raise ValueError('declared bridge lacks current catalog asset')

    def partition(self, rows):
        report = {'scope_id': self.id, 'observed_total': len(rows), 'in_scope_paths': [],
                  'bridge_paths': [], 'external_owners': {}, 'unknown': []}
        for row in rows:
            path = row['path']
            kind, owner = self.classification(path)
            if kind in ('included', 'bridge'):
                report['in_scope_paths'].append(path)
                if kind == 'bridge':
                    report['bridge_paths'].append(path)
            elif kind == 'external':
                report['external_owners'].setdefault(owner, {'count': 0, 'paths': []})['paths'].append(path)
            else:
                report['unknown'].append(path)
        for key in ('in_scope_paths', 'bridge_paths', 'unknown'):
            report[key].sort()
        for owner in report['external_owners'].values():
            owner['paths'].sort(); owner['count'] = len(owner['paths'])
        report['in_scope_count'] = len(report['in_scope_paths'])
        report['bridge_count'] = len(report['bridge_paths'])
        report['unknown_count'] = len(report['unknown'])
        return report

"""Reconcile independent observations against the same version-bound Registry."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True); p.add_argument('--registry-data', type=Path, required=True)
    p.add_argument('--assets', type=Path); p.add_argument('--methods', type=Path); p.add_argument('--namespace')
    a = p.parse_args()
    spec = importlib.util.spec_from_file_location('owned_registry', a.root/'evas/capabilities/registry.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    catalog = module.load(a.registry_data, root=a.root).catalog()
    if not a.assets and not a.methods:
        p.error('at least one actual observation is required')
    asset_report = None
    if a.assets:
        receipt = json.loads(a.assets.read_text())
        if receipt.get('schema_version') != 1 or receipt.get('producer') != 'capabilities.observe-assets-v1' or receipt.get('scope') != {'kind': 'all-tracked-regular-checkout-files', 'untracked': 'excluded-explicitly'}:
            raise ValueError('unknown asset observation scope/schema')
        rows = receipt['assets']
        try:
            asset_report = catalog.reconcile_assets(rows, external_manifest={row['path']: row for row in rows})
        except ValueError as error:
            if not hasattr(error, 'report'):
                raise
            print(json.dumps({'reconciled': False, 'assets': error.report}, sort_keys=True))
            return 1
    if a.methods:
        catalog.reconcile_methods(a.namespace, json.loads(a.methods.read_text()))
    print(json.dumps({'reconciled': True, 'assets': asset_report, 'namespaces': catalog.namespace_counts()}, sort_keys=True))

if __name__ == '__main__':
    sys.exit(main() or 0)

"""Real generator fixture for derived support views. No catalog rebuild and no simulator."""
import ast
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = (
    'evas/capabilities/generated/support-facts.json',
    'evas/capabilities/generated/support.md',
)
PRIOR = (
    'evas/capabilities/registry.json',
    'evas/capabilities/generated/comparison.md',
    'evas/capabilities/generated/paper.md',
    'evas/capabilities/generated/normative.md',
    'evas/docs/development/TRACEABILITY.md',
)
EXTERNAL = {
    'algorithm': 'external-input-manifest',
    'scope': 'actual-execution-inputs',
    'producer': 'capabilities.observe-assets-v1',
}


def load_generator():
    path = ROOT / 'scripts/capabilities/generate_catalog.py'
    spec = importlib.util.spec_from_file_location('catalog_derived_generator', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DerivedSupportOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = load_generator()
        legacy_path = ROOT / 'evas/capabilities/data/historical-comparison.json'
        cls.legacy = json.loads(legacy_path.read_text())
        cls.paths = cls.generator.generated_output_paths(cls.legacy)
        cls.metadata = {'evas/capabilities/data/registry.json',
                        *('evas/capabilities/data/' + name for name in cls.generator.PARTS)}

    def test_real_historical_nodes_keep_old_outputs_and_derive_both_support_views(self):
        node_pages = {path for path in self.paths
                      if path.startswith('evas/capabilities/') and path.endswith('/README.md')}
        self.assertEqual(node_pages, {'evas/capabilities/' + node['id'] + '/README.md'
                                      for node in self.legacy['nodes']})
        self.assertGreater(len(node_pages), 0)
        for path in (*SUPPORT, *PRIOR):
            with self.subTest(path=path):
                role, content = self.generator.external_asset_identity(path, self.paths, self.metadata)
                self.assertEqual(role, 'derived')
                self.assertEqual(content, EXTERNAL)
                self.assertNotIn('value', content)
        for path in SUPPORT:
            self.assertNotIn(path, self.metadata)
            self.assertNotIn(path, self.generator.GOVERNANCE)
        governance = next(iter(self.generator.GOVERNANCE))
        self.assertEqual(self.generator.external_asset_identity(
            governance, self.paths, self.metadata)[0], 'governance')
        self.assertEqual(self.generator.external_asset_identity(
            'evas/capabilities/data/registry.json', self.paths, self.metadata)[0], 'catalog-meta')
        self.assertIsNone(self.generator.external_asset_identity(
            'evas/src/evas/compiler.py', self.paths, self.metadata))

    def test_previous_support_asset_version_remains_beside_the_external_identity(self):
        prior = {
            'schema_version': 1, 'id': 'asset:support-facts', 'version': 'prior-sha',
            'kind': 'asset', 'current_path': SUPPORT[0],
            'content': {'algorithm': 'sha256', 'value': 'a' * 64},
        }
        current = {
            **prior, 'version': 'external-version', 'content': dict(EXTERNAL),
        }
        merged = {(prior['id'], prior['version']): prior}
        migrations = []
        pointer = {}
        self.generator.retain_generated_object(
            merged, migrations, pointer, {prior['id']: prior}, current)
        self.assertEqual(merged[(prior['id'], prior['version'])]['content']['algorithm'], 'sha256')
        self.assertEqual(merged[(current['id'], current['version'])]['content'], EXTERNAL)
        self.assertEqual(pointer[prior['id']], current['version'])
        self.assertEqual(migrations, [{
            'id': prior['id'],
            'previous': self.generator.ref(prior),
            'current': self.generator.ref(current),
            'reason': 'version-bound regenerated content; previous object retained',
        }])
        conflict = {**current, 'kind': 'asset-changed'}
        with self.assertRaisesRegex(ValueError, 'conflicting reused object version'):
            self.generator.retain_generated_object(merged, [], {}, {prior['id']: prior}, conflict)

    def test_historical_selection_loops_remain_in_the_generator(self):
        tree = ast.parse((ROOT / 'scripts/capabilities/generate_catalog.py').read_text())
        build = next(node for node in tree.body
                     if isinstance(node, ast.FunctionDef) and node.name == 'build')
        loops = [node for node in ast.walk(build) if isinstance(node, ast.For)
                 and isinstance(node.target, ast.Tuple)]
        targets = [[item.id for item in node.target.elts if isinstance(item, ast.Name)]
                   for node in loops]
        self.assertIn(['index', 'row'], targets)
        self.assertIn(['group', 'protocol', 'key', 'scope_pointer'], targets)


if __name__ == '__main__':
    unittest.main()

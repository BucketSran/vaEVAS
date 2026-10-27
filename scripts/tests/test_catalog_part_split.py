"""Part files for methods and history stay deterministic on synthetic objects."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class CatalogPartSplitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generator = module('catalog_part_generator', ROOT / 'scripts/capabilities/generate_catalog.py')
        cls.registry = module('catalog_part_registry', ROOT / 'evas/capabilities/registry.py')

    def test_slot_is_sha256_prefix_and_part_count_is_fixed(self):
        self.assertEqual(self.generator.PART_COUNT, 16)
        vectors = (('catalog-part-split:fixed', 8), ('method:stable', 15), ('history:fixed', 6))
        for object_id, slot in vectors:
            digest = hashlib.sha256(object_id.encode('utf-8')).digest()
            self.assertEqual(int.from_bytes(digest[:8], 'big') % 16, slot)
            self.assertEqual(self.generator.part_slot(object_id), slot)
        names = list(self.generator.PARTS)
        self.assertEqual(names, [name for name, _kind in self.generator.ordered_parts()])
        self.assertEqual(names[:2], ['catalog-sources.json', 'asset-index.json'])
        self.assertEqual(names[2:18], ['method-index-%02d.json' % index for index in range(16)])
        self.assertEqual(names[18], 'entrypoint-index.json')
        self.assertEqual(names[19:], ['historical-index-%02d.json' % index for index in range(16)])
        self.assertNotIn('method-index.json', names)
        self.assertNotIn('historical-index.json', names)
        metadata = {'evas/capabilities/data/registry.json',
                    *('evas/capabilities/data/' + name for name in self.generator.PARTS)}
        self.assertEqual(len(metadata), 1 + len(names))
        self.assertIn('evas/capabilities/data/method-index-00.json', metadata)
        self.assertIn('evas/capabilities/data/historical-index-15.json', metadata)
        self.assertNotIn('evas/capabilities/data/method-index.json', metadata)

    def test_same_id_stays_together_and_empty_parts_remain(self):
        objects = self.objects()
        buckets = self.generator.partition_objects(list(reversed(objects)))
        self.assertEqual(set(buckets), set(self.generator.PARTS))
        method_name = 'method-index-15.json'
        history_name = 'historical-index-06.json'
        self.assertEqual([obj['version'] for obj in buckets[method_name]], ['1', '2'])
        self.assertEqual({obj['id'] for obj in buckets[method_name]}, {'method:stable'})
        self.assertEqual([obj['version'] for obj in buckets[history_name]], ['1', '2'])
        self.assertEqual({obj['id'] for obj in buckets[history_name]}, {'history:fixed'})
        self.assertEqual(buckets['method-index-00.json'], [])
        self.assertEqual(buckets['historical-index-00.json'], [])
        self.assertEqual(len(buckets['catalog-sources.json']), 1)
        self.assertEqual(len(buckets['asset-index.json']), 1)
        self.assertEqual(len(buckets['entrypoint-index.json']), 1)
        self.assertEqual(self.generator.partition_objects(objects), buckets)
        rotated = objects[1:] + objects[:1]
        self.assertEqual(self.generator.partition_objects(rotated), buckets)

    def test_written_bytes_ignore_insertion_order_and_load_returns_the_same_objects(self):
        objects = self.objects()
        orders = (objects, list(reversed(objects)), objects[1:] + objects[:1])
        rendered = [self.render(order) for order in orders]
        self.assertEqual(rendered[0], rendered[1])
        self.assertEqual(rendered[0], rendered[2])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = root / 'evas/capabilities/data'
            for name, payload in rendered[0].items():
                target = data / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
            self.write_sidecars(data)
            empty = json.loads((data / 'method-index-00.json').read_text())
            self.assertEqual(empty, {'schema_version': 1, 'kind': 'methods', 'objects': []})
            loaded = self.registry.load(data, root=root)
            self.assertEqual(set(loaded.objects), {(obj['id'], obj['version']) for obj in objects})
            self.assertEqual(loaded.data['object_parts'], list(self.generator.PARTS))
            for obj in objects:
                self.assertEqual(loaded.objects[(obj['id'], obj['version'])], obj)

    def test_build_keeps_the_existing_history_loops_and_calls_partition(self):
        tree = ast.parse((ROOT / 'scripts/capabilities/generate_catalog.py').read_text())
        build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
        calls = [node.func.id for node in ast.walk(build)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertIn('partition_objects', calls)
        def loops(names):
            return [node for node in build.body if isinstance(node, ast.For)
                    and isinstance(node.target, ast.Tuple)
                    and [item.id for item in node.target.elts] == names]
        self.assertEqual(len(loops(['index', 'row'])), 1)
        self.assertEqual(len(loops(['group', 'protocol', 'key', 'scope_pointer'])), 1)

    def objects(self):
        reference = self.registry.reference
        source = {'schema_version': 1, 'id': 'source:fixture', 'version': '1', 'kind': 'source',
                  'status': 'active', 'origin': 'fixture-only', 'availability': 'repository-contained',
                  'locator': {'kind': 'embedded', 'value': {'data': 'fixture'}},
                  'sha256': self.registry.digest({'data': 'fixture'}), 'dependencies': []}
        entry = {'schema_version': 1, 'id': 'entry:python', 'version': '1', 'kind': 'entrypoint',
                 'status': 'active', 'namespace': 'python-regression', 'collector': 'unittest',
                 'start': 'evas/tests', 'pattern': 'test*.py', 'dependencies': []}
        asset = {'schema_version': 1, 'id': 'asset:stable', 'version': '1', 'kind': 'asset',
                 'status': 'active', 'namespace': 'EVAS-assets', 'current_path': 'evas/tests/test_demo.py',
                 'content': {'algorithm': 'sha256', 'value': 'a' * 64},
                 'role': {'status': 'pending', 'reason': 'fixture role not reviewed'},
                 'consumers': [reference(entry)], 'consumer_status': 'pending', 'location_history': [],
                 'dependencies': [reference(source)]}
        def method(version):
            return {'schema_version': 1, 'id': 'method:stable', 'version': version, 'kind': 'method',
                    'status': 'active', 'namespace': 'python-regression',
                    'runtime_id': 'test_demo.Case.test_one', 'module': reference(asset),
                    'definition': {'path': asset['current_path'], 'sha256': 'b' * 64, 'line': 1,
                                   'name': 'test_one'},
                    'generated': False, 'entrypoints': [reference(entry)], 'runtime_history': [],
                    'semantic_status': 'pending', 'dependencies': [reference(asset)]}
        def history(version):
            current = method('2')
            return {'schema_version': 1, 'id': 'history:fixed', 'version': version,
                    'kind': 'historical-audit-record', 'status': 'active', 'source': reference(source),
                    'row_pointer': '/rows/0', 'original_row_sha256': 'c' * 64,
                    'scope_pointer': '/summary/scope', 'scope_sha256': 'd' * 64,
                    'identity_binding': 'bound', 'history_protocol': 'evas-method-audit-3257-v1',
                    'method': reference(current),
                    'alignment': {'status': 'pending', 'reason': 'fixture alignment is not a match'},
                    'qualification_status': 'not-granted', 'dependencies': [reference(source)]}
        return [source, entry, asset, method('1'), method('2'), history('1'), history('2')]

    def render(self, objects):
        buckets = self.generator.partition_objects(objects)
        rendered = {}
        for name, rows in buckets.items():
            rendered[name] = (json.dumps({'schema_version': 1, 'kind': self.generator.PARTS[name], 'objects': rows},
                                         ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        header = {'schema_version': 1, 'objects': [], 'object_parts': list(self.generator.PARTS),
                  'current': {obj['id']: '2' if obj['id'] in ('method:stable', 'history:fixed') else obj['version']
                              for obj in objects}}
        rendered['registry.json'] = (json.dumps(header, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
        return rendered

    def write_sidecars(self, data):
        empty = self.registry.digest([])
        payloads = {
            'source-inventory.json': {'items': []},
            'dispositions.json': {'items': []},
            'boundary-audit.json': {'normalized_inventory_identity': empty},
            'target-scope.json': {},
            'language-profile.json': {'base': '2.4', 'selected_changes': [], 'changes': {}},
        }
        for name, payload in payloads.items():
            (data / name).write_text(json.dumps(payload))


if __name__ == '__main__':
    unittest.main()

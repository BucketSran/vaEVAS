"""Historical identity survives a move without reinterpreting the real audit."""
import copy
import ast
import importlib.util
import json
from pathlib import Path
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class HistoricalMethodSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = module('history_selection_registry', ROOT / 'evas/capabilities/registry.py')
        cls.generator = module('history_selection_generator', ROOT / 'scripts/capabilities/generate_catalog.py')
        registry = cls.api.load(ROOT / 'evas/capabilities/data', root=ROOT, repositories={'vaevas': ROOT})
        catalog = registry.catalog()
        cls.history = catalog.current('historical-audit-record')[0]
        cls.old_method = catalog.bound(cls.history['method'])
        cls.old_owner = catalog.bound(cls.old_method['module'])
        cls.source = catalog.bound(cls.history['source'])
        cls.row = catalog.read_history(cls.history)
        cls.audit_scope = json.loads(registry.read_source(cls.source))['summary']['scope']
        cls.findings = catalog.current('historical-finding')
        cls.finding_documents = {}
        cls.finding_sources = {}
        cls.finding_methods = {}
        cls.finding_owners = {}
        for history in cls.findings:
            source = catalog.bound(history['source'])
            cls.finding_documents[source['origin']] = json.loads(registry.read_source(source))
            cls.finding_sources[source['origin']] = source
            for ref in history['methods']:
                method = catalog.bound(ref)
                owner = catalog.bound(method['module'])
                cls.finding_methods[method['runtime_id']] = method
                cls.finding_owners[owner['current_path']] = owner

    def moved(self):
        owner = copy.deepcopy(self.old_owner)
        owner.update(version='moved-owner', current_path='evas/tests/review_moved/' + Path(owner['current_path']).name)
        method = copy.deepcopy(self.old_method)
        method.update(version='moved-method', module=self.api.reference(owner))
        method['definition']['path'] = owner['current_path']
        return owner, method

    def test_move_or_runtime_rename_keeps_exact_original_version_and_raw_row(self):
        for renamed in (False, True):
            with self.subTest(runtime_renamed=renamed):
                owner, current = self.moved()
                if renamed:
                    current['runtime_id'] += '_renamed'
                selected, selected_owner, scope = self.generator.select_audited_method(
                    self.row, current, [self.old_owner, self.old_method], [owner])
                self.assertEqual(selected, self.old_method)
                self.assertEqual(selected_owner, self.old_owner)
                self.assertEqual(scope, 'retained-original-method-version')
                tree = ast.parse((ROOT / 'scripts/capabilities/generate_catalog.py').read_text())
                build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
                loop = next(node for node in build.body if isinstance(node, ast.For)
                            and isinstance(node.target, ast.Tuple)
                            and [item.id for item in node.target.elts] == ['index', 'row'])
                context = dict(self.generator.__dict__, audit={'rows': [self.row],
                    'summary': {'scope': self.audit_scope}}, by_runtime={current['runtime_id']: current},
                    assets={owner['current_path']: owner}, previous_objects=[self.old_owner, self.old_method],
                    histories=[], s=self.source)
                exec(compile(ast.Module(body=[loop], type_ignores=[]), 'actual-generator-audit-loop', 'exec'), context)
                history = context['histories'][0]
                history['row_pointer'] = self.history['row_pointer']
                self.assertEqual(history['method'], self.api.reference(self.old_method))
                self.assertEqual(history['alignment']['scope'], scope)
                objects = [self.source, self.old_owner, self.old_method, owner, current]
                registry = types.SimpleNamespace(objects={(o['id'], o['version']): o for o in objects},
                    root=ROOT, repositories={'vaevas': ROOT})
                self.assertEqual(self.api._owned('asset_catalog').Catalog(registry).read_history(history), self.row)

    def test_equal_method_hash_cannot_borrow_wrong_module_identity(self):
        owner, current = self.moved()
        wrong_owner = copy.deepcopy(self.old_owner)
        wrong_owner['version'] = 'wrong-owner'
        wrong_owner['content']['value'] = '0' * 64
        wrong_method = copy.deepcopy(self.old_method)
        wrong_method['module'] = self.api.reference(wrong_owner)
        with self.assertRaisesRegex(ValueError, 'original source identity'):
            self.generator.select_audited_method(self.row, current,
                [wrong_owner, wrong_method], [owner])

    def test_all_original_finding_protocols_keep_paths_after_file_moves(self):
        tree = ast.parse((ROOT / 'scripts/capabilities/generate_catalog.py').read_text())
        build = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'build')
        specs = next(node for node in build.body if isinstance(node, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'specs' for t in node.targets))
        loop = next(node for node in build.body if isinstance(node, ast.For)
                    and isinstance(node.target, ast.Tuple)
                    and [item.id for item in node.target.elts] == ['group', 'protocol', 'key', 'scope_pointer'])
        for history in self.findings:
            with self.subTest(protocol=history['history_protocol']):
                target = self.finding_methods[next(m['runtime_id'] for m in self.finding_methods.values()
                    if self.api.reference(m) == history['methods'][0])]
                old_owner = self.finding_owners[target['definition']['path']]
                new_owner = copy.deepcopy(old_owner)
                new_owner.update(version='finding-moved-owner',
                    current_path='evas/tests/review_moved/' + Path(old_owner['current_path']).name)
                current = copy.deepcopy(self.finding_methods)
                for method in current.values():
                    if method['module'] == self.api.reference(old_owner):
                        method['module'] = self.api.reference(new_owner)
                        method['definition']['path'] = new_owner['current_path']
                        method['version'] = 'finding-moved-method'
                assets = dict(self.finding_owners)
                del assets[old_owner['current_path']]
                assets[new_owner['current_path']] = new_owner
                previous = [*self.finding_methods.values(), *self.finding_owners.values()]
                def original(group, path):
                    self.assertEqual(path, self.finding_sources[group]['locator']['path'])
                    return self.finding_documents[group], self.finding_sources[group]
                context = dict(self.generator.__dict__, original=original,
                    prefix='evas/capabilities/history/', by_runtime=current, previous_objects=previous,
                    assets=assets, histories=[], api=self.api)
                exec(compile(ast.Module(body=[specs, loop], type_ignores=[]),
                             'actual-generator-finding-loop', 'exec'), context)
                objects = [*previous, *assets.values(), *current.values(), *self.finding_sources.values()]
                registry = types.SimpleNamespace(objects={(o['id'], o['version']): o for o in objects},
                    root=ROOT, repositories={'vaevas': ROOT})
                catalog = self.api._owned('asset_catalog').Catalog(registry)
                for generated in context['histories']:
                    old = next(h for h in self.findings if h['id'] == generated['id'])
                    self.assertEqual(generated['methods'], old['methods'])
                    self.assertEqual(generated['alignment']['status'], 'pending')
                    self.assertEqual(catalog.read_history(generated), catalog.read_history(old))

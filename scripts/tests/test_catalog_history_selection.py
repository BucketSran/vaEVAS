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

"""Inventory CLI distinguishes explicit reasons, wrappers and source-only evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'diagnostic_inventory.py'


class InventoryCLI(unittest.TestCase):
    def test_structural_inventory_has_no_line_based_identity_or_message_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            py = root / 'evas/src/evas'
            rs = root / 'evas/rust_core/ir/src'
            py.mkdir(parents=True)
            rs.mkdir(parents=True)
            source = '''from evas.errors import CompileError

def fail(message, code='compile_error'):
    raise CompileError(message, code=code)
def compile():
    fail('resource budget unsupported', code='future_reason')
    fail('invalid input')
'''
            (py / 'probe.py').write_text(source)
            (rs / 'lib.rs').write_text('''fn run() { Error::new("future_failure", "unsupported"); if error.kind == "invalid_ir" {} }
#[cfg(test)] mod tests { fn probe() { Error::new("invalid_ir", "test"); } }
fn after_test() { Error::new("invalid_ir", "actual"); }
''')
            def inventory():
                result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(root)],
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                return json.loads(result.stdout)['entries']
            first = inventory()
            self.assertTrue(all(row['evidence'] == 'source_audit' for row in first))
            reasons = [row['reason'] for row in first]
            self.assertIn('future_reason', reasons)
            self.assertIn('compile_error', reasons)
            self.assertEqual(reasons.count('invalid_ir'), 1)
            self.assertTrue(all(row['category'] == 'unknown' for row in first if row['reason'] and row['reason'].startswith('future')))
            (py / 'probe.py').write_text('\n\n' + source)
            second = inventory()
            self.assertEqual([row['id'] for row in first], [row['id'] for row in second])

    def test_rust_error_factories_local_import_alias_and_qualified_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rust = root / 'evas/rust_core/src'
            rust.mkdir(parents=True)
            (rust / 'event_accuracy.rs').write_text('''pub(crate) fn unresolved(message: &str) -> Error {
    Error::new("event_resolution", message)
}
fn live() { unresolved("direct"); }
#[cfg(test)] fn absent(message: &str) -> Error { Error::new("invalid_ir", message) }
''')
            (rust / 'consumer.rs').write_text('''use crate::event_accuracy::{unresolved as uncertain};
use crate::event_accuracy as accuracy;
fn run() { uncertain("alias"); accuracy::unresolved("module alias");
crate::event_accuracy::unresolved("qualified"); }
fn invalid(message: &str) -> bool { false }
fn negative() { invalid("ordinary function is not an Error factory"); }
fn transport() { input.map_err(|error| error); }
''')
            (rust / 'future.rs').write_text('''use crate::ir::Error as Failure;
fn construct(message: &str) -> Failure { Failure::new("future_resolution", message) }
fn run() { construct("unknown reason stays unknown"); }
''')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(root)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            entries = json.loads(result.stdout)['entries']
            self.assertEqual(sum(row['form'] == 'conversion' for row in entries), 1)
            calls = [row for row in entries if row['form'] == 'wrapper_call']
            self.assertEqual(len(calls), 5)
            self.assertEqual([row['reason'] for row in calls].count('event_resolution'), 4)
            future = [row for row in calls if row['reason'] == 'future_resolution']
            self.assertEqual(len(future), 1)
            self.assertEqual(future[0]['category'], 'unknown')
            self.assertTrue(all('ordinary function' not in row['expression'] for row in calls))
            self.assertTrue(all('absent' not in row['function'] for row in entries))

    def test_current_audited_rust_wrapper_callers_are_in_the_public_inventory(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = json.loads(result.stdout)['entries']
        for module in ('event_accuracy', 'dynamic_roots', 'transition', 'schedule',
                       'pwl', 'slew', 'affine_bounds', 'continuous'):
            rows = [row for row in entries if row['path'] == f'evas/rust_core/src/{module}.rs'
                    and row['form'] == 'wrapper_call']
            self.assertTrue(rows, module)
        for module, function in (('dynamic_roots', 'strict_sign'), ('transition', 'deadline')):
            self.assertTrue(any(row['path'] == f'evas/rust_core/src/{module}.rs'
                                and row['function'] == function and row['form'] == 'wrapper_call'
                                for row in entries), (module, function))

    def test_conditional_factory_does_not_borrow_its_only_literal_branch_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rust = root / 'evas/rust_core/src'
            rust.mkdir(parents=True)
            (rust / 'mixed.rs').write_text('''fn mixed(flag: bool, existing: Error) -> Error {
if flag { Error::new("invalid_ir", "one branch") } else { existing }
}
fn run() { mixed(false, existing); }
''')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(root)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [row for row in json.loads(result.stdout)['entries'] if row['form'] == 'wrapper_call']
            self.assertEqual(len(rows), 1)
            self.assertIsNone(rows[0]['reason'])
            self.assertEqual(rows[0]['category'], 'unknown')

    def test_current_path_modules_and_named_error_closures_are_registered(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)], capture_output=True,
                                text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)['entries']
        for module, token, count in [('continuous_derivatives', 'unsupported', 2),
                                     ('continuous_initialization', 'unsupported', 1),
                                     ('implicit_dynamics', 'unsupported', 3),
                                     ('nonlinear_dynamics', 'unsupported', 4),
                                     ('continuous_derivatives', 'reject', 2), ('pwl', 'invalid', 2)]:
            actual = [row for row in rows if row['path'] == f'evas/rust_core/src/{module}.rs'
                      and row['form'] == 'wrapper_call' and row['expression'].startswith(token + ' (')]
            self.assertEqual(len(actual), count, (module, token))

    def test_path_modules_super_glob_closure_scope_and_shadowing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rust = root / 'evas/rust_core/src'
            rust.mkdir(parents=True)
            (rust / 'lib.rs').write_text('mod parent;')
            (rust / 'parent.rs').write_text('''fn factory(message: &str) -> Error {
Error::new("unsupported_operator", message)
}
#[path="odd_name.rs"] mod child;
#[path="shadow.rs"] mod shadow;
''')
            (rust / 'odd_name.rs').write_text('''use super::*;
#[path="leaf.rs"] mod nested;
fn one() { let deny = || { factory("supported provenance") }; deny(); }
fn unrelated() { let deny = || true; deny(); let value = || (1 + 2); value(); }
''')
            (rust / 'leaf.rs').write_text('''use super::*;
fn run() { factory("transitive glob"); }
''')
            (rust / 'shadow.rs').write_text('''use super::*;
fn factory(message: &str) -> bool { false }
fn run() { factory("local ordinary function shadows inherited factory"); }
''')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--root', str(root)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            rows = json.loads(result.stdout)['entries']
            calls = [row for row in rows if row['form'] == 'wrapper_call']
            self.assertEqual(len(calls), 3)
            self.assertTrue(all(row['reason'] == 'unsupported_operator' for row in calls))
            self.assertFalse(any(row['function'] == 'unrelated' or row['path'].endswith('shadow.rs') for row in calls))
            deny = next(row for row in calls if row['expression'].startswith('deny ('))
            self.assertEqual(deny['factory'], 'crate::parent::child::one::deny')
            self.assertTrue(any(row['path'].endswith('leaf.rs') and row['factory'] == 'crate::parent::factory' for row in calls))

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

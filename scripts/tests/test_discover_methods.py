"""Actual TestLoader fixtures; every test body would raise if executed."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE=Path(__file__).resolve().parents[1]/'capabilities/discover_methods.py'
spec=importlib.util.spec_from_file_location('discovery_tool',FILE)
discovery=importlib.util.module_from_spec(spec);spec.loader.exec_module(discovery)

class NativeSkipDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);(self.root/'checks').mkdir()

    def run_source(self,source):
        (self.root/'checks/test_sample.py').write_text(source)
        return discovery.discover(self.root,'checks',namespace='maintenance')

    def test_native_skip_skipif_skipunless_and_class_declaration_do_not_execute_bodies(self):
        result=self.run_source('''import unittest
class Case(unittest.TestCase):
 @unittest.skip("native skip")
 def test_skip(self):
  raise RuntimeError("BODY MUST NOT RUN")
 @unittest.skipIf(True,"native conditional")
 def test_skipif(self):
  raise RuntimeError("BODY MUST NOT RUN")
 @unittest.skipUnless(False,"native unless")
 def test_skipunless(self):
  raise RuntimeError("BODY MUST NOT RUN")
 @unittest.skipIf(False,"inactive conditional")
 def test_enabled(self):
  raise RuntimeError("BODY MUST NOT RUN")
@unittest.skip("class declaration")
class ClassSkipped(unittest.TestCase):
 def test_class(self):
  raise RuntimeError("BODY MUST NOT RUN")
''')
        self.assertTrue(result['complete'],result['errors']);self.assertEqual(len(result['methods']),5)
        self.assertEqual(result['discovered_instances'],5);self.assertEqual(result['error_count'],0)
        self.assertEqual(result['skipped_declarations'],4)
        self.assertEqual(sum('native_skip_wrapper' in r for r in result['methods']),3)
        self.assertTrue(all(r['definition']['path']=='checks/test_sample.py' for r in result['methods']))
        self.assertEqual(result['collector']['definition_profile'],'actual-code-or-registered-native-skip-v1')

    def test_custom_functools_wraps_uses_actual_wrapper_source_not_original(self):
        source='''import functools, unittest
def custom(func):
 @functools.wraps(func)
 def actual_wrapper(self):
  raise RuntimeError("CUSTOM WRAPPER MUST NOT RUN")
 return actual_wrapper
class Case(unittest.TestCase):
 @custom
 def test_custom(self):
  raise RuntimeError("ORIGINAL BODY MUST NOT RUN")
'''
        result=self.run_source(source);self.assertTrue(result['complete'],result['errors'])
        actual=result['methods'][0]
        self.assertEqual(actual['definition']['line'],3)
        self.assertNotIn('native_skip_wrapper',actual)

    def test_native_skip_outside_custom_wrapper_preserves_custom_callable_definition(self):
        source='''import functools, unittest
def custom(func):
 @functools.wraps(func)
 def actual_wrapper(self):
  raise RuntimeError("CUSTOM BODY MUST NOT RUN")
 return actual_wrapper
class Case(unittest.TestCase):
 @unittest.skip("outer native skip")
 @custom
 def test_custom(self):
  raise RuntimeError("ORIGINAL BODY MUST NOT RUN")
'''
        result=self.run_source(source);self.assertTrue(result['complete'],result['errors'])
        self.assertEqual(result['methods'][0]['definition']['line'],3)
        self.assertIn('native_skip_wrapper',result['methods'][0])

    def test_actual_factory_generated_method_identity_is_retained(self):
        result=self.run_source('''import unittest
def factory():
 def generated(self):
  raise RuntimeError("FACTORY BODY MUST NOT RUN")
 return generated
class Case(unittest.TestCase):
 test_factory=factory()
''')
        self.assertTrue(result['complete'],result['errors']);self.assertTrue(result['methods'][0]['generated'])
        self.assertEqual(result['discovered_instances'],1)

    def test_import_error_retains_all_instances_loader_errors_and_resolved_methods(self):
        (self.root/'checks/test_broken.py').write_text('raise ImportError("fixture import failure")\n')
        result=self.run_source('''import unittest
class Case(unittest.TestCase):
 def test_good(self):
  raise RuntimeError("BODY MUST NOT RUN")
''')
        self.assertFalse(result['complete']);self.assertEqual(result['discovered_instances'],2)
        self.assertEqual(len(result['methods']),1);self.assertEqual(len(result['unresolved_instances']),1)
        self.assertEqual(result['loader_error_count'],1);self.assertEqual(result['error_count'],len(result['errors']))

    def test_tampered_native_wrapped_pointer_is_explicitly_incomplete(self):
        result=self.run_source('''import unittest
class Case(unittest.TestCase):
 @unittest.skip("native")
 def test_original(self):
  raise RuntimeError("BODY MUST NOT RUN")
def replacement(self):
 raise RuntimeError("REPLACEMENT BODY MUST NOT RUN")
Case.test_original.__wrapped__=replacement
''')
        self.assertFalse(result['complete']);self.assertEqual(result['discovered_instances'],1)
        self.assertEqual(len(result['unresolved_instances']),1)

    def test_import_stdout_and_stderr_are_actual_captured_transport(self):
        result=self.run_source('''import sys, unittest
print("ACTUAL IMPORT STDOUT")
sys.stderr.write("ACTUAL IMPORT STDERR\\n")
class Case(unittest.TestCase):
 def test_body(self):
  raise RuntimeError("BODY MUST NOT RUN")
''')
        self.assertTrue(result['complete'],result['errors'])
        self.assertIn('ACTUAL IMPORT STDOUT',result['transport']['stdout'])
        self.assertEqual(result['transport']['stderr'],'ACTUAL IMPORT STDERR\n')
        self.assertEqual(result['collector']['source_relationship'],'external-tool-override')
        self.assertTrue(result['environment']['python_version'])

    def test_custom_wrapper_outside_native_skip_is_not_stripped(self):
        source='''import functools, unittest
def custom(func):
 @functools.wraps(func)
 def actual_wrapper(self):
  raise RuntimeError("CUSTOM BODY MUST NOT RUN")
 return actual_wrapper
class Case(unittest.TestCase):
 @custom
 @unittest.skip("inner native skip")
 def test_custom(self):
  raise RuntimeError("ORIGINAL BODY MUST NOT RUN")
'''
        result=self.run_source(source);self.assertTrue(result['complete'],result['errors'])
        self.assertEqual(result['methods'][0]['definition']['line'],3)
        self.assertNotIn('native_skip_wrapper',result['methods'][0])
        self.assertTrue(result['methods'][0]['skip_declaration']['declared'])
